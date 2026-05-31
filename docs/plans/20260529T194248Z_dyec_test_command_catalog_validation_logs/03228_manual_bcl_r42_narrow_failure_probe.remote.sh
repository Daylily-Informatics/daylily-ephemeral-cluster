#!/usr/bin/env bash
set -euo pipefail

analysis_root="/fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert/daylily-omics-analysis"
bcl_root="$analysis_root/results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert"

echo "time=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "sacct:"
sacct -j 3546,3547,3548,3549 --format JobID,JobName%80,Partition,State,ExitCode,Elapsed,NodeList%40 -P || true
echo "shallow log dirs:"
find "$analysis_root" -maxdepth 5 -type d \( -name 'logs' -o -name 'log' -o -name 'slurm*' \) -printf '%p\n' | sort || true
echo "bcl logs listing:"
find "$bcl_root/logs" -maxdepth 1 -type f -printf '%T@ %s %p\n' | sort -n || true
echo "bcl metrics listing:"
find "$bcl_root/metrics" -maxdepth 1 -type f -printf '%T@ %s %p\n' 2>/dev/null | sort -n || true
echo "bcl tables listing:"
find "$bcl_root/tables" -maxdepth 1 -type f -printf '%T@ %s %p\n' 2>/dev/null | sort -n || true
echo "snakemake latest log:"
latest="$(find "$analysis_root/.snakemake/log" -maxdepth 1 -type f -name '*.snakemake.log' -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)"
if [[ -n "$latest" ]]; then
  echo "$latest"
  tail -n 260 "$latest"
fi
