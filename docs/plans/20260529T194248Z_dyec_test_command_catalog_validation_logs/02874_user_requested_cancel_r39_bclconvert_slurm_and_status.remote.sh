#!/usr/bin/env bash
set -euo pipefail
SESSION='ccv20260529r39_illumina_bclconvert'
ANALYSIS_ROOT='/fsx/analysis_results/ubuntu/ccv20260529r39_illumina_bclconvert'
STATUS_FILE="$ANALYSIS_ROOT/status.json"

echo "== tmux state before follow-up =="
tmux has-session -t "$SESSION" 2>/dev/null && tmux list-panes -t "$SESSION" -F 'pane=#{pane_id} pid=#{pane_pid} cmd=#{pane_current_command} active=#{pane_active}' || echo "tmux_session_absent"

echo "== matching slurm jobs before follow-up =="
squeue -u ubuntu -h -o '%i|%j|%T|%M|%D|%R|%Z' | awk -F'|' -v root="$ANALYSIS_ROOT" -v session="$SESSION" '$0 ~ session || $0 ~ root || $2 ~ /bcl|BCL|snakemake/ {print}' || true

mapfile -t jobs < <(squeue -u ubuntu -h -o '%i|%j|%T|%M|%D|%R|%Z' | awk -F'|' -v root="$ANALYSIS_ROOT" -v session="$SESSION" '$0 ~ session || $0 ~ root || $2 ~ /bcl|BCL|snakemake/ {print $1}' | sort -u)
if (( ${#jobs[@]} > 0 )); then
  echo "Cancelling Slurm jobs: ${jobs[*]}"
  scancel "${jobs[@]}" || true
else
  echo "No matching Slurm jobs to cancel."
fi

for attempt in $(seq 1 30); do
  remaining=$(squeue -u ubuntu -h -o '%i|%j|%T|%M|%D|%R|%Z' | awk -F'|' -v root="$ANALYSIS_ROOT" -v session="$SESSION" '$0 ~ session || $0 ~ root || $2 ~ /bcl|BCL|snakemake/ {print}' || true)
  if [[ -z "$remaining" ]]; then
    echo "Matching Slurm jobs absent after ${attempt}s poll."
    break
  fi
  echo "Waiting for matching Slurm jobs to clear: $remaining"
  sleep 2
done

if [[ -f "$STATUS_FILE" ]]; then
  python3 - "$STATUS_FILE" <<'PYSTATUS'
import datetime as dt
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding='utf-8'))
payload['completed_at'] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
payload['exit_code'] = 130
payload['terminated_by'] = 'user_requested_controller_stop'
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
PYSTATUS
  echo "Updated status file: $STATUS_FILE"
else
  echo "Status file missing: $STATUS_FILE"
fi

echo "== tmux state after follow-up =="
tmux has-session -t "$SESSION" 2>/dev/null && tmux list-panes -t "$SESSION" -F 'pane=#{pane_id} pid=#{pane_pid} cmd=#{pane_current_command} active=#{pane_active}' || echo "tmux_session_absent"

echo "== matching slurm jobs after follow-up =="
squeue -u ubuntu -h -o '%i|%j|%T|%M|%D|%R|%Z' | awk -F'|' -v root="$ANALYSIS_ROOT" -v session="$SESSION" '$0 ~ session || $0 ~ root || $2 ~ /bcl|BCL|snakemake/ {print}' || true

echo "== status =="
if [[ -f "$STATUS_FILE" ]]; then
  cat "$STATUS_FILE"
fi
