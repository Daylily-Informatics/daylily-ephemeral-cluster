#!/usr/bin/env python3
"""Run the goodole3 DayOA command-catalog validation matrix.

This is a durable execution helper for the ledger opened at
docs/plans/20260526T223700Z_goodole3_dayoa_dyec_release_catalog_ledger.md.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, write_remote_text
from daylily_ec.repositories import load_repository_catalog


ROOT = Path(__file__).resolve().parents[2]
PLAN_ROOT = ROOT / "docs" / "plans"
RUN_ROOT = PLAN_ROOT / "20260526T223700Z_goodole3_inputs"
LOG_ROOT = PLAN_ROOT / "20260526T223700Z_goodole3_logs"
EVENTS_PATH = PLAN_ROOT / "20260526T223700Z_goodole3_catalog_runs.jsonl"

CLUSTER = "goodole3"
PROFILE = "lsmc"
REGION = "us-west-2"
EXECUTING_ENTITY = "ubuntu"
REFERENCE_S3_URI = "s3://lsmc-dayoa-references-usw2"
CONTROL_DATA_S3_URI = "s3://lsmc-dayoa-control-data-usw2"
STAGE_S3_URI = "s3://lsmc-ssf-sequencing-data/staged_external_data"
STAGE_TARGET = "/fsx/staging/staged_external_sequencing_data"

SAMPLE_INPUTS = {
    "illumina_snv_alignstats": "illumina_hg003_5x.tsv",
    "illumina_snv_alignstats_relatedness_vep_multiqc": "illumina_0p1x_kitchensink.tsv",
    "ultima_snv_alignstats": "ultima_hg003_5x.tsv",
    "ultima_snv_alignstats_kitchensink": "ultima_hg003_5x.tsv",
    "ont_snv_alignstats": "ont_hg003_5x.tsv",
    "ont_snv_alignstats_kitchensink": "ont_hg003_5x.tsv",
    "pacbio_snv_alignstats": "pacbio_hg003_5x.tsv",
    "roche_snv_alignstats": "roche_hg003_5x.tsv",
    "hybrid_ilmn_ont_snv": "hybrid_ilmn_ont_hg003_5x5x.tsv",
    "hybrid_ilmn_ont_snv_kitchensink": "hybrid_ilmn_ont_hg003_5x5x.tsv",
    "hybrid_ultima_ont_snv": "hybrid_ultima_ont_hg003_5x5x.tsv",
}

RUN_CONTEXT_INPUTS = {
    "illumina_run_qc": "illumina_run_context.tsv",
    "illumina_bclconvert": "illumina_run_context.tsv",
    "illumina_run_qc_bclconvert": "illumina_run_context.tsv",
    "ont_run_qc": "ont_run_context.tsv",
    "ultima_run_qc": "ultima_run_context_candidate.tsv",
}

BLOCKED_COMMANDS = {
    "complete_genomics_mgi_snv_concordance": (
        "Not run: candidate CG/MGI mate-pair contract remains unverified; "
        "_386_1 and _386_2 sizes are inconsistent and no substitution is authorized."
    ),
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_events() -> list[dict[str, Any]]:
    if not EVENTS_PATH.exists():
        return []
    events = []
    for line in EVENTS_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def append_event(event: dict[str, Any]) -> None:
    event = {"ts": utc_now(), **event}
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def last_event(command_id: str, phase: str, status: str | None = None) -> dict[str, Any] | None:
    for event in reversed(load_events()):
        if event.get("command_id") != command_id or event.get("phase") != phase:
            continue
        if status is not None and event.get("status") != status:
            continue
        return event
    return None


def run_cmd(argv: list[str], *, log_name: str, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    log_path = LOG_ROOT / log_name
    env = os.environ.copy()
    env["AWS_PROFILE"] = PROFILE
    proc = subprocess.run(
        argv,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    payload = {
        "argv": argv,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
    log_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return proc


def require_success(proc: subprocess.CompletedProcess[str], *, command_id: str, phase: str) -> None:
    if proc.returncode == 0:
        return
    append_event(
        {
            "command_id": command_id,
            "phase": phase,
            "status": "failed",
            "returncode": proc.returncode,
            "stderr_tail": proc.stderr[-4000:],
            "stdout_tail": proc.stdout[-4000:],
        }
    )
    raise RuntimeError(f"{command_id} {phase} failed with rc={proc.returncode}")


def dyec() -> str:
    executable = shutil.which("dyec")
    if not executable:
        raise RuntimeError("dyec is not on PATH; run through source ./activate")
    return executable


def safe_id(command_id: str, suffix: str = "") -> str:
    base = f"gd3_{command_id}{suffix}"
    return re.sub(r"[^A-Za-z0-9._-]", "_", base)


def parse_stage_dir(stdout: str) -> str:
    match = re.search(r"Remote FSx stage directory:\s*(\S+)", stdout)
    if not match:
        raise RuntimeError("Unable to parse Remote FSx stage directory from staging stdout")
    return match.group(1)


def stage_sample(command_id: str, manifest_name: str, timeout_seconds: int) -> str:
    existing = last_event(command_id, "stage", "success")
    if existing and existing.get("remote_stage_dir"):
        return str(existing["remote_stage_dir"])
    config_dir = RUN_ROOT / "generated" / command_id
    config_dir.mkdir(parents=True, exist_ok=True)
    argv = [
        dyec(),
        "samples",
        "stage",
        str(RUN_ROOT / manifest_name),
        "--reference-s3-uri",
        REFERENCE_S3_URI,
        "--control-data-s3-uri",
        CONTROL_DATA_S3_URI,
        "--stage-s3-uri",
        STAGE_S3_URI,
        "--stage-target",
        STAGE_TARGET,
        "--config-dir",
        str(config_dir),
        "--profile",
        PROFILE,
        "--region",
        REGION,
    ]
    proc = run_cmd(argv, log_name=f"{command_id}_stage.log", timeout=timeout_seconds)
    require_success(proc, command_id=command_id, phase="stage")
    generated_stage_dir = parse_stage_dir(proc.stdout)
    stage_name = Path(generated_stage_dir.rstrip("/")).name
    timestamp = stage_name.replace("remote_stage_", "")
    samples_path = config_dir / f"{timestamp}_samples.tsv"
    units_path = config_dir / f"{timestamp}_units.tsv"
    if not samples_path.is_file() or not units_path.is_file():
        raise RuntimeError(f"Generated samples/units files not found in {config_dir}")

    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    command_key = hashlib.sha1(command_id.encode("utf-8")).hexdigest()[:8]
    remote_stage_dir = f"/home/ubuntu/ds/gd3/{command_key}/{stage_name}"
    remote_samples_path = f"{remote_stage_dir}/a_samples.tsv"
    remote_units_path = f"{remote_stage_dir}/a_units.tsv"
    write_remote_text(
        target.instance_id,
        REGION,
        remote_samples_path,
        samples_path.read_text(encoding="utf-8"),
        profile=PROFILE,
    )
    write_remote_text(
        target.instance_id,
        REGION,
        remote_units_path,
        units_path.read_text(encoding="utf-8"),
        profile=PROFILE,
    )
    verify = run_shell(
        target.instance_id,
        REGION,
        "set -euo pipefail\n"
        f"test -s {remote_samples_path!r}\n"
        f"test -s {remote_units_path!r}\n"
        f"printf 'REMOTE_STAGE_DIR=%s\\n' {remote_stage_dir!r}\n",
        profile=PROFILE,
        timeout=180,
        comment=f"Verify staged configs for {command_id}",
    )
    (LOG_ROOT / f"{command_id}_stage_config_copy.log").write_text(
        json.dumps(
            {
                "remote_stage_dir": remote_stage_dir,
                "remote_samples_path": remote_samples_path,
                "remote_units_path": remote_units_path,
                "verify_stdout": verify.stdout,
                "verify_stderr": verify.stderr,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    append_event(
        {
            "command_id": command_id,
            "phase": "stage",
            "status": "success",
            "manifest": str(RUN_ROOT / manifest_name),
            "generated_stage_dir": generated_stage_dir,
            "remote_stage_dir": remote_stage_dir,
            "samples_tsv": str(samples_path),
            "units_tsv": str(units_path),
            "stage_transport": "ssm_config_copy",
            "log": str(LOG_ROOT / f"{command_id}_stage.log"),
            "copy_log": str(LOG_ROOT / f"{command_id}_stage_config_copy.log"),
        }
    )
    return remote_stage_dir


def read_run_context(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if len(rows) != 1:
        raise RuntimeError(f"Expected exactly one run context row in {path}; got {len(rows)}")
    return {key: value for key, value in rows[0].items()}


def ensure_run_mount(command_id: str, context_name: str, timeout_seconds: int) -> None:
    context = read_run_context(RUN_ROOT / context_name)
    mount_id = context["MOUNT_ID"]
    existing = last_event(mount_id, "mount", "success")
    if existing:
        append_event(
            {
                "command_id": command_id,
                "phase": "mount",
                "status": "success",
                "mount_id": mount_id,
                "note": "existing successful mount event reused",
            }
        )
        return
    argv = [
        dyec(),
        "--json",
        "mounts",
        "create",
        context["SOURCE_S3_URI"],
        "--profile",
        PROFILE,
        "--region",
        REGION,
        "--cluster",
        CLUSTER,
        "--platform",
        context["PLATFORM"],
        "--mount-id",
        mount_id,
        "--run-id",
        context["RUNID"],
        "--file-system-path",
        f"/run_dir_mounts/{mount_id}",
        "--read-only",
        "--batch-import-metadata-on-create",
        "--auto-import",
        "NEW,CHANGED",
        "--wait",
        "--timeout-seconds",
        str(timeout_seconds),
    ]
    proc = run_cmd(argv, log_name=f"{mount_id}_mount.log", timeout=timeout_seconds + 300)
    if proc.returncode != 0 and "overlaps with existing" in proc.stderr:
        append_event(
            {
                "command_id": mount_id,
                "phase": "mount",
                "status": "success",
                "mount_id": mount_id,
                "note": "mount already existed with overlapping path",
                "stderr_tail": proc.stderr[-2000:],
            }
        )
        return
    require_success(proc, command_id=mount_id, phase="mount")
    append_event(
        {
            "command_id": mount_id,
            "phase": "mount",
            "status": "success",
            "mount_id": mount_id,
            "context": str(RUN_ROOT / context_name),
            "log": str(LOG_ROOT / f"{mount_id}_mount.log"),
        }
    )


def launch_workflow(
    command: Any,
    *,
    command_id: str,
    phase: str,
    dry_run: bool,
    stage_dir: str | None,
    run_context_name: str | None,
) -> str:
    prior = last_event(command_id, phase, "completed")
    if prior:
        return str(prior.get("session_name") or safe_id(command_id, "_dryrun" if dry_run else ""))
    launched = last_event(command_id, f"{phase}_launch", "success")
    if launched and launched.get("session_name"):
        return str(launched["session_name"])
    session_name = safe_id(command_id, "_dryrun" if dry_run else "")
    analysis_id = session_name
    run_context_file = str(RUN_ROOT / run_context_name) if run_context_name else None
    argv = [
        dyec(),
        *command.launch_argv(
            analysis_id=analysis_id,
            executing_entity=EXECUTING_ENTITY,
            git_tag=command.git_tag,
            profile=PROFILE,
            region=REGION,
            cluster=CLUSTER,
            stage_dir=stage_dir,
            session_name=session_name,
            run_context_file=run_context_file,
            dry_run=dry_run,
            skip_project_check=True,
        ),
    ]
    proc = run_cmd(argv, log_name=f"{command_id}_{phase}_launch.log", timeout=600)
    require_success(proc, command_id=command_id, phase=f"{phase}_launch")
    append_event(
        {
            "command_id": command_id,
            "phase": f"{phase}_launch",
            "status": "success",
            "session_name": session_name,
            "analysis_id": analysis_id,
            "stage_dir": stage_dir,
            "run_context": str(RUN_ROOT / run_context_name) if run_context_name else "",
            "log": str(LOG_ROOT / f"{command_id}_{phase}_launch.log"),
        }
    )
    return session_name


def read_status(command_id: str, session_name: str, phase: str) -> dict[str, Any] | None:
    proc = run_cmd(
        [
            dyec(),
            "--json",
            "workflow",
            "status",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
            "--session",
            session_name,
        ],
        log_name=f"{command_id}_{phase}_status_latest.log",
        timeout=180,
    )
    if proc.returncode != 0:
        return None
    return json.loads(proc.stdout)


def capture_logs(command_id: str, session_name: str, phase: str) -> None:
    run_cmd(
        [
            dyec(),
            "workflow",
            "logs",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
            "--session",
            session_name,
            "--lines",
            "240",
        ],
        log_name=f"{command_id}_{phase}_tmux_tail.log",
        timeout=180,
    )


def poll_until_terminal(command_id: str, session_name: str, phase: str, timeout_seconds: int) -> int | None:
    deadline = time.monotonic() + timeout_seconds
    last_payload: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        payload = read_status(command_id, session_name, phase)
        if payload is not None:
            last_payload = payload
            exit_code = payload.get("exit_code")
            if exit_code is not None:
                capture_logs(command_id, session_name, phase)
                append_event(
                    {
                        "command_id": command_id,
                        "phase": phase,
                        "status": "completed",
                        "session_name": session_name,
                        "exit_code": exit_code,
                        "status_payload": payload,
                        "status_log": str(LOG_ROOT / f"{command_id}_{phase}_status_latest.log"),
                        "tmux_tail_log": str(LOG_ROOT / f"{command_id}_{phase}_tmux_tail.log"),
                    }
                )
                return int(exit_code)
        time.sleep(60)
    append_event(
        {
            "command_id": command_id,
            "phase": phase,
            "status": "running",
            "session_name": session_name,
            "last_status_payload": last_payload,
            "note": f"poll timeout after {timeout_seconds}s",
        }
    )
    return None


def run_command(command: Any, args: argparse.Namespace) -> None:
    command_id = command.command_id
    if command_id in BLOCKED_COMMANDS:
        if not last_event(command_id, "blocked", "blocked"):
            append_event(
                {
                    "command_id": command_id,
                    "phase": "blocked",
                    "status": "blocked",
                    "reason": BLOCKED_COMMANDS[command_id],
                }
            )
        return
    stage_dir = None
    run_context_name = None
    if command_id in SAMPLE_INPUTS:
        if args.phase in {"dryrun", "all"}:
            stage_dir = stage_sample(command_id, SAMPLE_INPUTS[command_id], args.staging_timeout_seconds)
        else:
            stage_event = last_event(command_id, "stage", "success")
            if not stage_event:
                raise RuntimeError(f"No prior stage event for {command_id}")
            stage_dir = str(stage_event["remote_stage_dir"])
    elif command_id in RUN_CONTEXT_INPUTS:
        run_context_name = RUN_CONTEXT_INPUTS[command_id]
        ensure_run_mount(command_id, run_context_name, args.mount_timeout_seconds)
    else:
        raise RuntimeError(f"No input mapping for {command_id}")

    dry_exit = None
    if args.phase in {"dryrun", "all"}:
        session = launch_workflow(
            command,
            command_id=command_id,
            phase="dryrun",
            dry_run=True,
            stage_dir=stage_dir,
            run_context_name=run_context_name,
        )
        dry_exit = poll_until_terminal(command_id, session, "dryrun", args.dryrun_timeout_seconds)
    else:
        event = last_event(command_id, "dryrun", "completed")
        if event is not None:
            dry_exit = int(event.get("exit_code"))

    if args.phase == "dryrun":
        return
    if dry_exit != 0:
        append_event(
            {
                "command_id": command_id,
                "phase": "live",
                "status": "skipped",
                "reason": f"dryrun exit_code={dry_exit}",
            }
        )
        return
    session = launch_workflow(
        command,
        command_id=command_id,
        phase="live",
        dry_run=False,
        stage_dir=stage_dir,
        run_context_name=run_context_name,
    )
    poll_until_terminal(command_id, session, "live", args.live_timeout_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["dryrun", "live", "all"], default="dryrun")
    parser.add_argument("--staging-timeout-seconds", type=int, default=3600)
    parser.add_argument("--mount-timeout-seconds", type=int, default=2400)
    parser.add_argument("--dryrun-timeout-seconds", type=int, default=7200)
    parser.add_argument("--live-timeout-seconds", type=int, default=43200)
    parser.add_argument("--command-id", action="append", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    catalog = load_repository_catalog()
    selected = set(args.command_id or [])
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    append_event(
        {
            "command_id": "_driver",
            "phase": "start",
            "status": "running",
            "phase_requested": args.phase,
            "selected": sorted(selected),
        }
    )
    for command in catalog.commands():
        if command.repository != "daylily-omics-analysis":
            continue
        if selected and command.command_id not in selected:
            continue
        print(f"[{utc_now()}] {command.command_id}", flush=True)
        try:
            run_command(command, args)
        except Exception as exc:
            append_event(
                {
                    "command_id": command.command_id,
                    "phase": "driver",
                    "status": "failed",
                    "error": str(exc),
                }
            )
            print(f"{command.command_id}: {exc}", file=sys.stderr, flush=True)
    append_event(
        {
            "command_id": "_driver",
            "phase": "finish",
            "status": "completed",
            "phase_requested": args.phase,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
