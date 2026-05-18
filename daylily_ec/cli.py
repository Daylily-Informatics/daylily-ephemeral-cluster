"""CLI entry point for daylily-ec built on cli-core-yo v2."""

from __future__ import annotations

import contextlib
import io
import json
import logging
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, List, Optional

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
    EXEMPT_JSON,
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


def _resolved_aws_profile(profile: Optional[str]) -> str:
    from daylily_ec.scripts.common import CommandError

    resolved_profile = profile or os.environ.get("AWS_PROFILE", "")
    if not resolved_profile:
        raise CommandError("AWS profile is required. Set AWS_PROFILE or use --profile.")
    return resolved_profile


def _aws_env(*, profile: Optional[str], region: Optional[str] = None) -> dict[str, str]:
    env = dict(os.environ)
    if profile:
        env["AWS_PROFILE"] = profile
    if region:
        env["AWS_REGION"] = region
        env.setdefault("AWS_DEFAULT_REGION", region)
    return env


def _command_failure_detail(proc: subprocess.CompletedProcess[str]) -> str:
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    details: list[str] = []
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            details.append(stdout)
        else:
            if isinstance(payload, dict) and payload.get("message"):
                details.append(str(payload["message"]))
            else:
                details.append(stdout)
    if stderr:
        details.append(stderr)
    return "\n".join(details) or "unknown error"


def _run_pcluster_json(
    command: list[str],
    *,
    profile: str,
    region: str,
) -> dict[str, Any]:
    from daylily_ec.scripts.common import CommandError

    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=_aws_env(profile=profile, region=region),
        )
    except FileNotFoundError as exc:
        raise CommandError("pcluster CLI not found on PATH.") from exc

    if proc.returncode != 0:
        raise CommandError(f"pcluster command failed: {_command_failure_detail(proc)}")

    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise CommandError("Failed to parse pcluster JSON output.") from exc
    if not isinstance(payload, dict):
        raise CommandError("pcluster returned non-object JSON.")
    return payload


def _cluster_row_from_details(name: str, details: dict[str, Any]) -> dict[str, Any]:
    head_node = details.get("headNode") if isinstance(details.get("headNode"), dict) else {}
    return {
        "name": name,
        "status": details.get("clusterStatus", "N/A"),
        "created_at": details.get("creationTime", "N/A"),
        "updated_at": details.get("lastUpdatedTime", "N/A"),
        "headnode_launched_at": head_node.get("launchTime", "N/A"),
        "ip": head_node.get("publicIpAddress", "N/A"),
        "instance_id": head_node.get("instanceId", ""),
        "details": details,
    }


def _cluster_headnode_config_status(
    row: dict[str, Any],
    *,
    profile: str,
    region: str,
) -> None:
    instance_id = str(row.get("instance_id") or "").strip()
    if not instance_id:
        row["headnode_configured"] = None
        row["headnode_configured_text"] = "N/A"
        row["headnode_config_error"] = "headnode instance id is unavailable"
        return

    from daylily_ec.aws.ssm import SsmCommandFailedError, SsmError, run_shell

    script = "\n".join(
        [
            "set -euo pipefail",
            'test "$(whoami)" = "ubuntu"',
            'test "${CONDA_DEFAULT_ENV:-}" = "DAY-EC"',
            "command -v daylily-ec >/dev/null",
            "command -v day-clone >/dev/null",
            "day-clone --list >/dev/null",
        ]
    )
    try:
        run_shell(
            instance_id,
            region,
            script,
            profile=profile,
            timeout=60,
            comment=f"Check headnode configuration for {row['name']}",
        )
    except SsmCommandFailedError as exc:
        row["headnode_configured"] = False
        row["headnode_configured_text"] = "NO"
        row["headnode_config_error"] = (
            exc.result.stderr.strip() or exc.result.stdout.strip() or str(exc)
        )
        return
    except (SsmError, TimeoutError, RuntimeError) as exc:
        row["headnode_configured"] = False
        row["headnode_configured_text"] = "NO"
        row["headnode_config_error"] = str(exc)
        return

    row["headnode_configured"] = True
    row["headnode_configured_text"] = "YES"
    row["headnode_config_error"] = ""


def _cluster_rows_from_list(
    payload: dict[str, Any],
    *,
    profile: str,
    region: str,
    details: bool,
    verbose: bool,
) -> list[dict[str, Any]]:
    clusters = payload.get("clusters", [])
    if not isinstance(clusters, list):
        return []

    rows: list[dict[str, Any]] = []
    for item in clusters:
        if not isinstance(item, dict):
            continue
        name = str(item.get("clusterName") or "")
        if not name:
            continue
        row = _cluster_row_from_details(
            name,
            _describe_cluster_payload(profile=profile, region=region, cluster=name),
        )
        row["region"] = region
        if verbose or details:
            _cluster_headnode_config_status(row, profile=profile, region=region)
        else:
            row = {
                "name": row["name"],
                "region": row["region"],
                "ip": row["ip"],
            }
        if verbose and not details:
            row.pop("details", None)
        rows.append(row)
    return rows


def _describe_cluster_payload(
    *,
    profile: str,
    region: str,
    cluster: str,
) -> dict[str, Any]:
    return _run_pcluster_json(
        [
            "pcluster",
            "describe-cluster",
            "--cluster-name",
            cluster,
            "--region",
            region,
        ],
        profile=profile,
        region=region,
    )


def _emit_cluster_table(
    regions: list[str],
    rows: list[dict[str, Any]],
    *,
    verbose: bool,
    include_instance: bool,
) -> None:
    region_label = ", ".join(regions)
    if not rows:
        output.print_text(f"No clusters found in {region_label}.")
        return
    output.heading("Clusters in %s" % region_label)
    if not verbose and not include_instance:
        header = "%-30s %-15s %-15s" % (
            "CLUSTER_NAME",
            "REGION",
            "PUBLIC_IP",
        )
        sep = "%s %s %s" % (
            "\u2500" * 30,
            "\u2500" * 15,
            "\u2500" * 15,
        )
        output.print_text(header)
        output.print_text(sep)
        for row in rows:
            output.print_text(
                "%-30s %-15s %-15s"
                % (
                    row["name"],
                    row["region"],
                    row["ip"],
                )
            )
        return

    if include_instance:
        header = "%-30s %-15s %-15s %-20s %-19s %-28s %-28s %-28s %-20s" % (
            "CLUSTER_NAME",
            "REGION",
            "PUBLIC_IP",
            "STATUS",
            "HEADNODE_CONFIGURED",
            "CREATED_AT",
            "UPDATED_AT",
            "HEADNODE_LAUNCHED_AT",
            "INSTANCE_ID",
        )
        sep = "%s %s %s %s %s %s %s %s %s" % (
            "\u2500" * 30,
            "\u2500" * 15,
            "\u2500" * 15,
            "\u2500" * 20,
            "\u2500" * 19,
            "\u2500" * 28,
            "\u2500" * 28,
            "\u2500" * 28,
            "\u2500" * 20,
        )
        output.print_text(header)
        output.print_text(sep)
        for row in rows:
            output.print_text(
                "%-30s %-15s %-15s %-20s %-19s %-28s %-28s %-28s %-20s"
                % (
                    row["name"],
                    row["region"],
                    row["ip"],
                    row["status"],
                    row["headnode_configured_text"],
                    row["created_at"],
                    row["updated_at"],
                    row["headnode_launched_at"],
                    row.get("instance_id") or "",
                )
            )
        return

    header = "%-30s %-15s %-15s %-20s %-19s %-28s %-28s %-28s" % (
        "CLUSTER_NAME",
        "REGION",
        "PUBLIC_IP",
        "STATUS",
        "HEADNODE_CONFIGURED",
        "CREATED_AT",
        "UPDATED_AT",
        "HEADNODE_LAUNCHED_AT",
    )
    sep = "%s %s %s %s %s %s %s %s" % (
        "\u2500" * 30,
        "\u2500" * 15,
        "\u2500" * 15,
        "\u2500" * 20,
        "\u2500" * 19,
        "\u2500" * 28,
        "\u2500" * 28,
        "\u2500" * 28,
    )
    output.print_text(header)
    output.print_text(sep)
    for row in rows:
        output.print_text(
            "%-30s %-15s %-15s %-20s %-19s %-28s %-28s %-28s"
            % (
                row["name"],
                row["region"],
                row["ip"],
                row["status"],
                row["headnode_configured_text"],
                row["created_at"],
                row["updated_at"],
                row["headnode_launched_at"],
            )
        )


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
    raise SystemExit(rc)


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


