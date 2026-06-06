#!/usr/bin/env bash
set -euo pipefail

SESSION=hybonly_stage_ilmn_20260606T010256Z
SCRIPT=/home/ubuntu/hyb_only_stage_ilmn_data_20260606T010256Z.sh
STDOUT=/fsx/scratch/ILMN/logs/tmux_stage_ilmn.stdout.txt
STDERR=/fsx/scratch/ILMN/logs/tmux_stage_ilmn.stderr.txt
RCFILE=/fsx/scratch/ILMN/logs/tmux_stage_ilmn.rc

chmod +x "$SCRIPT"
mkdir -p /fsx/scratch/ILMN/logs

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "ERROR: tmux session already exists: $SESSION" >&2
  exit 3
fi

tmux new-session -d -s "$SESSION" "bash -l -c '$SCRIPT > $STDOUT 2> $STDERR; rc=\$?; echo \$rc > $RCFILE; exit \$rc'"
tmux list-windows -t "$SESSION"
tmux list-panes -t "$SESSION"
