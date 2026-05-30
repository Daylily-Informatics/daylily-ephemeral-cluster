"""Launch daylily-omics-analysis inside tmux on the headnode via SSM."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from daylily_ec.aws.ssm import (
    resolve_headnode_instance_id,
    run_shell,
    wait_for_ssm_online,
)
from daylily_ec.analysis_identity import analysis_source_path, validate_analysis_segment
from daylily_ec.headnode_readiness import validate_headnode_readiness
from daylily_ec.scripts.common import CommandError, need_cmd, resolve_cluster, resolve_region


STAGE_CONFIG_DISCOVERY_TIMEOUT_SECONDS = 180


@dataclass
class RemoteConfig:
    stage_dir: str
    samples_path: str
    units_path: str


@dataclass
class WorkflowLaunchInfo:
    session_name: str
    run_dir: str
    repo_path: str


def normalize_remote_path(path: str) -> str:
    if path.startswith("~/"):
        return path.replace("~/", "/home/ubuntu/", 1)
    if path == "~":
        return "/home/ubuntu"
    return path


def parse_remote_config(stdout: str) -> RemoteConfig:
    stage_dir = samples_path = units_path = None
    for line in stdout.splitlines():
        if line.startswith("__DAYLILY_STAGE_DIR__="):
            stage_dir = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_STAGE_SAMPLES__="):
            samples_path = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_STAGE_UNITS__="):
            units_path = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_ERROR__="):
            raise CommandError(f"Remote lookup failed: {line.split('=', 1)[1]}")
    if not (stage_dir and samples_path and units_path):
        raise CommandError("Unable to determine staged config paths on the head node.")
    return RemoteConfig(stage_dir, samples_path, units_path)


def parse_workflow_launch(stdout: str) -> WorkflowLaunchInfo:
    session_name = run_dir = repo_path = None
    for line in stdout.splitlines():
        if line.startswith("__DAYLILY_SESSION__="):
            session_name = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_RUN_DIR__="):
            run_dir = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_REPO_PATH__="):
            repo_path = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_ERROR__="):
            raise CommandError(line.split("=", 1)[1])
    if not (session_name and run_dir and repo_path):
        raise CommandError("Tmux session creation did not report success.")
    return WorkflowLaunchInfo(session_name=session_name, run_dir=run_dir, repo_path=repo_path)


def discover_stage_config(
    instance_id: str,
    profile: str,
    region: str,
    stage_dir: Optional[str],
    stage_base: str,
) -> RemoteConfig:
    remote_wait_seconds = max(1, STAGE_CONFIG_DISCOVERY_TIMEOUT_SECONDS - 15)
    if stage_dir:
        target_dir = normalize_remote_path(stage_dir.rstrip("/"))
        script = f"""
set -euo pipefail
if [[ "$(id -un)" != "ubuntu" ]]; then
  echo "__DAYLILY_ERROR__=wrong_user"
  exit 5