def _normalize_cluster_list_regions(regions: List[str]) -> list[str]:
    normalized = [region.strip() for region in regions if region.strip()]
    if not normalized:
        output.error("At least one --region value is required.")
        raise typer.Exit(1)
    return normalized


def cluster_list(
    regions: List[str] = typer.Option(
        ...,
        "--region",
        help="AWS region to query. Repeat --region once per requested region.",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE env var.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Include status, headnode configuration, and timestamp columns.",
    ),
    details: bool = typer.Option(
        False,
        "--details",
        help="Include raw pcluster describe payloads in JSON output. Implies --verbose table columns.",
    ),
) -> None:
    """List ParallelCluster clusters in one or more regions."""

    from daylily_ec.scripts.common import CommandError

    _warn_if_dayec_env_inactive()
    try:
        resolved_profile = _resolved_aws_profile(profile)
        requested_regions = _normalize_cluster_list_regions(regions)
        rows: list[dict[str, Any]] = []
        for region in requested_regions:
            payload = _run_pcluster_json(
                ["pcluster", "list-clusters", "--region", region],
                profile=resolved_profile,
                region=region,
            )
            rows.extend(
                _cluster_rows_from_list(
                    payload,
                    profile=resolved_profile,
                    region=region,
                    details=details,
                    verbose=verbose,
                )
            )
    except CommandError as exc:
        _exit_headnode_error(exc)

    result = {"regions": requested_regions, "clusters": rows}
    if _json_mode():
        output.emit_json(result)
        return
    _emit_cluster_table(
        requested_regions,
        rows,
        verbose=verbose,
        include_instance=details,
    )


def cluster_describe(
    region: str = typer.Option(
        ...,
        "--region",
        help="AWS region to query (e.g. us-west-2).",
    ),
    cluster: str = typer.Option(
        ...,
        "--cluster",
        "--cluster-name",
        help="ParallelCluster name.",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE env var.",
    ),
) -> None:
    """Return the full pcluster describe-cluster payload."""

    from daylily_ec.scripts.common import CommandError

    _warn_if_dayec_env_inactive()
    try:
        payload = _describe_cluster_payload(
            profile=_resolved_aws_profile(profile),
            region=region,
            cluster=cluster,
        )
    except CommandError as exc:
        _exit_headnode_error(exc)

    if _json_mode():
        output.emit_json(payload)
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=False))


def cluster_wait(
    region: str = typer.Option(
        ...,
        "--region",
        help="AWS region to query (e.g. us-west-2).",
    ),
    cluster: str = typer.Option(
        ...,
        "--cluster",
        "--cluster-name",
        help="ParallelCluster name.",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE env var.",
    ),
    status: str = typer.Option(
        "CREATE_COMPLETE",
        "--status",
        help="Cluster status to wait for.",
    ),
    timeout: int = typer.Option(
        3600,
        "--timeout",
        help="Maximum seconds to wait.",
    ),
    poll_interval: int = typer.Option(
        30,
        "--poll-interval",
        help="Seconds between polls.",
    ),
) -> None:
    """Wait until a ParallelCluster cluster reaches a target status."""

    from daylily_ec.scripts.common import CommandError

    _warn_if_dayec_env_inactive()
    try:
        resolved_profile = _resolved_aws_profile(profile)
    except CommandError as exc:
        _exit_headnode_error(exc)
    target_status = status.strip()
    deadline = time.time() + timeout
    terminal_failure_prefixes = ("CREATE_FAILED", "DELETE_FAILED", "UPDATE_FAILED", "ROLLBACK")

    while True:
        try:
            payload = _describe_cluster_payload(
                profile=resolved_profile,
                region=region,
                cluster=cluster,
            )
        except CommandError as exc:
            _exit_headnode_error(exc)

        current_status = str(payload.get("clusterStatus") or "")
        if current_status == target_status:
            result = {
                "cluster": cluster,
                "region": region,
                "status": current_status,
                "details": payload,
            }
            if _json_mode():
                output.emit_json(result)
            else:
                output.success(f"Cluster '{cluster}' reached {current_status}.")
            return

        if current_status.startswith(terminal_failure_prefixes):
            output.error(
                "Cluster '%s' entered terminal status %s before %s."
                % (cluster, current_status, target_status)
            )
            raise typer.Exit(1)

        if time.time() >= deadline:
            output.error(
                "Timed out waiting for cluster '%s' to reach %s; last status was %s."
                % (cluster, target_status, current_status or "UNKNOWN")
            )
            raise typer.Exit(1)

        if not _json_mode():
            output.print_text("Status: %s" % (current_status or "UNKNOWN"))
        time.sleep(max(poll_interval, 1))


def export(
    cluster_name: Optional[str] = typer.Option(
        None,
        "--cluster-name",
        "--cluster",
        help="ParallelCluster name used to resolve the FSx file system.",
    ),
    fsx_file_system_id: Optional[str] = typer.Option(
        None,
        "--fsx-file-system-id",
        help="Explicit FSx file system id. Required when --cluster is omitted.",
    ),
    source_path: str = typer.Option(
        ...,
        "--source-path",
        help="Completed analysis directory under /fsx/analysis_results/ubuntu/<analysis-dir>/.",
    ),
    destination_s3_uri: str = typer.Option(
        ...,
        "--destination-s3-uri",
        help="S3 URI backing the temporary export DRA.",
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
    wait: bool = typer.Option(True, "--wait/--no-wait", help="Wait for DRA/task/detach."),
    timeout_seconds: int = typer.Option(3600, "--timeout-seconds", help="Wait timeout."),
) -> None:
    """Export FSx outputs through an explicit temporary DRA."""

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
            fsx_file_system_id=fsx_file_system_id,
            source_path=source_path,
            destination_s3_uri=destination_s3_uri,
            region=region,
            profile=profile,
            output_dir=output_dir.expanduser().resolve(),
            wait=wait,
            timeout_seconds=timeout_seconds,
        )
    )
    raise typer.Exit(rc)


def _emit_export_payload(payload: Any, *, text: str) -> None:
    if _json_mode():
        output.emit_json(payload)
        return
    typer.echo(text)


