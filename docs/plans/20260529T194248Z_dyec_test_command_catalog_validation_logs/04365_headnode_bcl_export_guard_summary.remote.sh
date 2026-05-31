#!/usr/bin/env bash
set -euo pipefail

analysis="/fsx/analysis_results/ubuntu/ccv20260530r56_illumina_bclconvert/daylily-omics-analysis"
run_root="/home/ubuntu/daylily-runs/ccv20260530r56_illumina_bclconvert"

echo "=== now ==="
date -u +%Y-%m-%dT%H:%M:%SZ

echo "=== fsx ==="
df -hT /fsx

echo "=== dyec export processes ==="
ps -eo pid,ppid,stat,etime,cmd | grep -E 'ccv20260530r56_illumina_bclconvert|dyec export|data-repository' | grep -v grep || true

echo "=== run dir links ==="
if [ -d "$analysis/config/run_dir_links" ]; then
  find "$analysis/config/run_dir_links" -maxdepth 2 -mindepth 1 -printf '%M %p -> %l\n' 2>/dev/null | sort
else
  echo "absent: $analysis/config/run_dir_links"
fi

echo "=== link path type ==="
if [ -e "$analysis/config/run_dir_links/20260514_LH01106_0009_B23TVLGLT4" ] || [ -L "$analysis/config/run_dir_links/20260514_LH01106_0009_B23TVLGLT4" ]; then
  stat -c '%F %N' "$analysis/config/run_dir_links/20260514_LH01106_0009_B23TVLGLT4" || true
else
  echo "absent: $analysis/config/run_dir_links/20260514_LH01106_0009_B23TVLGLT4"
fi

echo "=== export files ==="
find "$run_root" -maxdepth 5 -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TSZ %s %p\n' 2>/dev/null | sort | tail -80 || true

echo "=== fsx export yaml ==="
find "$run_root" -name 'fsx_export.yaml' -print -exec sed -n '1,220p' {} \; 2>/dev/null || true