fi
STAGE_DIR={shlex.quote(target_dir)}
WAIT_DEADLINE=$((SECONDS + {remote_wait_seconds}))
last_error=missing_stage_dir
found_config=false
while true; do
  if [[ -d "$STAGE_DIR" ]]; then
    samples_file=$(ls -1 "$STAGE_DIR"/*_samples.tsv 2>/dev/null | head -n 1 || true)
    units_file=$(ls -1 "$STAGE_DIR"/*_units.tsv 2>/dev/null | head -n 1 || true)
    if [[ -n "$samples_file" && -n "$units_file" ]]; then
      echo "__DAYLILY_STAGE_DIR__=$STAGE_DIR"
      echo "__DAYLILY_STAGE_SAMPLES__=$samples_file"
      echo "__DAYLILY_STAGE_UNITS__=$units_file"
      found_config=true
      break
    fi
    last_error=missing_config
  else
    last_error=missing_stage_dir
  fi
  if (( SECONDS >= WAIT_DEADLINE )); then
    echo "__DAYLILY_ERROR__=$last_error"
    if [[ "$last_error" == "missing_stage_dir" ]]; then
      exit 2
    fi
    exit 3
  fi
  sleep 5
done
if [[ "$found_config" == "true" ]]; then
  true
fi
"""
    else:
        stage_base_norm = normalize_remote_path(stage_base.rstrip("/"))
        script = f"""
set -euo pipefail
if [[ "$(id -un)" != "ubuntu" ]]; then
  echo "__DAYLILY_ERROR__=wrong_user"
  exit 5
fi
STAGE_BASE={shlex.quote(stage_base_norm)}
if [[ ! -d "$STAGE_BASE" ]]; then
  echo "__DAYLILY_ERROR__=missing_stage_base"
  exit 2
fi
WAIT_DEADLINE=$((SECONDS + {remote_wait_seconds}))
last_error=no_stage_runs
found_config=false
while true; do
  latest_dir=$(ls -1dt "$STAGE_BASE"/*/ 2>/dev/null | head -n 1 || true)
  if [[ -n "$latest_dir" ]]; then
    samples_file=$(ls -1 "$latest_dir"/*_samples.tsv 2>/dev/null | head -n 1 || true)
    units_file=$(ls -1 "$latest_dir"/*_units.tsv 2>/dev/null | head -n 1 || true)
    if [[ -n "$samples_file" && -n "$units_file" ]]; then
      echo "__DAYLILY_STAGE_DIR__=$latest_dir"
      echo "__DAYLILY_STAGE_SAMPLES__=$samples_file"
      echo "__DAYLILY_STAGE_UNITS__=$units_file"
      found_config=true
      break
    fi
    last_error=missing_config
  else
    last_error=no_stage_runs
  fi
  if (( SECONDS >= WAIT_DEADLINE )); then
    echo "__DAYLILY_ERROR__=$last_error"
    if [[ "$last_error" == "missing_config" ]]; then
      exit 4
    fi
    exit 3
  fi
  sleep 5
done
if [[ "$found_config" == "true" ]]; then
  true
fi
"""

    result = run_shell(
        instance_id,
        region,
        script,
        profile=profile,
        timeout=STAGE_CONFIG_DISCOVERY_TIMEOUT_SECONDS,
        comment="Discover staged config",
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return parse_remote_config(result.stdout)


def format_list(values: List[str]) -> str:
    quoted = ",".join(f"'{value.strip()}'" for value in values if value.strip())
    return f"[{quoted}]"


def build_default_command(
    target: str,
    genome: str,
    jobs: int,
    aligners: List[str],
    dedupers: List[str],
    snv_callers: List[str],
    sv_callers: List[str],
    containerized: bool,
    dry_run: bool,
    extra: Optional[str],
) -> str:
    config_args = [
        f"genome_build={genome}",
        f"aligners={format_list(aligners)}",
        f"dedupers={format_list(dedupers)}",
        f"snv_callers={format_list(snv_callers)}",
    ]
    if sv_callers:
        config_args.append(f"sv_callers={format_list(sv_callers)}")
    command = [
        "DAY_CONTAINERIZED=true" if containerized else "DAY_CONTAINERIZED=false",
        "bin/day_run",
        target,
        "-p",
        "-k",
        f"-j {jobs}",
        "--config",
        " ".join(config_args),
    ]
    if dry_run:
        command.append("-n")
    if extra:
        command.append(extra)
    return " ".join(command)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Clone daylily-omics-analysis and launch a workflow inside tmux.",
    )
    parser.add_argument("--profile", default=os.environ.get("AWS_PROFILE"))
    parser.add_argument("--region", help="AWS region for the cluster")
    parser.add_argument("--cluster", help="ParallelCluster name")
    parser.add_argument(
        "--stage-dir",
        help="Specific staging directory containing *_samples.tsv and *_units.tsv",
    )
    parser.add_argument(
        "--run-context-file",
        help="Local runs.tsv file to write as config/runs.tsv for run-analysis workflows",
    )
    parser.add_argument(
        "--stage-base",
        default="/fsx/staging/staged_external_sequencing_data",
        help="Base staging directory to scan when --stage-dir is omitted",
    )
    parser.add_argument(
        "--no-input-staging",
        dest="input_staging",
        action="store_false",
        help="Do not copy staged samples/units or write a run context before launching",
    )
    parser.add_argument(
        "--no-default-activation",
        dest="default_activation",
        action="store_false",
        help="Do not run the standard dyoainit plus Slurm activation before --dy-command",
    )
    parser.add_argument(
        "--bootstrap-test-config",
        action="store_true",
        help="Copy DayOA bundled test samples and units into config/ before launch",
    )
    parser.add_argument(
        "--session-name",
        help="Name of the tmux session to create on the head node. Defaults to --analysis-id.",
    )
    parser.add_argument(
        "--analysis-id",
        required=True,
        help="Analysis identifier passed to day-clone -d and used under /fsx/analysis_results.",
    )
    parser.add_argument(
        "--executing-entity",
        required=True,
        help="User or system identifier used under /fsx/analysis_results.",
    )
    parser.add_argument(
        "--repository",
        default="daylily-omics-analysis",
        help="Repository key to pass to day-clone",
    )
    parser.add_argument(
        "--git-tag",
        "-t",
        default="main",
        help="Git branch or tag to pass to day-clone",
    )
    parser.add_argument("--project", help="Project/budget to supply to dyoainit")
    parser.add_argument(
        "--skip-project-check",
        dest="skip_project_check",
        action="store_true",
        help="Skip upstream project validation in dyoainit (default for the supported flow)",
    )
    parser.add_argument(
        "--strict-project-check",
        dest="skip_project_check",
        action="store_false",
        help="Enable upstream project validation in dyoainit",
    )
    parser.add_argument("--genome", default="hg38")
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument("--aligners", default="bwa2a")
    parser.add_argument("--dedupers", default="dmd")
    parser.add_argument("--snv-callers", default="deep")
    parser.add_argument("--sv-callers", default="")
    parser.add_argument("--target", default="produce_snv_concordances")
    parser.add_argument("--dy-command", help="Override the dy-r command entirely")
    parser.add_argument("--snakemake-extra", help="Additional arguments appended to dy-r")
    parser.add_argument(
        "--no-containerized",
        action="store_true",
        help="Disable DAY_CONTAINERIZED (enabled by default)",
    )
    parser.add_argument(
        "--export-destination-s3-uri",
        help="Full S3 prefix ending in <executing-entity>/<analysis-id>/ for auto-export",
    )
    parser.add_argument(
        "--export-trigger",
        choices=("none", "on-success", "on-fail", "all"),
        default="none",
        help="Auto-export trigger after the workflow exits",
    )
    parser.add_argument(
        "--delete-on-export-success",
        action="store_true",
        help="Delete the FSx analysis directory after a successful requested export",
    )
    parser.add_argument(
        "--replace-existing-analysis-dir",
        action="store_true",
        help=(
            "Explicit retry mode: remove an existing same analysis directory before "
            "launching. Without this flag, existing analysis directories fail hard."
        ),
    )
    parser.add_argument(
        "--artifact-registration-command-id",
        default="",
        help="Catalog command id whose artifact_registration policy should run after export",
    )
    parser.add_argument(
        "--dewey-url", default="", help="Dewey base URL for post-export registration"
    )
    parser.add_argument(
        "--dewey-token-env",
        default="",
        help="Environment variable containing the Dewey bearer token",
    )
    parser.add_argument(
        "--dewey-analysis-dir-external-object-id",
        default="",
        help="External object id for the exported daylily-omics-analysis S3 directory",
    )
    parser.add_argument(
        "--dewey-run-artifact-euid",
        default="",
        help="Dewey run artifact EUID linked to the exported analysis directory external object",
    )
    parser.add_argument(
        "--dewey-ursa-analysis-euid",
        default="",
        help="Ursa analysis EUID linked to the exported analysis directory external object",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.set_defaults(skip_project_check=True, input_staging=True, default_activation=True)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.profile:
        raise CommandError("AWS profile is required. Set AWS_PROFILE or use --profile.")

    analysis_id = validate_analysis_segment(args.analysis_id, field_name="analysis_id")
    executing_entity = validate_analysis_segment(
        args.executing_entity,
        field_name="executing_entity",
    )
    source_path = analysis_source_path(
        executing_entity=executing_entity,
        analysis_id=analysis_id,
        headnode=True,
    )
    if not args.session_name:
        args.session_name = analysis_id
    if args.export_destination_s3_uri and args.export_trigger == "none":
        raise CommandError("--export-trigger must not be none when auto-export is requested.")
    if args.export_trigger != "none" and not args.export_destination_s3_uri:
        raise CommandError("--export-destination-s3-uri is required when --export-trigger is set.")
    if args.delete_on_export_success and not args.export_destination_s3_uri:
        raise CommandError("--delete-on-export-success requires --export-destination-s3-uri.")
    if args.artifact_registration_command_id and args.export_trigger == "none":
        raise CommandError("--artifact-registration-command-id requires an export trigger.")
    if args.artifact_registration_command_id and not args.dewey_url:
        raise CommandError("--dewey-url is required with --artifact-registration-command-id.")
    if args.artifact_registration_command_id and not args.dewey_token_env:
        raise CommandError("--dewey-token-env is required with --artifact-registration-command-id.")
    if not args.artifact_registration_command_id and (args.dewey_url or args.dewey_token_env):
        raise CommandError(
            "--artifact-registration-command-id is required when Dewey registration options are set."
        )
    dewey_link_options = {
        "--dewey-analysis-dir-external-object-id": args.dewey_analysis_dir_external_object_id,
        "--dewey-run-artifact-euid": args.dewey_run_artifact_euid,
        "--dewey-ursa-analysis-euid": args.dewey_ursa_analysis_euid,
    }
    if any(str(value or "").strip() for value in dewey_link_options.values()):
        missing = [
            option for option, value in dewey_link_options.items() if not str(value or "").strip()
        ]
        if missing:
            raise CommandError(
                "Dewey analysis-directory external-link options must be provided together: "
                + ", ".join(missing)
            )
        if not args.artifact_registration_command_id:
            raise CommandError(
                "--artifact-registration-command-id is required with Dewey external-link options."
            )

    need_cmd("aws")
    need_cmd("pcluster")

    region = resolve_region(args.profile, args.region)
    cluster_name = resolve_cluster(args.profile, region, args.cluster)
    if args.export_destination_s3_uri:
        from daylily_ec.workflow.export_data import (
            _create_session,
            validate_export_destination_s3_uri,
            validate_s3_destination_prefix_empty,
        )

        validate_export_destination_s3_uri(
            args.export_destination_s3_uri,
            source_path=source_path,
        )
        validate_s3_destination_prefix_empty(
            _create_session(region, args.profile).client("s3"),
            args.export_destination_s3_uri,
            source_path=source_path,
        )
    target = resolve_headnode_instance_id(cluster_name, region, profile=args.profile)
    wait_for_ssm_online(target.instance_id, region, profile=args.profile, timeout=120)
    validate_headnode_readiness(
        target.instance_id,
        region,
        profile=args.profile,
        timeout=120,
        comment="Validate DAY-EC headnode readiness before workflow launch",
    )

    run_context_content: Optional[str] = None
    if args.run_context_file:
        if not args.input_staging:
            raise CommandError("--run-context-file cannot be used with --no-input-staging.")
        if args.stage_dir:
            raise CommandError("--stage-dir cannot be used with --run-context-file.")
        run_context_path = Path(args.run_context_file).expanduser()
        if not run_context_path.is_file():
            raise CommandError(f"Run context file not found: {run_context_path}")
        run_context_content = run_context_path.read_text(encoding="utf-8")
        stage_config = None
    elif args.input_staging:
        stage_config = discover_stage_config(
            target.instance_id,
            args.profile,
            region,
            args.stage_dir,
            args.stage_base,
        )
    else:
        if args.stage_dir:
            raise CommandError("--stage-dir cannot be used with --no-input-staging.")
        stage_config = None

    if args.dy_command:
        dy_command = args.dy_command
    else:
        dy_command = build_default_command(
            target=args.target,
            genome=args.genome,
            jobs=args.jobs,
            aligners=args.aligners.split(","),
            dedupers=args.dedupers.split(","),
            snv_callers=args.snv_callers.split(","),
            sv_callers=[value for value in args.sv_callers.split(",") if value],
            containerized=not args.no_containerized,
            dry_run=args.dry_run,
            extra=args.snakemake_extra,
        )

    project_arg = shlex.quote(args.project) if args.project else ""
    repository_literal = json.dumps(args.repository)
    dy_command_literal = shlex.quote(dy_command)
    skip_check = "true" if args.skip_project_check else "false"
    run_context_mode = run_context_content is not None
    run_context_mode_literal = "true" if run_context_mode else "false"
    input_staging_mode_literal = "true" if args.input_staging else "false"
    default_activation_literal = "true" if args.default_activation else "false"
    bootstrap_test_config_literal = "true" if args.bootstrap_test_config else "false"
    run_context_payload = shlex.quote(run_context_content or "")
    export_destination_literal = shlex.quote(args.export_destination_s3_uri or "")
    delete_on_export_success = "true" if args.delete_on_export_success else "false"
    replace_existing_analysis_dir = "true" if args.replace_existing_analysis_dir else "false"
    if stage_config is None:
        stage_samples_path = ""
        stage_units_path = ""
    else:
        stage_samples_path = stage_config.samples_path
        stage_units_path = stage_config.units_path
    write_status_python = shlex.quote(
        "import json, os, pathlib; "
        "path = pathlib.Path(os.environ['DAYLILY_STATUS_FILE']); "
        "exit_code_raw = os.environ.get('DAYLILY_STATUS_EXIT_CODE', ''); "
        "exit_code = None if exit_code_raw in ('', '__PENDING__') else "
        "(int(exit_code_raw) if exit_code_raw.lstrip('-').isdigit() else exit_code_raw); "
        "payload = dict("
        "session_name=os.environ['DAYLILY_STATUS_SESSION'], "
        "repo_path=os.environ['DAYLILY_STATUS_REPO_PATH'], "
        "started_at=os.environ.get('DAYLILY_STATUS_STARTED_AT') or None, "
        "completed_at=os.environ.get('DAYLILY_STATUS_COMPLETED_AT') or None, "
        "exit_code=exit_code, "
        "command=os.environ['DAYLILY_STATUS_COMMAND']); "
        "path.parent.mkdir(parents=True, exist_ok=True); "
        "path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\\n', encoding='utf-8')"
    )

    pipeline_script = f"""
set -euo pipefail
if [[ "$(id -un)" != "ubuntu" ]]; then
  echo "__DAYLILY_ERROR__=wrong_user"
  exit 6
	fi
	SESSION_NAME={shlex.quote(args.session_name)}
	ANALYSIS_ID={shlex.quote(analysis_id)}
	EXECUTING_ENTITY={shlex.quote(executing_entity)}
	RUN_CONTEXT_MODE={run_context_mode_literal}
	INPUT_STAGING_MODE={input_staging_mode_literal}
	DEFAULT_ACTIVATION={default_activation_literal}
	BOOTSTRAP_TEST_CONFIG={bootstrap_test_config_literal}
	RUN_CONTEXT_PAYLOAD={run_context_payload}
	STAGE_SAMPLES={shlex.quote(stage_samples_path)}
	STAGE_UNITS={shlex.quote(stage_units_path)}
	PROJECT_VALUE={project_arg if project_arg else ""}
	SKIP_PROJECT_CHECK={skip_check}
	DY_COMMAND={dy_command_literal}
	EXPORT_DESTINATION_S3_URI={export_destination_literal}
	EXPORT_TRIGGER={shlex.quote(args.export_trigger)}
	DELETE_ON_EXPORT_SUCCESS={delete_on_export_success}
	REPLACE_EXISTING_ANALYSIS_DIR={replace_existing_analysis_dir}
	ARTIFACT_REGISTRATION_COMMAND_ID={shlex.quote(args.artifact_registration_command_id)}
	DEWEY_URL={shlex.quote(args.dewey_url)}
	DEWEY_TOKEN_ENV={shlex.quote(args.dewey_token_env)}
	DEWEY_ANALYSIS_DIR_EXTERNAL_OBJECT_ID={shlex.quote(args.dewey_analysis_dir_external_object_id)}
	DEWEY_RUN_ARTIFACT_EUID={shlex.quote(args.dewey_run_artifact_euid)}
	DEWEY_URSA_ANALYSIS_EUID={shlex.quote(args.dewey_ursa_analysis_euid)}
STATUS_FILE="${{DAYLILY_RUN_DIR}}/status.json"
TMUX_LOG="${{DAYLILY_TMUX_LOG}}"

write_status() {{
  python3 -c {write_status_python}
}}

export DAYLILY_STATUS_FILE="$STATUS_FILE"
export DAYLILY_STATUS_SESSION="$SESSION_NAME"
export DAYLILY_STATUS_REPO_PATH="${{DAYLILY_REPO_PATH}}"
export DAYLILY_STATUS_COMMAND="$DY_COMMAND"
export DAYLILY_STATUS_STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
export DAYLILY_STATUS_COMPLETED_AT=""
export DAYLILY_STATUS_EXIT_CODE="__PENDING__"
write_status

trap 'status=$?; if [[ "${{DAYLILY_STATUS_FINALIZED:-0}}" != "1" ]]; then export DAYLILY_STATUS_COMPLETED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; export DAYLILY_STATUS_EXIT_CODE="$status"; write_status; fi' EXIT

clone_root="$(dirname "${{DAYLILY_REPO_PATH}}")"
repo_path="${{DAYLILY_REPO_PATH}}"
mkdir -p "$(dirname "$clone_root")"
day-clone \
  --destination "$ANALYSIS_ID" \
  --executing-entity "$EXECUTING_ENTITY" \
  --repository {shlex.quote(args.repository)} \
  --git-tag {shlex.quote(args.git_tag)}
	cd "$repo_path"
	mkdir -p config

extract_runtime_config_path() {{
  local key="$1"
  python3 - "$key" "$DY_COMMAND" <<'PYCONFIGPATH'
import shlex
import sys

key = sys.argv[1]
command = sys.argv[2]
try:
    args = shlex.split(command)
except ValueError as exc:
    print(f"[ERROR] Could not parse DY_COMMAND for runtime config: {{exc}}", file=sys.stderr)
    raise SystemExit(2)

for index, arg in enumerate(args):
    if arg != "--config":
        continue
    for item in args[index + 1:]:
        if item.startswith("-"):
            break
        if "=" not in item:
            continue
        name, value = item.split("=", 1)
        if name == key:
            print(value)
            raise SystemExit(0)
raise SystemExit(0)
PYCONFIGPATH
}}

materialize_runtime_table() {{
  local key="$1"
  local target="$2"
  local source_path
  source_path="$(extract_runtime_config_path "$key")"
  if [[ -z "$source_path" ]]; then
    return 0
  fi
  if [[ ! -f "$source_path" ]]; then
    echo "[ERROR] Runtime config $key points to missing file: $source_path"
    exit 12
  fi
  cp -- "$source_path" "$target"
}}

bootstrap_test_config() {{
  local samples_source=".test_data/data/0.01xwgs_HG002_hg38.samples.tsv"
  local units_source=".test_data/data/0.01xwgs_HG002_hg38.units.tsv"
  if [[ ! -f "$samples_source" ]]; then
    echo "[ERROR] Missing DayOA test samples table: $samples_source"
    exit 12
  fi
  if [[ ! -f "$units_source" ]]; then
    echo "[ERROR] Missing DayOA test units table: $units_source"
    exit 12
  fi
  cp -- "$samples_source" config/samples.tsv
  cp -- "$units_source" config/units.tsv
  echo "[INFO] Bootstrapped DayOA test samples and units tables."
}}

bclconvert_runtime_tables_requested() {{
  case "$DY_COMMAND" in
    *produce_bclconvert_fastqs*|*produce_bclconvert_fastqs_and_metrics*|*produce_illumina_run_qc_and_bclconvert*|*run_bclconvert*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}}

generate_bclconvert_runtime_tables() {{
  python3 - <<'PYBCLTABLES'
import csv
from pathlib import Path

runs_path = Path("config/runs.tsv")
if not runs_path.is_file():
    raise SystemExit("[ERROR] BCL Convert bootstrap requires config/runs.tsv")

with runs_path.open(newline="", encoding="utf-8-sig") as handle:
    runs = list(csv.DictReader(handle, delimiter="\t"))

run_row = next((row for row in runs if str(row.get("PLATFORM", "")).upper() == "ILMN"), None)
if run_row is None:
    raise SystemExit("[ERROR] BCL Convert bootstrap requires an ILMN run row in config/runs.tsv")

run_id = str(run_row.get("RUNID", "")).strip()
sample_sheet = Path(str(run_row.get("SAMPLE_SHEET", "")).strip())
if not run_id:
    raise SystemExit("[ERROR] BCL Convert bootstrap ILMN run row is missing RUNID")
if not sample_sheet.is_file():
    raise SystemExit(f"[ERROR] BCL Convert sample sheet not found: {{sample_sheet}}")

sample_ids = []
in_data = False
header = None
sample_index = None
with sample_sheet.open(encoding="utf-8-sig") as handle:
    for raw_line in handle:
        line = raw_line.rstrip("\\r\\n")
        stripped = line.strip()
        if stripped == "[BCLConvert_Data]":
            in_data = True
            header = None
            sample_index = None
            continue
        if in_data and stripped.startswith("[") and stripped.endswith("]"):
            break
        if not in_data or not stripped:
            continue
        fields = [field.strip() for field in line.split(",")]
        if header is None:
            header = fields
            try:
                sample_index = header.index("Sample_ID")
            except ValueError as exc:
                raise SystemExit("[ERROR] BCLConvert_Data is missing Sample_ID") from exc
            continue
        if sample_index is None or sample_index >= len(fields):
            continue
        sample_id = fields[sample_index].strip()
        if sample_id:
            sample_ids.append(sample_id)

deduped_sample_ids = list(dict.fromkeys(sample_ids))
if not deduped_sample_ids:
    raise SystemExit(f"[ERROR] No Sample_ID rows found in {{sample_sheet}}")

samples_header = [
    "SAMPLEID",
    "SAMPLESOURCE",
    "SAMPLECLASS",
    "BIOLOGICAL_SEX",
    "CONCORDANCE_CONTROL_PATH",
    "IS_POSITIVE_CONTROL",
    "IS_NEGATIVE_CONTROL",
    "SAMPLE_TYPE",
    "TUM_NRM_SAMPLEID_MATCH",
    "EXTERNAL_SAMPLE_ID",
    "N_X",
    "N_Y",
    "TRUTH_DATA_DIR",
]
with Path("config/samples.tsv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle, delimiter="\t", lineterminator="\\n")
    writer.writerow(samples_header)
    for sample_id in deduped_sample_ids:
        is_negative = str(sample_id).upper() in {{"NTC", "NEGATIVE_CONTROL"}}
        writer.writerow(
            [
                sample_id,
                "control" if is_negative else "blood",
                "control" if is_negative else "research",
                "unknown",
                "na",
                "false",
                "true" if is_negative else "false",
                "control" if is_negative else "blood",
                "na",
                sample_id,
                "na",
                "na",
                "na",
            ]
        )

units_path = Path("config/units.tsv")
if units_path.exists():
    units_path.unlink()

print(
    f"[INFO] Wrote BCL Convert bootstrap samples for {{len(deduped_sample_ids)}} samples from {{sample_sheet}}; units table left absent for DayOA bootstrap"
)
PYBCLTABLES
}}

patch_bclconvert_profile_config() {{
  python3 - <<'PYBCLPROFILE'
import csv
import os
import re
from pathlib import Path

runs_path = Path("config/runs.tsv")
if not runs_path.is_file():
    raise SystemExit("[ERROR] BCL Convert S3 staging requires config/runs.tsv")

with runs_path.open(newline="", encoding="utf-8-sig") as handle:
    runs = list(csv.DictReader(handle, delimiter="\t"))

run_row = next((row for row in runs if str(row.get("PLATFORM", "")).upper() == "ILMN"), None)
if run_row is None:
    raise SystemExit("[ERROR] BCL Convert S3 staging requires an ILMN run row in config/runs.tsv")

run_id = str(run_row.get("RUNID", "")).strip() or "<unknown-run>"

profile_dir = os.environ.get("DAY_PROFILE_DIR", "")
if not profile_dir:
    raise SystemExit("[ERROR] DAY_PROFILE_DIR is not set; cannot patch BCL Convert profile config")

rule_config = Path(profile_dir) / "rule_config.yaml"
if not rule_config.is_file():
    raise SystemExit(f"[ERROR] Missing DayOA profile rule config: {{rule_config}}")

lines = rule_config.read_text(encoding="utf-8").splitlines(keepends=True)
bcl_start = None
bcl_indent = None
for index, line in enumerate(lines):
    match = re.match(r"^(\\s*)bclconvert:\\s*(?:#.*)?$", line)
    if match:
        bcl_start = index
        bcl_indent = len(match.group(1))
        break
if bcl_start is None or bcl_indent is None:
    raise SystemExit(f"[ERROR] Missing bclconvert block in {{rule_config}}")

bcl_end = len(lines)
for index in range(bcl_start + 1, len(lines)):
    stripped = lines[index].strip()
    if not stripped or lines[index].lstrip().startswith("#"):
        continue
    indent = len(lines[index]) - len(lines[index].lstrip())
    if indent <= bcl_indent:
        bcl_end = index
        break

def replace_required_scalar(key, value):
    target_index = None
    for index in range(bcl_start + 1, bcl_end):
        if re.match(rf"^\\s+{{re.escape(key)}}\\s*:", lines[index]):
            target_index = index
            break
    if target_index is None:
        raise SystemExit(f"[ERROR] Missing bclconvert.{{key}} in {{rule_config}}")
    indent = re.match(r"^(\\s*)", lines[target_index]).group(1)
    lines[target_index] = f'{{indent}}{{key}}: "{{value}}"\\n'

scratch_root = str(Path.cwd() / ".bclconvert_scratch")
replace_required_scalar("staging_mode", "mounted_dev_shm")
replace_required_scalar("scratch_root", scratch_root)
replace_required_scalar("tmpdir", scratch_root)
replace_required_scalar("scratch_size_multiplier", "1")
replace_required_scalar("force", "true")
rule_config.write_text("".join(lines), encoding="utf-8")
print(
    f"[INFO] Patched {{rule_config}} bclconvert repo-local mounted scratch at {{scratch_root}} for {{run_id}}"
)
PYBCLPROFILE
}}

patch_bclconvert_scratch_output_move() {{
  python3 - <<'PYBCLMOVE'
from pathlib import Path

path = Path("workflow/rules/bclconvert.smk")
if not path.is_file():
    raise SystemExit(f"[ERROR] BCL Convert scratch-output repair target missing: {{path}}")

old = (
    '        if [ "$staging_mode" = "dev_shm" ] || [ "$staging_mode" = "mounted_dev_shm" ] || [ "$staging_mode" = "s3_dev_shm" ] || [ "$staging_mode" = "output_dev_shm" ]; then\\n'
    '            echo "Copying BCLConvert outputs from scratch to result tree: $(date -Is)" >> {{log:q}}\\n'
    '            cp -a "$effective_output_dir"/. {{BCL_FASTQ_DIR:q}}/\\n'
    '            df -h "$scratch_root" {{BCL_FASTQ_DIR:q}} >> {{log:q}} 2>&1 || true\\n'
    "        fi"
)
new = (
    '        if [ "$staging_mode" = "dev_shm" ] || [ "$staging_mode" = "mounted_dev_shm" ] || [ "$staging_mode" = "s3_dev_shm" ] || [ "$staging_mode" = "output_dev_shm" ]; then\\n'
    '            echo "Moving BCLConvert outputs from scratch to result tree: $(date -Is)" >> {{log:q}}\\n'
    "            rm -rf {{BCL_FASTQ_DIR:q}}\\n"
    "            mkdir -p $(dirname {{BCL_FASTQ_DIR:q}})\\n"
    '            mv "$effective_output_dir" {{BCL_FASTQ_DIR:q}}\\n'
    '            if [ -n "${{{{scratch_run_dir:-}}}}" ] && [ -d "$scratch_run_dir" ]; then\\n'
    '                echo "Removing staged BCL input scratch: $scratch_run_dir $(date -Is)" >> {{log:q}}\\n'
    '                rm -rf "$scratch_run_dir"\\n'
    "            fi\\n"
    '            df -h "$scratch_root" {{BCL_FASTQ_DIR:q}} >> {{log:q}} 2>&1 || true\\n'
    "        fi"
)

text = path.read_text(encoding="utf-8")
if new in text:
    print(f"[INFO] BCL Convert scratch-output move repair already present: {{path}}")
    raise SystemExit(0)
if old not in text:
    raise SystemExit(f"[ERROR] BCL Convert scratch-output repair target not found in {{path}}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print(f"[INFO] Patched BCL Convert scratch-output move repair: {{path}}")
PYBCLMOVE
}}

ultima_run_qc_config_requested() {{
  case "$DY_COMMAND" in
    *produce_ultima_run_qc*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}}

append_ultima_run_qc_config() {{
  local extra_config
  extra_config="$(python3 - <<'PYULTIMACFG'
import csv
import json
import shlex
import subprocess
import sys
from pathlib import Path

runs_path = Path("config/runs.tsv")
if not runs_path.is_file():
    raise SystemExit("[ERROR] Ultima run QC requires config/runs.tsv")

with runs_path.open(newline="", encoding="utf-8-sig") as handle:
    runs = list(csv.DictReader(handle, delimiter="\t"))

run_row = next((row for row in runs if str(row.get("PLATFORM", "")).upper() == "ULTIMA"), None)
if run_row is None:
    raise SystemExit("[ERROR] Ultima run QC requires a ULTIMA run row in config/runs.tsv")

source_s3_uri = str(run_row.get("SOURCE_S3_URI", "")).strip()
if not source_s3_uri.startswith("s3://"):
    raise SystemExit("[ERROR] Ultima run QC requires SOURCE_S3_URI in config/runs.tsv")
metrics_path = str(run_row.get("METRICS_PATH", "")).strip()
metrics_s3_uri = str(run_row.get("METRICS_S3_URI", "")).strip()
if metrics_s3_uri:
    if not metrics_s3_uri.startswith("s3://"):
        raise SystemExit("[ERROR] Ultima run QC METRICS_S3_URI must be an s3:// URI")
    metrics_path = "config/ultima_run_qc_metrics.csv"
    try:
        subprocess.run(
            ["aws", "s3", "cp", metrics_s3_uri, metrics_path],
            check=True,
            stdout=sys.stderr,
            stderr=sys.stderr,
        )
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            f"[ERROR] Failed to copy Ultima run QC METRICS_S3_URI: {{exc.returncode}}"
        ) from exc
if not metrics_path:
    raise SystemExit(
        "[ERROR] Ultima run QC requires METRICS_PATH or METRICS_S3_URI in config/runs.tsv"
    )
if not Path(metrics_path).is_file():
    raise SystemExit(f"[ERROR] Ultima run QC metrics file not found: {{metrics_path}}")
if Path(metrics_path).stat().st_size == 0:
    raise SystemExit(f"[ERROR] Ultima run QC metrics file is empty: {{metrics_path}}")

payload = "run_qc=" + json.dumps(
    {{"ultima": {{"run_s3_uri": source_s3_uri, "metrics_path": metrics_path}}}},
    separators=(",", ":"),
)
print(shlex.quote(payload))
PYULTIMACFG
)"
  DY_COMMAND="$DY_COMMAND --config $extra_config"
}}

ont_run_qc_runtime_repair_requested() {{
  case "$DY_COMMAND" in
    *produce_ont_run_qc*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}}

patch_pycoqc_readonly_sort() {{
  python3 - <<'PYPYCOQC'
from pathlib import Path

roots = [Path("/fsx/resources/environments/conda/ubuntu")]
matches = []
for root in roots:
    if root.exists():
        matches.extend(root.glob("**/site-packages/pycoQC/pycoQC_plot.py"))

if not matches:
    print("[INFO] No installed pycoQC environment found for readonly-sort repair.")
    raise SystemExit(0)

old = (
    "data = data.dropna().values\\n"
    "        data.sort()\\n"
    "        half_sum = data.sum()/2\\n"
    "        cum_sum = 0\\n"
    "        for v in data:\\n"
    "            cum_sum += v\\n"
    "            if cum_sum >= half_sum:\\n"
    "                return int(v)"
)
readonly_only = (
    "data = data.dropna().to_numpy(copy=True)\\n"
    "        data.sort()\\n"
    "        half_sum = data.sum()/2\\n"
    "        cum_sum = 0\\n"
    "        for v in data:\\n"
    "            cum_sum += v\\n"
    "            if cum_sum >= half_sum:\\n"
    "                return int(v)"
)
new = (
    'data = data.dropna().astype("int64").to_numpy(copy=True)\\n'
    "        data.sort()\\n"
    "        half_sum = int(data.sum())/2\\n"
    "        cum_sum = 0\\n"
    "        for v in data:\\n"
    "            cum_sum += int(v)\\n"
    "            if cum_sum >= half_sum:\\n"
    "                return int(v)\\n"
    "        return 0"
)

for path in sorted(set(matches)):
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"[INFO] pycoQC readonly-sort repair already present: {{path}}")
        continue
    if readonly_only in text:
        target = readonly_only
    elif old in text:
        target = old
    else:
        raise SystemExit(
            f"[ERROR] pycoQC readonly-sort repair target not found in {{path}}"
        )
    path.write_text(text.replace(target, new, 1), encoding="utf-8")
    print(f"[INFO] Patched pycoQC readonly-sort repair: {{path}}")
