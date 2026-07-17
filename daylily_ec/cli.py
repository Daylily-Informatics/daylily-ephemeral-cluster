"""CLI entry point for daylily-ec built on cli-core-yo v2."""

from __future__ import annotations

import contextlib
import base64
import csv
import functools
import hashlib
import io
import json
import logging
import os
import shlex
import subprocess
import sys
import traceback
import time
from time import monotonic as _monotonic
from pathlib import Path, PurePosixPath
from typing import Any, List, Optional

import click
import typer
from cli_core_yo import output
from cli_core_yo import app as cli_core_app
from cli_core_yo.app import create_app
from cli_core_yo.errors import CliCoreYoError
from cli_core_yo.runtime import get_context
from cli_core_yo.runtime import _reset as _reset_cli_core_runtime
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
from daylily_ec import versioning
from daylily_ec.aws.spot_pricing import (
    DEFAULT_GLOBAL_SPOT_MAX_COST,
    DEFAULT_SPOT_COST_LIMIT_PCT,
    DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD,
    MAX_GLOBAL_SPOT_MAX_COST,
    MAX_SPOT_COST_LIMIT_PCT,
    MIN_SPOT_COST_LIMIT_PCT,
    validate_spot_pricing_limits,
)
from daylily_ec.resources import ensure_extracted
from daylily_ec.workflow.snakemake_resources import DEFAULT_JOB_MAX_RUNTIME_MINUTES

EXPORT_TRIGGERS = {"none", "on-success", "on-fail", "all"}
BENCHMARK_GENOME_BUILDS = {"hg38", "hg38_broad", "b37"}
DEFAULT_CREATE_REGION_AZ = "us-west-2d"
DEFAULT_CREATE_CLUSTER_TYPE = "intel"

logger = logging.getLogger(__name__)


def _format_create_runtime(seconds: float) -> str:
    """Return a compact wall-clock duration for the final create line."""

    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {remaining_seconds}s"
    if minutes:
        return f"{minutes}m {remaining_seconds}s"
    return f"{remaining_seconds}s"


def _report_create_runtime(callback):
    """Print and INFO-log total create wall time on every callback exit."""

    @functools.wraps(callback)
    def wrapped(*args, **kwargs):
        started_at = _monotonic()
        try:
            return callback(*args, **kwargs)
        finally:
            elapsed_seconds = max(0.0, _monotonic() - started_at)
            message = (
                "Total DYEC create runtime: "
                f"{_format_create_runtime(elapsed_seconds)} ({elapsed_seconds:.1f}s)"
            )
            logger.info(message)
            typer.echo(message)

    return wrapped


def _validate_analysis_launch_options(
    *,
    analysis_id: str,
    executing_entity: str,
    cluster: Optional[str],
    export_destination_s3_uri: Optional[str],
    export_trigger: str,
    delete_on_export_success: bool,
) -> Optional[str]:
    from daylily_ec.analysis_identity import analysis_source_path, validate_analysis_segment
    from daylily_ec.workflow.export_data import resolve_launch_export_destination_s3_uri

    try:
        resolved_analysis_id = validate_analysis_segment(
            analysis_id,
            field_name="analysis_id",
        )
        resolved_executing_entity = validate_analysis_segment(
            executing_entity,
            field_name="executing_entity",
        )
        if export_trigger not in EXPORT_TRIGGERS:
            raise ValueError("export_trigger must be one of: " + ", ".join(sorted(EXPORT_TRIGGERS)))
        if export_destination_s3_uri and export_trigger == "none":
            raise ValueError(
                "--export-trigger must not be none when --export-destination-s3-uri is set"
            )
        if export_trigger != "none" and not export_destination_s3_uri:
            raise ValueError("--export-destination-s3-uri is required when --export-trigger is set")
        if delete_on_export_success and not export_destination_s3_uri:
            raise ValueError("--delete-on-export-success requires --export-destination-s3-uri")
        resolved_export_destination_s3_uri = None
        if export_destination_s3_uri:
            resolved_export_destination_s3_uri = resolve_launch_export_destination_s3_uri(
                export_destination_s3_uri,
                source_path=analysis_source_path(
                    executing_entity=resolved_executing_entity,
                    analysis_id=resolved_analysis_id,
                    headnode=True,
                ),
                cluster_name=cluster,
            )
        return resolved_export_destination_s3_uri
    except (RuntimeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


def _resolve_executing_entity_option(
    *,
    executing_entity: Optional[str],
    cluster: Optional[str],
) -> str:
    from daylily_ec.analysis_identity import validate_analysis_segment

    candidate = (executing_entity or "").strip() or (cluster or "").strip()
    if not candidate:
        raise typer.BadParameter("--executing-entity is required when --cluster is omitted")
    try:
        return validate_analysis_segment(candidate, field_name="executing_entity")
    except (RuntimeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


def _dayec_info_hook() -> list[tuple[str, str]]:
    return [("Project Root", str(Path(__file__).resolve().parents[1]))]


def _install_dayec_version_provider() -> None:
    original_get_dist_version = cli_core_app._get_dist_version

    def _get_dist_version(dist_name: str) -> str:
        if dist_name == versioning.DIST_NAME:
            return versioning.get_version()
        return original_get_dist_version(dist_name)

    cli_core_app._get_dist_version = _get_dist_version


_install_dayec_version_provider()


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
            as_user="auto",
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


@_report_create_runtime
def create(
    region_az: str = typer.Option(
        DEFAULT_CREATE_REGION_AZ,
        "--region-az",
        help=f"AWS region + availability zone. Defaults to {DEFAULT_CREATE_REGION_AZ}.",
    ),
    cluster_type: str = typer.Option(
        DEFAULT_CREATE_CLUSTER_TYPE,
        "--cluster-type",
        help=(
            "Cluster template family to autoselect when config does not set "
            "cluster_template_yaml. One of: dragen, intel, rhel, sentieon-single."
        ),
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE env var.",
    ),
    regional_cluster_cap: Optional[int] = typer.Option(
        None,
        "--regional-cluster-cap",
        help=(
            "Maximum projected non-deleted ParallelCluster records in the target region. "
            "Effective default: 5. Values above 5 require both acknowledgement flags."
        ),
    ),
    acknowledge_regional_cap_increase: bool = typer.Option(
        False,
        "--acknowledge-regional-cap-increase",
        help="Acknowledge the explicit policy override when raising the regional cap above 5.",
    ),
    acknowledge_regional_cap_risk: bool = typer.Option(
        False,
        "--acknowledge-regional-cap-risk",
        help="Acknowledge the regional capacity and cost risk when raising the cap above 5.",
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
    slurm_accounting: str = typer.Option(
        "on",
        "--slurm-accounting",
        click_type=click.Choice(["on", "off"], case_sensitive=True),
        help=(
            "Enable or disable the post-create Slurm accounting stage. "
            "The initial cluster build never includes accounting."
        ),
    ),
    fail_on_sacct_error: bool = typer.Option(
        False,
        "--fail-on-sacct-error",
        help=(
            "Return the AWS failure exit code when the post-create Slurm "
            "accounting stage fails. Ignored when --slurm-accounting off."
        ),
    ),
    create_slurm_accounting_if_missing: bool = typer.Option(
        False,
        "--create-slurm-accounting-if-missing",
        help=(
            "Approve creating the first regional Slurm accounting service when "
            "none exists. Requires --acknowledge-slurm-accounting-create-cost."
        ),
    ),
    acknowledge_slurm_accounting_create_cost: bool = typer.Option(
        False,
        "--acknowledge-slurm-accounting-create-cost",
        help=(
            "Acknowledge the cost of creating the first regional Slurm accounting "
            "service. Requires --create-slurm-accounting-if-missing."
        ),
    ),
    disable_budget_enforcement: bool = typer.Option(
        False,
        "--disable-budget-enforcement",
        help="Skip cluster AWS Budget enforcement; sbatch cost-center validation remains required.",
    ),
    budget_project: Optional[str] = typer.Option(
        None,
        "--budget-project",
        help="Retired. Cluster budgets are named by cluster name.",
    ),
    global_spot_max_cost: float = typer.Option(
        DEFAULT_GLOBAL_SPOT_MAX_COST,
        "--global-spot-max-cost",
        help=(
            "Global maximum PCluster SpotPrice bid per compute resource. "
            f"Defaults to {DEFAULT_GLOBAL_SPOT_MAX_COST:.2f}; hard limit "
            f"0 < value <= {MAX_GLOBAL_SPOT_MAX_COST:.2f}."
        ),
    ),
    spot_cost_limit_pct: float = typer.Option(
        DEFAULT_SPOT_COST_LIMIT_PCT,
        "--spot-cost-limit-pct",
        help=(
            "Multiplier applied to each reference median spot price before the global cap. "
            f"Defaults to {DEFAULT_SPOT_COST_LIMIT_PCT:.2f}; hard limit "
            f"{MIN_SPOT_COST_LIMIT_PCT:.1f} <= value <= {MAX_SPOT_COST_LIMIT_PCT:.1f}."
        ),
    ),
    write_spot_pricing_warn_threshold: float = typer.Option(
        DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD,
        "--write-spot-pricing-warn-threshold",
        help=(
            "Runtime observed spot price threshold that writes "
            "spot_price_warn_exception_messages.log rows. "
            f"Defaults to {DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD:.2f}."
        ),
    ),
) -> None:
    """Create an ephemeral AWS ParallelCluster environment."""

    from daylily_ec.workflow.create_cluster import (
        normalize_create_cluster_type,
        parse_create_repo_overrides,
        run_create_workflow,
        validate_create_cluster_type_region,
        validate_regional_cluster_cap_options,
    )

    _warn_if_dayec_env_inactive()
    try:
        cluster_type = normalize_create_cluster_type(cluster_type)
        validate_create_cluster_type_region(cluster_type, region_az)
        repo_overrides = parse_create_repo_overrides(repo_override)
        validate_regional_cluster_cap_options(
            regional_cluster_cap,
            acknowledge_regional_cap_increase=acknowledge_regional_cap_increase,
            acknowledge_regional_cap_risk=acknowledge_regional_cap_risk,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if budget_project:
        raise typer.BadParameter(
            "--budget-project is retired; cluster budgets are named by cluster name."
        )
    if create_slurm_accounting_if_missing != acknowledge_slurm_accounting_create_cost:
        missing_flag = (
            "--acknowledge-slurm-accounting-create-cost"
            if create_slurm_accounting_if_missing
            else "--create-slurm-accounting-if-missing"
        )
        raise typer.BadParameter(
            "--create-slurm-accounting-if-missing and "
            "--acknowledge-slurm-accounting-create-cost must be supplied together; "
            f"missing {missing_flag}."
        )
    try:
        (
            global_spot_max_cost,
            spot_cost_limit_pct,
            write_spot_pricing_warn_threshold,
        ) = validate_spot_pricing_limits(
            global_spot_max_cost=global_spot_max_cost,
            spot_cost_limit_pct=spot_cost_limit_pct,
            write_spot_pricing_warn_threshold=write_spot_pricing_warn_threshold,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if debug:
        logging.basicConfig(level=logging.DEBUG)

    output.action("Creating cluster in %s ..." % region_az)
    rc = run_create_workflow(
        region_az,
        profile=profile,
        config_path=config,
        cluster_type=cluster_type,
        pass_on_warn=pass_on_warn,
        debug=debug,
        non_interactive=non_interactive,
        disable_budget_enforcement=disable_budget_enforcement,
        budget_project=budget_project,
        global_spot_max_cost=global_spot_max_cost,
        spot_cost_limit_pct=spot_cost_limit_pct,
        write_spot_pricing_warn_threshold=write_spot_pricing_warn_threshold,
        repo_overrides=repo_overrides or None,
        regional_cluster_cap=regional_cluster_cap,
        acknowledge_regional_cap_increase=acknowledge_regional_cap_increase,
        acknowledge_regional_cap_risk=acknowledge_regional_cap_risk,
        slurm_accounting=slurm_accounting,
        fail_on_sacct_error=fail_on_sacct_error,
        create_slurm_accounting_if_missing=create_slurm_accounting_if_missing,
        acknowledge_slurm_accounting_create_cost=(acknowledge_slurm_accounting_create_cost),
    )
    raise SystemExit(rc)


def slurm_accounting_ensure(
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
    stack_name: str = typer.Option(
        "",
        "--stack-name",
        help="Explicit regional DayEC Slurm accounting stack name.",
    ),
    database_name: str = typer.Option(
        "dayec_slurm_acct",
        "--database-name",
        help="Slurm accounting database name.",
    ),
    db_username: str = typer.Option(
        "slurm_acct",
        "--db-username",
        help="Slurm accounting database user name.",
    ),
    instance_type: str = typer.Option(
        "t4g.micro",
        "--instance-type",
        help="EC2 instance type for a newly created MariaDB host.",
    ),
) -> None:
    """Ensure the single DayEC Slurm accounting MariaDB stack for a region."""

    from daylily_ec.aws.cloudformation import ensure_pcluster_env_stack
    from daylily_ec.aws.context import AWSContext
    from daylily_ec.aws.slurm_accounting import (
        SlurmAccountingError,
        ensure_slurm_accounting_db,
    )

    _warn_if_dayec_env_inactive()
    try:
        aws_ctx = AWSContext.build(region_az, profile=profile)
        cfn_outputs = ensure_pcluster_env_stack(aws_ctx, region_az)
        if not cfn_outputs.vpc_id or not cfn_outputs.private_subnet_id:
            raise SlurmAccountingError("Baseline stack is missing VPC or private subnet outputs.")
        db = ensure_slurm_accounting_db(
            aws_ctx,
            region_az=region_az,
            vpc_id=cfn_outputs.vpc_id,
            private_subnet_id=cfn_outputs.private_subnet_id,
            create_if_missing=True,
            stack_name=stack_name,
            database_name=database_name,
            username=db_username,
            instance_type=instance_type,
            warning_callback=output.warning,
        )
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)

    payload = {
        "stack_name": db.stack_name,
        "status": db.status,
        "database_name": db.database_name,
        "username": db.username,
        "client_security_group_id": db.client_security_group_id,
        "instance_id": db.instance_id,
    }
    if _json_mode():
        output.emit_json(payload)
        return

    output.heading("Slurm accounting DB")
    output.print_text(f"Stack:     {db.stack_name}")
    output.print_text(f"Status:    {db.status}")
    output.print_text(f"Database:  {db.database_name}")
    output.print_text(f"User:      {db.username}")
    output.print_text(f"Client SG: {db.client_security_group_id}")
    if db.instance_id:
        output.print_text(f"Instance:  {db.instance_id}")


def slurm_accounting_attach(
    cluster: str = typer.Option(
        ...,
        "--cluster",
        help="Existing ParallelCluster name.",
    ),
    region: str = typer.Option(
        ...,
        "--region",
        help="AWS region containing the existing cluster.",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE.",
    ),
    cluster_configuration: Optional[Path] = typer.Option(
        None,
        "--cluster-configuration",
        help=("Original ParallelCluster YAML. Defaults to the newest matching DYEC state record."),
    ),
    stack_name: str = typer.Option(
        "",
        "--stack-name",
        help="Explicit existing regional DayEC Slurm accounting stack name.",
    ),
    database_name: str = typer.Option(
        "dayec_slurm_acct",
        "--database-name",
        help="Slurm accounting database name.",
    ),
    db_username: str = typer.Option(
        "slurm_acct",
        "--db-username",
        help="Slurm accounting database user name.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate and write the update config without submitting the real update.",
    ),
) -> None:
    """Attach existing Slurm accounting to a healthy cluster after creation."""
    from daylily_ec.workflow.attach_slurm_accounting import (
        attach_slurm_accounting,
    )

    _warn_if_dayec_env_inactive()
    try:
        result = attach_slurm_accounting(
            cluster_name=cluster,
            region=region,
            profile=profile,
            cluster_configuration=cluster_configuration,
            stack_name=stack_name,
            database_name=database_name,
            db_username=db_username,
            dry_run_only=dry_run,
        )
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)

    payload = {
        "cluster_name": result.cluster_name,
        "region": result.region,
        "accounting_stack_name": result.accounting_stack_name,
        "update_config_path": result.update_config_path,
        "dry_run_only": result.dry_run_only,
        "update_submitted": result.update_submitted,
    }
    if _json_mode():
        output.emit_json(payload)
        return

    output.heading("Slurm accounting attachment")
    output.print_text(f"Cluster:       {result.cluster_name}")
    output.print_text(f"Region:        {result.region}")
    output.print_text(f"Stack:         {result.accounting_stack_name}")
    output.print_text(f"Update config: {result.update_config_path}")
    if result.dry_run_only:
        output.success("ParallelCluster update dry-run succeeded; no update was submitted.")
    else:
        output.success("ParallelCluster accounting update submitted.")


def _cost_center_context(profile: Optional[str], home_region: str):
    from daylily_ec.aws.context import AWSContext

    aws_ctx = AWSContext.build_region(home_region, profile=profile)
    return aws_ctx, aws_ctx.client("dynamodb")


def cost_centers_ensure_registry(
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    home_region: str = typer.Option("us-west-2", "--home-region", help="Cost-center home region."),
    table_name: str = typer.Option(
        "dayec-cost-centers", "--table-name", help="Registry table name."
    ),
    usage_table_name: str = typer.Option(
        "dayec-cost-center-usage",
        "--usage-table-name",
        help="Usage summary table name.",
    ),
) -> None:
    """Ensure global cost-center registry DynamoDB tables exist."""
    from daylily_ec.aws.cost_centers import ensure_cost_center_registry

    _warn_if_dayec_env_inactive()
    try:
        aws_ctx, dynamodb = _cost_center_context(profile, home_region)
        payload = ensure_cost_center_registry(
            dynamodb,
            table_name=table_name,
            usage_table_name=usage_table_name,
            actor_arn=aws_ctx.caller_arn,
        )
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)
    _emit_payload(payload, f"Cost-center registry ready: {payload}")


def cost_centers_create(
    name: str = typer.Argument(..., help="Cost-center name."),
    monthly_cap_usd: str = typer.Option(..., "--monthly-cap-usd", help="Monthly cap in USD."),
    allowed_user: Optional[List[str]] = typer.Option(None, "--allowed-user", help="Allowed user."),
    allowed_group: Optional[List[str]] = typer.Option(
        None, "--allowed-group", help="Allowed group."
    ),
    owner_email: Optional[List[str]] = typer.Option(None, "--owner-email", help="Owner email."),
    notes: str = typer.Option("", "--notes", help="Free-text notes."),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    home_region: str = typer.Option("us-west-2", "--home-region", help="Cost-center home region."),
    table_name: str = typer.Option(
        "dayec-cost-centers", "--table-name", help="Registry table name."
    ),
    usage_table_name: str = typer.Option(
        "dayec-cost-center-usage",
        "--usage-table-name",
        help="Usage summary table initialized for immediate Slurm submission.",
    ),
) -> None:
    """Create an active cost center and its current-month zero usage snapshot."""
    from daylily_ec.aws.cost_centers import create_cost_center

    _warn_if_dayec_env_inactive()
    try:
        aws_ctx, dynamodb = _cost_center_context(profile, home_region)
        item = create_cost_center(
            dynamodb,
            name,
            monthly_cap_usd=monthly_cap_usd,
            allowed_users=allowed_user or (),
            allowed_groups=allowed_group or (),
            owner_emails=owner_email or (),
            notes=notes,
            actor_arn=aws_ctx.caller_arn,
            table_name=table_name,
            usage_table_name=usage_table_name,
        )
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)
    _emit_payload(item.to_dict(), f"Created cost center: {item.name}")


def cost_centers_edit(
    name: str = typer.Argument(..., help="Cost-center name."),
    monthly_cap_usd: Optional[str] = typer.Option(
        None, "--monthly-cap-usd", help="Monthly cap in USD."
    ),
    allowed_user: Optional[List[str]] = typer.Option(
        None, "--allowed-user", help="Replacement allowed user list."
    ),
    allowed_group: Optional[List[str]] = typer.Option(
        None, "--allowed-group", help="Replacement allowed group list."
    ),
    owner_email: Optional[List[str]] = typer.Option(
        None, "--owner-email", help="Replacement owner email list."
    ),
    notes: Optional[str] = typer.Option(None, "--notes", help="Replacement notes."),
    status: Optional[str] = typer.Option(
        None, "--status", help="Replacement status: active or disabled."
    ),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    home_region: str = typer.Option("us-west-2", "--home-region", help="Cost-center home region."),
    table_name: str = typer.Option(
        "dayec-cost-centers", "--table-name", help="Registry table name."
    ),
) -> None:
    """Edit provided cost-center fields."""
    from daylily_ec.aws.cost_centers import edit_cost_center

    _warn_if_dayec_env_inactive()
    try:
        aws_ctx, dynamodb = _cost_center_context(profile, home_region)
        item = edit_cost_center(
            dynamodb,
            name,
            monthly_cap_usd=monthly_cap_usd,
            allowed_users=allowed_user,
            allowed_groups=allowed_group,
            owner_emails=owner_email,
            notes=notes,
            status=status,
            actor_arn=aws_ctx.caller_arn,
            table_name=table_name,
        )
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)
    _emit_payload(item.to_dict(), f"Updated cost center: {item.name}")


