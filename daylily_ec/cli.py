"""CLI entry point for daylily-ec built on cli-core-yo v2."""

from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import typer
from cli_core_yo import output
from cli_core_yo.app import create_app, run
from cli_core_yo.runtime import get_context
from cli_core_yo.spec import (
    BackendDetectSpec,
    BackendValidationSpec,
    CliSpec,
    EnvSpec,
    ExecutionBackendSpec,
    PluginSpec,
    PolicySpec,
    PrereqSpec,
    RuntimeSpec,
    XdgSpec,
)

from daylily_ec._registry_v2 import (
    DAYLILY_EC_RUNTIME_TAG,
    EXEMPT,
    REQUIRED_JSON,
    REQUIRED_LONG_RUNNING,
    REQUIRED_MUTATING_INTERACTIVE,
    REQUIRED_MUTATING_LONG_RUNNING,
    register_group_commands,
    register_root_command,
    required_policy,
)
from daylily_ec.resources import ensure_extracted


def _dayec_info_hook() -> list[tuple[str, str]]:
    return [("Project Root", str(Path(__file__).resolve().parents[1]))]


spec = CliSpec(
    prog_name="daylily-ec",
    app_display_name="Daylily Ephemeral Cluster",
    dist_name="daylily-ephemeral-cluster",
    root_help=(
        "Create and manage ephemeral AWS ParallelCluster environments for bioinformatics workloads."
    ),
    xdg=XdgSpec(app_dir_name="daylily"),
    policy=PolicySpec(),
    env=EnvSpec(
        active_env_var="DAYLILY_EC_ACTIVE",
        project_root_env_var="DAYLILY_EC_REPO_ROOT",
        activate_script_name="source ./activate",
        deactivate_script_name="conda deactivate",
        preferred_backend="day-ec-conda",
    ),
    runtime=RuntimeSpec(
        supported_backends=[
            ExecutionBackendSpec(
                name="day-ec-conda",
                kind="conda",
                entry_guidance="source ./activate",
                detect=BackendDetectSpec(env_vars=("CONDA_PREFIX",)),
                validation=BackendValidationSpec(env_vars=("CONDA_PREFIX",)),
            )
        ],
        default_backend="day-ec-conda",
        guard_mode="advisory",
        prereqs=[
            PrereqSpec(
                key="day-ec-conda-active-env",
                kind="env_var",
                value="CONDA_DEFAULT_ENV",
                help="Activate DAY-EC with source ./activate.",
                severity="warn",
                applies_to_backends={"day-ec-conda"},
                tags={DAYLILY_EC_RUNTIME_TAG},
                success_message="DAY-EC conda environment is active.",
                failure_message=(
                    "DAY-EC conda environment is not active. "
                    "Continuing anyway; the supported path is `source ./activate`."
                ),
            ),
            PrereqSpec(
                key="day-ec-conda-env-name",
                kind="command_probe",
                value=(
                    sys.executable,
                    "-c",
                    "import os, sys; sys.exit(0 if os.environ.get('CONDA_DEFAULT_ENV', '').strip() == 'DAY-EC' else 1)",
                ),
                help="Use the DAY-EC conda environment from source ./activate.",
                severity="warn",
                applies_to_backends={"day-ec-conda"},
                tags={DAYLILY_EC_RUNTIME_TAG},
                success_message="DAY-EC conda environment name is valid.",
                failure_message=(
                    "Active conda environment is not DAY-EC. "
                    "Continuing anyway; the supported path is `source ./activate`."
                ),
            ),
        ],
    ),
    plugins=PluginSpec(explicit=["daylily_ec.cli.register"]),
    info_hooks=[_dayec_info_hook],
)


def _json_mode() -> bool:
    try:
        return bool(get_context().json_mode)
    except Exception:
        return False


def _emit_payload(payload: dict[str, object], text: str) -> None:
    if _json_mode():
        output.emit_json(payload)
        return
    output.print_text(text)


