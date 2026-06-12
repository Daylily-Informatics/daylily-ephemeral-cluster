#!/usr/bin/env python3
"""Poll the Sentieon acceptance gate, then launch the gated 4NA SMN12 rerun.

This is intentionally narrow and fail-hard:
- no Slurm/job control
- no cleanup
- no raw snakemake invocation
- no fallback inputs or alternate tags
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, wait_for_ssm_online


CLUSTER = "dyecX4"
REGION = "us-west-2"
PROFILE = "lsmc"
ENTITY = "ubuntu"
DAYOA_TAG = "10.0.16"
PROJECT = "sentieon-upgrade"
GENOME = "hg38_broad"
ROOT = Path("/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster")
PLAN_DIR = ROOT / "docs/plans"
INPUT_DIR = PLAN_DIR / "20260612T183610Z_dyecX4_4na_smn12_after_sentieon_gate_inputs"
STATE_PATH = PLAN_DIR / "20260612T183610Z_dyecX4_4na_smn12_after_sentieon_gate_state.json"
LOG_PATH = PLAN_DIR / "20260612T183610Z_dyecX4_4na_smn12_after_sentieon_gate_monitor.log"
POLL_SECONDS = 420

ACCEPTANCE_ANALYSES = [
    "sentup_hg003_ont5x_hg38b_solo_20260612T162900Z",
    "sentup_hg003_ilmn30x_pangenome_current_20260612T162900Z",
    "sentup_hg003_ilmn30x_pangenome_prior_20260612T162900Z",
    "sentup_hg003_ilmn30x_hg38_solo_20260612T181511Z",
    "sentup_hg003_hiomr_kitchensink_20260612T185650Z",
]

SMN12_COMMAND = (
    "dy-r produce_smn12_orthogonal_calls produce_htd_calls produce_sentdhiomr_segdup "
    "-p -T 0 -k -j 350 --rerun-triggers mtime "
    "--config "
    "'aligners=[\"sent\"]' "
    "'dedupers=[\"dmd\"]' "
    "'snv_callers=[\"sentdhiomr\"]' "
    "'sv_callers=[\"sentdhiomr\"]' "
    "'htd_callers=[\"smn12\",\"smaca\",\"sma_finder\",\"hapsma\",\"gauchian\",\"cyrius\"]' "
    "'sentdhiomr={\"segdup_genes\":\"SMN1\"}'"
)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(message: str) -> None:
    line = f"{now()} {message}"
    print(line, flush=True)
    with LOG_PATH.open("a") as handle:
        handle.write(line + "\n")


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"phase": "wait_acceptance"}
    return json.loads(STATE_PATH.read_text())


def save_state(state: dict) -> None:
    tmp = STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    tmp.replace(STATE_PATH)


def launch_stamp() -> str:
    state = load_state()
    if "stamp" not in state:
        state["stamp"] = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        save_state(state)
    return state["stamp"]


def poll_runs(analysis_ids: list[str]) -> dict[str, dict[str, str]]:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=120)
    joined = " ".join(analysis_ids)
    script = f"""
set -euo pipefail
for id in {joined}; do
  run=/home/ubuntu/daylily-runs/$id
  status_json=$run/status.json
  exit_code=
  completed_at=
  if [ -f "$status_json" ]; then
    exit_code=$(python3 - "$status_json" <<'PY'
import json, sys
d=json.load(open(sys.argv[1]))
v=d.get("exit_code")
print("" if v is None else v)
PY
)
    completed_at=$(python3 - "$status_json" <<'PY'
import json, sys
d=json.load(open(sys.argv[1]))
print(d.get("completed_at") or "")
PY
)
  fi
  receipt=$run/export/fsx_export.yaml
  receipt_status=
  lifecycle=
  detached=
  delete_fs=
  destination=
  if [ -f "$receipt" ]; then
    receipt_status=$(sed -n 's/^[[:space:]]*status:[[:space:]]*//p' "$receipt" | head -1 | tr -d '"')
    lifecycle=$(sed -n 's/^[[:space:]]*task_lifecycle:[[:space:]]*//p' "$receipt" | head -1 | tr -d '"')
    detached=$(sed -n 's/^[[:space:]]*detached:[[:space:]]*//p' "$receipt" | head -1 | tr -d '"')
    delete_fs=$(sed -n 's/^[[:space:]]*delete_data_in_file_system:[[:space:]]*//p' "$receipt" | head -1 | tr -d '"')
    destination=$(sed -n 's/^[[:space:]]*destination_s3_uri:[[:space:]]*//p' "$receipt" | head -1 | tr -d '"')
  fi
  printf '__RUN__\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' "$id" "$exit_code" "$completed_at" "$receipt_status" "$lifecycle" "$detached" "$delete_fs" "$destination"
done
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        timeout=180,
        comment="Poll Sentieon acceptance/4NA SMN12 gate",
    )
    rows: dict[str, dict[str, str]] = {}
    for line in result.stdout.splitlines():
        if not line.startswith("__RUN__\t"):
            continue
        _, aid, exit_code, completed_at, receipt_status, lifecycle, detached, delete_fs, destination = line.split("\t", 8)
        rows[aid] = {
            "exit_code": exit_code,
            "completed_at": completed_at,
            "receipt_status": receipt_status,
            "task_lifecycle": lifecycle,
            "detached": detached,
            "delete_data_in_file_system": delete_fs,
            "destination_s3_uri": destination,
        }
    missing = [aid for aid in analysis_ids if aid not in rows]
    if missing:
        raise RuntimeError(f"missing poll rows: {missing}; stdout={result.stdout!r}; stderr={result.stderr!r}")
    return rows


