#!/usr/bin/env bash
set -euo pipefail
echo "time_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "df=/fsx"
df -h /fsx
echo "tmux=hybonly_stage_ilmn_20260606T010256Z"
if tmux has-session -t hybonly_stage_ilmn_20260606T010256Z 2>/dev/null; then
  echo "tmux_state=running"
  tmux capture-pane -pt hybonly_stage_ilmn_20260606T010256Z -S -80
else
  echo "tmux_state=absent"
fi
echo "ilmn_dir"
ls -lh /fsx/scratch/ILMN 2>/dev/null | sed -n '1,80p' || true
echo "ilmn_tmp_dir"
ls -lh /fsx/scratch/ILMN/tmp 2>/dev/null | sed -n '1,80p' || true
echo "stage_processes"
ps -fu ubuntu | awk '/hyb_only_stage_ilmn|cp --|gzip -t|NA00232|NA09677|NA03986|NA05164|Altair-HG/ && !/awk/ {print}'
echo "ilmn_log_tail"
tail -120 /fsx/scratch/ILMN/logs/stage_commands.log 2>/dev/null || true
echo "ilmn_rc"
cat /fsx/scratch/ILMN/logs/tmux_stage_ilmn.rc 2>/dev/null || true