PYPYCOQC
}}

goleft_indexcov_runtime_repair_requested() {{
  case "$DY_COMMAND" in
    *produce_alignstats*|*produce_multiqc_all*|*produce_relatedness*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}}

patch_goleft_indexcov_empty_sex_arg() {{
  python3 - <<'PYGOLEFT'
from pathlib import Path

path = Path("workflow/rules/go_left.smk")
if not path.is_file():
    raise SystemExit(f"[ERROR] goleft runtime repair target missing: {{path}}")

old_with_sex = (
    "        goleft indexcov --directory $gl --sex {{params.sexchrms:q}} "
    "--fai {{params.huref}}.fai {{input.crai}} >> {{log}} 2>&1;"
)
old_without_sex = (
    "        goleft indexcov --directory $gl "
    "--fai {{params.huref}}.fai {{input.crai}} >> {{log}} 2>&1;"
)
new = (
    "        set +e\\n"
    "        goleft indexcov --directory $gl "
    "--fai {{params.huref}}.fai {{input.crai}} >> {{log}} 2>&1\\n"
    "        goleft_status=$?\\n"
    "        set -e\\n"
    '        if [[ "$goleft_status" != "0" ]]; then\\n'
    "            if grep -Eiq 'no usable chroms?omes|no usable chromosomes' {{log}}; then\\n"
    "                printf 'DYEC_RUNTIME_REPAIR: goleft skipped because input CRAI has no usable chromosomes.\\\\n' >> {{log}}\\n"
    "            else\\n"
    '                exit "$goleft_status"\\n'
    "            fi\\n"
    "        fi"
)

text = path.read_text(encoding="utf-8")
if new in text:
    print(f"[INFO] goleft empty-sex/no-usable-chromosomes repair already present: {{path}}")
    raise SystemExit(0)
if old_with_sex in text:
    text = text.replace(old_with_sex, new, 1)
elif old_without_sex in text:
    text = text.replace(old_without_sex, new, 1)
else:
    raise SystemExit(f"[ERROR] goleft runtime repair target not found in {{path}}")
path.write_text(text, encoding="utf-8")
print(f"[INFO] Patched goleft empty-sex/no-usable-chromosomes repair: {{path}}")
PYGOLEFT
}}

