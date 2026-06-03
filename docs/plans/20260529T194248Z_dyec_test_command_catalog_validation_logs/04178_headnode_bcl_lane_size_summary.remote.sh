#!/usr/bin/env bash
set -euo pipefail

analysis="/fsx/analysis_results/ubuntu/ccv20260530r56_illumina_bclconvert/daylily-omics-analysis"
run_id="20260514_LH01106_0009_B23TVLGLT4"
bcl_dir="$analysis/results/runs/$run_id/bclconvert"

echo "=== now ==="
date -u +%Y-%m-%dT%H:%M:%SZ

echo "=== fsx ==="
df -hT /fsx /dev/shm /

echo "=== slurm ==="
squeue -h -o '%i|%P|%T|%M|%D|%R|%j' | sort || true

echo "=== bclconvert output sizes ==="
du -sh "$bcl_dir" 2>/dev/null || true
du -sh "$bcl_dir"/lane_fastqs/L00* 2>/dev/null || true
du -sh "$bcl_dir"/lane_reports/L00* 2>/dev/null || true

echo "=== lane done files ==="
find "$bcl_dir"/lane_reports -maxdepth 2 -name 'bclconvert.done' -printf '%TY-%Tm-%TdT%TH:%TM:%TSZ %p\n' 2>/dev/null | sort || true

echo "=== recent lane log tails ==="
for log in "$bcl_dir"/logs/run_bclconvert.L00*.log; do
  [ -e "$log" ] || continue
  echo "--- ${log##*/} ---"
  tail -20 "$log" || true
done