def cost_centers_disable(
    name: str = typer.Argument(..., help="Cost-center name."),
    reason: str = typer.Option(..., "--reason", help="Disable reason."),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    home_region: str = typer.Option("us-west-2", "--home-region", help="Cost-center home region."),
    table_name: str = typer.Option(
        "dayec-cost-centers", "--table-name", help="Registry table name."
    ),
) -> None:
    """Disable a cost center."""
    from daylily_ec.aws.cost_centers import disable_cost_center

    _warn_if_dayec_env_inactive()
    try:
        aws_ctx, dynamodb = _cost_center_context(profile, home_region)
        item = disable_cost_center(
            dynamodb,
            name,
            reason=reason,
            actor_arn=aws_ctx.caller_arn,
            table_name=table_name,
        )
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)
    _emit_payload(item.to_dict(), f"Disabled cost center: {item.name}")


def cost_centers_show(
    name: str = typer.Argument(..., help="Cost-center name."),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    home_region: str = typer.Option("us-west-2", "--home-region", help="Cost-center home region."),
    table_name: str = typer.Option(
        "dayec-cost-centers", "--table-name", help="Registry table name."
    ),
) -> None:
    """Show one cost center."""
    from daylily_ec.aws.cost_centers import get_cost_center

    _warn_if_dayec_env_inactive()
    try:
        _aws_ctx, dynamodb = _cost_center_context(profile, home_region)
        item = get_cost_center(dynamodb, name, table_name=table_name)
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)
    _emit_payload(item.to_dict(), json.dumps(item.to_dict(), indent=2))


def cost_centers_list(
    status: str = typer.Option("all", "--status", help="active, disabled, system, or all."),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    home_region: str = typer.Option("us-west-2", "--home-region", help="Cost-center home region."),
    table_name: str = typer.Option(
        "dayec-cost-centers", "--table-name", help="Registry table name."
    ),
) -> None:
    """List cost centers."""
    from daylily_ec.aws.cost_centers import list_cost_centers

    _warn_if_dayec_env_inactive()
    try:
        _aws_ctx, dynamodb = _cost_center_context(profile, home_region)
        items = list_cost_centers(dynamodb, table_name=table_name, status=status)
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)
    payload = {"cost_centers": [item.to_dict() for item in items]}
    _emit_payload(payload, json.dumps(payload, indent=2))


def cost_centers_usage(
    name: Optional[str] = typer.Argument(None, help="Optional cost-center name."),
    month: str = typer.Option(..., "--month", help="Usage month YYYY-MM."),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    home_region: str = typer.Option("us-west-2", "--home-region", help="Cost-center home region."),
    usage_table_name: str = typer.Option(
        "dayec-cost-center-usage",
        "--usage-table-name",
        help="Usage summary table name.",
    ),
) -> None:
    """Show latest monthly usage snapshot for one or all cost centers."""
    from daylily_ec.aws.cost_centers import get_cost_center_usage, list_cost_center_usage

    _warn_if_dayec_env_inactive()
    try:
        _aws_ctx, dynamodb = _cost_center_context(profile, home_region)
        if name:
            item = get_cost_center_usage(
                dynamodb,
                name,
                month=month,
                usage_table_name=usage_table_name,
                allow_missing=True,
            )
            payload: dict[str, object] = {"usage": item.to_dict() if item else None}
        else:
            payload = {
                "usage": [
                    item.to_dict()
                    for item in list_cost_center_usage(
                        dynamodb,
                        month=month,
                        usage_table_name=usage_table_name,
                    )
                ]
            }
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)
    _emit_payload(payload, json.dumps(payload, indent=2))


def cost_centers_put_usage(
    name: str = typer.Argument(..., help="Cost-center name."),
    month: str = typer.Option(..., "--month", help="Usage month YYYY-MM."),
    monthly_spend_usd: str = typer.Option(
        ...,
        "--monthly-spend-usd",
        help="Monthly spend snapshot in USD.",
    ),
    latest_processed_hour: str = typer.Option(
        ...,
        "--latest-processed-hour",
        help="Latest processed UTC hour, for example 2026-07-08T15:00:00Z.",
    ),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    home_region: str = typer.Option("us-west-2", "--home-region", help="Cost-center home region."),
    table_name: str = typer.Option(
        "dayec-cost-centers", "--table-name", help="Registry table name."
    ),
    usage_table_name: str = typer.Option(
        "dayec-cost-center-usage",
        "--usage-table-name",
        help="Usage summary table name.",
    ),
) -> None:
    """Create or replace one monthly cost-center usage snapshot."""
    from daylily_ec.aws.cost_centers import (
        CostCenterUsage,
        get_cost_center,
        put_cost_center_usage,
        utc_now_iso,
    )

    _warn_if_dayec_env_inactive()
    try:
        _aws_ctx, dynamodb = _cost_center_context(profile, home_region)
        get_cost_center(dynamodb, name, table_name=table_name)
        item = put_cost_center_usage(
            dynamodb,
            CostCenterUsage(
                name=name,
                month=month,
                monthly_spend_usd=monthly_spend_usd,
                latest_processed_hour=latest_processed_hour,
                updated_at=utc_now_iso(),
            ),
            usage_table_name=usage_table_name,
        )
        payload: dict[str, object] = {"usage": item.to_dict()}
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)
    _emit_payload(payload, json.dumps(payload, indent=2))


def cost_centers_refresh_usage(
    name: str = typer.Argument(..., help="Dedicated cost-center name."),
    cluster: str = typer.Option(
        ...,
        "--cluster",
        help="ParallelCluster name. Must exactly equal the cost-center name.",
    ),
    month: str = typer.Option(..., "--month", help="Usage month YYYY-MM."),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    home_region: str = typer.Option(
        "us-west-2", "--home-region", help="Cost-center DynamoDB home region."
    ),
    athena_region: str = typer.Option(
        "us-east-1", "--athena-region", help="Region containing the CUR Athena table."
    ),
    database: str = typer.Option("dayec_cur", "--database", help="CUR Glue database."),
    table: str = typer.Option("cur2_hourly", "--table", help="CUR Glue table."),
    athena_output_s3_uri: Optional[str] = typer.Option(
        None,
        "--athena-output-s3-uri",
        help=(
            "Athena query-results S3 URI. Defaults to the authenticated account's dayec-cur bucket."
        ),
    ),
    registry_table_name: str = typer.Option(
        "dayec-cost-centers", "--registry-table-name", help="Cost-center registry table."
    ),
    usage_table_name: str = typer.Option(
        "dayec-cost-center-usage", "--usage-table-name", help="Usage snapshot table."
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Query and calculate authoritative usage without writing DynamoDB.",
    ),
) -> None:
    """Refresh dedicated-cluster monthly usage from authoritative CUR rows."""
    from daylily_ec.aws.cur import CurAthenaConfig
    from daylily_ec.cost_center_refresh import refresh_dedicated_cluster_usage

    _warn_if_dayec_env_inactive()
    try:
        aws_ctx, dynamodb = _cost_center_context(profile, home_region)
        output_s3_uri = athena_output_s3_uri or (
            f"s3://dayec-cur-{aws_ctx.account_id}-us-east-1/dayec-cur/athena-results/"
        )
        result = refresh_dedicated_cluster_usage(
            athena_client=aws_ctx.session.client("athena", region_name=athena_region),
            dynamodb_client=dynamodb,
            cost_center_name=name,
            cluster_name=cluster,
            month=month,
            cur_config=CurAthenaConfig(
                database=database,
                table=table,
                output_s3_uri=output_s3_uri,
                cluster_tag_column="",
                cluster_tag_map_column="resource_tags",
                cluster_tag_key="user_parallelcluster_cluster_name",
                region_column="product_region_code",
                currency_column="line_item_currency_code",
            ),
            registry_table_name=registry_table_name,
            usage_table_name=usage_table_name,
            dry_run=dry_run,
        )
        payload = result.to_dict()
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)
    _emit_payload(payload, json.dumps(payload, indent=2))


def cost_centers_ensure_cur_export(
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    billing_region: str = typer.Option(
        "us-east-1",
        "--billing-region",
        help="BCM Data Exports home region.",
    ),
    bucket: Optional[str] = typer.Option(
        None,
        "--bucket",
        help="S3 bucket for the CUR 2.0 export. Defaults to dayec-cur-<account>-us-east-1.",
    ),
    bucket_region: str = typer.Option(
        "us-east-1",
        "--bucket-region",
        help="Region for the CUR export bucket.",
    ),
    athena_region: Optional[str] = typer.Option(
        None,
        "--athena-region",
        help="Region for Glue/Athena metadata. Defaults to --bucket-region.",
    ),
    export_name: str = typer.Option(
        "dayec-cur2-hourly",
        "--export-name",
        help="BCM Data Export name.",
    ),
    s3_prefix: str = typer.Option(
        "dayec-cur",
        "--s3-prefix",
        help="S3 prefix for delivered export data.",
    ),
    database: str = typer.Option(
        "dayec_cur",
        "--database",
        help="Glue database for Athena CUR queries.",
    ),
    table: str = typer.Option(
        "cur2_hourly",
        "--table",
        help="Glue table for Athena CUR queries.",
    ),
    athena_output_s3_uri: str = typer.Option(
        "",
        "--athena-output-s3-uri",
        help="Athena query result output URI. Defaults under the CUR bucket/prefix.",
    ),
    cluster_tag_key: str = typer.Option(
        "user_parallelcluster_cluster_name",
        "--cluster-tag-key",
        help="CUR resource_tags key used for cluster attribution.",
    ),
    update_existing_export: bool = typer.Option(
        False,
        "--update-existing-export",
        help="Explicitly update an existing same-name Data Export if its definition differs.",
    ),
    adopt_glue_table: bool = typer.Option(
        False,
        "--adopt-glue-table",
        help="Explicitly adopt an existing same-name Glue table that is not dayec-managed.",
    ),
) -> None:
    """Ensure the CUR 2.0 Data Export and Athena table used for cost-center accounting."""
    from daylily_ec.aws.context import AWSContext
    from daylily_ec.aws.cur_export import (
        CurExportConfig,
        default_cur_export_bucket,
        ensure_cur2_athena_source,
    )

    _warn_if_dayec_env_inactive()
    try:
        aws_ctx = AWSContext.build_region(billing_region, profile=profile)
        resolved_bucket = bucket or default_cur_export_bucket(aws_ctx.account_id)
        resolved_athena_region = athena_region or bucket_region
        payload = ensure_cur2_athena_source(
            s3_client=aws_ctx.session.client("s3", region_name=bucket_region),
            bcm_client=aws_ctx.client("bcm-data-exports"),
            glue_client=aws_ctx.session.client("glue", region_name=resolved_athena_region),
            config=CurExportConfig(
                account_id=aws_ctx.account_id,
                bucket=resolved_bucket,
                bucket_region=bucket_region,
                billing_region=billing_region,
                athena_region=resolved_athena_region,
                export_name=export_name,
                s3_prefix=s3_prefix,
                database=database,
                table=table,
                athena_output_s3_uri=athena_output_s3_uri,
                cluster_tag_key=cluster_tag_key,
            ),
            update_existing_export=update_existing_export,
            adopt_glue_table=adopt_glue_table,
        )
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)
    _emit_payload(payload, json.dumps(payload, indent=2, sort_keys=True))


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


def _emit_cluster_tags_text(payload: dict[str, Any]) -> None:
    cluster = payload["cluster"]
    region = payload["region"]
    if payload["dry_run"]:
        output.heading(f"Cluster tag dry-run: {cluster} ({region})")
    elif payload["updated"]:
        output.heading(f"Cluster tags updated: {cluster} ({region})")
    else:
        output.heading(f"Cluster tags: {cluster} ({region})")
    output.print_text(f"Stack:  {payload['stack_id']}")
    output.print_text(f"Status: {payload['stack_status']}")
    if payload["set"]:
        output.print_text(
            "Set:    " + ", ".join(f"{k}={v}" for k, v in sorted(payload["set"].items()))
        )
    if payload["deleted"]:
        output.print_text("Delete: " + ", ".join(payload["deleted"]))
    if payload["updated"] and payload["waited"]:
        output.print_text("Update: complete")
    elif payload["updated"]:
        output.print_text("Update: requested")
    elif payload["dry_run"]:
        output.print_text("Update: not submitted")
    else:
        output.print_text("Update: no changes")

    output.print_text("")
    output.print_text("%-42s %s" % ("KEY", "VALUE"))
    output.print_text("%s %s" % ("-" * 42, "-" * 32))
    for key, value in sorted(payload["after"].items()):
        output.print_text("%-42s %s" % (key, value))


def cluster_tags(
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
    set_values: Optional[List[str]] = typer.Option(
        None,
        "--set",
        metavar="KEY=VALUE",
        help="Set or replace a cluster tag. Repeat for multiple tags.",
    ),
    delete_values: Optional[List[str]] = typer.Option(
        None,
        "--delete",
        metavar="KEY",
        help="Delete an existing cluster tag. Repeat for multiple tags.",
    ),
    wait: bool = typer.Option(
        True,
        "--wait/--no-wait",
        help="Wait for the CloudFormation tag update to complete.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show the requested tag result without updating AWS.",
    ),
) -> None:
    """List or edit tags on the CloudFormation stack backing a cluster."""

    import boto3

    from daylily_ec.aws.cluster_tags import (
        ClusterTagError,
        parse_tag_assignments,
        parse_tag_deletions,
        stack_id_from_describe_cluster,
        update_cluster_stack_tags,
    )
    from daylily_ec.scripts.common import CommandError

    _warn_if_dayec_env_inactive()
    try:
        resolved_profile = _resolved_aws_profile(profile)
        describe_payload = _describe_cluster_payload(
            profile=resolved_profile,
            region=region,
            cluster=cluster,
        )
        stack_id = stack_id_from_describe_cluster(describe_payload)
        set_tags = parse_tag_assignments(set_values)
        delete_keys = parse_tag_deletions(delete_values)
        cfn_client = boto3.Session(
            profile_name=resolved_profile,
            region_name=region,
        ).client("cloudformation")
        result = update_cluster_stack_tags(
            cfn_client,
            stack_id=stack_id,
            set_tags=set_tags,
            delete_keys=delete_keys,
            wait=wait,
            dry_run=dry_run,
        )
    except (ClusterTagError, CommandError) as exc:
        _exit_headnode_error(exc)

    payload = result.to_payload(cluster=cluster, region=region)
    if _json_mode():
        output.emit_json(payload)
        return
    _emit_cluster_tags_text(payload)


