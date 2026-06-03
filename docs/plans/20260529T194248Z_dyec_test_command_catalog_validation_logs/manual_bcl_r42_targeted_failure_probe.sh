#!/usr/bin/env bash
set -euo pipefail

analysis_root="/fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert/daylily-omics-analysis"
bcl_root="$analysis_root/results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert"

echo "time=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "sacct:"
sacct -j 3546,3547,3548,3549 --format JobID,JobName%80,Partition,State,ExitCode,Elapsed,NodeList%40 -P || true
echo "logs:"
ls -lah "$bcl_root/logs" || true
echo "metrics:"
ls -lah "$bcl_root/metrics" || true
echo "tables:"
ls -lah "$bcl_root/tables" || true
echo "known rule logs:"
for path in \
  "$bcl_root/logs/bclconvert_metrics_summary.log" \
  "$bcl_root/logs/bclconvert_generate_units_tsv.log" \
  "$bcl_root/logs/run_bclconvert.merge_lanes.log"; do
  echo "--- $path ---"
  if [[ -f "$path" ]]; then
    tail -n 120 "$path"
  else
    echo "missing"
  fi
done
echo "latest snakemake logs:"
ls -lat "$analysis_root/.snakemake/log" | head -10 || true
latest="$(ls -t "$analysis_root/.snakemake/log"/*.snakemake.log 2>/dev/null | head -1 || true)"
if [[ -n "$latest" ]]; then
  echo "--- $latest ---"
  tail -n 260 "$latest"
fi
