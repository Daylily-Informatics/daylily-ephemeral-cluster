#!/usr/bin/env bash
set -euo pipefail
SESSION='ccv20260529r39_illumina_bclconvert'
ANALYSIS_ROOT='/fsx/analysis_results/ubuntu/ccv20260529r39_illumina_bclconvert'
STATUS_FILE="$ANALYSIS_ROOT/status.json"
REPO_PATH="$ANALYSIS_ROOT/daylily-omics-analysis"

echo "== before tmux =="
tmux has-session -t "$SESSION" 2>/dev/null && tmux list-panes -t "$SESSION" -F 'pane={pane_id} pid={pane_pid} cmd={pane_current_command} active={pane_active}' || echo "tmux_session_absent"
if tmux has-session -t "$SESSION" 2>/dev/null; then
  pane_pid=$(tmux list-panes -t "$SESSION" -F '{pane_pid}' | head -n 1 || true)
  if [[ -n "${pane_pid:-}" ]]; then
    echo "== controller process tree before =="
    if command -v pstree >/dev/null 2>&1; then
      pstree -ap "$pane_pid" || true
    else
      ps -eo pid,ppid,stat,etime,cmd | awk -v root="$pane_pid" '$1 == root || $2 == root {print}' || true
    fi
  fi
fi

echo "== before slurm =="
squeue -u ubuntu -h -o '%i|%j|%T|%M|%D|%R|%Z' | awk -F'|' -v root="$ANALYSIS_ROOT" -v session="$SESSION" '$0 ~ session || $0 ~ root || $2 ~ /bcl|BCL|snakemake/ {print}' || true

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Sending Ctrl-C to tmux session $SESSION"
  tmux send-keys -t "$SESSION" C-c
  sleep 15
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Killing tmux session $SESSION"
  tmux kill-session -t "$SESSION"
else
  echo "tmux session $SESSION already absent after Ctrl-C"
fi

mapfile -t jobs < <(squeue -u ubuntu -h -o '%i|%j|%T|%M|%D|%R|%Z' | awk -F'|' -v root="$ANALYSIS_ROOT" -v session="$SESSION" '$0 ~ session || $0 ~ root || $2 ~ /bcl|BCL|snakemake/ {print $1}' | sort -u)
if ((${' '}${#jobs[@]} > 0)); then
  echo "Cancelling Slurm jobs: ${jobs[*]}"
  scancel "${jobs[@]}" || true
  sleep 5
else
  echo "No matching Slurm jobs to cancel after controller termination."
fi

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
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '
', encoding='utf-8')
PYSTATUS
  echo "Updated status file: $STATUS_FILE"
else
  echo "Status file missing: $STATUS_FILE"
fi

echo "== after tmux =="
tmux has-session -t "$SESSION" 2>/dev/null && tmux list-panes -t "$SESSION" -F 'pane={pane_id} pid={pane_pid} cmd={pane_current_command} active={pane_active}' || echo "tmux_session_absent"

echo "== after slurm =="
squeue -u ubuntu -h -o '%i|%j|%T|%M|%D|%R|%Z' | awk -F'|' -v root="$ANALYSIS_ROOT" -v session="$SESSION" '$0 ~ session || $0 ~ root || $2 ~ /bcl|BCL|snakemake/ {print}' || true

echo "== status =="
if [[ -f "$STATUS_FILE" ]]; then
  cat "$STATUS_FILE"
fi
