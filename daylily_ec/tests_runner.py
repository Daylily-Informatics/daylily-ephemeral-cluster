"""Local test and command-catalog orchestration for the DYEC CLI."""

from __future__ import annotations

import contextlib
import csv
import io
import json
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence
from urllib.parse import urlparse

from daylily_ec.analysis_identity import analysis_source_path, validate_analysis_segment
from daylily_ec.repositories import (
    AnalysisCommand,
    RepositoryCatalog,
    TestDataProfile,
    load_repository_catalog,
)
from daylily_ec.run_mounts import (
    CreateRunMountRequest,
    MOUNT_PURPOSE_RUN,
    RunMountRecord,
    create_run_mount,
    list_run_mounts,
    normalize_s3_uri,
)
from daylily_ec.workflow.export_data import normalize_s3_uri as normalize_export_s3_uri
from daylily_ec.workflow.export_data import validate_export_destination_s3_uri
from daylily_ec.workflow.snakemake_resources import (
    DEFAULT_JOB_MAX_RUNTIME_MINUTES,
    append_default_job_runtime,
    validate_job_max_runtime_minutes,
)


class TestsRunnerError(RuntimeError):
    """Raised when a DYEC tests subcommand cannot complete its contract."""


DYEC_RELEASED_CORE_COMMAND_TOKEN = "dyec-released-core"
DYEC_RELEASED_ALL_COMMAND_TOKEN = "dyec-released-all"

DYEC_RELEASED_CORE_COMMAND_IDS = (
    "illumina_snv_alignstats",
    "illumina_hg002_kitchensink_multiqc",
    "ultima_snv_alignstats",
    "ultima_snv_alignstats_kitchensink",
    "ont_snv_alignstats",
    "ont_snv_alignstats_kitchensink",
    "hybrid_ilmn_ont_snv",
    "hybrid_ilmn_ont_snv_kitchensink",
    "illumina_run_qc",
    "ont_run_qc",
    "ultima_run_qc",
)

KITCHEN_SINK_COMMAND_IDS = frozenset(
    {
        "illumina_hg002_kitchensink_multiqc",
        "ultima_snv_alignstats_kitchensink",
        "ont_snv_alignstats_kitchensink",
        "hybrid_ilmn_ont_snv_kitchensink",
    }
)

PANGENOME_COMMAND_IDS = frozenset(
    {
        "illumina_pangenome_snv",
        "ultima_pangenome_snv",
    }
)

LIVE_VALIDATION_COMMAND_IDS = KITCHEN_SINK_COMMAND_IDS | PANGENOME_COMMAND_IDS
COVERAGE_GATE_OVERRIDE_FLAGS = ("--no-cov", "--cov-fail-under")
DEFAULT_COMMAND_CATALOG_PARALLEL = 16
RUN_DRA_CREATE_WAIT_TIMEOUT_SECONDS = 90 * 60

MODE_MANIFESTS = {
    "ilmn_solo": Path("examples/staging/ilmn_solo/analysis_samples_manifest.tsv"),
    "ultima_solo": Path("examples/staging/ultima_solo/analysis_samples_manifest.tsv"),
    "ont_solo": Path("examples/staging/ont_solo/analysis_samples_manifest.tsv"),
    "hybrid_ilmn_ont": Path("examples/staging/hybrid_ilmn_ont/analysis_samples_manifest.tsv"),
    "pacbio_solo": Path("examples/staging/pacbio_solo/analysis_samples_manifest.tsv"),
    "roche_solo": Path("examples/staging/roche_solo/analysis_samples_manifest.tsv"),
    "complete_genomics_solo": Path(
        "examples/staging/complete_genomics_solo/analysis_samples_manifest.tsv"
    ),
}

SKIP_VALUE_FLAGS = {"-j", "--jobs", "-T", "--timestamp"}
STRIP_FLAGS = {
    "-p",
    "--printshellcmds",
    "-k",
    "--keep-going",
    "-n",
    "--dry-run",
    "--conda-create-envs-only",
}

SHELL_CONTROL_TOKENS = {";"}


@dataclass(frozen=True)
class CommandCatalogOptions:
    cluster: str
    profile: str
    region: str
    command_codes: str
    evidence_s3_uri: str
    dry_run_only: bool = False
    create_missing_mounts: bool = False
    parallel: int = DEFAULT_COMMAND_CATALOG_PARALLEL
    jobs: int = 150
    max_runtime_minutes: int = DEFAULT_JOB_MAX_RUNTIME_MINUTES
    executing_entity: str = "ubuntu"
    output_dir: Optional[Path] = None
    stamp: Optional[str] = None
    timeout_minutes: int = 360
    poll_interval_seconds: int = 30
    catalog_config: Optional[Path] = None


@dataclass(frozen=True)
class WorkflowLaunchMetadata:
    session_name: str = ""
    run_dir: str = ""
    repo_path: str = ""


@dataclass(frozen=True)
class RenderedPhase:
    command_id: str
    command_type: str
    phase: str
    analysis_id: str
    session_name: str
    dy_command: str
    workflow_argv: tuple[str, ...]
    export_destination_s3_uri: str
    manifest_path: Optional[str] = None
    samples_path: Optional[str] = None
    units_path: Optional[str] = None
    run_context_path: Optional[str] = None