def exports_attach(
    cluster_name: Optional[str] = typer.Option(None, "--cluster-name", "--cluster"),
    fsx_file_system_id: Optional[str] = typer.Option(None, "--fsx-file-system-id"),
    source_path: str = typer.Option(..., "--source-path"),
    destination_s3_uri: str = typer.Option(..., "--destination-s3-uri"),
    region: str = typer.Option(..., "--region"),
    profile: Optional[str] = typer.Option(None, "--profile"),
    wait: bool = typer.Option(True, "--wait/--no-wait"),
    timeout_seconds: int = typer.Option(900, "--timeout-seconds"),
) -> None:
    """Attach a temporary output DRA to a completed analysis directory."""

    from daylily_ec.workflow.export_data import attach_export_dra

    try:
        record = attach_export_dra(
            cluster_name=cluster_name,
            fsx_file_system_id=fsx_file_system_id,
            source_path=source_path,
            destination_s3_uri=destination_s3_uri,
            region=region,
            profile=profile,
            wait=wait,
            timeout_seconds=timeout_seconds,
        )
        _emit_export_payload(
            record.to_payload(),
            text=(
                f"Export DRA attached: {record.association_id}\n"
                f"Headnode path: {record.headnode_path}\n"
                f"S3 destination: {record.destination_s3_uri}"
            ),
        )
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def exports_run(
    cluster_name: Optional[str] = typer.Option(None, "--cluster-name", "--cluster"),
    fsx_file_system_id: Optional[str] = typer.Option(None, "--fsx-file-system-id"),
    source_path: str = typer.Option(..., "--source-path"),
    destination_s3_uri: str = typer.Option(..., "--destination-s3-uri"),
    region: str = typer.Option(..., "--region"),
    profile: Optional[str] = typer.Option(None, "--profile"),
    wait: bool = typer.Option(True, "--wait/--no-wait"),
    timeout_seconds: int = typer.Option(3600, "--timeout-seconds"),
) -> None:
    """Run an explicit FSx export task for an analysis directory."""

    from daylily_ec.workflow.export_data import (
        _create_session,
        resolve_export_fsx_id,
        run_export_task,
    )

    try:
        client = _create_session(region, profile).client("fsx")
        resolved_fsx_id = resolve_export_fsx_id(
            client,
            cluster_name=cluster_name,
            fsx_file_system_id=fsx_file_system_id,
        )
        payload = run_export_task(
            fsx_file_system_id=resolved_fsx_id,
            source_path=source_path,
            destination_s3_uri=destination_s3_uri,
            wait=wait,
            timeout_seconds=timeout_seconds,
            fsx_client=client,
        )
        payload["fsx_file_system_id"] = resolved_fsx_id
        _emit_export_payload(
            payload,
            text=(
                f"Export task started: {payload['task_id']}\n"
                f"Lifecycle: {payload['task_lifecycle']}\n"
                f"Report path: {payload['report_path']}"
            ),
        )
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def exports_detach(
    association_id: str = typer.Option(..., "--association-id"),
    region: str = typer.Option(..., "--region"),
    profile: Optional[str] = typer.Option(None, "--profile"),
    wait: bool = typer.Option(True, "--wait/--no-wait"),
    timeout_seconds: int = typer.Option(900, "--timeout-seconds"),
) -> None:
    """Detach an output DRA without deleting cached FSx data."""

    from daylily_ec.workflow.export_data import detach_export_dra

    try:
        payload = detach_export_dra(
            association_id=association_id,
            region=region,
            profile=profile,
            wait=wait,
            timeout_seconds=timeout_seconds,
        )
        _emit_export_payload(
            payload,
            text=(
                f"Export DRA detached: {association_id}\n"
                f"Lifecycle: {payload['detach_lifecycle']}\n"
                "DeleteDataInFileSystem: false"
            ),
        )
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


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
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Inspect the delete target without changing AWS resources.",
    ),
) -> None:
    """Delete a cluster and monitor teardown to completion."""

    from daylily_ec.workflow.delete_cluster import (
        DeleteOptions,
        run_delete_dry_run,
        run_delete_workflow,
    )

    _warn_if_dayec_env_inactive()
    options = DeleteOptions(
        cluster_name=cluster_name,
        region=region,
        profile=profile,
        state_file=state_file,
        yes=yes,
    )
    rc = run_delete_dry_run(options) if dry_run else run_delete_workflow(options)
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


def _run_aws_validate_command(
    mode: str,
    *,
    profile: str,
    region_az: str,
    config: Optional[str],
    gap_analysis: Optional[Path],
) -> None:
    from daylily_ec.aws.validation import (
        AwsValidationError,
        AwsValidationOptions,
        run_aws_validation,
    )
    from daylily_ec.workflow.create_cluster import EXIT_AWS_FAILURE

    _warn_if_dayec_env_inactive()
    try:
        rc, report = run_aws_validation(
            AwsValidationOptions(
                mode=mode,  # type: ignore[arg-type]
                profile=profile,
                region_az=region_az,
                config_path=config,
                gap_analysis_path=gap_analysis,
            )
        )
    except (AwsValidationError, FileNotFoundError, RuntimeError, ValueError) as exc:
        if _json_mode():
            output.emit_json({"mode": mode, "error": str(exc)})
        else:
            output.error(f"AWS validation failed to start: {exc}")
        raise SystemExit(EXIT_AWS_FAILURE) from exc

    if _json_mode():
        output.emit_json(report.model_dump(mode="json"))
        raise SystemExit(rc)

    output.print_text(
        "AWS validation %s: PASS=%s WARN=%s FAIL=%s"
        % (
            mode,
            report.summary.get("PASS", 0),
            report.summary.get("WARN", 0),
            report.summary.get("FAIL", 0),
        )
    )
    for check in report.checks:
        if check.status.value == "PASS":
            continue
        line = f"{check.status.value} {check.id}"
        if check.remediation:
            line = f"{line}: {check.remediation}"
        if check.status.value == "FAIL":
            output.error(line)
        else:
            output.warning(line)
    if gap_analysis is not None:
        output.print_text(f"Gap analysis written: {gap_analysis}")
    if rc == 0:
        output.success("AWS validation passed.")
    else:
        output.error("AWS validation found permission or quota gaps.")
    raise SystemExit(rc)


def aws_validate_permissions(
    profile: str = typer.Option(
        ...,
        "--profile",
        help="Explicit named AWS CLI profile to validate; 'default' is rejected.",
    ),
    region_az: str = typer.Option(
        ...,
        "--region-az",
        help="Target AWS availability zone, e.g. us-west-2b.",
    ),
    config: Optional[str] = typer.Option(
        None,
        "--config",
        help="Daylily config path. Accepted for report context.",
    ),
    gap_analysis: Optional[Path] = typer.Option(
        None,
        "--gap-analysis",
        help="Write an AWS-admin Markdown gap analysis report.",
    ),
) -> None:
    """Validate AWS permissions needed by Daylily."""

    _run_aws_validate_command(
        "permissions",
        profile=profile,
        region_az=region_az,
        config=config,
        gap_analysis=gap_analysis,
    )


def aws_validate_quotas(
    profile: str = typer.Option(
        ...,
        "--profile",
        help="Explicit named AWS CLI profile to validate; 'default' is rejected.",
    ),
    region_az: str = typer.Option(
        ...,
        "--region-az",
        help="Target AWS availability zone, e.g. us-west-2b.",
    ),
    config: Optional[str] = typer.Option(
        None,
        "--config",
        help="Daylily config path to render for quota demand.",
    ),
    gap_analysis: Optional[Path] = typer.Option(
        None,
        "--gap-analysis",
        help="Write an AWS-admin Markdown gap analysis report.",
    ),
) -> None:
    """Validate AWS quotas needed by the rendered Daylily cluster."""

    _run_aws_validate_command(
        "quotas",
        profile=profile,
        region_az=region_az,
        config=config,
        gap_analysis=gap_analysis,
    )


