#!/usr/bin/env bash
set -euo pipefail
echo "time_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "df=/fsx"
df -h /fsx
echo "tmux=hybonly_stage_ont_20260606T010256Z"
if tmux has-session -t hybonly_stage_ont_20260606T010256Z 2>/dev/null; then
  echo "tmux_state=running"
  tmux capture-pane -pt hybonly_stage_ont_20260606T010256Z -S -80
else
  echo "tmux_state=absent"
fi
echo "ont_dir"
ls -lh /fsx/scratch/ONT 2>/dev/null || true
echo "ont_tmp_dir"
ls -lh /fsx/scratch/ONT/tmp 2>/dev/null || true
echo "stage_processes"
ps -fu ubuntu | awk '/hyb_only_stage_ont|NA00232|NA09677|NA03986|NA05164|gzip -t|cat --/ && !/awk/ {print}'
echo "ont_log_tail"
tail -80 /fsx/scratch/ONT/logs/stage_commands.log 2>/dev/null || true
echo "ont_rc"
cat /fsx/scratch/ONT/logs/tmux_stage_ont.rc 2>/dev/null || true
