"""Run the supported Daylily lifecycle against a real AWS sandbox account."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import yaml

from daylily_ec.aws.ssm import (
    ensure_ubuntu_session_preferences,
    resolve_headnode_instance_id,
    run_shell,
    wait_for_ssm_online,
)
from daylily_ec.scripts.common import CommandError, aws_env, need_cmd, run_command


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = Path.home() / ".config" / "daylily" / "daylily_ephemeral_cluster.yaml"
DEFAULT_STAGE_BASE = "/fsx/data/staged_sample_data"
DEFAULT_EXPORT_TARGET = "analysis_results"
CLUSTER_NAME_PREFIX = "day-ssm-e2e"
MAX_CLUSTER_NAME_LEN = 26


@dataclass
class StepResult:
    name: str
    status: str
    details: Dict[str, str] = field(default_factory=dict)


@dataclass
class RunnerSummary:
    cluster_name: str
    region: str
    region_az: str
    profile: str
    config_path: str
    analysis_samples: str
    output_json: str
    started_at: str
    steps: List[StepResult] = field(default_factory=list)


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def default_cluster_name() -> str:
    return f"{CLUSTER_NAME_PREFIX}-{_timestamp_slug()}"


def validate_cluster_name(cluster_name: str) -> str:
    if len(cluster_name) > MAX_CLUSTER_NAME_LEN:
        raise CommandError(
            "Cluster name "
            f"'{cluster_name}' is too long for the supported template. "
            f"Use {MAX_CLUSTER_NAME_LEN} characters or fewer so the derived FSx name stays valid."
        )
    return cluster_name


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the supported Daylily SSH-to-SSM lifecycle against a real AWS sandbox account.",
    )
    parser.add_argument("--profile", default=os.environ.get("AWS_PROFILE"))
    parser.add_argument("--region", required=True, help="AWS region for the cluster")
    parser.add_argument("--region-az", required=True, help="AWS region/AZ to create into")
    parser.add_argument(
        "--config",
        default=os.environ.get("DAY_EX_CFG") or str(DEFAULT_CONFIG_PATH),
        help="Base Daylily config file to copy and override for this run",
    )
    parser.add_argument(
        "--cluster-name",
        default=default_cluster_name(),
        help="Cluster name for this run (default: generated timestamped name)",
    )
    parser.add_argument(
        "--reference-bucket",
        required=True,
        help="S3 URI backing the FSx data repository for laptop-side staging",
    )
    parser.add_argument(
        "--analysis-samples",
        required=True,
        help="analysis_samples.tsv fixture to stage from the laptop",
    )
    parser.add_argument(
        "--stage-config-dir",
        default=None,
        help="Directory to write generated samples.tsv/units.tsv (default: tmp-e2e-config/<cluster>)",
    )
    parser.add_argument(
        "--stage-base",
        default=DEFAULT_STAGE_BASE,
        help=f"Remote stage base used for workflow launch (default: {DEFAULT_STAGE_BASE})",
    )
    parser.add_argument(
        "--export-output-dir",
        default=None,
        help="Directory for export artifacts (default: tmp-e2e-export/<cluster>)",
    )
    parser.add_argument(
        "--export-target-uri",
        default=DEFAULT_EXPORT_TARGET,
        help=f"FSx export target path (default: {DEFAULT_EXPORT_TARGET})",
    )
    parser.add_argument(
        "--pass-on-warn",
        action="store_true",
        help="Forward --pass-on-warn to preflight/create",
    )
    parser.add_argument(
        "--workflow-live",
        action="store_true",
        help="Launch the workflow without --dry-run",
    )
    parser.add_argument(
        "--interactive-session-smoke",
        action="store_true",
        help="Attempt a live Session Manager open/exit probe through a PTY-capable local shell",
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="Skip the export step",
    )
    parser.add_argument(
        "--delete-cluster",
        action="store_true",
        help="Delete the cluster at the end of the run",
    )
    parser.add_argument(
        "--allow-destroy",
        action="store_true",
        help="Required alongside --delete-cluster before the runner will execute deletion",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Write machine-readable step results here (default: tmp-e2e-results/<cluster>.json)",
    )
    return parser.parse_args(argv)


def ensure_profile(profile: Optional[str]) -> str:
    if not profile:
        raise CommandError("AWS profile is required. Set AWS_PROFILE or pass --profile.")
    return profile


def validate_delete_flags(*, delete_cluster: bool, allow_destroy: bool) -> None:
    if delete_cluster and not allow_destroy:
        raise CommandError(
            "--delete-cluster requires --allow-destroy. The runner stays non-destructive by default."
        )


def _set_triplet_value(raw_cfg: dict, key: str, value: str) -> None:
    config = raw_cfg.setdefault("ephemeral_cluster", {}).setdefault("config", {})
    existing = config.get(key)
    if isinstance(existing, list) and len(existing) >= 3:
        existing[0] = "USESETVALUE"
        existing[2] = value
        return
    default_value = ""
    if isinstance(existing, list) and len(existing) >= 2:
        default_value = str(existing[1] or "")
    config[key] = ["USESETVALUE", default_value, value]


def write_runner_config(base_config_path: Path, cluster_name: str, dest_dir: Path) -> Path:
    if not base_config_path.is_file():
        raise CommandError(f"Config file not found: {base_config_path}")
    raw_cfg = yaml.safe_load(base_config_path.read_text(encoding="utf-8")) or {}
    _set_triplet_value(raw_cfg, "cluster_name", cluster_name)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{cluster_name}_runner_config.yaml"
    dest_path.write_text(yaml.safe_dump(raw_cfg, sort_keys=False), encoding="utf-8")
    return dest_path


def parse_remote_stage_dir(stdout: str) -> str:
    match = re.search(r"^Remote FSx stage directory:\s*(?P<path>\S+)\s*$", stdout, re.MULTILINE)
    if not match:
        raise CommandError("Unable to determine Remote FSx stage directory from staging output.")
    return match.group("path")


def parse_tmux_session(stdout: str) -> str:
    match = re.search(r"Tmux session '(?P<name>[^']+)' created on the head node\.", stdout)
    if not match:
        raise CommandError("Unable to determine tmux session name from workflow launcher output.")
    return match.group("name")


def _summary_output_path(cluster_name: str, explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    return (REPO_ROOT / "tmp-e2e-results" / f"{cluster_name}.json").resolve()


def _record_step(summary: RunnerSummary, output_path: Path, name: str, status: str, **details: str) -> None:
    summary.steps.append(StepResult(name=name, status=status, details=details))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                **asdict(summary),
                "steps": [asdict(step) for step in summary.steps],
            },
            indent=2,
            sort_keys=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _command_display(command: Sequence[str]) -> str:
    return " ".join(command)


def _run_local_command(
    summary: RunnerSummary,
    output_path: Path,
    name: str,
    command: Sequence[str],
    *,
    env: Dict[str, str],
) -> str:
    print(f"[RUN] {name}: {_command_display(command)}")
    result = run_command(command, capture_output=True, env=env)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    _record_step(summary, output_path, name, "passed", command=_command_display(command))
    return result.stdout or ""


def _validate_headnode_bootstrap(
    summary: RunnerSummary,
    output_path: Path,
    *,
    instance_id: str,
    profile: str,
    region: str,
) -> None:
    validation_script = """