def aws_validate_all(
    profile: str = typer.Option(
        ...,
        "--profile",
        help="Explicit named AWS CLI profile to validate; 'default' is rejected.",
    ),
    region_az: str = typer.Option(
        ...,
        "--region-az",
        help="Target AWS availability zone, e.g. us-west-2b.",
    ),
    config: Optional[str] = typer.Option(
        None,
        "--config",
        help="Daylily config path to render for quota demand.",
    ),
    gap_analysis: Optional[Path] = typer.Option(
        None,
        "--gap-analysis",
        help="Write an AWS-admin Markdown gap analysis report.",
    ),
) -> None:
    """Validate AWS permissions and quotas needed by Daylily."""

    _run_aws_validate_command(
        "all",
        profile=profile,
        region_az=region_az,
        config=config,
        gap_analysis=gap_analysis,
    )


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
        raise CommandError(f"pcluster describe-cluster failed: {_command_failure_detail(proc)}")

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
            start_session(
                target.instance_id,
                resolved_region,
                profile=resolved_profile,
                replace_process=True,
            )
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


def headnode_configure(
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
    repo_overrides: Optional[Path] = typer.Option(
        None,
        "--repo-overrides",
        help="File containing repo overrides as repo-key:git-ref lines.",
    ),
) -> None:
    """Configure a cluster headnode through the supported SSM bootstrap."""

    from daylily_ec.aws.ssm import SsmError, wait_for_ssm_online
    from daylily_ec.scripts.common import CommandError
    from daylily_ec.scripts.daylily_cfg_headnode import _load_repo_overrides
    from daylily_ec.workflow.create_cluster import configure_headnode

    _warn_if_dayec_env_inactive()
    try:
        resolved_profile, resolved_region, resolved_cluster, target = _resolve_headnode_cli_target(
            profile=profile,
            region=region,
            cluster=cluster,
        )
        overrides = _load_repo_overrides(str(repo_overrides) if repo_overrides else None)
        wait_for_ssm_online(
            target.instance_id,
            resolved_region,
            profile=resolved_profile,
            timeout=120,
        )
        ok = configure_headnode(
            cluster_name=resolved_cluster,
            head_node_instance_id=target.instance_id,
            region=resolved_region,
            profile=resolved_profile,
            repo_overrides=overrides or None,
        )
        if not ok:
            raise CommandError(f"Headnode configuration failed for cluster '{resolved_cluster}'.")
    except (CommandError, SsmError, TimeoutError) as exc:
        _exit_headnode_error(exc)

    output.success(f"Headnode configured via SSM for cluster '{resolved_cluster}'.")


def _invoke_stage_samples(argv: list[str]) -> int:
    from daylily_ec.stage_samples import main as stage_samples_main

    return int(stage_samples_main(argv))


def _invoke_workflow_launch(argv: list[str]) -> int:
    from daylily_ec.scripts.daylily_run_omics_analysis_headnode import main as launch_main

    return int(launch_main(argv))


def _parse_remote_stage_dir(stage_stdout: str) -> str:
    from daylily_ec.scripts.common import CommandError

    for line in stage_stdout.splitlines():
        if line.startswith("Remote FSx stage directory:"):
            stage_dir = line.split(":", 1)[1].strip()
            if stage_dir:
                return stage_dir
    raise CommandError("Staging output did not include a Remote FSx stage directory.")


def _parse_workflow_launch_metadata(launch_stdout: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in launch_stdout.splitlines():
        if line.startswith("__DAYLILY_SESSION__="):
            parsed["session_name"] = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_RUN_DIR__="):
            parsed["run_dir"] = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_REPO_PATH__="):
            parsed["repo_path"] = line.split("=", 1)[1].strip()
    return parsed


def samples_stage(
    analysis_samples: Path = typer.Argument(
        ...,
        help="Path to analysis_samples.tsv.",
    ),
    reference_bucket: str = typer.Option(
        ...,
        "--reference-bucket",
        help="S3 URI mapped to the FSx data repository.",
    ),
    config_dir: Optional[Path] = typer.Option(
        None,
        "--config-dir",
        help="Directory for generated samples.tsv and units.tsv.",
    ),
    stage_target: str = typer.Option(
        "/data/staged_sample_data",
        "--stage-target",
        help="FSx staging base directory.",
    ),
    run_metric_staging: Optional[List[str]] = typer.Option(
        None,
        "--run-metric-staging",
        help=(
            "Copy run metric files into runs/<RUN_UID>/ from RUN_UID:PLATFORM:FOFN. "
            "Can be specified multiple times."
        ),
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE env var.",
    ),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help="AWS region. Defaults to AWS_REGION/AWS_DEFAULT_REGION.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Print AWS CLI commands before execution.",
    ),
    precheck_only: bool = typer.Option(
        False,
        "--precheck-only",
        help="Validate the manifest and exit without staging or writing generated configs.",
    ),
) -> None:
    """Stage analysis samples and generate workflow manifests."""

    _warn_if_dayec_env_inactive()
    argv = [
        str(analysis_samples),
        "--reference-bucket",
        reference_bucket,
        "--stage-target",
        stage_target,
    ]
    for spec in run_metric_staging or []:
        argv.extend(["--run-metric-staging", spec])
    if config_dir:
        argv.extend(["--config-dir", str(config_dir)])
    if profile:
        argv.extend(["--profile", profile])
    if region:
        argv.extend(["--region", region])
    if debug:
        argv.append("--debug")
    if precheck_only:
        argv.append("--precheck-only")

    try:
        rc = _invoke_stage_samples(argv)
    except RuntimeError as exc:
        _exit_headnode_error(exc)
    raise typer.Exit(rc)


