#!/usr/bin/env bash
set -euo pipefail

analysis_root="/fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert/daylily-omics-analysis"

echo "time=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "sacct:"
sacct -j 3546,3547,3548,3549 --format JobID,JobName%80,Partition,State,ExitCode,Elapsed,NodeList%40 -P || true
echo "matching files:"
find "$analysis_root" -type f \
  \( -name '*3546*' -o -name '*3547*' -o -name '*3548*' -o -name '*3549*' -o -name '*bclconvert_metrics_summary*' -o -name '*bclconvert_generate_units_tsv*' \) \
  -printf '%s %p\n' | sort -n || true
echo "latest snakemake log:"
latest="$(find "$analysis_root/.snakemake/log" -type f -name '*.snakemake.log' -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)"
if [[ -n "$latest" ]]; then
  echo "$latest"
  tail -n 240 "$latest"
fi
echo "cluster logs:"
find "$analysis_root" -type f \
  \( -path '*/logs/*' -o -path '*/slurm*' -o -path '*/.snakemake/*' \) \
  -printf '%T@ %s %p\n' 2>/dev/null | sort -n | tail -120 || true