set -euo pipefail
bash -lc '
set -euo pipefail
test "$(whoami)" = ubuntu
test "${DAYLILY_EC_HEADNODE_BOOTSTRAPPED:-0}" = 1
test "${CONDA_DEFAULT_ENV:-}" = DAY-EC
command -v daylily-ec >/dev/null 2>&1
command -v day-clone >/dev/null 2>&1
day-clone --list >/dev/null
'
"""
    result = run_shell(
        instance_id,
        region,
        validation_script,
        profile=profile,
        timeout=120,
        comment="Daylily SSH-to-SSM E2E bootstrap validation",
    )
    _record_step(
        summary,
        output_path,
        "validate-headnode-bootstrap",
        "passed",
        command="ssm:bootstrap-validation",
        command_id=result.command_id,
    )


def _inspect_runtime_state(
    summary: RunnerSummary,
    output_path: Path,
    *,
    instance_id: str,
    profile: str,
    region: str,
) -> None:
    inspect_script = """
set -euo pipefail
tmux ls
sinfo
squeue -o "%.18i %.8u %.8T %.10M %.30N %.50j"
"""
    result = run_shell(
        instance_id,
        region,
        inspect_script,
        profile=profile,
        timeout=120,
        comment="Daylily SSH-to-SSM E2E runtime inspection",
    )
    _record_step(
        summary,
        output_path,
        "inspect-runtime-state",
        "passed",
        command="ssm:tmux-sinfo-squeue",
        command_id=result.command_id,
    )


def _resolve_stage_config_dir(cluster_name: str, explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    return (REPO_ROOT / "tmp-e2e-config" / cluster_name).resolve()


def _resolve_export_output_dir(cluster_name: str, explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    return (REPO_ROOT / "tmp-e2e-export" / cluster_name).resolve()


def _build_interactive_smoke_command(profile: str, region: str, cluster_name: str) -> list[str]:
    helper = (
        f"printf 'exit\\n' | "
        f"{(REPO_ROOT / 'bin' / 'daylily-ssh-into-headnode').resolve()} "
        f"--profile {profile} --region {region} --cluster {cluster_name}"
    )
    if sys.platform == "darwin":
        return ["script", "-q", "/dev/null", "/bin/sh", "-lc", helper]
    return ["script", "-q", "-c", helper, "/dev/null"]


def _smoke_interactive_session(
    summary: RunnerSummary,
    output_path: Path,
    *,
    profile: str,
    region: str,
    cluster_name: str,
    env: Dict[str, str],
) -> None:
    if not shutil.which("script"):
        raise CommandError("interactive session smoke requires the local `script` command.")
    command = _build_interactive_smoke_command(profile, region, cluster_name)
    print(f"[RUN] smoke-interactive-session: {_command_display(command)}")
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=env,
            timeout=45,
            check=False,
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if "Starting session with SessionId:" not in stdout:
            raise CommandError(
                "Interactive Session Manager smoke did not report a live session start before timing out."
            ) from exc
        _record_step(
            summary,
            output_path,
            "smoke-interactive-session",
            "passed",
            command=_command_display(command),
            detail="Timed out after confirming a live Session Manager session start.",
        )
        return

    if "Starting session with SessionId:" not in stdout and result.returncode != 0:
        message = stderr.strip() or stdout.strip() or "interactive Session Manager smoke failed"
        raise CommandError(message)
    _record_step(
        summary,
        output_path,
        "smoke-interactive-session",
        "passed",
        command=_command_display(command),
        returncode=str(result.returncode),
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    profile = ensure_profile(args.profile)
    validate_delete_flags(delete_cluster=args.delete_cluster, allow_destroy=args.allow_destroy)
    args.cluster_name = validate_cluster_name(args.cluster_name)

    need_cmd("aws")
    need_cmd("daylily-ec")
    need_cmd("pcluster")
    need_cmd("session-manager-plugin")

    base_config_path = Path(args.config).expanduser().resolve()
    analysis_samples = Path(args.analysis_samples).expanduser().resolve()
    if not analysis_samples.is_file():
        raise CommandError(f"analysis_samples.tsv fixture not found: {analysis_samples}")

    stage_config_dir = _resolve_stage_config_dir(args.cluster_name, args.stage_config_dir)
    export_output_dir = _resolve_export_output_dir(args.cluster_name, args.export_output_dir)
    output_json = _summary_output_path(args.cluster_name, args.output_json)

    summary = RunnerSummary(
        cluster_name=args.cluster_name,
        region=args.region,
        region_az=args.region_az,
        profile=profile,
        config_path=str(base_config_path),
        analysis_samples=str(analysis_samples),
        output_json=str(output_json),
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    _record_step(summary, output_json, "runner-start", "passed")

    env = aws_env(profile=profile, region=args.region)
    with tempfile.TemporaryDirectory(prefix=f"{args.cluster_name}-cfg-") as tmp_dir_name:
        runner_config = write_runner_config(base_config_path, args.cluster_name, Path(tmp_dir_name))
        _record_step(
            summary,
            output_json,
            "prepare-config",
            "passed",
            runner_config=str(runner_config),
        )

        preflight_cmd = [
            "daylily-ec",
            "preflight",
            "--region-az",
            args.region_az,
            "--profile",
            profile,
            "--config",
            str(runner_config),
            "--non-interactive",
        ]
        if args.pass_on_warn:
            preflight_cmd.append("--pass-on-warn")
        _run_local_command(summary, output_json, "preflight", preflight_cmd, env=env)

        create_cmd = [
            "daylily-ec",
            "create",
            "--region-az",
            args.region_az,
            "--profile",
            profile,
            "--config",
            str(runner_config),
            "--non-interactive",
        ]
        if args.pass_on_warn:
            create_cmd.append("--pass-on-warn")
        _run_local_command(summary, output_json, "create-cluster", create_cmd, env=env)

    target = resolve_headnode_instance_id(args.cluster_name, args.region, profile=profile)
    _record_step(
        summary,
        output_json,
        "resolve-headnode",
        "passed",
        instance_id=target.instance_id,
    )

    wait_for_ssm_online(target.instance_id, args.region, profile=profile, timeout=300)
    _record_step(summary, output_json, "wait-for-ssm", "passed", instance_id=target.instance_id)

    ensure_ubuntu_session_preferences(args.region, profile=profile)
    _record_step(
        summary,
        output_json,
        "validate-session-manager-shell",
        "passed",
        document="SSM-SessionManagerRunShell",
        requirement="ubuntu login shell",
    )
    if args.interactive_session_smoke:
        _smoke_interactive_session(
            summary,
            output_path=output_json,
            profile=profile,
            region=args.region,
            cluster_name=args.cluster_name,
            env=env,
        )
    else:
        _record_step(
            summary,
            output_json,
            "smoke-interactive-session",
            "skipped",
            reason="Set --interactive-session-smoke to probe a live Session Manager shell open/exit.",
        )

    _validate_headnode_bootstrap(
        summary,
        output_path=output_json,
        instance_id=target.instance_id,
        profile=profile,
        region=args.region,
    )

    stage_config_dir.mkdir(parents=True, exist_ok=True)
    stage_cmd = [
        str((REPO_ROOT / "bin" / "daylily-stage-samples-from-local-to-headnode").resolve()),
        "--profile",
        profile,
        "--region",
        args.region,
        "--reference-bucket",
        args.reference_bucket,
        "--config-dir",
        str(stage_config_dir),
        str(analysis_samples),
    ]
    stage_stdout = _run_local_command(summary, output_json, "stage-from-laptop", stage_cmd, env=env)
    remote_stage_dir = parse_remote_stage_dir(stage_stdout)
    _record_step(
        summary,
        output_json,
        "parse-stage-output",
        "passed",
        remote_stage_dir=remote_stage_dir,
    )

    launch_cmd = [
        str((REPO_ROOT / "bin" / "daylily-run-omics-analysis-headnode").resolve()),
        "--profile",
        profile,
        "--region",
        args.region,
        "--cluster",
        args.cluster_name,
        "--stage-base",
        args.stage_base,
    ]
    if not args.workflow_live:
        launch_cmd.append("--dry-run")
    launch_stdout = _run_local_command(summary, output_json, "launch-workflow", launch_cmd, env=env)
    session_name = parse_tmux_session(launch_stdout)
    _record_step(
        summary,
        output_json,
        "parse-workflow-output",
        "passed",
        session_name=session_name,
    )

    _inspect_runtime_state(
        summary,
        output_path=output_json,
        instance_id=target.instance_id,
        profile=profile,
        region=args.region,
    )

    cfg_headnode_cmd = [
        str((REPO_ROOT / "bin" / "daylily-cfg-headnode").resolve()),
        "--profile",
        profile,
        "--region",
        args.region,
        "--cluster",
        args.cluster_name,
    ]
    _run_local_command(summary, output_json, "rerun-headnode-bootstrap", cfg_headnode_cmd, env=env)

    if args.skip_export:
        _record_step(summary, output_json, "export-results", "skipped", reason="--skip-export")
    else:
        export_output_dir.mkdir(parents=True, exist_ok=True)
        export_cmd = [
            "daylily-ec",
            "export",
            "--cluster-name",
            args.cluster_name,
            "--region",
            args.region,
            "--target-uri",
            args.export_target_uri,
            "--output-dir",
            str(export_output_dir),
        ]
        _run_local_command(summary, output_json, "export-results", export_cmd, env=env)
        export_yaml = export_output_dir / "fsx_export.yaml"
        if not export_yaml.is_file():
            raise CommandError(f"Export did not write expected artifact: {export_yaml}")
        _record_step(
            summary,
            output_json,
            "verify-export-artifact",
            "passed",
            fsx_export_yaml=str(export_yaml),
        )

    if args.delete_cluster:
        delete_cmd = [
            "daylily-ec",
            "delete",
            "--cluster-name",
            args.cluster_name,
            "--region",
            args.region,
            "--profile",
            profile,
            "--yes",
        ]
        _run_local_command(summary, output_json, "delete-cluster", delete_cmd, env=env)
    else:
        _record_step(
            summary,
            output_json,
            "delete-cluster",
            "skipped",
            reason="Set --delete-cluster --allow-destroy to run the destructive teardown step.",
        )

    print(f"[OK] Wrote E2E summary to {output_json}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except CommandError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