def samples_run(
    analysis_samples: Path = typer.Argument(
        ...,
        help="Path to analysis_samples.tsv.",
    ),
    command_id: str = typer.Option(
        ...,
        "--command-id",
        help="Repository catalog analysis command id to launch.",
    ),
    destination: str = typer.Option(
        ...,
        "--destination",
        help="Required day-clone destination for the analysis repository.",
    ),
    reference_bucket: str = typer.Option(
        ...,
        "--reference-bucket",
        help="S3 URI mapped to the FSx data repository.",
    ),
    config_dir: Optional[Path] = typer.Option(
        None,
        "--config-dir",
        help="Directory for generated samples.tsv, units.tsv, and run receipt.",
    ),
    stage_target: str = typer.Option(
        "/data/staged_sample_data",
        "--stage-target",
        help="FSx staging base directory.",
    ),
    run_metric_staging: Optional[List[str]] = typer.Option(
        None,
        "--run-metric-staging",
        help=(
            "Copy run metric files into runs/<RUN_UID>/ from RUN_UID:PLATFORM:FOFN. "
            "Can be specified multiple times."
        ),
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE env var.",
    ),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help="AWS region. Defaults to AWS_REGION/AWS_DEFAULT_REGION.",
    ),
    cluster: Optional[str] = typer.Option(
        None,
        "--cluster",
        "--cluster-name",
        help="ParallelCluster name.",
    ),
    git_tag: Optional[str] = typer.Option(
        None,
        "--git-tag",
        "-t",
        help="Override the catalog command's DayOA git tag.",
    ),
    session_name: Optional[str] = typer.Option(
        None,
        "--session-name",
        help="Tmux session name. Defaults to --destination.",
    ),
    project: Optional[str] = typer.Option(None, "--project", help="Project/budget for dyoainit."),
    skip_project_check: bool = typer.Option(
        True,
        "--skip-project-check/--strict-project-check",
        help="Skip or enable upstream project validation in dyoainit.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Launch the catalog dry-run command."),
    catalog_config: Optional[Path] = typer.Option(
        None,
        "--catalog-config",
        help="Path to daylily_available_repositories.yaml.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Print AWS CLI commands during staging.",
    ),
) -> None:
    """Stage analysis samples and launch a compatible catalog workflow command."""

    from daylily_ec.repositories import load_repository_catalog
    from daylily_ec.scripts.common import CommandError
    from daylily_ec.stage_samples import detect_manifest_data_modes

    _warn_if_dayec_env_inactive()
    analysis_path = analysis_samples.expanduser().resolve()
    try:
        catalog = load_repository_catalog(catalog_config)
        command = catalog.get_command(command_id)
        data_modes = detect_manifest_data_modes(analysis_path)
        incompatible = command.incompatible_modes(data_modes)
        if incompatible:
            raise CommandError(
                f"Analysis command {command.command_id} is not compatible with "
                f"manifest data mode(s): {', '.join(incompatible)}. "
                "Compatible modes: " + ", ".join(command.compatible_data_modes)
            )
        resolved_profile = _resolved_aws_profile(profile)
        resolved_region = (
            region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        )

        stage_argv = [
            str(analysis_path),
            "--reference-bucket",
            reference_bucket,
            "--stage-target",
            stage_target,
        ]
        for spec in run_metric_staging or []:
            stage_argv.extend(["--run-metric-staging", spec])
        resolved_config_dir = config_dir.expanduser() if config_dir else analysis_path.parent
        stage_argv.extend(["--config-dir", str(resolved_config_dir)])
        stage_argv.extend(["--profile", resolved_profile])
        if resolved_region:
            stage_argv.extend(["--region", resolved_region])
        if debug:
            stage_argv.append("--debug")

        stage_stdout_buffer = io.StringIO()
        with contextlib.redirect_stdout(stage_stdout_buffer):
            stage_rc = _invoke_stage_samples(stage_argv)
        stage_stdout = stage_stdout_buffer.getvalue()
        if stage_stdout:
            typer.echo(stage_stdout, nl=False)
        if stage_rc != 0:
            raise typer.Exit(stage_rc)

        remote_stage_dir = _parse_remote_stage_dir(stage_stdout)
        resolved_session_name = session_name or destination
        resolved_git_tag = git_tag or command.git_tag
        workflow_cli_argv = command.launch_argv(
            destination=destination,
            git_tag=resolved_git_tag,
            profile=resolved_profile,
            region=resolved_region,
            cluster=cluster,
            stage_dir=remote_stage_dir,
            session_name=resolved_session_name,
            project=project,
            dry_run=dry_run,
            skip_project_check=skip_project_check,
        )
        launch_stdout_buffer = io.StringIO()
        with contextlib.redirect_stdout(launch_stdout_buffer):
            launch_rc = _invoke_workflow_launch(workflow_cli_argv[2:])
        launch_stdout = launch_stdout_buffer.getvalue()
        if launch_stdout:
            typer.echo(launch_stdout, nl=False)
        if launch_rc != 0:
            raise typer.Exit(launch_rc)

        stage_name = Path(remote_stage_dir.rstrip("/")).name
        timestamp = stage_name.replace("remote_stage_", "")
        receipt_path = resolved_config_dir / f"{timestamp}_samples_run_receipt.json"
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt = {
            "analysis_samples": str(analysis_path),
            "command_id": command.command_id,
            "compatible_data_modes": command.compatible_data_modes,
            "detected_data_modes": data_modes,
            "destination": destination,
            "dry_run": dry_run,
            "dy_command": command.dryrun_dy_command if dry_run else command.dy_command,
            "git_tag": resolved_git_tag,
            "remote_stage_dir": remote_stage_dir,
            "samples_tsv": str(resolved_config_dir / f"{timestamp}_samples.tsv"),
            "session_name": resolved_session_name,
            "units_tsv": str(resolved_config_dir / f"{timestamp}_units.tsv"),
            "workflow_argv": workflow_cli_argv,
            "workflow_launch": _parse_workflow_launch_metadata(launch_stdout),
        }
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        typer.echo(f"Samples run receipt: {receipt_path}")
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def workflow_launch(
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region."),
    cluster: Optional[str] = typer.Option(
        None,
        "--cluster",
        "--cluster-name",
        help="ParallelCluster name.",
    ),
    stage_dir: Optional[str] = typer.Option(
        None,
        "--stage-dir",
        help="Specific staging directory containing generated manifests.",
    ),
    run_context_file: Optional[Path] = typer.Option(
        None,
        "--run-context-file",
        help="Local runs.tsv file to copy to config/runs.tsv for run-analysis workflows.",
    ),
    stage_base: str = typer.Option(
        "/fsx/staged_sample_data",
        "--stage-base",
        help="Base staging directory to scan when --stage-dir is omitted.",
    ),
    session_name: str = typer.Option(
        "daylily-omics-analysis",
        "--session-name",
        help="Tmux session name.",
    ),
    destination: str = typer.Option(..., "--destination", help="Required day-clone destination."),
    repository: str = typer.Option(
        "daylily-omics-analysis",
        "--repository",
        help="Repository key to pass to day-clone.",
    ),
    git_tag: str = typer.Option(
        "main",
        "--git-tag",
        "-t",
        help="Git branch or tag passed to day-clone.",
    ),
    project: Optional[str] = typer.Option(None, "--project", help="Project/budget for dyoainit."),
    skip_project_check: bool = typer.Option(
        True,
        "--skip-project-check/--strict-project-check",
        help="Skip or enable upstream project validation in dyoainit.",
    ),
    genome: str = typer.Option("hg38", "--genome", help="Genome build."),
    jobs: int = typer.Option(6, "--jobs", help="Snakemake job count."),
    aligners: str = typer.Option("bwa2a", "--aligners", help="Comma-separated aligner list."),
    dedupers: str = typer.Option("dmd", "--dedupers", help="Comma-separated deduper list."),
    snv_callers: str = typer.Option(
        "deep",
        "--snv-callers",
        help="Comma-separated SNV caller list.",
    ),
    sv_callers: str = typer.Option(
        "",
        "--sv-callers",
        help="Comma-separated SV caller list.",
    ),
    target: str = typer.Option(
        "produce_snv_concordances",
        "--target",
        help="Workflow target.",
    ),
    dy_command: Optional[str] = typer.Option(
        None,
        "--dy-command",
        help="Override the dy-r command entirely.",
    ),
    snakemake_extra: Optional[str] = typer.Option(
        None,
        "--snakemake-extra",
        help="Additional arguments appended to dy-r.",
    ),
    no_containerized: bool = typer.Option(
        False,
        "--no-containerized",
        help="Disable DAY_CONTAINERIZED.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Launch a dry-run workflow command."),
) -> None:
    """Launch daylily-omics-analysis inside tmux on the headnode."""

    from daylily_ec.scripts.common import CommandError

    _warn_if_dayec_env_inactive()
    argv: list[str] = []
    for flag, value in (
        ("--profile", profile),
        ("--region", region),
        ("--cluster", cluster),
        ("--stage-dir", stage_dir),
        ("--run-context-file", str(run_context_file.expanduser()) if run_context_file else None),
        ("--stage-base", stage_base),
        ("--session-name", session_name),
        ("--destination", destination),
        ("--repository", repository),
        ("--git-tag", git_tag),
        ("--project", project),
        ("--genome", genome),
        ("--jobs", str(jobs)),
        ("--aligners", aligners),
        ("--dedupers", dedupers),
        ("--snv-callers", snv_callers),
        ("--sv-callers", sv_callers),
        ("--target", target),
        ("--dy-command", dy_command),
        ("--snakemake-extra", snakemake_extra),
    ):
        if value is not None:
            argv.extend([flag, value])
    argv.append("--skip-project-check" if skip_project_check else "--strict-project-check")
    if no_containerized:
        argv.append("--no-containerized")
    if dry_run:
        argv.append("--dry-run")

    try:
        raise typer.Exit(_invoke_workflow_launch(argv))
    except CommandError as exc:
        _exit_headnode_error(exc)