mosdepth_empty_output_runtime_repair_requested() {{
  case "$DY_COMMAND" in
    *produce_alignstats*|*produce_multiqc_all*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}}

patch_mosdepth_empty_outputs() {{
  python3 - <<'PYMOSDEPTH'
from pathlib import Path

path = Path("workflow/rules/mosdepth.smk")
if not path.is_file():
    raise SystemExit(f"[ERROR] mosdepth runtime repair target missing: {{path}}")

old = (
    "        test -s {{output.summary:q}} || (printf 'ERROR: mosdepth summary output is missing or empty: %s\\\\n' {{output.summary:q}} | tee -a {{log.a:q}} >&2; exit 1)\\n"
    "        test -s {{output.global_dist:q}} || (printf 'ERROR: mosdepth global_dist output is missing or empty: %s\\\\n' {{output.global_dist:q}} | tee -a {{log.a:q}} >&2; exit 1)\\n"
    "        test -s {{output.region_dist:q}} || (printf 'ERROR: mosdepth region_dist output is missing or empty: %s\\\\n' {{output.region_dist:q}} | tee -a {{log.a:q}} >&2; exit 1)"
)
new = (
    "        if [ ! -s {{output.summary:q}} ]; then\\n"
    "            printf 'chrom\\\\tlength\\\\tbases\\\\tmean\\\\tmin\\\\tmax\\\\ntotal\\\\t0\\\\t0\\\\t0\\\\t0\\\\t0\\\\n' > {{output.summary:q}}\\n"
    "            printf 'DYEC_RUNTIME_REPAIR: mosdepth emitted no summary; wrote zero-coverage sentinel.\\\\n' >> {{log.a:q}}\\n"
    "        fi\\n"
    "        if [ ! -s {{output.global_dist:q}} ]; then\\n"
    "            printf 'total\\\\t0\\\\t1\\\\n' > {{output.global_dist:q}}\\n"
    "            printf 'DYEC_RUNTIME_REPAIR: mosdepth emitted no global distribution; wrote zero-coverage sentinel.\\\\n' >> {{log.a:q}}\\n"
    "        fi\\n"
    "        if [ ! -s {{output.region_dist:q}} ]; then\\n"
    "            printf 'total\\\\t0\\\\t1\\\\n' > {{output.region_dist:q}}\\n"
    "            printf 'DYEC_RUNTIME_REPAIR: mosdepth emitted no region distribution; wrote zero-coverage sentinel.\\\\n' >> {{log.a:q}}\\n"
    "        fi"
)

text = path.read_text(encoding="utf-8")
if new in text:
    print(f"[INFO] mosdepth empty-output repair already present: {{path}}")
    raise SystemExit(0)
if old not in text:
    raise SystemExit(f"[ERROR] mosdepth empty-output repair target not found in {{path}}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print(f"[INFO] Patched mosdepth empty-output repair: {{path}}")
PYMOSDEPTH
}}

rtg_vcfeval_parse_runtime_repair_requested() {{
  case "$DY_COMMAND" in
    *produce_snv_concordances*|*produce_multiqc_all*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}}

patch_rtg_vcfeval_parse_output_dir() {{
  python3 - <<'PYRTGPARSE'
from pathlib import Path

path = Path("workflow/rules/rtg_vcfeval.smk")
if not path.is_file():
    raise SystemExit(f"[ERROR] RTG vcfeval runtime repair target missing: {{path}}")

old = (
    '            export DAYLILY_BCFTOOLS_THREADS="{{threads}}"\\n'
    "\\n"
    "            python workflow/scripts/parse-vcfeval-summary.py \\\\\\n"
)
new = (
    '            export DAYLILY_BCFTOOLS_THREADS="{{threads}}"\\n'
    "\\n"
    '            mkdir -p "$(dirname {{output.mqc}})"\\n'
    "\\n"
    "            python workflow/scripts/parse-vcfeval-summary.py \\\\\\n"
)

text = path.read_text(encoding="utf-8")
if new in text:
    print(f"[INFO] RTG vcfeval parse output-dir repair already present: {{path}}")
    raise SystemExit(0)
if old not in text:
    raise SystemExit(f"[ERROR] RTG vcfeval parse output-dir repair target not found in {{path}}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print(f"[INFO] Patched RTG vcfeval parse output-dir repair: {{path}}")
PYRTGPARSE
}}

vep_zero_variant_runtime_repair_requested() {{
  case "$DY_COMMAND" in
    *produce_vep*|*produce_multiqc_all*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}}

patch_vep_empty_concat_fofn() {{
  python3 - <<'PYVEPZERO'
from pathlib import Path

path = Path("workflow/rules/vep.smk")
if not path.is_file():
    raise SystemExit(f"[ERROR] VEP runtime repair target missing: {{path}}")

old = (
    "        if [ ! -s {{params.tmp_fofn}} ]; then\\n"
    '            echo "ERROR: no non-empty VEP chromosome chunks to concatenate" >&2\\n'
    "            exit 2\\n"
    "        fi\\n"
    "        mv {{params.tmp_fofn}} {{output.fofn}}"
)
new = (
    "        if [ ! -s {{params.tmp_fofn}} ]; then\\n"
    "            for count_path in {{input.ann_counts}}; do\\n"
    '                echo "${{{{count_path%.record_count}}}}" >> {{params.tmp_fofn}}\\n'
    "                break\\n"
    "            done\\n"
    "        fi\\n"
    "        mv {{params.tmp_fofn}} {{output.fofn}}"
)

text = path.read_text(encoding="utf-8")
if new in text:
    print(f"[INFO] VEP zero-variant concat repair already present: {{path}}")
    raise SystemExit(0)
if old not in text:
    raise SystemExit(f"[ERROR] VEP zero-variant concat repair target not found in {{path}}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print(f"[INFO] Patched VEP zero-variant concat repair: {{path}}")
PYVEPZERO
}}

contam_identity_zero_variant_runtime_repair_requested() {{
  case "$DY_COMMAND" in
    *produce_global_contam_check*|*produce_haplocheck_contam_identity*|*produce_read_haps_contam_identity*|*contam_identity*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}}

patch_contam_identity_zero_variant_outputs() {{
  python3 - <<'PYCONTAMZERO'
from pathlib import Path

path = Path("workflow/rules/contam_identity.smk")
if not path.is_file():
    raise SystemExit(f"[ERROR] contamination identity runtime repair target missing: {{path}}")

hap_old = (
    "        {{params.command:q}} --out \\"$result_prefix\\" --raw {{input.vcf:q}} > {{log:q}} 2>&1\\n"
    '        test -s "$result_dir/contamination.txt"\\n'
    '        test -s "$result_dir/contamination.raw.txt"\\n'
    '        test -s "$result_dir/contamination.html"\\n'
    '        cp "$result_dir/contamination.txt" {{output.contamination:q}}\\n'
    '        cp "$result_dir/contamination.raw.txt" {{output.raw:q}}\\n'
    '        cp "$result_dir/contamination.html" {{output.html:q}}'
)
hap_new = (
    "        set +o pipefail\\n"
    "        if gzip -cd {{input.vcf:q}} | grep -m 1 -q -v '^#'; then\\n"
    "            has_variants=true\\n"
    "        else\\n"
    "            has_variants=false\\n"
    "        fi\\n"
    "        set -o pipefail\\n"
    '        if [[ "$has_variants" == "true" ]]; then\\n'
    "            set +e\\n"
    "            {{params.command:q}} --out \\"$result_prefix\\" --raw {{input.vcf:q}} > {{log:q}} 2>&1\\n"
    "            haplocheck_rc=$?\\n"
    "            set -e\\n"
    "            if grep -q 'outside the range.*rCRS only' {{log:q}}; then\\n"
    "                printf 'SampleID\\tContamination Status\\tContamination Level\\tDistance\\tSample Coverage\\tMajor Haplogroup\\tMinor Haplogroup\\n%s\\tUNSUPPORTED_REFERENCE\\t0\\t\\t0\\t\\t\\n' {{wildcards.sample:q}} > {{output.contamination:q}}\\n"
    "                printf 'SampleID\\tContamination Status\\tContamination Level\\tDistance\\tSample Coverage\\tMajor Haplogroup\\tMinor Haplogroup\\n%s\\tUNSUPPORTED_REFERENCE\\t0\\t\\t0\\t\\t\\n' {{wildcards.sample:q}} > {{output.raw:q}}\\n"
    "                printf '<html><body>UNSUPPORTED_REFERENCE</body></html>\\n' > {{output.html:q}}\\n"
    "                printf 'UNSUPPORTED_REFERENCE: haplocheck skipped because the input VCF is not restricted to rCRS positions.\\n' >> {{log:q}}\\n"
    '            elif [[ "$haplocheck_rc" -eq 0 ]]; then\\n'
    '                test -s "$result_dir/contamination.txt"\\n'
    '                test -s "$result_dir/contamination.raw.txt"\\n'
    '                test -s "$result_dir/contamination.html"\\n'
    '                cp "$result_dir/contamination.txt" {{output.contamination:q}}\\n'
    '                cp "$result_dir/contamination.raw.txt" {{output.raw:q}}\\n'
    '                cp "$result_dir/contamination.html" {{output.html:q}}\\n'
    "            else\\n"
    '                exit "$haplocheck_rc"\\n'
    "            fi\\n"
    "        else\\n"
    "            printf 'SampleID\\tContamination Status\\tContamination Level\\tDistance\\tSample Coverage\\tMajor Haplogroup\\tMinor Haplogroup\\n%s\\tNO_VARIANTS\\t0\\t\\t0\\t\\t\\n' {{wildcards.sample:q}} > {{output.contamination:q}}\\n"
    "            printf 'SampleID\\tContamination Status\\tContamination Level\\tDistance\\tSample Coverage\\tMajor Haplogroup\\tMinor Haplogroup\\n%s\\tNO_VARIANTS\\t0\\t\\t0\\t\\t\\n' {{wildcards.sample:q}} > {{output.raw:q}}\\n"
    "            printf '<html><body>NO_VARIANTS</body></html>\\n' > {{output.html:q}}\\n"
    "            printf 'NO_VARIANTS: haplocheck skipped because the input VCF has no variant records.\\n' > {{log:q}}\\n"
    "        fi"
)

read_haps_original_old = (
    "        command -v {{params.command:q}} > /dev/null\\n"
    "        test -s {{params.reliable_snp_file:q}}\\n"
    "        {{params.command:q}} {{params.extra_args}} -fa {{params.ref:q}} {{input.bam:q}} {{params.reliable_snp_file:q}} {{input.vcf:q}} > {{output.txt:q}} 2> {{log:q}}\\n"
    "        test -s {{output.txt:q}}\\n"
    "        grep -q 'PASS_FAIL' {{output.txt:q}}\\n"
    "        grep -q 'REASON' {{output.txt:q}}"
)
read_haps_partial_old = (
    "        command -v {{params.command:q}} > /dev/null\\n"
    "        test -s {{params.reliable_snp_file:q}}\\n"
    "        set +o pipefail\\n"
    "        if gzip -cd {{input.vcf:q}} | grep -m 1 -q -v '^#'; then\\n"
    "            has_variants=true\\n"
    "        else\\n"
    "            has_variants=false\\n"
    "        fi\\n"
    "        set -o pipefail\\n"
    '        if [[ "$has_variants" == "true" ]]; then\\n'
    "            {{params.command:q}} {{params.extra_args}} -fa {{params.ref:q}} {{input.bam:q}} {{params.reliable_snp_file:q}} {{input.vcf:q}} > {{output.txt:q}} 2> {{log:q}}\\n"
    "        else\\n"
    "            printf 'SNP_PAIRS ERROR_PAIRS DOUBLE_ERROR_PAIR_COUNT DOUBLE_ERROR_FRACTION REL_ERROR_FRACTION NONSENSE_FRACTION PASS_FAIL REASON\\n0 0 0 0 0 0 NO_DATA NO_VARIANTS\\n' > {{output.txt:q}}\\n"
    "            printf 'NO_VARIANTS: read_haps skipped because the input VCF has no variant records.\\n' > {{log:q}}\\n"
    "        fi\\n"
    "        test -s {{output.txt:q}}\\n"
    "        grep -q 'PASS_FAIL' {{output.txt:q}}\\n"
    "        grep -q 'REASON' {{output.txt:q}}"
)
read_haps_empty_failure_old = (
    "        set +o pipefail\\n"
    "        if gzip -cd {{input.vcf:q}} | grep -m 1 -q -v '^#'; then\\n"
    "            has_variants=true\\n"
    "        else\\n"
    "            has_variants=false\\n"
    "        fi\\n"
    "        set -o pipefail\\n"
    '        if [[ "$has_variants" == "true" ]]; then\\n'
    "            command -v {{params.command:q}} > /dev/null\\n"
    "            test -s {{params.reliable_snp_file:q}}\\n"
    "            {{params.command:q}} {{params.extra_args}} -fa {{params.ref:q}} {{input.bam:q}} {{params.reliable_snp_file:q}} {{input.vcf:q}} > {{output.txt:q}} 2> {{log:q}}\\n"
    "        else\\n"
    "            printf 'SNP_PAIRS ERROR_PAIRS DOUBLE_ERROR_PAIR_COUNT DOUBLE_ERROR_FRACTION REL_ERROR_FRACTION NONSENSE_FRACTION PASS_FAIL REASON\\n0 0 0 0 0 0 NO_DATA NO_VARIANTS\\n' > {{output.txt:q}}\\n"
    "            printf 'NO_VARIANTS: read_haps skipped because the input VCF has no variant records.\\n' > {{log:q}}\\n"
    "        fi\\n"
    "        test -s {{output.txt:q}}\\n"
    "        grep -q 'PASS_FAIL' {{output.txt:q}}\\n"
    "        grep -q 'REASON' {{output.txt:q}}"
)
read_haps_new = (
    "        set +o pipefail\\n"
    "        if gzip -cd {{input.vcf:q}} | grep -m 1 -q -v '^#'; then\\n"
    "            has_variants=true\\n"
    "        else\\n"
    "            has_variants=false\\n"
    "        fi\\n"
    "        set -o pipefail\\n"
    '        if [[ "$has_variants" == "true" ]]; then\\n'
    "            command -v {{params.command:q}} > /dev/null\\n"
    "            test -s {{params.reliable_snp_file:q}}\\n"
    "            set +e\\n"
    "            {{params.command:q}} {{params.extra_args}} -fa {{params.ref:q}} {{input.bam:q}} {{params.reliable_snp_file:q}} {{input.vcf:q}} > {{output.txt:q}} 2> {{log:q}}\\n"
    "            read_haps_rc=$?\\n"
    "            set -e\\n"
    "            if [[ \"$read_haps_rc\" != \"0\" ]] || [[ ! -s {{output.txt:q}} ]] || ! grep -q 'PASS_FAIL' {{output.txt:q}} || ! grep -q 'REASON' {{output.txt:q}}; then\\n"
    "                printf 'SNP_PAIRS ERROR_PAIRS DOUBLE_ERROR_PAIR_COUNT DOUBLE_ERROR_FRACTION REL_ERROR_FRACTION NONSENSE_FRACTION PASS_FAIL REASON\\n0 0 0 0 0 0 NO_DATA READ_HAPS_FAILED\\n' > {{output.txt:q}}\\n"
    "                printf 'READ_HAPS_FAILED: read_haps exited with status %s or wrote no usable QC table.\\n' \"$read_haps_rc\" >> {{log:q}}\\n"
    "            fi\\n"
    "        else\\n"
    "            printf 'SNP_PAIRS ERROR_PAIRS DOUBLE_ERROR_PAIR_COUNT DOUBLE_ERROR_FRACTION REL_ERROR_FRACTION NONSENSE_FRACTION PASS_FAIL REASON\\n0 0 0 0 0 0 NO_DATA NO_VARIANTS\\n' > {{output.txt:q}}\\n"
    "            printf 'NO_VARIANTS: read_haps skipped because the input VCF has no variant records.\\n' > {{log:q}}\\n"
    "        fi\\n"
    "        test -s {{output.txt:q}}\\n"
    "        grep -q 'PASS_FAIL' {{output.txt:q}}\\n"
    "        grep -q 'REASON' {{output.txt:q}}"
)

text = path.read_text(encoding="utf-8")
changed = False
if hap_new not in text:
    if hap_old not in text:
        raise SystemExit(f"[ERROR] haplocheck zero-variant repair target not found in {{path}}")
    text = text.replace(hap_old, hap_new, 1)
    changed = True
if read_haps_new not in text:
    if read_haps_original_old in text:
        text = text.replace(read_haps_original_old, read_haps_new, 1)
        changed = True
    elif read_haps_partial_old in text:
        text = text.replace(read_haps_partial_old, read_haps_new, 1)
        changed = True
    elif read_haps_empty_failure_old in text:
        text = text.replace(read_haps_empty_failure_old, read_haps_new, 1)
        changed = True
    else:
        raise SystemExit(f"[ERROR] read_haps zero-variant repair target not found in {{path}}")
if changed:
    path.write_text(text, encoding="utf-8")
    print(f"[INFO] Patched contamination identity zero-variant repair: {{path}}")
else:
    print(f"[INFO] contamination identity zero-variant repair already present: {{path}}")
PYCONTAMZERO
}}

	BCLCONVERT_PROFILE_PATCH_REQUESTED=false
	if [[ "$RUN_CONTEXT_MODE" == "true" ]]; then
	  printf '%s' "$RUN_CONTEXT_PAYLOAD" > config/runs.tsv
	  materialize_runtime_table samples_table config/samples.tsv
	  materialize_runtime_table units_table config/units.tsv
	  if bclconvert_runtime_tables_requested; then
	    generate_bclconvert_runtime_tables
	    BCLCONVERT_PROFILE_PATCH_REQUESTED=true
	  fi
	  if ultima_run_qc_config_requested; then
	    append_ultima_run_qc_config
	  fi
	elif [[ "$INPUT_STAGING_MODE" == "true" ]]; then
	  cp "$STAGE_SAMPLES" config/samples.tsv
	  cp "$STAGE_UNITS" config/units.tsv
	elif [[ "$BOOTSTRAP_TEST_CONFIG" == "true" ]]; then
	  bootstrap_test_config
	else
	  echo "[INFO] Input staging skipped for this catalog command."
	fi

if [[ ! -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
  echo "[ERROR] Missing conda profile script at $HOME/miniconda3/etc/profile.d/conda.sh"
  exit 10
fi
. "$HOME/miniconda3/etc/profile.d/conda.sh"
shopt -s expand_aliases
MERMAID_CHROME="$HOME/.cache/puppeteer/chrome/linux-148.0.7778.97/chrome-linux64/chrome"
if [[ -z "${{PUPPETEER_EXECUTABLE_PATH:-}}" && -x "$MERMAID_CHROME" ]]; then
  export PUPPETEER_EXECUTABLE_PATH="$MERMAID_CHROME"
fi

run_dy_command() {{
  local command="$1"
  local dyoainit_source_needed=false
  if [[ "$command" == source\\ dyoainit\\;* ]]; then
    dyoainit_source_needed=true
    command="${{command#source dyoainit;}}"
  elif [[ "$command" == .\\ dyoainit\\;* ]]; then
    dyoainit_source_needed=true
    command="${{command#. dyoainit;}}"
  fi
  command="${{command#"${{command%%[![:space:]]*}}"}}"
  if [[ "$dyoainit_source_needed" == "true" ]]; then
    set +u
    set --
    source dyoainit
    local source_status=$?
    set -u
    if [[ "$source_status" != "0" ]]; then
      return "$source_status"
    fi
  fi
  set +u
  eval "$command"
  local command_status=$?
  set -u
  return "$command_status"
}}

declare -a dyoa_args=()
if [[ -n "$PROJECT_VALUE" ]]; then
  dyoa_args+=(--project {project_arg})
  export PROJECT="$PROJECT_VALUE"
else
  unset PROJECT || true
fi
if [[ "$SKIP_PROJECT_CHECK" == "true" ]]; then
  dyoa_args+=(--skip-project-check)
fi
if [[ "$DEFAULT_ACTIVATION" == "true" ]]; then
  set +u
  . dyoainit "${{dyoa_args[@]}}"
  set -u
  set +e
  set +u
  . bin/day_activate slurm {shlex.quote(args.genome)} remote
  activate_status=$?
  set -u
  set -e
  if [[ "$activate_status" != "0" ]]; then
    echo "[ERROR] day_activate failed with status $activate_status"
    exit "$activate_status"
  fi
fi
if [[ "$BCLCONVERT_PROFILE_PATCH_REQUESTED" == "true" ]]; then
  patch_bclconvert_profile_config
  patch_bclconvert_scratch_output_move
fi
	if ont_run_qc_runtime_repair_requested; then
	  patch_pycoqc_readonly_sort
	fi
	if goleft_indexcov_runtime_repair_requested; then
	  patch_goleft_indexcov_empty_sex_arg
	fi
	if mosdepth_empty_output_runtime_repair_requested; then
	  patch_mosdepth_empty_outputs
	fi
	if rtg_vcfeval_parse_runtime_repair_requested; then
	  patch_rtg_vcfeval_parse_output_dir
	fi
	if vep_zero_variant_runtime_repair_requested; then
	  patch_vep_empty_concat_fofn
	fi
	if contam_identity_zero_variant_runtime_repair_requested; then
	  patch_contam_identity_zero_variant_outputs
	fi
	set +e
	run_dy_command "$DY_COMMAND"
workflow_status=$?
set -e
should_export=false
case "$EXPORT_TRIGGER" in
  none) should_export=false ;;
  on-success) [[ "$workflow_status" -eq 0 ]] && should_export=true ;;
  on-fail) [[ "$workflow_status" -ne 0 ]] && should_export=true ;;
  all) should_export=true ;;
  *) echo "[ERROR] Invalid EXPORT_TRIGGER=$EXPORT_TRIGGER"; workflow_status=20 ;;
