"""CLI entry point for daylily-ec built on cli-core-yo v2."""

from __future__ import annotations

import base64
import binascii
import contextlib
from concurrent.futures import ThreadPoolExecutor
import csv
import functools
import hashlib
import inspect
import io
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from pathlib import Path, PurePosixPath
from time import monotonic as _monotonic
from typing import Any, List, Optional

import click
import typer
import yaml
from cli_core_yo import app as cli_core_app
from cli_core_yo import output
from cli_core_yo.app import _CliCoreRootGroup, create_app
from cli_core_yo.errors import CliCoreYoError
from cli_core_yo.runtime import _reset as _reset_cli_core_runtime
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

from daylily_ec import versioning
from daylily_ec._registry_v2 import (
    DAYLILY_EC_RUNTIME_TAG,
    EXEMPT,
    EXEMPT_JSON,
    REQUIRED_JSON,
    REQUIRED_LONG_RUNNING,
    REQUIRED_MUTATING_INTERACTIVE,
    REQUIRED_MUTATING_LONG_RUNNING,
    alphabetize_registry,
    register_group_commands,
    register_root_command,
    required_policy,
)
from daylily_ec.cli_context import (
    CONTEXT_FIELDS,
    clear_local_context,
    context_option,
    load_local_context,
    update_local_context,
)
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
ANALYSIS_MANIFEST_SNAPSHOT_SCHEMA = "dyec.analysis_manifest_snapshot.v1"
MAX_ANALYSIS_MANIFEST_SNAPSHOT_BYTES = 4 * 1024 * 1024

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
    from daylily_ec.analysis_identity import validate_analysis_segment

    try:
        validate_analysis_segment(
            analysis_id,
            field_name="analysis_id",
        )
        validate_analysis_segment(
            executing_entity,
            field_name="executing_entity",
        )
        if export_trigger not in EXPORT_TRIGGERS:
            raise ValueError("export_trigger must be one of: " + ", ".join(sorted(EXPORT_TRIGGERS)))
        if export_destination_s3_uri or export_trigger != "none" or delete_on_export_success:
            raise ValueError(
                "workflow launch does not embed export in the DayOA controller; after a "
                "successful controller exit, run the catalog DYEC export visit and DRA commands"
            )
        return None
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


def _resolve_cost_center_option(cost_center: Optional[str]) -> Optional[str]:
    """Validate an explicit Slurm cost-center value without inferring one."""

    if cost_center is None:
        return None
    try:
        from daylily_ec.aws.cost_centers import CostCenterError, validate_cost_center_name

        return validate_cost_center_name(cost_center)
    except CostCenterError as exc:
        raise typer.BadParameter(str(exc), param_hint="--cost-center") from exc


def _dayec_info_hook() -> list[tuple[str, str]]:
    from daylily_ec.repositories import load_repository_catalog

    catalog = load_repository_catalog()
    dayoa = catalog.repositories["daylily-omics-analysis"]
    return [
        ("Pinned DayOA Version", dayoa.default_ref),
        ("Project Root", str(Path(__file__).resolve().parents[1])),
    ]


def _install_dayec_version_provider() -> None:
    original_get_dist_version = cli_core_app._get_dist_version

    def _get_dist_version(dist_name: str) -> str:
        if dist_name == versioning.DIST_NAME:
            return versioning.get_version()
        return original_get_dist_version(dist_name)

    cli_core_app._get_dist_version = _get_dist_version


_install_dayec_version_provider()


def _show_dayec_version(value: bool) -> bool:
    if value:
        typer.echo(f"Daylily Ephemeral Cluster {versioning.get_version()}")
        raise typer.Exit()
    return value


def _show_dayec_verbose(value: bool) -> bool:
    """Emit project-local DYEC invocation details before the subcommand."""

    if not value:
        return value
    context = load_local_context()
    project_path = Path(__file__).resolve().parents[1]
    executable = Path(sys.argv[0]).resolve()
    click.echo("DYEC verbose:", err=True)
    click.echo(f"  PWD: {Path.cwd()}", err=True)
    click.echo(f"  Project path: {project_path}", err=True)
    click.echo(f"  Executable: {executable}", err=True)
    click.echo(f"  Version: {versioning.get_version()}", err=True)
    click.echo(
        f"  Local context: {context.path} ({'present' if context.present else 'absent'})",
        err=True,
    )
    for field in CONTEXT_FIELDS:
        click.echo(f"  {field}: {context.value(field) or 'unset'}", err=True)
    return value


def _install_dayec_version_option(target_app: typer.Typer) -> None:
    root_callback = target_app.registered_callback.callback
    if root_callback is None:
        raise RuntimeError("DYEC root callback is not registered")

    signature = inspect.signature(root_callback)
    version_parameter = inspect.Parameter(
        "version",
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=bool,
        default=typer.Option(
            False,
            "--version",
            help="Show version and exit.",
            is_eager=True,
            callback=_show_dayec_version,
        ),
    )
    verbose_parameter = inspect.Parameter(
        "verbose",
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=bool,
        default=typer.Option(
            False,
            "--verbose",
            "-v",
            help="Print DYEC project-local context before running the subcommand.",
            is_eager=True,
            callback=_show_dayec_verbose,
        ),
    )
    root_callback.__signature__ = signature.replace(
        parameters=[*signature.parameters.values(), version_parameter, verbose_parameter]
    )


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


def agent_guidance() -> None:
    """Print operational guidance for agents using DYEC and DayOA safely."""

    guidance = {
        "summary": (
            "Use the installed DYEC console script as the supported control plane; "
            "do not bypass it with raw pcluster or raw Snakemake."
        ),
        "local_setup": [
            "cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster",
            "source ./activate",
            "dyec --help",
        ],
        "headnode_access": [
            "dyec headnode connect --profile <profile> --region <region> --cluster <cluster>",
            "Use the interactive ubuntu bash login shell.",
            "For DayOA controllers, use a named one-pane tmux session.",
        ],
        "cluster_lifecycle_contract": [
            "Upstream services invoke the installed dyec console script; never pcluster, daylily_ec.pcluster, or python -m daylily_ec.cli.",
            "Use dyec cluster compute-fleet with exact STOP_REQUESTED/STOPPED or START_REQUESTED/RUNNING state pairs.",
            "Use dyec slurm-accounting recover for partial post-create accounting; never rerun create against CREATE_COMPLETE.",
            "Accounting recovery binds the exact AWS profile/account, config hashes, stack, database, and user; it never selects a fallback target.",
            "Reuse its stable output directory; an ambiguous reclaimed update-submission intent fails closed and is never resubmitted.",
            "accounting_verified=true includes a bounded working sacct probe.",
        ],
        "dayoa_controller_contract": [
            "Inside tmux, run setup as separate commands: source dyoainit; dy-a <profile> <genome>; dy-r <targets> <flags>.",
            "Never invoke raw snakemake for DayOA workflow execution.",
            "Use explicit DayOA tags for new clones: day-clone -t <tag> -d <analysis-id>.",
            "A successful dry controller validates the live command in the same analysis ID/root/checkout, staged inputs, and runtime config; remove only -n for live.",
            "The -dry and -live labels may name controller sessions, never separate analysis directories. A changed command, pin, inputs, or config requires a deliberate new analysis and dry run.",
        ],
        "analysis_root_safety": [
            "Record visits before reading or touching /fsx/analysis_results/**.",
            "Acquire an analysis write lock before workflow writes, deletes, unlocks, or restarts.",
            "Never take over another owner silently; use the token takeover flow and require explicit approval.",
        ],
        "headnode_file_transfer": [
            "Upload: dyec headnode upload [-r] <local> <remote> --staging-s3-uri s3://bucket/prefix --profile <profile> --region <region> --cluster <cluster>",
            "Download: dyec headnode download [-r] <remote> <local> --staging-s3-uri s3://bucket/prefix --profile <profile> --region <region> --cluster <cluster>",
            "The S3 relay prefix is retained and printed for audit; clean it up explicitly if desired.",
        ],
        "runtime_cache_export_contract": [
            "Never copy Conda, container, Apptainer, Singularity, or Nextflow cache trees with aws s3 cp, aws s3 sync, aws s3 mv, or SDK object-copy loops.",
            "--no-follow-symlinks is not a cache-preserving alternative: it omits links instead of preserving their type and target.",
            "Use dyec runtime-cache export; it stages complete real entries with cp -a in a fresh /fsx/analysis_results/<executing-entity>/<cache-export-id>/ root and exports only through FSx DRA attach/export/detach.",
            "An existing root, active cache builder, incomplete entry, non-empty or overlapping S3 destination, or unavailable DRA must fail closed; there is no S3 CLI fallback.",
        ],
        "monitoring": [
            "Start with dyec analysis status full --analysis-root <root> --tail-lines <n> when available.",
            "Use squeue -o '%i  %P  %C  %t  %N  %c  %T  %m  %M  %D  %j' for Slurm queue truth.",
            "Queue emptiness is not success; terminal artifacts and controller rc matter.",
        ],
    }
    if _json_mode():
        output.emit_json(guidance)
        return

    output.print_text("DYEC agent guidance")
    output.print_text("===================")
    output.print_text(str(guidance["summary"]))
    for title, values in guidance.items():
        if title == "summary":
            continue
        output.print_text("")
        output.print_text(title.replace("_", " ").title())
        for item in values:
            output.print_text(f"- {item}")


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
            'case "$(whoami)" in ubuntu|ec2-user) ;; *) exit 1 ;; esac',
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


def _summarize_squeue_jobs(
    *,
    instance_id: str,
    cluster: str,
    profile: str,
    region: str,
    remote_user: str,
) -> dict[str, Any]:
    """Return a compact, machine-readable Slurm state count for one headnode."""

    from daylily_ec.aws.ssm import (
        SsmCommandFailedError,
        SsmError,
        run_shell,
        wait_for_ssm_online,
    )
    from daylily_ec.scripts.common import CommandError

    begin_marker = "__DYEC_CLUSTER_JOBS_BEGIN__"
    end_marker = "__DYEC_CLUSTER_JOBS_END__"
    try:
        wait_for_ssm_online(
            instance_id,
            region,
            profile=profile,
            timeout=120,
        )
        result = run_shell(
            instance_id,
            region,
            "\n".join(
                [
                    "set -euo pipefail",
                    "printf '%s\\n' " + shlex.quote(begin_marker),
                    "squeue --noheader -o " + shlex.quote("%i|%t"),
                    "printf '%s\\n' " + shlex.quote(end_marker),
                ]
            ),
            profile=profile,
            as_user=remote_user,
            timeout=120,
            comment=f"Summarize Slurm jobs for {cluster}",
        )
    except SsmCommandFailedError as exc:
        detail = exc.result.stderr.strip() or exc.result.stdout.strip() or str(exc)
        raise CommandError(
            f"Could not inspect Slurm jobs for cluster '{cluster}': {detail}"
        ) from exc
    except (SsmError, TimeoutError) as exc:
        raise CommandError(
            f"Could not inspect Slurm jobs for cluster '{cluster}': {exc}"
        ) from exc

    states: dict[str, int] = {}
    seen_begin = False
    seen_end = False
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if line == begin_marker:
            if seen_begin or seen_end:
                raise CommandError(
                    f"Unexpected duplicate squeue summary marker for cluster '{cluster}'."
                )
            seen_begin = True
            continue
        if line == end_marker:
            if not seen_begin or seen_end:
                raise CommandError(
                    f"Unexpected squeue summary marker order for cluster '{cluster}'."
                )
            seen_end = True
            continue
        if not seen_begin or seen_end:
            continue
        if not line:
            continue
        fields = line.split("|", maxsplit=1)
        if len(fields) != 2 or not fields[0].strip() or not fields[1].strip():
            raise CommandError(
                f"Unexpected squeue summary output for cluster '{cluster}': {raw_line!r}"
            )
        state = fields[1].strip()
        states[state] = states.get(state, 0) + 1

    if not seen_begin or not seen_end:
        raise CommandError(f"Missing squeue summary markers for cluster '{cluster}'.")

    total = sum(states.values())
    running = states.get("R", 0)
    pending = states.get("PD", 0)
    return {
        "job_query_status": "SUCCESS",
        "total_jobs": total,
        "running_jobs": running,
        "pending_jobs": pending,
        "other_jobs": total - running - pending,
        "jobs_by_state": dict(sorted(states.items())),
    }


def _emit_cluster_jobs_table(regions: list[str], rows: list[dict[str, Any]]) -> None:
    region_label = ", ".join(regions)
    if not rows:
        output.print_text(f"No clusters found in {region_label}.")
        return

    output.heading("Cluster job snapshot in %s" % region_label)
    header = "%-30s %-15s %-20s %-16s %-7s %-9s %-9s %-7s" % (
        "CLUSTER_NAME",
        "REGION",
        "STATUS",
        "JOB_QUERY",
        "TOTAL",
        "RUNNING",
        "PENDING",
        "OTHER",
    )
    sep = "%s %s %s %s %s %s %s %s" % (
        "─" * 30,
        "─" * 15,
        "─" * 20,
        "─" * 16,
        "─" * 7,
        "─" * 9,
        "─" * 9,
        "─" * 7,
    )
    output.print_text(header)
    output.print_text(sep)
    for row in rows:
        values = [
            row["total_jobs"],
            row["running_jobs"],
            row["pending_jobs"],
            row["other_jobs"],
        ]
        text_values = ["N/A" if value is None else str(value) for value in values]
        output.print_text(
            "%-30s %-15s %-20s %-16s %-7s %-9s %-9s %-7s"
            % (
                row["name"],
                row["region"],
                row["status"],
                row["job_query_status"],
                *text_values,
            )
        )


def cluster_jobs(
    regions: Optional[List[str]] = context_option(
        "aws_region",
        None,
        "--region",
        help="AWS region to query. Repeat --region once per requested region.",
        required=True,
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE env var.",
    ),
    remote_user: str = typer.Option(
        "auto",
        "--remote-user",
        help="Remote login user for read-only SSM job queries: auto, ubuntu, or ec2-user.",
    ),
) -> None:
    """Summarize Slurm job counts for every ready cluster in the given regions."""

    from daylily_ec.scripts.common import CommandError

    _warn_if_dayec_env_inactive()
    try:
        resolved_profile = _resolved_aws_profile(profile)
        requested_regions = _normalize_cluster_list_regions(regions)
        rows: list[dict[str, Any]] = []
        ready_rows: list[tuple[dict[str, Any], str, str]] = []
        for region in requested_regions:
            payload = _run_pcluster_json(
                ["pcluster", "list-clusters", "--region", region],
                profile=resolved_profile,
                region=region,
            )
            clusters = payload.get("clusters", [])
            if not isinstance(clusters, list):
                raise CommandError("pcluster list-clusters returned a non-list clusters value.")
            for item in clusters:
                if not isinstance(item, dict):
                    raise CommandError("pcluster list-clusters returned a non-object cluster entry.")
                name = str(item.get("clusterName") or "").strip()
                if not name:
                    raise CommandError(
                        "pcluster list-clusters returned a cluster entry without clusterName."
                    )
                details = _describe_cluster_payload(
                    profile=resolved_profile,
                    region=region,
                    cluster=name,
                )
                base_row = _cluster_row_from_details(name, details)
                status = str(base_row["status"])
                row: dict[str, Any] = {
                    "name": name,
                    "region": region,
                    "status": status,
                    "instance_id": base_row["instance_id"] or None,
                }
                if status not in {"CREATE_COMPLETE", "UPDATE_COMPLETE"}:
                    row.update(
                        {
                            "job_query_status": "CLUSTER_NOT_READY",
                            "total_jobs": None,
                            "running_jobs": None,
                            "pending_jobs": None,
                            "other_jobs": None,
                            "jobs_by_state": {},
                        }
                    )
                else:
                    instance_id = str(base_row["instance_id"] or "").strip()
                    if not instance_id:
                        raise CommandError(
                            f"Cluster '{name}' is {status} but has no headnode instance id."
                        )
                    ready_rows.append((row, instance_id, region))
                rows.append(row)
        with ThreadPoolExecutor(max_workers=len(ready_rows) or 1) as executor:
            futures = [
                (
                    row,
                    executor.submit(
                        _summarize_squeue_jobs,
                        instance_id=instance_id,
                        cluster=str(row["name"]),
                        profile=resolved_profile,
                        region=region,
                        remote_user=remote_user,
                    ),
                )
                for row, instance_id, region in ready_rows
            ]
            for row, future in futures:
                row.update(future.result())
    except CommandError as exc:
        _exit_headnode_error(exc)

    result = {"regions": requested_regions, "clusters": rows}
    if _json_mode():
        output.emit_json(result)
        return
    _emit_cluster_jobs_table(requested_regions, rows)


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
    region_az: Optional[str] = context_option(
        "aws_region_az",
        None,
        "--region-az",
        help=f"AWS region + availability zone. Defaults to {DEFAULT_CREATE_REGION_AZ}.",
        fallback=DEFAULT_CREATE_REGION_AZ,
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
    admin_email: Optional[str] = typer.Option(
        None,
        "--admin-email",
        help="Override the AWS Budget notification email for this create only.",
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

    local_context = load_local_context()
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
        create_slurm_accounting_if_missing=create_slurm_accounting_if_missing,
        acknowledge_slurm_accounting_create_cost=(acknowledge_slurm_accounting_create_cost),
        budget_email_override=(admin_email or "").strip() or None,
        budget_email_fallback=local_context.cluster_admin_email,
    )
    raise SystemExit(rc)


def slurm_accounting_ensure(
    region_az: Optional[str] = context_option(
        "aws_region_az",
        None,
        "--region-az",
        help="AWS region + availability zone (e.g. us-west-2b).",
        required=True,
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
    region: Optional[str] = context_option(
        "aws_region",
        None,
        "--region",
        help="AWS region containing the existing cluster.",
        required=True,
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
    privatelink_stack_name: str = typer.Option(
        "",
        "--privatelink-stack-name",
        help="Explicit healthy DayEC accounting PrivateLink bridge stack.",
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
            privatelink_stack_name=privatelink_stack_name,
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


def slurm_accounting_recover(
    cluster: str = typer.Option(
        ...,
        "--cluster",
        help="Exact existing ParallelCluster name.",
    ),
    region: Optional[str] = context_option(
        "aws_region",
        None,
        "--region",
        help="AWS region containing the exact recovery cluster.",
        required=True,
    ),
    region_az: Optional[str] = context_option(
        "aws_region_az",
        None,
        "--region-az",
        help="Exact AWS region + availability zone (for example us-west-2d).",
        required=True,
    ),
    profile: str = typer.Option(
        ...,
        "--profile",
        help="Exact AWS CLI profile for every recovery operation.",
    ),
    cluster_configuration: Path = typer.Option(
        ...,
        "--cluster-configuration",
        help="Exact persisted pre-accounting ParallelCluster YAML.",
    ),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        help="Stable directory for deterministic update config and recovery receipt files.",
    ),
    stack_name: str = typer.Option(
        ...,
        "--stack-name",
        help="Exact regional DayEC Slurm accounting stack name.",
    ),
    database_name: str = typer.Option(
        ...,
        "--database-name",
        help="Exact Slurm accounting database name.",
    ),
    db_username: str = typer.Option(
        ...,
        "--db-username",
        help="Exact Slurm accounting database user name.",
    ),
    instance_type: str = typer.Option(
        ...,
        "--instance-type",
        help="Exact accounting instance type used only if singleton creation is approved.",
    ),
    create_slurm_accounting_if_missing: bool = typer.Option(
        False,
        "--create-slurm-accounting-if-missing",
        help="Allow creation of the missing regional accounting singleton.",
    ),
    acknowledge_slurm_accounting_create_cost: bool = typer.Option(
        False,
        "--acknowledge-slurm-accounting-create-cost",
        help="Acknowledge the ongoing AWS cost of creating the accounting singleton.",
    ),
    timeout_seconds: int = typer.Option(
        5400,
        "--timeout-seconds",
        min=1,
        help="Maximum seconds for the complete recovery.",
    ),
    poll_interval_seconds: int = typer.Option(
        30,
        "--poll-interval-seconds",
        min=1,
        help="Seconds between bounded provider-state polls.",
    ),
) -> None:
    """Recover one partial accounting attach and verify working ``sacct``."""

    from daylily_ec.workflow.recover_slurm_accounting import (
        SLURM_ACCOUNTING_RECOVERY_SCHEMA,
        SlurmAccountingRecoveryError,
        recover_slurm_accounting,
    )

    _warn_if_dayec_env_inactive()
    try:
        result = recover_slurm_accounting(
            cluster_name=cluster,
            region=region,
            region_az=region_az,
            profile=profile,
            cluster_configuration=cluster_configuration,
            output_dir=output_dir,
            stack_name=stack_name,
            database_name=database_name,
            db_username=db_username,
            instance_type=instance_type,
            create_slurm_accounting_if_missing=create_slurm_accounting_if_missing,
            acknowledge_slurm_accounting_create_cost=(acknowledge_slurm_accounting_create_cost),
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )
    except SlurmAccountingRecoveryError as exc:
        _exit_versioned_contract_error(
            schema_version=SLURM_ACCOUNTING_RECOVERY_SCHEMA,
            error_code="slurm_accounting_recovery_failed",
            message=str(exc),
            stage=exc.stage,
            reason_code=exc.reason_code,
        )
    except Exception:  # noqa: BLE001
        _exit_versioned_contract_error(
            schema_version=SLURM_ACCOUNTING_RECOVERY_SCHEMA,
            error_code="internal_error",
            message="Unexpected DYEC Slurm-accounting recovery failure.",
        )

    payload = result.to_payload()
    if _json_mode():
        output.emit_json(payload)
        return

    output.heading("Slurm accounting recovery")
    output.print_text(f"Cluster:     {payload['cluster']}")
    output.print_text(f"Region/AZ:   {payload['region_az']}")
    output.print_text(f"Stack:       {payload['accounting_stack_name']}")
    output.print_text(f"Stack state: {payload['final_cluster_state']}")
    output.print_text(f"Fleet:       {payload['final_fleet_state']}")
    output.print_text(f"Config SHA:  {payload['cluster_configuration_sha256']}")
    output.print_text(f"Receipt:     {payload['recovery_receipt_path']}")
    output.success("Slurm accounting recovered and sacct verified.")


def slurm_accounting_privatelink_ensure(
    region: Optional[str] = context_option(
        "aws_region",
        None,
        "--region",
        help="AWS region containing the provider and consumer VPCs.",
        required=True,
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE.",
    ),
    provider_accounting_stack: str = typer.Option(
        ...,
        "--provider-accounting-stack",
        help="Explicit existing DayEC MariaDB accounting stack.",
    ),
    consumer_vpc_id: str = typer.Option(
        ...,
        "--consumer-vpc-id",
        help="VPC whose ParallelCluster headnodes will use the bridge.",
    ),
    consumer_endpoint_subnet_cidr: str = typer.Option(
        ...,
        "--consumer-endpoint-subnet-cidr",
        help="Unused canonical IPv4 /28 for the consumer endpoint subnet.",
    ),
    stack_name: str = typer.Option(
        "",
        "--stack-name",
        help="Explicit bridge stack name; otherwise derived from the consumer VPC ID.",
    ),
) -> None:
    """Ensure an account-restricted TCP/3306 PrivateLink accounting bridge."""
    from daylily_ec.aws.context import AWSContext
    from daylily_ec.aws.slurm_accounting_privatelink import (
        ensure_slurm_accounting_privatelink_bridge,
    )

    _warn_if_dayec_env_inactive()
    try:
        aws_ctx = AWSContext.build_region(region, profile=profile)
        bridge = ensure_slurm_accounting_privatelink_bridge(
            aws_ctx,
            provider_accounting_stack_name=provider_accounting_stack,
            consumer_vpc_id=consumer_vpc_id,
            consumer_endpoint_subnet_cidr=consumer_endpoint_subnet_cidr,
            stack_name=stack_name,
        )
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)

    payload = {
        "stack_name": bridge.stack_name,
        "status": bridge.status,
        "provider_accounting_stack_name": bridge.provider_accounting_stack_name,
        "provider_vpc_id": bridge.provider_vpc_id,
        "consumer_vpc_id": bridge.consumer_vpc_id,
        "endpoint_id": bridge.endpoint_id,
        "endpoint_service_id": bridge.endpoint_service_id,
        "endpoint_subnet_id": bridge.endpoint_subnet_id,
        "client_security_group_id": bridge.client_security_group_id,
        "accounting_instance_id": bridge.accounting_instance_id,
    }
    if _json_mode():
        output.emit_json(payload)
        return

    output.heading("Slurm accounting PrivateLink bridge")
    output.print_text(f"Stack:        {bridge.stack_name}")
    output.print_text(f"Status:       {bridge.status}")
    output.print_text(f"Provider DB:  {bridge.provider_accounting_stack_name}")
    output.print_text(f"Provider VPC: {bridge.provider_vpc_id}")
    output.print_text(f"Consumer VPC: {bridge.consumer_vpc_id}")
    output.print_text(f"Endpoint:     {bridge.endpoint_id}")
    output.print_text(f"Client SG:    {bridge.client_security_group_id}")
    output.success("PrivateLink database target is healthy on TCP 3306.")


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
    max_usage_age_hours: Optional[int] = typer.Option(
        None,
        "--max-usage-age-hours",
        help="Optional telemetry freshness threshold in hours (1-2160).",
    ),
    active_until: Optional[str] = typer.Option(
        None,
        "--active-until",
        help="Optional exclusive UTC end datetime, exactly YYYY-MM-DDTHH:MM:SSZ.",
    ),
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
) -> None:
    """Create an active cost center without synthesizing a monthly usage row."""
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
            max_usage_age_hours=max_usage_age_hours,
            active_until=active_until,
            actor_arn=aws_ctx.caller_arn,
            table_name=table_name,
        )
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)
    _emit_payload(item.to_dict(), f"Created cost center: {item.name}")