def repositories_commands(
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        help="Path to daylily_available_repositories.yaml.",
    ),
    repository: Optional[str] = typer.Option(
        None,
        "--repository",
        help="Limit output to one repository key.",
    ),
    command_id: Optional[str] = typer.Option(
        None,
        "--command-id",
        help="Limit output to one analysis command id.",
    ),
) -> None:
    """List blessed analysis command profiles from the repository catalog."""

    from daylily_ec.repositories import load_repository_catalog
    from daylily_ec.scripts.common import CommandError

    try:
        catalog = load_repository_catalog(config)
        payload = catalog.to_public_payload()
        if repository:
            repo_key = repository.strip()
            repositories = payload["repositories"]
            if not isinstance(repositories, dict) or repo_key not in repositories:
                raise CommandError(f"Unknown repository: {repo_key}")
            payload["repositories"] = {repo_key: repositories[repo_key]}
            payload["commands"] = [
                command
                for command in payload["commands"]
                if isinstance(command, dict) and command.get("repository") == repo_key
            ]
        if command_id:
            command_key = command_id.strip()
            payload["commands"] = [
                command
                for command in payload["commands"]
                if isinstance(command, dict) and command.get("command_id") == command_key
            ]
            if not payload["commands"]:
                raise CommandError(f"Unknown analysis command: {command_key}")
        if _json_mode():
            output.emit_json(payload)
            return
        typer.echo(json.dumps(payload, indent=2, sort_keys=False))
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def _emit_mount_payload(payload: Any, *, text: str) -> None:
    if _json_mode():
        output.emit_json(payload)
        return
    typer.echo(text)


def _create_mount_payload(
    *,
    cluster: Optional[str],
    fsx_file_system_id: Optional[str],
    region: str,
    profile: Optional[str],
    source_s3_uri: str,
    mount_id: Optional[str],
    run_id: Optional[str],
    platform: str,
    file_system_path: Optional[str],
    read_only: bool,
    batch_import_metadata_on_create: bool,
    auto_import: str,
    auto_export: Optional[str],
    allow_writeback_admin: bool,
    wait: bool,
    timeout_seconds: int,
    tag: List[str],
) -> Any:
    from daylily_ec.run_mounts import (
        CreateRunMountRequest,
        create_run_mount,
        parse_auto_export_events,
        parse_auto_import_events,
        parse_tags,
    )

    auto_export_events = parse_auto_export_events(
        auto_export,
        allow_writeback_admin=allow_writeback_admin,
        read_only=read_only,
    )
    request = CreateRunMountRequest(
        cluster_name=cluster,
        fsx_file_system_id=fsx_file_system_id,
        region=region,
        profile=profile,
        source_s3_uri=source_s3_uri,
        mount_id=mount_id,
        run_id=run_id,
        platform=platform,
        file_system_path=file_system_path,
        read_only=read_only,
        batch_import_metadata_on_create=batch_import_metadata_on_create,
        auto_import_events=parse_auto_import_events(auto_import),
        auto_export_events=auto_export_events,
        allow_writeback_admin=allow_writeback_admin,
        wait=wait,
        timeout_seconds=timeout_seconds,
        tags=parse_tags(tag),
    )
    return create_run_mount(request)