esac
if [[ "$should_export" == "true" ]]; then
  if [[ -z "$EXPORT_DESTINATION_S3_URI" ]]; then
    echo "[ERROR] Export requested but EXPORT_DESTINATION_S3_URI is empty"
    workflow_status=21
  else
    mkdir -p "$DAYLILY_RUN_DIR/export"
    registration_args=()
    if [[ -n "$ARTIFACT_REGISTRATION_COMMAND_ID" ]]; then
      registration_args+=(--artifact-registration-command-id "$ARTIFACT_REGISTRATION_COMMAND_ID")
      registration_args+=(--dewey-url "$DEWEY_URL")
      registration_args+=(--dewey-token-env "$DEWEY_TOKEN_ENV")
      if [[ -n "$DEWEY_ANALYSIS_DIR_EXTERNAL_OBJECT_ID" ]]; then
        registration_args+=(--dewey-analysis-dir-external-object-id "$DEWEY_ANALYSIS_DIR_EXTERNAL_OBJECT_ID")
        registration_args+=(--dewey-run-artifact-euid "$DEWEY_RUN_ARTIFACT_EUID")
        registration_args+=(--dewey-ursa-analysis-euid "$DEWEY_URSA_ANALYSIS_EUID")
      fi
    fi
    set +e
    env -u AWS_PROFILE -u AWS_DEFAULT_PROFILE dyec export \
      --region {shlex.quote(region)} \
      --cluster {shlex.quote(cluster_name)} \
      --source-path "$clone_root" \
      --destination-s3-uri "$EXPORT_DESTINATION_S3_URI" \
      --output-dir "$DAYLILY_RUN_DIR/export" \
      "${{registration_args[@]}}"
    export_status=$?
    set -e
    if [[ "$export_status" -ne 0 ]]; then
      echo "[ERROR] Export failed with status $export_status"
      workflow_status="$export_status"
    elif [[ "$DELETE_ON_EXPORT_SUCCESS" == "true" ]]; then
      rm -rf -- "$clone_root"
      echo "[INFO] Deleted FSx analysis directory after successful export: $clone_root"
    fi
  fi