def _dayec_env_warning_message() -> str | None:
    active_env = os.environ.get("CONDA_DEFAULT_ENV", "").strip()
    conda_prefix = os.environ.get("CONDA_PREFIX", "").strip()
    if active_env == "DAY-EC":
        return None
    if active_env:
        return (
            f"Active conda environment is '{active_env}', not DAY-EC. "
            "Continuing anyway; the supported path is `source ./activate`."
        )
    if conda_prefix:
        return (
            "A conda environment is active but CONDA_DEFAULT_ENV is not DAY-EC. "
            "Continuing anyway; the supported path is `source ./activate`."
        )
    return (
        "DAY-EC conda environment is not active. "
        "Continuing anyway; the supported path is `source ./activate`."
    )


def _warn_if_dayec_env_inactive() -> None:
    if _json_mode():
        return
    message = _dayec_env_warning_message()
    if message:
        output.warning(message)


def create(
    region_az: str = typer.Option(
        ...,
        "--region-az",
        help="AWS region + availability zone (e.g. us-west-2b).",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE env var.",
    ),
    config: Optional[str] = typer.Option(
        None,
        "--config",
        help=(
            "Path to daylily config YAML. Default: config/daylily_ephemeral_cluster_template.yaml"
        ),
    ),
    pass_on_warn: bool = typer.Option(
        False,
        "--pass-on-warn",
        help="Continue on preflight warnings instead of failing.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug output (print commands as executed).",
    ),
    repo_override: Optional[List[str]] = typer.Option(
        None,
        "--repo-override",
        help=(
            "Override default_ref for a repository: <repo-key>:<git-ref>. "
            "Can be specified multiple times."
        ),
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Disable interactive prompts; use config defaults or fail.",
    ),
) -> None:
    """Create an ephemeral AWS ParallelCluster environment."""

    from daylily_ec.workflow.create_cluster import run_create_workflow

    _warn_if_dayec_env_inactive()
    _ = repo_override
    if debug:
        logging.basicConfig(level=logging.DEBUG)

    output.action("Creating cluster in %s ..." % region_az)
    rc = run_create_workflow(
        region_az,
        profile=profile,
        config_path=config,
        pass_on_warn=pass_on_warn,
        debug=debug,
        non_interactive=non_interactive,
    )
    raise typer.Exit(rc)


def preflight(
    region_az: str = typer.Option(
        ...,
        "--region-az",
        help="AWS region + availability zone (e.g. us-west-2b).",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE env var.",
    ),
    config: Optional[str] = typer.Option(
        None,
        "--config",
        help="Path to daylily config YAML.",
    ),
    pass_on_warn: bool = typer.Option(
        False,
        "--pass-on-warn",
        help="Treat warnings as non-fatal.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug output.",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Disable interactive prompts.",
    ),
) -> None:
    """Run preflight validation only (no cluster creation)."""

    from daylily_ec.workflow.create_cluster import run_preflight_only

    _warn_if_dayec_env_inactive()
    if debug:
        logging.basicConfig(level=logging.DEBUG)

    output.action("Running preflight for %s ..." % region_az)
    rc = run_preflight_only(
        region_az,
        profile=profile,
        config_path=config,
        pass_on_warn=pass_on_warn,
        debug=debug,
        non_interactive=non_interactive,
    )
    raise typer.Exit(rc)


