#!/usr/bin/env bash
set -euo pipefail

analysis_root="/fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert/daylily-omics-analysis"
run_id="20260514_LH01106_0009_B23TVLGLT4"
generated_units="$analysis_root/results/runs/${run_id}/bclconvert/tables/generated.units.tsv"
target_units="$analysis_root/config/units.tsv"

echo "time=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
test -s "$generated_units"
cp -- "$generated_units" "$target_units"
ls -lah "$generated_units" "$target_units"
head -5 "$target_units"