def cost_centers_edit(
    name: str = typer.Argument(..., help="Cost-center name."),
    monthly_cap_usd: Optional[str] = typer.Option(
        None, "--monthly-cap-usd", help="Monthly cap in USD."
    ),
    max_usage_age_hours: Optional[int] = typer.Option(
        None,
        "--max-usage-age-hours",
        help="Replacement telemetry freshness threshold in hours (1-2160).",
    ),
    active_until: Optional[str] = typer.Option(
        None,
        "--active-until",
        help="Replacement exclusive UTC end datetime, exactly YYYY-MM-DDTHH:MM:SSZ.",
    ),
    clear_active_until: bool = typer.Option(
        False,
        "--clear-active-until",
        help="Remove the end datetime so the active cost center has no time limit.",
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
            max_usage_age_hours=max_usage_age_hours,
            active_until=active_until,
            clear_active_until=clear_active_until,
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
    region_az: Optional[str] = context_option(
        "aws_region_az",
        None,
        "--region-az",
        help="AWS region + availability zone (e.g. us-west-2b).",
        required=True,
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
    region: Optional[str] = context_option(
        "aws_region",
        None,
        "--region",
        help="AWS region to query (e.g. us-west-2).",
        required=True,
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
    regions: Optional[List[str]] = context_option(
        "aws_region",
        None,
        "--region",
        help="AWS region to query. Repeat --region once per requested region.",
        required=True,
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
    region: Optional[str] = context_option(
        "aws_region",
        None,
        "--region",
        help="AWS region to query (e.g. us-west-2).",
        required=True,
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
    region: Optional[str] = context_option(
        "aws_region",
        None,
        "--region",
        help="AWS region to query (e.g. us-west-2).",
        required=True,
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


def cluster_compute_fleet(
    cluster: str = typer.Option(
        ...,
        "--cluster",
        help="Exact ParallelCluster name.",
    ),
    region: Optional[str] = context_option(
        "aws_region",
        None,
        "--region",
        help="AWS region containing the exact cluster.",
        required=True,
    ),
    profile: str = typer.Option(
        ...,
        "--profile",
        help="Exact AWS CLI profile for every fleet operation.",
    ),
    status: str = typer.Option(
        ...,
        "--status",
        click_type=click.Choice(
            ["STOP_REQUESTED", "START_REQUESTED"],
            case_sensitive=True,
        ),
        help="Exact compute-fleet request state.",
    ),
    wait_for: str = typer.Option(
        ...,
        "--wait-for",
        click_type=click.Choice(["STOPPED", "RUNNING"], case_sensitive=True),
        help="Exact terminal state paired with --status.",
    ),
    drain: bool = typer.Option(
        False,
        "--drain",
        help=(
            "For STOP_REQUESTED, wait for controllers/jobs to become empty naturally; "
            "never cancel or signal work."
        ),
    ),
    timeout_seconds: int = typer.Option(
        1200,
        "--timeout-seconds",
        min=1,
        help="Maximum seconds for idle proof and terminal-state wait.",
    ),
    poll_interval_seconds: int = typer.Option(
        30,
        "--poll-interval-seconds",
        min=1,
        help="Seconds between bounded idle/state polls.",
    ),
) -> None:
    """Request or reclaim one guarded compute-fleet transition."""

    from daylily_ec.workflow.compute_fleet import (
        COMPUTE_FLEET_SCHEMA,
        ComputeFleetOperationError,
        run_compute_fleet_transition,
    )

    _warn_if_dayec_env_inactive()
    try:
        result = run_compute_fleet_transition(
            cluster_name=cluster,
            region=region,
            profile=profile,
            request_status=status,
            wait_for_status=wait_for,
            drain=drain,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )
    except ComputeFleetOperationError as exc:
        _exit_versioned_contract_error(
            schema_version=COMPUTE_FLEET_SCHEMA,
            error_code="compute_fleet_operation_failed",
            message=str(exc),
        )
    except Exception:  # noqa: BLE001
        _exit_versioned_contract_error(
            schema_version=COMPUTE_FLEET_SCHEMA,
            error_code="internal_error",
            message="Unexpected DYEC compute-fleet operation failure.",
        )

    payload = result.to_payload()
    if _json_mode():
        output.emit_json(payload)
        return

    output.heading("Compute fleet transition")
    output.print_text(f"Cluster:   {payload['cluster']}")
    output.print_text(f"Region:    {payload['region']}")
    output.print_text(f"Initial:   {payload['initial_status']}")
    output.print_text(f"Final:     {payload['final_status']}")
    output.print_text(f"Submitted: {str(payload['request_submitted']).lower()}")
    output.success(f"Compute fleet reached {payload['final_status']}.")


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
    region: Optional[str] = context_option(
        "aws_region",
        None,
        "--region",
        help="AWS region to query (e.g. us-west-2).",
        required=True,
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
    region: Optional[str] = context_option(
        "aws_region",
        None,
        "--region",
        help="AWS region where the FSx filesystem lives.",
        required=True,
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
    delete_data_in_file_system: bool = typer.Option(
        False,
        "--delete-data-in-file-system",
        help=(
            "Delete the exported source data from FSx when detaching the temporary "
            "export DRA after a successful export task."
        ),
    ),
) -> None:
    """Export FSx outputs through an explicit DRA and immutable S3 receipt."""

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
            delete_data_in_file_system=delete_data_in_file_system,
        )
    )
    raise typer.Exit(rc)


def _emit_export_payload(payload: Any, *, text: str) -> None:
    if _json_mode():
        output.emit_json(payload)
        return
    typer.echo(text)


def runtime_cache_export(
    cluster_name: str = typer.Option(
        ...,
        "--cluster",
        "--cluster-name",
        help="ParallelCluster whose generation-scoped runtime caches will be saved.",
    ),
    executing_entity: str = typer.Option(
        ...,
        "--executing-entity",
        help="Owner segment for the fresh /fsx/analysis_results staging root.",
    ),
    cache_export_id: str = typer.Option(
        ...,
        "--cache-export-id",
        help="Immutable execution segment for the fresh runtime-cache staging root.",
    ),
    destination_s3_uri: str = typer.Option(
        ...,
        "--destination-s3-uri",
        help=(
            "Empty non-overlapping S3 prefix ending in "
            "<executing-entity>/<cache-export-id>/."
        ),
    ),
    region: Optional[str] = context_option(
        "aws_region",
        None,
        "--region",
        help="AWS region for the cluster and FSx.",
        required=True,
    ),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        help="New local directory for runtime_cache_export.yaml and the DRA receipt.",
    ),
    human_requestor: str = typer.Option(
        ...,
        "--human-requestor",
        help="Human requestor recorded in the analysis-root lock and visit evidence.",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE when omitted.",
    ),
    cache_user: str = typer.Option(
        "ubuntu",
        "--cache-user",
        help="Generation-scoped cache owner: ubuntu, daylily, or ec2-user.",
    ),
    stage_timeout_seconds: int = typer.Option(
        7200,
        "--stage-timeout-seconds",
        help="SSM timeout for cp -a staging on the headnode.",
    ),
    export_timeout_seconds: int = typer.Option(
        5400,
        "--export-timeout-seconds",
        help="Timeout for the FSx DRA attach, export task, and safe detach.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Render the immutable staging and DRA plan without AWS or FSx mutations.",
    ),
) -> None:
    """Save complete runtime caches to S3 exclusively through an FSx DRA."""

    from daylily_ec.runtime_cache_export import (
        RuntimeCacheExportError,
        RuntimeCacheExportOptions,
        run_runtime_cache_export,
    )

    try:
        payload = run_runtime_cache_export(
            RuntimeCacheExportOptions(
                cluster_name=cluster_name,
                executing_entity=executing_entity,
                cache_export_id=cache_export_id,
                destination_s3_uri=destination_s3_uri,
                region=region,
                profile=profile,
                output_dir=output_dir.expanduser().resolve(),
                human_requestor=human_requestor,
                cache_user=cache_user,
                stage_timeout_seconds=stage_timeout_seconds,
                export_timeout_seconds=export_timeout_seconds,
                dry_run=dry_run,
            )
        )
        _emit_export_payload(
            payload,
            text=(
                f"Runtime-cache export {payload['status']}: {payload['stage_root']}\n"
                f"Transport: {payload['transport']}\n"
                f"S3 destination: {payload['destination_s3_uri']}"
            ),
        )
    except (RuntimeCacheExportError, ValueError) as exc:
        _exit_headnode_error(exc)


def exports_attach(
    cluster_name: Optional[str] = typer.Option(None, "--cluster-name", "--cluster"),
    fsx_file_system_id: Optional[str] = typer.Option(None, "--fsx-file-system-id"),
    source_path: str = typer.Option(..., "--source-path"),
    destination_s3_uri: str = typer.Option(..., "--destination-s3-uri"),
    region: Optional[str] = context_option("aws_region", None, "--region", required=True),
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
    region: Optional[str] = context_option("aws_region", None, "--region", required=True),
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


def exports_transfer(
    cluster_name: str = typer.Option(..., "--cluster-name", "--cluster"),
    fsx_file_system_id: Optional[str] = typer.Option(None, "--fsx-file-system-id"),
    source_path: str = typer.Option(..., "--source-path"),
    destination_s3_uri: str = typer.Option(..., "--destination-s3-uri"),
    destination_analysis_id: str = typer.Option(..., "--destination-analysis-id"),
    region: Optional[str] = context_option("aws_region", None, "--region", required=True),
    profile: Optional[str] = typer.Option(None, "--profile"),
    timeout_seconds: int = typer.Option(5400, "--timeout-seconds"),
) -> None:
    """Attach, export, and detach one exact analysis directory without deletion."""

    from daylily_ec.workflow.export_data import (
        STATUS_FILENAME,
        ExportOptions,
        run_export_workflow,
    )

    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    try:
        with tempfile.TemporaryDirectory(prefix="dyec-export-transfer-") as output_dir:
            options = ExportOptions(
                cluster_name=cluster_name,
                fsx_file_system_id=fsx_file_system_id,
                source_path=source_path,
                destination_s3_uri=destination_s3_uri,
                destination_analysis_id=destination_analysis_id,
                region=region,
                profile=profile,
                output_dir=Path(output_dir),
                wait=True,
                timeout_seconds=timeout_seconds,
                delete_data_in_file_system=False,
            )
            with (
                contextlib.redirect_stdout(captured_stdout),
                contextlib.redirect_stderr(captured_stderr),
            ):
                rc = run_export_workflow(options)
            status_path = options.output_dir / STATUS_FILENAME
            if not status_path.is_file():
                raise RuntimeError("DYEC export transfer did not write its status receipt")
            receipt = yaml.safe_load(status_path.read_text(encoding="utf-8"))
            if not isinstance(receipt, dict) or not isinstance(
                receipt.get("fsx_export"), dict
            ):
                raise RuntimeError("DYEC export transfer status receipt is invalid")
            payload = dict(receipt["fsx_export"])
            if rc != 0 or payload.get("status") != "success":
                detail = (
                    payload.get("failure_details")
                    or captured_stderr.getvalue()
                    or captured_stdout.getvalue()
                )
                raise RuntimeError(f"DYEC export transfer failed: {detail}")
            if payload.get("delete_data_in_file_system") is not False:
                raise RuntimeError("DYEC export transfer must preserve FSx data")
            if payload.get("detached") is not True:
                raise RuntimeError(
                    "DYEC export transfer did not detach its temporary DRA"
                )
            _emit_export_payload(
                payload,
                text=(
                    f"Export transfer complete: {payload['task_id']}\n"
                    f"S3 destination: {payload['destination_s3_uri']}"
                ),
            )
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def exports_cleanup(
    cluster_name: str = typer.Option(..., "--cluster-name", "--cluster"),
    fsx_file_system_id: Optional[str] = typer.Option(None, "--fsx-file-system-id"),
    source_path: str = typer.Option(..., "--source-path"),
    destination_s3_uri: str = typer.Option(..., "--destination-s3-uri"),
    destination_analysis_id: str = typer.Option(..., "--destination-analysis-id"),
    region: Optional[str] = context_option("aws_region", None, "--region", required=True),
    profile: Optional[str] = typer.Option(None, "--profile"),
    timeout_seconds: int = typer.Option(5400, "--timeout-seconds"),
    confirm_fsx_delete: bool = typer.Option(
        False,
        "--confirm-fsx-delete",
        help=(
            "Confirm deletion of the exact /fsx/analysis_results/<owner>/<execution>/ "
            "directory after durable export and registration receipts."
        ),
    ),
) -> None:
    """Delete one exact exported analysis directory from FSx, never from S3."""

    from daylily_ec.workflow.export_data import cleanup_exported_analysis

    if not confirm_fsx_delete:
        raise typer.BadParameter(
            "--confirm-fsx-delete is required for exact post-receipt FSx cleanup",
            param_hint="--confirm-fsx-delete",
        )
    try:
        payload = cleanup_exported_analysis(
            cluster_name=cluster_name,
            fsx_file_system_id=fsx_file_system_id,
            source_path=source_path,
            destination_s3_uri=destination_s3_uri,
            destination_analysis_id=destination_analysis_id,
            region=region,
            profile=profile,
            timeout_seconds=timeout_seconds,
        )
        _emit_export_payload(
            payload,
            text=(
                f"FSx analysis cleanup complete: {payload['headnode_path']}\n"
                f"Association: {payload['association_id']}\n"
                "S3 objects preserved"
            ),
        )
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def exports_detach(
    association_id: str = typer.Option(..., "--association-id"),
    region: Optional[str] = context_option("aws_region", None, "--region", required=True),
    profile: Optional[str] = typer.Option(None, "--profile"),
    wait: bool = typer.Option(True, "--wait/--no-wait"),
    timeout_seconds: int = typer.Option(900, "--timeout-seconds"),
    delete_data_in_file_system: bool = typer.Option(
        False,
        "--delete-data-in-file-system",
        help="Delete FSx data in the exported DRA path while detaching.",
    ),
) -> None:
    """Detach an output DRA, optionally deleting cached FSx data."""

    from daylily_ec.workflow.export_data import detach_export_dra

    try:
        payload = detach_export_dra(
            association_id=association_id,
            region=region,
            profile=profile,
            wait=wait,
            timeout_seconds=timeout_seconds,
            delete_data_in_file_system=delete_data_in_file_system,
        )
        _emit_export_payload(
            payload,
            text=(
                f"Export DRA detached: {association_id}\n"
                f"Lifecycle: {payload['detach_lifecycle']}\n"
                f"DeleteDataInFileSystem: {str(delete_data_in_file_system).lower()}"
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


def set_vars(
    aws_profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="Set the project-local AWS profile; a blank value clears it.",
    ),
    aws_region: Optional[str] = typer.Option(
        None,
        "--region",
        help="Set the project-local AWS region; a blank value clears it.",
    ),
    aws_region_az: Optional[str] = typer.Option(
        None,
        "--region-az",
        help="Set the project-local AWS region and availability zone; a blank value clears it.",
    ),
    cluster_admin_email: Optional[str] = typer.Option(
        None,
        "--cluster-admin-email",
        help="Set the project-local AWS Budget notification email; a blank value clears it.",
    ),
) -> None:
    """Update supplied fields in $PWD/.dyec.config.yaml only."""

    supplied = {
        field: value
        for field, value in {
            "aws_profile": aws_profile,
            "aws_region": aws_region,
            "aws_region_az": aws_region_az,
            "cluster_admin_email": cluster_admin_email,
        }.items()
        if value is not None
    }
    if not supplied:
        raise click.UsageError(
            "set-vars requires at least one of --profile, --region, --region-az, "
            "or --cluster-admin-email."
        )
    context, affected, present = update_local_context(updates=supplied)
    action = "Updated" if present else "Cleared"
    typer.echo(f"{action} {', '.join(affected)} in {context.path}")


def unset_vars(
    clear_profile: bool = typer.Option(False, "--profile", help="Clear aws_profile."),
    clear_region: bool = typer.Option(False, "--region", help="Clear aws_region."),
    clear_region_az: bool = typer.Option(
        False,
        "--region-az",
        help="Clear aws_region_az.",
    ),
    clear_cluster_admin_email: bool = typer.Option(
        False,
        "--cluster-admin-email",
        help="Clear cluster_admin_email.",
    ),
) -> None:
    """Clear selected project-local context fields, or all fields by default."""

    selected = tuple(
        field
        for field, enabled in (
            ("aws_profile", clear_profile),
            ("aws_region", clear_region),
            ("aws_region_az", clear_region_az),
            ("cluster_admin_email", clear_cluster_admin_email),
        )
        if enabled
    )
    context, affected, present = clear_local_context(fields=selected)
    if present:
        typer.echo(f"Cleared {', '.join(affected)} in {context.path}")
    else:
        typer.echo(f"Cleared {', '.join(affected)}; removed empty {context.path}")


def aws_budget_set_limit(
    name: str = typer.Argument(
        ..., help="Existing AWS Budget name (cluster name for DYEC clusters)."
    ),
    monthly_cap_usd: str = typer.Option(
        ..., "--monthly-cap-usd", help="Replacement monthly USD cap."
    ),
    expected_current_monthly_cap_usd: str = typer.Option(
        ...,
        "--expected-current-monthly-cap-usd",
        help="Required current monthly USD cap; mismatch fails before mutation.",
    ),
    profile: Optional[str] = context_option(
        "aws_profile",
        None,
        "--profile",
        help="AWS CLI profile.",
        required=True,
    ),
    region: Optional[str] = context_option(
        "aws_region",
        None,
        "--region",
        help="AWS Budgets home region.",
        required=True,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate the exact old/new cap contract without updating AWS.",
    ),
) -> None:
    """Replace one fixed monthly USD AWS Budget limit with exact old-cap proof."""

    from daylily_ec.aws.budgets import update_budget_limit
    from daylily_ec.aws.context import AWSContext

    try:
        aws_ctx = AWSContext.build_region(str(region), profile=profile)
        result = update_budget_limit(
            aws_ctx.client("budgets"),
            aws_ctx.account_id,
            name,
            monthly_cap_usd,
            expected_current_amount=expected_current_monthly_cap_usd,
            dry_run=dry_run,
        )
    except (RuntimeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)

    payload = {
        "budget_name": result.budget_name,
        "previous_monthly_cap_usd": result.previous_amount,
        "requested_monthly_cap_usd": result.requested_amount,
        "observed_monthly_cap_usd": result.observed_amount,
        "unit": result.unit,
        "changed": result.changed,
        "dry_run": result.dry_run,
        "update_submitted": result.update_submitted,
        "region": str(region),
    }
    if _json_mode():
        output.emit_json(payload)
    else:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))


def aws_audit_api_calls(
    profile: Optional[str] = context_option(
        "aws_profile",
        None,
        "--profile",
        help="Exact AWS CLI profile to audit.",
        required=True,
    ),
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
    profile: Optional[str] = context_option(
        "aws_profile",
        None,
        "--profile",
        help="Exact AWS CLI profile to audit.",
        required=True,
    ),
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
        build_remote_spot_price_log_script,
        build_spot_cost_intervals,
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
    profile: Optional[str] = context_option(
        "aws_profile",
        None,
        "--profile",
        help="Explicit named AWS CLI profile to validate; 'default' is rejected.",
        required=True,
    ),
    region_az: Optional[str] = context_option(
        "aws_region_az",
        None,
        "--region-az",
        help="Target AWS availability zone, e.g. us-west-2b.",
        required=True,
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
    profile: Optional[str] = context_option(
        "aws_profile",
        None,
        "--profile",
        help="Explicit named AWS CLI profile to validate; 'default' is rejected.",
        required=True,
    ),
    region_az: Optional[str] = context_option(
        "aws_region_az",
        None,
        "--region-az",
        help="Target AWS availability zone, e.g. us-west-2b.",
        required=True,
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
    profile: Optional[str] = context_option(
        "aws_profile",
        None,
        "--profile",
        help="Explicit named AWS CLI profile to validate; 'default' is rejected.",
        required=True,
    ),
    region_az: Optional[str] = context_option(
        "aws_region_az",
        None,
        "--region-az",
        help="Target AWS availability zone, e.g. us-west-2b.",
        required=True,
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


def _exit_versioned_contract_error(
    *,
    schema_version: str,
    error_code: str,
    message: str,
    stage: str | None = None,
    reason_code: str | None = None,
) -> None:
    """Exit one public JSON contract without leaking raw provider diagnostics."""

    if _json_mode():
        payload = {
            "schema_version": schema_version,
            "ok": False,
            "error_code": error_code,
            "error": message,
        }
        if stage is not None and reason_code is not None:
            payload["stage"] = stage
            payload["reason_code"] = reason_code
        output.emit_json(payload)
    else:
        output.error(message)
    raise typer.Exit(1)


def _exit_workflow_ssm_failure(exc) -> None:
    """Surface the remote workflow probe's diagnostics, not only the SSM wrapper RC."""

    payload = {
        "ok": False,
        "instance_id": exc.result.instance_id,
        "ssm_command_id": exc.result.command_id,
        "status": exc.result.status,
        "response_code": exc.result.response_code,
        "stdout": exc.result.stdout,
        "stderr": exc.result.stderr,
        "error": str(exc),
    }
    if _json_mode():
        output.emit_json(payload)
    else:
        if exc.result.stdout.strip():
            typer.echo(exc.result.stdout.rstrip())
        if exc.result.stderr.strip():
            typer.echo(exc.result.stderr.rstrip(), err=True)
        output.error(str(exc))
    raise typer.Exit(exc.result.response_code or 1) from exc


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
    remote_user: str = typer.Option(
        "auto",
        "--remote-user",
        help="Remote login user: auto, ubuntu, or ec2-user.",
    ),
) -> None:
    """Open a cluster-appropriate bash login/interactive shell on a headnode."""

    from daylily_ec.aws.ssm import (
        SsmError,
        resolve_remote_user,
        start_session,
        wait_for_ssm_online,
    )
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
        resolved_remote_user = resolve_remote_user(
            target.instance_id,
            resolved_region,
            profile=resolved_profile,
            as_user=remote_user,
        )
        connect_cmd = (
            "aws ssm start-session "
            f"--region {resolved_region} "
            f"--target {target.instance_id} "
            "--document-name SSM-SessionManagerRunShell"
        )
        output.print_text(
            f"Opening Session Manager session as {resolved_remote_user} to {target.instance_id} "
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
                as_user=resolved_remote_user,
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


def headnode_run(
    command: str = typer.Argument(..., help="Command string to run on the headnode."),
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
    cwd: Optional[str] = typer.Option(
        None,
        "--cwd",
        help="Optional working directory on the headnode before running the command.",
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
) -> None:
    """Run one arbitrary command on the headnode and return stdout/stderr."""

    from daylily_ec.aws.ssm import (
        SsmCommandFailedError,
        SsmError,
        run_shell,
        wait_for_ssm_online,
    )
    from daylily_ec.scripts.common import CommandError

    _warn_if_dayec_env_inactive()
    try:
        if not command.strip():
            raise CommandError("command must not be blank")
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
        script_lines = ["set -euo pipefail"]
        if cwd:
            script_lines.append(f"cd {shlex.quote(cwd)}")
        script_lines.append(command)
        result = run_shell(
            target.instance_id,
            resolved_region,
            "\n".join(script_lines),
            profile=resolved_profile,
            as_user=remote_user,
            timeout=timeout,
            comment="DYEC headnode run",
        )
        payload = {
            "ok": True,
            "cluster": resolved_cluster,
            "region": resolved_region,
            "instance_id": target.instance_id,
            "ssm_command_id": result.command_id,
            "response_code": result.response_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        if _json_mode():
            output.emit_json(payload)
            return
        if result.stdout:
            typer.echo(result.stdout.rstrip())
        if result.stderr:
            typer.echo(result.stderr.rstrip(), err=True)
    except SsmCommandFailedError as exc:
        payload = {
            "ok": False,
            "instance_id": exc.result.instance_id,
            "ssm_command_id": exc.result.command_id,
            "status": exc.result.status,
            "response_code": exc.result.response_code,
            "stdout": exc.result.stdout,
            "stderr": exc.result.stderr,
            "error": str(exc),
        }
        if _json_mode():
            output.emit_json(payload)
        else:
            if exc.result.stdout:
                typer.echo(exc.result.stdout.rstrip())
            if exc.result.stderr:
                typer.echo(exc.result.stderr.rstrip(), err=True)
            output.error(str(exc))
        raise typer.Exit(exc.result.response_code or 1) from exc
    except (CommandError, SsmError, TimeoutError) as exc:
        _exit_headnode_error(exc)


def _run_headnode_semantic_script(
    *,
    profile: Optional[str],
    region: Optional[str],
    cluster: Optional[str],
    script: str,
    parser,
    comment: str,
    timeout: int = 120,
) -> dict[str, Any]:
    from daylily_ec.aws.ssm import SsmCommandFailedError, SsmError, run_shell, wait_for_ssm_online
    from daylily_ec.scripts.common import CommandError

    try:
        if isinstance(timeout, bool) or timeout < 1:
            raise ValueError("timeout must be a positive integer")
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
        try:
            result = run_shell(
                target.instance_id,
                resolved_region,
                script,
                profile=resolved_profile,
                as_user="ubuntu",
                timeout=timeout,
                comment=comment,
            )
        except SsmCommandFailedError as exc:
            payload = parser(exc.result.stdout)
            error = payload.get("error") if isinstance(payload, dict) else None
            raise CommandError(
                f"Semantic headnode command failed: {error or exc}"
            ) from exc
        payload = parser(result.stdout)
        if not isinstance(payload, dict):
            raise ValueError("semantic headnode parser must return a JSON object")
        if payload.get("ok") is False:
            raise CommandError(
                f"Semantic headnode command failed: {payload.get('error') or 'remote probe failed'}"
            )
        return {
            **payload,
            "cluster": resolved_cluster,
            "region": resolved_region,
            "instance_id": target.instance_id,
            "ssm_command_id": result.command_id,
        }
    except (CommandError, SsmError, TimeoutError, ValueError, RuntimeError):
        raise


def _emit_headnode_payload(payload: dict[str, Any]) -> None:
    if _json_mode():
        output.emit_json(payload)
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


_SEMANTIC_OPERATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


def _semantic_operation_id(value: str) -> str:
    resolved = str(value or "")
    if not _SEMANTIC_OPERATION_ID_RE.fullmatch(resolved):
        raise ValueError(
            "operation_id must be 1-64 characters using only letters, numbers, '.', '_', ':', or '-'"
        )
    return resolved


def headnode_system_info(
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region."),
    cluster: Optional[str] = typer.Option(None, "--cluster", "--cluster-name"),
    timeout: int = typer.Option(120, "--timeout", help="SSM command timeout in seconds."),
) -> None:
    """Return bounded static headnode host facts as JSON."""

    from daylily_ec.headnode_observability import (
        build_system_info_script,
        parse_system_info_output,
    )

    _warn_if_dayec_env_inactive()
    try:
        payload = _run_headnode_semantic_script(
            profile=profile,
            region=region,
            cluster=cluster,
            script=build_system_info_script(),
            parser=parse_system_info_output,
            comment="DYEC headnode system info",
            timeout=timeout,
        )
        _emit_headnode_payload(payload)
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def headnode_fsx_usage(
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region."),
    cluster: Optional[str] = typer.Option(None, "--cluster", "--cluster-name"),
    timeout: int = typer.Option(120, "--timeout", help="SSM command timeout in seconds."),
) -> None:
    """Return bounded `df -Pk /fsx` facts as JSON."""

    from daylily_ec.headnode_observability import (
        build_fsx_usage_script,
        parse_fsx_usage_output,
    )

    _warn_if_dayec_env_inactive()
    try:
        payload = _run_headnode_semantic_script(
            profile=profile,
            region=region,
            cluster=cluster,
            script=build_fsx_usage_script(),
            parser=parse_fsx_usage_output,
            comment="DYEC headnode FSx usage",
            timeout=timeout,
        )
        _emit_headnode_payload(payload)
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def headnode_analysis_roots(
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region."),
    cluster: Optional[str] = typer.Option(None, "--cluster", "--cluster-name"),
    mode: str = typer.Option(
        "direct",
        "--mode",
        help="Discovery mode: direct or recursive-dayoa.",
    ),
    max_results: int = typer.Option(200, "--max-results", help="Maximum analyses returned."),
    max_depth: int = typer.Option(8, "--max-depth", help="Recursive search depth."),
    max_scanned_entries: int = typer.Option(
        10000,
        "--max-scanned-entries",
        help="Maximum filesystem entries inspected.",
    ),
    timeout: int = typer.Option(300, "--timeout", help="SSM command timeout in seconds."),
) -> None:
    """Discover DayOA analysis roots under /fsx/analysis_results with bounded traversal."""

    from daylily_ec.headnode_observability import (
        build_analysis_discovery_script,
        parse_analysis_discovery_output,
    )

    _warn_if_dayec_env_inactive()
    try:
        payload = _run_headnode_semantic_script(
            profile=profile,
            region=region,
            cluster=cluster,
            script=build_analysis_discovery_script(
                mode,
                max_results=max_results,
                max_depth=max_depth,
                max_scanned_entries=max_scanned_entries,
            ),
            parser=parse_analysis_discovery_output,
            comment="DYEC headnode analysis discovery",
            timeout=timeout,
        )
        _emit_headnode_payload(payload)
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def headnode_dayoa_controllers(
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region."),
    cluster: Optional[str] = typer.Option(None, "--cluster", "--cluster-name"),
    max_controllers: int = typer.Option(20, "--max-controllers"),
    max_tmux_panes: int = typer.Option(40, "--max-tmux-panes"),
    max_slurm_jobs: int = typer.Option(100, "--max-slurm-jobs"),
    timeout: int = typer.Option(180, "--timeout", help="SSM command timeout in seconds."),
) -> None:
    """Inventory DayOA controllers, tmux panes, and Slurm jobs without exposing command lines."""

    from daylily_ec.headnode_control import (
        build_controller_inventory_script,
        parse_controller_inventory_output,
    )

    _warn_if_dayec_env_inactive()
    try:
        payload = _run_headnode_semantic_script(
            profile=profile,
            region=region,
            cluster=cluster,
            script=build_controller_inventory_script(
                max_controllers=max_controllers,
                max_tmux_panes=max_tmux_panes,
                max_slurm_jobs=max_slurm_jobs,
            ),
            parser=parse_controller_inventory_output,
            comment="DYEC headnode controller inventory",
            timeout=timeout,
        )
        _emit_headnode_payload(payload)
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def headnode_dayoa_controller_action(
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region."),
    cluster: Optional[str] = typer.Option(None, "--cluster", "--cluster-name"),
    pid: str = typer.Option(..., "--pid", help="Controller process PID."),
    confirm_pid: str = typer.Option(
        ...,
        "--confirm-pid",
        help="Must exactly match --pid.",
    ),
    analysis_root: str = typer.Option(
        ...,
        "--analysis-root",
        help="Exact /fsx/analysis_results/<owner>/<analysis> root for the controller.",
    ),
    action: str = typer.Option(..., "--action", help="stop, restart, or kill."),
    operation_id: str = typer.Option(
        ..., "--operation-id", help="Unique caller operation identifier."
    ),
    timeout: int = typer.Option(120, "--timeout", help="SSM command timeout in seconds."),
) -> None:
    """Signal one validated DayOA controller process by exact PID and analysis root."""

    from daylily_ec.headnode_control import (
        build_controller_action_script,
        parse_controller_action_output,
    )

    _warn_if_dayec_env_inactive()
    try:
        resolved_operation_id = _semantic_operation_id(operation_id)
        payload = _run_headnode_semantic_script(
            profile=profile,
            region=region,
            cluster=cluster,
            script=build_controller_action_script(
                pid=pid,
                confirm_pid=confirm_pid,
                expected_analysis_root=analysis_root,
                action=action,
            ),
            parser=parse_controller_action_output,
            comment=f"DYEC headnode controller {action} ({resolved_operation_id})",
            timeout=timeout,
        )
        payload["operation_id"] = resolved_operation_id
        _emit_headnode_payload(payload)
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def headnode_slurm_job_action(
    job_ids: List[str] = typer.Option(
        ..., "--job-id", help="Exact Slurm job ID; repeat for multiple jobs."
    ),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region."),
    cluster: Optional[str] = typer.Option(None, "--cluster", "--cluster-name"),
    action: str = typer.Option(..., "--action", help="suspend, resume, or cancel."),
    timeout: int = typer.Option(120, "--timeout", help="SSM command timeout in seconds."),
) -> None:
    """Run an explicit Slurm job action against listed job IDs only."""

    from daylily_ec.headnode_control import (
        build_slurm_job_action_script,
        parse_slurm_job_action_output,
    )

    _warn_if_dayec_env_inactive()
    try:
        payload = _run_headnode_semantic_script(
            profile=profile,
            region=region,
            cluster=cluster,
            script=build_slurm_job_action_script(action=action, job_ids=job_ids),
            parser=parse_slurm_job_action_output,
            comment=f"DYEC headnode Slurm job {action}",
            timeout=timeout,
        )
        _emit_headnode_payload(payload)
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def headnode_slurm_drain(
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region."),
    cluster: Optional[str] = typer.Option(None, "--cluster", "--cluster-name"),
    confirm_cluster: str = typer.Option(
        ...,
        "--confirm-cluster",
        help="Must exactly match the resolved --cluster.",
    ),
    reason: str = typer.Option(..., "--reason", help="Reason recorded for drain."),
    operation_id: str = typer.Option(..., "--operation-id", help="Operator-provided action id."),
    timeout: int = typer.Option(120, "--timeout", help="SSM command timeout in seconds."),
) -> None:
    """Drain all Slurm nodes with exact cluster confirmation; never cancel jobs."""

    from daylily_ec.headnode_control import (
        build_slurm_all_node_state_script,
        parse_slurm_all_node_state_output,
    )

    _warn_if_dayec_env_inactive()
    try:
        resolved_operation_id = _semantic_operation_id(operation_id)
        resolved_profile, resolved_region, resolved_cluster = _resolve_headnode_cli_selection(
            profile=profile,
            region=region,
            cluster=cluster,
        )
        script = build_slurm_all_node_state_script(
            action="drain",
            cluster=resolved_cluster,
            confirm_cluster=confirm_cluster,
            reason=reason,
            operation_id=resolved_operation_id,
        )
        payload = _run_headnode_semantic_script(
            profile=resolved_profile,
            region=resolved_region,
            cluster=resolved_cluster,
            script=script,
            parser=parse_slurm_all_node_state_output,
            timeout=timeout,
            comment=f"DYEC Slurm all-node drain ({resolved_operation_id})",
        )
        _emit_headnode_payload(payload)
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def _normalize_staging_s3_uri(value: str) -> str:
    cleaned = str(value or "").strip().rstrip("/")
    if not cleaned.startswith("s3://"):
        raise ValueError("--staging-s3-uri must be an s3:// URI.")
    bucket_and_key = cleaned[len("s3://") :]
    if not bucket_and_key or "/" not in bucket_and_key:
        raise ValueError("--staging-s3-uri must include a bucket and prefix.")
    return cleaned


def _headnode_transfer_prefix(*, staging_s3_uri: str, cluster: str) -> str:
    safe_cluster = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in cluster)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return (
        f"{_normalize_staging_s3_uri(staging_s3_uri)}/"
        f"dyec-headnode-transfer/{safe_cluster}/{stamp}-{uuid.uuid4().hex[:12]}"
    )


def _run_aws_s3_cp(args: list[str], *, profile: str, region: str) -> None:
    from daylily_ec.scripts.common import CommandError, aws_env

    try:
        proc = subprocess.run(
            ["aws", "s3", "cp", *args],
            capture_output=True,
            text=True,
            env=aws_env(profile=profile, region=region),
        )
    except FileNotFoundError as exc:
        raise CommandError("aws CLI not found on PATH.") from exc
    if proc.returncode != 0:
        raise CommandError(f"aws s3 cp failed: {_command_failure_detail(proc)}")


def headnode_upload(
    local_path: Path = typer.Argument(..., help="Local file or directory to upload."),
    remote_path: str = typer.Argument(..., help="Destination path on the headnode."),
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
    staging_s3_uri: str = typer.Option(
        ...,
        "--staging-s3-uri",
        help="Required temporary s3://bucket/prefix used as the relay between local and headnode.",
    ),
    recursive: bool = typer.Option(
        False,
        "-r",
        "--recursive",
        help="Recursively copy a directory.",
    ),
    remote_user: str = typer.Option(
        "auto",
        "--remote-user",
        help="Remote login user for SSM Run Command: auto, ubuntu, or ec2-user.",
    ),
    timeout: int = typer.Option(
        900,
        "--timeout",
        help="SSM command timeout in seconds for the headnode copy step.",
    ),
) -> None:
    """Copy a local file or directory to the headnode through an explicit S3 relay."""

    from daylily_ec.aws.ssm import (
        SsmCommandFailedError,
        SsmError,
        run_shell,
        wait_for_ssm_online,
    )
    from daylily_ec.scripts.common import CommandError

    _warn_if_dayec_env_inactive()
    try:
        source = local_path.expanduser()
        if recursive:
            if not source.is_dir():
                raise CommandError(f"Recursive upload source is not a directory: {source}")
        elif not source.is_file():
            raise CommandError(f"Upload source is not a regular file: {source}")

        resolved_profile, resolved_region, resolved_cluster, target = _resolve_headnode_cli_target(
            profile=profile,
            region=region,
            cluster=cluster,
        )
        transfer_prefix = _headnode_transfer_prefix(
            staging_s3_uri=staging_s3_uri,
            cluster=resolved_cluster,
        )
        if recursive:
            relay_source = transfer_prefix + "/"
            _run_aws_s3_cp(
                ["--recursive", str(source), relay_source],
                profile=resolved_profile,
                region=resolved_region,
            )
            remote_script = "\n".join(
                [
                    "set -euo pipefail",
                    f"mkdir -p {shlex.quote(remote_path)}",
                    f"aws s3 cp --recursive {shlex.quote(relay_source)} {shlex.quote(remote_path)}",
                ]
            )
        else:
            relay_source = f"{transfer_prefix}/{source.name}"
            _run_aws_s3_cp(
                [str(source), relay_source],
                profile=resolved_profile,
                region=resolved_region,
            )
            remote_script = "\n".join(
                [
                    "set -euo pipefail",
                    f"remote_path={shlex.quote(remote_path)}",
                    'if [[ "$remote_path" == */ ]]; then mkdir -p "$remote_path"; '
                    'else mkdir -p "$(dirname "$remote_path")"; fi',
                    f"aws s3 cp {shlex.quote(relay_source)} \"$remote_path\"",
                ]
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
            remote_script,
            profile=resolved_profile,
            as_user=remote_user,
            timeout=timeout,
            comment="DYEC headnode upload",
        )
    except SsmCommandFailedError as exc:
        if exc.result.stderr.strip():
            typer.echo(exc.result.stderr.rstrip(), err=True)
        _exit_headnode_error(exc)
    except (CommandError, SsmError, TimeoutError, ValueError) as exc:
        _exit_headnode_error(exc)

    payload = {
        "direction": "upload",
        "cluster": resolved_cluster,
        "region": resolved_region,
        "instance_id": target.instance_id,
        "local_path": str(source),
        "remote_path": remote_path,
        "recursive": recursive,
        "staging_s3_uri": transfer_prefix + "/",
        "ssm_command_id": result.command_id,
    }
    if _json_mode():
        output.emit_json(payload)
        return
    output.success(f"Uploaded {source} to {remote_path} on {resolved_cluster}.")
    output.print_text(f"S3 relay retained at {transfer_prefix}/")


def headnode_download(
    remote_path: str = typer.Argument(..., help="Source path on the headnode."),
    local_path: Path = typer.Argument(..., help="Local destination file or directory."),
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
    staging_s3_uri: str = typer.Option(
        ...,
        "--staging-s3-uri",
        help="Required temporary s3://bucket/prefix used as the relay between headnode and local.",
    ),
    recursive: bool = typer.Option(
        False,
        "-r",
        "--recursive",
        help="Recursively copy a directory.",
    ),
    remote_user: str = typer.Option(
        "auto",
        "--remote-user",
        help="Remote login user for SSM Run Command: auto, ubuntu, or ec2-user.",
    ),
    timeout: int = typer.Option(
        900,
        "--timeout",
        help="SSM command timeout in seconds for the headnode copy step.",
    ),
) -> None:
    """Copy a file or directory from the headnode to local storage through an S3 relay."""

    from daylily_ec.aws.ssm import (
        SsmCommandFailedError,
        SsmError,
        run_shell,
        wait_for_ssm_online,
    )
    from daylily_ec.scripts.common import CommandError

    _warn_if_dayec_env_inactive()
    try:
        resolved_profile, resolved_region, resolved_cluster, target = _resolve_headnode_cli_target(
            profile=profile,
            region=region,
            cluster=cluster,
        )
        transfer_prefix = _headnode_transfer_prefix(
            staging_s3_uri=staging_s3_uri,
            cluster=resolved_cluster,
        )
        if recursive:
            relay_source = transfer_prefix + "/"
            remote_script = "\n".join(
                [
                    "set -euo pipefail",
                    f"test -d {shlex.quote(remote_path)}",
                    f"aws s3 cp --recursive {shlex.quote(remote_path)} {shlex.quote(relay_source)}",
                ]
            )
        else:
            remote_name = PurePosixPath(remote_path).name
            if not remote_name:
                raise CommandError("Non-recursive remote path must name a file.")
            relay_source = f"{transfer_prefix}/{remote_name}"
            remote_script = "\n".join(
                [
                    "set -euo pipefail",
                    f"test -f {shlex.quote(remote_path)}",
                    f"aws s3 cp {shlex.quote(remote_path)} {shlex.quote(relay_source)}",
                ]
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
            remote_script,
            profile=resolved_profile,
            as_user=remote_user,
            timeout=timeout,
            comment="DYEC headnode download",
        )
        destination = local_path.expanduser()
        if recursive:
            destination.mkdir(parents=True, exist_ok=True)
            _run_aws_s3_cp(
                ["--recursive", relay_source, str(destination)],
                profile=resolved_profile,
                region=resolved_region,
            )
        else:
            if str(local_path).endswith(os.sep):
                destination.mkdir(parents=True, exist_ok=True)
            elif destination.parent:
                destination.parent.mkdir(parents=True, exist_ok=True)
            _run_aws_s3_cp(
                [relay_source, str(destination)],
                profile=resolved_profile,
                region=resolved_region,
            )
    except SsmCommandFailedError as exc:
        if exc.result.stderr.strip():
            typer.echo(exc.result.stderr.rstrip(), err=True)
        _exit_headnode_error(exc)
    except (CommandError, SsmError, TimeoutError, ValueError) as exc:
        _exit_headnode_error(exc)

    payload = {
        "direction": "download",
        "cluster": resolved_cluster,
        "region": resolved_region,
        "instance_id": target.instance_id,
        "remote_path": remote_path,
        "local_path": str(destination),
        "recursive": recursive,
        "staging_s3_uri": transfer_prefix + "/",
        "ssm_command_id": result.command_id,
    }
    if _json_mode():
        output.emit_json(payload)
        return
    output.success(f"Downloaded {remote_path} from {resolved_cluster} to {destination}.")
    output.print_text(f"S3 relay retained at {transfer_prefix}/")


def _configure_headnode_command(
    *,
    profile: Optional[str],
    region: Optional[str],
    cluster: Optional[str],
    repo_overrides: Optional[Path],
    state_file: Optional[Path],
    dyec_deploy_key_secret_arn: str,
    dayoa_deploy_key_secret_arn: str,
    github_token_secret_arn: str,
    remote_user: str,
    force: bool,
) -> None:
    from daylily_ec.aws.ssm import SsmError, wait_for_ssm_online
    from daylily_ec.headnode_config_inputs import resolve_headnode_deploy_key_inputs
    from daylily_ec.scripts.common import CommandError
    from daylily_ec.scripts.daylily_cfg_headnode import _load_repo_overrides
    from daylily_ec.workflow.create_cluster import (
        configure_headnode,
        resolve_configured_headnode_repo_spec,
    )

    _warn_if_dayec_env_inactive()
    github_token_arn = github_token_secret_arn.strip()
    try:
        resolved_profile, resolved_region, resolved_cluster, target = _resolve_headnode_cli_target(
            profile=profile,
            region=region,
            cluster=cluster,
        )
        deploy_key_inputs = resolve_headnode_deploy_key_inputs(
            cluster_name=resolved_cluster,
            region=resolved_region,
            state_file=state_file,
            dyec_deploy_key_secret_arn=dyec_deploy_key_secret_arn,
            dayoa_deploy_key_secret_arn=dayoa_deploy_key_secret_arn,
        )
        overrides = _load_repo_overrides(str(repo_overrides) if repo_overrides else None)
        try:
            dyec_repo_spec = resolve_configured_headnode_repo_spec(
                deploy_key_auth=True
            )
        except RuntimeError as exc:
            raise CommandError(f"Unable to resolve the running DYEC release: {exc}") from exc
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
            dyec_deploy_key_secret_arn=deploy_key_inputs.dyec_secret_arn,
            dyec_deploy_key_region=resolved_region,
            dyec_repo_url=dyec_repo_spec.url,
            dyec_repo_ref=dyec_repo_spec.ref,
            dayoa_deploy_key_secret_arn=deploy_key_inputs.dayoa_secret_arn,
            dayoa_deploy_key_region=resolved_region,
            github_token_secret_arn=github_token_arn,
            github_token_region=resolved_region if github_token_arn else "",
            repo_overrides=overrides or None,
            remote_user=remote_user,
            force=force,
        )
        if not ok:
            raise CommandError(f"Headnode configuration failed for cluster '{resolved_cluster}'.")
    except (CommandError, SsmError, TimeoutError) as exc:
        _exit_headnode_error(exc)

    if deploy_key_inputs.state_path is not None:
        output.print_text(
            "Using deploy-key references from state "
            f"{deploy_key_inputs.state_path} and config {deploy_key_inputs.config_path}."
        )
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
    state_file: Optional[Path] = typer.Option(
        None,
        "--state-file",
        help=(
            "Exact local DYEC create-state JSON to use for deploy-key references. "
            "Defaults to the newest state for --cluster."
        ),
    ),
    dyec_deploy_key_secret_arn: str = typer.Option(
        "",
        "--dyec-deploy-key-secret-arn",
        help=(
            "Optional exact Secrets Manager ARN for the DYEC deploy key. Provide this and "
            "--dayoa-deploy-key-secret-arn together only to override the state-backed default."
        ),
    ),
    dayoa_deploy_key_secret_arn: str = typer.Option(
        "",
        "--dayoa-deploy-key-secret-arn",
        help=(
            "Optional exact Secrets Manager ARN for the DayOA deploy key. Provide this and "
            "--dyec-deploy-key-secret-arn together only to override the state-backed default."
        ),
    ),
    github_token_secret_arn: str = typer.Option(
        "",
        "--github-token-secret-arn",
        help=(
            "Exact Secrets Manager ARN for the LSMC Bio GitHub token. The token must allow "
            "read/write access to the DayOA and DYEC repositories; the headnode role must "
            "already allow access to this secret."
        ),
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help=(
            "Explicitly remove the DAYOA and DAY-EC Conda environments, clean all local "
            "Conda caches, and rebuild the pinned headnode toolchain."
        ),
    ),
) -> None:
    """Configure a headnode with the same exact release as this DYEC executable."""

    _configure_headnode_command(
        profile=profile,
        region=region,
        cluster=cluster,
        repo_overrides=repo_overrides,
        state_file=state_file,
        dyec_deploy_key_secret_arn=dyec_deploy_key_secret_arn,
        dayoa_deploy_key_secret_arn=dayoa_deploy_key_secret_arn,
        github_token_secret_arn=github_token_secret_arn,
        remote_user="ubuntu",
        force=force,
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
    state_file: Optional[Path] = typer.Option(
        None,
        "--state-file",
        help=(
            "Exact local DYEC create-state JSON to use for deploy-key references. "
            "Defaults to the newest state for --cluster."
        ),
    ),
    dyec_deploy_key_secret_arn: str = typer.Option(
        "",
        "--dyec-deploy-key-secret-arn",
        help=(
            "Optional exact Secrets Manager ARN for the DYEC deploy key. Provide this and "
            "--dayoa-deploy-key-secret-arn together only to override the state-backed default."
        ),
    ),
    dayoa_deploy_key_secret_arn: str = typer.Option(
        "",
        "--dayoa-deploy-key-secret-arn",
        help=(
            "Optional exact Secrets Manager ARN for the DayOA deploy key. Provide this and "
            "--dyec-deploy-key-secret-arn together only to override the state-backed default."
        ),
    ),
    github_token_secret_arn: str = typer.Option(
        "",
        "--github-token-secret-arn",
        help=(
            "Exact Secrets Manager ARN for the LSMC Bio GitHub token. The token must allow "
            "read/write access to the DayOA and DYEC repositories; the headnode role must "
            "already allow access to this secret."
        ),
    ),
) -> None:
    """Configure a DRAGEN headnode with the same release as this DYEC executable."""

    _configure_headnode_command(
        profile=profile,
        region=region,
        cluster=cluster,
        repo_overrides=repo_overrides,
        state_file=state_file,
        dyec_deploy_key_secret_arn=dyec_deploy_key_secret_arn,
        dayoa_deploy_key_secret_arn=dayoa_deploy_key_secret_arn,
        github_token_secret_arn=github_token_secret_arn,
        remote_user="ec2-user",
        force=False,
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
        elif line.startswith("__DAYLILY_COST_CENTER__="):
            parsed["cost_center"] = line.split("=", 1)[1].strip()
    return parsed


CG_SLIM_MATERIALIZATION_MARKER = "__DYEC_CG_SLIM_MATERIALIZATION__="


def _cg_slim_materialization_script(workflow_paths: list[str]) -> str:
    """Build the bounded read-only headnode verifier for two mounted CG files."""

    return "\n".join(
        [
            "set -euo pipefail",
            "python3 - " + shlex.quote(json.dumps(workflow_paths)) + " <<'PY'",
            "import json",
            "import os",
            "import stat",
            "import sys",
            "paths = json.loads(sys.argv[1])",
            "for path in paths:",
            "    state = os.stat(path)",
            "    if not stat.S_ISREG(state.st_mode):",
            "        raise SystemExit('not a regular file: ' + path)",
            "    with open(path, 'rb') as handle:",
            "        gzip_magic = handle.read(2).hex()",
            "    if gzip_magic != '1f8b':",
            "        raise SystemExit('not a gzip stream: ' + path)",
            "    payload = {'workflow_path': path, 'size_bytes': state.st_size, 'gzip_magic': gzip_magic}",
            f"    print({CG_SLIM_MATERIALIZATION_MARKER!r} + json.dumps(payload, sort_keys=True))",
            "PY",
        ]
    )


def _parse_cg_slim_materialization(
    stdout: str, *, expected_paths: list[str]
) -> list[dict[str, object]]:
    """Parse exactly the two marker payloads emitted by the read-only verifier."""

    verified: list[dict[str, object]] = []
    for line in stdout.splitlines():
        if not line.startswith(CG_SLIM_MATERIALIZATION_MARKER):
            continue
        try:
            payload = json.loads(line[len(CG_SLIM_MATERIALIZATION_MARKER) :])
        except json.JSONDecodeError as exc:
            raise ValueError("mounted CG verifier emitted invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("mounted CG verifier payload must be an object")
        verified.append(payload)
    if [str(item.get("workflow_path") or "") for item in verified] != expected_paths:
        raise ValueError("mounted CG verifier did not attest the exact expected pair in order")
    return verified


def samples_materialize_cg_slim(
    source_manifest: Path = typer.Option(
        ...,
        "--source-manifest",
        help="Explicit one-row CG slim source table with exact S3 input URIs.",
    ),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        help="Required new local directory for the six manifests and receipts.",
    ),
    reference_s3_uri: str = typer.Option(
        ...,
        "--reference-s3-uri",
        help="Exact S3 root mounted at --reference-fsx-root.",
    ),
    reference_fsx_root: str = typer.Option(
        ...,
        "--reference-fsx-root",
        help="Exact mounted reference role root; must be /fsx/references.",
    ),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region."),
    cluster: str = typer.Option(
        ...,
        "--cluster",
        "--cluster-name",
        help="Cluster whose headnode exposes the mounted slim inputs.",
    ),
    remote_user: str = typer.Option(
        "auto",
        "--remote-user",
        help="Remote SSM login user: auto, ubuntu, or ec2-user.",
    ),
) -> None:
    """Create a materialized six-manifest receipt for an exact mounted CG slim pair."""

    from datetime import datetime, timezone

    from daylily_ec.aws.ssm import resolve_remote_user, run_shell, wait_for_ssm_online
    from daylily_ec.complete_genomics_manifest import (
        finalize_complete_genomics_slim_mounted_reference_materialization,
        generate_complete_genomics_slim_mounted_reference_six_manifest,
    )
    from daylily_ec.identity_receipts import validate as validate_identities
    from daylily_ec.manifest_set import atomic_json, load_manifest_set

    _warn_if_dayec_env_inactive()
    destination = output_dir.expanduser().resolve()
    temporary_root: Path | None = None
    try:
        if destination.exists():
            raise ValueError(
                f"refusing to overwrite existing CG slim manifest directory: {destination}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_root = Path(
            tempfile.mkdtemp(prefix=".dyec-cg-slim-materialize-", dir=str(destination.parent))
        )
        staged_bundle = temporary_root / "manifest"
        generate_complete_genomics_slim_mounted_reference_six_manifest(
            source=source_manifest.expanduser().resolve(),
            output_dir=staged_bundle,
            reference_s3_uri=reference_s3_uri,
            reference_fsx_root=reference_fsx_root,
        )
        manifests = load_manifest_set(staged_bundle)
        [sequencing_input] = manifests.rows["sequencing_inputs.tsv"]
        expected_paths = [
            sequencing_input["ILMN_R1_PATH"],
            sequencing_input["ILMN_R2_PATH"],
        ]
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
        resolved_remote_user = resolve_remote_user(
            target.instance_id,
            resolved_region,
            profile=resolved_profile,
            as_user=remote_user,
        )
        remote_result = run_shell(
            target.instance_id,
            resolved_region,
            _cg_slim_materialization_script(expected_paths),
            profile=resolved_profile,
            as_user=resolved_remote_user,
            timeout=120,
            comment="Verify mounted Complete Genomics slim inputs",
        )
        files_verified = _parse_cg_slim_materialization(
            remote_result.stdout,
            expected_paths=expected_paths,
        )
        verified_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        receipt = finalize_complete_genomics_slim_mounted_reference_materialization(
            manifest_dir=staged_bundle,
            files_verified=files_verified,
            verified_at=verified_at,
            headnode={
                "cluster": resolved_cluster,
                "region": resolved_region,
                "instance_id": target.instance_id,
                "ssm_command_id": remote_result.command_id,
                "remote_user": resolved_remote_user,
            },
        )
        identity_validation = validate_identities(staged_bundle)
        atomic_json(staged_bundle / "identity_validation_receipt.json", identity_validation)
        os.replace(staged_bundle, destination)
        temporary_root.rmdir()
        temporary_root = None
        payload = {
            "schema_version": "dyec.complete_genomics.slim_materialization.v1",
            "manifest_dir": str(destination),
            "source_manifest": str(source_manifest.expanduser().resolve()),
            "staging_receipt": receipt,
            "identity_validation": identity_validation,
        }
        if _json_mode():
            output.emit_json(payload)
        else:
            typer.echo(f"Materialized CG slim six-manifest set at {destination}")
    except Exception as exc:  # noqa: BLE001
        if temporary_root is not None:
            shutil.rmtree(temporary_root, ignore_errors=True)
        _exit_headnode_error(exc)


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
    cost_center: Optional[str] = typer.Option(
        None,
        "--cost-center",
        help="Explicit active Slurm cost center; exported as DAY_PROJECT only for job submission.",
    ),
    pass_on_budget_exceeded: bool = typer.Option(
        False,
        "--pass-on-budget-exceeded",
        help="Request warning-only handling of an exceeded cluster AWS Budget.",
    ),
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
        resolved_cost_center = _resolve_cost_center_option(cost_center)
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
        if command.input_contract == "six_manifest":
            raise CommandError(
                "dyec samples run does not infer DayOA 13 topology from a consolidated table; "
                "validate six local manifests, then use `dyec workflow launch --manifest-dir DIR "
                "--git-tag TAG`"
            )
        data_modes = detect_manifest_data_modes(analysis_path)
        incompatible = command.incompatible_modes(data_modes)
        if incompatible:
            raise CommandError(
                f"Analysis command {command.command_id} is not compatible with "
                f"manifest data mode(s): {', '.join(incompatible)}. "
                "Compatible modes: " + ", ".join(command.compatible_data_modes)
            )
        _validate_sample_command_input_requirements(analysis_path, command)
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
            cost_center=resolved_cost_center,
            dry_run=dry_run,
            skip_project_check=skip_project_check,
            export_destination_s3_uri=resolved_export_destination_s3_uri,
            export_trigger=export_trigger,
            delete_on_export_success=delete_on_export_success,
            replace_existing_analysis_dir=replace_existing_analysis_dir,
        )
        if pass_on_budget_exceeded:
            workflow_cli_argv.append("--pass-on-budget-exceeded")
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


def _run_identity_operation(operation, *, output_path: Optional[Path], **kwargs: object) -> None:
    """Execute one provider-neutral local identity operation."""

    from daylily_ec.identity_receipts import IdentityReceiptError, write_payload
    from daylily_ec.manifest_set import ManifestSetError

    try:
        payload = operation(**kwargs)
        write_payload(payload, output_path)
    except (IdentityReceiptError, ManifestSetError, OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    if _json_mode():
        output.emit_json(payload)
    else:
        output.print_text(json.dumps(payload, indent=2, sort_keys=True))
        if output_path is not None:
            output.success(f"Wrote identity evidence: {output_path.expanduser().resolve()}")


def identities_validate(
    manifest_dir: Path = typer.Option(..., "--manifest-dir", help="Exact six-manifest directory."),
    output_path: Optional[Path] = typer.Option(None, "--output", help="Optional JSON receipt path."),
) -> None:
    """Validate local six-manifest topology and identity eligibility."""

    from daylily_ec.identity_receipts import validate

    _run_identity_operation(
        validate,
        output_path=output_path,
        manifest_dir=manifest_dir,
    )


def identities_plan(
    manifest_dir: Path = typer.Option(..., "--manifest-dir", help="Exact six-manifest directory."),
    identity_receipt: Optional[Path] = typer.Option(
        None,
        "--identity-receipt",
        help="Optional local owner-issued identity receipt; no service lookup is performed.",
    ),
    output_path: Optional[Path] = typer.Option(None, "--output", help="Optional plan JSON path."),
) -> None:
    """Plan hash-bound local identity receipt application without network access."""

    from daylily_ec.identity_receipts import plan

    _run_identity_operation(
        plan,
        output_path=output_path,
        manifest_dir=manifest_dir,
        identity_receipt=identity_receipt,
    )


def identities_apply(
    manifest_dir: Path = typer.Option(..., "--manifest-dir", help="Exact source manifests."),
    plan_path: Path = typer.Option(..., "--plan", help="Hash-bound local identity plan JSON."),
    output_dir: Path = typer.Option(..., "--output-dir", help="Required empty output directory."),
) -> None:
    """Apply a verified local receipt into a new manifest directory."""

    from daylily_ec.identity_receipts import apply

    _run_identity_operation(
        apply,
        output_path=None,
        manifest_dir=manifest_dir,
        plan_path=plan_path,
        output_dir=output_dir,
    )


def identities_status(
    manifest_dir: Path = typer.Option(..., "--manifest-dir", help="Exact six-manifest directory."),
    output_path: Optional[Path] = typer.Option(None, "--output", help="Optional status JSON path."),
) -> None:
    """Report blank, test, and owner-issued local identifier counts."""

    from daylily_ec.identity_receipts import status

    _run_identity_operation(status, output_path=output_path, manifest_dir=manifest_dir)


def identities_evidence(
    manifest_dir: Path = typer.Option(..., "--manifest-dir", help="Exact six-manifest directory."),
    output_path: Path = typer.Option(..., "--output", help="Required evidence JSON path."),
) -> None:
    """Write checksumed provider-neutral identity evidence."""

    from daylily_ec.identity_receipts import evidence

    _run_identity_operation(evidence, output_path=output_path, manifest_dir=manifest_dir)


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
    manifest_dir: Optional[Path] = typer.Option(
        None,
        "--manifest-dir",
        help="Local directory containing exactly the six DayOA 13 manifests.",
    ),
    payload_staging_s3_uri: Optional[str] = typer.Option(
        None,
        "--payload-staging-s3-uri",
        help=(
            "Explicit s3://bucket/prefix relay for large local launch payloads such as "
            "six manifests. Required when manifest payloads would exceed SSM limits."
        ),
    ),
    remote_user: str = typer.Option(
        "auto",
        "--remote-user",
        help="Headnode login user for launch setup and tmux controller: auto, ubuntu, or ec2-user.",
    ),
    input_contract: str = typer.Option(
        "six_manifest",
        "--input-contract",
        help="Explicit input contract: six_manifest, run_context, or none.",
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
        help="Run the standard dyoainit plus dy-a Slurm setup before --dy-command.",
    ),
    analysis_lock: bool = typer.Option(
        True,
        "--analysis-lock/--no-analysis-lock",
        help="Acquire an analysis-root write lock for the controller before running dy-r.",
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
    git_tag: Optional[str] = typer.Option(
        None,
        "--git-tag",
        "-t",
        help="Required explicit DayOA branch or tag passed to day-clone.",
    ),
    project: Optional[str] = typer.Option(None, "--project", help="Project/budget for dyoainit."),
    cost_center: Optional[str] = typer.Option(
        None,
        "--cost-center",
        help="Explicit active Slurm cost center; exported as DAY_PROJECT only for job submission.",
    ),
    pass_on_budget_exceeded: bool = typer.Option(
        False,
        "--pass-on-budget-exceeded",
        help="Request warning-only handling of an exceeded cluster AWS Budget.",
    ),
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
    produce_analysis_artifact_manifest: Optional[str] = typer.Option(
        None,
        "--produce-analysis-artifact-manifest",
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
    reuse_existing_analysis_dir: bool = typer.Option(
        False,
        "--reuse-existing-analysis-dir",
        help=(
            "Continue an existing exact analysis root without replacing it. Requires "
            "--input-contract none and --no-input-staging; DYEC verifies and checks out "
            "the explicit --git-tag before starting the new controller."
        ),
    ),
    reuse_local_git_ref: bool = typer.Option(
        False,
        "--reuse-local-git-ref",
        help=(
            "For an existing-analysis continuation, resolve the explicit --git-tag only "
            "from the existing checkout; do not fetch from origin."
        ),
    ),
    reuse_local_git_commit: Optional[str] = typer.Option(
        None,
        "--reuse-local-git-commit",
        help=(
            "Full immutable commit required to exist in the existing checkout. Requires "
            "--reuse-existing-analysis-dir and --reuse-local-git-ref; DYEC never fetches "
            "or substitutes a revision."
        ),
    ),
    pinned_source_test_override: Optional[str] = typer.Option(
        None,
        "--pinned-source-test-override",
        help=(
            "Reasoned test-only override for one explicitly approved dirty reused checkout. "
            "Requires local ref+commit, --dry-run, and no export."
        ),
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
    if not str(git_tag or "").strip():
        raise typer.BadParameter(
            "--git-tag is required; DYEC never discovers or defaults a DayOA revision",
            param_hint="--git-tag",
        )
    if reuse_existing_analysis_dir:
        if replace_existing_analysis_dir:
            raise typer.BadParameter(
                "--reuse-existing-analysis-dir cannot be combined with "
                "--replace-existing-analysis-dir",
                param_hint="--reuse-existing-analysis-dir",
            )
        if input_contract != "none":
            raise typer.BadParameter(
                "--reuse-existing-analysis-dir requires --input-contract none",
                param_hint="--input-contract",
            )
        if input_staging:
            raise typer.BadParameter(
                "--reuse-existing-analysis-dir requires --no-input-staging",
                param_hint="--input-staging",
            )
        if any(
            (
                stage_dir,
                manifest_dir,
                run_context_file,
                specimens_file,
                samples_file,
                libraries_file,
                units_file,
            )
        ):
            raise typer.BadParameter(
                "--reuse-existing-analysis-dir cannot rewrite staging or manifest inputs; "
                "continue the exact existing analysis root",
                param_hint="--reuse-existing-analysis-dir",
            )
        if bootstrap_test_config:
            raise typer.BadParameter(
                "--reuse-existing-analysis-dir cannot bootstrap test configuration",
                param_hint="--bootstrap-test-config",
            )
    else:
        if reuse_local_git_ref:
            raise typer.BadParameter(
                "--reuse-local-git-ref requires --reuse-existing-analysis-dir",
                param_hint="--reuse-local-git-ref",
            )
        if reuse_local_git_commit is not None:
            raise typer.BadParameter(
                "--reuse-local-git-commit requires --reuse-existing-analysis-dir",
                param_hint="--reuse-local-git-commit",
            )
    if reuse_local_git_commit is not None:
        if not reuse_local_git_ref:
            raise typer.BadParameter(
                "--reuse-local-git-commit requires --reuse-local-git-ref",
                param_hint="--reuse-local-git-commit",
            )
        if re.fullmatch(r"[0-9a-f]{40}", reuse_local_git_commit) is None:
            raise typer.BadParameter(
                "--reuse-local-git-commit must be a lowercase 40-character commit SHA",
                param_hint="--reuse-local-git-commit",
            )
    if pinned_source_test_override is not None:
        pinned_source_test_override = pinned_source_test_override.strip()
        if not pinned_source_test_override:
            raise typer.BadParameter(
                "--pinned-source-test-override requires a non-empty reason",
                param_hint="--pinned-source-test-override",
            )
        if "\n" in pinned_source_test_override or "\r" in pinned_source_test_override:
            raise typer.BadParameter(
                "--pinned-source-test-override reason must be single-line",
                param_hint="--pinned-source-test-override",
            )
        if not reuse_existing_analysis_dir:
            raise typer.BadParameter(
                "--pinned-source-test-override requires --reuse-existing-analysis-dir",
                param_hint="--pinned-source-test-override",
            )
        if not reuse_local_git_ref:
            raise typer.BadParameter(
                "--pinned-source-test-override requires --reuse-local-git-ref",
                param_hint="--pinned-source-test-override",
            )
        if reuse_local_git_commit is None:
            raise typer.BadParameter(
                "--pinned-source-test-override requires --reuse-local-git-commit",
                param_hint="--pinned-source-test-override",
            )
        if not dry_run:
            raise typer.BadParameter(
                "--pinned-source-test-override requires --dry-run",
                param_hint="--pinned-source-test-override",
            )
        if dy_command is not None:
            from daylily_ec.scripts.daylily_run_omics_analysis_headnode import (
                dy_command_has_dry_run_flag,
            )

            if not dy_command_has_dry_run_flag(dy_command):
                raise typer.BadParameter(
                    "--pinned-source-test-override requires --dy-command to include -n",
                    param_hint="--dy-command",
                )
    if manifest_dir is not None:
        if input_contract != "six_manifest":
            raise typer.BadParameter(
                "--manifest-dir requires --input-contract six_manifest",
                param_hint="--manifest-dir",
            )
        if any((stage_dir, specimens_file, samples_file, libraries_file, units_file)):
            raise typer.BadParameter(
                "--manifest-dir cannot be combined with legacy staging or individual manifest options",
                param_hint="--manifest-dir",
            )
        from daylily_ec.manifest_set import ManifestSetError, load_manifest_set

        try:
            load_manifest_set(manifest_dir)
        except ManifestSetError as exc:
            raise typer.BadParameter(str(exc), param_hint="--manifest-dir") from exc
    elif input_contract == "six_manifest" and input_staging:
        raise typer.BadParameter(
            "six_manifest workflow launch requires --manifest-dir",
            param_hint="--manifest-dir",
        )
    producer_option_values: dict[str, str] = {}
    for flag, value in (
        ("--produce-analysis-artifact-manifest", produce_analysis_artifact_manifest),
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
    resolved_cost_center = _resolve_cost_center_option(cost_center)
    resolved_export_destination_s3_uri = _validate_analysis_launch_options(
        analysis_id=analysis_id,
        executing_entity=resolved_executing_entity,
        cluster=cluster,
        export_destination_s3_uri=export_destination_s3_uri,
        export_trigger=export_trigger,
        delete_on_export_success=delete_on_export_success,
    )
    resolved_session_name = session_name or analysis_id
    argv: list[str] = []
    for flag, value in (
        ("--profile", profile),
        ("--region", region),
        ("--cluster", cluster),
        ("--stage-dir", stage_dir),
        ("--manifest-dir", str(manifest_dir.expanduser()) if manifest_dir else None),
        ("--payload-staging-s3-uri", payload_staging_s3_uri),
        ("--remote-user", remote_user),
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
        ("--reuse-local-git-commit", reuse_local_git_commit),
        ("--pinned-source-test-override", pinned_source_test_override),
        ("--project", project),
        ("--cost-center", resolved_cost_center),
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
    ):
        if value is not None:
            argv.extend([flag, value])
    for flag, value in producer_option_values.items():
        argv.extend([flag, value])
    if pass_on_budget_exceeded:
        argv.append("--pass-on-budget-exceeded")
    if not input_staging:
        argv.append("--no-input-staging")
    if not default_activation:
        argv.append("--no-default-activation")
    if not analysis_lock:
        argv.append("--no-analysis-lock")
    if bootstrap_test_config:
        argv.append("--bootstrap-test-config")
    argv.append("--skip-project-check" if skip_project_check else "--strict-project-check")
    if no_containerized:
        argv.append("--no-containerized")
    if delete_on_export_success:
        argv.append("--delete-on-export-success")
    if replace_existing_analysis_dir:
        argv.append("--replace-existing-analysis-dir")
    if reuse_existing_analysis_dir:
        argv.append("--reuse-existing-analysis-dir")
    if reuse_local_git_ref:
        argv.append("--reuse-local-git-ref")
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


def _catalog_load_command(
    config: Optional[Path], command_id: str, *, dyec_version: Optional[str] = None
):
    from daylily_ec.repositories import load_repository_catalog
    from daylily_ec.scripts.common import CommandError

    catalog = load_repository_catalog(config)
    try:
        command = catalog.get_command_for_dyec_build(command_id, dyec_version)
    except KeyError as exc:
        raise CommandError(str(exc)) from exc
    return catalog, command


def _catalog_command_summary(command: Any) -> dict[str, Any]:
    return {
        "command_id": command.command_id,
        "repository": command.repository,
        "display_name": command.display_name,
        "description": command.description,
        "type": command.type,
        "validated_version": command.validated_version,
        "validation_pending": command.validation_pending,
        "validation_evidence_s3_uri_prefix": command.validation_evidence_s3_uri_prefix,
        "command_class": command.command_class,
        "input_contract": command.input_contract,
        "requires_staging": command.requires_staging,
        "requires_run_mount": command.requires_run_mount,
        "test_data_profile": command.test_data_profile,
        "compatible_platforms": list(command.compatible_platforms),
        "compatible_cluster_types": list(command.compatible_cluster_types),
        "compatible_data_modes": list(command.compatible_data_modes),
        "git_tag": command.git_tag,
        "genome": command.genome,
        "day_profile": command.day_profile,
        "jobs": command.jobs,
        "dy_command": command.dy_command,
        "dryrun_dy_command": command.dryrun_dy_command,
    }


def _catalog_validate_explicit_inputs(
    command: Any,
    *,
    stage_dir: Optional[str],
    manifest_dir: Optional[str],
    run_context_file: Optional[str],
    specimens_file: Optional[str],
    samples_file: Optional[str],
    libraries_file: Optional[str],
    units_file: Optional[str],
    allow_stage_discovery: bool,
    require_staging_receipt: bool = False,
) -> None:
    from daylily_ec.scripts.common import CommandError

    if allow_stage_discovery and command.input_contract not in {
        "sample_manifest",
        "sample_manifest_v12",
    }:
        raise CommandError("--allow-stage-discovery is only valid for sample manifest commands")
    if command.input_contract == "sample_manifest_v12" and not allow_stage_discovery:
        if not stage_dir and not (specimens_file and samples_file and libraries_file):
            raise CommandError(
                f"Catalog command {command.command_id} requires --stage-dir or all of "
                "--specimens-file, --samples-file, and --libraries-file. "
                "Use `dyec samples run` when the source table still needs staging."
            )
    elif command.input_contract == "sample_manifest" and not allow_stage_discovery:
        if not stage_dir and not (samples_file and units_file):
            raise CommandError(
                f"Catalog command {command.command_id} requires --stage-dir or both "
                "--samples-file and --units-file. Use `dyec samples run` when the source "
                "table still needs staging."
            )
    elif command.input_contract == "six_manifest":
        if not manifest_dir:
            raise CommandError(f"Catalog command {command.command_id} requires --manifest-dir.")
        if require_staging_receipt and command.staging_receipt_required:
            receipt_path = Path(manifest_dir) / "staging_receipt.json"
            if not receipt_path.is_file():
                raise CommandError(
                    f"Catalog command {command.command_id} requires a materialized staging receipt: "
                    f"{receipt_path}"
                )
            try:
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise CommandError(f"Invalid staging receipt {receipt_path}: {exc}") from exc
            if receipt.get("state") != "materialized":
                raise CommandError(
                    f"Catalog command {command.command_id} requires staging_receipt.json state "
                    "'materialized' before workflow launch."
                )
    elif command.input_contract == "run_context":
        if not run_context_file:
            raise CommandError(f"Catalog command {command.command_id} requires --run-context-file.")
    elif command.input_contract == "none":
        unexpected = [
            name
            for name, value in (
                ("--stage-dir", stage_dir),
                ("--manifest-dir", manifest_dir),
                ("--run-context-file", run_context_file),
                ("--specimens-file", specimens_file),
                ("--samples-file", samples_file),
                ("--libraries-file", libraries_file),
                ("--units-file", units_file),
            )
            if value
        ]
        if unexpected:
            raise CommandError(
                f"Catalog utility command {command.command_id} does not accept input files: "
                + ", ".join(unexpected)
            )


_DY_CONFIG_OVERRIDE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*=.*$")


def _normalize_dy_config_overrides(values: Optional[list[str]]) -> list[str]:
    from daylily_ec.scripts.common import CommandError

    normalized: list[str] = []
    for raw in values or []:
        value = str(raw or "").strip()
        if not value:
            continue
        if not _DY_CONFIG_OVERRIDE_RE.fullmatch(value):
            raise CommandError(
                "--dy-config values must be explicit Snakemake config assignments like key=value"
            )
        normalized.append(value)
    return normalized


def _append_dy_config_overrides(workflow_argv: list[str], values: Optional[list[str]]) -> list[str]:
    overrides = _normalize_dy_config_overrides(values)
    if not overrides:
        return []
    try:
        dy_command_index = workflow_argv.index("--dy-command") + 1
    except ValueError as exc:
        from daylily_ec.scripts.common import CommandError

        raise CommandError("workflow argv does not contain --dy-command") from exc
    dy_command = str(workflow_argv[dy_command_index]).strip()
    tokens = shlex.split(dy_command)
    rewritten: list[str] = []
    config_values: list[str] = []
    first_config_index: int | None = None
    token_index = 0
    while token_index < len(tokens):
        token = tokens[token_index]
        if token == "--config":
            if first_config_index is None:
                first_config_index = len(rewritten)
            token_index += 1
            while token_index < len(tokens) and not tokens[token_index].startswith("-"):
                config_values.append(tokens[token_index])
                token_index += 1
            continue
        rewritten.append(token)
        token_index += 1
    insert_at = first_config_index if first_config_index is not None else len(rewritten)
    rewritten[insert_at:insert_at] = ["--config", *config_values, *overrides]
    workflow_argv[dy_command_index] = shlex.join(rewritten)
    return overrides


def _catalog_render_payload(
    *,
    config: Optional[Path],
    command_id: str,
    dyec_version: Optional[str],
    analysis_id: str,
    executing_entity: Optional[str],
    profile: Optional[str],
    region: Optional[str],
    cluster: Optional[str],
    git_tag: Optional[str],
    stage_dir: Optional[str],
    manifest_dir: Optional[Path],
    payload_staging_s3_uri: Optional[str],
    remote_user: str,
    run_context_file: Optional[Path],
    specimens_file: Optional[Path],
    samples_file: Optional[Path],
    libraries_file: Optional[Path],
    units_file: Optional[Path],
    session_name: Optional[str],
    project: Optional[str],
    cost_center: Optional[str],
    dry_run: bool,
    skip_project_check: bool,
    allow_stage_discovery: bool,
    max_runtime_minutes: int,
    export_destination_s3_uri: Optional[str],
    export_trigger: str,
    delete_on_export_success: bool,
    replace_existing_analysis_dir: bool,
    dy_config: Optional[list[str]] = None,
    require_staging_receipt: bool = False,
) -> dict[str, Any]:
    catalog, command = _catalog_load_command(config, command_id, dyec_version=dyec_version)
    resolved_dyec_version = catalog.resolve_dyec_build_key(dyec_version)
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
    resolved_cost_center = _resolve_cost_center_option(cost_center)
    manifest_dir_text = str(manifest_dir.expanduser()) if manifest_dir else None
    run_context_file_text = str(run_context_file.expanduser()) if run_context_file else None
    specimens_file_text = str(specimens_file.expanduser()) if specimens_file else None
    samples_file_text = str(samples_file.expanduser()) if samples_file else None
    libraries_file_text = str(libraries_file.expanduser()) if libraries_file else None
    units_file_text = str(units_file.expanduser()) if units_file else None
    _catalog_validate_explicit_inputs(
        command,
        stage_dir=stage_dir,
        manifest_dir=manifest_dir_text,
        run_context_file=run_context_file_text,
        specimens_file=specimens_file_text,
        samples_file=samples_file_text,
        libraries_file=libraries_file_text,
        units_file=units_file_text,
        allow_stage_discovery=allow_stage_discovery,
        require_staging_receipt=require_staging_receipt,
    )
    resolved_git_tag = git_tag or command.git_tag
    workflow_argv = command.launch_argv(
        analysis_id=analysis_id,
        executing_entity=resolved_executing_entity,
        git_tag=resolved_git_tag,
        profile=profile,
        region=region,
        cluster=cluster,
        stage_dir=stage_dir,
        manifest_dir=manifest_dir_text,
        run_context_file=run_context_file_text,
        specimens_file=specimens_file_text,
        samples_file=samples_file_text,
        libraries_file=libraries_file_text,
        units_file=units_file_text,
        session_name=session_name,
        project=project,
        cost_center=resolved_cost_center,
        dry_run=dry_run,
        skip_project_check=skip_project_check,
        export_destination_s3_uri=resolved_export_destination_s3_uri,
        export_trigger=export_trigger,
        delete_on_export_success=delete_on_export_success,
        replace_existing_analysis_dir=replace_existing_analysis_dir,
        remote_user=remote_user,
    )
    if payload_staging_s3_uri:
        workflow_argv.extend(["--payload-staging-s3-uri", payload_staging_s3_uri])
    workflow_argv.extend(["--max-runtime-minutes", str(max_runtime_minutes)])
    normalized_dy_config = _append_dy_config_overrides(workflow_argv, dy_config)
    dy_command = workflow_argv[workflow_argv.index("--dy-command") + 1]
    return {
        "command_catalog_version": catalog.command_catalog_version,
        "dyec_version": resolved_dyec_version,
        "result_export": (
            catalog.result_export.model_dump(mode="json")
            if catalog.result_export is not None
            else None
        ),
        "command": _catalog_command_summary(command),
        "analysis_id": analysis_id,
        "executing_entity": resolved_executing_entity,
        "git_tag": resolved_git_tag,
        "dry_run": dry_run,
        "cost_center": resolved_cost_center,
        "dy_command": dy_command,
        "dy_config": normalized_dy_config,
        "workflow_argv": workflow_argv,
        "workflow_command": shlex.join(["dyec", *workflow_argv]),
        "export_destination_s3_uri": resolved_export_destination_s3_uri,
        "payload_staging_s3_uri": payload_staging_s3_uri,
    }


def catalog_list(
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
    command_class: Optional[str] = typer.Option(
        None,
        "--command-class",
        help="Limit output to sample_analysis, run_analysis, or utility.",
    ),
    command_type: Optional[str] = typer.Option(
        None,
        "--type",
        help="Limit output to prod, test, dev, or research.",
    ),
    dyec_version: Optional[str] = typer.Option(
        None,
        "--dyec-version",
        help="Use an immutable numeric DYEC snapshot instead of the default current view.",
    ),
) -> None:
    """List command-catalog entries as launchable command summaries."""

    from daylily_ec.repositories import load_repository_catalog
    from daylily_ec.scripts.common import CommandError

    try:
        catalog = load_repository_catalog(config)
        resolved_dyec_version = catalog.resolve_dyec_build_key(dyec_version)
        commands = catalog.commands_for_dyec_build(dyec_version)
        if repository:
            repo_key = repository.strip()
            if repo_key not in catalog.repositories:
                raise CommandError(f"Unknown repository: {repo_key}")
            commands = [command for command in commands if command.repository == repo_key]
        if command_class:
            commands = [command for command in commands if command.command_class == command_class]
        if command_type:
            commands = [command for command in commands if command.type == command_type]
        payload = {
            "command_catalog_version": catalog.command_catalog_version,
            "default_repository": catalog.default_repository,
            "dyec_version": resolved_dyec_version,
            "result_export": (
                catalog.result_export.model_dump(mode="json")
                if catalog.result_export is not None
                else None
            ),
            "commands": [_catalog_command_summary(command) for command in commands],
        }
        if _json_mode():
            output.emit_json(payload)
            return
        typer.echo(json.dumps(payload, indent=2, sort_keys=False))
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def catalog_show(
    command_id: str = typer.Argument(..., help="Repository catalog command id."),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        help="Path to daylily_pipeline_command_catalog.yaml.",
    ),
    dyec_version: Optional[str] = typer.Option(
        None,
        "--dyec-version",
        help="Show an immutable numeric DYEC snapshot instead of the default current view.",
    ),
) -> None:
    """Show one command-catalog entry, including exact dy-r command strings."""

    try:
        catalog, command = _catalog_load_command(config, command_id, dyec_version=dyec_version)
        payload = {
            "command_catalog_version": catalog.command_catalog_version,
            "dyec_version": catalog.resolve_dyec_build_key(dyec_version),
            "result_export": (
                catalog.result_export.model_dump(mode="json")
                if catalog.result_export is not None
                else None
            ),
            "command": command.to_public_payload(),
        }
        if _json_mode():
            output.emit_json(payload)
            return
        typer.echo(json.dumps(payload, indent=2, sort_keys=False))
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def catalog_validation_compare(
    command_id: str = typer.Argument(..., help="Repository catalog command id."),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        help="Path to daylily_pipeline_command_catalog.yaml.",
    ),
    dyec_version: Optional[str] = typer.Option(
        None,
        "--dyec-version",
        help="Compare an immutable numeric snapshot instead of the default current view.",
    ),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region."),
) -> None:
    """Quickly compare a catalog command against its stored successful S3 evidence."""

    try:
        from daylily_ec.catalog_validation import compare_command_validation_evidence

        catalog, command = _catalog_load_command(config, command_id, dyec_version=dyec_version)
        payload = compare_command_validation_evidence(
            command,
            profile=profile,
            region=region,
        ).to_payload()
        payload["dyec_version"] = catalog.resolve_dyec_build_key(dyec_version)
        if _json_mode():
            output.emit_json(payload)
            return
        typer.echo(json.dumps(payload, indent=2, sort_keys=False))
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def catalog_config_bjuice_preval(
    sample: List[str] = typer.Option(
        ...,
        "--sample",
        help="External sample/specimen label to include, e.g. HG003. Repeat for multiple samples.",
    ),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        help="Empty output directory where six DayOA manifests will be written.",
    ),
    source_manifest_json: Path = typer.Option(
        ...,
        "--source-manifest-json",
        help="Reviewed Bjuice source_manifest_resolved.json.",
    ),
    run_evidence_json: Path = typer.Option(
        ...,
        "--run-evidence-json",
        help="Reviewed Bjuice run_evidence_v2.json.",
    ),
    library_run_matrix_tsv: Path = typer.Option(
        ...,
        "--library-run-matrix-tsv",
        help="Reviewed Bjuice library/run matrix TSV with source-owned EUIDs.",
    ),
    sample_metadata_tsv: Path = typer.Option(
        ...,
        "--sample-metadata-tsv",
        help="Reviewed legacy samples.tsv snapshot for sample/specimen metadata.",
    ),
    legacy_units_tsv: Path = typer.Option(
        ...,
        "--legacy-units-tsv",
        help="Reviewed legacy units.tsv snapshot for former unit-level analysis fields.",
    ),
    sr_subsample_pct: str = typer.Option(
        "",
        "--sr-subsample-pct",
        help="Value for DayOA SUBSAMPLE_PCT, e.g. 0.25. Blank means full input.",
    ),
    ont_subsample_pct: str = typer.Option(
        "",
        "--ont-subsample-pct",
        help="Value for DayOA ONT_SUBSAMPLE_PCT, e.g. 0.25. Blank means full input.",
    ),
    analysis_label: str = typer.Option(
        "BJUICEPREVAL",
        "--analysis-label",
        help="Prefix for generated ANALYSIS_UNIT_UID values.",
    ),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile for S3 listing."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region for S3 listing."),
    fsx_run_mount_root: str = typer.Option(
        "/fsx/run_dir_mounts",
        "--fsx-run-mount-root",
        help="Headnode FSx run-mount root used for ILMN FASTQ paths.",
    ),
    ont_fsx_root: str = typer.Option(
        "/fsx/run_dir_mounts/pca100-2026",
        "--ont-fsx-root",
        help="Headnode FSx run-mount root used for ONT pca100/2026 FASTQ paths.",
    ),
    order_type: str = typer.Option("RESEARCH", "--order-type"),
) -> None:
    """Generate exact DayOA six manifests for reviewed Bjuice prevalence samples."""

    try:
        from daylily_ec.bjuice_preval_config import generate_bjuice_preval_manifests

        result = generate_bjuice_preval_manifests(
            output_dir=output_dir.expanduser(),
            samples=sample,
            source_manifest_json=source_manifest_json.expanduser(),
            run_evidence_json=run_evidence_json.expanduser(),
            library_run_matrix_tsv=library_run_matrix_tsv.expanduser(),
            sample_metadata_tsv=sample_metadata_tsv.expanduser(),
            legacy_units_tsv=legacy_units_tsv.expanduser(),
            sr_subsample_pct=sr_subsample_pct,
            ont_subsample_pct=ont_subsample_pct,
            analysis_label=analysis_label,
            profile=profile,
            region=region,
            fsx_run_mount_root=fsx_run_mount_root,
            ont_fsx_root=ont_fsx_root,
            order_type=order_type,
        )
        payload = {
            "ok": True,
            "output_dir": str(result.output_dir),
            "receipt_path": str(result.receipt_path),
            "manifest_hashes": dict(result.manifest_hashes),
            "sample_count": len(sample),
            "samples": list(sample),
        }
        if _json_mode():
            output.emit_json(payload)
            return
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def catalog_config_bjuice_v2_hg002_multi_au(
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        help="Empty output directory where the DayOA manifests will be written.",
    ),
    source_manifest_json: Path = typer.Option(
        ...,
        "--source-manifest-json",
        help="Reviewed Bjuice source_manifest_resolved.json.",
    ),
    run_evidence_json: Path = typer.Option(
        ...,
        "--run-evidence-json",
        help="Reviewed Bjuice run_evidence_v2.json.",
    ),
    library_run_matrix_tsv: Path = typer.Option(
        ...,
        "--library-run-matrix-tsv",
        help="Reviewed Bjuice library/run matrix TSV. Source identity fields are never copied to output.",
    ),
    sample_metadata_tsv: Path = typer.Option(
        ...,
        "--sample-metadata-tsv",
        help="Reviewed sample metadata TSV containing the HG002 analysis fields.",
    ),
    legacy_units_tsv: Path = typer.Option(
        ...,
        "--legacy-units-tsv",
        help="Reviewed legacy units TSV used only for explicit matching analysis fields.",
    ),
    direct_ilmn_coverage_x: str = typer.Option(
        ...,
        "--direct-ilmn-coverage-x",
        help="Verified direct Illumina HG002 coverage denominator C_ILMN; total/hybrid coverage is rejected.",
    ),
    direct_ilmn_coverage_evidence: Path = typer.Option(
        ...,
        "--direct-ilmn-coverage-evidence",
        help=(
            "Terminal direct-coverage JSON receipt with schema "
            "dyec.bjuice_v2_direct_ilmn_coverage_receipt.v1 and matching "
            "ilmn_direct_coverage_x."
        ),
    ),
    retarget_plan_json: Optional[Path] = typer.Option(
        None,
        "--retarget-plan-json",
        help=(
            "Strict HG002 seven-AU measured-coverage retarget plan. When supplied, it must "
            "declare every canonical AU, direct-denominator ILMN fraction, and measured ONT window."
        ),
    ),
    analysis_unit_plan_json: Optional[Path] = typer.Option(
        None,
        "--analysis-unit-plan-json",
        help=(
            "Explicit HG002 custom AU matrix. Each row declares its label, direct Illumina "
            "target, ONT target, and [start,end) hour interval. Mutually exclusive with "
            "--retarget-plan-json."
        ),
    ),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile for S3 listing."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region for S3 listing."),
    fsx_run_mount_root: str = typer.Option(
        "/fsx/run_dir_mounts",
        "--fsx-run-mount-root",
        help="Headnode FSx run-mount root used for ILMN FASTQ paths.",
    ),
    ont_fsx_root: str = typer.Option(
        "/fsx/run_dir_mounts/pca100-2026",
        "--ont-fsx-root",
        help="Headnode FSx run-mount root used for ONT pca100/2026 FASTQ paths.",
    ),
) -> None:
    """Generate default or explicitly planned HG002 Bjuice v2 manifests."""

    try:
        from daylily_ec.bjuice_v2_hg002_multi_au_config import (
            generate_bjuice_v2_hg002_multi_au_manifests,
        )

        result = generate_bjuice_v2_hg002_multi_au_manifests(
            output_dir=output_dir.expanduser(),
            source_manifest_json=source_manifest_json.expanduser(),
            run_evidence_json=run_evidence_json.expanduser(),
            library_run_matrix_tsv=library_run_matrix_tsv.expanduser(),
            sample_metadata_tsv=sample_metadata_tsv.expanduser(),
            legacy_units_tsv=legacy_units_tsv.expanduser(),
            direct_ilmn_coverage_x=direct_ilmn_coverage_x,
            direct_ilmn_coverage_evidence=direct_ilmn_coverage_evidence.expanduser(),
            retarget_plan_json=(retarget_plan_json.expanduser() if retarget_plan_json else None),
            analysis_unit_plan_json=(
                analysis_unit_plan_json.expanduser() if analysis_unit_plan_json else None
            ),
            profile=profile,
            region=region,
            fsx_run_mount_root=fsx_run_mount_root,
            ont_fsx_root=ont_fsx_root,
        )
        payload = {
            "ok": True,
            "output_dir": str(result.output_dir),
            "receipt_path": str(result.receipt_path),
            "manifest_hashes": dict(result.manifest_hashes),
            "sample_id": "HG002",
            "analysis_unit_count": len(result.receipt["analysis_units"]),
            "analysis_unit_labels": [row["label"] for row in result.receipt["analysis_units"]],
            "direct_ilmn_coverage_x": direct_ilmn_coverage_x,
            "retarget_plan_json": str(retarget_plan_json) if retarget_plan_json else None,
            "analysis_unit_plan_json": (
                str(analysis_unit_plan_json) if analysis_unit_plan_json else None
            ),
        }
        if _json_mode():
            output.emit_json(payload)
            return
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def catalog_render(
    command_id: str = typer.Argument(..., help="Repository catalog command id."),
    analysis_id: str = typer.Option(..., "--analysis-id", help="FSx analysis identifier."),
    executing_entity: Optional[str] = typer.Option(
        None,
        "--executing-entity",
        "-u",
        help="User/system identifier under /fsx/analysis_results. Defaults to --cluster.",
    ),
    config: Optional[Path] = typer.Option(None, "--config", help="Catalog YAML path."),
    dyec_version: Optional[str] = typer.Option(
        None,
        "--dyec-version",
        help="Render an immutable numeric snapshot instead of the default current view.",
    ),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region."),
    cluster: Optional[str] = typer.Option(None, "--cluster", "--cluster-name"),
    git_tag: Optional[str] = typer.Option(None, "--git-tag", "-t", help="Override DayOA tag."),
    stage_dir: Optional[str] = typer.Option(
        None,
        "--stage-dir",
        help="Existing remote FSx staging directory for staged sample manifests.",
    ),
    manifest_dir: Optional[Path] = typer.Option(
        None,
        "--manifest-dir",
        help="Local directory containing exact six-manifest DayOA inputs.",
    ),
    payload_staging_s3_uri: Optional[str] = typer.Option(
        None,
        "--payload-staging-s3-uri",
        help="Explicit s3://bucket/prefix relay for large local launch payloads.",
    ),
    remote_user: str = typer.Option(
        "auto",
        "--remote-user",
        help="Headnode login user for launch setup and tmux controller: auto, ubuntu, or ec2-user.",
    ),
    run_context_file: Optional[Path] = typer.Option(
        None,
        "--run-context-file",
        help="Local run-context TSV for run-analysis commands.",
    ),
    specimens_file: Optional[Path] = typer.Option(None, "--specimens-file"),
    samples_file: Optional[Path] = typer.Option(None, "--samples-file"),
    libraries_file: Optional[Path] = typer.Option(None, "--libraries-file"),
    units_file: Optional[Path] = typer.Option(None, "--units-file"),
    session_name: Optional[str] = typer.Option(None, "--session-name"),
    project: Optional[str] = typer.Option(None, "--project", help="Project/budget for dyoainit."),
    cost_center: Optional[str] = typer.Option(
        None,
        "--cost-center",
        help="Explicit active Slurm cost center for the rendered workflow launch.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Render dry-run dy-r command."),
    skip_project_check: bool = typer.Option(
        True,
        "--skip-project-check/--strict-project-check",
        help="Skip or enable upstream project validation in dyoainit.",
    ),
    allow_stage_discovery: bool = typer.Option(
        False,
        "--allow-stage-discovery",
        help="Explicitly permit workflow launch to discover the latest staged sample manifest.",
    ),
    max_runtime_minutes: int = typer.Option(
        DEFAULT_JOB_MAX_RUNTIME_MINUTES,
        "--max-runtime-minutes",
        help="Forwarded compatibility value for workflow launch.",
    ),
    export_destination_s3_uri: Optional[str] = typer.Option(None, "--export-destination-s3-uri"),
    export_trigger: str = typer.Option("none", "--export-trigger"),
    delete_on_export_success: bool = typer.Option(False, "--delete-on-export-success"),
    replace_existing_analysis_dir: bool = typer.Option(False, "--replace-existing-analysis-dir"),
    dy_config: Optional[List[str]] = typer.Option(
        None,
        "--dy-config",
        help="Append one dy-r/Snakemake config assignment to the rendered command, e.g. key=value.",
    ),
) -> None:
    """Render the exact `dyec workflow launch` argv for a catalog command."""

    try:
        payload = _catalog_render_payload(
            config=config,
            command_id=command_id,
            dyec_version=dyec_version,
            analysis_id=analysis_id,
            executing_entity=executing_entity,
            profile=profile,
            region=region,
            cluster=cluster,
            git_tag=git_tag,
            stage_dir=stage_dir,
            manifest_dir=manifest_dir,
            payload_staging_s3_uri=payload_staging_s3_uri,
            remote_user=remote_user,
            run_context_file=run_context_file,
            specimens_file=specimens_file,
            samples_file=samples_file,
            libraries_file=libraries_file,
            units_file=units_file,
            session_name=session_name,
            project=project,
            cost_center=cost_center,
            dry_run=dry_run,
            skip_project_check=skip_project_check,
            allow_stage_discovery=allow_stage_discovery,
            max_runtime_minutes=max_runtime_minutes,
            export_destination_s3_uri=export_destination_s3_uri,
            export_trigger=export_trigger,
            delete_on_export_success=delete_on_export_success,
            replace_existing_analysis_dir=replace_existing_analysis_dir,
            dy_config=dy_config,
        )
        if _json_mode():
            output.emit_json(payload)
            return
        typer.echo(json.dumps(payload, indent=2, sort_keys=False))
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


def catalog_launch(
    command_id: str = typer.Argument(..., help="Repository catalog command id."),
    analysis_id: str = typer.Option(..., "--analysis-id", help="FSx analysis identifier."),
    executing_entity: Optional[str] = typer.Option(
        None,
        "--executing-entity",
        "-u",
        help="User/system identifier under /fsx/analysis_results. Defaults to --cluster.",
    ),
    config: Optional[Path] = typer.Option(None, "--config", help="Catalog YAML path."),
    dyec_version: Optional[str] = typer.Option(
        None,
        "--dyec-version",
        help="Launch an immutable numeric snapshot instead of the default current view.",
    ),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region."),
    cluster: Optional[str] = typer.Option(None, "--cluster", "--cluster-name"),
    git_tag: Optional[str] = typer.Option(None, "--git-tag", "-t", help="Override DayOA tag."),
    stage_dir: Optional[str] = typer.Option(None, "--stage-dir"),
    manifest_dir: Optional[Path] = typer.Option(None, "--manifest-dir"),
    payload_staging_s3_uri: Optional[str] = typer.Option(
        None,
        "--payload-staging-s3-uri",
        help="Explicit s3://bucket/prefix relay for large local launch payloads.",
    ),
    remote_user: str = typer.Option(
        "auto",
        "--remote-user",
        help="Headnode login user for launch setup and tmux controller: auto, ubuntu, or ec2-user.",
    ),
    run_context_file: Optional[Path] = typer.Option(None, "--run-context-file"),
    specimens_file: Optional[Path] = typer.Option(None, "--specimens-file"),
    samples_file: Optional[Path] = typer.Option(None, "--samples-file"),
    libraries_file: Optional[Path] = typer.Option(None, "--libraries-file"),
    units_file: Optional[Path] = typer.Option(None, "--units-file"),
    session_name: Optional[str] = typer.Option(None, "--session-name"),
    project: Optional[str] = typer.Option(None, "--project", help="Project/budget for dyoainit."),
    cost_center: Optional[str] = typer.Option(
        None,
        "--cost-center",
        help="Explicit active Slurm cost center for the launched workflow.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Launch dry-run dy-r command."),
    skip_project_check: bool = typer.Option(
        True,
        "--skip-project-check/--strict-project-check",
        help="Skip or enable upstream project validation in dyoainit.",
    ),
    allow_stage_discovery: bool = typer.Option(
        False,
        "--allow-stage-discovery",
        help="Explicitly permit workflow launch to discover the latest staged sample manifest.",
    ),
    max_runtime_minutes: int = typer.Option(
        DEFAULT_JOB_MAX_RUNTIME_MINUTES,
        "--max-runtime-minutes",
        help="Forwarded compatibility value for workflow launch.",
    ),
    export_destination_s3_uri: Optional[str] = typer.Option(None, "--export-destination-s3-uri"),
    export_trigger: str = typer.Option("none", "--export-trigger"),
    delete_on_export_success: bool = typer.Option(False, "--delete-on-export-success"),
    replace_existing_analysis_dir: bool = typer.Option(False, "--replace-existing-analysis-dir"),
    dy_config: Optional[List[str]] = typer.Option(
        None,
        "--dy-config",
        help="Append one dy-r/Snakemake config assignment to the launched command, e.g. key=value.",
    ),
) -> None:
    """Quick-launch one command-catalog entry through the standard workflow launcher."""

    _warn_if_dayec_env_inactive()
    try:
        payload = _catalog_render_payload(
            config=config,
            command_id=command_id,
            dyec_version=dyec_version,
            analysis_id=analysis_id,
            executing_entity=executing_entity,
            profile=profile,
            region=region,
            cluster=cluster,
            git_tag=git_tag,
            stage_dir=stage_dir,
            manifest_dir=manifest_dir,
            payload_staging_s3_uri=payload_staging_s3_uri,
            remote_user=remote_user,
            run_context_file=run_context_file,
            specimens_file=specimens_file,
            samples_file=samples_file,
            libraries_file=libraries_file,
            units_file=units_file,
            session_name=session_name,
            project=project,
            cost_center=cost_center,
            dry_run=dry_run,
            skip_project_check=skip_project_check,
            allow_stage_discovery=allow_stage_discovery,
            max_runtime_minutes=max_runtime_minutes,
            export_destination_s3_uri=export_destination_s3_uri,
            export_trigger=export_trigger,
            delete_on_export_success=delete_on_export_success,
            replace_existing_analysis_dir=replace_existing_analysis_dir,
            dy_config=dy_config,
            require_staging_receipt=True,
        )
        launch_stdout_buffer = io.StringIO()
        with contextlib.redirect_stdout(launch_stdout_buffer):
            launch_rc = _invoke_workflow_launch(payload["workflow_argv"][2:])
        launch_stdout = launch_stdout_buffer.getvalue()
        if launch_rc != 0:
            if launch_stdout:
                typer.echo(launch_stdout, nl=False)
            raise typer.Exit(launch_rc)
        launch_metadata = _parse_workflow_launch_metadata(launch_stdout)
        payload["workflow_launch"] = launch_metadata
        if _json_mode():
            output.emit_json(payload)
            return
        if launch_stdout:
            typer.echo(launch_stdout, nl=False)
    except typer.Exit:
        raise
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
    region: Optional[str] = context_option(
        "aws_region",
        None,
        "--region",
        help="AWS region.",
        required=True,
    ),
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
    region: Optional[str] = context_option("aws_region", None, "--region", required=True),
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
    region: Optional[str] = context_option("aws_region", None, "--region", required=True),
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
    region: Optional[str] = context_option("aws_region", None, "--region", required=True),
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
    region: Optional[str] = context_option("aws_region", None, "--region", required=True),
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
    region: Optional[str] = context_option("aws_region", None, "--region", required=True),
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


def _workflow_run_dir(
    session: Optional[str],
    run_dir: Optional[str],
    *,
    remote_user: str = "ubuntu",
) -> str:
    from daylily_ec.scripts.common import CommandError

    if bool(session) == bool(run_dir):
        raise CommandError("Provide exactly one of --session or --run-dir.")
    if run_dir:
        return run_dir.rstrip("/")
    return f"/home/{remote_user}/daylily-runs/{session}"


def _read_workflow_file(
    *,
    profile: Optional[str],
    region: Optional[str],
    cluster: Optional[str],
    session: Optional[str],
    run_dir: Optional[str],
    filename: str,
    remote_user: str = "auto",
    tail_lines: Optional[int] = None,
):
    from daylily_ec.aws.ssm import SsmError, resolve_remote_user, run_shell, wait_for_ssm_online
    from daylily_ec.scripts.common import CommandError

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
        resolved_remote_user = resolve_remote_user(
            target.instance_id,
            resolved_region,
            profile=resolved_profile,
            as_user=remote_user,
        )
        resolved_run_dir = _workflow_run_dir(
            session,
            run_dir,
            remote_user=resolved_remote_user,
        )
        file_path = f"{resolved_run_dir}/{filename}"
        if tail_lines is None:
            read_command = 'cat "$FILE_PATH"'
        else:
            read_command = f'tail -n {max(tail_lines, 1)} "$FILE_PATH"'
        script = f"""
set +e +u
set +o pipefail 2>/dev/null || true
if [[ "$(id -un)" != {shlex.quote(resolved_remote_user)} ]]; then
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
            as_user=resolved_remote_user,
            timeout=120,
            comment=f"Read Daylily workflow {filename}",
        )
    except (CommandError, SsmError, TimeoutError) as exc:
        _exit_headnode_error(exc)


def _read_workflow_controller_log(
    *,
    profile: Optional[str],
    region: Optional[str],
    cluster: Optional[str],
    session: Optional[str],
    run_dir: Optional[str],
    remote_user: str,
    tail_lines: int,
):
    """Read the controller-owned log attributed by the clone-resident v2 status."""

    from daylily_ec.aws.ssm import SsmError, resolve_remote_user, run_shell, wait_for_ssm_online
    from daylily_ec.scripts.common import CommandError

    observability = _collect_workflow_observability(
        profile=profile,
        region=region,
        cluster=cluster,
        session=session,
        run_dir=run_dir,
        remote_user=remote_user,
    )
    repo_text = str(observability.get("repo_path") or "").strip()
    repo_path = PurePosixPath(repo_text)
    if (
        not repo_path.is_absolute()
        or repo_path.name != "daylily-omics-analysis"
        or "analysis_results" not in repo_path.parts
    ):
        raise CommandError("Clone-resident v2 status has an invalid DayOA repository path.")
    log_path = repo_path / ".dyec" / "controller.log"

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
        resolved_remote_user = resolve_remote_user(
            target.instance_id,
            resolved_region,
            profile=resolved_profile,
            as_user=remote_user,
        )
        script = f"""
set +e +u
set +o pipefail 2>/dev/null || true
if [[ "$(id -un)" != {shlex.quote(resolved_remote_user)} ]]; then
  echo "__DAYLILY_ERROR__=wrong_user"
  exit 5
fi
FILE_PATH={shlex.quote(str(log_path))}
case "$FILE_PATH" in
  /fsx/analysis_results/*/daylily-omics-analysis/.dyec/controller.log) ;;
  *) echo "__DAYLILY_ERROR__=invalid_controller_log_path"; exit 5 ;;
esac
if [[ ! -f "$FILE_PATH" ]]; then
  echo "__DAYLILY_ERROR__=missing_file:$FILE_PATH"
  exit 2
fi
tail -n {max(tail_lines, 1)} "$FILE_PATH"
"""
        return run_shell(
            target.instance_id,
            resolved_region,
            script,
            profile=resolved_profile,
            as_user=resolved_remote_user,
            timeout=120,
            comment="Read Daylily workflow controller log",
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


def _collect_workflow_observability(
    *,
    profile: Optional[str],
    region: Optional[str],
    cluster: Optional[str],
    session: Optional[str],
    run_dir: Optional[str],
    repo_path: Optional[str],
    controller_pid: Optional[int],
    snakemake_log: Optional[str],
    remote_user: str,
    tail_lines: Optional[int] = None,
) -> dict[str, Any]:
    """Collect invocation-attributed controller, log, progress, and Slurm evidence."""

    from daylily_ec.aws.ssm import resolve_remote_user, run_shell, wait_for_ssm_online
    from daylily_ec.scripts.common import CommandError
    from daylily_ec.workflow_observability import (
        build_remote_probe_command,
        normalize_repo_path,
        normalize_snakemake_log,
    )

    manual_requested = any(
        value is not None for value in (repo_path, controller_pid, snakemake_log)
    )
    if manual_requested:
        if repo_path is None or controller_pid is None:
            raise CommandError(
                "Manual/recovery inspection requires both --repo-path and --controller-pid."
            )
        if run_dir is not None:
            raise CommandError("Manual/recovery inspection does not accept --run-dir.")
        try:
            resolved_repo_path = normalize_repo_path(repo_path)
            resolved_snakemake_log = (
                normalize_snakemake_log(snakemake_log, repo_path=resolved_repo_path)
                if snakemake_log
                else None
            )
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc
        if controller_pid < 1:
            raise CommandError("--controller-pid must be a positive integer.")
        mode = "manual"
        resolved_run_dir = None
    else:
        mode = "launched"
        resolved_repo_path = None
        resolved_snakemake_log = None

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
    resolved_remote_user = resolve_remote_user(
        target.instance_id,
        resolved_region,
        profile=resolved_profile,
        as_user=remote_user,
    )
    if mode == "launched":
        resolved_run_dir = _workflow_run_dir(
            session,
            run_dir,
            remote_user=resolved_remote_user,
        )

    probe_arguments = ["--mode", mode]
    if session:
        probe_arguments.extend(["--session", session])
    if resolved_run_dir:
        probe_arguments.extend(["--run-dir", resolved_run_dir])
    if resolved_repo_path:
        probe_arguments.extend(["--repo-path", resolved_repo_path])
    if controller_pid is not None:
        probe_arguments.extend(["--controller-pid", str(controller_pid)])
    if resolved_snakemake_log:
        probe_arguments.extend(["--snakemake-log", resolved_snakemake_log])
    if tail_lines is not None:
        if isinstance(tail_lines, bool) or tail_lines < 1:
            raise CommandError("--lines must be a positive integer.")
        probe_arguments.extend(["--tail-lines", str(tail_lines)])
    result = run_shell(
        target.instance_id,
        resolved_region,
        build_remote_probe_command(probe_arguments),
        profile=resolved_profile,
        as_user=resolved_remote_user,
        timeout=120,
        comment="Inspect exact Daylily workflow invocation",
    )
    return _parse_workflow_status_payload(result.stdout)


def _parse_marked_json_payload(stdout: str, *, marker: str, context: str) -> dict[str, Any]:
    from daylily_ec.scripts.common import CommandError

    marked = [
        line[len(marker) :]
        for line in stdout.splitlines()
        if line.startswith(marker)
    ]
    if len(marked) != 1:
        raise CommandError(f"{context} output did not contain exactly one marker")
    try:
        payload = json.loads(marked[0].strip())
    except json.JSONDecodeError as exc:
        raise CommandError(f"{context} marker payload was not valid JSON") from exc
    if not isinstance(payload, dict):
        raise CommandError(f"{context} marker payload was not an object")
    return payload


def _download_remote_json_payload(
    *,
    instance_id: str,
    region: str,
    profile: str,
    remote_user: str,
    remote_path: str,
    expected_size: int,
    expected_sha256: str,
    comment: str,
    max_size_bytes: int = 20 * 1024 * 1024,
) -> dict[str, Any]:
    from daylily_ec.aws.ssm import run_shell
    from daylily_ec.scripts.common import CommandError

    if expected_size < 0:
        raise CommandError("remote JSON manifest reported a negative size")
    if expected_size > max_size_bytes:
        raise CommandError(
            f"remote JSON payload is {expected_size} bytes, above the "
            f"{max_size_bytes} byte transfer limit"
        )
    chunk_bytes = 15000
    chunk_marker = "__DYEC_REMOTE_JSON_CHUNK__="
    digest = hashlib.sha256()
    chunks: list[bytes] = []
    for offset in range(0, expected_size, chunk_bytes):
        count = min(chunk_bytes, expected_size - offset)
        script = (
            "set -euo pipefail\n"
            f"test -f {shlex.quote(remote_path)}\n"
            f"printf '%s' {shlex.quote(chunk_marker)}\n"
            f"dd if={shlex.quote(remote_path)} bs=1 skip={offset} count={count} status=none | base64 -w0\n"
            "printf '\\n'"
        )
        result = run_shell(
            instance_id,
            region,
            script,
            profile=profile,
            as_user=remote_user,
            timeout=120,
            comment=comment,
        )
        marked = [
            line[len(chunk_marker) :]
            for line in result.stdout.splitlines()
            if line.startswith(chunk_marker)
        ]
        if len(marked) != 1:
            raise CommandError("remote JSON chunk output did not contain exactly one marker")
        try:
            chunk = base64.b64decode(marked[0].strip(), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise CommandError("remote JSON chunk was not valid base64") from exc
        digest.update(chunk)
        chunks.append(chunk)
    payload_bytes = b"".join(chunks)
    if len(payload_bytes) != expected_size:
        raise CommandError("remote JSON transfer failed size verification")
    actual_sha256 = digest.hexdigest()
    if actual_sha256 != expected_sha256:
        raise CommandError("remote JSON transfer failed SHA-256 verification")
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise CommandError("remote JSON payload contained malformed JSON after transfer") from exc
    if not isinstance(payload, dict):
        raise CommandError("remote JSON payload was not an object")
    return payload


def _collect_remote_json_payload(
    *,
    instance_id: str,
    region: str,
    profile: str,
    remote_user: str,
    remote_argv: list[str],
    operation: str,
    timeout: int,
) -> dict[str, Any]:
    from daylily_ec.aws.ssm import run_shell
    from daylily_ec.scripts.common import CommandError

    remote_json = f"/tmp/dyec-{operation.replace('_', '-')}-{uuid.uuid4().hex}.json"
    remote_raw = f"{remote_json}.raw"
    remote_manifest = f"{remote_json}.manifest"
    manifest_marker = "__DYEC_REMOTE_JSON_MANIFEST__="
    script = "\n".join(
        [
            "set -euo pipefail",
            "command -v dyec >/dev/null",
            f"remote_json={shlex.quote(remote_json)}",
            f"remote_raw={shlex.quote(remote_raw)}",
            f"remote_manifest={shlex.quote(remote_manifest)}",
            f"manifest_marker={shlex.quote(manifest_marker)}",
            f"{shlex.join(remote_argv)} > \"$remote_raw\"",
            "python3 - \"$remote_raw\" \"$remote_json\" \"$remote_manifest\" \"$manifest_marker\" <<'PY'",
            "import hashlib, json, pathlib, sys",
            "raw_path = pathlib.Path(sys.argv[1])",
            "path = pathlib.Path(sys.argv[2])",
            "manifest_path = pathlib.Path(sys.argv[3])",
            "manifest_marker = sys.argv[4]",
            "raw_text = raw_path.read_text(encoding='utf-8')",
            "decoder = json.JSONDecoder()",
            "candidates = []",
            "try:",
            "    parsed = json.loads(raw_text)",
            "    if isinstance(parsed, dict):",
            "        candidates.append(parsed)",
            "except json.JSONDecodeError:",
            "    for index, char in enumerate(raw_text):",
            "        if char != '{':",
            "            continue",
            "        try:",
            "            parsed, end = decoder.raw_decode(raw_text, index)",
            "        except json.JSONDecodeError:",
            "            continue",
            "        if isinstance(parsed, dict) and not raw_text[end:].strip():",
            "            candidates.append(parsed)",
            "if len(candidates) != 1:",
            "    raise SystemExit('ERROR: remote command did not emit exactly one JSON object')",
            "data = (json.dumps(candidates[0], sort_keys=True) + '\\n').encode('utf-8')",
            "path.write_bytes(data)",
            "payload = {",
            "    'path': str(path),",
            "    'size': len(data),",
            "    'sha256': hashlib.sha256(data).hexdigest(),",
            "}",
            "manifest_path.write_text(json.dumps(payload, sort_keys=True) + '\\n', encoding='utf-8')",
            "print(manifest_marker + json.dumps(payload, sort_keys=True))",
            "PY",
        ]
    )
    result = run_shell(
        instance_id,
        region,
        script,
        profile=profile,
        as_user=remote_user,
        timeout=timeout,
        comment=f"Collect {operation} JSON",
    )
    manifest = _parse_marked_json_payload(
        result.stdout,
        marker=manifest_marker,
        context="remote JSON manifest",
    )
    remote_path = manifest.get("path")
    size = manifest.get("size")
    sha256 = manifest.get("sha256")
    if not isinstance(remote_path, str) or not remote_path.startswith("/tmp/"):
        raise CommandError("remote JSON manifest did not include a /tmp path")
    if not isinstance(size, int):
        raise CommandError("remote JSON manifest did not include an integer size")
    if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise CommandError("remote JSON manifest did not include a SHA-256 digest")
    try:
        return _download_remote_json_payload(
            instance_id=instance_id,
            region=region,
            profile=profile,
            remote_user=remote_user,
            remote_path=remote_path,
            expected_size=size,
            expected_sha256=sha256,
            comment=f"Read {operation} JSON chunk",
        )
    finally:
        cleanup_script = (
            "set +e\n"
            f"rm -f {shlex.quote(remote_path)} "
            f"{shlex.quote(str(remote_path) + '.raw')} "
            f"{shlex.quote(str(remote_path) + '.manifest')}"
        )
        with contextlib.suppress(Exception):
            run_shell(
                instance_id,
                region,
                cleanup_script,
                profile=profile,
                as_user=remote_user,
                timeout=60,
                comment=f"Clean {operation} JSON",
            )


def _analysis_manifest_snapshot_remote_argv(analysis_root: str) -> list[str]:
    """Build the bounded, read-only remote projection for one six-manifest set."""

    script = "\n".join(
        [
            "import base64, hashlib, json, sys",
            "from pathlib import Path",
            "from daylily_ec.analysis_lock import normalize_analysis_root, write_visit",
            "root = normalize_analysis_root(sys.argv[1])",
            "write_visit(root, mode='export', intent='snapshot exact six-manifest inputs for DYEC relaunch')",
            "config = root / 'daylily-omics-analysis' / 'config'",
            "names = ('specimens.tsv', 'samples.tsv', 'libraries.tsv', 'sequencing_inputs.tsv', 'analysis_units.tsv', 'analysis_unit_inputs.tsv')",
            f"limit = {MAX_ANALYSIS_MANIFEST_SNAPSHOT_BYTES}",
            "total = 0",
            "files = {}",
            "for name in names:",
            "    path = config / name",
            "    if path.is_symlink() or not path.is_file():",
            "        raise SystemExit('required regular manifest is missing: ' + str(path))",
            "    data = path.read_bytes()",
            "    total += len(data)",
            "    if total > limit:",
            "        raise SystemExit('six-manifest snapshot exceeds bounded transfer limit')",
            "    files[name] = {'size_bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'content_base64': base64.b64encode(data).decode('ascii')}",
            "payload = {'schema_version': 'dyec.analysis_manifest_snapshot.v1', 'analysis_root': str(root), 'source_config_dir': str(config), 'total_size_bytes': total, 'files': files}",
            "print(json.dumps(payload, sort_keys=True))",
        ]
    )
    return ["python3", "-c", script, analysis_root]


def _materialize_analysis_manifest_snapshot(
    payload: dict[str, Any],
    *,
    output_dir: Path,
) -> dict[str, Any]:
    """Validate and atomically materialize a remote exact six-manifest snapshot."""

    from daylily_ec.manifest_set import MANIFEST_NAMES, ManifestSetError, load_manifest_set
    from daylily_ec.scripts.common import CommandError

    if payload.get("schema_version") != ANALYSIS_MANIFEST_SNAPSHOT_SCHEMA:
        raise CommandError("analysis manifest snapshot has an unsupported schema version")
    analysis_root = payload.get("analysis_root")
    source_config_dir = payload.get("source_config_dir")
    file_payloads = payload.get("files")
    total_size = payload.get("total_size_bytes")
    if not isinstance(analysis_root, str) or not analysis_root.startswith("/fsx/"):
        raise CommandError("analysis manifest snapshot did not include a valid analysis root")
    if not isinstance(source_config_dir, str) or not source_config_dir.startswith(analysis_root + "/"):
        raise CommandError("analysis manifest snapshot did not include a valid config directory")
    if not isinstance(file_payloads, dict) or set(file_payloads) != set(MANIFEST_NAMES):
        raise CommandError("analysis manifest snapshot did not contain exactly the six manifests")
    if isinstance(total_size, bool) or not isinstance(total_size, int) or total_size < 0:
        raise CommandError("analysis manifest snapshot did not include a valid total byte count")
    if total_size > MAX_ANALYSIS_MANIFEST_SNAPSHOT_BYTES:
        raise CommandError("analysis manifest snapshot exceeds the bounded transfer limit")

    decoded: dict[str, bytes] = {}
    expected_hashes: dict[str, str] = {}
    for name in MANIFEST_NAMES:
        record = file_payloads[name]
        if not isinstance(record, dict):
            raise CommandError(f"analysis manifest snapshot entry is invalid: {name}")
        encoded = record.get("content_base64")
        expected_size = record.get("size_bytes")
        expected_hash = record.get("sha256")
        if not isinstance(encoded, str):
            raise CommandError(f"analysis manifest snapshot entry has no content: {name}")
        if isinstance(expected_size, bool) or not isinstance(expected_size, int) or expected_size < 0:
            raise CommandError(f"analysis manifest snapshot entry has an invalid size: {name}")
        if not isinstance(expected_hash, str) or re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None:
            raise CommandError(f"analysis manifest snapshot entry has an invalid digest: {name}")
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise CommandError(f"analysis manifest snapshot entry is not valid base64: {name}") from exc
        if len(content) != expected_size:
            raise CommandError(f"analysis manifest snapshot entry size mismatch: {name}")
        if hashlib.sha256(content).hexdigest() != expected_hash:
            raise CommandError(f"analysis manifest snapshot entry digest mismatch: {name}")
        decoded[name] = content
        expected_hashes[name] = expected_hash
    if sum(len(content) for content in decoded.values()) != total_size:
        raise CommandError("analysis manifest snapshot total size mismatch")

    destination = output_dir.expanduser().resolve()
    if destination.exists():
        raise CommandError(f"refusing to overwrite manifest snapshot destination: {destination}")
    if not destination.parent.is_dir():
        raise CommandError(f"manifest snapshot destination parent does not exist: {destination.parent}")
    temporary = destination.with_name(f".{destination.name}.partial-{uuid.uuid4().hex}")
    try:
        temporary.mkdir(mode=0o700)
        for name in MANIFEST_NAMES:
            (temporary / name).write_bytes(decoded[name])
        manifests = load_manifest_set(temporary)
        if dict(manifests.hashes) != expected_hashes:
            raise CommandError("materialized analysis manifest snapshot hashes do not match source")
        receipt = {
            "schema_version": ANALYSIS_MANIFEST_SNAPSHOT_SCHEMA,
            "analysis_root": analysis_root,
            "source_config_dir": source_config_dir,
            "output_dir": str(destination),
            "manifest_hashes": expected_hashes,
            "total_size_bytes": total_size,
            "lineage_validated": True,
        }
        (temporary / "dyec_analysis_manifest_snapshot.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
        return receipt
    except ManifestSetError as exc:
        raise CommandError(str(exc)) from exc
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)


def workflow_status(
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region."),
    cluster: Optional[str] = typer.Option(None, "--cluster", "--cluster-name"),
    session: Optional[str] = typer.Option(
        None,
        "--session",
        "--session-name",
        help="Tmux session/run name.",
    ),
    run_dir: Optional[str] = typer.Option(None, "--run-dir", help="Explicit run directory."),
    repo_path: Optional[str] = typer.Option(
        None,
        "--repo-path",
        help="Exact DayOA checkout for a manual/recovery controller.",
    ),
    controller_pid: Optional[int] = typer.Option(
        None,
        "--controller-pid",
        help="Exact live or terminal manual/recovery controller PID.",
    ),
    snakemake_log: Optional[str] = typer.Option(
        None,
        "--snakemake-log",
        help="Exact manual/recovery .snakemake log when FD correlation is unavailable.",
    ),
    remote_user: str = typer.Option(
        "auto",
        "--remote-user",
        help="Remote login user for default run-dir resolution: auto, ubuntu, or ec2-user.",
    ),
    receipt_wait_seconds: int = typer.Option(
        90,
        "--receipt-wait-seconds",
        min=0,
        max=300,
        help=(
            "Bounded wait for a just-launched controller to create its clone-resident v2 status; "
            "0 preserves immediate failure for a missing receipt."
        ),
    ),
) -> None:
    """Report exact controller, Snakemake, progress, Slurm, and terminal state."""

    from daylily_ec.aws.ssm import SsmCommandFailedError, SsmError
    from daylily_ec.scripts.common import CommandError

    _warn_if_dayec_env_inactive()
    receipt_deadline = time.monotonic() + receipt_wait_seconds
    while True:
        try:
            payload = _collect_workflow_observability(
                profile=profile,
                region=region,
                cluster=cluster,
                session=session,
                run_dir=run_dir,
                repo_path=repo_path,
                controller_pid=controller_pid,
                snakemake_log=snakemake_log,
                remote_user=remote_user,
            )
            break
        except SsmCommandFailedError as exc:
            stderr = str(getattr(exc.result, "stderr", ""))
            receipt_missing = (
                "clone-resident status v2 is missing" in stderr
                or "controller target receipt is missing" in stderr
            )
            if receipt_missing and time.monotonic() < receipt_deadline:
                time.sleep(min(2.0, max(0.0, receipt_deadline - time.monotonic())))
                continue
            _exit_workflow_ssm_failure(exc)
        except (CommandError, SsmError, TimeoutError, json.JSONDecodeError) as exc:
            _exit_headnode_error(exc)

    if _json_mode():
        output.emit_json(payload)
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=False))


def workflow_logs(
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region."),
    cluster: Optional[str] = typer.Option(None, "--cluster", "--cluster-name"),
    session: Optional[str] = typer.Option(
        None,
        "--session",
        "--session-name",
        help="Tmux session/run name.",
    ),
    run_dir: Optional[str] = typer.Option(None, "--run-dir", help="Explicit run directory."),
    repo_path: Optional[str] = typer.Option(
        None,
        "--repo-path",
        help="Exact DayOA checkout for a manual/recovery controller.",
    ),
    controller_pid: Optional[int] = typer.Option(
        None,
        "--controller-pid",
        help="Exact live or terminal manual/recovery controller PID.",
    ),
    snakemake_log: Optional[str] = typer.Option(
        None,
        "--snakemake-log",
        help="Exact manual/recovery .snakemake log when FD correlation is unavailable.",
    ),
    remote_user: str = typer.Option(
        "auto",
        "--remote-user",
        help="Remote login user for default run-dir resolution: auto, ubuntu, or ec2-user.",
    ),
    lines: int = typer.Option(200, "--lines", min=1, help="Number of log lines to print."),
    stream: str = typer.Option(
        "tmux",
        "--stream",
        help="Log stream: tmux, controller, or snakemake.",
    ),
) -> None:
    """Tail a workflow tmux, controller, or exact active Snakemake log."""

    from daylily_ec.aws.ssm import SsmCommandFailedError, SsmError
    from daylily_ec.scripts.common import CommandError

    _warn_if_dayec_env_inactive()
    normalized_stream = stream.strip().lower()
    try:
        if normalized_stream in {"tmux", "controller"} and any(
            value is not None for value in (repo_path, controller_pid, snakemake_log)
        ):
            raise CommandError(
                "--repo-path, --controller-pid, and --snakemake-log apply only to "
                "--stream snakemake."
            )
        if normalized_stream == "tmux":
            result = _read_workflow_file(
                profile=profile,
                region=region,
                cluster=cluster,
                session=session,
                run_dir=run_dir,
                filename="tmux.log",
                remote_user=remote_user,
                tail_lines=lines,
            )
        elif normalized_stream == "controller":
            result = _read_workflow_controller_log(
                profile=profile,
                region=region,
                cluster=cluster,
                session=session,
                run_dir=run_dir,
                remote_user=remote_user,
                tail_lines=lines,
            )
        elif normalized_stream == "snakemake":
            payload = _collect_workflow_observability(
                profile=profile,
                region=region,
                cluster=cluster,
                session=session,
                run_dir=run_dir,
                repo_path=repo_path,
                controller_pid=controller_pid,
                snakemake_log=snakemake_log,
                remote_user=remote_user,
                tail_lines=lines,
            )
            log = payload.get("snakemake_log")
            attributed_repo = payload.get("repo_path")
            if not isinstance(log, dict) or not isinstance(attributed_repo, str):
                raise CommandError("Workflow status did not contain exact Snakemake attribution.")
            attributed_log = log.get("path")
            if not isinstance(attributed_log, str) or not attributed_log:
                problem = str(log.get("problem") or "exact attribution is unavailable")
                raise CommandError(f"Cannot read Snakemake log: {problem}.")
            from daylily_ec.workflow_observability import decode_snakemake_tail

            tail = decode_snakemake_tail(log.get("tail"))
            if tail:
                typer.echo(tail, nl=False)
            return
        else:
            raise typer.BadParameter(
                "--stream must be exactly 'tmux', 'controller', or 'snakemake'"
            )
    except SsmCommandFailedError as exc:
        _exit_workflow_ssm_failure(exc)
    except (CommandError, SsmError, TimeoutError, RuntimeError) as exc:
        _exit_headnode_error(exc)
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
    remote_user: str,
) -> str:
    return f"""
set -euo pipefail
if [[ "$(id -un)" != {shlex.quote(remote_user)} ]]; then
  echo "DYEC benchmark collection must run as {remote_user}; got $(id -un)." >&2
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
    remote_user: str = typer.Option(
        "auto",
        "--remote-user",
        help="Remote login user for benchmark collection: auto, ubuntu, or ec2-user.",
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
        from daylily_ec.aws.ssm import resolve_remote_user

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
        resolved_remote_user = resolve_remote_user(
            target.instance_id,
            resolved_region,
            profile=resolved_profile,
            as_user=remote_user,
        )
        script = _build_workflow_collect_benchmarks_script(
            analysis_root=resolved_analysis_root,
            genome_build=resolved_build,
            cluster=resolved_cluster,
            human_requestor=resolved_human,
            remote_user=resolved_remote_user,
        )
        result = run_shell(
            target.instance_id,
            resolved_region,
            script,
            profile=resolved_profile,
            as_user=resolved_remote_user,
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


def workflow_benchmark_report(
    analysis_root: str = typer.Option(
        ...,
        "--analysis-root",
        help="Exact /fsx/analysis_results/<owner>/<analysis> root.",
    ),
    genome_build: str = typer.Option(
        ...,
        "--genome-build",
        help="Exact benchmark genome build: b37, hg38, or hg38_broad.",
    ),
    max_bytes: int = typer.Option(
        4 * 1024 * 1024,
        "--max-bytes",
        help="Maximum canonical benchmark TSV size to parse.",
    ),
    max_rows: int = typer.Option(
        10000,
        "--max-rows",
        help="Maximum canonical benchmark TSV rows to return.",
    ),
    profile: Optional[str] = typer.Option(None, "--profile", help="AWS CLI profile."),
    region: Optional[str] = typer.Option(None, "--region", help="AWS region."),
    cluster: Optional[str] = typer.Option(None, "--cluster", "--cluster-name"),
    timeout: int = typer.Option(300, "--timeout", help="SSM command timeout in seconds."),
) -> None:
    """Parse one existing canonical DayOA benchmark summary without modifying it."""

    from daylily_ec.headnode_observability import (
        build_benchmark_report_script,
        parse_benchmark_report_output,
    )

    _warn_if_dayec_env_inactive()
    try:
        payload = _run_headnode_semantic_script(
            profile=profile,
            region=region,
            cluster=cluster,
            script=build_benchmark_report_script(
                analysis_root,
                genome_build,
                max_bytes=max_bytes,
                max_rows=max_rows,
            ),
            parser=parse_benchmark_report_output,
            comment=f"DYEC benchmark report for {analysis_root}",
            timeout=timeout,
        )
        _emit_headnode_payload(payload)
    except Exception as exc:  # noqa: BLE001
        _exit_headnode_error(exc)


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
    remote_user: str = typer.Option(
        "auto",
        "--remote-user",
        help="Remote login user for default run-dir resolution: auto, ubuntu, or ec2-user.",
    ),
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
    force_kill_session: bool = typer.Option(
        False,
        "--force-kill-session",
        help="Kill the named tmux session instead of sending Ctrl-C and waiting.",
    ),
    analysis_root: Optional[str] = typer.Option(
        None,
        "--analysis-root",
        help="Exact analysis root whose controller-owned lock may be released after stop.",
    ),
    release_analysis_lock: bool = typer.Option(
        False,
        "--release-analysis-lock",
        help="Release the stopped controller's DYEC analysis lock; requires --analysis-root.",
    ),
) -> None:
    """Stop a headnode workflow tmux controller, with explicit optional Slurm cancellation."""

    from daylily_ec.aws.ssm import (
        SsmCommandFailedError,
        SsmError,
        resolve_remote_user,
        run_shell,
        wait_for_ssm_online,
    )
    from daylily_ec.scripts.common import CommandError

    _warn_if_dayec_env_inactive()
    if cancel_slurm_jobs and not str(job_name_pattern or "").strip():
        raise typer.BadParameter("--job-name-pattern is required with --cancel-slurm-jobs")
    if job_name_pattern and not cancel_slurm_jobs:
        raise typer.BadParameter("--job-name-pattern requires --cancel-slurm-jobs")
    if release_analysis_lock and not str(analysis_root or "").strip():
        raise typer.BadParameter("--analysis-root is required with --release-analysis-lock")
    if analysis_root and not release_analysis_lock:
        raise typer.BadParameter("--analysis-root requires --release-analysis-lock")

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
        resolved_remote_user = resolve_remote_user(
            target.instance_id,
            resolved_region,
            profile=resolved_profile,
            as_user=remote_user,
        )
        resolved_run_dir = _workflow_run_dir(
            session,
            run_dir,
            remote_user=resolved_remote_user,
        )
        resolved_session = session or Path(resolved_run_dir).name
        script = f"""
set -euo pipefail
export DAYLILY_WORKFLOW_SESSION={shlex.quote(resolved_session)}
export DAYLILY_WORKFLOW_RUN_DIR={shlex.quote(resolved_run_dir)}
export DAYLILY_CANCEL_SLURM_JOBS={shlex.quote("true" if cancel_slurm_jobs else "false")}
export DAYLILY_JOB_NAME_PATTERN={shlex.quote(job_name_pattern or "")}
export DAYLILY_FORCE_KILL_SESSION={shlex.quote("true" if force_kill_session else "false")}
export DAYLILY_RELEASE_ANALYSIS_LOCK={shlex.quote("true" if release_analysis_lock else "false")}
export DAYLILY_ANALYSIS_ROOT={shlex.quote(analysis_root or "")}
python3 - <<'PY'
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys
import time


def run(command, *, env=None):
    return subprocess.run(command, capture_output=True, text=True, env=env)


def require_command(name):
    result = run(["bash", "-lc", f"command -v {{name}}"])
    if result.returncode != 0:
        raise SystemExit(f"required command not found on headnode PATH: {{name}}")


def tmux_session_name(session_name):
    return re.sub(r"[^A-Za-z0-9_-]", "_", session_name)


def tmux_present(name):
    return run(["tmux", "has-session", "-t", name]).returncode == 0


def tmux_pane_command(name):
    result = run(["tmux", "display-message", "-p", "-t", name, "#{{pane_current_command}}"])
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


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
force_kill_session = os.environ["DAYLILY_FORCE_KILL_SESSION"] == "true"
release_analysis_lock = os.environ["DAYLILY_RELEASE_ANALYSIS_LOCK"] == "true"
analysis_root = os.environ.get("DAYLILY_ANALYSIS_ROOT", "").strip()
session_tmux = tmux_session_name(session)
require_command("tmux")
before_tmux = tmux_present(session_tmux)
jobs_before = slurm_jobs_matching(job_name_pattern) if cancel_slurm else []

killed_tmux = False
interrupted_tmux = False
interrupt_completed = False
interrupt_wait_seconds = 90
if before_tmux:
    if force_kill_session:
        kill = run(["tmux", "kill-session", "-t", session_tmux])
        if kill.returncode != 0:
            raise SystemExit(
                kill.stderr.strip() or kill.stdout.strip() or "tmux kill-session failed"
            )
        killed_tmux = True
    else:
        interrupt = run(["tmux", "send-keys", "-t", session_tmux, "C-c"])
        if interrupt.returncode != 0:
            raise SystemExit(
                interrupt.stderr.strip() or interrupt.stdout.strip() or "tmux send-keys C-c failed"
            )
        interrupted_tmux = True
        deadline = time.time() + interrupt_wait_seconds
        while time.time() < deadline:
            if not tmux_present(session_tmux):
                interrupt_completed = True
                break
            if tmux_pane_command(session_tmux) in {{"bash", "sh", "zsh"}}:
                interrupt_completed = True
                break
            time.sleep(2)
        if not interrupt_completed:
            kill = run(["tmux", "kill-session", "-t", session_tmux])
            if kill.returncode != 0:
                raise SystemExit(
                    kill.stderr.strip() or kill.stdout.strip() or "tmux kill-session failed"
                )
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

lock_agent_id = f"dyec-workflow-{{session_tmux}}"
lock_release = {{
    "requested": release_analysis_lock,
    "analysis_root": analysis_root or None,
    "agent_id": lock_agent_id,
    "released": False,
    "already_unlocked": False,
    "error": "",
}}
if release_analysis_lock:
    if after_tmux:
        lock_release["error"] = "refusing to release analysis lock while tmux session still exists"
    else:
        require_command("dyec")
        release_env = os.environ.copy()
        release_env["DAYOA_AGENT_ID"] = lock_agent_id
        release_env["DAYOA_AGENT_KIND"] = "dyec-cli"
        release_env["DAYOA_HUMAN_REQUESTOR"] = os.environ.get("USER", "ubuntu")
        release_env["DAYOA_TMUX_SESSION"] = session_tmux
        release = run(
            [
                "dyec",
                "analysis",
                "lock",
                "release",
                "--analysis-root",
                analysis_root,
                "--human-requestor",
                release_env["DAYOA_HUMAN_REQUESTOR"],
                "--note",
                "controller stopped by dyec workflow stop",
            ],
            env=release_env,
        )
        if release.returncode != 0:
            release_detail = (
                release.stderr.strip() or release.stdout.strip() or "analysis lock release failed"
            )
            if "No active write lock to release:" in release_detail:
                lock_release["already_unlocked"] = True
            else:
                lock_release["error"] = release_detail
        else:
            lock_release["released"] = True

payload = {{
    "session_name": session,
    "run_dir": str(run_dir),
    "tmux_session_name": session_tmux,
    "tmux_session_before": before_tmux,
    "tmux_session_after": after_tmux,
    "interrupted_tmux_session": interrupted_tmux,
    "tmux_interrupt_completed": interrupt_completed,
    "tmux_interrupt_wait_seconds": interrupt_wait_seconds,
    "killed_tmux_session": killed_tmux,
    "cancel_slurm_jobs": cancel_slurm,
    "job_name_pattern": job_name_pattern,
    "slurm_jobs_before": jobs_before,
    "scancelled_job_ids": scancelled_job_ids,
    "slurm_jobs_after": jobs_after,
    "clone_resident_status_mutated_by_stop": False,
    "clone_resident_status_note": "not modified; the controller owns its append-only v2 attempt",
    "force_kill_session": force_kill_session,
    "analysis_lock_release": lock_release,
}}
print("__DAYLILY_WORKFLOW_STOP__=" + json.dumps(payload, sort_keys=True))
if lock_release["error"]:
    raise SystemExit(lock_release["error"])
PY
"""
        result = run_shell(
            target.instance_id,
            resolved_region,
            script,
            profile=resolved_profile,
            as_user=resolved_remote_user,
            timeout=timeout,
            comment=f"Stop Daylily workflow {resolved_session}",
        )
        payload = _parse_workflow_stop_payload(result.stdout)
    except SsmCommandFailedError as exc:
        if exc.result.stdout.strip():
            typer.echo(exc.result.stdout.rstrip())
        if exc.result.stderr.strip():
            typer.echo(exc.result.stderr.rstrip(), err=True)
        _exit_headnode_error(exc)
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
        "auto",
        "--remote-user",
        help="Remote SSM login user: auto, ubuntu, or ec2-user.",
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
            from daylily_ec.aws.ssm import resolve_remote_user, wait_for_ssm_online

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
            resolved_remote_user = resolve_remote_user(
                target.instance_id,
                resolved_region,
                profile=resolved_profile,
                as_user=remote_user,
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
            payload = _collect_remote_json_payload(
                instance_id=target.instance_id,
                region=resolved_region,
                profile=resolved_profile,
                remote_user=resolved_remote_user,
                remote_argv=remote_argv,
                operation=f"{mode}_analysis_status",
                timeout=300,
            )
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


def analysis_snapshot_manifests(
    analysis_root: str = typer.Option(..., "--analysis-root", help="Exact source analysis root."),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        help="New local directory for the validated six-manifest snapshot.",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS profile for the source analysis root.",
    ),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help="AWS region for the source analysis root.",
    ),
    cluster: str = typer.Option(
        ...,
        "--cluster",
        "--cluster-name",
        help="Cluster whose headnode contains the source analysis root.",
    ),
    remote_user: str = typer.Option(
        "auto",
        "--remote-user",
        help="Remote SSM login user: auto, ubuntu, or ec2-user.",
    ),
) -> None:
    """Copy an exact six-manifest input set through DYEC without rewriting it."""

    try:
        from daylily_ec.aws.ssm import resolve_remote_user, wait_for_ssm_online

        _warn_if_dayec_env_inactive()
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
        resolved_remote_user = resolve_remote_user(
            target.instance_id,
            resolved_region,
            profile=resolved_profile,
            as_user=remote_user,
        )
        payload = _collect_remote_json_payload(
            instance_id=target.instance_id,
            region=resolved_region,
            profile=resolved_profile,
            remote_user=resolved_remote_user,
            remote_argv=_analysis_manifest_snapshot_remote_argv(analysis_root),
            operation="analysis_manifest_snapshot",
            timeout=300,
        )
        result = _materialize_analysis_manifest_snapshot(payload, output_dir=output_dir)
        result["cluster"] = {
            "name": resolved_cluster,
            "region": resolved_region,
            "headnode_instance_id": target.instance_id,
        }
        _emit_analysis_payload(
            result,
            text=(
                "materialized validated six-manifest snapshot at "
                f"{result['output_dir']}"
            ),
        )
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
    pipeline: str = typer.Argument(..., help="Pipeline contract; currently hiomr-kitchensink."),
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
    remote_user: str = typer.Option(
        "auto",
        "--remote-user",
        help="Remote SSM login user: auto, ubuntu, or ec2-user.",
    ),
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
            from daylily_ec.aws.ssm import wait_for_ssm_online

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
            payload = _collect_remote_json_payload(
                instance_id=target.instance_id,
                region=resolved_region,
                profile=resolved_profile,
                remote_user=remote_user,
                remote_argv=remote_argv,
                operation="command_sample_stats",
                timeout=300,
            )
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
    profile: Optional[str] = context_option(
        "aws_profile",
        None,
        "--profile",
        help="AWS CLI profile.",
        required=True,
    ),
    region: Optional[str] = context_option(
        "aws_region",
        None,
        "--region",
        help="AWS region.",
        required=True,
    ),
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
        observability = _collect_workflow_observability(
            profile=profile,
            region=region,
            cluster=cluster,
            session=session_name,
            run_dir=None if session_name else (metadata.run_dir or None),
        )
        terminal = observability.get("terminal")
        if not isinstance(terminal, dict):
            raise RuntimeError("workflow observability omitted terminal v2 status")
        return {
            "state": observability.get("state"),
            "controller_exit_code": terminal.get("controller_exit_code"),
            "day_run_exit_code": terminal.get("day_run_exit_code"),
            "snakemake_exit_code": terminal.get("snakemake_exit_code"),
            "status_path": (
                observability.get("status", {}).get("path")
                if isinstance(observability.get("status"), dict)
                else None
            ),
        }

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
    register_root_command(
        registry,
        "set-vars",
        set_vars,
        EXEMPT,
    )
    register_root_command(
        registry,
        "unset-vars",
        unset_vars,
        EXEMPT,
    )
    register_group_commands(
        registry,
        "agent",
        "Operational guidance for agents using DYEC safely.",
        [("guidance", agent_guidance, EXEMPT_JSON)],
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
        "aws/budget",
        "AWS Budget inspection and limit management.",
        [
            (
                "set-limit",
                aws_budget_set_limit,
                required_policy(supports_json=True, mutates_state=True),
            ),
        ],
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
            (
                "recover",
                slurm_accounting_recover,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
        ],
    )
    register_group_commands(
        registry,
        "slurm-accounting/privatelink",
        "TCP-only PrivateLink bridges to existing Slurm accounting databases.",
        [
            (
                "ensure",
                slurm_accounting_privatelink_ensure,
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
            ("jobs", cluster_jobs, REQUIRED_JSON),
            ("describe", cluster_describe, REQUIRED_JSON),
            ("wait", cluster_wait, REQUIRED_LONG_RUNNING),
            (
                "compute-fleet",
                cluster_compute_fleet,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
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
            (
                "run",
                headnode_run,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
            ("jobs", headnode_jobs, required_policy()),
            ("system-info", headnode_system_info, REQUIRED_JSON),
            ("fsx-usage", headnode_fsx_usage, REQUIRED_JSON),
            ("analysis-roots", headnode_analysis_roots, REQUIRED_JSON),
            ("dayoa-controllers", headnode_dayoa_controllers, REQUIRED_JSON),
            (
                "dayoa-controller-action",
                headnode_dayoa_controller_action,
                required_policy(supports_json=True, mutates_state=True),
            ),
            (
                "slurm-job-action",
                headnode_slurm_job_action,
                required_policy(supports_json=True, mutates_state=True),
            ),
            (
                "slurm-drain",
                headnode_slurm_drain,
                required_policy(supports_json=True, mutates_state=True),
            ),
            ("upload", headnode_upload, required_policy(supports_json=True, long_running=True)),
            ("download", headnode_download, required_policy(supports_json=True, long_running=True)),
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
            (
                "materialize-cg-slim",
                samples_materialize_cg_slim,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
            ("run", samples_run, REQUIRED_MUTATING_LONG_RUNNING),
        ],
    )
    register_group_commands(
        registry,
        "identities",
        "Provider-neutral local manifest identity receipts; never contacts an identity service.",
        [
            ("validate", identities_validate, REQUIRED_JSON),
            ("plan", identities_plan, REQUIRED_JSON),
            (
                "apply",
                identities_apply,
                required_policy(supports_json=True, mutates_state=True),
            ),
            ("status", identities_status, REQUIRED_JSON),
            (
                "evidence",
                identities_evidence,
                required_policy(supports_json=True, mutates_state=True),
            ),
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
            ("benchmark-report", workflow_benchmark_report, REQUIRED_JSON),
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
        "catalog",
        "Command-catalog discovery, rendering, and quick-launch helpers.",
        [
            ("list", catalog_list, EXEMPT_JSON),
            ("show", catalog_show, EXEMPT_JSON),
            ("validation-compare", catalog_validation_compare, REQUIRED_JSON),
            (
                "config-bjuice-preval",
                catalog_config_bjuice_preval,
                required_policy(supports_json=True, long_running=True),
            ),
            (
                "config-bjuice-v2-hg002-multi-au",
                catalog_config_bjuice_v2_hg002_multi_au,
                required_policy(supports_json=True, long_running=True),
            ),
            ("render", catalog_render, EXEMPT_JSON),
            (
                "launch",
                catalog_launch,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
            (
                "quick-launch",
                catalog_launch,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
        ],
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
                "transfer",
                exports_transfer,
                required_policy(supports_json=True, mutates_state=True, long_running=True),
            ),
            (
                "cleanup",
                exports_cleanup,
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
        "runtime-cache",
        "DRA-only preservation of cluster-scoped runtime caches.",
        [
            (
                "export",
                runtime_cache_export,
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
            (
                "snapshot-manifests",
                analysis_snapshot_manifests,
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
    alphabetize_registry(registry)


class _AlphabeticalTyperGroup(typer.core.TyperGroup):
    """Render command and subgroup names in one deterministic alphabetic order."""

    def list_commands(self, ctx: click.Context) -> list[str]:
        return sorted(
            super().list_commands(ctx),
            key=lambda command_name: (command_name.casefold(), command_name),
        )


class _AlphabeticalCliCoreRootGroup(_CliCoreRootGroup):
    """Preserve cli-core-yo runtime bootstrapping while sorting root help."""

    def list_commands(self, ctx: click.Context) -> list[str]:
        return sorted(
            super().list_commands(ctx),
            key=lambda command_name: (command_name.casefold(), command_name),
        )


def _install_alphabetical_help_order(target_app: typer.Typer) -> None:
    """Apply the help-order renderer to the root and every nested command group."""
    target_app.info.cls = _AlphabeticalCliCoreRootGroup

    def _install_nested(typer_app: typer.Typer) -> None:
        for group_info in typer_app.registered_groups:
            nested_app = group_info.typer_instance
            if nested_app is None:
                raise RuntimeError("DYEC command group is missing its Typer application.")
            nested_app.info.cls = _AlphabeticalTyperGroup
            _install_nested(nested_app)

    _install_nested(target_app)


def _build_cli_app() -> typer.Typer:
    target_app = create_app(spec)
    _install_alphabetical_help_order(target_app)
    _install_dayec_version_option(target_app)
    return target_app


app = _build_cli_app()


def _run_cli(argv: Optional[List[str]] = None) -> int:
    """Run the CLI and preserve command callback integer return codes."""
    _reset_cli_core_runtime()
    args = list(argv if argv is not None else sys.argv[1:])
    try:
        cli_app = _build_cli_app()
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