def drift(
    state_file: str = typer.Option(
        ...,
        "--state-file",
        help="Path to a state JSON file from a previous run.",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug output.",
    ),
) -> None:
    """Check for drift against a previous run's state."""

    from daylily_ec.aws.context import AWSContext
    from daylily_ec.state.drift import run_drift_check
    from daylily_ec.state.models import StateRecord
    from daylily_ec.workflow.create_cluster import (
        EXIT_AWS_FAILURE,
        EXIT_DRIFT,
        EXIT_SUCCESS,
    )

    _warn_if_dayec_env_inactive()
    if debug:
        logging.basicConfig(level=logging.DEBUG)

    state_path = Path(state_file)
    if not state_path.is_file():
        output.error("State file not found: %s" % state_file)
        raise typer.Exit(EXIT_AWS_FAILURE)

    state = StateRecord.model_validate_json(state_path.read_text(encoding="utf-8"))
    output.action("Checking drift for cluster '%s' ..." % state.cluster_name)

    region_az = state.region_az or "%sa" % state.region
    try:
        aws_ctx = AWSContext.build(region_az, profile=profile)
    except RuntimeError as exc:
        output.error("AWS context failed: %s" % exc)
        raise typer.Exit(EXIT_AWS_FAILURE) from exc

    report = run_drift_check(
        state,
        cfn_client=aws_ctx.client("cloudformation"),
        budgets_client=aws_ctx.client("budgets"),
        sns_client=aws_ctx.client("sns"),
        scheduler_client=aws_ctx.client("scheduler"),
        account_id=aws_ctx.account_id,
    )

    payload = json.loads(json.dumps(report.__dict__, default=str))
    if _json_mode():
        output.emit_json(payload)
    else:
        output.detail(json.dumps(payload, indent=2, default=str))

    if report.has_drift:
        output.warn("Drift detected.")
        raise typer.Exit(EXIT_DRIFT)

    output.success("No drift detected.")
    raise typer.Exit(EXIT_SUCCESS)


def cluster_info(
    region: str = typer.Option(
        ...,
        "--region",
        help="AWS region to query (e.g. us-west-2).",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE env var.",
    ),
) -> None:
    """List ParallelCluster clusters and their status."""

    _warn_if_dayec_env_inactive()
    resolved_profile = profile or os.environ.get("AWS_PROFILE", "")
    if not resolved_profile:
        output.error("AWS_PROFILE is not set. Use --profile or export AWS_PROFILE.")
        raise typer.Exit(1)

    env = dict(os.environ)
    env["AWS_PROFILE"] = resolved_profile

    try:
        proc = subprocess.run(
            ["pcluster", "list-clusters", "--region", region],
            capture_output=True,
            text=True,
            env=env,
        )
    except FileNotFoundError:
        output.error("pcluster CLI not found on PATH.")
        raise typer.Exit(1)

    if proc.returncode != 0:
        output.error("pcluster list-clusters failed: %s" % proc.stderr.strip())
        raise typer.Exit(1)

    try:
        clusters_json = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        output.error("Failed to parse list-clusters output: %s" % proc.stdout[:200])
        raise typer.Exit(1)

    cluster_names = [item["clusterName"] for item in clusters_json.get("clusters", [])]
    if not cluster_names:
        _emit_payload({"region": region, "clusters": []}, "No clusters found in %s." % region)
        raise typer.Exit(0)

    rows: list[dict[str, str]] = []
    for name in cluster_names:
        try:
            desc_proc = subprocess.run(
                ["pcluster", "describe-cluster", "--region", region, "-n", name],
                capture_output=True,
                text=True,
                env=env,
            )
        except FileNotFoundError:
            rows.append({"name": name, "status": "ERROR", "ip": "N/A"})
            continue

        if desc_proc.returncode != 0:
            rows.append({"name": name, "status": "ERROR", "ip": "N/A"})
            continue

        try:
            details = json.loads(desc_proc.stdout) if desc_proc.stdout.strip() else {}
        except json.JSONDecodeError:
            details = {}

        rows.append(
            {
                "name": name,
                "status": details.get("clusterStatus", "N/A"),
                "ip": details.get("headNode", {}).get("publicIpAddress", "N/A"),
            }
        )

    payload = {"region": region, "clusters": rows}
    if _json_mode():
        output.emit_json(payload)
        return

    output.heading("Clusters in %s" % region)
    header = "%-30s %-20s %-15s" % ("CLUSTER_NAME", "STATUS", "PUBLIC_IP")
    sep = "%s %s %s" % ("\u2500" * 30, "\u2500" * 20, "\u2500" * 15)
    output.print_text(header)
    output.print_text(sep)
    for row in rows:
        output.print_text("%-30s %-20s %-15s" % (row["name"], row["status"], row["ip"]))