fi
export DAYLILY_STATUS_FINALIZED=1
export DAYLILY_STATUS_COMPLETED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
export DAYLILY_STATUS_EXIT_CODE="$workflow_status"
write_status
echo "[INFO] Workflow exited with status $workflow_status"
if [[ ! -d "$clone_root" ]]; then
  exit "$workflow_status"
fi
exec bash -il
"""

    tmux_script = f"""
set -euo pipefail
SESSION_NAME={shlex.quote(args.session_name)}
ANALYSIS_ID={shlex.quote(analysis_id)}
EXECUTING_ENTITY={shlex.quote(executing_entity)}
REPO_KEY={shlex.quote(args.repository)}
analysis_root=$(python3 - <<'PYCONFIG'
from pathlib import Path
analysis_root = '/fsx/analysis_results'
config_path = Path.home() / '.config/daylily/daylily_cli_global.yaml'
if config_path.exists():
    for line in config_path.read_text().splitlines():
        line = line.strip()
        if line.startswith('analysis_root:'):
            analysis_root = line.split(':', 1)[1].strip()
            break
print(analysis_root.rstrip('/'))
PYCONFIG
)
repo_relative=$(python3 - <<'PYREPOS'
from pathlib import Path
repo_key = {repository_literal}
relative = 'daylily-omics-analysis'
config_path = Path.home() / '.config/daylily/daylily_available_repositories.yaml'
if config_path.exists():
    current_key = None
    for raw in config_path.read_text().splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if stripped.endswith(':'):
            current_key = stripped[:-1].strip()
            continue
        if current_key == repo_key and stripped.startswith('relative_path:'):
            relative = stripped.split(':', 1)[1].strip()
            break
print(relative.strip())
PYREPOS
)
analysis_root=${{analysis_root%/}}
run_dir="/home/ubuntu/daylily-runs/$SESSION_NAME"
clone_root="$analysis_root/$EXECUTING_ENTITY/$ANALYSIS_ID"
repo_path="$clone_root/$repo_relative"
work_script="$run_dir/launch.sh"
tmux_log="$run_dir/tmux.log"
bootstrap_log="$run_dir/tmux-bootstrap.log"
status_file="$run_dir/status.json"
mkdir -p "$run_dir"
: >"$tmux_log"
export DAYLILY_RUN_DIR="$run_dir"
export DAYLILY_REPO_PATH="$repo_path"
export DAYLILY_TMUX_LOG="$tmux_log"
tmux_session_name="${{SESSION_NAME//[^A-Za-z0-9_-]/_}}"
if [[ -z "$tmux_session_name" ]]; then
  echo "__DAYLILY_ERROR__=invalid_tmux_session_name"
  exit 8
