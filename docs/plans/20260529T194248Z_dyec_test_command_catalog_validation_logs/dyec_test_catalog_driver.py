#!/usr/bin/env python3
"""Run and log the dyec-test DayOA command catalog validation.

The script is a durable execution helper for
docs/plans/20260529T194248Z_dyec_test_command_catalog_validation_ledger.md.
It intentionally invokes the public DYEC CLI for staging, launch, monitor,
export-triggered cleanup, mount management, and cluster inspection.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import fcntl
import json
import os
import re
import shlex
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from daylily_ec.aws.ssm import SsmCommandFailedError, resolve_headnode_instance_id, run_shell
from daylily_ec.repositories import load_repository_catalog


ROOT = Path(__file__).resolve().parents[3]
DAYOA_ROOT = Path("/Users/jmajor/projects/daylily/daylily-omics-analysis")
LOG_ROOT = Path(__file__).resolve().parent
COMMAND_LOG = LOG_ROOT / "command_log.tsv"
COMMAND_LOG_SEQ = LOG_ROOT / "command_log.seq"
EVENTS_PATH = LOG_ROOT / "events.jsonl"

PROFILE = "lsmc"
REGION = "us-west-2"
CLUSTER = "dyec-test"
EXECUTING_ENTITY = "ubuntu"
REFERENCE_S3_URI = "s3://lsmc-dayoa-references-usw2"
CONTROL_DATA_S3_URI = "s3://lsmc-dayoa-control-data-usw2"
STAGE_S3_URI = "s3://lsmc-ssf-sequencing-data/staged_external_data"
STAGE_TARGET = "/fsx/staging/staged_external_sequencing_data"
EXPORT_ROOT = "s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test"
RUN_SUFFIX = os.environ.get("DYEC_VALIDATION_RUN_SUFFIX", "ccv20260529r26")

SAMPLE_INPUT_ROOT = ROOT / "docs" / "plans" / "20260526T224018Z_blahab44_inputs"
GOODOLE_INPUT_ROOT = ROOT / "docs" / "plans" / "20260526T223700Z_goodole3_inputs"

SAMPLE_INPUTS = {
    "illumina_snv_alignstats": SAMPLE_INPUT_ROOT / "illumina_hg003_5x.tsv",
    "illumina_snv_alignstats_relatedness_vep_multiqc": SAMPLE_INPUT_ROOT / "illumina_hg003_5x.tsv",
    "illumina_hg002_kitchensink_multiqc": GOODOLE_INPUT_ROOT / "illumina_0p1x_kitchensink.tsv",
    "ultima_snv_alignstats": SAMPLE_INPUT_ROOT / "ultima_hg003_5x.tsv",
    "ultima_snv_alignstats_kitchensink": SAMPLE_INPUT_ROOT / "ultima_hg003_5x.tsv",
    "ont_snv_alignstats": SAMPLE_INPUT_ROOT / "ont_hg003_5x.tsv",
    "ont_snv_alignstats_kitchensink": SAMPLE_INPUT_ROOT / "ont_hg003_5x.tsv",
    "pacbio_snv_alignstats": SAMPLE_INPUT_ROOT / "pacbio_hg003_5x.tsv",
    "roche_snv_alignstats": SAMPLE_INPUT_ROOT / "roche_hg003_5x.tsv",
    "complete_genomics_mgi_snv_concordance": SAMPLE_INPUT_ROOT
    / "complete_genomics_mgi_hg003_candidate_blocked.tsv",
    "hybrid_ilmn_ont_snv": SAMPLE_INPUT_ROOT / "hybrid_ilmn_ont_hg003_5x5x.tsv",
    "hybrid_ilmn_ont_snv_kitchensink": SAMPLE_INPUT_ROOT / "hybrid_ilmn_ont_hg003_5x5x.tsv",
    "inflection-bjuice-product-v0.1": SAMPLE_INPUT_ROOT / "hybrid_ilmn_ont_hg003_5x5x.tsv",
    "hybrid_ultima_ont_snv": SAMPLE_INPUT_ROOT / "hybrid_ultima_ont_hg003_5x5x.tsv",
}

RUN_CONTEXT_INPUTS = {
    "illumina_run_qc": SAMPLE_INPUT_ROOT / "illumina_run_context.tsv",
    "illumina_bclconvert": SAMPLE_INPUT_ROOT / "illumina_run_context.tsv",
    "illumina_run_qc_bclconvert": SAMPLE_INPUT_ROOT / "illumina_run_context.tsv",
    "ont_run_qc": SAMPLE_INPUT_ROOT / "ont_run_context.tsv",
    "ultima_run_qc": SAMPLE_INPUT_ROOT / "ultima_run_context_candidate.tsv",
}

INPUT_BLOCKED: dict[str, dict[str, Any]] = {}


log_lock = threading.Lock()
event_lock = threading.Lock()
mount_locks: dict[str, threading.Lock] = {}
created_mount_ids: set[str] = set()
seq_counter: int | None = None
sample_stage_locks: dict[str, threading.Lock] = {}
sample_stage_cache: dict[str, dict[str, str]] = {}
sample_config_cache: dict[str, dict[str, str]] = {}


def utc_now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def shell_join(argv: list[str]) -> str:
    return " ".join(shlex.quote(str(arg)) for arg in argv)


def safe_name(value: str, *, limit: int = 72) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return cleaned[:limit] or "command"


def analysis_id(command_id: str, *, dry_run: bool) -> str:
    base = f"{RUN_SUFFIX}_{safe_name(command_id, limit=52)}"
    return f"{base}_dryrun" if dry_run else base


def export_uri_for(analysis: str) -> str:
    return f"{EXPORT_ROOT.rstrip('/')}/{EXECUTING_ENTITY}/{analysis}/"


def init_command_log() -> None:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    if COMMAND_LOG.exists():
        return
    COMMAND_LOG.write_text(
        "\t".join(
            [
                "seq",
                "start_utc",
                "end_utc",
                "label",
                "cwd",
                "env",
                "command",
                "returncode",
                "stdout_path",
                "stderr_path",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def next_seq() -> int:
    init_command_log()
    COMMAND_LOG_SEQ.parent.mkdir(parents=True, exist_ok=True)
    with COMMAND_LOG_SEQ.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            handle.seek(0)
            value = handle.read().strip()
            if value:
                seq = int(value)
            else:
                with COMMAND_LOG.open(encoding="utf-8") as log_handle:
                    seq = max(sum(1 for _ in log_handle) - 1, 0)
            seq += 1
            handle.seek(0)
            handle.truncate()
            handle.write(f"{seq}\n")
            handle.flush()
            os.fsync(handle.fileno())
            return seq
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def append_event(event: dict[str, Any]) -> None:
    payload = {"ts": utc_now(), **event}
    with event_lock:
        with EVENTS_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")


def load_events() -> list[dict[str, Any]]:
    if not EVENTS_PATH.exists():
        return []
    return [
        json.loads(line) for line in EVENTS_PATH.read_text(encoding="utf-8").splitlines() if line
    ]


def last_event(command_id: str, phase: str, status: str | None = None) -> dict[str, Any] | None:
    for event in reversed(load_events()):
        if event.get("command_id") != command_id or event.get("phase") != phase:
            continue
        if status is not None and event.get("status") != status:
            continue
        return event
    return None


def run_command(
    argv: list[str],
    *,
    label: str,
    cwd: Path = ROOT,
    timeout: int | None = None,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["AWS_PROFILE"] = PROFILE
    if env_extra:
        env.update(env_extra)
    seq = next_seq()
    safe_label = safe_name(label, limit=80)
    stdout_path = LOG_ROOT / f"{seq:05d}_{safe_label}.stdout.txt"
    stderr_path = LOG_ROOT / f"{seq:05d}_{safe_label}.stderr.txt"
    start = utc_now()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        stdout = proc.stdout
        stderr = proc.stderr
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\nTIMEOUT after {timeout}s"
        returncode = 124
        proc = subprocess.CompletedProcess(argv, returncode, stdout, stderr)
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    end = utc_now()
    env_label = "AWS_PROFILE=lsmc"
    with log_lock:
        with COMMAND_LOG.open("a", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            handle.write(
                "\t".join(
                    [
                        str(seq),
                        start,
                        end,
                        label,
                        str(cwd),
                        env_label,
                        shell_join(argv),
                        str(returncode),
                        str(stdout_path),
                        str(stderr_path),
                    ]
                )
                + "\n"
            )
            fcntl.flock(handle, fcntl.LOCK_UN)
    return proc


def run_headnode_script(
    script: str,
    *,
    label: str,
    timeout: int,
) -> int:
    env_label = "AWS_PROFILE=lsmc"
    seq = next_seq()
    safe_label = safe_name(label, limit=80)
    script_path = LOG_ROOT / f"{seq:05d}_{safe_label}.remote.sh"
    stdout_path = LOG_ROOT / f"{seq:05d}_{safe_label}.stdout.txt"
    stderr_path = LOG_ROOT / f"{seq:05d}_{safe_label}.stderr.txt"
    script_path.write_text(script, encoding="utf-8")
    start = utc_now()
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    command_repr = (
        "SSM run_shell "
        f"--cluster {CLUSTER} --instance-id {target.instance_id} "
        f"--region {REGION} --as-user ubuntu --script {script_path}"
    )
    try:
        result = run_shell(
            target.instance_id,
            REGION,
            script,
            profile=PROFILE,
            as_user="ubuntu",
            timeout=timeout,
            comment=f"DYEC catalog validation: {safe_name(label, limit=70)}",
        )
        returncode = result.response_code
        stdout = result.stdout
        stderr = result.stderr
    except SsmCommandFailedError as exc:
        returncode = exc.result.response_code
        stdout = exc.result.stdout
        stderr = exc.result.stderr
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    end = utc_now()
    with log_lock:
        with COMMAND_LOG.open("a", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            handle.write(
                "\t".join(
                    [
                        str(seq),
                        start,
                        end,
                        label,
                        str(ROOT),
                        env_label,
                        command_repr,
                        str(returncode),
                        str(stdout_path),
                        str(stderr_path),
                    ]
                )
                + "\n"
            )
            fcntl.flock(handle, fcntl.LOCK_UN)
    return returncode


def run_instance_script(
    instance_id: str,
    script: str,
    *,
    label: str,
    timeout: int,
) -> int:
    env_label = "AWS_PROFILE=lsmc"
    seq = next_seq()
    safe_label = safe_name(label, limit=80)
    script_path = LOG_ROOT / f"{seq:05d}_{safe_label}.remote.sh"
    stdout_path = LOG_ROOT / f"{seq:05d}_{safe_label}.stdout.txt"
    stderr_path = LOG_ROOT / f"{seq:05d}_{safe_label}.stderr.txt"
    script_path.write_text(script, encoding="utf-8")
    start = utc_now()
    command_repr = (
        "SSM run_shell "
        f"--cluster {CLUSTER} --instance-id {instance_id} "
        f"--region {REGION} --as-user ubuntu --script {script_path}"
    )
    try:
        result = run_shell(
            instance_id,
            REGION,
            script,
            profile=PROFILE,
            as_user="ubuntu",
            timeout=timeout,
            comment=f"DYEC catalog validation: {safe_name(label, limit=70)}",
        )
        returncode = result.response_code
        stdout = result.stdout
        stderr = result.stderr
    except SsmCommandFailedError as exc:
        returncode = exc.result.response_code
        stdout = exc.result.stdout
        stderr = exc.result.stderr
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    end = utc_now()
    with log_lock:
        with COMMAND_LOG.open("a", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            handle.write(
                "\t".join(
                    [
                        str(seq),
                        start,
                        end,
                        label,
                        str(ROOT),
                        env_label,
                        command_repr,
                        str(returncode),
                        str(stdout_path),
                        str(stderr_path),
                    ]
                )
                + "\n"
            )
            fcntl.flock(handle, fcntl.LOCK_UN)
    return returncode


def dyec_args(*args: str) -> list[str]:
    return ["dyec", *args]


def require_success(proc: subprocess.CompletedProcess[str], *, command_id: str, phase: str) -> None:
    if proc.returncode == 0:
        return
    append_event(
        {
            "command_id": command_id,
            "phase": phase,
            "status": "failed",
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-4000:],
        }
    )
    raise RuntimeError(f"{command_id} {phase} failed rc={proc.returncode}")


def run_gate0() -> int:
    init_command_log()
    commands = [
        (
            "dyec_git_status",
            ["git", "status", "--short", "--branch", "--untracked-files=all"],
            ROOT,
        ),
        ("dyec_git_head", ["git", "log", "-1", "--oneline", "--decorate"], ROOT),
        ("dyec_git_tags", ["git", "tag", "--points-at", "HEAD"], ROOT),
        (
            "dayoa_git_status",
            ["git", "status", "--short", "--branch", "--untracked-files=all"],
            DAYOA_ROOT,
        ),
        ("dayoa_git_head", ["git", "log", "-1", "--oneline", "--decorate"], DAYOA_ROOT),
        ("dayoa_git_tags", ["git", "tag", "--points-at", "HEAD"], DAYOA_ROOT),
        ("aws_identity", ["aws", "sts", "get-caller-identity", "--output", "json"], ROOT),
        ("dyec_version", dyec_args("--json", "version"), ROOT),
        (
            "catalog_snapshot",
            dyec_args(
                "--json",
                "repositories",
                "commands",
                "--config",
                "config/daylily_available_repositories.yaml",
                "--repository",
                "daylily-omics-analysis",
            ),
            ROOT,
        ),
        (
            "cluster_info",
            dyec_args("--json", "cluster-info", "--profile", PROFILE, "--region", REGION),
            ROOT,
        ),
        (
            "headnode_info",
            dyec_args(
                "--json",
                "headnode",
                "info",
                "--profile",
                PROFILE,
                "--region",
                REGION,
                "--cluster",
                CLUSTER,
            ),
            ROOT,
        ),
        (
            "mounts_list",
            dyec_args(
                "--json",
                "mounts",
                "list",
                "--profile",
                PROFILE,
                "--region",
                REGION,
                "--cluster",
                CLUSTER,
            ),
            ROOT,
        ),
        (
            "headnode_jobs",
            dyec_args(
                "headnode", "jobs", "--profile", PROFILE, "--region", REGION, "--cluster", CLUSTER
            ),
            ROOT,
        ),
    ]
    results = []
    for label, argv, cwd in commands:
        proc = run_command(argv, label=f"gate0_{label}", cwd=cwd, timeout=240)
        results.append({"label": label, "returncode": proc.returncode})
    catalog = load_repository_catalog(ROOT / "config" / "daylily_available_repositories.yaml")
    command_rows = [
        {
            "command_id": command.command_id,
            "class": command.command_class,
            "git_tag": command.git_tag,
            "genome": command.genome,
            "jobs": command.jobs,
            "input_contract": command.input_contract,
        }
        for command in catalog.commands()
        if command.repository == "daylily-omics-analysis"
    ]
    append_event(
        {
            "command_id": "_gate0",
            "phase": "baseline",
            "status": "completed" if all(item["returncode"] == 0 for item in results) else "failed",
            "results": results,
            "catalog_command_count": len(command_rows),
            "catalog_commands": command_rows,
        }
    )
    return 0 if all(item["returncode"] == 0 for item in results) else 1


def precheck_blocked(command_id: str) -> dict[str, Any]:
    spec = INPUT_BLOCKED[command_id]
    manifest = spec["manifest"]
    proc = run_command(
        dyec_args(
            "samples",
            "stage",
            str(manifest),
            "--reference-s3-uri",
            REFERENCE_S3_URI,
            "--control-data-s3-uri",
            CONTROL_DATA_S3_URI,
            "--stage-s3-uri",
            STAGE_S3_URI,
            "--stage-target",
            STAGE_TARGET,
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
            "--precheck-only",
        ),
        label=f"{command_id}_precheck_blocked",
        timeout=900,
    )
    append_event(
        {
            "command_id": command_id,
            "phase": "input_precheck",
            "status": "completed" if proc.returncode == 0 else "failed",
            "returncode": proc.returncode,
            "manifest": str(manifest),
        }
    )
    append_event(
        {
            "command_id": command_id,
            "phase": "final",
            "status": "blocked",
            "classification": "INPUT_BLOCKED",
            "reason": spec["reason"],
        }
    )
    return {"command_id": command_id, "status": "blocked", "classification": "INPUT_BLOCKED"}


def read_run_context(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if len(rows) != 1:
        raise RuntimeError(f"expected one run context row in {path}, got {len(rows)}")
    return dict(rows[0])


def list_mount_records(*, label: str) -> list[dict[str, Any]]:
    proc = run_command(
        dyec_args(
            "--json",
            "mounts",
            "list",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
        ),
        label=label,
        timeout=240,
    )
    require_success(proc, command_id="_mounts", phase=label)
    payload = json.loads(proc.stdout or "{}")
    mounts = payload.get("mounts", [])
    if not isinstance(mounts, list):
        raise RuntimeError(f"unexpected mounts list payload for {label}: {payload!r}")
    return [mount for mount in mounts if isinstance(mount, dict)]


def ensure_control_data_mount() -> int:
    existing = [
        mount
        for mount in list_mount_records(label="control_data_mount_list")
        if mount.get("purpose") == "control-data"
        and str(mount.get("headnode_path") or "") == "/fsx/control_data/"
    ]
    if existing:
        append_event(
            {
                "command_id": "_control_data_mount",
                "phase": "mount",
                "status": "success",
                "mount_id": existing[0].get("mount_id", ""),
                "lifecycle": existing[0].get("lifecycle", ""),
                "note": "existing control-data mount found",
            }
        )
        return 0
    proc = run_command(
        dyec_args(
            "--json",
            "mounts",
            "create",
            CONTROL_DATA_S3_URI.rstrip("/") + "/",
            "--purpose",
            "control-data",
            "--mount-id",
            "control_data",
            "--run-id",
            "control_data",
            "--platform",
            "OTHER",
            "--file-system-path",
            "/control_data/",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
            "--read-only",
            "--batch-import-metadata-on-create",
            "--auto-import",
            "NEW,CHANGED",
            "--wait",
            "--timeout-seconds",
            "2400",
        ),
        label="control_data_mount_create",
        timeout=3000,
    )
    require_success(proc, command_id="_control_data_mount", phase="mount_create")
    append_event(
        {
            "command_id": "_control_data_mount",
            "phase": "mount",
            "status": "success",
            "source_s3_uri": CONTROL_DATA_S3_URI.rstrip("/") + "/",
            "headnode_path": "/fsx/control_data/",
        }
    )
    return 0


def find_mount_record(mount_id: str, *, label: str) -> dict[str, Any] | None:
    for mount in list_mount_records(label=label):
        if mount.get("mount_id") == mount_id:
            return mount
    return None


def run_mount_has_readable_projection(mount_id: str) -> bool:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", mount_id):
        raise RuntimeError(f"unsafe mount id: {mount_id}")
    mount_dir = f"/fsx/run_dir_mounts/{mount_id}"
    script = "\n".join(
        [
            "set -euo pipefail",
            f"mount_dir={shlex.quote(mount_dir)}",
            'test -d "$mount_dir"',
            'first_file=$(find "$mount_dir" -mindepth 1 -maxdepth 6 -type f -print -quit)',
            'test -n "$first_file"',
            'test -r "$first_file"',
            'head -c 1 "$first_file" >/dev/null',
            'echo "readable_projection=$first_file"',
        ]
    )
    return (
        run_headnode_script(script, label=f"probe_run_mount_readable_{mount_id}", timeout=180) == 0
    )


def wait_for_mount_available(command_id: str, mount_id: str, *, timeout: int = 2400) -> None:
    deadline = time.monotonic() + timeout
    while True:
        mount = find_mount_record(mount_id, label=f"{command_id}_mount_wait_{mount_id}")
        if mount is None:
            raise RuntimeError(f"mount disappeared while waiting: {mount_id}")
        lifecycle = str(mount.get("lifecycle", "")).upper()
        projection_status = str(mount.get("local_projection_status", ""))
        append_event(
            {
                "command_id": command_id,
                "phase": "mount_wait",
                "status": "success" if lifecycle == "AVAILABLE" else "running",
                "mount_id": mount_id,
                "lifecycle": lifecycle,
                "local_projection_status": projection_status,
            }
        )
        if lifecycle == "AVAILABLE":
            return
        if projection_status == "present" and run_mount_has_readable_projection(mount_id):
            append_event(
                {
                    "command_id": command_id,
                    "phase": "mount_wait",
                    "status": "success",
                    "mount_id": mount_id,
                    "lifecycle": lifecycle,
                    "local_projection_status": projection_status,
                    "note": "accepted readable run-mount projection before DRA lifecycle reached AVAILABLE",
                }
            )
            return
        if lifecycle in {"FAILED", "DELETING", "DELETED"}:
            raise RuntimeError(f"mount {mount_id} reached terminal lifecycle {lifecycle}")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"mount {mount_id} did not become AVAILABLE within {timeout}s")
        time.sleep(30)


def ensure_run_mount(command_id: str, context_path: Path) -> None:
    context = read_run_context(context_path)
    mount_id = context["MOUNT_ID"]
    lock = mount_locks.setdefault(mount_id, threading.Lock())
    with lock:
        existing = find_mount_record(mount_id, label=f"{command_id}_mount_list_{mount_id}")
        if existing is not None:
            append_event(
                {
                    "command_id": command_id,
                    "phase": "mount",
                    "status": "success",
                    "mount_id": mount_id,
                    "lifecycle": existing.get("lifecycle", ""),
                    "local_projection_status": existing.get("local_projection_status", ""),
                    "note": "shared mount verified from live DYEC mount list",
                }
            )
            wait_for_mount_available(command_id, mount_id)
            return
        proc = run_command(
            dyec_args(
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
                "--no-wait",
            ),
            label=f"{command_id}_mount_{mount_id}",
            timeout=3000,
        )
        if proc.returncode != 0 and "overlaps with existing" not in proc.stderr:
            require_success(proc, command_id=command_id, phase="mount")
        wait_for_mount_available(command_id, mount_id)
        append_event(
            {
                "command_id": mount_id,
                "phase": "mount",
                "status": "success",
                "context": str(context_path),
                "source_s3_uri": context["SOURCE_S3_URI"],
                "mount_id": mount_id,
                "note": "created or already overlapped; retained for bundled run-analysis reuse",
            }
        )


def parse_remote_stage(stdout: str) -> list[str]:
    stages = []
    for match in re.finditer(r"Remote FSx stage directory:\s*(\S+)", stdout):
        stage = Path(match.group(1).rstrip("/")).name
        if stage:
            stages.append(stage)
    return stages


def parse_generated_config(stdout: str) -> tuple[str, str]:
    samples_match = re.search(r"samples\.tsv\s*->\s*(\S+)", stdout)
    units_match = re.search(r"units\.tsv\s*->\s*(\S+)", stdout)
    if not samples_match or not units_match:
        raise RuntimeError("Could not parse generated samples.tsv/units.tsv paths")
    return samples_match.group(1), units_match.group(1)


def ensure_sample_config(command_id: str, manifest: Path) -> tuple[str, str]:
    key = str(manifest.resolve())
    lock = sample_stage_locks.setdefault(key, threading.Lock())
    with lock:
        cached = sample_config_cache.get(key)
        if cached:
            append_event(
                {
                    "command_id": command_id,
                    "phase": "sample_config",
                    "status": "success",
                    "manifest": key,
                    "samples_file": cached["samples_file"],
                    "units_file": cached["units_file"],
                    "note": "shared local generated config already created in this driver process",
                }
            )
            return cached["samples_file"], cached["units_file"]

        config_dir = LOG_ROOT / "generated_sample_configs" / safe_name(manifest.stem)
        config_dir.mkdir(parents=True, exist_ok=True)
        proc = run_command(
            dyec_args(
                "samples",
                "stage",
                str(manifest),
                "--config-only",
                "--config-dir",
                str(config_dir),
                "--reference-s3-uri",
                REFERENCE_S3_URI,
                "--control-data-s3-uri",
                CONTROL_DATA_S3_URI,
                "--stage-s3-uri",
                STAGE_S3_URI,
                "--stage-target",
                STAGE_TARGET,
                "--profile",
                PROFILE,
                "--region",
                REGION,
            ),
            label=f"{safe_name(manifest.stem)}_shared_sample_config",
            timeout=1200,
        )
        require_success(proc, command_id=command_id, phase="sample_config")
        samples_file, units_file = parse_generated_config(proc.stdout)
        sample_config_cache[key] = {"samples_file": samples_file, "units_file": units_file}
        append_event(
            {
                "command_id": command_id,
                "phase": "sample_config",
                "status": "success",
                "manifest": key,
                "samples_file": samples_file,
                "units_file": units_file,
                "note": "generated local samples.tsv/units.tsv from default-mounted inputs; no sample DRA created",
            }
        )
        return samples_file, units_file


def ensure_sample_stage(command_id: str, manifest: Path) -> str:
    key = str(manifest.resolve())
    lock = sample_stage_locks.setdefault(key, threading.Lock())
    with lock:
        cached = sample_stage_cache.get(key)
        if cached:
            append_event(
                {
                    "command_id": command_id,
                    "phase": "sample_stage",
                    "status": "success",
                    "manifest": key,
                    "stage_dir": cached["stage_dir"],
                    "mount_id": cached["mount_id"],
                    "note": "shared sample stage already created in this driver process",
                }
            )
            return cached["stage_dir"]
        proc = run_command(
            dyec_args(
                "samples",
                "stage",
                str(manifest),
                "--reference-s3-uri",
                REFERENCE_S3_URI,
                "--control-data-s3-uri",
                CONTROL_DATA_S3_URI,
                "--stage-s3-uri",
                STAGE_S3_URI,
                "--stage-target",
                STAGE_TARGET,
                "--profile",
                PROFILE,
                "--region",
                REGION,
                "--cluster",
                CLUSTER,
                "--staging-mount-timeout-seconds",
                "2400",
            ),
            label=f"{safe_name(manifest.stem)}_shared_sample_stage",
            timeout=3600,
        )
        require_success(proc, command_id=command_id, phase="sample_stage")
        stage_dirs = re.findall(r"Remote FSx stage directory:\s*(\S+)", proc.stdout)
        stage_ids = parse_remote_stage(proc.stdout)
        if len(stage_dirs) != 1 or len(stage_ids) != 1:
            append_event(
                {
                    "command_id": command_id,
                    "phase": "sample_stage",
                    "status": "failed",
                    "manifest": key,
                    "stdout_tail": proc.stdout[-4000:],
                    "stderr_tail": proc.stderr[-4000:],
                    "reason": "expected exactly one staged FSx directory",
                }
            )
            raise RuntimeError(f"{command_id} sample_stage could not parse staged FSx directory")
        stage_dir = stage_dirs[0].rstrip("/")
        stage_id = stage_ids[0]
        created_mount_ids.add(stage_id)
        sample_stage_cache[key] = {"stage_dir": stage_dir, "mount_id": stage_id}
        append_event(
            {
                "command_id": command_id,
                "phase": "sample_stage",
                "status": "success",
                "manifest": key,
                "stage_dir": stage_dir,
                "mount_id": stage_id,
                "note": "created shared sample stage for manifest bundle",
            }
        )
        return stage_dir


def launch_sample(command: Any, *, dry_run: bool) -> subprocess.CompletedProcess[str]:
    command_id = command.command_id
    manifest = SAMPLE_INPUTS[command_id]
    samples_file, units_file = ensure_sample_config(command_id, manifest)
    return launch_workflow(
        command,
        dry_run=dry_run,
        samples_file=samples_file,
        units_file=units_file,
    )


def launch_workflow(
    command: Any,
    *,
    dry_run: bool,
    run_context_path: Path | None = None,
    stage_dir: str | None = None,
    samples_file: str | None = None,
    units_file: str | None = None,
) -> subprocess.CompletedProcess[str]:
    command_id = command.command_id
    aid = analysis_id(command_id, dry_run=dry_run)
    kwargs = {
        "analysis_id": aid,
        "executing_entity": EXECUTING_ENTITY,
        "git_tag": command.git_tag,
        "profile": PROFILE,
        "region": REGION,
        "cluster": CLUSTER,
        "session_name": aid,
        "run_context_file": str(run_context_path) if run_context_path else None,
        "stage_dir": stage_dir,
        "samples_file": samples_file,
        "units_file": units_file,
        "dry_run": dry_run,
        "skip_project_check": True,
        "export_destination_s3_uri": None if dry_run else export_uri_for(aid),
        "export_trigger": "none" if dry_run else "on-success",
        "delete_on_export_success": False if dry_run else True,
    }
    argv = dyec_args(*command.launch_argv(**kwargs))
    proc = run_command(
        argv,
        label=f"{command_id}_{'dryrun' if dry_run else 'live'}_launch",
        timeout=900,
    )
    return proc


def read_status(command_id: str, session_name: str, phase: str) -> dict[str, Any] | None:
    proc = run_command(
        dyec_args(
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
        ),
        label=f"{command_id}_{phase}_status",
        timeout=240,
    )
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def capture_logs(command_id: str, session_name: str, phase: str, *, lines: int = 240) -> None:
    run_command(
        dyec_args(
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
            str(lines),
        ),
        label=f"{command_id}_{phase}_logs",
        timeout=240,
    )


def poll_until_terminal(
    command_id: str, session_name: str, phase: str, timeout_seconds: int
) -> int | None:
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
                        "analysis_id": session_name,
                        "exit_code": int(exit_code),
                        "status_payload": payload,
                    }
                )
                return int(exit_code)
        time.sleep(20)
    append_event(
        {
            "command_id": command_id,
            "phase": phase,
            "status": "running",
            "session_name": session_name,
            "last_status_payload": last_payload,
            "note": f"poll timed out after {timeout_seconds}s",
        }
    )
    return None


def verify_export(command_id: str, aid: str) -> bool:
    uri = export_uri_for(aid)
    proc = run_command(
        ["aws", "s3", "ls", uri, "--recursive", "--summarize", "--human-readable"],
        label=f"{command_id}_export_s3_verify",
        timeout=900,
    )
    ok = (
        proc.returncode == 0
        and "Total Objects:" in proc.stdout
        and "Total Objects: 0" not in proc.stdout
    )
    append_event(
        {
            "command_id": command_id,
            "phase": "export_verify",
            "status": "success" if ok else "failed",
            "destination_s3_uri": uri,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-2000:],
            "stderr_tail": proc.stderr[-2000:],
        }
    )
    return ok


def run_local_export(command_id: str, aid: str) -> int:
    source_path = f"/fsx/analysis_results/{EXECUTING_ENTITY}/{aid}/"
    destination = export_uri_for(aid)
    output_dir = LOG_ROOT / "export_receipts" / aid
    output_dir.mkdir(parents=True, exist_ok=True)
    proc = run_command(
        dyec_args(
            "export",
            "--cluster",
            CLUSTER,
            "--source-path",
            source_path,
            "--destination-s3-uri",
            destination,
            "--region",
            REGION,
            "--output-dir",
            str(output_dir),
            "--profile",
            PROFILE,
            "--verbose",
            "--timeout-seconds",
            "7200",
        ),
        label=f"{command_id}_local_export_{aid}",
        timeout=7800,
    )
    append_event(
        {
            "command_id": command_id,
            "phase": "local_export",
            "status": "success" if proc.returncode == 0 else "failed",
            "returncode": proc.returncode,
            "analysis_id": aid,
            "source_path": source_path,
            "destination_s3_uri": destination,
            "receipt_path": str(output_dir / "fsx_export.yaml"),
            "stdout_tail": proc.stdout[-2000:],
            "stderr_tail": proc.stderr[-2000:],
        }
    )
    if proc.returncode != 0:
        return proc.returncode
    return 0 if verify_export(command_id, aid) else 1


def cleanup_analysis_dir(aid: str) -> int:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", aid):
        raise RuntimeError(f"unsafe analysis id: {aid}")
    analysis_dir = f"/fsx/analysis_results/{EXECUTING_ENTITY}/{aid}"
    script = "\n".join(
        [
            "set -euo pipefail",
            f"analysis_dir={shlex.quote(analysis_dir)}",
            'case "$analysis_dir" in',
            "  /fsx/analysis_results/ubuntu/ccv20260529*) ;;",
            '  *) echo "unsafe validation analysis dir: $analysis_dir" >&2; exit 2 ;;',
            "esac",
            'if [[ -d "$analysis_dir" ]]; then rm -rf -- "$analysis_dir"; fi',
            'if [[ -e "$analysis_dir" ]]; then echo "cleanup failed: $analysis_dir remains" >&2; exit 1; fi',
            'echo "deleted_or_absent=$analysis_dir"',
        ]
    )
    rc = run_headnode_script(script, label=f"cleanup_analysis_dir_{aid}", timeout=900)
    append_event(
        {
            "command_id": "_cleanup",
            "phase": "analysis_dir_delete",
            "status": "success" if rc == 0 else "failed",
            "analysis_id": aid,
            "analysis_dir": analysis_dir,
            "returncode": rc,
        }
    )
    return rc


def inspect_analysis_failure(aid: str) -> int:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", aid):
        raise RuntimeError(f"unsafe analysis id: {aid}")
    analysis_dir = f"/fsx/analysis_results/{EXECUTING_ENTITY}/{aid}"
    repo_dir = f"{analysis_dir}/daylily-omics-analysis"
    script = "\n".join(
        [
            "set -euo pipefail",
            f"analysis_dir={shlex.quote(analysis_dir)}",
            f"repo_dir={shlex.quote(repo_dir)}",
            "echo '=== status ==='",
            'status_file=/home/ubuntu/daylily-runs/$(basename "$analysis_dir")/status.json',
            'if [[ -f "$status_file" ]]; then cat "$status_file"; else echo "missing $status_file"; fi',
            "echo '=== repo ==='",
            'test -d "$repo_dir"',
            'cd "$repo_dir"',
            "pwd",
            "echo '=== latest snakemake logs ==='",
            "find .snakemake/log -maxdepth 1 -type f -printf '%T@ %p\\n' 2>/dev/null | sort -n | tail -n 5 || true",
            "latest_log=$(find .snakemake/log -maxdepth 1 -type f -printf '%T@ %p\\n' 2>/dev/null | sort -n | tail -n 1 | cut -d' ' -f2- || true)",
            'if [[ -n "$latest_log" && -f "$latest_log" ]]; then',
            '  echo "=== latest log path: $latest_log ==="',
            "  grep -nEi 'error|exception|traceback|missingoutput|ruleexception|failed|non-zero|killed|oom|out.of.memory|slurmstepd' \"$latest_log\" || true",
            "  echo '=== latest log tail ==='",
            '  tail -n 260 "$latest_log"',
            "fi",
            "echo '=== rule logs with errors ==='",
            "find results logs -type f \\( -name '*.log' -o -name '*.err' -o -name '*.out' \\) 2>/dev/null "
            "| xargs grep -nEi 'error|exception|traceback|missingoutput|ruleexception|failed|non-zero|killed|oom|out.of.memory|slurmstepd' 2>/dev/null "
            "| tail -n 220 || true",
        ]
    )
    rc = run_headnode_script(script, label=f"inspect_analysis_failure_{aid}", timeout=900)
    append_event(
        {
            "command_id": "_inspection",
            "phase": "analysis_failure",
            "status": "success" if rc == 0 else "failed",
            "analysis_id": aid,
            "returncode": rc,
        }
    )
    return rc


def find_vep_cache() -> int:
    script = "\n".join(
        [
            "set -euo pipefail",
            "echo '=== local VEP paths ==='",
            "for p in /fsx/references/runtime_assets/tool_specific_resources/vep /fsx/data/runtime_assets/tool_specific_resources/vep /fsx/references/runtime_assets/tool_specific_resources; do",
            '  echo "--- $p"',
            '  if [[ -e "$p" ]]; then',
            '    ls -la "$p" | head -n 80',
            "    find \"$p\" -maxdepth 5 -type d \\( -iname '*vep*' -o -iname '*GRCh38*' -o -iname 'homo_sapiens' \\) -print | sort | head -n 200",
            "  else",
            "    echo 'missing'",
            "  fi",
            "done",
            "echo '=== S3 VEP prefixes ==='",
            "for uri in s3://lsmc-dayoa-references-usw2/runtime_assets/tool_specific_resources/vep/homo_sapiens/ s3://daylily-dayoa-references-usw2/runtime_assets/tool_specific_resources/vep/homo_sapiens/ s3://lsmc-dayoa-control-data-usw2/runtime_assets/tool_specific_resources/vep/homo_sapiens/ s3://lsmc-dayoa-control-data-usw2/tool_specific_resources/vep/homo_sapiens/; do",
            '  echo "--- $uri"',
            '  aws s3 ls "$uri" --recursive | head -n 80 || true',
            "done",
        ]
    )
    rc = run_headnode_script(script, label="find_vep_cache", timeout=900)
    append_event(
        {
            "command_id": "_inspection",
            "phase": "find_vep_cache",
            "status": "success" if rc == 0 else "failed",
            "returncode": rc,
        }
    )
    return rc


def cleanup_mount_id_list(mount_ids: list[str] | set[str], *, context: str) -> int:
    targets = sorted(set(mount_ids))
    existing_mount_ids = {
        mount["mount_id"]
        for mount in list_mount_records(label=f"{context}_cleanup_mounts_list")
        if mount.get("mount_id")
    }
    append_event(
        {
            "command_id": "_cleanup",
            "phase": "mount_targets",
            "status": "running",
            "context": context,
            "mount_ids": targets,
        }
    )
    rc = 0
    for mount_id in targets:
        if mount_id not in existing_mount_ids:
            created_mount_ids.discard(mount_id)
            append_event(
                {
                    "command_id": "_cleanup",
                    "phase": "mount_delete",
                    "status": "skipped_absent",
                    "context": context,
                    "mount_id": mount_id,
                    "returncode": 0,
                    "stderr_tail": "",
                }
            )
            continue
        proc = run_command(
            dyec_args(
                "mounts",
                "delete",
                "--mount-id",
                mount_id,
                "--profile",
                PROFILE,
                "--region",
                REGION,
                "--cluster",
                CLUSTER,
                "--wait",
                "--timeout-seconds",
                "1800",
            ),
            label=f"{context}_cleanup_mount_{mount_id}",
            timeout=2400,
        )
        if proc.returncode != 0:
            rc = proc.returncode
        else:
            created_mount_ids.discard(mount_id)
        append_event(
            {
                "command_id": "_cleanup",
                "phase": "mount_delete",
                "status": "success" if proc.returncode == 0 else "failed",
                "context": context,
                "mount_id": mount_id,
                "returncode": proc.returncode,
                "stderr_tail": proc.stderr[-2000:],
            }
        )
    return rc


def validate_one(command: Any) -> dict[str, Any]:
    command_id = command.command_id
    append_event(
        {
            "command_id": command_id,
            "phase": "start",
            "status": "running",
            "command_class": command.command_class,
            "git_tag": command.git_tag,
        }
    )
    if command_id in INPUT_BLOCKED:
        return precheck_blocked(command_id)

    run_context_path = None
    if command.command_class == "sample_analysis":
        if command_id not in SAMPLE_INPUTS:
            raise RuntimeError(f"no sample input mapping for {command_id}")
        input_path = SAMPLE_INPUTS[command_id]
    elif command.command_class == "run_analysis":
        if command_id not in RUN_CONTEXT_INPUTS:
            raise RuntimeError(f"no run context mapping for {command_id}")
        run_context_path = RUN_CONTEXT_INPUTS[command_id]
        input_path = run_context_path
        ensure_run_mount(command_id, run_context_path)
    elif command.command_class == "utility":
        input_path = None
    else:
        raise RuntimeError(f"unsupported command class {command.command_class}")

    append_event(
        {
            "command_id": command_id,
            "phase": "input",
            "status": "success",
            "input_path": str(input_path) if input_path else "",
        }
    )

    dry_stage_ids: list[str] = []
    if command.command_class == "sample_analysis":
        dry_proc = launch_sample(command, dry_run=True)
        dry_stage_ids = parse_remote_stage(dry_proc.stdout)
        if dry_proc.returncode != 0:
            cleanup_mount_id_list(dry_stage_ids, context=f"{command_id}_dryrun_failed")
    else:
        dry_proc = launch_workflow(command, dry_run=True, run_context_path=run_context_path)
    require_success(dry_proc, command_id=command_id, phase="dryrun_launch")
    dry_aid = analysis_id(command_id, dry_run=True)
    dry_exit = poll_until_terminal(command_id, dry_aid, "dryrun", 10800)
    if dry_stage_ids:
        cleanup_mount_id_list(dry_stage_ids, context=f"{command_id}_dryrun")
    if dry_exit != 0:
        append_event(
            {
                "command_id": command_id,
                "phase": "final",
                "status": "dryrun_only",
                "classification": "DRYRUN_ACCEPTED" if dry_exit == 0 else "DAYOA_FAILURE",
                "reason": f"dry-run exit_code={dry_exit}; live launch skipped",
            }
        )
        return {
            "command_id": command_id,
            "status": "dryrun_only",
            "classification": "DAYOA_FAILURE",
            "dry_exit": dry_exit,
        }

    live_stage_ids: list[str] = []
    if command.command_class == "sample_analysis":
        live_proc = launch_sample(command, dry_run=False)
        live_stage_ids = parse_remote_stage(live_proc.stdout)
        if live_proc.returncode != 0:
            cleanup_mount_id_list(live_stage_ids, context=f"{command_id}_live_failed")
    else:
        live_proc = launch_workflow(command, dry_run=False, run_context_path=run_context_path)
    require_success(live_proc, command_id=command_id, phase="live_launch")
    live_aid = analysis_id(command_id, dry_run=False)
    live_exit = poll_until_terminal(command_id, live_aid, "live", 86400)
    if live_stage_ids:
        cleanup_mount_id_list(live_stage_ids, context=f"{command_id}_live")
    if live_exit == 0:
        export_ok = verify_export(command_id, live_aid)
        append_event(
            {
                "command_id": command_id,
                "phase": "final",
                "status": "success" if export_ok else "failed",
                "classification": "SUCCESS" if export_ok else "INFRA_FAILURE",
                "analysis_id": live_aid,
                "export_uri": export_uri_for(live_aid),
            }
        )
        return {
            "command_id": command_id,
            "status": "success" if export_ok else "failed",
            "classification": "SUCCESS" if export_ok else "INFRA_FAILURE",
            "live_exit": live_exit,
        }

    append_event(
        {
            "command_id": command_id,
            "phase": "final",
            "status": "failed",
            "classification": "DAYOA_FAILURE",
            "analysis_id": live_aid,
            "reason": f"live exit_code={live_exit}",
        }
    )
    return {
        "command_id": command_id,
        "status": "failed",
        "classification": "DAYOA_FAILURE",
        "live_exit": live_exit,
    }


def cleanup_mounts() -> int:
    initial = run_command(
        dyec_args(
            "--json",
            "mounts",
            "list",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
        ),
        label="cleanup_mounts_before",
        timeout=240,
    )
    mount_ids = sorted(created_mount_ids)
    append_event(
        {
            "command_id": "_cleanup",
            "phase": "mount_targets",
            "status": "running",
            "mount_ids": mount_ids,
            "precleanup_returncode": initial.returncode,
        }
    )
    rc = cleanup_mount_id_list(mount_ids, context="driver_final")
    after = run_command(
        dyec_args(
            "--json",
            "mounts",
            "list",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
        ),
        label="cleanup_mounts_after",
        timeout=240,
    )
    append_event(
        {
            "command_id": "_cleanup",
            "phase": "finish",
            "status": "success" if rc == 0 else "failed",
            "postcleanup_returncode": after.returncode,
        }
    )
    return rc


def run_catalog(selected: list[str] | None, max_workers: int) -> int:
    catalog = load_repository_catalog(ROOT / "config" / "daylily_available_repositories.yaml")
    commands = [
        command for command in catalog.commands() if command.repository == "daylily-omics-analysis"
    ]
    if selected:
        wanted = set(selected)
        commands = [command for command in commands if command.command_id in wanted]
    append_event(
        {
            "command_id": "_driver",
            "phase": "start",
            "status": "running",
            "selected": [command.command_id for command in commands],
            "max_workers": max_workers,
        }
    )
    failures = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(validate_one, command): command.command_id for command in commands
        }
        for future in as_completed(futures):
            command_id = futures[future]
            try:
                result = future.result()
                print(f"{utc_now()} {command_id} {result}", flush=True)
                if result.get("status") not in {"success", "dryrun_only", "blocked"}:
                    failures += 1
            except Exception as exc:
                failures += 1
                append_event(
                    {
                        "command_id": command_id,
                        "phase": "driver",
                        "status": "failed",
                        "classification": "INFRA_FAILURE",
                        "error": str(exc),
                    }
                )
                print(f"{utc_now()} {command_id} ERROR {exc}", file=sys.stderr, flush=True)
    cleanup_rc = cleanup_mounts()
    append_event(
        {
            "command_id": "_driver",
            "phase": "finish",
            "status": "completed" if failures == 0 and cleanup_rc == 0 else "failed",
            "failures": failures,
            "cleanup_returncode": cleanup_rc,
        }
    )
    return 0 if failures == 0 and cleanup_rc == 0 else 1


def run_dryrun_only(command_id: str, stage_dir: str | None) -> int:
    catalog = load_repository_catalog(ROOT / "config" / "daylily_available_repositories.yaml")
    command = catalog.get_command(command_id)
    run_context_path = None
    if command.command_class == "sample_analysis":
        if stage_dir is None:
            manifest = SAMPLE_INPUTS.get(command_id)
            if manifest is None:
                raise RuntimeError(f"no sample input mapping for {command_id}")
            stage_dir = ensure_sample_stage(command_id, manifest)
    elif command.command_class == "run_analysis":
        run_context_path = RUN_CONTEXT_INPUTS.get(command_id)
        if run_context_path is None:
            raise RuntimeError(f"no run context mapping for {command_id}")
    elif command.command_class != "utility":
        raise RuntimeError(f"unsupported command class {command.command_class}")

    append_event(
        {
            "command_id": command_id,
            "phase": "dryrun_only_start",
            "status": "running",
            "command_class": command.command_class,
            "git_tag": command.git_tag,
            "stage_dir": stage_dir or "",
            "run_context_path": str(run_context_path) if run_context_path else "",
        }
    )
    proc = launch_workflow(
        command, dry_run=True, run_context_path=run_context_path, stage_dir=stage_dir
    )
    require_success(proc, command_id=command_id, phase="dryrun_launch")
    dry_aid = analysis_id(command_id, dry_run=True)
    dry_exit = poll_until_terminal(command_id, dry_aid, "dryrun", 10800)
    append_event(
        {
            "command_id": command_id,
            "phase": "dryrun_only_final",
            "status": "success" if dry_exit == 0 else "failed",
            "classification": "SUCCESS" if dry_exit == 0 else "DAYOA_FAILURE",
            "analysis_id": dry_aid,
            "exit_code": dry_exit,
        }
    )
    return 0 if dry_exit == 0 else 1


def run_live_only(command_id: str, stage_dir: str | None) -> int:
    catalog = load_repository_catalog(ROOT / "config" / "daylily_available_repositories.yaml")
    command = catalog.get_command(command_id)
    run_context_path = None
    if command.command_class == "sample_analysis":
        if not stage_dir:
            raise RuntimeError(f"{command_id} live-only requires --live-stage-dir")
    elif command.command_class == "run_analysis":
        run_context_path = RUN_CONTEXT_INPUTS.get(command_id)
        if run_context_path is None:
            raise RuntimeError(f"no run context mapping for {command_id}")
    elif command.command_class != "utility":
        raise RuntimeError(f"unsupported command class {command.command_class}")

    append_event(
        {
            "command_id": command_id,
            "phase": "live_only_start",
            "status": "running",
            "command_class": command.command_class,
            "git_tag": command.git_tag,
            "stage_dir": stage_dir or "",
            "run_context_path": str(run_context_path) if run_context_path else "",
        }
    )
    proc = launch_workflow(
        command, dry_run=False, run_context_path=run_context_path, stage_dir=stage_dir
    )
    require_success(proc, command_id=command_id, phase="live_launch")
    live_aid = analysis_id(command_id, dry_run=False)
    live_exit = poll_until_terminal(command_id, live_aid, "live", 86400)
    export_ok = False
    if live_exit == 0:
        export_ok = verify_export(command_id, live_aid)
    append_event(
        {
            "command_id": command_id,
            "phase": "live_only_final",
            "status": "success" if live_exit == 0 and export_ok else "failed",
            "classification": "SUCCESS"
            if live_exit == 0 and export_ok
            else ("DAYOA_FAILURE" if live_exit not in {0, None} else "INFRA_FAILURE"),
            "analysis_id": live_aid,
            "exit_code": live_exit,
            "export_uri": export_uri_for(live_aid) if export_ok else "",
        }
    )
    return 0 if live_exit == 0 and export_ok else 1


def repair_mermaid_chrome() -> int:
    script = "\n".join(
        [
            "set -euo pipefail",
            "echo USER=$(id -un)",
            "echo HOME=$HOME",
            "source /home/ubuntu/miniconda3/etc/profile.d/conda.sh",
            "conda activate DAYOA",
            "echo PATH=$PATH",
            "echo MMDC=$(command -v mmdc || true)",
            "echo NPX=$(command -v npx || true)",
            "mmdc --version",
            "node -e \"const p=require('/home/ubuntu/miniconda3/envs/DAYOA/lib/node_modules/@mermaid-js/mermaid-cli/node_modules/puppeteer-core/package.json'); console.log('puppeteer-core='+p.version)\"",
            "rm -rf /home/ubuntu/.cache/puppeteer/chrome/linux-148.0.7778.97",
            "npx --yes puppeteer browsers install chrome@148.0.7778.97",
            "export PUPPETEER_EXECUTABLE_PATH=/home/ubuntu/.cache/puppeteer/chrome/linux-148.0.7778.97/chrome-linux64/chrome",
            'ls -l "$PUPPETEER_EXECUTABLE_PATH"',
            '"$PUPPETEER_EXECUTABLE_PATH" --version',
            "printf '%s\\n' 'graph TD' 'A-->B' > /tmp/daylily_mermaid_validation.mmd",
            "mmdc -i /tmp/daylily_mermaid_validation.mmd -o /tmp/daylily_mermaid_validation.svg",
            "test -s /tmp/daylily_mermaid_validation.svg",
            "sha256sum /tmp/daylily_mermaid_validation.svg",
        ]
    )
    rc = run_headnode_script(script, label="repair_mermaid_chrome", timeout=2400)
    append_event(
        {
            "command_id": "_headnode_runtime",
            "phase": "mermaid_chrome_repair",
            "status": "success" if rc == 0 else "failed",
            "returncode": rc,
        }
    )
    return rc


def cleanup_selected_mounts(mount_ids: list[str]) -> int:
    before = run_command(
        dyec_args(
            "--json",
            "mounts",
            "list",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
        ),
        label="manual_cleanup_mounts_before",
        timeout=240,
    )
    rc = cleanup_mount_id_list(mount_ids, context="manual")
    after = run_command(
        dyec_args(
            "--json",
            "mounts",
            "list",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
        ),
        label="manual_cleanup_mounts_after",
        timeout=240,
    )
    append_event(
        {
            "command_id": "_cleanup",
            "phase": "manual_finish",
            "status": "success" if rc == 0 else "failed",
            "mount_ids": sorted(set(mount_ids)),
            "precleanup_returncode": before.returncode,
            "postcleanup_returncode": after.returncode,
        }
    )
    return rc


def summarize() -> int:
    events = load_events()
    finals = [event for event in events if event.get("phase") == "final"]
    print(json.dumps({"finals": finals, "count": len(finals)}, indent=2, sort_keys=True))
    return 0


def log_workflow_status(command_id: str, session_name: str, phase: str) -> int:
    payload = read_status(command_id, session_name, phase)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload is not None else 1


def log_workflow_logs(command_id: str, session_name: str, phase: str, *, lines: int) -> int:
    capture_logs(command_id, session_name, phase, lines=lines)
    return 0


def log_headnode_jobs() -> int:
    proc = run_command(
        dyec_args(
            "headnode", "jobs", "--profile", PROFILE, "--region", REGION, "--cluster", CLUSTER
        ),
        label="manual_headnode_jobs",
        timeout=240,
    )
    print(proc.stdout)
    print(proc.stderr, file=sys.stderr)
    return proc.returncode


def log_mounts_list() -> int:
    proc = run_command(
        dyec_args(
            "--json",
            "mounts",
            "list",
            "--profile",
            PROFILE,
            "--region",
            REGION,
            "--cluster",
            CLUSTER,
        ),
        label="manual_mounts_list",
        timeout=240,
    )
    print(proc.stdout)
    print(proc.stderr, file=sys.stderr)
    return proc.returncode


def log_headnode_fsx_health() -> int:
    script = "\n".join(
        [
            "set -euo pipefail",
            "echo '=== identity ==='",
            "date -u +%Y-%m-%dT%H:%M:%SZ",
            "hostname -f || hostname",
            "id",
            "uptime",
            "echo '=== memory ==='",
            "free -h",
            "echo '=== filesystems ==='",
            "df -hT /fsx /dev/shm /tmp",
            "df -i /fsx /dev/shm /tmp",
            "echo '=== /fsx mount ==='",
            "findmnt /fsx || true",
            "mount | grep ' /fsx ' || true",
            "echo '=== lustre df ==='",
            "if command -v lfs >/dev/null 2>&1; then lfs df -h /fsx; lfs df -i /fsx; else echo 'lfs not installed'; fi",
            "echo '=== validation analysis dirs ==='",
            "find /fsx/analysis_results/ubuntu -maxdepth 1 -type d -name 'ccv20260529*' -printf '%f\\n' | sort | wc -l",
            "find /fsx/analysis_results/ubuntu -maxdepth 1 -type d -name 'ccv20260529*' -printf '%TY-%Tm-%TdT%TH:%TM:%TS %f\\n' | sort | tail -n 40",
            "echo '=== validation active dirs file-count sample ==='",
            'for d in /fsx/analysis_results/ubuntu/ccv20260529r6_ont_snv_alignstats_kitchensink /fsx/analysis_results/ubuntu/ccv20260529r6_pacbio_snv_alignstats; do [[ -d "$d" ]] && echo "$(find "$d" -xdev -type f | wc -l) files $d"; done',
            "echo '=== daylily run statuses ==='",
            'find /home/ubuntu/daylily-runs -maxdepth 2 -name status.json -path \'*/ccv20260529*/*\' -print | sort | tail -n 40 | while read -r f; do echo "--- $f"; cat "$f"; done',
            "echo '=== process sample ==='",
            "ps -eo pid,ppid,stat,pcpu,pmem,etime,cmd --sort=-pcpu | head -n 35",
        ]
    )
    rc = run_headnode_script(script, label="manual_headnode_fsx_health", timeout=900)
    append_event(
        {
            "command_id": "_inspection",
            "phase": "headnode_fsx_health",
            "status": "success" if rc == 0 else "failed",
            "returncode": rc,
        }
    )
    return rc


def log_headnode_slurm_health() -> int:
    script = "\n".join(
        [
            "set -euo pipefail",
            "echo '=== sinfo summary ==='",
            "sinfo -o '%P|%a|%D|%t|%C|%m|%G|%N'",
            "echo '=== nodes ==='",
            "sinfo -Nel || true",
            "echo '=== queue ==='",
            "squeue -o '%i|%P|%C|%t|%M|%D|%R|%j'",
            "echo '=== fairshare/account summary ==='",
            "sacctmgr show assoc format=Account,User,Partition,GrpTRES,GrpJobs,GrpSubmit,MaxTRES,MaxJobs,MaxSubmit -Pn 2>/dev/null | head -n 80 || true",
        ]
    )
    rc = run_headnode_script(script, label="manual_headnode_slurm_health", timeout=300)
    append_event(
        {
            "command_id": "_inspection",
            "phase": "headnode_slurm_health",
            "status": "success" if rc == 0 else "failed",
            "returncode": rc,
        }
    )
    return rc


def probe_headnode_s3_prefix(prefix: str) -> int:
    probe_uri = prefix.rstrip("/") + f"/_dyec_probe_{int(time.time())}.txt"
    script = "\n".join(
        [
            "set -euo pipefail",
            f"prefix={shlex.quote(prefix.rstrip('/') + '/')}",
            f"probe_uri={shlex.quote(probe_uri)}",
            "tmp=$(mktemp)",
            'printf \'dyec catalog validation probe %s\\n\' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$tmp"',
            'aws s3 ls "$prefix" >/tmp/dyec_probe_ls.out 2>/tmp/dyec_probe_ls.err || true',
            "cat /tmp/dyec_probe_ls.err >&2",
            'aws s3 cp "$tmp" "$probe_uri"',
            'aws s3 rm "$probe_uri"',
            'rm -f "$tmp"',
        ]
    )
    rc = run_headnode_script(script, label="probe_headnode_s3_prefix", timeout=600)
    append_event(
        {
            "command_id": "_headnode_runtime",
            "phase": "s3_prefix_probe",
            "status": "success" if rc == 0 else "failed",
            "returncode": rc,
            "prefix": prefix.rstrip("/") + "/",
        }
    )
    return rc


def ensure_reference_compat_symlink() -> int:
    script = "\n".join(
        [
            "set -euo pipefail",
            "echo '=== headnode reference compatibility path ==='",
            "if [[ -e /fsx/data && ! -L /fsx/data ]]; then",
            '  if [[ "$(readlink -f /fsx/data)" != /fsx/references ]]; then',
            "    echo 'ERROR: /fsx/data exists but does not resolve to /fsx/references' >&2",
            "    exit 1",
            "  fi",
            "else",
            "  sudo ln -sfn /fsx/references /fsx/data",
            "fi",
            "test -L /fsx/data",
            'test "$(readlink -f /fsx/data)" = /fsx/references',
            "ls -ld /fsx/data",
            "echo '=== compute-node reference compatibility path ==='",
            "export PROJECT=dyec-test",
            "mapfile -t node_rows < <(sinfo -h -N -o '%N|%P' | sed 's/*//g' | sort -u)",
            "if [[ ${#node_rows[@]} -eq 0 ]]; then",
            "  echo 'ERROR: no Slurm compute nodes are visible' >&2",
            "  exit 1",
            "fi",
            'for row in "${node_rows[@]}"; do',
            "  node=${row%%|*}",
            "  partition=${row#*|}",
            "  partition=${partition%%,*}",
            '  echo "--- $node partition=$partition"',
            '  srun --overlap --partition="$partition" --nodes=1 --ntasks=1 --nodelist="$node" bash -lc \'set -euo pipefail; if [[ -e /fsx/data && ! -L /fsx/data ]]; then if [[ "$(readlink -f /fsx/data)" != /fsx/references ]]; then echo "ERROR: /fsx/data exists but does not resolve to /fsx/references" >&2; exit 1; fi; else sudo ln -sfn /fsx/references /fsx/data; fi; test -L /fsx/data; test "$(readlink -f /fsx/data)" = /fsx/references; ls -ld /fsx/data\'',
            "done",
        ]
    )
    rc = run_headnode_script(script, label="ensure_reference_compat_symlink", timeout=1800)
    append_event(
        {
            "command_id": "_headnode_runtime",
            "phase": "reference_compat_symlink",
            "status": "success" if rc == 0 else "failed",
            "returncode": rc,
        }
    )
    return rc


def ensure_reference_compat_symlink_ec2() -> int:
    proc = run_command(
        [
            "aws",
            "ec2",
            "describe-instances",
            "--region",
            REGION,
            "--filters",
            "Name=instance-state-name,Values=running",
            f"Name=tag:parallelcluster:cluster-name,Values={CLUSTER}",
            "Name=tag:parallelcluster:node-type,Values=Compute",
            "--query",
            "Reservations[].Instances[].InstanceId",
            "--output",
            "json",
        ],
        label="list_compute_instances_for_reference_compat_symlink",
        timeout=240,
    )
    require_success(proc, command_id="_headnode_runtime", phase="list_compute_instances")
    instance_ids = json.loads(proc.stdout)
    if not instance_ids:
        append_event(
            {
                "command_id": "_headnode_runtime",
                "phase": "reference_compat_symlink_ec2",
                "status": "failed",
                "reason": "no running compute instances found",
            }
        )
        return 1
    script = "\n".join(
        [
            "set -euo pipefail",
            "echo USER=$(id -un)",
            "hostname -f || hostname",
            "if [[ -e /fsx/data && ! -L /fsx/data ]]; then",
            '  if [[ "$(readlink -f /fsx/data)" != /fsx/references ]]; then',
            "    echo 'ERROR: /fsx/data exists but does not resolve to /fsx/references' >&2",
            "    exit 1",
            "  fi",
            "else",
            "  sudo ln -sfn /fsx/references /fsx/data",
            "fi",
            "test -L /fsx/data",
            'test "$(readlink -f /fsx/data)" = /fsx/references',
            "ls -ld /fsx/data",
        ]
    )
    failures = 0
    for instance_id in instance_ids:
        rc = run_instance_script(
            instance_id,
            script,
            label=f"ensure_reference_compat_symlink_{instance_id}",
            timeout=300,
        )
        if rc != 0:
            failures += 1
        append_event(
            {
                "command_id": "_headnode_runtime",
                "phase": "reference_compat_symlink_ec2_instance",
                "status": "success" if rc == 0 else "failed",
                "instance_id": instance_id,
                "returncode": rc,
            }
        )
    append_event(
        {
            "command_id": "_headnode_runtime",
            "phase": "reference_compat_symlink_ec2",
            "status": "success" if failures == 0 else "failed",
            "instances": instance_ids,
            "failures": failures,
        }
    )
    return 0 if failures == 0 else 1


def cancel_slurm_job(job_id: str) -> int:
    if not re.fullmatch(r"[0-9]+", job_id):
        raise RuntimeError(f"unsafe Slurm job id: {job_id}")
    script = "\n".join(
        [
            "set -euo pipefail",
            "export PROJECT=dyec-test",
            f"job_id={shlex.quote(job_id)}",
            "echo '=== before ==='",
            "squeue -j \"$job_id\" -o '%i|%P|%C|%t|%M|%D|%R|%j' || true",
            'scancel "$job_id" || true',
            "sleep 2",
            "echo '=== after ==='",
            "squeue -j \"$job_id\" -o '%i|%P|%C|%t|%M|%D|%R|%j' || true",
        ]
    )
    rc = run_headnode_script(script, label=f"cancel_slurm_job_{job_id}", timeout=300)
    append_event(
        {
            "command_id": "_cleanup",
            "phase": "slurm_cancel",
            "status": "success" if rc == 0 else "failed",
            "job_id": job_id,
            "returncode": rc,
        }
    )
    return rc


def cache_roche_containers() -> int:
    script = "\n".join(
        [
            "set -euo pipefail",
            "host_name=$(hostname)",
            "cache_dir=/fsx/resources/environments/containers/ubuntu/${host_name}",
            'install -d -m 1777 "$cache_dir"',
            "command -v singularity",
            "declare -A images",
            "images[7a424a40c6fd659f4d052893dd3554fa]='docker://roche/sbxd-small-variant-caller:latest'",
            "images[49599841644a581df7ed78059707ff95]='docker://broadinstitute/gatk-nightly:2025-08-19-4.6.2.0-17-g2a1f41bf3-NIGHTLY-SNAPSHOT'",
            'for hash in "${!images[@]}"; do',
            "  uri=${images[$hash]}",
            "  image_path=${cache_dir}/${hash}.simg",
            '  echo "=== $hash $uri ==="',
            '  if [[ ! -s "$image_path" ]]; then',
            "    tmp=${image_path}.tmp.$$",
            '    rm -f "$tmp"',
            '    singularity pull --disable-cache "$tmp" "$uri"',
            '    mv "$tmp" "$image_path"',
            "  fi",
            '  test -s "$image_path"',
            '  ls -lh "$image_path"',
            '  sha256sum "$image_path"',
            "done",
        ]
    )
    rc = run_headnode_script(script, label="cache_roche_containers", timeout=7200)
    append_event(
        {
            "command_id": "_headnode_runtime",
            "phase": "cache_roche_containers",
            "status": "success" if rc == 0 else "failed",
            "returncode": rc,
        }
    )
    return rc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate0", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--repair-mermaid-chrome", action="store_true")
    parser.add_argument("--cleanup-mount-id", action="append", default=None)
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument("--status-session")
    parser.add_argument("--logs-session")
    parser.add_argument("--logs-lines", type=int, default=240)
    parser.add_argument("--status-command-id")
    parser.add_argument("--status-phase", default="live")
    parser.add_argument("--headnode-jobs", action="store_true")
    parser.add_argument("--mounts-list", action="store_true")
    parser.add_argument("--headnode-fsx-health", action="store_true")
    parser.add_argument("--headnode-slurm-health", action="store_true")
    parser.add_argument("--headnode-script-file")
    parser.add_argument("--instance-script-file")
    parser.add_argument("--instance-id")
    parser.add_argument("--probe-headnode-s3-prefix")
    parser.add_argument("--ensure-reference-compat-symlink", action="store_true")
    parser.add_argument("--ensure-reference-compat-symlink-ec2", action="store_true")
    parser.add_argument("--ensure-control-data-mount", action="store_true")
    parser.add_argument("--local-export-analysis-id")
    parser.add_argument("--local-export-command-id")
    parser.add_argument("--cleanup-analysis-id")
    parser.add_argument("--inspect-analysis-failure")
    parser.add_argument("--find-vep-cache", action="store_true")
    parser.add_argument("--cancel-slurm-job-id")
    parser.add_argument("--cache-roche-containers", action="store_true")
    parser.add_argument("--command-id", action="append", default=None)
    parser.add_argument("--dryrun-only-command-id")
    parser.add_argument("--dryrun-stage-dir")
    parser.add_argument("--live-only-command-id")
    parser.add_argument("--live-stage-dir")
    parser.add_argument("--max-workers", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_command_log()
    if args.gate0:
        return run_gate0()
    if args.run:
        return run_catalog(args.command_id, args.max_workers)
    if args.dryrun_only_command_id:
        return run_dryrun_only(args.dryrun_only_command_id, args.dryrun_stage_dir)
    if args.live_only_command_id:
        return run_live_only(args.live_only_command_id, args.live_stage_dir)
    if args.repair_mermaid_chrome:
        return repair_mermaid_chrome()
    if args.cleanup_mount_id:
        return cleanup_selected_mounts(args.cleanup_mount_id)
    if args.summarize:
        return summarize()
    if args.status_session:
        command_id = args.status_command_id or args.status_session
        return log_workflow_status(command_id, args.status_session, args.status_phase)
    if args.logs_session:
        command_id = args.status_command_id or args.logs_session
        return log_workflow_logs(
            command_id, args.logs_session, args.status_phase, lines=args.logs_lines
        )
    if args.headnode_jobs:
        return log_headnode_jobs()
    if args.mounts_list:
        return log_mounts_list()
    if args.headnode_fsx_health:
        return log_headnode_fsx_health()
    if args.headnode_slurm_health:
        return log_headnode_slurm_health()
    if args.headnode_script_file:
        script_path = Path(args.headnode_script_file)
        return run_headnode_script(
            script_path.read_text(encoding="utf-8"), label=script_path.stem, timeout=900
        )
    if args.instance_script_file:
        if not args.instance_id:
            raise RuntimeError("--instance-id is required with --instance-script-file")
        script_path = Path(args.instance_script_file)
        return run_instance_script(
            args.instance_id,
            script_path.read_text(encoding="utf-8"),
            label=script_path.stem,
            timeout=900,
        )
    if args.probe_headnode_s3_prefix:
        return probe_headnode_s3_prefix(args.probe_headnode_s3_prefix)
    if args.ensure_reference_compat_symlink:
        return ensure_reference_compat_symlink()
    if args.ensure_reference_compat_symlink_ec2:
        return ensure_reference_compat_symlink_ec2()
    if args.ensure_control_data_mount:
        return ensure_control_data_mount()
    if args.local_export_analysis_id:
        command_id = args.local_export_command_id or args.local_export_analysis_id
        return run_local_export(command_id, args.local_export_analysis_id)
    if args.cleanup_analysis_id:
        return cleanup_analysis_dir(args.cleanup_analysis_id)
    if args.inspect_analysis_failure:
        return inspect_analysis_failure(args.inspect_analysis_failure)
    if args.find_vep_cache:
        return find_vep_cache()
    if args.cancel_slurm_job_id:
        return cancel_slurm_job(args.cancel_slurm_job_id)
    if args.cache_roche_containers:
        return cache_roche_containers()
    print("Select --gate0, --run, or --summarize.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