def _validate_dewey_analysis_directory_link_options(
    *,
    artifact_registration_command_id: Optional[str],
    dewey_analysis_dir_external_object_id: Optional[str],
    dewey_run_artifact_euid: Optional[str],
    dewey_ursa_analysis_euid: Optional[str],
) -> None:
    options = {
        "--dewey-analysis-dir-external-object-id": dewey_analysis_dir_external_object_id,
        "--dewey-run-artifact-euid": dewey_run_artifact_euid,
        "--dewey-ursa-analysis-euid": dewey_ursa_analysis_euid,
    }
    if not any(str(value or "").strip() for value in options.values()):
        return
    missing = [option for option, value in options.items() if not str(value or "").strip()]
    if missing:
        raise typer.BadParameter(
            "Dewey analysis-directory external-link options must be provided together: "
            + ", ".join(missing)
        )
    if not artifact_registration_command_id:
        raise typer.BadParameter(
            "--artifact-registration-command-id is required with Dewey external-link options"
        )


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
        help="Completed analysis directory under /fsx/analysis_results/<executing-entity>/<analysis-id>/.",
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
    artifact_registration_command_id: Optional[str] = typer.Option(
        None,
        "--artifact-registration-command-id",
        help="Repository catalog command id whose explicit artifact_registration policy should be applied after export.",
    ),
    repository_catalog: Optional[Path] = typer.Option(
        None,
        "--repository-catalog",
        help="Repository catalog YAML path. Defaults to the packaged catalog.",
    ),
    dewey_url: str = typer.Option(
        "",
        "--dewey-url",
        help="Dewey base URL for post-export artifact registration.",
    ),
    dewey_token_env: str = typer.Option(
        "",
        "--dewey-token-env",
        help="Environment variable containing the Dewey bearer token.",
    ),
    dewey_analysis_dir_external_object_id: str = typer.Option(
        "",
        "--dewey-analysis-dir-external-object-id",
        help="External object id for the exported daylily-omics-analysis S3 directory.",
    ),
    dewey_run_artifact_euid: str = typer.Option(
        "",
        "--dewey-run-artifact-euid",
        help="Dewey run artifact EUID to link to the exported analysis directory external object.",
    ),
    dewey_ursa_analysis_euid: str = typer.Option(
        "",
        "--dewey-ursa-analysis-euid",
        help="Ursa analysis EUID to link to the exported analysis directory external object.",
    ),
) -> None:
    """Export FSx outputs through an explicit temporary DRA."""

    from daylily_ec.workflow.export_data import (
        ExportOptions,
        configure_logging,
        run_export_workflow,
    )
    from daylily_ec.repositories import load_repository_catalog

    _warn_if_dayec_env_inactive()
    artifact_registration_policy = None
    artifact_registration_genome = ""
    _validate_dewey_analysis_directory_link_options(
        artifact_registration_command_id=artifact_registration_command_id,
        dewey_analysis_dir_external_object_id=dewey_analysis_dir_external_object_id,
        dewey_run_artifact_euid=dewey_run_artifact_euid,
        dewey_ursa_analysis_euid=dewey_ursa_analysis_euid,
    )
    if artifact_registration_command_id:
        catalog = load_repository_catalog(repository_catalog)
        command = catalog.get_command(artifact_registration_command_id)
        if command.artifact_registration is None:
            raise typer.BadParameter(
                f"Command {artifact_registration_command_id!r} has no artifact_registration policy"
            )
        artifact_registration_policy = command.artifact_registration
        artifact_registration_genome = command.genome
        if not dewey_url:
            raise typer.BadParameter(
                "--dewey-url is required with --artifact-registration-command-id"
            )
        if not dewey_token_env:
            raise typer.BadParameter(
                "--dewey-token-env is required with --artifact-registration-command-id"
            )
    elif dewey_url or dewey_token_env:
        raise typer.BadParameter(
            "--artifact-registration-command-id is required when Dewey registration options are set"
        )
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
            artifact_registration_policy=artifact_registration_policy,
            artifact_registration_genome=artifact_registration_genome,
            dewey_url=dewey_url,
            dewey_token_env=dewey_token_env,
            dewey_analysis_dir_external_object_id=dewey_analysis_dir_external_object_id,
            dewey_run_artifact_euid=dewey_run_artifact_euid,
            dewey_ursa_analysis_euid=dewey_ursa_analysis_euid,
            artifact_registration_command_id=artifact_registration_command_id or "",
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
            cluster_name=cluster_name,
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