def export(
    cluster_name: str = typer.Option(
        ...,
        "--cluster-name",
        "--cluster",
        help="ParallelCluster name.",
    ),
    target_uri: str = typer.Option(
        ...,
        "--target-uri",
        help="FSx relative path or S3 URI to export.",
    ),
    region: str = typer.Option(
        ...,
        "--region",
        help="AWS region where the FSx filesystem lives.",
    ),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        help="Directory where fsx_export.yaml will be written.",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE env var.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Enable verbose export logging.",
    ),
) -> None:
    """Export FSx results back to the backing S3 repository."""

    from daylily_ec.workflow.export_data import (
        ExportOptions,
        configure_logging,
        run_export_workflow,
    )

    _warn_if_dayec_env_inactive()
    configure_logging(verbose)
    rc = run_export_workflow(
        ExportOptions(
            cluster_name=cluster_name,
            target_uri=target_uri,
            region=region,
            profile=profile,
            output_dir=output_dir.expanduser().resolve(),
        )
    )
    raise typer.Exit(rc)


def delete(
    cluster_name: Optional[str] = typer.Option(
        None,
        "--cluster-name",
        help="ParallelCluster name. Prompts when omitted.",
    ),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help="AWS region where the cluster lives. Prompts when omitted.",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE env var.",
    ),
    state_file: Optional[Path] = typer.Option(
        None,
        "--state-file",
        help="Optional state JSON file from a previous daylily-ec run.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Skip the FSx deletion confirmation prompt.",
    ),
) -> None:
    """Delete a cluster and monitor teardown to completion."""

    from daylily_ec.workflow.delete_cluster import DeleteOptions, run_delete_workflow

    _warn_if_dayec_env_inactive()
    rc = run_delete_workflow(
        DeleteOptions(
            cluster_name=cluster_name,
            region=region,
            profile=profile,
            state_file=state_file,
            yes=yes,
        )
    )
    raise typer.Exit(rc)


def resources_dir() -> None:
    """Print the extracted resource directory used by Daylily."""
    path = str(ensure_extracted())
    if _json_mode():
        output.emit_json({"resources_dir": path})
        return
    output.print_text(path)


def pricing_snapshot(
    region: Optional[List[str]] = typer.Option(
        None,
        "--region",
        help="AWS region to monitor. Repeat for multiple regions.",
    ),
    partition: Optional[List[str]] = typer.Option(
        None,
        "--partition",
        help="Production partition name. Repeat for multiple partitions.",
    ),
    config: Optional[str] = typer.Option(
        None,
        "--config",
        help="Cluster YAML used as the partition source of truth.",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE env var.",
    ),
) -> None:
    """Emit a raw JSON pricing snapshot for the requested regions and partitions."""

    from daylily_ec.aws.pricing_snapshots import collect_pricing_snapshot

    _warn_if_dayec_env_inactive()
    payload = collect_pricing_snapshot(
        regions=region,
        partitions=partition,
        cluster_config_path=config,
        profile=profile,
    ).to_dict()

    if _json_mode():
        output.emit_json(payload)
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=False))


def headnode_init(
    project: Optional[str] = typer.Option(
        None,
        "--project",
        help="Budget/project name to export into the headnode shell.",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE env var.",
    ),
    skip_project_check: bool = typer.Option(
        False,
        "--skip-project-check",
        help="Skip budget-tag validation and AWS budget lookups.",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Disable prompts and emit warnings instead of asking for input.",
    ),
    emit_shell: bool = typer.Option(
        False,
        "--emit-shell",
        help="Print shell code for eval-based bootstrap flows.",
    ),
) -> None:
    """Initialize headnode shell state and optionally repair missing project budgets."""

    from daylily_ec.headnode import run_headnode_init

    _warn_if_dayec_env_inactive()
    raise typer.Exit(
        run_headnode_init(
            project=project,
            profile=profile,
            skip_project_check=skip_project_check,
            non_interactive=non_interactive,
            emit_shell=emit_shell,
        )
    )