@dataclass
class PhaseResult:
    phase: RenderedPhase
    launch_rc: int = 0
    status_payload: dict[str, Any] = field(default_factory=dict)
    launch_stdout: str = ""
    launch_stderr: str = ""
    launch_metadata: WorkflowLaunchMetadata = field(default_factory=WorkflowLaunchMetadata)

    @property
    def exit_code(self) -> Optional[int]:
        value = self.status_payload.get("exit_code")
        return value if isinstance(value, int) else None

    @property
    def succeeded(self) -> bool:
        if self.launch_rc != 0:
            return False
        if not self.status_payload:
            return True
        return self.exit_code == 0


@dataclass(frozen=True)
class CommandCatalogResult:
    rc: int
    output_dir: Path
    evidence_prefix_s3_uri: str
    command_ids: tuple[str, ...]
    dry_run_only: bool
    phases: tuple[PhaseResult, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "rc": self.rc,
            "output_dir": str(self.output_dir),
            "evidence_prefix_s3_uri": self.evidence_prefix_s3_uri,
            "command_ids": list(self.command_ids),
            "dry_run_only": self.dry_run_only,
            "phases": [
                {
                    "command_id": phase.phase.command_id,
                    "command_type": phase.phase.command_type,
                    "phase": phase.phase.phase,
                    "analysis_id": phase.phase.analysis_id,
                    "session_name": phase.phase.session_name,
                    "launch_rc": phase.launch_rc,
                    "exit_code": phase.exit_code,
                    "export_destination_s3_uri": phase.phase.export_destination_s3_uri,
                    "run_dir": phase.launch_metadata.run_dir,
                    "repo_path": phase.launch_metadata.repo_path,
                }
                for phase in self.phases
            ],
        }


StageFunc = Callable[[list[str]], int]
LaunchFunc = Callable[[list[str]], int]
StatusFunc = Callable[[WorkflowLaunchMetadata, RenderedPhase], dict[str, Any]]
MountListFunc = Callable[..., list[RunMountRecord]]
MountCreateFunc = Callable[..., RunMountRecord]


def run_pytest(*, coverage: bool, pytest_args: Sequence[str]) -> int:
    """Run pytest through the current Python interpreter."""
    args = list(pytest_args)
    if not args:
        args = ["-q"]
    if coverage:
        _reject_coverage_gate_overrides(args)
    cmd = [sys.executable, "-m", "pytest"]
    if coverage:
        cmd.extend(["--cov=daylily_ec", "--cov-branch", "--cov-fail-under=80"])
    cmd.extend(args)
    return subprocess.run(cmd).returncode


def _reject_coverage_gate_overrides(pytest_args: Sequence[str]) -> None:
    offenders = [
        arg
        for arg in pytest_args
        if arg == "--no-cov"
        or arg == "--cov-fail-under"
        or arg.startswith("--cov-fail-under=")
    ]
    if offenders:
        raise TestsRunnerError(
            "dyec tests pytest --coverage owns the coverage source and 80% fail-under gate; "
            "do not pass pytest-cov override flags: " + ", ".join(offenders)
        )


def parse_command_codes(command_codes: str, catalog: RepositoryCatalog) -> tuple[AnalysisCommand, ...]:
    """Resolve a command-code string to catalog commands."""
    requested = str(command_codes or "").strip()
    if not requested:
        raise TestsRunnerError("--command-codes is required.")
    lowered = requested.lower()
    if lowered == DYEC_RELEASED_CORE_COMMAND_TOKEN:
        return tuple(catalog.get_command(command_id) for command_id in DYEC_RELEASED_CORE_COMMAND_IDS)
    if lowered == DYEC_RELEASED_ALL_COMMAND_TOKEN:
        return tuple(command for command in catalog.commands() if command.type != "research")
    tokens = [token for token in requested.replace(",", " ").split() if token]
    commands: list[AnalysisCommand] = []
    seen: set[str] = set()
    for token in tokens:
        try:
            command = catalog.get_command(token)
        except KeyError as exc:
            raise TestsRunnerError(str(exc)) from exc
        if command.command_id in seen:
            raise TestsRunnerError(f"Duplicate command id: {command.command_id}")
        seen.add(command.command_id)
        commands.append(command)
    return tuple(commands)


def dyec_released_core_command_codes() -> str:
    """Return the released core validation command-code selector."""
    return DYEC_RELEASED_CORE_COMMAND_TOKEN


def command_ids(commands: Iterable[AnalysisCommand]) -> tuple[str, ...]:
    return tuple(command.command_id for command in commands)


def ordered_commands(commands: Sequence[AnalysisCommand]) -> tuple[AnalysisCommand, ...]:
    """Return commands with kitchen sinks first, preserving relative input order otherwise."""
    kitchen = [command for command in commands if command.command_id in KITCHEN_SINK_COMMAND_IDS]
    other = [command for command in commands if command.command_id not in KITCHEN_SINK_COMMAND_IDS]
    return tuple(kitchen + other)