def exports_register_dewey(
    source_path: str = typer.Option(
        ...,
        "--source-path",
        help="Exported analysis directory under /fsx/analysis_results/<executing-entity>/<analysis-id>/.",
    ),
    destination_s3_uri: str = typer.Option(
        ...,
        "--destination-s3-uri",
        help="Existing S3 URI ending in <executing-entity>/<analysis-id>/.",
    ),
    region: str = typer.Option(..., "--region", help="AWS region for S3 access."),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        help="Directory where fsx_export.yaml and dewey_registration_receipt.json will be written.",
    ),
    artifact_registration_command_id: str = typer.Option(
        ...,
        "--artifact-registration-command-id",
        help="Repository catalog command id whose explicit artifact_registration policy should be applied.",
    ),
    manifest_source: str = typer.Option(
        ...,
        "--manifest-source",
        help="Registration manifest source: dayoa-manifest or s3-inventory.",
    ),
    repository_catalog: Optional[Path] = typer.Option(
        None,
        "--repository-catalog",
        help="Repository catalog YAML path. Defaults to the packaged catalog.",
    ),
    dewey_url: str = typer.Option(..., "--dewey-url", help="Dewey base URL."),
    dewey_token_env: str = typer.Option(
        ...,
        "--dewey-token-env",
        help="Environment variable containing the Dewey bearer token.",
    ),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose registration logging."),
    dewey_analysis_dir_external_object_id: str = typer.Option(
        "",
        "--dewey-analysis-dir-external-object-id",
        help="External object id for the exported daylily-omics-analysis S3 directory.",
    ),
    dewey_run_artifact_euid: str = typer.Option(
        "",
        "--dewey-run-artifact-euid",
        help="Dewey run artifact EUID to link to the exported analysis directory external object.",
    ),
    dewey_ursa_analysis_euid: str = typer.Option(
        "",
        "--dewey-ursa-analysis-euid",
        help="Ursa analysis EUID to link to the exported analysis directory external object.",
    ),
) -> None:
    """Register an existing exported analysis directory with Dewey without running FSx export."""

    from daylily_ec.repositories import load_repository_catalog
    from daylily_ec.workflow.export_data import (
        RegisterExistingExportOptions,
        configure_logging,
        run_dewey_registration_for_existing_export,
    )

    _warn_if_dayec_env_inactive()
    normalized_manifest_source = manifest_source.strip().replace("-", "_")
    if normalized_manifest_source not in {"dayoa_manifest", "s3_inventory"}:
        raise typer.BadParameter("--manifest-source must be dayoa-manifest or s3-inventory")
    _validate_dewey_analysis_directory_link_options(
        artifact_registration_command_id=artifact_registration_command_id,
        dewey_analysis_dir_external_object_id=dewey_analysis_dir_external_object_id,
        dewey_run_artifact_euid=dewey_run_artifact_euid,
        dewey_ursa_analysis_euid=dewey_ursa_analysis_euid,
    )
    catalog = load_repository_catalog(repository_catalog)
    command = catalog.get_command(artifact_registration_command_id)
    if command.artifact_registration is None:
        raise typer.BadParameter(
            f"Command {artifact_registration_command_id!r} has no artifact_registration policy"
        )
    configure_logging(verbose)
    rc = run_dewey_registration_for_existing_export(
        RegisterExistingExportOptions(
            source_path=source_path,
            destination_s3_uri=destination_s3_uri,
            region=region,
            profile=profile,
            output_dir=output_dir.expanduser().resolve(),
            artifact_registration_policy=command.artifact_registration,
            artifact_registration_genome=command.genome,
            artifact_registration_manifest_source=normalized_manifest_source,
            artifact_registration_command_id=artifact_registration_command_id,
            dewey_url=dewey_url,
            dewey_token_env=dewey_token_env,
            dewey_analysis_dir_external_object_id=dewey_analysis_dir_external_object_id,
            dewey_run_artifact_euid=dewey_run_artifact_euid,
            dewey_ursa_analysis_euid=dewey_ursa_analysis_euid,
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


def aws_audit_api_calls(
    profile: str = typer.Option(..., "--profile", help="Exact AWS CLI profile to audit."),
    account_id: str = typer.Option(
        ...,
        "--account-id",
        help="Expected 12-digit AWS account id; included in every exact cache key.",
    ),
    start: str = typer.Option(
        ...,
        "--start",
        help="Inclusive billing and CloudTrail start date in YYYY-MM-DD form.",
    ),
    end: str = typer.Option(
        ...,
        "--end",
        help="Exclusive billing and CloudTrail end date in YYYY-MM-DD form.",
    ),
    trail_region: str = typer.Option(
        ...,
        "--trail-region",
        help="Region used for CloudTrail LookupEvents.",
    ),
    resource_region: List[str] = typer.Option(
        ...,
        "--resource-region",
        help="Region searched for source-IP EC2 mappings. Repeat for multiple regions.",
    ),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        help="Explicit directory for the summary and CSV evidence.",
    ),
    cache_dir: Path = typer.Option(
        ...,
        "--cache-dir",
        help="Explicit persistent exact-request cache directory.",
    ),
    cache_max_age_hours: float = typer.Option(
        24.0,
        "--cache-max-age-hours",
        min=0.0,
        help="Maximum age of a reusable exact-request cache entry.",
    ),
    cloudtrail_slices_per_day: int = typer.Option(
        4,
        "--cloudtrail-slices-per-day",
        min=1,
        help="Bounded sampling slices per day; must divide 24 evenly.",
    ),
    cloudtrail_events_per_slice: int = typer.Option(
        25,
        "--cloudtrail-events-per-slice",
        min=1,
        max=50,
        help="Maximum CloudTrail events collected from each slice.",
    ),
    top_source_ips: int = typer.Option(
        5,
        "--top-source-ips",
        min=0,
        help="Number of sampled source IPs to map through EC2 Elastic IPs.",
    ),
    top_principals: int = typer.Option(
        3,
        "--top-principals",
        min=0,
        help="Number of sampled IAM user principals to enrich.",
    ),
    paid_call_budget: int = typer.Option(
        1,
        "--paid-call-budget",
        min=0,
        max=300,
        help=(
            "Maximum live paid Cost Explorer calls allowed in this run; capped at 300 "
            "for a $3.00 ceiling at the observed $0.01/request rate."
        ),
    ),
    cache_only: bool = typer.Option(
        False,
        "--cache-only/--allow-live-calls",
        help="Guarantee zero live AWS calls; fail on missing or stale cache entries.",
    ),
    refresh: bool = typer.Option(
        False,
        "--refresh/--reuse-cache",
        help="Bypass valid cache entries; paid calls remain budget-limited.",
    ),
    ce_min_interval_seconds: float = typer.Option(
        1.0,
        "--ce-min-interval-seconds",
        min=0.0,
        help="Minimum interval between live Cost Explorer calls.",
    ),
    cloudtrail_min_interval_seconds: float = typer.Option(
        0.5,
        "--cloudtrail-min-interval-seconds",
        min=0.0,
        help="Minimum interval between live CloudTrail calls.",
    ),
    other_min_interval_seconds: float = typer.Option(
        0.2,
        "--other-min-interval-seconds",
        min=0.0,
        help="Minimum interval between other live read calls per AWS service.",
    ),
) -> None:
    """Audit Cost Explorer request charges and attribute sampled callers."""

    from datetime import date

    from daylily_ec.aws.api_call_audit import ApiCallAuditConfig, run_api_call_audit

    _warn_if_dayec_env_inactive()
    try:
        parsed_start = date.fromisoformat(start)
        parsed_end = date.fromisoformat(end)
        summary = run_api_call_audit(
            ApiCallAuditConfig(
                profile=profile,
                account_id=account_id,
                start_date=parsed_start,
                end_date=parsed_end,
                trail_region=trail_region,
                resource_regions=tuple(resource_region),
                output_dir=output_dir,
                cache_dir=cache_dir,
                cache_max_age_seconds=cache_max_age_hours * 60 * 60,
                cloudtrail_slices_per_day=cloudtrail_slices_per_day,
                cloudtrail_events_per_slice=cloudtrail_events_per_slice,
                top_source_ips=top_source_ips,
                top_principals=top_principals,
                paid_call_budget=paid_call_budget,
                cache_only=cache_only,
                refresh=refresh,
                ce_min_interval_seconds=ce_min_interval_seconds,
                cloudtrail_min_interval_seconds=cloudtrail_min_interval_seconds,
                other_min_interval_seconds=other_min_interval_seconds,
            )
        )
    except (OSError, RuntimeError, ValueError) as exc:
        _exit_headnode_error(exc)

    if _json_mode():
        output.emit_json(summary)
        return
    reuse = summary["request_reuse"]
    typer.echo(
        json.dumps(
            {
                "output_dir": str(output_dir.expanduser().resolve()),
                "billed_api_requests": summary["billed_api_requests"],
                "billed_api_cost_usd": summary["billed_api_cost_usd"],
                "cache_hits": reuse["cache_hits"],
                "live_calls": reuse["live_calls"],
                "paid_live_calls": reuse["paid_live_calls"],
            },
            indent=2,
            sort_keys=True,
        )
    )


def aws_audit_cost_resources(
    profile: str = typer.Option(..., "--profile", help="Exact AWS CLI profile to audit."),
    account_id: str = typer.Option(
        ...,
        "--account-id",
        help="Expected 12-digit AWS account id included in every cache key.",
    ),
    start: str = typer.Option(
        ...,
        "--start",
        help="Inclusive service-cost start date in YYYY-MM-DD form.",
    ),
    end: str = typer.Option(
        ...,
        "--end",
        help="Exclusive service/resource cost and utilization end date.",
    ),
    resource_start: str = typer.Option(
        ...,
        "--resource-start",
        help="Inclusive resource-detail start date; no more than 14 days before --end.",
    ),
    control_region: str = typer.Option(
        ...,
        "--control-region",
        help="Explicit region for identity, enabled-region, and global control reads.",
    ),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        help="Explicit absent or empty directory for machine-readable outputs.",
    ),
    cache_dir: Path = typer.Option(
        ...,
        "--cache-dir",
        help="Explicit persistent exact-request cache directory reused across runs.",
    ),
    history_file: Path = typer.Option(
        ...,
        "--history-file",
        help="Explicit persistent type/resource history JSON used across runs.",
    ),
    initialize_history: bool = typer.Option(
        False,
        "--initialize-history",
        help="Create a missing history file; rejected when history already exists.",
    ),
    cost_tag_key: List[str] = typer.Option(
        [],
        "--cost-tag-key",
        help="Cost-allocation tag key to group by value. Repeat for multiple keys.",
    ),
    cluster_tag_key: List[str] = typer.Option(
        ...,
        "--cluster-tag-key",
        help="Explicit cluster tag key. Repeat for all supported cluster tag contracts.",
    ),
    discover_cost_tag_keys: bool = typer.Option(
        True,
        "--discover-cost-tag-keys/--skip-cost-tag-key-discovery",
        help="Use one or more budgeted Cost Explorer pages to catalog active tag keys.",
    ),
    include_budgets: bool = typer.Option(
        True,
        "--include-budgets/--skip-budgets",
        help="Collect cached read-only budgets, filters, alerts, subscribers, actions, and tags.",
    ),
    parallelcluster_executable: Path = typer.Option(
        ...,
        "--parallelcluster-executable",
        help="Explicit pcluster executable used only for cached read-only cluster calls.",
    ),
    parallelcluster_region: List[str] = typer.Option(
        ...,
        "--parallelcluster-region",
        help="Region queried through pcluster. Repeat for every required cluster region.",
    ),
    utilization_limit: int = typer.Option(
        50,
        "--utilization-limit",
        min=0,
        help="Maximum highest-cost current resources selected for metric enrichment.",
    ),
    utilization_period_seconds: int = typer.Option(
        3600,
        "--utilization-period-seconds",
        min=60,
        help="CloudWatch metric period for supported type-specific enrichers.",
    ),
    paid_call_budget: int = typer.Option(
        50,
        "--paid-call-budget",
        min=0,
        max=300,
        help=(
            "Maximum live Cost Explorer pages in this run; hard-capped at 300 / "
            "$3.00 at the observed $0.01 primary-view request rate."
        ),
    ),
    cache_max_age_hours: float = typer.Option(
        24.0,
        "--cache-max-age-hours",
        min=0.0,
        help="Maximum age of a reusable exact-request cache entry.",
    ),
    cache_only: bool = typer.Option(
        False,
        "--cache-only/--allow-live-calls",
        help="Guarantee zero live AWS/pcluster calls; fail on missing or stale cache.",
    ),
    refresh: bool = typer.Option(
        False,
        "--refresh/--reuse-cache",
        help="Bypass valid cache entries while retaining throttles and paid-call ceiling.",
    ),
    ce_min_interval_seconds: float = typer.Option(
        1.0,
        "--ce-min-interval-seconds",
        min=0.0,
        help="Minimum interval between live Cost Explorer calls.",
    ),
    other_min_interval_seconds: float = typer.Option(
        0.2,
        "--other-min-interval-seconds",
        min=0.0,
        help="Minimum interval between other live read calls per AWS service.",
    ),
    parallelcluster_min_interval_seconds: float = typer.Option(
        0.5,
        "--parallelcluster-min-interval-seconds",
        min=0.0,
        help="Minimum interval between live read-only pcluster calls.",
    ),
) -> None:
    """Collect reusable cost, tag, budget, lifecycle, and utilization datasets."""

    from datetime import date

    from daylily_ec.aws.on_demand_cost_report import (
        OnDemandCostReportConfig,
        run_on_demand_cost_report,
    )

    _warn_if_dayec_env_inactive()
    try:
        summary = run_on_demand_cost_report(
            OnDemandCostReportConfig(
                profile=profile,
                account_id=account_id,
                start_date=date.fromisoformat(start),
                end_date=date.fromisoformat(end),
                resource_start_date=date.fromisoformat(resource_start),
                control_region=control_region,
                output_dir=output_dir,
                cache_dir=cache_dir,
                history_path=history_file,
                initialize_history=initialize_history,
                cost_tag_keys=tuple(cost_tag_key),
                cluster_tag_keys=tuple(cluster_tag_key),
                discover_cost_tag_keys=discover_cost_tag_keys,
                include_budgets=include_budgets,
                parallelcluster_executable=parallelcluster_executable,
                parallelcluster_regions=tuple(parallelcluster_region),
                utilization_limit=utilization_limit,
                utilization_period_seconds=utilization_period_seconds,
                paid_call_budget=paid_call_budget,
                cache_max_age_seconds=cache_max_age_hours * 60 * 60,
                cache_only=cache_only,
                refresh=refresh,
                ce_min_interval_seconds=ce_min_interval_seconds,
                other_min_interval_seconds=other_min_interval_seconds,
                parallelcluster_min_interval_seconds=(parallelcluster_min_interval_seconds),
            )
        )
    except (OSError, RuntimeError, ValueError) as exc:
        _exit_headnode_error(exc)

    if _json_mode():
        output.emit_json(summary)
        return
    typer.echo(
        json.dumps(
            {
                "output_dir": str(output_dir.expanduser().resolve()),
                "resources": summary["counts"]["resources"],
                "untagged_resources": summary["counts"]["untagged_resources"],
                "budgets": summary["counts"]["budgets"],
                "paid_live_calls": summary["paid_call_guard"]["actual_paid_live_calls"],
                "estimated_cost_explorer_cost_usd": summary["paid_call_guard"][
                    "actual_estimated_cost_usd_at_observed_rate"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


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
    table_view: bool = typer.Option(
        False,
        "--table-view",
        help="Render one pricing-summary row per partition and availability zone.",
    ),
    target_capacity_vcpus: Optional[int] = typer.Option(
        None,
        "--target-capacity-vcpus",
        min=1,
        help="Explicit vCPU target used to request EC2 Spot Placement Scores.",
    ),
) -> None:
    """Emit a pricing snapshot for the requested regions and partitions."""

    from daylily_ec.aws.pricing_snapshots import (
        collect_pricing_snapshot,
        format_pricing_snapshot_table,
    )

    _warn_if_dayec_env_inactive()
    if table_view and _json_mode():
        raise typer.BadParameter("--table-view cannot be combined with --json")
    if table_view and target_capacity_vcpus is None:
        raise typer.BadParameter("--target-capacity-vcpus is required with --table-view")
    payload = collect_pricing_snapshot(
        regions=region,
        partitions=partition,
        cluster_config_path=config,
        profile=profile,
        target_capacity_vcpus=target_capacity_vcpus,
    ).to_dict()

    if table_view:
        typer.echo(format_pricing_snapshot_table(payload))
        return
    if _json_mode():
        output.emit_json(payload)
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=False))


def pricing_spot_logs(
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
    path: Optional[List[str]] = typer.Option(
        None,
        "--path",
        help="Remote directory to scan. Repeatable. Defaults to /fsx/logs, /fsx/scratch, and /fsx/tmp.",
    ),
    name_glob: Optional[List[str]] = typer.Option(
        None,
        "--name-glob",
        help="Remote file-name glob to scan. Repeatable. Defaults to *.log.",
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Write CSV to this local file instead of stdout.",
    ),
    cost_output: Optional[Path] = typer.Option(
        None,
        "--cost-output",
        help="Write per-instance compute cost interval summary CSV to this local file.",
    ),
    cost_price_source: str = typer.Option(
        "history",
        "--cost-price-source",
        help="Price source for cost intervals: history or logged.",
    ),
    remote_user: str = typer.Option(
        "auto",
        "--remote-user",
        help="Remote login user for SSM Run Command: auto, ubuntu, or ec2-user.",
    ),
    timeout: int = typer.Option(
        300,
        "--timeout",
        help="SSM command timeout in seconds.",
    ),
    allow_empty: bool = typer.Option(
        False,
        "--allow-empty",
        help="Emit an empty CSV/JSON payload instead of failing when no rows are found.",
    ),
) -> None:
    """Fetch cluster spot-price logs from the head node as one CSV."""

    from daylily_ec.aws.ssm import (
        SsmCommandFailedError,
        SsmError,
        run_shell,
        wait_for_ssm_online,
    )
    from daylily_ec.scripts.common import CommandError
    from daylily_ec.spot_price_logs import (
        DEFAULT_SPOT_LOG_NAME_GLOBS,
        DEFAULT_SPOT_LOG_PATHS,
        build_spot_cost_intervals,
        build_remote_spot_price_log_script,
        extract_remote_spot_price_payload,
        normalize_spot_price_rows,
        spot_cost_intervals_to_csv,
        spot_price_rows_to_csv,
    )

    _warn_if_dayec_env_inactive()
    remote_paths = path or list(DEFAULT_SPOT_LOG_PATHS)
    remote_name_globs = name_glob or list(DEFAULT_SPOT_LOG_NAME_GLOBS)
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
        result = run_shell(
            target.instance_id,
            resolved_region,
            build_remote_spot_price_log_script(
                paths=remote_paths,
                name_globs=remote_name_globs,
            ),
            profile=resolved_profile,
            as_user=remote_user,
            timeout=timeout,
            comment="Daylily spot price log export",
        )
        remote_payload = extract_remote_spot_price_payload(result.stdout)
    except SsmCommandFailedError as exc:
        if exc.result.stderr.strip():
            typer.echo(exc.result.stderr.rstrip(), err=True)
        _exit_headnode_error(exc)
    except (CommandError, SsmError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        _exit_headnode_error(exc)

    rows = normalize_spot_price_rows(
        remote_payload["rows"],
        cluster=resolved_cluster,
        headnode_instance_id=target.instance_id,
    )
    if not rows and not allow_empty:
        _exit_headnode_error(
            RuntimeError(
                "No spot price log rows found under "
                + ", ".join(remote_paths)
                + " with name globs "
                + ", ".join(remote_name_globs)
            )
        )

    ec2_client = None
    if cost_price_source == "history" and any(
        row.get("node_type") == "ComputeFleet" for row in rows
    ):
        import boto3

        ec2_client = boto3.Session(
            profile_name=resolved_profile,
            region_name=resolved_region,
        ).client("ec2")
    try:
        cost_intervals = build_spot_cost_intervals(
            rows,
            price_source=cost_price_source,
            ec2_client=ec2_client,
            compute_only=True,
        )
    except ValueError as exc:
        _exit_headnode_error(exc)

    payload = {
        "cluster": resolved_cluster,
        "headnode_instance_id": target.instance_id,
        "region": resolved_region,
        "paths": remote_payload.get("paths", remote_paths),
        "name_globs": remote_payload.get("name_globs", remote_name_globs),
        "visited_files": remote_payload.get("visited_files", 0),
        "row_count": len(rows),
        "rows": rows,
        "cost_interval_count": len(cost_intervals),
        "cost_intervals": cost_intervals,
    }
    if cost_output is not None:
        cost_output.parent.mkdir(parents=True, exist_ok=True)
        cost_output.write_text(spot_cost_intervals_to_csv(cost_intervals), encoding="utf-8")
    if _json_mode():
        output.emit_json(payload)
        return

    csv_text = spot_price_rows_to_csv(rows)
    if output_file is not None:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(csv_text, encoding="utf-8")
        if cost_output is not None:
            typer.echo(f"{output_file}\n{cost_output}")
        else:
            typer.echo(str(output_file))
        return
    if cost_output is not None:
        typer.echo(f"cost intervals: {cost_output}", err=True)
    typer.echo(csv_text.rstrip("\n"))


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
    root_unverified = [
        check
        for check in report.checks
        if check.id.startswith("iam.simulation.")
        and check.status.value == "WARN"
        and check.details.get("simulation_performed") is False
    ]
    if root_unverified:
        output.warning(
            "WARN iam.simulation.root_unverified: IAM cannot simulate the account-root "
            f"principal; {len(root_unverified)} operator permission groups are UNKNOWN. "
            "Use the actual non-root operator profile for PASS/FAIL decisions."
        )
    for check in report.checks:
        if check in root_unverified:
            continue
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
        output.print_text(f"Validation report written: {gap_analysis}")
    if rc == 0:
        output.success("AWS validation passed.")
    else:
        output.error("AWS validation found permission, readiness, or quota gaps.")
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
        help="Daylily config path used for runtime-policy and cost-control readiness.",
    ),
    gap_analysis: Optional[Path] = typer.Option(
        None,
        "--gap-analysis",
        help="Write the complete AWS permissions, readiness, and quotas Markdown report.",
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
        help="Write the complete AWS permissions, readiness, and quotas Markdown report.",
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
        help="Daylily config path used for readiness checks and rendered quota demand.",
    ),
    gap_analysis: Optional[Path] = typer.Option(
        None,
        "--gap-analysis",
        help="Write the complete AWS permissions, readiness, and quotas Markdown report.",
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
    remote_user: str = typer.Option(
        "auto",
        "--remote-user",
        help="Remote login user for SSM Run Command: auto, ubuntu, or ec2-user.",
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
            as_user=remote_user,
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


def _configure_headnode_command(
    *,
    profile: Optional[str],
    region: Optional[str],
    cluster: Optional[str],
    repo_overrides: Optional[Path],
    dyec_deploy_key_secret_arn: str,
    dayoa_deploy_key_secret_arn: str,
    remote_user: str,
) -> None:
    from daylily_ec.aws.ssm import SsmError, wait_for_ssm_online
    from daylily_ec.scripts.common import CommandError
    from daylily_ec.scripts.daylily_cfg_headnode import _load_repo_overrides
    from daylily_ec.workflow.create_cluster import (
        configure_headnode,
        resolve_configured_headnode_repo_spec,
    )

    _warn_if_dayec_env_inactive()
    try:
        resolved_profile, resolved_region, resolved_cluster, target = _resolve_headnode_cli_target(
            profile=profile,
            region=region,
            cluster=cluster,
        )
        overrides = _load_repo_overrides(str(repo_overrides) if repo_overrides else None)
        dyec_secret_arn = dyec_deploy_key_secret_arn.strip()
        try:
            dyec_repo_spec = (
                resolve_configured_headnode_repo_spec(deploy_key_auth=True)
                if dyec_secret_arn
                else None
            )
        except RuntimeError as exc:
            raise CommandError(f"Unable to pin the active DYEC checkout: {exc}") from exc
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
            dyec_deploy_key_secret_arn=dyec_secret_arn,
            dyec_deploy_key_region=resolved_region if dyec_secret_arn else "",
            dyec_repo_url=dyec_repo_spec.url if dyec_repo_spec else "",
            dyec_repo_ref=dyec_repo_spec.ref if dyec_repo_spec else "",
            dayoa_deploy_key_secret_arn=dayoa_deploy_key_secret_arn.strip(),
            dayoa_deploy_key_region=resolved_region if dayoa_deploy_key_secret_arn.strip() else "",
            repo_overrides=overrides or None,
            remote_user=remote_user,
        )
        if not ok:
            raise CommandError(f"Headnode configuration failed for cluster '{resolved_cluster}'.")
    except (CommandError, SsmError, TimeoutError) as exc:
        _exit_headnode_error(exc)

    output.success(f"Headnode configured via SSM for cluster '{resolved_cluster}'.")


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
    dyec_deploy_key_secret_arn: str = typer.Option(
        "",
        "--dyec-deploy-key-secret-arn",
        help=(
            "Exact Secrets Manager ARN for the DYEC read-only deploy key. The headnode "
            "role must already allow access to this secret."
        ),
    ),
    dayoa_deploy_key_secret_arn: str = typer.Option(
        "",
        "--dayoa-deploy-key-secret-arn",
        help=(
            "Exact Secrets Manager ARN for the DayOA read-only deploy key. Required when "
            "configuring a legacy headnode that does not already have the reference."
        ),
    ),
) -> None:
    """Configure a cluster headnode through the supported Ubuntu SSM bootstrap."""

    _configure_headnode_command(
        profile=profile,
        region=region,
        cluster=cluster,
        repo_overrides=repo_overrides,
        dyec_deploy_key_secret_arn=dyec_deploy_key_secret_arn,
        dayoa_deploy_key_secret_arn=dayoa_deploy_key_secret_arn,
        remote_user="ubuntu",
    )


def headnode_configure_dragen(
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
    dyec_deploy_key_secret_arn: str = typer.Option(
        "",
        "--dyec-deploy-key-secret-arn",
        help=(
            "Exact Secrets Manager ARN for the DYEC read-only deploy key. The headnode "
            "role must already allow access to this secret."
        ),
    ),
    dayoa_deploy_key_secret_arn: str = typer.Option(
        "",
        "--dayoa-deploy-key-secret-arn",
        help=(
            "Exact Secrets Manager ARN for the DayOA read-only deploy key. Required when "
            "configuring a legacy headnode that does not already have the reference."
        ),
    ),
) -> None:
    """Configure a RHEL/DRAGEN cluster headnode through SSM as ec2-user."""

    _configure_headnode_command(
        profile=profile,
        region=region,
        cluster=cluster,
        repo_overrides=repo_overrides,
        dyec_deploy_key_secret_arn=dyec_deploy_key_secret_arn,
        dayoa_deploy_key_secret_arn=dayoa_deploy_key_secret_arn,
        remote_user="ec2-user",
    )


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


def _validate_sample_command_input_requirements(analysis_path: Path, command: Any) -> None:
    """Fail before staging when a command's explicit source contract is not satisfied."""

    from daylily_ec.scripts.common import CommandError

    required = list(command.input_requirements.required_source_columns)
    accepted_sets = list(command.input_requirements.accepted_source_column_sets)
    if not required and not accepted_sets:
        return
    with analysis_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        headers = set(reader.fieldnames or [])
        missing_headers = sorted(set(required) - headers)
        if missing_headers:
            raise CommandError(
                f"Analysis command {command.command_id} requires source column(s): "
                + ", ".join(missing_headers)
            )
        rows = list(reader)
    for row_number, row in enumerate(rows, start=2):
        blank_required = [field for field in required if not str(row.get(field) or "").strip()]
        if blank_required:
            raise CommandError(
                f"Analysis command {command.command_id} requires explicit nonblank source "
                f"value(s) on row {row_number}: {', '.join(blank_required)}"
            )
        if accepted_sets and not any(
            all(str(row.get(field) or "").strip() for field in column_set)
            for column_set in accepted_sets
        ):
            rendered_sets = " or ".join("+".join(column_set) for column_set in accepted_sets)
            raise CommandError(
                f"Analysis command {command.command_id} row {row_number} must populate one "
                f"accepted source column set: {rendered_sets}"
            )


def _parse_workflow_launch_metadata(launch_stdout: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in launch_stdout.splitlines():
        if line.startswith("__DAYLILY_SESSION__="):
            parsed["session_name"] = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_RUN_DIR__="):
            parsed["run_dir"] = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_REPO_PATH__="):
            parsed["repo_path"] = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_DY_COMMAND__="):
            parsed["dy_command"] = line.split("=", 1)[1].strip()
    return parsed


def samples_stage(
    analysis_samples: Path = typer.Argument(
        ...,
        help="Path to analysis_samples.tsv.",
    ),
    manifest_contract: str = typer.Option(
        "dayoa12",
        "--manifest-contract",
        help=(
            "Explicit output contract: dayoa12 (specimens/samples/libraries) or "
            "legacy_v11 for commands explicitly pinned before DayOA 12."
        ),
    ),
    reference_s3_uri: str = typer.Option(
        ...,
        "--reference-s3-uri",
        help="S3 URI mapped to /fsx/references.",
    ),
    control_data_s3_uri: str = typer.Option(
        ...,
        "--control-data-s3-uri",
        help="S3 URI mapped to /fsx/control_data.",
    ),
    stage_s3_uri: str = typer.Option(
        ...,
        "--stage-s3-uri",
        help="S3 URI used as the exact root for external staging remote_stage_* prefixes.",
    ),
    config_dir: Optional[Path] = typer.Option(
        None,
        "--config-dir",
        help="Directory for the exact generated manifest contract.",
    ),
    stage_target: str = typer.Option(
        "/fsx/staging/staged_external_sequencing_data",
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
    fsx_s3_uri_map: Optional[List[str]] = typer.Option(
        None,
        "--fsx-s3-uri-map",
        help=(
            "Explicit FSx-to-S3 mapping for mounted read-only subpaths. "
            "Use /fsx/prefix=s3://bucket/prefix; can be specified multiple times."
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
        help="ParallelCluster name for creating the staged-prefix FSx DRA.",
    ),
    fsx_file_system_id: Optional[str] = typer.Option(
        None,
        "--fsx-file-system-id",
        help="FSx file system id for creating the staged-prefix DRA.",
    ),
    staging_mount_timeout_seconds: int = typer.Option(
        900,
        "--staging-mount-timeout-seconds",
        help="Seconds to wait for the staged-prefix DRA to become available.",
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
    config_only: bool = typer.Option(
        False,
        "--config-only",
        help=(
            "Validate the manifest and write the exact generated manifests locally without "
            "creating a staged-prefix DRA."
        ),
    ),
) -> None:
    """Stage analysis samples and generate workflow manifests."""

    _warn_if_dayec_env_inactive()
    argv = [
        str(analysis_samples),
        "--manifest-contract",
        manifest_contract,
        "--reference-s3-uri",
        reference_s3_uri,
        "--control-data-s3-uri",
        control_data_s3_uri,
        "--stage-s3-uri",
        stage_s3_uri,
        "--stage-target",
        stage_target,
    ]
    for spec in run_metric_staging or []:
        argv.extend(["--run-metric-staging", spec])
    for mapping in fsx_s3_uri_map or []:
        argv.extend(["--fsx-s3-uri-map", mapping])
    if config_dir:
        argv.extend(["--config-dir", str(config_dir)])
    if profile:
        argv.extend(["--profile", profile])
    if region:
        argv.extend(["--region", region])
    if cluster:
        argv.extend(["--cluster", cluster])
    if fsx_file_system_id:
        argv.extend(["--fsx-file-system-id", fsx_file_system_id])
    if staging_mount_timeout_seconds != 900:
        argv.extend(["--staging-mount-timeout-seconds", str(staging_mount_timeout_seconds)])
    if debug:
        argv.append("--debug")
    if precheck_only:
        argv.append("--precheck-only")
    if config_only:
        argv.append("--config-only")

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
    analysis_id: str = typer.Option(
        ...,
        "--analysis-id",
        help="Required analysis identifier used for the FSx analysis directory.",
    ),
    executing_entity: Optional[str] = typer.Option(
        None,
        "--executing-entity",
        "-u",
        help="User or system identifier used under /fsx/analysis_results. Defaults to --cluster.",
    ),
    reference_s3_uri: str = typer.Option(
        ...,
        "--reference-s3-uri",
        help="S3 URI mapped to /fsx/references.",
    ),
    control_data_s3_uri: str = typer.Option(
        ...,
        "--control-data-s3-uri",
        help="S3 URI mapped to /fsx/control_data.",
    ),
    stage_s3_uri: str = typer.Option(
        ...,
        "--stage-s3-uri",
        help="S3 URI used as the exact root for external staging remote_stage_* prefixes.",
    ),
    config_dir: Optional[Path] = typer.Option(
        None,
        "--config-dir",
        help=(
            "Directory for generated command-contract manifests and the run receipt. "
            "DayOA 12 commands emit specimens.tsv, samples.tsv, and libraries.tsv."
        ),
    ),
    stage_target: str = typer.Option(
        "/fsx/staging/staged_external_sequencing_data",
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
        help="Tmux session name. Defaults to --analysis-id.",
    ),
    project: Optional[str] = typer.Option(None, "--project", help="Project/budget for dyoainit."),
    skip_project_check: bool = typer.Option(
        True,
        "--skip-project-check/--strict-project-check",
        help="Skip or enable upstream project validation in dyoainit.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Launch the catalog dry-run command."),
    max_runtime_minutes: int = typer.Option(
        DEFAULT_JOB_MAX_RUNTIME_MINUTES,
        "--max-runtime-minutes",
        help=(
            "Deprecated compatibility option. DYEC does not append Snakemake --default-resources."
        ),
    ),
    export_destination_s3_uri: Optional[str] = typer.Option(
        None,
        "--export-destination-s3-uri",
        help=(
            "S3 auto-export destination. A full destination is preserved; an export root "
            "is expanded to <root>/<cluster>/<analysis-id>/."
        ),
    ),
    export_trigger: str = typer.Option(
        "none",
        "--export-trigger",
        help="Auto-export trigger: none, on-success, on-fail, or all.",
    ),
    delete_on_export_success: bool = typer.Option(
        False,
        "--delete-on-export-success",
        help="Delete the FSx analysis directory after a successful requested export.",
    ),
    replace_existing_analysis_dir: bool = typer.Option(
        False,
        "--replace-existing-analysis-dir",
        help=(
            "Explicit retry mode: remove an existing same analysis directory before launch. "
            "Existing analysis directories fail hard unless this flag is set."
        ),
    ),
    dewey_url: Optional[str] = typer.Option(
        None,
        "--dewey-url",
        help="Dewey base URL for post-export artifact registration.",
    ),
    dewey_token_env: Optional[str] = typer.Option(
        None,
        "--dewey-token-env",
        help="Environment variable containing the Dewey bearer token.",
    ),
    dewey_analysis_dir_external_object_id: Optional[str] = typer.Option(
        None,
        "--dewey-analysis-dir-external-object-id",
        help="External object id for the exported daylily-omics-analysis S3 directory.",
    ),
    dewey_run_artifact_euid: Optional[str] = typer.Option(
        None,
        "--dewey-run-artifact-euid",
        help="Dewey run artifact EUID to link to the exported analysis directory external object.",
    ),
    dewey_ursa_analysis_euid: Optional[str] = typer.Option(
        None,
        "--dewey-ursa-analysis-euid",
        help="Ursa analysis EUID to link to the exported analysis directory external object.",
    ),
    catalog_config: Optional[Path] = typer.Option(
        None,
        "--catalog-config",
        help="Path to daylily_pipeline_command_catalog.yaml.",
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
        resolved_executing_entity = _resolve_executing_entity_option(
            executing_entity=executing_entity,
            cluster=cluster,
        )
        resolved_export_destination_s3_uri = _validate_analysis_launch_options(
            analysis_id=analysis_id,
            executing_entity=resolved_executing_entity,
            cluster=cluster,
            export_destination_s3_uri=export_destination_s3_uri,
            export_trigger=export_trigger,
            delete_on_export_success=delete_on_export_success,
        )
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
        _validate_sample_command_input_requirements(analysis_path, command)
        artifact_registration_command_id = None
        if dewey_url or dewey_token_env:
            if export_trigger == "none":
                raise CommandError("--dewey-url/--dewey-token-env require --export-trigger.")
            if not dewey_url or not dewey_token_env:
                raise CommandError("--dewey-url and --dewey-token-env must be provided together.")
            if command.artifact_registration is None:
                raise CommandError(
                    f"Analysis command {command.command_id} has no artifact_registration policy."
                )
            artifact_registration_command_id = command.command_id
        try:
            _validate_dewey_analysis_directory_link_options(
                artifact_registration_command_id=artifact_registration_command_id,
                dewey_analysis_dir_external_object_id=dewey_analysis_dir_external_object_id,
                dewey_run_artifact_euid=dewey_run_artifact_euid,
                dewey_ursa_analysis_euid=dewey_ursa_analysis_euid,
            )
        except typer.BadParameter as exc:
            raise CommandError(str(exc)) from exc
        resolved_profile = _resolved_aws_profile(profile)
        resolved_region = (
            region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        )

        stage_argv = [
            str(analysis_path),
            "--manifest-contract",
            "dayoa12" if command.input_contract == "sample_manifest_v12" else "legacy_v11",
            "--reference-s3-uri",
            reference_s3_uri,
            "--control-data-s3-uri",
            control_data_s3_uri,
            "--stage-s3-uri",
            stage_s3_uri,
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
        if cluster:
            stage_argv.extend(["--cluster", cluster])
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
        resolved_session_name = session_name or analysis_id
        resolved_git_tag = git_tag or command.git_tag
        workflow_cli_argv = command.launch_argv(
            analysis_id=analysis_id,
            executing_entity=resolved_executing_entity,
            git_tag=resolved_git_tag,
            profile=resolved_profile,
            region=resolved_region,
            cluster=cluster,
            stage_dir=remote_stage_dir,
            session_name=resolved_session_name,
            project=project,
            dry_run=dry_run,
            skip_project_check=skip_project_check,
            export_destination_s3_uri=resolved_export_destination_s3_uri,
            export_trigger=export_trigger,
            delete_on_export_success=delete_on_export_success,
            replace_existing_analysis_dir=replace_existing_analysis_dir,
            artifact_registration_command_id=artifact_registration_command_id,
            dewey_url=dewey_url,
            dewey_token_env=dewey_token_env,
            dewey_analysis_dir_external_object_id=dewey_analysis_dir_external_object_id,
            dewey_run_artifact_euid=dewey_run_artifact_euid,
            dewey_ursa_analysis_euid=dewey_ursa_analysis_euid,
        )
        workflow_cli_argv.extend(["--max-runtime-minutes", str(max_runtime_minutes)])
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
        workflow_launch_metadata = _parse_workflow_launch_metadata(launch_stdout)
        effective_dy_command = workflow_launch_metadata.get("dy_command")
        if not effective_dy_command:
            raise CommandError("Workflow launch output did not include the effective dy-r command.")
        receipt = {
            "analysis_samples": str(analysis_path),
            "command_id": command.command_id,
            "compatible_data_modes": command.compatible_data_modes,
            "compatible_cluster_types": command.compatible_cluster_types,
            "detected_data_modes": data_modes,
            "analysis_id": analysis_id,
            "executing_entity": resolved_executing_entity,
            "dry_run": dry_run,
            "dy_command": effective_dy_command,
            "export_destination_s3_uri": resolved_export_destination_s3_uri,
            "export_trigger": export_trigger,
            "max_runtime_minutes": max_runtime_minutes,
            "delete_on_export_success": delete_on_export_success,
            "replace_existing_analysis_dir": replace_existing_analysis_dir,
            "dewey_analysis_dir_external_object_id": dewey_analysis_dir_external_object_id,
            "dewey_run_artifact_euid": dewey_run_artifact_euid,
            "dewey_ursa_analysis_euid": dewey_ursa_analysis_euid,
            "git_tag": resolved_git_tag,
            "remote_stage_dir": remote_stage_dir,
            "input_contract": command.input_contract,
            "specimens_tsv": (
                str(resolved_config_dir / f"{timestamp}_specimens.tsv")
                if command.input_contract == "sample_manifest_v12"
                else None
            ),
            "samples_tsv": str(resolved_config_dir / f"{timestamp}_samples.tsv"),
            "session_name": resolved_session_name,
            "libraries_tsv": (
                str(resolved_config_dir / f"{timestamp}_libraries.tsv")
                if command.input_contract == "sample_manifest_v12"
                else None
            ),
            "units_tsv": (
                str(resolved_config_dir / f"{timestamp}_units.tsv")
                if command.input_contract == "sample_manifest"
                else None
            ),
            "workflow_argv": workflow_cli_argv,
            "workflow_launch": workflow_launch_metadata,
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
    input_contract: str = typer.Option(
        "sample_manifest",
        "--input-contract",
        help="Explicit input contract: sample_manifest, sample_manifest_v12, run_context, or none.",
    ),
    run_context_file: Optional[Path] = typer.Option(
        None,
        "--run-context-file",
        help="Local runs.tsv file to copy to config/runs.tsv for run-analysis workflows.",
    ),
    specimens_file: Optional[Path] = typer.Option(
        None,
        "--specimens-file",
        help="Local specimens.tsv for a DayOA 12 sample-analysis workflow.",
    ),
    samples_file: Optional[Path] = typer.Option(
        None,
        "--samples-file",
        help="Local samples.tsv file to copy to config/samples.tsv for sample-analysis workflows.",
    ),
    libraries_file: Optional[Path] = typer.Option(
        None,
        "--libraries-file",
        help="Local libraries.tsv for a DayOA 12 sample-analysis workflow.",
    ),
    units_file: Optional[Path] = typer.Option(
        None,
        "--units-file",
        help="Legacy local units.tsv; rejected for DayOA 12 commands.",
    ),
    stage_base: str = typer.Option(
        "/fsx/staging/staged_external_sequencing_data",
        "--stage-base",
        help="Base staging directory to scan when --stage-dir is omitted.",
    ),
    input_staging: bool = typer.Option(
        True,
        "--input-staging/--no-input-staging",
        help="Copy the exact staged input-contract manifests into the workflow clone.",
    ),
    default_activation: bool = typer.Option(
        True,
        "--default-activation/--no-default-activation",
        help="Run the standard dyoainit plus Slurm day_activate setup before --dy-command.",
    ),
    bootstrap_test_config: bool = typer.Option(
        False,
        "--bootstrap-test-config",
        help="Copy DayOA bundled test samples and units into config/ before launch.",
    ),
    session_name: Optional[str] = typer.Option(
        None,
        "--session-name",
        help="Tmux session name. Defaults to --analysis-id.",
    ),
    analysis_id: str = typer.Option(
        ...,
        "--analysis-id",
        help="Required analysis identifier used for the FSx analysis directory.",
    ),
    executing_entity: Optional[str] = typer.Option(
        None,
        "--executing-entity",
        "-u",
        help="User or system identifier used under /fsx/analysis_results. Defaults to --cluster.",
    ),
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
    produce_ursa_manifest: Optional[str] = typer.Option(
        None,
        "--produce-ursa-manifest",
        help="Override the DYEC default passed to dy-r; value must be true or false.",
    ),
    produce_rulegraph: Optional[str] = typer.Option(
        None,
        "--produce-rulegraph",
        help="Override the DYEC default passed to dy-r; value must be true or false.",
    ),
    produce_filegraph: Optional[str] = typer.Option(
        None,
        "--produce-filegraph",
        help="Override the DYEC default passed to dy-r; value must be true or false.",
    ),
    produce_dag: Optional[str] = typer.Option(
        None,
        "--produce-dag",
        help="Override the DYEC default passed to dy-r; value must be true or false.",
    ),
    max_runtime_minutes: int = typer.Option(
        DEFAULT_JOB_MAX_RUNTIME_MINUTES,
        "--max-runtime-minutes",
        help=(
            "Deprecated compatibility option. DYEC does not append Snakemake --default-resources."
        ),
    ),
    no_containerized: bool = typer.Option(
        False,
        "--no-containerized",
        help="Disable DAY_CONTAINERIZED.",
    ),
    export_destination_s3_uri: Optional[str] = typer.Option(
        None,
        "--export-destination-s3-uri",
        help=(
            "S3 auto-export destination. A full destination is preserved; an export root "
            "is expanded to <root>/<cluster>/<analysis-id>/."
        ),
    ),
    export_trigger: str = typer.Option(
        "none",
        "--export-trigger",
        help="Auto-export trigger: none, on-success, on-fail, or all.",
    ),
    delete_on_export_success: bool = typer.Option(
        False,
        "--delete-on-export-success",
        help="Delete the FSx analysis directory after a successful requested export.",
    ),
    replace_existing_analysis_dir: bool = typer.Option(
        False,
        "--replace-existing-analysis-dir",
        help=(
            "Explicit retry mode: remove an existing same analysis directory before launch. "
            "Existing analysis directories fail hard unless this flag is set."
        ),
    ),
    artifact_registration_command_id: Optional[str] = typer.Option(
        None,
        "--artifact-registration-command-id",
        help="Catalog command id whose artifact_registration policy should run after export.",
    ),
    dewey_url: Optional[str] = typer.Option(
        None,
        "--dewey-url",
        help="Dewey base URL for post-export artifact registration.",
    ),
    dewey_token_env: Optional[str] = typer.Option(
        None,
        "--dewey-token-env",
        help="Environment variable containing the Dewey bearer token.",
    ),
    dewey_analysis_dir_external_object_id: Optional[str] = typer.Option(
        None,
        "--dewey-analysis-dir-external-object-id",
        help="External object id for the exported daylily-omics-analysis S3 directory.",
    ),
    dewey_run_artifact_euid: Optional[str] = typer.Option(
        None,
        "--dewey-run-artifact-euid",
        help="Dewey run artifact EUID to link to the exported analysis directory external object.",
    ),
    dewey_ursa_analysis_euid: Optional[str] = typer.Option(
        None,
        "--dewey-ursa-analysis-euid",
        help="Ursa analysis EUID to link to the exported analysis directory external object.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Launch a dry-run workflow command."),
) -> None:
    """Launch daylily-omics-analysis inside tmux on the headnode."""

    from daylily_ec.scripts.common import CommandError
    from daylily_ec.workflow.dyr_preflight import (
        DyrPreflightOptionsError,
        parse_strict_bool,
    )

    _warn_if_dayec_env_inactive()
    producer_option_values: dict[str, str] = {}
    for flag, value in (
        ("--produce-ursa-manifest", produce_ursa_manifest),
        ("--produce-rulegraph", produce_rulegraph),
        ("--produce-filegraph", produce_filegraph),
        ("--produce-dag", produce_dag),
    ):
        if value is None:
            continue
        try:
            parsed = parse_strict_bool(value, option=flag)
        except DyrPreflightOptionsError as exc:
            raise typer.BadParameter(str(exc), param_hint=flag) from exc
        producer_option_values[flag] = "true" if parsed else "false"
    resolved_executing_entity = _resolve_executing_entity_option(
        executing_entity=executing_entity,
        cluster=cluster,
    )
    resolved_export_destination_s3_uri = _validate_analysis_launch_options(
        analysis_id=analysis_id,
        executing_entity=resolved_executing_entity,
        cluster=cluster,
        export_destination_s3_uri=export_destination_s3_uri,
        export_trigger=export_trigger,
        delete_on_export_success=delete_on_export_success,
    )
    if artifact_registration_command_id and export_trigger == "none":
        raise typer.BadParameter("--artifact-registration-command-id requires --export-trigger")
    if artifact_registration_command_id and not dewey_url:
        raise typer.BadParameter("--dewey-url is required with --artifact-registration-command-id")
    if artifact_registration_command_id and not dewey_token_env:
        raise typer.BadParameter(
            "--dewey-token-env is required with --artifact-registration-command-id"
        )
    if not artifact_registration_command_id and (dewey_url or dewey_token_env):
        raise typer.BadParameter(
            "--artifact-registration-command-id is required when Dewey registration options are set"
        )
    _validate_dewey_analysis_directory_link_options(
        artifact_registration_command_id=artifact_registration_command_id,
        dewey_analysis_dir_external_object_id=dewey_analysis_dir_external_object_id,
        dewey_run_artifact_euid=dewey_run_artifact_euid,
        dewey_ursa_analysis_euid=dewey_ursa_analysis_euid,
    )
    resolved_session_name = session_name or analysis_id
    argv: list[str] = []
    for flag, value in (
        ("--profile", profile),
        ("--region", region),
        ("--cluster", cluster),
        ("--stage-dir", stage_dir),
        ("--input-contract", input_contract),
        ("--run-context-file", str(run_context_file.expanduser()) if run_context_file else None),
        ("--specimens-file", str(specimens_file.expanduser()) if specimens_file else None),
        ("--samples-file", str(samples_file.expanduser()) if samples_file else None),
        ("--libraries-file", str(libraries_file.expanduser()) if libraries_file else None),
        ("--units-file", str(units_file.expanduser()) if units_file else None),
        ("--stage-base", stage_base),
        ("--session-name", resolved_session_name),
        ("--analysis-id", analysis_id),
        ("--executing-entity", resolved_executing_entity),
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
        ("--max-runtime-minutes", str(max_runtime_minutes)),
        ("--export-destination-s3-uri", resolved_export_destination_s3_uri),
        ("--export-trigger", export_trigger),
        ("--artifact-registration-command-id", artifact_registration_command_id),
        ("--dewey-url", dewey_url),
        ("--dewey-token-env", dewey_token_env),
        ("--dewey-analysis-dir-external-object-id", dewey_analysis_dir_external_object_id),
        ("--dewey-run-artifact-euid", dewey_run_artifact_euid),
        ("--dewey-ursa-analysis-euid", dewey_ursa_analysis_euid),
    ):
        if value is not None:
            argv.extend([flag, value])
    for flag, value in producer_option_values.items():
        argv.extend([flag, value])
    if not input_staging:
        argv.append("--no-input-staging")
    if not default_activation:
        argv.append("--no-default-activation")
    if bootstrap_test_config:
        argv.append("--bootstrap-test-config")
    argv.append("--skip-project-check" if skip_project_check else "--strict-project-check")
    if no_containerized:
        argv.append("--no-containerized")
    if delete_on_export_success:
        argv.append("--delete-on-export-success")
    if replace_existing_analysis_dir:
        argv.append("--replace-existing-analysis-dir")
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
        help="Path to daylily_pipeline_command_catalog.yaml.",
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
    purpose: str,
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
        purpose=purpose,
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
        tags=parse_tags(tag, purpose=purpose),
    )
    return create_run_mount(request)


def mounts_create(
    source_s3_uri: str = typer.Argument(
        ...,
        metavar="S3_URI",
        help="S3 run-directory URI to mount; the final folder becomes the mount id.",
    ),
    purpose: str = typer.Option(
        "run",
        "--purpose",
        help="Mount purpose: run, reference, control-data, staging, or custom.",
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
        help="Keep the source S3 prefix read-only by policy. Writeback requires .atlas_rw.",
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
        help="Forbidden unless --allow-writeback-admin, --no-read-only, and .atlas_rw are set.",
    ),
    allow_writeback_admin: bool = typer.Option(
        False,
        "--allow-writeback-admin",
        help="Explicit admin override allowing AutoExport writeback policy.",
    ),
    wait: bool = typer.Option(False, "--wait/--no-wait", help="Wait for AVAILABLE."),
    timeout_seconds: int = typer.Option(900, "--timeout-seconds", help="Wait timeout."),
    tag: List[str] = typer.Option([], "--tag", help="Repeatable KEY=VALUE DRA tag."),
) -> None:
    """Create an FSx DRA mount; defaults read-only unless writeback is explicitly allowed."""

    from daylily_ec.run_mounts import format_mount_created

    try:
        record = _create_mount_payload(
            cluster=cluster,
            fsx_file_system_id=fsx_file_system_id,
            region=region,
            profile=profile,
            source_s3_uri=source_s3_uri,
            purpose=purpose,
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
    wait: bool = typer.Option(False, "--wait/--no-wait"),
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
            purpose="run",
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
    purpose: Optional[str] = typer.Option(None, "--purpose"),
) -> None:
    """List managed FSx DRA mounts."""

    from daylily_ec.run_mounts import format_mount_list, list_run_mounts

    try:
        records = list_run_mounts(
            cluster_name=cluster,
            fsx_file_system_id=fsx_file_system_id,
            region=region,
            profile=profile,
            purpose=purpose,
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
    wait: bool = typer.Option(False, "--wait/--no-wait"),
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


def _normalize_benchmark_genome_build(genome_build: str) -> str:
    resolved = str(genome_build or "").strip()
    if resolved not in BENCHMARK_GENOME_BUILDS:
        raise typer.BadParameter(
            "--genome-build must be one of: " + ", ".join(sorted(BENCHMARK_GENOME_BUILDS))
        )
    return resolved


def _normalize_benchmark_analysis_root(analysis_root: str) -> str:
    raw = str(analysis_root or "").strip().rstrip("/")
    if not raw:
        raise typer.BadParameter("--analysis-root is required")
    if "\x00" in raw or "\n" in raw or "\r" in raw:
        raise typer.BadParameter("--analysis-root must be a single POSIX path")
    path = PurePosixPath(raw)
    if not path.is_absolute():
        raise typer.BadParameter("--analysis-root must be an absolute headnode path")
    if any(part in {".", ".."} for part in path.parts):
        raise typer.BadParameter("--analysis-root must not contain . or .. path segments")
    if path.parts[:3] != ("/", "fsx", "analysis_results"):
        raise typer.BadParameter(
            "--analysis-root must be under /fsx/analysis_results/<owner>/<analysis_id>"
        )
    if path.name == "daylily-omics-analysis":
        raise typer.BadParameter(
            "--analysis-root must be the parent analysis directory, not the DayOA clone. "
            "Use /fsx/analysis_results/<owner>/<analysis_id>."
        )
    if len(path.parts) != 5:
        raise typer.BadParameter(
            "--analysis-root must be /fsx/analysis_results/<owner>/<analysis_id>"
        )
    return path.as_posix()


def _build_workflow_collect_benchmarks_script(
    *,
    analysis_root: str,
    genome_build: str,
    cluster: str,
    human_requestor: str,
) -> str:
    return f"""
set -euo pipefail
if [[ "$(id -un)" != "ubuntu" ]]; then
  echo "DYEC benchmark collection must run as ubuntu; got $(id -un)." >&2
  exit 64
fi

ANALYSIS_ROOT={shlex.quote(analysis_root)}
GENOME_BUILD={shlex.quote(genome_build)}
DYEC_CLUSTER_NAME={shlex.quote(cluster)}
export DAYOA_HUMAN_REQUESTOR={shlex.quote(human_requestor)}
agent_stamp="$(date -u +%Y%m%dT%H%M%SZ)"
export DAYOA_AGENT_ID="dyec-benchmark-${{GENOME_BUILD}}-${{agent_stamp}}-$$"
export DAYOA_AGENT_KIND="dyec-cli"
export DAYOA_TMUX_SESSION=""
export DAYOA_LEDGER_PATH=""
export DYEC_CLUSTER="$DYEC_CLUSTER_NAME"

DAYOA_ROOT="${{ANALYSIS_ROOT}}/daylily-omics-analysis"
COLLECTOR="bin/util/benchmarks/collect_day_benchmark_data.sh"
REPORT_DIR="${{DAYOA_ROOT}}/results/day/${{GENOME_BUILD}}/reports"
SUMMARY_TSV="${{REPORT_DIR}}/benchmarks_summary.tsv"

case "$GENOME_BUILD" in
  hg38|hg38_broad|b37) ;;
  *)
    echo "Unsupported genome build: $GENOME_BUILD. Expected hg38, hg38_broad, or b37." >&2
    exit 64
    ;;
esac
if [[ "$ANALYSIS_ROOT" != /fsx/analysis_results/* ]]; then
  echo "Analysis root must be under /fsx/analysis_results: $ANALYSIS_ROOT" >&2
  exit 64
fi
if [[ ! -d "$ANALYSIS_ROOT" ]]; then
  echo "Analysis root does not exist on the headnode: $ANALYSIS_ROOT" >&2
  exit 66
fi
if [[ ! -d "$DAYOA_ROOT" ]]; then
  echo "DayOA clone does not exist: $DAYOA_ROOT" >&2
  exit 66
fi
if [[ ! -f "$DAYOA_ROOT/dayoainit" ]]; then
  echo "DayOA initializer missing: $DAYOA_ROOT/dayoainit" >&2
  exit 66
fi
if [[ ! -f "$DAYOA_ROOT/$COLLECTOR" ]]; then
  echo "DayOA benchmark collector missing: $DAYOA_ROOT/$COLLECTOR" >&2
  exit 66
fi
if ! command -v dyec >/dev/null 2>&1; then
  echo "dyec CLI is required on the headnode for analysis lock auditing. Run dyec headnode configure, then retry." >&2
  exit 66
fi

lock_acquired=0
release_lock() {{
  local rc="$1"
  if [[ "$lock_acquired" == "1" ]]; then
    if ! dyec analysis lock release \\
      --analysis-root "$ANALYSIS_ROOT" \\
      --human-requestor "$DAYOA_HUMAN_REQUESTOR" \\
      --note "benchmark collector finished rc=${{rc}}" >/dev/null; then
      echo "Warning: failed to release DYEC analysis lock for $ANALYSIS_ROOT" >&2
    fi
  fi
}}
trap 'rc=$?; release_lock "$rc"; exit "$rc"' EXIT

dyec analysis lock acquire \\
  --analysis-root "$ANALYSIS_ROOT" \\
  --operation write \\
  --intent "collect DayOA benchmark summary for $GENOME_BUILD" \\
  --human-requestor "$DAYOA_HUMAN_REQUESTOR" \\
  --command-summary "bash $COLLECTOR $GENOME_BUILD" \\
  --operation-scope "benchmark-collection:$GENOME_BUILD" >/dev/null
lock_acquired=1

cd "$DAYOA_ROOT"
source dyoainit
if ! type dy-a >/dev/null 2>&1; then
  echo "DayOA activation did not define dy-a after source dyoainit." >&2
  exit 66
fi
dy-a local "$GENOME_BUILD"
bash "$COLLECTOR" "$GENOME_BUILD"

if [[ ! -s "$SUMMARY_TSV" ]]; then
  echo "Benchmark summary was not created or is empty: $SUMMARY_TSV" >&2
  exit 1
fi

export DAYLILY_BENCHMARK_ANALYSIS_ROOT="$ANALYSIS_ROOT"
export DAYLILY_BENCHMARK_DAYOA_ROOT="$DAYOA_ROOT"
export DAYLILY_BENCHMARK_GENOME_BUILD="$GENOME_BUILD"
export DAYLILY_BENCHMARK_REPORT_DIR="$REPORT_DIR"
export DAYLILY_BENCHMARK_SUMMARY_TSV="$SUMMARY_TSV"
export DAYLILY_BENCHMARK_ROW_COUNT="$(wc -l < "$SUMMARY_TSV" | tr -d ' ')"
export DAYLILY_BENCHMARK_BYTES="$(wc -c < "$SUMMARY_TSV" | tr -d ' ')"
python3 - <<'PY'
import json
import os

payload = {{
    "analysis_root": os.environ["DAYLILY_BENCHMARK_ANALYSIS_ROOT"],
    "dayoa_root": os.environ["DAYLILY_BENCHMARK_DAYOA_ROOT"],
    "genome_build": os.environ["DAYLILY_BENCHMARK_GENOME_BUILD"],
    "report_dir": os.environ["DAYLILY_BENCHMARK_REPORT_DIR"],
    "summary_tsv": os.environ["DAYLILY_BENCHMARK_SUMMARY_TSV"],
    "row_count": int(os.environ["DAYLILY_BENCHMARK_ROW_COUNT"] or "0"),
    "bytes": int(os.environ["DAYLILY_BENCHMARK_BYTES"] or "0"),
}}
print("__DAYLILY_BENCHMARK_COLLECTION__=" + json.dumps(payload, sort_keys=True))
PY
"""


def _parse_benchmark_collection_payload(stdout: str) -> dict[str, Any]:
    from daylily_ec.scripts.common import CommandError

    marker = "__DAYLILY_BENCHMARK_COLLECTION__="
    for line in stdout.splitlines():
        if line.startswith(marker):
            payload = json.loads(line.split("=", 1)[1])
            if not isinstance(payload, dict):
                raise CommandError("Benchmark collection payload contained non-object JSON.")
            return payload
    raise CommandError("Benchmark collection output did not include a payload marker.")


def workflow_collect_benchmarks(
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region."),
    cluster: Optional[str] = typer.Option(None, "--cluster", "--cluster-name"),
    analysis_root: str = typer.Option(
        ...,
        "--analysis-root",
        help="/fsx/analysis_results/<owner>/<analysis_id> directory containing daylily-omics-analysis.",
    ),
    genome_build: str = typer.Option(
        ...,
        "--genome-build",
        "--build",
        help="DayOA genome build: hg38, hg38_broad, or b37.",
    ),
    human_requestor: Optional[str] = typer.Option(
        None,
        "--human-requestor",
        "--human",
        help="Human recorded in analysis-root lock and visit metadata.",
    ),
    timeout: int = typer.Option(
        1800,
        "--timeout",
        help="Maximum seconds for the remote benchmark collection command.",
    ),
) -> None:
    """Collect DayOA benchmark TSVs into results/day/<genome-build>/reports."""

    from daylily_ec.aws.ssm import (
        SsmCommandFailedError,
        SsmError,
        run_shell,
        wait_for_ssm_online,
    )
    from daylily_ec.scripts.common import CommandError

    _warn_if_dayec_env_inactive()
    try:
        resolved_build = _normalize_benchmark_genome_build(genome_build)
        resolved_analysis_root = _normalize_benchmark_analysis_root(analysis_root)
        resolved_human = (
            str(human_requestor or "").strip()
            or os.environ.get("DAYOA_HUMAN_REQUESTOR", "").strip()
            or os.environ.get("USER", "").strip()
            or os.environ.get("LOGNAME", "").strip()
            or "dyec"
        )
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
        script = _build_workflow_collect_benchmarks_script(
            analysis_root=resolved_analysis_root,
            genome_build=resolved_build,
            cluster=resolved_cluster,
            human_requestor=resolved_human,
        )
        result = run_shell(
            target.instance_id,
            resolved_region,
            script,
            profile=resolved_profile,
            timeout=timeout,
            comment=f"Collect DayOA benchmarks for {resolved_analysis_root}",
        )
        payload = _parse_benchmark_collection_payload(result.stdout)
    except SsmCommandFailedError as exc:
        if exc.result.stdout.strip():
            typer.echo(exc.result.stdout.rstrip())
        if exc.result.stderr.strip():
            typer.echo(exc.result.stderr.rstrip(), err=True)
        _exit_headnode_error(exc)
    except (CommandError, SsmError, TimeoutError, json.JSONDecodeError) as exc:
        _exit_headnode_error(exc)

    if result.stderr:
        typer.echo(result.stderr.rstrip(), err=True)
    if _json_mode():
        output.emit_json(payload)
        return
    output.success("Benchmark summary collected.")
    output.print_text(f"Analysis root: {payload['analysis_root']}")
    output.print_text(f"DayOA root:    {payload['dayoa_root']}")
    output.print_text(f"Genome build:  {payload['genome_build']}")
    output.print_text(f"Summary TSV:   {payload['summary_tsv']}")
    output.print_text(f"Rows:          {payload['row_count']}")


def _parse_workflow_stop_payload(stdout: str) -> dict[str, Any]:
    from daylily_ec.scripts.common import CommandError

    marker = "__DAYLILY_WORKFLOW_STOP__="
    for line in stdout.splitlines():
        if line.startswith(marker):
            payload = json.loads(line.split("=", 1)[1])
            if not isinstance(payload, dict):
                raise CommandError("Workflow stop payload contained non-object JSON.")
            return payload
    raise CommandError("Workflow stop output did not include a stop payload marker.")


def workflow_stop(
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region."),
    cluster: Optional[str] = typer.Option(None, "--cluster", "--cluster-name"),
    session: Optional[str] = typer.Option(None, "--session", help="Tmux session/run name."),
    run_dir: Optional[str] = typer.Option(None, "--run-dir", help="Explicit run directory."),
    cancel_slurm_jobs: bool = typer.Option(
        False,
        "--cancel-slurm-jobs",
        help="Also cancel active Slurm jobs whose names match --job-name-pattern.",
    ),
    job_name_pattern: Optional[str] = typer.Option(
        None,
        "--job-name-pattern",
        help="Python regex used to select Slurm job names when --cancel-slurm-jobs is set.",
    ),
    timeout: int = typer.Option(
        120,
        "--timeout",
        help="Maximum seconds for the remote stop command.",
    ),
) -> None:
    """Stop a headnode workflow tmux controller, with explicit optional Slurm cancellation."""

    from daylily_ec.aws.ssm import SsmError, run_shell, wait_for_ssm_online
    from daylily_ec.scripts.common import CommandError

    _warn_if_dayec_env_inactive()
    if cancel_slurm_jobs and not str(job_name_pattern or "").strip():
        raise typer.BadParameter("--job-name-pattern is required with --cancel-slurm-jobs")
    if job_name_pattern and not cancel_slurm_jobs:
        raise typer.BadParameter("--job-name-pattern requires --cancel-slurm-jobs")

    try:
        resolved_run_dir = _workflow_run_dir(session, run_dir)
        resolved_session = session or Path(resolved_run_dir).name
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
        script = f"""
set -euo pipefail
export DAYLILY_WORKFLOW_SESSION={shlex.quote(resolved_session)}
export DAYLILY_WORKFLOW_RUN_DIR={shlex.quote(resolved_run_dir)}
export DAYLILY_CANCEL_SLURM_JOBS={shlex.quote("true" if cancel_slurm_jobs else "false")}
export DAYLILY_JOB_NAME_PATTERN={shlex.quote(job_name_pattern or "")}
python3 - <<'PY'
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys


def run(command):
    return subprocess.run(command, capture_output=True, text=True)


def require_command(name):
    result = run(["bash", "-lc", f"command -v {{name}}"])
    if result.returncode != 0:
        raise SystemExit(f"required command not found on headnode PATH: {{name}}")


def tmux_session_name(session_name):
    return re.sub(r"[^A-Za-z0-9_-]", "_", session_name)


def tmux_present(name):
    return run(["tmux", "has-session", "-t", f"={{name}}"]).returncode == 0


def slurm_jobs_matching(pattern_text):
    require_command("squeue")
    pattern = re.compile(pattern_text)
    result = run(["squeue", "-h", "-o", "%A\\t%j"])
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or result.stdout.strip() or "squeue failed")
    jobs = []
    for raw_line in result.stdout.splitlines():
        if not raw_line.strip():
            continue
        try:
            job_id, job_name = raw_line.split("\\t", 1)
        except ValueError:
            continue
        if pattern.search(job_name):
            jobs.append({{"job_id": job_id, "name": job_name}})
    return jobs


session = os.environ["DAYLILY_WORKFLOW_SESSION"]
run_dir = pathlib.Path(os.environ["DAYLILY_WORKFLOW_RUN_DIR"])
cancel_slurm = os.environ["DAYLILY_CANCEL_SLURM_JOBS"] == "true"
job_name_pattern = os.environ.get("DAYLILY_JOB_NAME_PATTERN", "")
session_tmux = tmux_session_name(session)
require_command("tmux")
before_tmux = tmux_present(session_tmux)
jobs_before = slurm_jobs_matching(job_name_pattern) if cancel_slurm else []

killed_tmux = False
if before_tmux:
    kill = run(["tmux", "kill-session", "-t", f"={{session_tmux}}"])
    if kill.returncode != 0:
        raise SystemExit(kill.stderr.strip() or kill.stdout.strip() or "tmux kill-session failed")
    killed_tmux = True

scancelled_job_ids = []
if cancel_slurm and jobs_before:
    require_command("scancel")
    scancelled_job_ids = [job["job_id"] for job in jobs_before]
    cancel = run(["scancel", *scancelled_job_ids])
    if cancel.returncode != 0:
        raise SystemExit(cancel.stderr.strip() or cancel.stdout.strip() or "scancel failed")

after_tmux = tmux_present(session_tmux)
jobs_after = slurm_jobs_matching(job_name_pattern) if cancel_slurm else []
status_path = run_dir / "status.json"
status_updated = False
if killed_tmux or scancelled_job_ids:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    status = {{}}
    if status_path.is_file():
        try:
            status = json.loads(status_path.read_text(encoding="utf-8") or "{{}}")
        except json.JSONDecodeError:
            status = {{}}
    if not isinstance(status, dict):
        status = {{}}
    status.setdefault("session_name", session)
    status["completed_at"] = now
    status["exit_code"] = 130
    status["stopped"] = True
    status["stop_reason"] = "dyec workflow stop"
    status["stop_cancelled_slurm_job_ids"] = scancelled_job_ids
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
    status_updated = True

payload = {{
    "session_name": session,
    "run_dir": str(run_dir),
    "tmux_session_name": session_tmux,
    "tmux_session_before": before_tmux,
    "tmux_session_after": after_tmux,
    "killed_tmux_session": killed_tmux,
    "cancel_slurm_jobs": cancel_slurm,
    "job_name_pattern": job_name_pattern,
    "slurm_jobs_before": jobs_before,
    "scancelled_job_ids": scancelled_job_ids,
    "slurm_jobs_after": jobs_after,
    "status_path": str(status_path),
    "status_updated": status_updated,
}}
print("__DAYLILY_WORKFLOW_STOP__=" + json.dumps(payload, sort_keys=True))
PY
"""
        result = run_shell(
            target.instance_id,
            resolved_region,
            script,
            profile=resolved_profile,
            timeout=timeout,
            comment=f"Stop Daylily workflow {resolved_session}",
        )
        payload = _parse_workflow_stop_payload(result.stdout)
    except (CommandError, SsmError, TimeoutError, json.JSONDecodeError) as exc:
        _exit_headnode_error(exc)

    if _json_mode():
        output.emit_json(payload)
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


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


def _emit_analysis_payload(payload: Any, *, text: Optional[str] = None) -> None:
    if _json_mode():
        output.emit_json(payload)
        return
    if text is not None:
        typer.echo(text)
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))


def analysis_visit(
    analysis_root: str = typer.Option(..., "--analysis-root", help="Analysis root path."),
    intent: str = typer.Option(..., "--intent", help="Reason for the visit."),
    mode: str = typer.Option(
        "read",
        "--mode",
        help="Visit mode: read, monitor, log, search, query, export, write, unlock, delete, kill.",
    ),
    note: Optional[str] = typer.Option(None, "--note", help="Short visit note."),
    human_requestor: Optional[str] = typer.Option(
        None,
        "--human-requestor",
        "--human",
        help="Human on whose behalf this visit is happening.",
    ),
    s3_visit_uri: Optional[str] = typer.Option(
        None,
        "--s3-visit-uri",
        help="Optional S3 analysis/report prefix where a no-delete visit marker is written.",
    ),
) -> None:
    """Record an analysis-root visit without requiring write-lock ownership."""

    try:
        from daylily_ec.analysis_lock import write_visit

        payload = write_visit(
            analysis_root,
            mode=mode,
            intent=intent,
            note=note,
            human_requestor=human_requestor,
            s3_visit_uri=s3_visit_uri,
        )
        _emit_analysis_payload(
            payload,
            text=f"recorded {mode} visit for {payload['analysis_root']}",
        )
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def analysis_status(
    mode: str = typer.Argument(..., help="Report detail: slim or full."),
    analysis_root: str = typer.Option(..., "--analysis-root", help="Exact analysis root path."),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS profile for remote cluster inspection.",
    ),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help="AWS region for remote cluster inspection.",
    ),
    cluster: Optional[str] = typer.Option(
        None,
        "--cluster",
        "--cluster-name",
        help="Cluster whose headnode contains the analysis root; omit when already on the headnode.",
    ),
    remote_user: str = typer.Option(
        "ubuntu",
        "--remote-user",
        help="Remote SSM login user. DayOA headnodes normally use ubuntu.",
    ),
    tail_lines: int = typer.Option(
        1000,
        "--tail-lines",
        min=1,
        help="Lines inspected per active-job stream and master log in full mode.",
    ),
) -> None:
    """Report exact-root DayOA progress, jobs, artifacts, filesystem, and telemetry."""

    try:
        from daylily_ec.analysis_status import collect_analysis_status, render_analysis_status

        if cluster:
            from daylily_ec.aws.ssm import run_shell, wait_for_ssm_online

            _warn_if_dayec_env_inactive()
            resolved_profile, resolved_region, resolved_cluster, target = (
                _resolve_headnode_cli_target(
                    profile=profile,
                    region=region,
                    cluster=cluster,
                )
            )
            wait_for_ssm_online(
                target.instance_id,
                resolved_region,
                profile=resolved_profile,
                timeout=120,
            )
            remote_argv = [
                "dyec",
                "--json",
                "analysis",
                "status",
                mode,
                "--analysis-root",
                analysis_root,
                "--tail-lines",
                str(tail_lines),
            ]
            script = "set -euo pipefail\ncommand -v dyec >/dev/null\n" + shlex.join(remote_argv)
            result = run_shell(
                target.instance_id,
                resolved_region,
                script,
                profile=resolved_profile,
                as_user=remote_user,
                timeout=300,
                comment=f"Daylily {mode} analysis status",
            )
            payload = _parse_workflow_status_payload(result.stdout)
            payload["cluster"] = {
                "name": resolved_cluster,
                "region": resolved_region,
                "headnode_instance_id": target.instance_id,
            }
        else:
            if profile or region:
                raise ValueError("--profile and --region require --cluster")
            payload = collect_analysis_status(
                analysis_root,
                mode=mode,
                tail_lines=tail_lines,
            )
        _emit_analysis_payload(payload, text=render_analysis_status(payload))
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def _download_sample_stats_dag(
    *,
    instance_id: str,
    region: str,
    profile: str,
    remote_user: str,
    remote_path: str,
    expected_size: int,
    expected_sha256: str,
    destination: Path,
) -> dict[str, Any]:
    from daylily_ec.aws.ssm import run_shell

    if expected_size > 20 * 1024 * 1024:
        raise ValueError("DAG PNG exceeds the 20 MiB bounded SSM transfer limit")
    target = destination.expanduser().resolve()
    if target.exists():
        raise ValueError(f"refusing to overwrite DAG destination: {target}")
    if not target.parent.is_dir():
        raise ValueError(f"DAG destination parent does not exist: {target.parent}")
    partial = target.with_name(f".{target.name}.partial")
    if partial.exists():
        raise ValueError(f"refusing to overwrite existing partial DAG transfer: {partial}")
    chunk_bytes = 15000
    try:
        with partial.open("xb") as handle:
            for offset in range(0, expected_size, chunk_bytes):
                script = (
                    "set -euo pipefail\n"
                    f"test -f {shlex.quote(remote_path)}\n"
                    f"dd if={shlex.quote(remote_path)} bs=1 skip={offset} count={min(chunk_bytes, expected_size - offset)} status=none | base64 -w0"
                )
                result = run_shell(
                    instance_id,
                    region,
                    script,
                    profile=profile,
                    as_user=remote_user,
                    timeout=120,
                    comment="Read verified DayOA DAG chunk",
                )
                handle.write(base64.b64decode(result.stdout.strip(), validate=True))
        digest = hashlib.sha256(partial.read_bytes()).hexdigest()
        if partial.stat().st_size != expected_size or digest != expected_sha256:
            raise ValueError("remote DAG transfer failed SHA-256 or size verification")
        partial.replace(target)
        return {"path": str(target), "size_bytes": expected_size, "sha256": digest}
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def command_sample_stats(
    pipeline: str = typer.Argument(..., help="Pipeline contract; currently hiomrs-kitchensink."),
    name: str = typer.Option(..., "--name", help="Required sole top-level JSON report key."),
    analysis_root: str = typer.Option(..., "--analysis-root", help="Exact analysis root path."),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="AWS profile for remote inspection."
    ),
    region: Optional[str] = typer.Option(
        None, "--region", help="AWS region for remote inspection."
    ),
    cluster: Optional[str] = typer.Option(
        None, "--cluster", "--cluster-name", help="Cluster containing the analysis root."
    ),
    remote_user: str = typer.Option("ubuntu", "--remote-user", help="Remote SSM login user."),
    tail_lines: int = typer.Option(
        1000, "--tail-lines", min=1, help="Bounded log lines inspected."
    ),
    dag_output: Optional[Path] = typer.Option(
        None, "--dag-output", help="Exact local filename for a verified DAG PNG copy."
    ),
) -> None:
    """Report source-backed per-unit HIOMRS progress and optionally copy its DAG."""

    try:
        from daylily_ec.command_sample_stats import (
            collect_command_sample_stats,
            copy_dag,
            enrich_aws_context,
            render_command_sample_stats,
        )

        if cluster:
            from daylily_ec.aws.ssm import run_shell, wait_for_ssm_online

            _warn_if_dayec_env_inactive()
            resolved_profile, resolved_region, resolved_cluster, target = (
                _resolve_headnode_cli_target(
                    profile=profile,
                    region=region,
                    cluster=cluster,
                )
            )
            wait_for_ssm_online(
                target.instance_id, resolved_region, profile=resolved_profile, timeout=120
            )
            remote_argv = [
                "dyec",
                "--json",
                "command",
                "sample-stats",
                pipeline,
                "--name",
                name,
                "--analysis-root",
                analysis_root,
                "--tail-lines",
                str(tail_lines),
            ]
            result = run_shell(
                target.instance_id,
                resolved_region,
                "set -euo pipefail\ncommand -v dyec >/dev/null\n" + shlex.join(remote_argv),
                profile=resolved_profile,
                as_user=remote_user,
                timeout=300,
                comment="Daylily command sample stats",
            )
            payload = _parse_workflow_status_payload(result.stdout)
            enrich_aws_context(
                payload,
                profile=resolved_profile,
                region=resolved_region,
                cluster=resolved_cluster,
                headnode_instance_id=target.instance_id,
            )
            if dag_output:
                report = payload[name]
                dag = report["dag"]
                if not dag["available"]:
                    raise ValueError("this analysis has no generated DAG PNG")
                report["dag_download"] = _download_sample_stats_dag(
                    instance_id=target.instance_id,
                    region=resolved_region,
                    profile=resolved_profile,
                    remote_user=remote_user,
                    remote_path=dag["path"],
                    expected_size=int(dag["size_bytes"]),
                    expected_sha256=dag["sha256"],
                    destination=dag_output,
                )
        else:
            if profile or region:
                raise ValueError("--profile and --region require --cluster")
            payload = collect_command_sample_stats(
                analysis_root,
                name=name,
                pipeline=pipeline,
                tail_lines=tail_lines,
            )
            if dag_output:
                copy_dag(payload, dag_output)
        _emit_analysis_payload(payload, text=render_command_sample_stats(payload))
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def analysis_guard(
    analysis_root: str = typer.Option(..., "--analysis-root", help="Analysis root path."),
    operation: str = typer.Option(
        ...,
        "--operation",
        help="Operation to guard: read, export, write, unlock, delete, or kill.",
    ),
    intent: str = typer.Option(..., "--intent", help="Reason for the guarded operation."),
    human_requestor: Optional[str] = typer.Option(
        None,
        "--human-requestor",
        "--human",
        help="Human on whose behalf this operation is happening.",
    ),
    command: List[str] = typer.Argument(
        [],
        metavar="[-- COMMAND...]",
        help="Optional command to execute only after the guard passes.",
    ),
) -> None:
    """Guard a read/write-like operation against the analysis-root lock state."""

    try:
        from daylily_ec.analysis_lock import assert_operation_allowed, guarded_run

        if command:
            rc = guarded_run(
                analysis_root,
                operation=operation,
                intent=intent,
                command=command,
                human_requestor=human_requestor,
            )
            raise typer.Exit(rc)
        payload = assert_operation_allowed(
            analysis_root,
            operation=operation,
            intent=intent,
            human_requestor=human_requestor,
            command_summary=None,
        )
        _emit_analysis_payload(payload, text=f"allowed {operation} for {analysis_root}")
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def analysis_lock_status(
    analysis_root: str = typer.Option(..., "--analysis-root", help="Analysis root path."),
) -> None:
    """Show the current write-lock owner for an analysis root."""

    try:
        from daylily_ec.analysis_lock import lock_status

        payload = lock_status(analysis_root)
        text = "unlocked"
        if payload["locked"]:
            owner = payload["owner"] or {}
            text = "locked by " + str(owner.get("agent_id", "unknown"))
        _emit_analysis_payload(payload, text=text)
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def analysis_lock_acquire(
    analysis_root: str = typer.Option(..., "--analysis-root", help="Analysis root path."),
    operation: str = typer.Option(
        "write",
        "--operation",
        help="Protected operation scope: write, unlock, delete, or kill.",
    ),
    intent: str = typer.Option(..., "--intent", help="Reason for acquiring the lock."),
    human_requestor: Optional[str] = typer.Option(
        None,
        "--human-requestor",
        "--human",
        help="Human on whose behalf this lock is acquired.",
    ),
    command_summary: Optional[str] = typer.Option(
        None,
        "--command-summary",
        help="Short summary of the controller/workflow command protected by this lock.",
    ),
    operation_scope: Optional[str] = typer.Option(
        None,
        "--operation-scope",
        help="Optional narrower scope recorded in owner metadata.",
    ),
) -> None:
    """Acquire an atomic analysis-root write lock with mkdir semantics."""

    try:
        from daylily_ec.analysis_lock import acquire_lock

        payload = acquire_lock(
            analysis_root,
            operation=operation,
            intent=intent,
            human_requestor=human_requestor,
            command_summary=command_summary,
            operation_scope=operation_scope,
        )
        _emit_analysis_payload(payload, text=f"acquired {operation} lock for {analysis_root}")
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def analysis_lock_release(
    analysis_root: str = typer.Option(..., "--analysis-root", help="Analysis root path."),
    human_requestor: Optional[str] = typer.Option(
        None,
        "--human-requestor",
        "--human",
        help="Human on whose behalf this lock is released.",
    ),
    note: Optional[str] = typer.Option(None, "--note", help="Release note."),
) -> None:
    """Release the current agent's analysis-root write lock."""

    try:
        from daylily_ec.analysis_lock import release_lock

        payload = release_lock(
            analysis_root,
            human_requestor=human_requestor,
            note=note,
        )
        _emit_analysis_payload(payload, text=f"released lock for {analysis_root}")
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def analysis_lock_heartbeat(
    analysis_root: str = typer.Option(..., "--analysis-root", help="Analysis root path."),
    human_requestor: Optional[str] = typer.Option(
        None,
        "--human-requestor",
        "--human",
        help="Human on whose behalf this heartbeat is recorded.",
    ),
    note: Optional[str] = typer.Option(None, "--note", help="Heartbeat note."),
) -> None:
    """Append a heartbeat for the current agent's active write lock."""

    try:
        from daylily_ec.analysis_lock import heartbeat_lock

        payload = heartbeat_lock(
            analysis_root,
            human_requestor=human_requestor,
            note=note,
        )
        _emit_analysis_payload(payload, text=f"heartbeat recorded for {analysis_root}")
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def analysis_lock_takeover(
    analysis_root: str = typer.Option(..., "--analysis-root", help="Analysis root path."),
    operation: str = typer.Option(
        "write",
        "--operation",
        help="Protected operation scope: write, unlock, delete, or kill.",
    ),
    reason: str = typer.Option(..., "--reason", help="Reason takeover is being requested."),
    request: bool = typer.Option(
        False,
        "--request/--no-request",
        help="Print the takeover token and current owner without mutating the lock.",
    ),
    confirm_token: Optional[str] = typer.Option(
        None,
        "--confirm-token",
        help="Token from a prior --request output.",
    ),
    approved_by: Optional[str] = typer.Option(
        None,
        "--approved-by",
        help="Human approver for the explicit takeover.",
    ),
    intent: str = typer.Option(
        "explicit approved takeover",
        "--intent",
        help="Intent recorded for the new lock owner.",
    ),
    human_requestor: Optional[str] = typer.Option(
        None,
        "--human-requestor",
        "--human",
        help="Human on whose behalf the takeover is happening.",
    ),
    command_summary: Optional[str] = typer.Option(
        None,
        "--command-summary",
        help="Short summary of the command protected after takeover.",
    ),
) -> None:
    """Request or execute a double-approved lock takeover."""

    try:
        from daylily_ec.analysis_lock import takeover_lock, takeover_request

        if request:
            payload = takeover_request(analysis_root, operation=operation, reason=reason)
            _emit_analysis_payload(
                payload,
                text=(
                    "takeover token "
                    + str(payload["token"])
                    + " for "
                    + str(payload["analysis_root"])
                ),
            )
            return
        if not confirm_token:
            raise typer.BadParameter("--confirm-token is required unless --request is set")
        payload = takeover_lock(
            analysis_root,
            operation=operation,
            confirm_token=confirm_token,
            approved_by=approved_by or "",
            reason=reason,
            intent=intent,
            human_requestor=human_requestor,
            command_summary=command_summary,
        )
        _emit_analysis_payload(payload, text=f"took over {operation} lock for {analysis_root}")
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def tests_pytest(
    coverage: bool = typer.Option(
        False,
        "--coverage",
        help="Run pytest with branch coverage for daylily_ec and fail below 80%.",
    ),
    pytest_args: Optional[List[str]] = typer.Argument(
        None,
        help="Arguments passed to pytest after `--`.",
    ),
) -> None:
    """Run the local pytest suite through the active Python environment."""

    from daylily_ec.tests_runner import TestsRunnerError, run_pytest

    _warn_if_dayec_env_inactive()
    try:
        rc = run_pytest(coverage=coverage, pytest_args=pytest_args or [])
    except TestsRunnerError as exc:
        raise typer.BadParameter(str(exc)) from exc
    raise typer.Exit(rc)


def tests_command_catalog(
    cluster: str = typer.Option(..., "--cluster", "--cluster-name", help="Target cluster name."),
    profile: str = typer.Option(..., "--profile", help="AWS CLI profile."),
    region: str = typer.Option(..., "--region", help="AWS region."),
    command_codes: str = typer.Option(
        ...,
        "--command-codes",
        help=(
            "Comma/space-separated catalog command ids, dyec-released-core, or dyec-released-all."
        ),
    ),
    evidence_s3_uri: str = typer.Option(
        ...,
        "--evidence-s3-uri",
        help="S3 root for command-catalog evidence export.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Launch only dry-run workflow phases.",
    ),
    create_missing_mounts: bool = typer.Option(
        False,
        "--create-missing-mounts",
        help="Create missing unique run-directory DRAs after read-only preflight.",
    ),
    parallel: int = typer.Option(16, "--parallel", help="Maximum concurrent launched phases."),
    jobs: Optional[int] = typer.Option(
        None,
        "--jobs",
        help="Override the per-command Snakemake job count from the catalog.",
    ),
    max_runtime_minutes: int = typer.Option(
        DEFAULT_JOB_MAX_RUNTIME_MINUTES,
        "--max-runtime-minutes",
        help=(
            "Deprecated compatibility option. DYEC does not append Snakemake --default-resources."
        ),
    ),
    executing_entity: str = typer.Option(
        "ubuntu",
        "--executing-entity",
        "-u",
        help="Analysis-result owner under /fsx/analysis_results.",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        help="Local evidence directory. Defaults to docs/plans/<stamp>_dyec_tests_command_catalog_logs.",
    ),
    stamp: Optional[str] = typer.Option(
        None,
        "--stamp",
        help="UTC stamp for reproducible evidence paths. Defaults to current UTC.",
    ),
    timeout_minutes: int = typer.Option(
        360,
        "--timeout-minutes",
        help="Minutes to wait for each launched workflow phase to finish.",
    ),
    poll_interval_seconds: int = typer.Option(
        30,
        "--poll-interval-seconds",
        help="Seconds between workflow status polls.",
    ),
    catalog_config: Optional[Path] = typer.Option(
        None,
        "--catalog-config",
        help="Path to daylily_pipeline_command_catalog.yaml.",
    ),
) -> None:
    """Run command-catalog prep tests on a cluster with exported evidence."""

    from daylily_ec.tests_runner import (
        CommandCatalogOptions,
        RenderedPhase,
        TestsRunnerError,
        WorkflowLaunchMetadata,
        run_command_catalog,
    )

    _warn_if_dayec_env_inactive()

    def status_reader(
        metadata: WorkflowLaunchMetadata,
        phase: RenderedPhase,
    ) -> dict[str, Any]:
        session_name = metadata.session_name or phase.session_name
        result = _read_workflow_file(
            profile=profile,
            region=region,
            cluster=cluster,
            session=session_name,
            run_dir=None if session_name else (metadata.run_dir or None),
            filename="status.json",
        )
        return _parse_workflow_status_payload(result.stdout)

    try:
        result = run_command_catalog(
            CommandCatalogOptions(
                cluster=cluster,
                profile=profile,
                region=region,
                command_codes=command_codes,
                evidence_s3_uri=evidence_s3_uri,
                dry_run_only=dry_run,
                create_missing_mounts=create_missing_mounts,
                parallel=parallel,
                jobs=jobs,
                max_runtime_minutes=max_runtime_minutes,
                executing_entity=executing_entity,
                output_dir=output_dir,
                stamp=stamp,
                timeout_minutes=timeout_minutes,
                poll_interval_seconds=poll_interval_seconds,
                catalog_config=catalog_config,
            ),
            launch_func=_invoke_workflow_launch,
            status_func=status_reader,
        )
    except (TestsRunnerError, RuntimeError, ValueError) as exc:
        _exit_headnode_error(exc)

    payload = result.to_payload()
    if _json_mode():
        output.emit_json(payload)
    else:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    raise typer.Exit(result.rc)


def tests_command_catalog_performance(
    benchmark_rows_tsv: Path = typer.Option(
        ...,
        "--benchmark-rows",
        help="Command-catalog benchmark_rows.tsv produced from DayOA benchmark files.",
    ),
    rule_summary_tsv: Optional[Path] = typer.Option(
        None,
        "--rule-summary",
        help="Optional rule_resource_summary.tsv with per-rule recommendations and packing.",
    ),
    slurm_jobs_tsv: Optional[Path] = typer.Option(
        None,
        "--slurm-jobs",
        help="Optional slurm_jobs_with_packing.tsv with job/node packing evidence.",
    ),
    dyec_version: str = typer.Option(..., "--dyec-version", help="DYEC version key to record."),
    dayoa_version: str = typer.Option("", "--dayoa-version", help="DayOA version/ref under test."),
    cluster: str = typer.Option("", "--cluster", "--cluster-name", help="Cluster name."),
    run_id: str = typer.Option("", "--run-id", help="Command-catalog run id or stamp."),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        help="Directory for command_catalog_performance_profile.json and summary TSV.",
    ),
    history_json: Optional[Path] = typer.Option(
        None,
        "--history-json",
        help="Historical comparator JSON keyed by DYEC version.",
    ),
    catalog_config: Optional[Path] = typer.Option(
        None,
        "--catalog-config",
        help="Path to daylily_pipeline_command_catalog.yaml.",
    ),
    command_id: Optional[List[str]] = typer.Option(
        None,
        "--command-id",
        help="Explicit command id to include; repeatable. Defaults to ids present in TSVs.",
    ),
    include_all_catalog_commands: bool = typer.Option(
        False,
        "--include-all-catalog-commands",
        help="Include every catalog command even if no benchmark rows were captured.",
    ),
    dev_command_id: Optional[List[str]] = typer.Option(
        None,
        "--dev-command-id",
        help="Command id to classify as the dev evidence cohort; repeatable.",
    ),
    prod_command_id: Optional[List[str]] = typer.Option(
        None,
        "--prod-command-id",
        help="Command id to force into the prod evidence cohort; repeatable.",
    ),
    captured_at: Optional[str] = typer.Option(
        None,
        "--captured-at",
        help="Optional UTC timestamp to store in the profile.",
    ),
    replace_existing_version: bool = typer.Option(
        False,
        "--replace-existing-version",
        help="Replace an existing dyec_versions[--dyec-version] history entry.",
    ),
) -> None:
    """Summarize command-catalog benchmarks and update the performance history."""

    from daylily_ec.command_catalog_performance import (
        CommandCatalogPerformanceError,
        CommandCatalogPerformanceOptions,
        build_command_catalog_performance_profile,
    )

    _warn_if_dayec_env_inactive()
    try:
        profile = build_command_catalog_performance_profile(
            CommandCatalogPerformanceOptions(
                benchmark_rows_tsv=benchmark_rows_tsv,
                rule_summary_tsv=rule_summary_tsv,
                slurm_jobs_tsv=slurm_jobs_tsv,
                dyec_version=dyec_version,
                dayoa_version=dayoa_version,
                cluster=cluster,
                run_id=run_id,
                output_dir=output_dir,
                history_json=history_json,
                catalog_config=catalog_config,
                command_ids=tuple(command_id or []),
                include_all_catalog_commands=include_all_catalog_commands,
                dev_command_ids=frozenset(dev_command_id or []),
                prod_command_ids=frozenset(prod_command_id or []),
                captured_at=captured_at,
                replace_existing_version=replace_existing_version,
            )
        )
    except (CommandCatalogPerformanceError, RuntimeError, ValueError) as exc:
        _exit_headnode_error(exc)

    if _json_mode():
        output.emit_json(profile)
    else:
        typer.echo(json.dumps(profile, indent=2, sort_keys=True))


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
        [
            ("snapshot", pricing_snapshot, REQUIRED_JSON),
            ("spot-logs", pricing_spot_logs, required_policy(supports_json=True)),
        ],
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
        "aws/audit",
        "Cached, throttled, read-only AWS API call attribution.",
        [
            (
                "api-calls",
                aws_audit_api_calls,
                required_policy(supports_json=True, long_running=True),
            ),
            (
                "cost-resources",
                aws_audit_cost_resources,
                required_policy(supports_json=True, long_running=True),
            ),
        ],
    )
    register_group_commands(
        registry,
        "slurm-accounting",
        "Slurm accounting database helpers.",
        [
            (
                "ensure",
                slurm_accounting_ensure,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
            (
                "attach",
                slurm_accounting_attach,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
        ],
    )
    register_group_commands(
        registry,
        "cost-centers",
        "Global cost-center registry helpers.",
        [
            (
                "ensure-registry",
                cost_centers_ensure_registry,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
            (
                "create",
                cost_centers_create,
                required_policy(supports_json=True, mutates_state=True),
            ),
            (
                "edit",
                cost_centers_edit,
                required_policy(supports_json=True, mutates_state=True),
            ),
            (
                "disable",
                cost_centers_disable,
                required_policy(supports_json=True, mutates_state=True),
            ),
            ("show", cost_centers_show, REQUIRED_JSON),
            ("list", cost_centers_list, REQUIRED_JSON),
            ("usage", cost_centers_usage, REQUIRED_JSON),
            (
                "put-usage",
                cost_centers_put_usage,
                required_policy(supports_json=True, mutates_state=True),
            ),
            (
                "refresh-usage",
                cost_centers_refresh_usage,
                required_policy(
                    supports_json=True,
                    mutates_state=True,
                    long_running=True,
                ),
            ),
            (
                "ensure-cur-export",
                cost_centers_ensure_cur_export,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
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
            (
                "tags",
                cluster_tags,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
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
            ("configure-dragen", headnode_configure_dragen, REQUIRED_MUTATING_LONG_RUNNING),
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
            (
                "collect-benchmarks",
                workflow_collect_benchmarks,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
            ("stop", workflow_stop, required_policy(supports_json=True, mutates_state=True)),
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
        "tests",
        "Local and cluster prep-test helpers.",
        [
            ("pytest", tests_pytest, REQUIRED_LONG_RUNNING),
            (
                "command-catalog",
                tests_command_catalog,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
            (
                "command-catalog-performance",
                tests_command_catalog_performance,
                EXEMPT_JSON,
            ),
        ],
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
            (
                "register-dewey",
                exports_register_dewey,
                required_policy(supports_json=True, mutates_state=True),
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
    register_group_commands(
        registry,
        "analysis",
        "Analysis-root visit logging and ownership guards.",
        [
            (
                "status",
                analysis_status,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
            ("visit", analysis_visit, required_policy(supports_json=True, mutates_state=True)),
            ("guard", analysis_guard, required_policy(mutates_state=True)),
        ],
    )
    register_group_commands(
        registry,
        "command",
        "Command-family progress and artifact inspection.",
        [
            (
                "sample-stats",
                command_sample_stats,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
        ],
    )
    register_group_commands(
        registry,
        "analysis/lock",
        "Analysis-root write-lock helpers.",
        [
            ("status", analysis_lock_status, required_policy(supports_json=True)),
            (
                "acquire",
                analysis_lock_acquire,
                required_policy(supports_json=True, mutates_state=True),
            ),
            (
                "release",
                analysis_lock_release,
                required_policy(supports_json=True, mutates_state=True),
            ),
            (
                "heartbeat",
                analysis_lock_heartbeat,
                required_policy(supports_json=True, mutates_state=True),
            ),
            (
                "takeover",
                analysis_lock_takeover,
                required_policy(supports_json=True, mutates_state=True),
            ),
        ],
    )


app = create_app(spec)


def _run_cli(argv: Optional[List[str]] = None) -> int:
    """Run the CLI and preserve command callback integer return codes."""
    _reset_cli_core_runtime()
    args = list(argv if argv is not None else sys.argv[1:])
    try:
        cli_app = create_app(spec)
        result = cli_app(args, standalone_mode=False)
        return result if isinstance(result, int) else 0
    except click.exceptions.NoArgsIsHelpError:
        return 0
    except click.ClickException as exc:
        exc.show(file=sys.stderr)
        return exc.exit_code
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0
    except CliCoreYoError as exc:
        output.error(str(exc))
        return exc.exit_code
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # pragma: no cover - exercised only on unexpected failures
        if os.environ.get("CLI_CORE_YO_DEBUG") == "1":
            traceback.print_exc(file=sys.stderr)
        output.error(f"Unexpected error: {exc}")
        return 1


def main() -> None:
    raise SystemExit(_run_cli())


if __name__ == "__main__":
    main()