def mounts_create(
    source_s3_uri: str = typer.Argument(
        ...,
        metavar="S3_URI",
        help="S3 run-directory URI to mount; the final folder becomes the mount id.",
    ),
    cluster: Optional[str] = typer.Option(
        None,
        "--cluster",
        "--cluster-name",
        help="ParallelCluster name used to resolve the FSx file system.",
    ),
    fsx_file_system_id: Optional[str] = typer.Option(
        None,
        "--fsx-file-system-id",
        help="Explicit FSx file system id. Required when --cluster is omitted.",
    ),
    region: str = typer.Option(..., "--region", help="AWS region."),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS profile."),
    mount_id: Optional[str] = typer.Option(None, "--mount-id", help="Safe mount id."),
    run_id: Optional[str] = typer.Option(None, "--run-id", help="Run id for local records."),
    platform: str = typer.Option("OTHER", "--platform", help="Run platform."),
    file_system_path: Optional[str] = typer.Option(
        None,
        "--file-system-path",
        help="FSx API path, normally /run_dir_mounts/<mount_id>/.",
    ),
    read_only: bool = typer.Option(
        True,
        "--read-only/--no-read-only",
        help="Keep the source S3 run directory read-only by policy.",
    ),
    batch_import_metadata_on_create: bool = typer.Option(
        True,
        "--batch-import-metadata-on-create/--no-batch-import-metadata-on-create",
        help="Ask FSx to import metadata when the DRA is created.",
    ),
    auto_import: str = typer.Option(
        "NEW,CHANGED",
        "--auto-import",
        help="Comma-separated FSx AutoImport events, none, or all.",
    ),
    auto_export: Optional[str] = typer.Option(
        None,
        "--auto-export",
        help="Forbidden unless --allow-writeback-admin and --no-read-only are set.",
    ),
    allow_writeback_admin: bool = typer.Option(
        False,
        "--allow-writeback-admin",
        help="Explicit admin override allowing AutoExport writeback policy.",
    ),
    wait: bool = typer.Option(True, "--wait/--no-wait", help="Wait for AVAILABLE."),
    timeout_seconds: int = typer.Option(900, "--timeout-seconds", help="Wait timeout."),
    tag: List[str] = typer.Option([], "--tag", help="Repeatable KEY=VALUE DRA tag."),
) -> None:
    """Create a read-only FSx DRA for a sequencer run directory."""

    from daylily_ec.run_mounts import format_mount_created

    try:
        record = _create_mount_payload(
            cluster=cluster,
            fsx_file_system_id=fsx_file_system_id,
            region=region,
            profile=profile,
            source_s3_uri=source_s3_uri,
            mount_id=mount_id,
            run_id=run_id,
            platform=platform,
            file_system_path=file_system_path,
            read_only=read_only,
            batch_import_metadata_on_create=batch_import_metadata_on_create,
            auto_import=auto_import,
            auto_export=auto_export,
            allow_writeback_admin=allow_writeback_admin,
            wait=wait,
            timeout_seconds=timeout_seconds,
            tag=tag,
        )
        _emit_mount_payload(record.to_output_payload(), text=format_mount_created(record))
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def mount_rundir(
    source_s3_uri: str = typer.Argument(
        ...,
        metavar="S3_URI",
        help="S3 run-directory URI to mount; the final folder becomes the mount id.",
    ),
    cluster: Optional[str] = typer.Option(None, "--cluster", "--cluster-name"),
    fsx_file_system_id: Optional[str] = typer.Option(None, "--fsx-file-system-id"),
    region: str = typer.Option(..., "--region"),
    profile: Optional[str] = typer.Option(None, "--profile"),
    mount_id: Optional[str] = typer.Option(None, "--mount-id"),
    run_id: Optional[str] = typer.Option(None, "--run-id"),
    platform: str = typer.Option("OTHER", "--platform"),
    file_system_path: Optional[str] = typer.Option(None, "--file-system-path"),
    read_only: bool = typer.Option(True, "--read-only/--no-read-only"),
    batch_import_metadata_on_create: bool = typer.Option(
        True,
        "--batch-import-metadata-on-create/--no-batch-import-metadata-on-create",
    ),
    auto_import: str = typer.Option("NEW,CHANGED", "--auto-import"),
    auto_export: Optional[str] = typer.Option(None, "--auto-export"),
    allow_writeback_admin: bool = typer.Option(False, "--allow-writeback-admin"),
    wait: bool = typer.Option(True, "--wait/--no-wait"),
    timeout_seconds: int = typer.Option(900, "--timeout-seconds"),
    tag: List[str] = typer.Option([], "--tag"),
) -> None:
    """Alias for `daylily-ec mounts create`."""

    from daylily_ec.run_mounts import format_mount_created

    try:
        record = _create_mount_payload(
            cluster=cluster,
            fsx_file_system_id=fsx_file_system_id,
            region=region,
            profile=profile,
            source_s3_uri=source_s3_uri,
            mount_id=mount_id,
            run_id=run_id,
            platform=platform,
            file_system_path=file_system_path,
            read_only=read_only,
            batch_import_metadata_on_create=batch_import_metadata_on_create,
            auto_import=auto_import,
            auto_export=auto_export,
            allow_writeback_admin=allow_writeback_admin,
            wait=wait,
            timeout_seconds=timeout_seconds,
            tag=tag,
        )
        _emit_mount_payload(record.to_output_payload(), text=format_mount_created(record))
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def mounts_list(
    cluster: Optional[str] = typer.Option(None, "--cluster", "--cluster-name"),
    fsx_file_system_id: Optional[str] = typer.Option(None, "--fsx-file-system-id"),
    region: str = typer.Option(..., "--region"),
    profile: Optional[str] = typer.Option(None, "--profile"),
) -> None:
    """List FSx run directory mounts."""

    from daylily_ec.run_mounts import format_mount_list, list_run_mounts

    try:
        records = list_run_mounts(
            cluster_name=cluster,
            fsx_file_system_id=fsx_file_system_id,
            region=region,
            profile=profile,
        )
        payload = {"mounts": [record.to_output_payload() for record in records]}
        _emit_mount_payload(payload, text=format_mount_list(records))
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def mounts_describe(
    mount_id: Optional[str] = typer.Option(None, "--mount-id"),
    association_id: Optional[str] = typer.Option(None, "--association-id"),
    cluster: Optional[str] = typer.Option(None, "--cluster", "--cluster-name"),
    fsx_file_system_id: Optional[str] = typer.Option(None, "--fsx-file-system-id"),
    region: str = typer.Option(..., "--region"),
    profile: Optional[str] = typer.Option(None, "--profile"),
) -> None:
    """Describe one FSx run directory mount."""

    from daylily_ec.run_mounts import describe_run_mount, format_mount_described

    try:
        record = describe_run_mount(
            mount_id=mount_id,
            association_id=association_id,
            cluster_name=cluster,
            fsx_file_system_id=fsx_file_system_id,
            region=region,
            profile=profile,
        )
        _emit_mount_payload(record.to_output_payload(), text=format_mount_described(record))
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def mounts_delete(
    mount_id: Optional[str] = typer.Option(None, "--mount-id"),
    association_id: Optional[str] = typer.Option(None, "--association-id"),
    cluster: Optional[str] = typer.Option(None, "--cluster", "--cluster-name"),
    fsx_file_system_id: Optional[str] = typer.Option(None, "--fsx-file-system-id"),
    region: str = typer.Option(..., "--region"),
    profile: Optional[str] = typer.Option(None, "--profile"),
    wait: bool = typer.Option(True, "--wait/--no-wait"),
    timeout_seconds: int = typer.Option(900, "--timeout-seconds"),
) -> None:
    """Delete one FSx DRA without deleting S3 objects or cached FSx data."""

    from daylily_ec.run_mounts import delete_run_mount, format_mount_deleted

    try:
        record = delete_run_mount(
            mount_id=mount_id,
            association_id=association_id,
            cluster_name=cluster,
            fsx_file_system_id=fsx_file_system_id,
            region=region,
            profile=profile,
            wait=wait,
            timeout_seconds=timeout_seconds,
        )
        _emit_mount_payload(record.to_output_payload(), text=format_mount_deleted(record))
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def mounts_verify(
    mount_id: Optional[str] = typer.Option(None, "--mount-id"),
    association_id: Optional[str] = typer.Option(None, "--association-id"),
    cluster: str = typer.Option(..., "--cluster", "--cluster-name"),
    fsx_file_system_id: Optional[str] = typer.Option(None, "--fsx-file-system-id"),
    region: str = typer.Option(..., "--region"),
    profile: Optional[str] = typer.Option(None, "--profile"),
    platform: Optional[str] = typer.Option(None, "--platform"),
    timeout_seconds: int = typer.Option(300, "--timeout-seconds"),
) -> None:
    """Verify a run mount path is usable on the cluster headnode."""

    from daylily_ec.run_mounts import format_mount_verified, verify_run_mount

    try:
        payload = verify_run_mount(
            mount_id=mount_id,
            association_id=association_id,
            cluster_name=cluster,
            fsx_file_system_id=fsx_file_system_id,
            region=region,
            profile=profile,
            platform=platform,
            timeout_seconds=timeout_seconds,
        )
        _emit_mount_payload(payload, text=format_mount_verified(payload))
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def _workflow_run_dir(session: Optional[str], run_dir: Optional[str]) -> str:
    from daylily_ec.scripts.common import CommandError

    if bool(session) == bool(run_dir):
        raise CommandError("Provide exactly one of --session or --run-dir.")
    if run_dir:
        return run_dir.rstrip("/")
    return f"/home/ubuntu/daylily-runs/{session}"


def _read_workflow_file(
    *,
    profile: Optional[str],
    region: Optional[str],
    cluster: Optional[str],
    session: Optional[str],
    run_dir: Optional[str],
    filename: str,
    tail_lines: Optional[int] = None,
):
    from daylily_ec.aws.ssm import SsmError, run_shell, wait_for_ssm_online
    from daylily_ec.scripts.common import CommandError

    try:
        resolved_run_dir = _workflow_run_dir(session, run_dir)
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
        file_path = f"{resolved_run_dir}/{filename}"
        if tail_lines is None:
            read_command = 'cat "$FILE_PATH"'
        else:
            read_command = f'tail -n {max(tail_lines, 1)} "$FILE_PATH"'
        script = f"""
set -euo pipefail
if [[ "$(id -un)" != "ubuntu" ]]; then
  echo "__DAYLILY_ERROR__=wrong_user"
  exit 5
fi
FILE_PATH={shlex.quote(file_path)}
if [[ ! -f "$FILE_PATH" ]]; then
  echo "__DAYLILY_ERROR__=missing_file:$FILE_PATH"
  exit 2
fi
{read_command}
"""
        return run_shell(
            target.instance_id,
            resolved_region,
            script,
            profile=resolved_profile,
            timeout=120,
            comment=f"Read Daylily workflow {filename}",
        )
    except (CommandError, SsmError, TimeoutError) as exc:
        _exit_headnode_error(exc)


def _parse_workflow_status_payload(stdout: str) -> dict[str, Any]:
    from daylily_ec.scripts.common import CommandError

    try:
        payload = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        start = stdout.find("{")
        end = stdout.rfind("}")
        if start < 0 or end <= start:
            raise
        payload = json.loads(stdout[start : end + 1])
    if not isinstance(payload, dict):
        raise CommandError("Workflow status file contained non-object JSON.")
    return payload