def split_shell_command(command: str) -> list[str]:
    """Split a catalog command while preserving shell control punctuation."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def join_shell_command(tokens: Sequence[str]) -> str:
    """Join shell tokens without quoting supported control punctuation."""
    parts: list[str] = []
    for token in tokens:
        if token in SHELL_CONTROL_TOKENS:
            if not parts:
                parts.append(token)
            else:
                parts[-1] = f"{parts[-1]}{token}"
            continue
        parts.append(shlex.quote(token))
    return " ".join(parts)


def render_dy_command(
    command: str,
    *,
    jobs: int,
    dry_run: bool,
    warmup: bool = False,
    max_runtime_minutes: int = DEFAULT_JOB_MAX_RUNTIME_MINUTES,
) -> str:
    """Normalize Snakemake flags in a catalog dy_command string."""
    tokens = split_shell_command(command)
    rendered: list[str] = []
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token in SKIP_VALUE_FLAGS:
            skip_next = True
            continue
        if token.startswith("-j") and token != "-j":
            continue
        if token.startswith("--jobs="):
            continue
        if token.startswith("-T") and token != "-T":
            continue
        if token.startswith("--timestamp="):
            continue
        if token in STRIP_FLAGS:
            continue
        rendered.append(token)
    rendered.extend(["-j", str(jobs), "-p", "-k", "-T", "0"])
    if dry_run:
        rendered.append("-n")
    if warmup:
        rendered.append("--conda-create-envs-only")
    return append_default_job_runtime(
        join_shell_command(rendered),
        max_runtime_minutes=max_runtime_minutes,
    )


def render_catalog_dy_command(
    command: AnalysisCommand,
    *,
    jobs: int,
    dry_run: bool,
    warmup: bool = False,
    max_runtime_minutes: int = DEFAULT_JOB_MAX_RUNTIME_MINUTES,
) -> str:
    """Render a catalog command with runtime config plus runner-normalized flags."""
    dy_command = (
        getattr(command, "dryrun_dy_command", command.dy_command) if dry_run else command.dy_command
    )
    if command.input_contract == "run_context":
        runtime_parameters = getattr(command, "runtime_parameters", {})
        if "run_context_file" not in runtime_parameters:
            raise TestsRunnerError(
                f"runtime_parameters.run_context_file is required for {command.command_id}"
            )
        runtime_config = " ".join(
            shlex.quote(f"{key}={value}") for key, value in runtime_parameters.items()
        )
        dy_command = f"{dy_command} --config {runtime_config}"
    return render_dy_command(
        dy_command,
        jobs=jobs,
        dry_run=dry_run,
        warmup=warmup,
        max_runtime_minutes=max_runtime_minutes,
    )


def selected_dayoa_version(commands: Sequence[AnalysisCommand]) -> str:
    tags = sorted({command.git_tag for command in commands})
    if len(tags) != 1:
        raise TestsRunnerError(
            "Selected catalog commands have multiple DayOA git tags: " + ", ".join(tags)
        )
    return tags[0]


def build_evidence_prefix(
    *,
    evidence_s3_uri: str,
    cluster: str,
    dayoa_version: str,
    stamp: str,
) -> str:
    root = normalize_export_s3_uri(evidence_s3_uri)
    return f"{root}{cluster}/command_catalog_results/{dayoa_version}-{stamp}/"


def export_destination_for_phase(
    *,
    evidence_prefix_s3_uri: str,
    executing_entity: str,
    analysis_id: str,
) -> str:
    destination = f"{evidence_prefix_s3_uri}{executing_entity}/{analysis_id}/"
    return validate_export_destination_s3_uri(
        destination,
        source_path=analysis_source_path(
            executing_entity=executing_entity,
            analysis_id=analysis_id,
            headnode=True,
        ),
    )


def default_output_dir(stamp: str) -> Path:
    return Path("docs") / "plans" / f"{stamp}_dyec_tests_command_catalog_logs"


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_command_catalog(
    options: CommandCatalogOptions,
    *,
    stage_func: Optional[StageFunc] = None,
    launch_func: Optional[LaunchFunc] = None,
    status_func: Optional[StatusFunc] = None,
    mount_list_func: MountListFunc = list_run_mounts,
    mount_create_func: MountCreateFunc = create_run_mount,
) -> CommandCatalogResult:
    """Run the command-catalog prep-test orchestration."""
    if options.parallel < 1:
        raise TestsRunnerError("--parallel must be at least 1.")
    if options.jobs < 1:
        raise TestsRunnerError("--jobs must be at least 1.")
    try:
        validate_job_max_runtime_minutes(options.max_runtime_minutes)
    except ValueError as exc:
        raise TestsRunnerError(str(exc)) from exc
    if options.timeout_minutes < 1:
        raise TestsRunnerError("--timeout-minutes must be at least 1.")
    if options.poll_interval_seconds < 1:
        raise TestsRunnerError("--poll-interval-seconds must be at least 1.")

    cluster = validate_analysis_segment(options.cluster, field_name="cluster")
    executing_entity = validate_analysis_segment(
        options.executing_entity,
        field_name="executing_entity",
    )
    stamp = options.stamp or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    catalog = load_repository_catalog(options.catalog_config)
    selected = ordered_commands(parse_command_codes(options.command_codes, catalog))
    dayoa_version = selected_dayoa_version(selected)
    output_dir = options.output_dir or default_output_dir(stamp)
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_prefix = build_evidence_prefix(
        evidence_s3_uri=options.evidence_s3_uri,
        cluster=cluster,
        dayoa_version=dayoa_version,
        stamp=stamp,
    )
    role_uris = catalog_role_uris(catalog)

    write_json(
        output_dir / "command_registry.json",
        {
            "command_ids": list(command_ids(selected)),
            "dayoa_version": dayoa_version,
            "dry_run_only": options.dry_run_only,
            "evidence_prefix_s3_uri": evidence_prefix,
            "jobs": options.jobs,
            "parallel": options.parallel,
        },
    )

    run_mounts, pending_run_commands = inspect_run_mounts(
        selected,
        catalog=catalog,
        cluster=cluster,
        profile=options.profile,
        region=options.region,
        mount_list_func=mount_list_func,
    )
    if pending_run_commands and not options.create_missing_mounts:
        raise TestsRunnerError(
            "Missing run-directory DRA mounts for: " + ", ".join(sorted(pending_run_commands))
        )
    write_run_mounts(output_dir, run_mounts)

    all_phases: list[RenderedPhase] = []
    results: list[PhaseResult] = []
    effective_stage_func = stage_func or default_stage_func
    effective_launch_func = launch_func or default_launch_func

    def run_ready_commands(commands_to_run: Sequence[AnalysisCommand]) -> None:
        if not commands_to_run:
            return
        manifests = prepare_command_inputs(
            commands_to_run,
            catalog=catalog,
            output_dir=output_dir,
            role_uris=role_uris,
            evidence_prefix_s3_uri=evidence_prefix,
            profile=options.profile,
            region=options.region,
            cluster=cluster,
            run_mounts=run_mounts,
            stage_func=effective_stage_func,
        )
        phases = render_phases(
            commands_to_run,
            manifests=manifests,
            evidence_prefix_s3_uri=evidence_prefix,
            executing_entity=executing_entity,
            profile=options.profile,
            region=options.region,
            cluster=cluster,
            jobs=options.jobs,
            dry_run_only=options.dry_run_only,
            output_dir=output_dir,
            stamp=stamp,
            max_runtime_minutes=options.max_runtime_minutes,
        )
        all_phases.extend(phases)
        write_phase_plan(output_dir / "phase_plan.json", all_phases)
        results.extend(
            execute_phases(
                phases,
                dry_run_only=options.dry_run_only,
                parallel=options.parallel,
                launch_func=effective_launch_func,
                status_func=status_func,
                timeout_minutes=options.timeout_minutes,
                poll_interval_seconds=options.poll_interval_seconds,
                output_dir=output_dir,
            )
        )

    initially_ready = [
        command
        for command in selected
        if command.input_contract != "run_context" or run_profile_source(command, catalog) in run_mounts
    ]
    run_ready_commands(initially_ready)

    for source, source_commands in sorted(pending_run_commands.items()):
        command = source_commands[0]
        mount_id = run_id_from_source(source)
        request = CreateRunMountRequest(
            source_s3_uri=source,
            cluster_name=cluster,
            fsx_file_system_id=None,
            region=options.region,
            profile=options.profile,
            mount_id=mount_id,
            run_id=mount_id,
            platform=run_platform(command),
            purpose=MOUNT_PURPOSE_RUN,
            read_only=True,
            wait=True,
            timeout_seconds=RUN_DRA_CREATE_WAIT_TIMEOUT_SECONDS,
        )
        run_mounts[source] = mount_create_func(request)
        write_run_mounts(output_dir, run_mounts)
        run_ready_commands(source_commands)

    rc = 0 if all(result.succeeded for result in results) else 1
    final = CommandCatalogResult(
        rc=rc,
        output_dir=output_dir,
        evidence_prefix_s3_uri=evidence_prefix,
        command_ids=command_ids(selected),
        dry_run_only=options.dry_run_only,
        phases=tuple(results),
    )
    write_json(output_dir / "summary.json", final.to_payload())
    return final


def default_stage_func(argv: list[str]) -> int:
    from daylily_ec.stage_samples import main as stage_main

    return int(stage_main(argv))


def default_launch_func(argv: list[str]) -> int:
    from daylily_ec.scripts.daylily_run_omics_analysis_headnode import main as launch_main

    return int(launch_main(argv))


def catalog_role_uris(catalog: RepositoryCatalog) -> dict[str, str]:
    reference_uri = ""
    control_data_uri = ""
    for location in catalog.test_data_locations:
        if location.mount_path in {"/fsx/data", "/fsx/references"}:
            reference_uri = role_root_uri(
                mount_path=location.mount_path,
                data_root=location.data_root,
                s3_uri=location.s3_uri,
            )
        elif location.mount_path == "/fsx/control_data":
            control_data_uri = role_root_uri(
                mount_path=location.mount_path,
                data_root=location.data_root,
                s3_uri=location.s3_uri,
            )
    missing = []
    if not reference_uri:
        missing.append("/fsx/data")
    if not control_data_uri:
        missing.append("/fsx/control_data")
    if missing:
        raise TestsRunnerError("Catalog is missing test data locations for: " + ", ".join(missing))
    return {
        "reference_s3_uri": reference_uri,
        "control_data_s3_uri": control_data_uri,
    }


def role_root_uri(*, mount_path: str, data_root: str, s3_uri: str) -> str:
    relative = str(data_root).removeprefix(mount_path).strip("/")
    parsed = urlparse(normalize_s3_uri(s3_uri))
    key = parsed.path.lstrip("/").rstrip("/")
    if relative and key.endswith(relative):
        key = key[: -len(relative)].rstrip("/")
    return f"s3://{parsed.netloc}/{key}/" if key else f"s3://{parsed.netloc}/"


def inspect_run_mounts(
    commands: Sequence[AnalysisCommand],
    *,
    catalog: RepositoryCatalog,
    cluster: str,
    profile: str,
    region: str,
    mount_list_func: MountListFunc,
) -> tuple[dict[str, RunMountRecord], dict[str, list[AnalysisCommand]]]:
    run_commands = [command for command in commands if command.input_contract == "run_context"]
    if not run_commands:
        return {}, {}
    existing = mount_list_func(
        cluster_name=cluster,
        fsx_file_system_id=None,
        region=region,
        profile=profile,
        purpose=MOUNT_PURPOSE_RUN,
    )
    records_by_source = {
        normalize_s3_uri(record.source_s3_uri): record
        for record in existing
        if str(record.lifecycle).upper() == "AVAILABLE"
    }
    missing: dict[str, list[AnalysisCommand]] = {}
    for command in run_commands:
        source = run_profile_source(command, catalog)
        if source not in records_by_source:
            missing.setdefault(source, []).append(command)
    return records_by_source, missing


def prepare_run_mounts(
    commands: Sequence[AnalysisCommand],
    *,
    catalog: RepositoryCatalog,
    cluster: str,
    profile: str,
    region: str,
    create_missing: bool,
    mount_list_func: MountListFunc,
    mount_create_func: MountCreateFunc,
) -> dict[str, RunMountRecord]:
    records_by_source, missing = inspect_run_mounts(
        commands,
        catalog=catalog,
        cluster=cluster,
        profile=profile,
        region=region,
        mount_list_func=mount_list_func,
    )
    if missing and not create_missing:
        raise TestsRunnerError(
            "Missing run-directory DRA mounts for: " + ", ".join(sorted(missing))
        )
    for source, source_commands in sorted(missing.items()):
        command = source_commands[0]
        mount_id = run_id_from_source(source)
        request = CreateRunMountRequest(
            source_s3_uri=source,
            cluster_name=cluster,
            fsx_file_system_id=None,
            region=region,
            profile=profile,
            mount_id=mount_id,
            run_id=mount_id,
            platform=run_platform(command),
            purpose=MOUNT_PURPOSE_RUN,
            read_only=True,
            wait=True,
            timeout_seconds=RUN_DRA_CREATE_WAIT_TIMEOUT_SECONDS,
        )
        records_by_source[source] = mount_create_func(request)
    return records_by_source


def write_run_mounts(output_dir: Path, run_mounts: Mapping[str, RunMountRecord]) -> None:
    write_json(
        output_dir / "run_mounts.json",
        {source: record_to_payload(record) for source, record in sorted(run_mounts.items())},
    )


def run_profile_source(command: AnalysisCommand, catalog: Optional[RepositoryCatalog] = None) -> str:
    resolved_catalog = catalog or load_repository_catalog()
    profile = resolved_catalog.test_data_profiles.get(command.test_data_profile)
    if profile is None:
        raise TestsRunnerError(
            f"Command {command.command_id} references unknown profile {command.test_data_profile}."
        )
    source = normalize_s3_uri(profile.source_s3_uri_template)
    if not source:
        raise TestsRunnerError(f"Command {command.command_id} has no run source S3 URI.")
    return source


def run_platform(command: AnalysisCommand) -> str:
    platform = command.input_requirements.required_run_context_values.get("PLATFORM")
    if platform:
        return platform
    if command.compatible_platforms:
        return command.compatible_platforms[0]
    raise TestsRunnerError(f"Command {command.command_id} has no run platform.")


def run_id_from_source(source_s3_uri: str) -> str:
    path = urlparse(normalize_s3_uri(source_s3_uri)).path.rstrip("/")
    value = path.rsplit("/", 1)[-1]
    return validate_analysis_segment(value, field_name="run_id")


def record_to_payload(record: RunMountRecord) -> dict[str, Any]:
    if hasattr(record, "model_dump"):
        return record.model_dump(mode="json")
    return dict(record.__dict__)


def prepare_command_inputs(
    commands: Sequence[AnalysisCommand],
    *,
    catalog: RepositoryCatalog,
    output_dir: Path,
    role_uris: Mapping[str, str],
    evidence_prefix_s3_uri: str,
    profile: str,
    region: str,
    cluster: str,
    run_mounts: Mapping[str, RunMountRecord],
    stage_func: StageFunc,
) -> dict[str, dict[str, str]]:
    manifests: dict[str, dict[str, str]] = {}
    stage_s3_uri = f"{evidence_prefix_s3_uri}_config_generation/"
    for command in commands:
        command_dir = output_dir / command.command_id
        command_dir.mkdir(parents=True, exist_ok=True)
        if command.input_contract == "sample_manifest":
            manifest = write_sample_manifest(command, command_dir)
            config_dir = command_dir / "config"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = stage_func(
                    [
                        str(manifest),
                        "--config-only",
                        "--config-dir",
                        str(config_dir),
                        "--reference-s3-uri",
                        role_uris["reference_s3_uri"],
                        "--control-data-s3-uri",
                        role_uris["control_data_s3_uri"],
                        "--stage-s3-uri",
                        stage_s3_uri,
                        "--profile",
                        profile,
                        "--region",
                        region,
                        "--cluster",
                        cluster,
                    ]
                )
            (command_dir / "stage_config_stdout.txt").write_text(stdout.getvalue(), encoding="utf-8")
            if rc != 0:
                raise TestsRunnerError(f"Config generation failed for {command.command_id}: rc={rc}")
            samples, units = generated_config_paths(config_dir)
            manifests[command.command_id] = {
                "manifest_path": str(manifest),
                "samples_path": str(samples),
                "units_path": str(units),
            }
        elif command.input_contract == "run_context":
            run_context = command_dir / "runs.tsv"
            source = run_profile_source(command, catalog)
            record = run_mounts.get(source)
            if record is None:
                raise TestsRunnerError(f"No run mount record resolved for {source}")
            write_run_context(
                run_context,
                command=command,
                record=record,
                test_data_profile=catalog.test_data_profiles[command.test_data_profile],
                profile=profile,
                region=region,
            )
            manifests[command.command_id] = {"run_context_path": str(run_context)}
        elif command.input_contract == "none":
            manifests[command.command_id] = {}
        else:
            raise TestsRunnerError(
                f"Unsupported input contract for {command.command_id}: {command.input_contract}"
            )
    return manifests


def write_sample_manifest(command: AnalysisCommand, output_dir: Path) -> Path:
    mode = next((mode for mode in command.compatible_data_modes if mode in MODE_MANIFESTS), "")
    if not mode:
        raise TestsRunnerError(
            f"Command {command.command_id} has no supported sample manifest mode."
        )
    source = Path.cwd() / MODE_MANIFESTS[mode]
    if not source.is_file():
        raise TestsRunnerError(f"Sample manifest template not found: {source}")
    destination = output_dir / "analysis_samples.tsv"
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames is None:
            raise TestsRunnerError(f"Sample manifest template has no header: {source}")
        rows = [row for row in reader if any(str(value or "").strip() for value in row.values())]
    if not rows:
        raise TestsRunnerError(f"Sample manifest template has no rows: {source}")
    converted = convert_sample_row(rows[0])
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=reader.fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerow(converted)
    return destination


def convert_sample_row(row: Mapping[str, str]) -> dict[str, str]:
    converted: dict[str, str] = {}
    for key, value in row.items():
        if key is None:
            continue
        converted[key] = convert_manifest_value(str(value or ""))
    converted["STAGE_DIRECTIVE"] = "pass_through"
    converted["STAGE_TARGET"] = "/fsx/staging/staged_external_sequencing_data"
    return converted


def convert_manifest_value(value: str) -> str:
    parts = value.split(",")
    converted = [convert_manifest_path(part) for part in parts]
    return ",".join(converted)


def convert_manifest_path(value: str) -> str:
    text = value.strip()
    replacements = {
        "s3://lsmc-dayoa-references-usw2/genomic_data/organism_reads_slim/": (
            "/fsx/data/genomic_data/organism_reads_slim/"
        ),
        "s3://lsmc-dayoa-references-usw2/": "/fsx/references/",
        "s3://lsmc-dayoa-control-data-usw2/": "/fsx/control_data/",
    }
    for prefix, replacement in replacements.items():
        if text.startswith(prefix):
            return replacement + text[len(prefix) :]
    return value


def generated_config_paths(config_dir: Path) -> tuple[Path, Path]:
    samples = sorted(config_dir.glob("*_samples.tsv"))
    units = sorted(config_dir.glob("*_units.tsv"))
    if len(samples) != 1 or len(units) != 1:
        raise TestsRunnerError(
            f"Expected one generated samples.tsv and units.tsv under {config_dir}; "
            f"found {len(samples)} samples and {len(units)} units."
        )
    return samples[0], units[0]


def write_run_context(
    path: Path,
    *,
    command: AnalysisCommand,
    record: RunMountRecord,
    test_data_profile: TestDataProfile,
    profile: str,
    region: str,
) -> None:
    run_id = record.run_id or record.mount_id or run_id_from_source(record.source_s3_uri)
    run_dir = record.headnode_path.rstrip("/")
    sample_sheet = f"{run_dir}/SampleSheet.csv" if run_platform(command) == "ILMN" else "na"
    row = {
        "RUNID": run_id,
        "PLATFORM": run_platform(command),
        "RUN_DIR": run_dir,
        "SOURCE_S3_URI": normalize_s3_uri(record.source_s3_uri),
        "MOUNT_ID": record.mount_id,
        "SAMPLE_SHEET": sample_sheet,
        "BASECALLING_STATE": "COMPLETE",
        "RUN_STATUS": "COMPLETE",
        "OUTPUT_ROOT": f"results/runs/{run_id}",
        "REGION": region,
        "PROFILE": profile,
    }
    row.update(test_data_profile.run_context_values)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row), delimiter="\t")
        writer.writeheader()
        writer.writerow(row)


def render_phases(
    commands: Sequence[AnalysisCommand],
    *,
    manifests: Mapping[str, Mapping[str, str]],
    evidence_prefix_s3_uri: str,
    executing_entity: str,
    profile: str,
    region: str,
    cluster: str,
    jobs: int,
    dry_run_only: bool,
    output_dir: Path,
    stamp: str,
    max_runtime_minutes: int,
) -> tuple[RenderedPhase, ...]:
    phases: list[RenderedPhase] = []
    if not dry_run_only:
        for command in commands:
            phases.append(
                render_phase(
                    command,
                    phase="warmup",
                    manifests=manifests[command.command_id],
                    evidence_prefix_s3_uri=evidence_prefix_s3_uri,
                    executing_entity=executing_entity,
                    profile=profile,
                    region=region,
                    cluster=cluster,
                    jobs=jobs,
                    output_dir=output_dir,
                    stamp=stamp,
                    max_runtime_minutes=max_runtime_minutes,
                    warmup=True,
                    dry_run=False,
                )
            )
    for command in commands:
        phases.append(
            render_phase(
                command,
                phase="dryrun",
                manifests=manifests[command.command_id],
                evidence_prefix_s3_uri=evidence_prefix_s3_uri,
                executing_entity=executing_entity,
                profile=profile,
                region=region,
                cluster=cluster,
                jobs=jobs,
                output_dir=output_dir,
                stamp=stamp,
                max_runtime_minutes=max_runtime_minutes,
                warmup=False,
                dry_run=True,
            )
        )
    if not dry_run_only:
        for command in commands:
            phases.append(
                render_phase(
                    command,
                    phase="live",
                    manifests=manifests[command.command_id],
                    evidence_prefix_s3_uri=evidence_prefix_s3_uri,
                    executing_entity=executing_entity,
                    profile=profile,
                    region=region,
                    cluster=cluster,
                    jobs=jobs,
                    output_dir=output_dir,
                    stamp=stamp,
                    max_runtime_minutes=max_runtime_minutes,
                    warmup=False,
                    dry_run=False,
                )
            )
    return tuple(phases)


def render_phase(
    command: AnalysisCommand,
    *,
    phase: str,
    manifests: Mapping[str, str],
    evidence_prefix_s3_uri: str,
    executing_entity: str,
    profile: str,
    region: str,
    cluster: str,
    jobs: int,
    output_dir: Path,
    stamp: str,
    max_runtime_minutes: int,
    warmup: bool,
    dry_run: bool,
) -> RenderedPhase:
    analysis_id = validate_analysis_segment(
        f"ccv_{phase}_{command.command_id}_{stamp}",
        field_name="analysis_id",
    )
    session_name = analysis_id
    export_destination = export_destination_for_phase(
        evidence_prefix_s3_uri=evidence_prefix_s3_uri,
        executing_entity=executing_entity,
        analysis_id=analysis_id,
    )
    dy_command = render_catalog_dy_command(
        command,
        jobs=jobs,
        dry_run=dry_run,
        warmup=warmup,
        max_runtime_minutes=max_runtime_minutes,
    )
    argv = [
        "workflow",
        "launch",
        "--repository",
        command.repository,
        "--analysis-id",
        analysis_id,
        "--executing-entity",
        executing_entity,
        "--git-tag",
        command.git_tag,
        "--genome",
        command.genome,
        "--dy-command",
        dy_command,
        "--profile",
        profile,
        "--region",
        region,
        "--cluster",
        cluster,
        "--session-name",
        session_name,
        "--skip-project-check",
    ]
    if command.no_containerized:
        argv.append("--no-containerized")
    if not getattr(command, "default_activation", True):
        argv.append("--no-default-activation")
    if dry_run:
        argv.append("--dry-run")
    if command.input_contract == "sample_manifest":
        argv.extend(["--samples-file", manifests["samples_path"]])
        argv.extend(["--units-file", manifests["units_path"]])
    elif command.input_contract == "run_context":
        argv.extend(["--run-context-file", manifests["run_context_path"]])
    elif command.input_contract == "none":
        argv.append("--no-input-staging")
        if "--no-default-activation" not in argv:
            argv.append("--no-default-activation")
        argv.append("--bootstrap-test-config")
    write_json(
        output_dir / command.command_id / f"{phase}_rendered.json",
        {
            "analysis_id": analysis_id,
            "command_type": command.type,
            "day_profile": getattr(command, "day_profile", "slurm"),
            "dy_command": dy_command,
            "workflow_argv": argv,
            "export_destination_s3_uri": export_destination,
        },
    )
    return RenderedPhase(
        command_id=command.command_id,
        command_type=command.type,
        phase=phase,
        analysis_id=analysis_id,
        session_name=session_name,
        dy_command=dy_command,
        workflow_argv=tuple(argv),
        export_destination_s3_uri=export_destination,
        manifest_path=manifests.get("manifest_path"),
        samples_path=manifests.get("samples_path"),
        units_path=manifests.get("units_path"),
        run_context_path=manifests.get("run_context_path"),
    )


def write_phase_plan(path: Path, phases: Sequence[RenderedPhase]) -> None:
    write_json(
        path,
        {
            "phases": [
                {
                    "command_id": phase.command_id,
                    "command_type": phase.command_type,
                    "phase": phase.phase,
                    "analysis_id": phase.analysis_id,
                    "dy_command": phase.dy_command,
                    "workflow_argv": list(phase.workflow_argv),
                    "export_destination_s3_uri": phase.export_destination_s3_uri,
                }
                for phase in phases
            ]
        },
    )


def execute_phases(
    phases: Sequence[RenderedPhase],
    *,
    dry_run_only: bool,
    parallel: int,
    launch_func: LaunchFunc,
    status_func: Optional[StatusFunc],
    timeout_minutes: int,
    poll_interval_seconds: int,
    output_dir: Path,
) -> list[PhaseResult]:
    results: list[PhaseResult] = []
    warmups = [phase for phase in phases if phase.phase == "warmup"]
    dryruns = [phase for phase in phases if phase.phase == "dryrun"]
    lives = [phase for phase in phases if phase.phase == "live"]
    for batch in chunked(warmups, parallel):
        results.extend(
            execute_batch(
                batch,
                launch_func=launch_func,
                status_func=status_func,
                timeout_minutes=timeout_minutes,
                poll_interval_seconds=poll_interval_seconds,
                output_dir=output_dir,
            )
        )
    for batch in chunked(dryruns, parallel):
        results.extend(
            execute_batch(
                batch,
                launch_func=launch_func,
                status_func=status_func,
                timeout_minutes=timeout_minutes,
                poll_interval_seconds=poll_interval_seconds,
                output_dir=output_dir,
            )
        )
    if not dry_run_only:
        dryrun_success = {
            result.phase.command_id
            for result in results
            if result.phase.phase == "dryrun" and result.succeeded
        }
        eligible_lives = [phase for phase in lives if phase.command_id in dryrun_success]
        skipped = [phase for phase in lives if phase.command_id not in dryrun_success]
        for phase in skipped:
            results.append(
                PhaseResult(
                    phase=phase,
                    launch_rc=1,
                    status_payload={"exit_code": 1, "reason": "dryrun did not succeed"},
                )
            )
        for batch in chunked(eligible_lives, parallel):
            results.extend(
                execute_batch(
                    batch,
                    launch_func=launch_func,
                    status_func=status_func,
                    timeout_minutes=timeout_minutes,
                    poll_interval_seconds=poll_interval_seconds,
                    output_dir=output_dir,
                )
            )
    return results


def execute_batch(
    phases: Sequence[RenderedPhase],
    *,
    launch_func: LaunchFunc,
    status_func: Optional[StatusFunc],
    timeout_minutes: int,
    poll_interval_seconds: int,
    output_dir: Path,
) -> list[PhaseResult]:
    launched = [launch_phase(phase, launch_func=launch_func, output_dir=output_dir) for phase in phases]
    if status_func is None:
        return launched
    waited: list[PhaseResult] = []
    for result in launched:
        if result.launch_rc != 0:
            waited.append(result)
            continue
        waited.append(
            wait_for_phase(
                result,
                status_func=status_func,
                timeout_minutes=timeout_minutes,
                poll_interval_seconds=poll_interval_seconds,
            )
        )
    return waited


def launch_phase(
    phase: RenderedPhase,
    *,
    launch_func: LaunchFunc,
    output_dir: Path,
) -> PhaseResult:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        rc = launch_func(list(phase.workflow_argv[2:]))
    launch_stdout = stdout.getvalue()
    launch_stderr = stderr.getvalue()
    metadata = parse_workflow_launch_metadata(launch_stdout)
    phase_dir = output_dir / phase.command_id
    phase_dir.mkdir(parents=True, exist_ok=True)
    (phase_dir / f"{phase.phase}_launch_stdout.txt").write_text(launch_stdout, encoding="utf-8")
    (phase_dir / f"{phase.phase}_launch_stderr.txt").write_text(launch_stderr, encoding="utf-8")
    return PhaseResult(
        phase=phase,
        launch_rc=rc,
        launch_stdout=launch_stdout,
        launch_stderr=launch_stderr,
        launch_metadata=metadata,
    )


def parse_workflow_launch_metadata(stdout: str) -> WorkflowLaunchMetadata:
    values: dict[str, str] = {}
    for line in stdout.splitlines():
        if line.startswith("__DAYLILY_SESSION__="):
            values["session_name"] = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_RUN_DIR__="):
            values["run_dir"] = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_REPO_PATH__="):
            values["repo_path"] = line.split("=", 1)[1].strip()
    return WorkflowLaunchMetadata(
        session_name=values.get("session_name", ""),
        run_dir=values.get("run_dir", ""),
        repo_path=values.get("repo_path", ""),
    )


def wait_for_phase(
    result: PhaseResult,
    *,
    status_func: StatusFunc,
    timeout_minutes: int,
    poll_interval_seconds: int,
) -> PhaseResult:
    deadline = time.time() + timeout_minutes * 60
    while time.time() <= deadline:
        payload = status_func(result.launch_metadata, result.phase)
        if isinstance(payload.get("exit_code"), int):
            result.status_payload = payload
            return result
        time.sleep(poll_interval_seconds)
    result.status_payload = {"exit_code": 1, "reason": "workflow status wait timed out"}
    return result


def chunked(items: Sequence[RenderedPhase], size: int) -> Iterable[Sequence[RenderedPhase]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]