def run_is_success(row: dict[str, str], require_receipt: bool) -> bool:
    if row["exit_code"] != "0":
        return False
    if not require_receipt:
        return True
    return (
        row["receipt_status"] == "success"
        and row["task_lifecycle"] == "SUCCEEDED"
        and row["detached"] == "true"
        and row["delete_data_in_file_system"] == "false"
    )


def fail_if_terminal_failure(rows: dict[str, dict[str, str]]) -> None:
    failures = [aid for aid, row in rows.items() if row["exit_code"] not in ("", "0")]
    if failures:
        raise RuntimeError(f"terminal nonzero analysis exit codes: {failures}")


def launch_workflow(analysis_id: str, dy_command: str, dry_run: bool) -> None:
    destination = f"s3://lsmc-ssf-sequencing-data/derived/analysis_results/sentieon-upgrade/ubuntu/{analysis_id}/"
    cmd = [
        "dyec",
        "workflow",
        "launch",
        "--profile",
        PROFILE,
        "--region",
        REGION,
        "--cluster",
        CLUSTER,
        "--analysis-id",
        analysis_id,
        "--session-name",
        analysis_id,
        "--executing-entity",
        ENTITY,
        "--git-tag",
        DAYOA_TAG,
        "--project",
        PROJECT,
        "--genome",
        GENOME,
        "--samples-file",
        str(INPUT_DIR / "samples.tsv"),
        "--units-file",
        str(INPUT_DIR / "units.tsv"),
        "--dy-command",
        dy_command,
    ]
    if dry_run:
        cmd.append("--dry-run")
    else:
        cmd.extend(["--export-destination-s3-uri", destination, "--export-trigger", "on-success"])
    log(f"launching {'dry-run' if dry_run else 'live'} analysis_id={analysis_id}")
    with LOG_PATH.open("a") as handle:
        subprocess.run(cmd, cwd=ROOT, check=True, text=True, stdout=handle, stderr=subprocess.STDOUT)
    log(f"launched {'dry-run' if dry_run else 'live'} analysis_id={analysis_id}")


def main() -> int:
    if not (INPUT_DIR / "samples.tsv").is_file() or not (INPUT_DIR / "units.tsv").is_file():
        raise RuntimeError(f"missing copied inputs in {INPUT_DIR}")
    while True:
        state = load_state()
        phase = state.get("phase", "wait_acceptance")
        if phase == "wait_acceptance":
            rows = poll_runs(ACCEPTANCE_ANALYSES)
            fail_if_terminal_failure(rows)
            for aid, row in rows.items():
                log(
                    "acceptance "
                    f"{aid} exit={row['exit_code'] or 'running'} receipt={row['receipt_status'] or 'missing'} "
                    f"lifecycle={row['task_lifecycle'] or 'missing'}"
                )
            if all(run_is_success(row, require_receipt=True) for row in rows.values()):
                stamp = launch_stamp()
                dry_id = f"hiomr_smn12_4na_sentup_j350_{stamp}_dryrun"
                state.update({"phase": "dryrun_launched", "dryrun_analysis_id": dry_id})
                save_state(state)
                launch_workflow(dry_id, SMN12_COMMAND + " -n", dry_run=True)
            else:
                time.sleep(POLL_SECONDS)
        elif phase == "dryrun_launched":
            dry_id = state["dryrun_analysis_id"]
            rows = poll_runs([dry_id])
            fail_if_terminal_failure(rows)
            row = rows[dry_id]
            log(f"dryrun {dry_id} exit={row['exit_code'] or 'running'}")
            if run_is_success(row, require_receipt=False):
                live_id = f"hiomr_smn12_4na_sentup_j350_{state['stamp']}"
                state.update({"phase": "live_launched", "live_analysis_id": live_id})
                save_state(state)
                launch_workflow(live_id, SMN12_COMMAND, dry_run=False)
            else:
                time.sleep(POLL_SECONDS)
        elif phase == "live_launched":
            live_id = state["live_analysis_id"]
            rows = poll_runs([live_id])
            fail_if_terminal_failure(rows)
            row = rows[live_id]
            log(
                f"live {live_id} exit={row['exit_code'] or 'running'} "
                f"receipt={row['receipt_status'] or 'missing'} lifecycle={row['task_lifecycle'] or 'missing'}"
            )
            if run_is_success(row, require_receipt=True):
                state.update({"phase": "complete", "completed_at": now(), "destination_s3_uri": row["destination_s3_uri"]})
                save_state(state)
                log(f"complete live_analysis_id={live_id} destination={row['destination_s3_uri']}")
                return 0
            time.sleep(POLL_SECONDS)
        elif phase == "complete":
            log(f"already complete live_analysis_id={state.get('live_analysis_id')}")
            return 0
        else:
            raise RuntimeError(f"unknown phase {phase!r}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f"FAILED {type(exc).__name__}: {exc}")
        raise