def workflow_status(
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region."),
    cluster: Optional[str] = typer.Option(None, "--cluster", "--cluster-name"),
    session: Optional[str] = typer.Option(None, "--session", help="Tmux session/run name."),
    run_dir: Optional[str] = typer.Option(None, "--run-dir", help="Explicit run directory."),
) -> None:
    """Read a workflow status.json file from the headnode."""

    from daylily_ec.scripts.common import CommandError

    _warn_if_dayec_env_inactive()
    try:
        result = _read_workflow_file(
            profile=profile,
            region=region,
            cluster=cluster,
            session=session,
            run_dir=run_dir,
            filename="status.json",
        )
        payload = _parse_workflow_status_payload(result.stdout)
    except (CommandError, json.JSONDecodeError) as exc:
        _exit_headnode_error(exc)

    if _json_mode():
        output.emit_json(payload)
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=False))


def workflow_logs(
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region."),
    cluster: Optional[str] = typer.Option(None, "--cluster", "--cluster-name"),
    session: Optional[str] = typer.Option(None, "--session", help="Tmux session/run name."),
    run_dir: Optional[str] = typer.Option(None, "--run-dir", help="Explicit run directory."),
    lines: int = typer.Option(200, "--lines", help="Number of tmux log lines to print."),
) -> None:
    """Tail a workflow tmux.log file from the headnode."""

    _warn_if_dayec_env_inactive()
    result = _read_workflow_file(
        profile=profile,
        region=region,
        cluster=cluster,
        session=session,
        run_dir=run_dir,
        filename="tmux.log",
        tail_lines=lines,
    )
    if result.stdout:
        typer.echo(result.stdout.rstrip())
    if result.stderr:
        typer.echo(result.stderr.rstrip(), err=True)


def _state_payload(path: Path) -> dict[str, Any]:
    from daylily_ec.state.store import load_state_record

    record = load_state_record(path)
    payload = record.model_dump(mode="json")
    payload["path"] = str(path)
    return payload


def state_list() -> None:
    """List Daylily state files."""

    from daylily_ec.state.store import config_dir

    state_dir = config_dir()
    rows: list[dict[str, Any]] = []
    for path in sorted(state_dir.glob("state_*.json")):
        try:
            rows.append(_state_payload(path))
        except Exception as exc:  # noqa: BLE001
            rows.append({"path": str(path), "error": str(exc)})

    payload = {"state_dir": str(state_dir), "states": rows}
    if _json_mode():
        output.emit_json(payload)
        return

    if not rows:
        output.print_text(f"No state files found in {state_dir}.")
        return
    output.heading("Daylily state files")
    header = "%-32s %-16s %-12s %s" % ("CLUSTER_NAME", "RUN_ID", "REGION", "PATH")
    output.print_text(header)
    output.print_text("%s %s %s %s" % ("\u2500" * 32, "\u2500" * 16, "\u2500" * 12, "\u2500" * 30))
    for row in rows:
        if "error" in row:
            output.print_text("%-32s %-16s %-12s %s" % ("ERROR", "", "", row["path"]))
            continue
        output.print_text(
            "%-32s %-16s %-12s %s"
            % (
                row.get("cluster_name") or "",
                row.get("run_id") or "",
                row.get("region") or "",
                row["path"],
            )
        )


def _latest_state_for_cluster(cluster_name: str) -> dict[str, Any]:
    from daylily_ec.scripts.common import CommandError
    from daylily_ec.state.store import config_dir

    matches: list[dict[str, Any]] = []
    for path in sorted(config_dir().glob("state_*.json")):
        try:
            payload = _state_payload(path)
        except Exception:
            continue
        if payload.get("cluster_name") == cluster_name:
            matches.append(payload)
    if not matches:
        raise CommandError(f"No state file found for cluster '{cluster_name}'.")
    return sorted(matches, key=lambda item: (str(item.get("run_id") or ""), str(item["path"])))[-1]


def state_show(
    state_file: Optional[Path] = typer.Option(
        None,
        "--state-file",
        help="State JSON file to show.",
    ),
    cluster_name: Optional[str] = typer.Option(
        None,
        "--cluster-name",
        "--cluster",
        help="Show the newest state file for this cluster.",
    ),
) -> None:
    """Show one Daylily state record."""

    from daylily_ec.scripts.common import CommandError

    try:
        if bool(state_file) == bool(cluster_name):
            raise CommandError("Provide exactly one of --state-file or --cluster-name.")
        payload = (
            _state_payload(state_file.expanduser().resolve())
            if state_file
            else _latest_state_for_cluster(str(cluster_name))
        )
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)

    if _json_mode():
        output.emit_json(payload)
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=False))


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
        required_policy(mutates_state=True, long_running=True),
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
        "aws",
        "AWS readiness validation helpers.",
        [],
    )
    register_group_commands(
        registry,
        "aws/validate",
        "Read-only AWS permission and quota validation.",
        [
            (
                "permissions",
                aws_validate_permissions,
                required_policy(supports_json=True),
            ),
            (
                "quotas",
                aws_validate_quotas,
                required_policy(supports_json=True),
            ),
            ("all", aws_validate_all, required_policy(supports_json=True)),
        ],
    )
    register_group_commands(
        registry,
        "cluster",
        "ParallelCluster inspection helpers.",
        [
            ("list", cluster_list, REQUIRED_JSON),
            ("describe", cluster_describe, REQUIRED_JSON),
            ("wait", cluster_wait, REQUIRED_LONG_RUNNING),
        ],
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
            ("configure", headnode_configure, REQUIRED_MUTATING_LONG_RUNNING),
        ],
    )
    register_group_commands(
        registry,
        "samples",
        "Sample staging helpers.",
        [
            ("stage", samples_stage, REQUIRED_MUTATING_LONG_RUNNING),
            ("run", samples_run, REQUIRED_MUTATING_LONG_RUNNING),
        ],
    )
    register_group_commands(
        registry,
        "workflow",
        "Headnode workflow helpers.",
        [
            ("launch", workflow_launch, REQUIRED_MUTATING_LONG_RUNNING),
            ("status", workflow_status, REQUIRED_JSON),
            ("logs", workflow_logs, required_policy()),
        ],
    )
    register_group_commands(
        registry,
        "repositories",
        "Repository catalog and blessed analysis command helpers.",
        [("commands", repositories_commands, EXEMPT_JSON)],
    )
    register_group_commands(
        registry,
        "exports",
        "Explicit FSx output DRA export helpers.",
        [
            (
                "attach",
                exports_attach,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
            (
                "run",
                exports_run,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
            (
                "detach",
                exports_detach,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
        ],
    )
    register_group_commands(
        registry,
        "mounts",
        "FSx run-directory mount helpers.",
        [
            ("list", mounts_list, REQUIRED_JSON),
            (
                "create",
                mounts_create,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
            ("describe", mounts_describe, REQUIRED_JSON),
            (
                "delete",
                mounts_delete,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
            ("verify", mounts_verify, required_policy(supports_json=True, long_running=True)),
        ],
    )
    register_group_commands(
        registry,
        "mount",
        "Run-directory mount aliases.",
        [
            (
                "rundir",
                mount_rundir,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            )
        ],
    )
    register_group_commands(
        registry,
        "state",
        "Local Daylily state inspection helpers.",
        [
            ("list", state_list, EXEMPT_JSON),
            ("show", state_show, EXEMPT_JSON),
        ],
    )


app = create_app(spec)


def main() -> None:
    raise SystemExit(run(spec))


if __name__ == "__main__":
    main()
