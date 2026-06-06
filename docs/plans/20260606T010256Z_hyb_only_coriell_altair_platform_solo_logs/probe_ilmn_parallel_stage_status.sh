#!/usr/bin/env bash
set -euo pipefail

echo "time_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "df=/fsx"
df -h /fsx
for tmux_name in hybonly_stage_ilmn_20260606T010256Z hybonly_stage_ilmn_parallel_20260606T010256Z; do
  echo "tmux=${tmux_name}"
  if tmux has-session -t "$tmux_name" 2>/dev/null; then
    echo "tmux_state=running"
  else
    echo "tmux_state=absent"
  fi
done

echo "ilmn_counts"
find /fsx/scratch/ILMN -maxdepth 1 -type f -name '*.fastq.gz' | wc -l | awk '{print "fastq_files=" $1}'
find /fsx/scratch/ILMN/logs/parallel_done -maxdepth 1 -type f -name '*.ok' 2>/dev/null | wc -l | awk '{print "parallel_done=" $1}'
find /fsx/scratch/ILMN/logs/parallel_errors -maxdepth 1 -type f -name '*.err' 2>/dev/null | wc -l | awk '{print "parallel_errors=" $1}'

echo "ilmn_dir_tail"
find /fsx/scratch/ILMN -maxdepth 1 -type f -name '*.fastq.gz' -printf '%TY-%Tm-%TdT%TH:%TM:%TS\t%s\t%f\n' | sort | tail -20 || true

echo "stage_processes"
ps -u ubuntu -f \
  | grep -E 'hyb_only_stage_ilmn|gzip -t /fsx/scratch/ILMN|/fsx/run_dir_mounts/ilmn-lh01121|xargs -n 2 -P' \
  | grep -v grep || true

echo "parallel_log_tail"
tail -40 /fsx/scratch/ILMN/logs/stage_commands_parallel.log 2>/dev/null || true

echo "parallel_rc"
cat /fsx/scratch/ILMN/logs/tmux_stage_ilmn_parallel.rc 2>/dev/null || true