def _resolve_headnode_cli_selection(
    *,
    profile: Optional[str],
    region: Optional[str],
    cluster: Optional[str],
):
    from daylily_ec.scripts.common import CommandError, need_cmd, resolve_cluster, resolve_region

    resolved_profile = profile or os.environ.get("AWS_PROFILE")
    if not resolved_profile:
        raise CommandError("AWS profile is required. Set AWS_PROFILE or use --profile.")

    need_cmd("aws")
    need_cmd("pcluster")

    resolved_region = resolve_region(resolved_profile, region)
    resolved_cluster = resolve_cluster(resolved_profile, resolved_region, cluster)
    return resolved_profile, resolved_region, resolved_cluster


def _resolve_headnode_cli_target(
    *,
    profile: Optional[str],
    region: Optional[str],
    cluster: Optional[str],
):
    from daylily_ec.aws.ssm import resolve_headnode_instance_id

    resolved_profile, resolved_region, resolved_cluster = _resolve_headnode_cli_selection(
        profile=profile,
        region=region,
        cluster=cluster,
    )
    target = resolve_headnode_instance_id(
        resolved_cluster,
        resolved_region,
        profile=resolved_profile,
    )
    return resolved_profile, resolved_region, resolved_cluster, target


def _describe_headnode_cluster(
    *,
    profile: str,
    region: str,
    cluster: str,
) -> dict[str, object]:
    from daylily_ec.scripts.common import CommandError, aws_env

    try:
        proc = subprocess.run(
            [
                "pcluster",
                "describe-cluster",
                "--cluster-name",
                cluster,
                "--region",
                region,
            ],
            capture_output=True,
            text=True,
            env=aws_env(profile=profile, region=region),
        )
    except FileNotFoundError as exc:
        raise CommandError("pcluster CLI not found on PATH.") from exc

    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "unknown error"
        raise CommandError(f"pcluster describe-cluster failed: {detail}")

    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise CommandError("Failed to parse pcluster describe-cluster output.") from exc

    if not isinstance(payload, dict):
        raise CommandError("pcluster describe-cluster returned non-object JSON.")
    return payload


def _exit_headnode_error(exc: BaseException) -> None:
    output.error(str(exc))
    raise typer.Exit(1)


def headnode_connect(
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE env var.",
    ),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help="AWS region. Prompts when omitted.",
    ),
    cluster: Optional[str] = typer.Option(
        None,
        "--cluster",
        "--cluster-name",
        help="ParallelCluster name. Prompts when omitted.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print the Session Manager command without opening a session.",
    ),
) -> None:
    """Open an ubuntu bash login shell on a cluster headnode via Session Manager."""

    from daylily_ec.aws.ssm import SsmError, start_session, wait_for_ssm_online
    from daylily_ec.scripts.common import CommandError

    _warn_if_dayec_env_inactive()
    try:
        resolved_profile, resolved_region, resolved_cluster, target = _resolve_headnode_cli_target(
            profile=profile,
            region=region,
            cluster=cluster,
        )
        wait_for_ssm_online(
            target.instance_id,
            resolved_region,
            profile=resolved_profile,
            timeout=120,
        )
        connect_cmd = (
            "aws ssm start-session "
            f"--region {resolved_region} "
            f"--target {target.instance_id} "
            "--document-name SSM-SessionManagerRunShell"
        )
        output.print_text(
            f"Opening Session Manager session as ubuntu to {target.instance_id} "
            f"(cluster={resolved_cluster} region={resolved_region} profile={resolved_profile})"
        )
        output.print_text(f"Session Manager command: {connect_cmd}")
        if dry_run:
            raise typer.Exit(0)
        raise typer.Exit(
            start_session(target.instance_id, resolved_region, profile=resolved_profile)
        )
    except (CommandError, SsmError, TimeoutError) as exc:
        _exit_headnode_error(exc)


