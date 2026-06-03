#!/usr/bin/env bash
set -euo pipefail

analysis_root="/fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert/daylily-omics-analysis"
bcl_root="$analysis_root/results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert"

echo "time=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
df -h /fsx
echo "squeue:"
squeue -h -o '%i %P %C %t %N %m %M %j' || true
echo "status:"
cat "/fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert/status.json" || true
echo
echo "run_dir_projection_links:"
find "$analysis_root/config" -maxdepth 3 -type l -printf '%p -> %l\n' | sort || true
echo "bclconvert outputs:"
find "$bcl_root" -maxdepth 3 -type f \
  \( -name 'bclconvert_metrics_summary.log' -o -name 'bclconvert_generate_units_tsv.log' -o -name 'fastq_list.csv' -o -name 'Demultiplex_Stats.csv' -o -name 'generated.units.tsv' -o -name '*.out' -o -name '*.err' \) \
  -printf '%s %p\n' | sort -n || true
echo "metrics summary log:"
cat "$bcl_root/logs/bclconvert_metrics_summary.log" || true
echo "generate units log:"
cat "$bcl_root/logs/bclconvert_generate_units_tsv.log" || true
echo "snakemake logs:"
find "$analysis_root/.snakemake" -maxdepth 4 -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -40 || true
