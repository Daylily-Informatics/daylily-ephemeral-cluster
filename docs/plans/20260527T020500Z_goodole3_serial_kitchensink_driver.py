#!/usr/bin/env python3
"""Run Goodole3 low-coverage DayOA sample workflows with bounded concurrency.

The inputs are the fixed pass-through configs generated during the Blahab44
validation run. They point at /fsx/references/genomic_data/organism_reads_slim,
so these launches do not create additional staging DRAs.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, write_remote_text


ROOT = Path(__file__).resolve().parents[2]
PLAN_ROOT = ROOT / "docs" / "plans"
SOURCE_CONFIG_ROOT = PLAN_ROOT / "20260526T224018Z_blahab44_inputs" / "generated"
LOG_ROOT = PLAN_ROOT / "20260527T032100Z_goodole3_serial_kitchensink_v206_logs"
EVENTS_PATH = PLAN_ROOT / "20260527T032100Z_goodole3_serial_kitchensink_v206_runs.jsonl"

CLUSTER = "goodole3"
PROFILE = "lsmc"
REGION = "us-west-2"
EXECUTING_ENTITY = "ubuntu"
GIT_TAG = "2.0.6"
GENOME = "hg38_broad"
REMOTE_BASE = "/home/ubuntu/ds/gd3serialksv206"
EXPORT_ROOT = "s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu"
INITIAL_MAX_ACTIVE = 3
BUMPED_MAX_ACTIVE = 4
MIN_FREE_GIB_FOR_BUMP = 1024
MAX_USED_PCT_FOR_BUMP = 80
POLL_SECONDS = 60


@dataclass(frozen=True)
class KitchenSinkRun:
    command_id: str
    analysis_id: str
    samples_tsv: Path
    units_tsv: Path
    dy_command: str


RUNS = (
    KitchenSinkRun(
        command_id="illumina_snv_alignstats_relatedness_vep_multiqc",
        analysis_id="gd3v206-ilmn5x",
        samples_tsv=SOURCE_CONFIG_ROOT
        / "illumina_snv_alignstats_relatedness_vep_multiqc"
        / "20260526T232930Z_768f9811_samples.tsv",
        units_tsv=SOURCE_CONFIG_ROOT
        / "illumina_snv_alignstats_relatedness_vep_multiqc"
        / "20260526T232930Z_768f9811_units.tsv",
        dy_command=(
            "bin/day_run produce_sent_align produce_dmd_dedup_cram "
            "produce_sentd_snv_vcf produce_alignstats produce_snv_concordances "
            "produce_relatedness produce_vep produce_multiqc_all "
            "--config 'multiqc_qc={\"enable_tools\":[\"vep\"]}' -p -j 100 -k"
        ),
    ),
    KitchenSinkRun(
        command_id="ultima_snv_alignstats_kitchensink",
        analysis_id="gd3v206-ug5x",
        samples_tsv=SOURCE_CONFIG_ROOT
        / "ultima_snv_alignstats_kitchensink"
        / "20260526T233423Z_7f724d71_samples.tsv",
        units_tsv=SOURCE_CONFIG_ROOT
        / "ultima_snv_alignstats_kitchensink"
        / "20260526T233423Z_7f724d71_units.tsv",
        dy_command=(
            "bin/day_run produce_alignstats produce_na_dedup_cram "
            "produce_sentdug_snv_vcf produce_snv_concordances produce_relatedness "
            "produce_vep produce_multiqc_all "
            "--config 'multiqc_qc={\"enable_tools\":[\"vep\"]}' -p -j 100 -k"
        ),
    ),
    KitchenSinkRun(
        command_id="ont_snv_alignstats_kitchensink",
        analysis_id="gd3v206-ont5x",
        samples_tsv=SOURCE_CONFIG_ROOT
        / "ont_snv_alignstats_kitchensink"
        / "20260526T233916Z_6c2b7b02_samples.tsv",
        units_tsv=SOURCE_CONFIG_ROOT
        / "ont_snv_alignstats_kitchensink"
        / "20260526T233916Z_6c2b7b02_units.tsv",
        dy_command=(
            "bin/day_run produce_alignstats produce_sentdont_snv_vcf "
            "produce_snv_concordances produce_relatedness produce_vep "
            "produce_multiqc_all "
            "--config 'multiqc_qc={\"enable_tools\":[\"vep\"]}' -p -j 5 -k"
        ),
    ),
    KitchenSinkRun(
        command_id="hybrid_ilmn_ont_snv_kitchensink",
        analysis_id="gd3v206-hio5x",
        samples_tsv=SOURCE_CONFIG_ROOT
        / "hybrid_ilmn_ont_snv_kitchensink"
        / "20260526T234857Z_77cd0b7a_samples.tsv",
        units_tsv=SOURCE_CONFIG_ROOT
        / "hybrid_ilmn_ont_snv_kitchensink"
        / "20260526T234857Z_77cd0b7a_units.tsv",
        dy_command=(
            "bin/day_run produce_snv_concordances produce_sentdhiomr_sv "
            "produce_sentdhiomr_snv_vcf produce_relatedness produce_vep "
            "produce_multiqc_all --config 'dedupers=[\"dmd\"]' "
            "'multiqc_qc={\"enable_tools\":[\"vep\"]}' -p -j 100 -k"
        ),
    ),
    KitchenSinkRun(
        command_id="illumina_snv_alignstats",
        analysis_id="gd3v206-ilmnbase5x",
        samples_tsv=SOURCE_CONFIG_ROOT
        / "illumina_snv_alignstats"
        / "20260526T232522Z_18359bf2_samples.tsv",
        units_tsv=SOURCE_CONFIG_ROOT
        / "illumina_snv_alignstats"
        / "20260526T232522Z_18359bf2_units.tsv",
        dy_command=(
            "bin/day_run produce_sent_align produce_dmd_dedup_cram "
            "produce_sentd_snv_vcf produce_snv_concordances produce_alignstats "
            "-p -k -j 20"
        ),
    ),
    KitchenSinkRun(
        command_id="ultima_snv_alignstats",
        analysis_id="gd3v206-ugbase5x",
        samples_tsv=SOURCE_CONFIG_ROOT
        / "ultima_snv_alignstats"
        / "20260526T233155Z_1a22f74d_samples.tsv",
        units_tsv=SOURCE_CONFIG_ROOT
        / "ultima_snv_alignstats"
        / "20260526T233155Z_1a22f74d_units.tsv",
        dy_command=(
            "bin/day_run produce_alignstats produce_na_dedup_cram "
            "produce_sentdug_snv_vcf produce_snv_concordances -p -j 20 -k"
        ),
    ),
    KitchenSinkRun(
        command_id="ont_snv_alignstats",
        analysis_id="gd3v206-ontbase5x",
        samples_tsv=SOURCE_CONFIG_ROOT
        / "ont_snv_alignstats"
        / "20260526T233649Z_58971985_samples.tsv",
        units_tsv=SOURCE_CONFIG_ROOT
        / "ont_snv_alignstats"
        / "20260526T233649Z_58971985_units.tsv",
        dy_command=(
            "bin/day_run produce_alignstats produce_sentdont_snv_vcf "
            "produce_snv_concordances -p -j 5 -k"
        ),
    ),
    KitchenSinkRun(
        command_id="pacbio_snv_alignstats",
        analysis_id="gd3v206-pbbase5x",
        samples_tsv=SOURCE_CONFIG_ROOT
        / "pacbio_snv_alignstats"
        / "20260526T234141Z_53f941a8_samples.tsv",
        units_tsv=SOURCE_CONFIG_ROOT
        / "pacbio_snv_alignstats"
        / "20260526T234141Z_53f941a8_units.tsv",
        dy_command=(
            "bin/day_run produce_sentmm2_align produce_na_dedup_cram "
            "produce_sentdpb_snv_vcf produce_alignstats produce_snv_concordances "
            "-p -j 2 -k -T 1"
        ),
    ),
    KitchenSinkRun(
        command_id="hybrid_ilmn_ont_snv",
        analysis_id="gd3v206-hiobase5x",
        samples_tsv=SOURCE_CONFIG_ROOT
        / "hybrid_ilmn_ont_snv"
        / "20260526T234631Z_e9e804ff_samples.tsv",
        units_tsv=SOURCE_CONFIG_ROOT
        / "hybrid_ilmn_ont_snv"
        / "20260526T234631Z_e9e804ff_units.tsv",
        dy_command=(
            "bin/day_run produce_snv_concordances produce_sentdhiomr_sv "
            "produce_sentdhiomr_snv_vcf --config 'dedupers=[\"dmd\"]' "
            "-p -j 100 -k"
        ),
    ),
    KitchenSinkRun(
        command_id="hybrid_ultima_ont_snv",
        analysis_id="gd3v206-huobase5x",
        samples_tsv=SOURCE_CONFIG_ROOT
        / "hybrid_ultima_ont_snv"
        / "20260526T235123Z_54761b1c_samples.tsv",
        units_tsv=SOURCE_CONFIG_ROOT
        / "hybrid_ultima_ont_snv"
        / "20260526T235123Z_54761b1c_units.tsv",
        dy_command=(
            "bin/day_run produce_sentdhuomr_snv_vcf produce_alignstats "
            "produce_snv_concordances -p -j 100 -k"
        ),
    ),
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def append_event(event: dict) -> None:
    event = {"ts": utc_now(), **event}
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def load_events() -> list[dict]:
    if not EVENTS_PATH.exists():
        return []
    return [json.loads(line) for line in EVENTS_PATH.read_text(encoding="utf-8").splitlines() if line]


def last_event(command_id: str, phase: str, status: str | None = None) -> dict | None:
    for event in reversed(load_events()):
        if event.get("command_id") != command_id or event.get("phase") != phase:
            continue
        if status is not None and event.get("status") != status:
            continue
        return event
    return None


def dyec() -> str:
    executable = shutil.which("dyec")
    if not executable:
        raise RuntimeError("dyec not found on PATH; run through source ./activate")
    return executable


def run_cmd(argv: list[str], *, log_name: str, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
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
    (LOG_ROOT / log_name).write_text(
        json.dumps(
            {
                "argv": argv,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return proc


def require_success(proc: subprocess.CompletedProcess[str], run: KitchenSinkRun, phase: str) -> None:
    if proc.returncode == 0:
        return
    append_event(
        {
            "command_id": run.command_id,
            "analysis_id": run.analysis_id,
            "phase": phase,
            "status": "failed",
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-4000:],
        }
    )
    raise RuntimeError(f"{run.analysis_id} {phase} failed with rc={proc.returncode}")


def ensure_remote_stage(run: KitchenSinkRun) -> str:
    existing = last_event(run.command_id, "remote_stage", "success")
    if existing:
        return str(existing["remote_stage_dir"])
    if not run.samples_tsv.is_file():
        raise FileNotFoundError(run.samples_tsv)
    if not run.units_tsv.is_file():
        raise FileNotFoundError(run.units_tsv)
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    remote_stage_dir = f"{REMOTE_BASE}/{run.analysis_id}"
    write_remote_text(
        target.instance_id,
        REGION,
        f"{remote_stage_dir}/a_samples.tsv",
        run.samples_tsv.read_text(encoding="utf-8"),
        profile=PROFILE,
    )
    write_remote_text(
        target.instance_id,
        REGION,
        f"{remote_stage_dir}/a_units.tsv",
        run.units_tsv.read_text(encoding="utf-8"),
        profile=PROFILE,
    )
    verify = run_shell(
        target.instance_id,
        REGION,
        "set -euo pipefail\n"
        f"test -s {remote_stage_dir!r}/a_samples.tsv\n"
        f"test -s {remote_stage_dir!r}/a_units.tsv\n"
        f"printf 'REMOTE_STAGE=%s\\n' {remote_stage_dir!r}\n",
        profile=PROFILE,
        timeout=180,
        comment=f"Verify serial kitchen sink configs for {run.analysis_id}",
    )
    (LOG_ROOT / f"{run.analysis_id}_remote_stage.log").write_text(
        json.dumps(
            {
                "remote_stage_dir": remote_stage_dir,
                "verify_status": verify.status,
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
            "command_id": run.command_id,
            "analysis_id": run.analysis_id,
            "phase": "remote_stage",
            "status": "success",
            "remote_stage_dir": remote_stage_dir,
            "samples_tsv": str(run.samples_tsv),
            "units_tsv": str(run.units_tsv),
        }
    )
    return remote_stage_dir


def launch(run: KitchenSinkRun, remote_stage_dir: str) -> str:
    existing = last_event(run.command_id, "launch", "success")
    if existing:
        return str(existing["session_name"])
    export_destination = f"{EXPORT_ROOT}/{run.analysis_id}/"
    argv = [
        dyec(),
        "workflow",
        "launch",
        "--repository",
        "daylily-omics-analysis",
        "--analysis-id",
        run.analysis_id,
        "--executing-entity",
        EXECUTING_ENTITY,
        "--git-tag",
        GIT_TAG,
        "--genome",
        GENOME,
        "--dy-command",
        run.dy_command,
        "--profile",
        PROFILE,
        "--region",
        REGION,
        "--cluster",
        CLUSTER,
        "--stage-dir",
        remote_stage_dir,
        "--session-name",
        run.analysis_id,
        "--skip-project-check",
        "--export-destination-s3-uri",
        export_destination,
        "--export-trigger",
        "on-success",
        "--delete-on-export-success",
    ]
    proc = run_cmd(argv, log_name=f"{run.analysis_id}_launch.log", timeout=900)
    require_success(proc, run, "launch")
    append_event(
        {
            "command_id": run.command_id,
            "analysis_id": run.analysis_id,
            "phase": "launch",
            "status": "success",
            "git_tag": GIT_TAG,
            "session_name": run.analysis_id,
            "remote_stage_dir": remote_stage_dir,
            "export_destination_s3_uri": export_destination,
            "delete_on_export_success": True,
            "log": str(LOG_ROOT / f"{run.analysis_id}_launch.log"),
        }
    )
    return run.analysis_id


def workflow_status(run: KitchenSinkRun, session_name: str) -> dict | None:
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
        log_name=f"{run.analysis_id}_status_latest.log",
        timeout=180,
    )
    if proc.returncode != 0:
        return None
    return json.loads(proc.stdout)


def reconciled_export_success(run: KitchenSinkRun) -> dict | None:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    receipt = f"/home/ubuntu/daylily-runs/{run.analysis_id}/export/fsx_export.yaml"
    analysis_dir = f"/fsx/analysis_results/ubuntu/{run.analysis_id}"
    resp = run_shell(
        target.instance_id,
        REGION,
        "set -euo pipefail\n"
        f"receipt={receipt!r}\n"
        f"analysis_dir={analysis_dir!r}\n"
        "if [ -f \"$receipt\" ] "
        "&& grep -q 'status: success' \"$receipt\" "
        "&& grep -q 'task_lifecycle: SUCCEEDED' \"$receipt\" "
        "&& grep -q 'detach_lifecycle: DELETED' \"$receipt\" "
        "&& [ ! -e \"$analysis_dir\" ]; then\n"
        "  printf 'RECONCILED_EXPORT_SUCCESS=1\\n'\n"
        "fi\n",
        profile=PROFILE,
        timeout=90,
        comment=f"Reconcile export terminal status for {run.analysis_id}",
    )
    if "RECONCILED_EXPORT_SUCCESS=1" not in resp.stdout:
        return None
    return {
        "command": run.dy_command,
        "completed_at": utc_now(),
        "exit_code": 0,
        "repo_path": f"{analysis_dir}/daylily-omics-analysis",
        "session_name": run.analysis_id,
        "started_at": None,
        "reconciled_from_export_receipt": receipt,
        "local_analysis_dir_absent": True,
    }


def terminal_status(run: KitchenSinkRun, session_name: str) -> dict | None:
    status = workflow_status(run, session_name)
    if status is not None and status.get("exit_code") is not None:
        return status
    reconciled = reconciled_export_success(run)
    if reconciled is not None:
        return reconciled
    return status


def capture_logs(run: KitchenSinkRun, session_name: str) -> None:
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
            "260",
        ],
        log_name=f"{run.analysis_id}_tmux_tail.log",
        timeout=180,
    )


def latest_completed_event(run: KitchenSinkRun) -> dict | None:
    return last_event(run.command_id, "live", "completed")


def latest_launch_event(run: KitchenSinkRun) -> dict | None:
    return last_event(run.command_id, "launch", "success")


def fsx_space() -> dict:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    resp = run_shell(
        target.instance_id,
        REGION,
        "set -euo pipefail\n"
        "df -Pk /fsx | awk 'NR==2 {printf \"size_kb=%s used_kb=%s avail_kb=%s used_pct=%s\\n\", $2, $3, $4, $5}'\n",
        profile=PROFILE,
        timeout=90,
        comment="Check /fsx space for concurrent kitchen sink policy",
    )
    fields: dict[str, str] = {}
    for token in resp.stdout.strip().split():
        if "=" in token:
            key, value = token.split("=", 1)
            fields[key] = value.rstrip("%")
    if not fields:
        raise RuntimeError(f"Could not parse df output: {resp.stdout!r} {resp.stderr!r}")
    avail_gib = int(fields["avail_kb"]) / 1024 / 1024
    return {
        "size_kb": int(fields["size_kb"]),
        "used_kb": int(fields["used_kb"]),
        "avail_kb": int(fields["avail_kb"]),
        "used_pct": int(fields["used_pct"]),
        "avail_gib": round(avail_gib, 1),
    }


def fsx_can_bump(space: dict) -> bool:
    return space["used_pct"] <= MAX_USED_PCT_FOR_BUMP and space["avail_gib"] >= MIN_FREE_GIB_FOR_BUMP


def wait_for_completion(run: KitchenSinkRun, session_name: str) -> int:
    existing = last_event(run.command_id, "live", "completed")
    if existing:
        return int(existing["exit_code"])
    while True:
        status = terminal_status(run, session_name)
        if status is not None and status.get("exit_code") is not None:
            capture_logs(run, session_name)
            exit_code = int(status["exit_code"])
            append_event(
                {
                    "command_id": run.command_id,
                    "analysis_id": run.analysis_id,
                    "phase": "live",
                    "status": "completed",
                    "session_name": session_name,
                    "exit_code": exit_code,
                    "status_payload": status,
                    "status_log": str(LOG_ROOT / f"{run.analysis_id}_status_latest.log"),
                    "tmux_tail_log": str(LOG_ROOT / f"{run.analysis_id}_tmux_tail.log"),
                }
            )
            return exit_code
        append_event(
            {
                "command_id": run.command_id,
                "analysis_id": run.analysis_id,
                "phase": "live",
                "status": "running",
                "session_name": session_name,
                "last_status_payload": status,
            }
        )
        time.sleep(POLL_SECONDS)


def main() -> int:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    append_event(
        {
            "command_id": "_driver",
            "phase": "start",
            "status": "running",
            "max_active_initial": INITIAL_MAX_ACTIVE,
            "max_active_bumped": BUMPED_MAX_ACTIVE,
            "min_free_gib_for_bump": MIN_FREE_GIB_FOR_BUMP,
            "max_used_pct_for_bump": MAX_USED_PCT_FOR_BUMP,
            "poll_seconds": POLL_SECONDS,
        }
    )
    sessions: dict[str, str] = {}
    bumped = False
    while True:
        completed_runs = {run.command_id for run in RUNS if latest_completed_event(run)}
        for run in RUNS:
            if run.command_id in completed_runs:
                sessions.pop(run.command_id, None)
                continue
            launched = latest_launch_event(run)
            if launched and run.command_id not in sessions:
                sessions[run.command_id] = str(launched["session_name"])

        for run in RUNS:
            session_name = sessions.get(run.command_id)
            if not session_name or run.command_id in completed_runs:
                continue
            status = terminal_status(run, session_name)
            if status is not None and status.get("exit_code") is not None:
                capture_logs(run, session_name)
                exit_code = int(status["exit_code"])
                append_event(
                    {
                        "command_id": run.command_id,
                        "analysis_id": run.analysis_id,
                        "phase": "live",
                        "status": "completed",
                        "session_name": session_name,
                        "exit_code": exit_code,
                        "status_payload": status,
                        "status_log": str(LOG_ROOT / f"{run.analysis_id}_status_latest.log"),
                        "tmux_tail_log": str(LOG_ROOT / f"{run.analysis_id}_tmux_tail.log"),
                    }
                )
                print(f"[{utc_now()}] completed {run.analysis_id} exit_code={exit_code}", flush=True)
                sessions.pop(run.command_id, None)
                completed_runs.add(run.command_id)
                if exit_code != 0:
                    append_event(
                        {
                            "command_id": "_driver",
                            "phase": "finish",
                            "status": "blocked",
                            "blocked_on": run.command_id,
                            "exit_code": exit_code,
                        }
                    )
                    return exit_code
            else:
                append_event(
                    {
                        "command_id": run.command_id,
                        "analysis_id": run.analysis_id,
                        "phase": "live",
                        "status": "running",
                        "session_name": session_name,
                        "last_status_payload": status,
                    }
                )

        active_count = len(sessions)
        space = fsx_space()
        max_active = INITIAL_MAX_ACTIVE
        if len(completed_runs) >= INITIAL_MAX_ACTIVE and fsx_can_bump(space):
            max_active = BUMPED_MAX_ACTIVE
            if not bumped:
                bumped = True
                append_event(
                    {
                        "command_id": "_driver",
                        "phase": "concurrency",
                        "status": "bumped",
                        "max_active": max_active,
                        "completed_count": len(completed_runs),
                        "fsx_space": space,
                    }
                )
                print(
                    f"[{utc_now()}] bumped max_active to {max_active}; /fsx used={space['used_pct']}% avail={space['avail_gib']}GiB",
                    flush=True,
                )
        else:
            append_event(
                {
                    "command_id": "_driver",
                    "phase": "concurrency",
                    "status": "holding",
                    "max_active": max_active,
                    "active_count": active_count,
                    "completed_count": len(completed_runs),
                    "fsx_space": space,
                }
            )

        for run in RUNS:
            if len(sessions) >= max_active:
                break
            if run.command_id in completed_runs or run.command_id in sessions:
                continue
            print(f"[{utc_now()}] starting {run.analysis_id} ({run.command_id})", flush=True)
            remote_stage_dir = ensure_remote_stage(run)
            session_name = launch(run, remote_stage_dir)
            sessions[run.command_id] = session_name

        if len(completed_runs) == len(RUNS):
            break
        time.sleep(POLL_SECONDS)
    append_event({"command_id": "_driver", "phase": "finish", "status": "completed"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
