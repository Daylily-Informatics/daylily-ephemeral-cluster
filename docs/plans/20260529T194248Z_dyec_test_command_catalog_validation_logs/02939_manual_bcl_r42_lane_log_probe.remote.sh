#!/usr/bin/env bash
set -euo pipefail

repo=/fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert/daylily-omics-analysis
cd "$repo"
for lane in L001 L006; do
  log="results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/logs/run_bclconvert.${lane}.log"
  echo "=== $lane $log ==="
  if [[ -f "$log" ]]; then
    tail -n 80 "$log"
  else
    echo "missing"
  fi
done