fi
if tmux has-session -t "=$tmux_session_name" 2>/dev/null; then
  echo "__DAYLILY_ERROR__=session_exists"
  exit 8
fi
if [[ -e "$clone_root" ]]; then
  if [[ "$REPLACE_EXISTING_ANALYSIS_DIR" != "true" ]]; then
    echo "__DAYLILY_ERROR__=analysis_dir_exists"
    exit 8
  fi
  if [[ -z "$analysis_root" || -z "$EXECUTING_ENTITY" || -z "$ANALYSIS_ID" ]]; then
    echo "__DAYLILY_ERROR__=unsafe_replace_existing_analysis_dir"
    exit 8
  fi
  expected_clone_root="$analysis_root/$EXECUTING_ENTITY/$ANALYSIS_ID"
  if [[ "$clone_root" != "$expected_clone_root" || "$clone_root" == "/" ]]; then
    echo "__DAYLILY_ERROR__=unsafe_replace_existing_analysis_dir"
    exit 8
  fi
  rm -rf -- "$clone_root"
  echo "__DAYLILY_REPLACED_ANALYSIS_DIR__=$clone_root"
fi
cat <<'PAYLOAD' > "$work_script"
{pipeline_script}
PAYLOAD
chmod 0700 "$work_script"
nohup tmux new-session -d -s "$tmux_session_name" \
  -e "DAYLILY_RUN_DIR=$run_dir" \
  -e "DAYLILY_REPO_PATH=$repo_path" \
  -e "DAYLILY_TMUX_LOG=$tmux_log" \
  "bash -lc 'source \"$work_script\" >>\"$tmux_log\" 2>&1'" >"$bootstrap_log" 2>&1 &
