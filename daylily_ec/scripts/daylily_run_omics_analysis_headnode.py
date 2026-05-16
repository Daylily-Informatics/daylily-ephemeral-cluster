"""Launch daylily-omics-analysis inside tmux on the headnode via SSM."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from dataclasses import dataclass
from typing import List, Optional

from daylily_ec.aws.ssm import (
    resolve_headnode_instance_id,
    run_shell,
    wait_for_ssm_online,
)
from daylily_ec.scripts.common import CommandError, need_cmd, resolve_cluster, resolve_region


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
    if stage_dir:
        target_dir = normalize_remote_path(stage_dir.rstrip("/"))
        script = f"""
set -euo pipefail
if [[ "$(id -un)" != "ubuntu" ]]; then
  echo "__DAYLILY_ERROR__=wrong_user"
  exit 5
fi
STAGE_DIR={shlex.quote(target_dir)}
if [[ ! -d "$STAGE_DIR" ]]; then
  echo "__DAYLILY_ERROR__=missing_stage_dir"
  exit 2
fi
samples_file=$(ls -1 "$STAGE_DIR"/*_samples.tsv 2>/dev/null | head -n 1)
units_file=$(ls -1 "$STAGE_DIR"/*_units.tsv 2>/dev/null | head -n 1)
if [[ -z "$samples_file" || -z "$units_file" ]]; then
  echo "__DAYLILY_ERROR__=missing_config"
  exit 3
fi
echo "__DAYLILY_STAGE_DIR__=$STAGE_DIR"
echo "__DAYLILY_STAGE_SAMPLES__=$samples_file"
echo "__DAYLILY_STAGE_UNITS__=$units_file"
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
latest_dir=$(ls -1dt "$STAGE_BASE"/*/ 2>/dev/null | head -n 1)
if [[ -z "$latest_dir" ]]; then
  echo "__DAYLILY_ERROR__=no_stage_runs"
  exit 3
fi
samples_file=$(ls -1 "$latest_dir"/*_samples.tsv 2>/dev/null | head -n 1)
units_file=$(ls -1 "$latest_dir"/*_units.tsv 2>/dev/null | head -n 1)
if [[ -z "$samples_file" || -z "$units_file" ]]; then
  echo "__DAYLILY_ERROR__=missing_config"
  exit 4
fi
echo "__DAYLILY_STAGE_DIR__=$latest_dir"
echo "__DAYLILY_STAGE_SAMPLES__=$samples_file"
echo "__DAYLILY_STAGE_UNITS__=$units_file"
"""

    result = run_shell(
        instance_id,
        region,
        script,
        profile=profile,
        timeout=60,
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
        "--stage-base",
        default="/fsx/staged_sample_data",
        help="Base staging directory to scan when --stage-dir is omitted",
    )
    parser.add_argument(
        "--session-name",
        default="daylily-omics-analysis",
        help="Name of the tmux session to create on the head node",
    )
    parser.add_argument(
        "--destination",
        required=True,
        help="Workspace destination passed to day-clone",
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
    parser.add_argument("--dry-run", action="store_true")
    parser.set_defaults(skip_project_check=True)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.profile:
        raise CommandError("AWS profile is required. Set AWS_PROFILE or use --profile.")

    need_cmd("aws")
    need_cmd("pcluster")

    region = resolve_region(args.profile, args.region)
    cluster_name = resolve_cluster(args.profile, region, args.cluster)
    target = resolve_headnode_instance_id(cluster_name, region, profile=args.profile)
    wait_for_ssm_online(target.instance_id, region, profile=args.profile, timeout=120)

    stage_config = discover_stage_config(
        target.instance_id,
        args.profile,
        region,
        args.stage_dir,
        args.stage_base,
    )

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
STAGE_SAMPLES={shlex.quote(stage_config.samples_path)}
STAGE_UNITS={shlex.quote(stage_config.units_path)}
PROJECT_VALUE={project_arg if project_arg else ""}
SKIP_PROJECT_CHECK={skip_check}
DY_COMMAND={dy_command_literal}
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
  --destination {shlex.quote(args.destination)} \
  --repository {shlex.quote(args.repository)} \
  --git-tag {shlex.quote(args.git_tag)}
cd "$repo_path"
mkdir -p config
cp "$STAGE_SAMPLES" config/samples.tsv
cp "$STAGE_UNITS" config/units.tsv

if [[ ! -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
  echo "[ERROR] Missing conda profile script at $HOME/miniconda3/etc/profile.d/conda.sh"
  exit 10
fi
. "$HOME/miniconda3/etc/profile.d/conda.sh"

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
set +e
eval "$DY_COMMAND"
workflow_status=$?
set -e
export DAYLILY_STATUS_FINALIZED=1
export DAYLILY_STATUS_COMPLETED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
export DAYLILY_STATUS_EXIT_CODE="$workflow_status"
write_status
echo "[INFO] Workflow exited with status $workflow_status"
exec bash -il
"""

    tmux_script = f"""
set -euo pipefail
SESSION_NAME={shlex.quote(args.session_name)}
DESTINATION={shlex.quote(args.destination)}
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
repo_path="$analysis_root/$(whoami)/$DESTINATION/$repo_relative"
work_script="$run_dir/launch.sh"
tmux_log="$run_dir/tmux.log"
bootstrap_log="$run_dir/tmux-bootstrap.log"
mkdir -p "$run_dir"
: >"$tmux_log"
export DAYLILY_RUN_DIR="$run_dir"
export DAYLILY_REPO_PATH="$repo_path"
export DAYLILY_TMUX_LOG="$tmux_log"
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  echo "__DAYLILY_ERROR__=session_exists"
  exit 8
fi
cat <<'PAYLOAD' > "$work_script"
{pipeline_script}
PAYLOAD
chmod 0700 "$work_script"
nohup tmux new-session -d -s "$SESSION_NAME" \
  -e "DAYLILY_RUN_DIR=$run_dir" \
  -e "DAYLILY_REPO_PATH=$repo_path" \
  -e "DAYLILY_TMUX_LOG=$tmux_log" \
  "bash -lc 'source \"$work_script\" >>\"$tmux_log\" 2>&1'" >"$bootstrap_log" 2>&1 &
sleep 2
if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  if [[ -s "$bootstrap_log" ]]; then
    cat "$bootstrap_log" >&2
  fi
  echo "__DAYLILY_ERROR__=session_start_failed"
  exit 8
fi
echo "__DAYLILY_SESSION__=$SESSION_NAME"
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