def headnode_info(
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE env var.",
    ),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help="AWS region. Prompts when omitted.",
    ),
    cluster: Optional[str] = typer.Option(
        None,
        "--cluster",
        "--cluster-name",
        help="ParallelCluster name. Prompts when omitted.",
    ),
) -> None:
    """Return the full pcluster describe-cluster payload for a headnode."""

    from daylily_ec.scripts.common import CommandError

    _warn_if_dayec_env_inactive()
    try:
        resolved_profile, resolved_region, resolved_cluster = _resolve_headnode_cli_selection(
            profile=profile,
            region=region,
            cluster=cluster,
        )
        payload = _describe_headnode_cluster(
            profile=resolved_profile,
            region=resolved_region,
            cluster=resolved_cluster,
        )
    except CommandError as exc:
        _exit_headnode_error(exc)

    if _json_mode():
        output.emit_json(payload)
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=False))


def headnode_jobs(
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE env var.",
    ),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help="AWS region. Prompts when omitted.",
    ),
    cluster: Optional[str] = typer.Option(
        None,
        "--cluster",
        "--cluster-name",
        help="ParallelCluster name. Prompts when omitted.",
    ),
) -> None:
    """Print Slurm jobs from the headnode using the Daylily sq format."""

    from daylily_ec.aws.ssm import (
        SsmCommandFailedError,
        SsmError,
        run_shell,
        wait_for_ssm_online,
    )
    from daylily_ec.headnode import SQUEUE_FORMAT
    from daylily_ec.scripts.common import CommandError

    _warn_if_dayec_env_inactive()
    try:
        resolved_profile, resolved_region, _resolved_cluster, target = _resolve_headnode_cli_target(
            profile=profile,
            region=region,
            cluster=cluster,
        )
        wait_for_ssm_online(
            target.instance_id,
            resolved_region,
            profile=resolved_profile,
            timeout=120,
        )
        result = run_shell(
            target.instance_id,
            resolved_region,
            "set -euo pipefail\nsqueue -o " + shlex.quote(SQUEUE_FORMAT),
            profile=resolved_profile,
            timeout=120,
            comment="Daylily headnode Slurm jobs",
        )
    except SsmCommandFailedError as exc:
        if exc.result.stderr.strip():
            typer.echo(exc.result.stderr.rstrip(), err=True)
        _exit_headnode_error(exc)
    except (CommandError, SsmError, TimeoutError) as exc:
        _exit_headnode_error(exc)

    if result.stdout:
        typer.echo(result.stdout.rstrip())
    if result.stderr:
        typer.echo(result.stderr.rstrip(), err=True)


def register(registry, cli_spec) -> None:
    _ = cli_spec
    register_root_command(
        registry,
        "create",
        create,
        REQUIRED_MUTATING_LONG_RUNNING,
    )
    register_root_command(
        registry,
        "preflight",
        preflight,
        REQUIRED_LONG_RUNNING,
    )
    register_root_command(
        registry,
        "drift",
        drift,
        REQUIRED_JSON,
    )
    register_root_command(
        registry,
        "cluster-info",
        cluster_info,
        REQUIRED_JSON,
    )
    register_root_command(
        registry,
        "export",
        export,
        REQUIRED_MUTATING_LONG_RUNNING,
    )
    register_root_command(
        registry,
        "delete",
        delete,
        REQUIRED_MUTATING_INTERACTIVE,
    )
    register_root_command(
        registry,
        "resources-dir",
        resources_dir,
        EXEMPT,
    )
    register_group_commands(
        registry,
        "pricing",
        "Spot pricing inspection helpers.",
        [("snapshot", pricing_snapshot, REQUIRED_JSON)],
    )
    register_group_commands(
        registry,
        "headnode",
        "Headnode bootstrap and shell-context helpers.",
        [
            ("init", headnode_init, REQUIRED_MUTATING_INTERACTIVE),
            ("connect", headnode_connect, required_policy(interactive=True)),
            ("info", headnode_info, REQUIRED_JSON),
            ("jobs", headnode_jobs, required_policy()),
        ],
    )


app = create_app(spec)


def main() -> None:
    raise SystemExit(run(spec))


if __name__ == "__main__":
    main()
