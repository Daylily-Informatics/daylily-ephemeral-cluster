#!/usr/bin/env bash
set -euo pipefail
SESSION='ccv20260529r39_illumina_bclconvert'
ANALYSIS_DIR="/fsx/analysis_results/ubuntu/$SESSION"
REPO_DIR="$ANALYSIS_DIR/daylily-omics-analysis"
SCRATCH_DIR="$REPO_DIR/.bclconvert_scratch"
RUN_STATE_DIR="/home/ubuntu/daylily-runs/$SESSION"
READONLY_DRA_MOUNT="/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4"

echo "DELETION_TARGET_ANALYSIS_DIR=$ANALYSIS_DIR"
echo "DELETION_TARGET_SCRATCH_COPY_DIR=$SCRATCH_DIR"
echo "PRESERVE_READONLY_DRA_MOUNT=$READONLY_DRA_MOUNT"
echo "== fsx before =="
df -h /fsx || true

echo "== slurm safety check =="
squeue -u ubuntu -h -o '%i|%j|%T|%M|%D|%R|%Z' | awk -F'|' -v root="$ANALYSIS_DIR" -v session="$SESSION" '$0 ~ session || $0 ~ root || $2 ~ /bcl|BCL|snakemake/ {print}' || true

echo "== target existence before =="
if [[ -e "$ANALYSIS_DIR" ]]; then
  ls -ld "$ANALYSIS_DIR" "$REPO_DIR" "$SCRATCH_DIR" 2>/dev/null || true
  du -sh "$ANALYSIS_DIR" "$SCRATCH_DIR" 2>/dev/null || true
else
  echo "analysis_dir_absent_before"
fi
if [[ -e "$READONLY_DRA_MOUNT" ]]; then
  echo "readonly_dra_mount_present_before"
  ls -ld "$READONLY_DRA_MOUNT"
else
  echo "readonly_dra_mount_absent_before"
fi

if [[ -f "$RUN_STATE_DIR/status.json" ]]; then
  python3 - "$RUN_STATE_DIR/status.json" <<'PYSTATUS'
import datetime as dt
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding='utf-8'))
payload['completed_at'] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
payload['exit_code'] = 130
payload['terminated_by'] = 'user_requested_controller_stop_and_analysis_cleanup'
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
PYSTATUS
  echo "updated_run_state_status=$RUN_STATE_DIR/status.json"
else
  echo "run_state_status_missing=$RUN_STATE_DIR/status.json"
fi

if [[ -e "$ANALYSIS_DIR" ]]; then
  rm -rf --one-file-system "$ANALYSIS_DIR"
  echo "removed_analysis_dir=$ANALYSIS_DIR"
else
  echo "analysis_dir_already_absent=$ANALYSIS_DIR"
fi

echo "== target existence after =="
if [[ -e "$ANALYSIS_DIR" ]]; then
  echo "ERROR_analysis_dir_still_exists=$ANALYSIS_DIR"
  exit 20
else
  echo "analysis_dir_absent_after=$ANALYSIS_DIR"
fi
if [[ -e "$READONLY_DRA_MOUNT" ]]; then
  echo "readonly_dra_mount_preserved_after=$READONLY_DRA_MOUNT"
  ls -ld "$READONLY_DRA_MOUNT"
else
  echo "ERROR_readonly_dra_mount_missing_after=$READONLY_DRA_MOUNT"
  exit 21
fi

echo "== fsx after =="
df -h /fsx || true

echo "== status after =="
if [[ -f "$RUN_STATE_DIR/status.json" ]]; then
  cat "$RUN_STATE_DIR/status.json"
fi
