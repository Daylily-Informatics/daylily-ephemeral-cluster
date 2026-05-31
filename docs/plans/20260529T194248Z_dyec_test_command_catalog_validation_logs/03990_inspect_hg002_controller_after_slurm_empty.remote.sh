#!/usr/bin/env bash
set -euo pipefail

session=ccv20260530r50_illumina_hg002_kitchensink_multiqc
repo=/fsx/analysis_results/ubuntu/${session}/daylily-omics-analysis

echo "=== controller status ==="
cat "/home/ubuntu/daylily-runs/${session}/status.json" || true

echo "=== tmux alive ==="
tmux list-sessions 2>/dev/null | grep "$session" || true

echo "=== controller ps ==="
pgrep -af "$session|snakemake|multiqc|day_run" | head -80 || true

echo "=== latest snakemake log ==="
cd "$repo"
latest=$(ls -t .snakemake/log/*.snakemake.log 2>/dev/null | head -1 || true)
printf '%s\n' "$latest"
if [ -n "$latest" ]; then
  tail -120 "$latest"
fi

echo "=== recent workflow logs ==="
find results/day/hg38 -type f -path '*log*' -mmin -10 -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' 2>/dev/null | sort | tail -80