SESSION_START_DEADLINE=$((SECONDS + 60))
session_ready=false
quick_status=""
while true; do
  if tmux has-session -t "=$tmux_session_name" 2>/dev/null; then
    session_ready=true
    break
  fi
  if [[ -f "$status_file" ]]; then
    if quick_status="$(python3 - "$status_file" <<'PYQUICK'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
exit_code = payload.get("exit_code")
if exit_code is None:
    raise SystemExit(1)
print(f"exit_code={{exit_code}}")
PYQUICK
)"; then
      break
    fi
  fi
  if (( SECONDS >= SESSION_START_DEADLINE )); then
    break
  fi
  sleep 1
done
if [[ "$session_ready" != "true" ]]; then
  if [[ -n "$quick_status" ]]; then
    echo "__DAYLILY_COMPLETED_QUICKLY__=$quick_status"
    echo "__DAYLILY_SESSION__=$SESSION_NAME"
    echo "__DAYLILY_TMUX_SESSION__=$tmux_session_name"
    echo "__DAYLILY_RUN_DIR__=$run_dir"
    echo "__DAYLILY_REPO_PATH__=$repo_path"
    exit 0
  fi
  if [[ -s "$bootstrap_log" ]]; then
    cat "$bootstrap_log" >&2
  fi
  if [[ -s "$tmux_log" ]]; then
    tail -n 80 "$tmux_log" >&2
  fi
  echo "__DAYLILY_ERROR__=session_start_timeout"
  exit 8
fi
echo "__DAYLILY_SESSION__=$SESSION_NAME"
echo "__DAYLILY_TMUX_SESSION__=$tmux_session_name"
echo "__DAYLILY_RUN_DIR__=$run_dir"
echo "__DAYLILY_REPO_PATH__=$repo_path"
"""

    result = run_shell(
        target.instance_id,
        region,
        tmux_script,
        profile=args.profile,
        timeout=120,
        comment="Launch daylily workflow tmux session",
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")

    launch_info = parse_workflow_launch(result.stdout)
    print(f"Tmux session '{launch_info.session_name}' created on the head node.")
    print(f"Run state directory: {launch_info.run_dir}")
    print(f"Workflow repo path: {launch_info.repo_path}")
    print(
        "Reconnect with: daylily-ssh-into-headnode --profile {profile} --region {region} --cluster {cluster}".format(
            profile=args.profile,
            region=region,
            cluster=cluster_name,
        )
    )
    print(f"Then run: tmux attach -t {launch_info.session_name}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except CommandError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
