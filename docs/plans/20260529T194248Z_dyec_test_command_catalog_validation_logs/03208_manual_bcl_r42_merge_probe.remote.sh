#!/usr/bin/env bash
set -euo pipefail

analysis_root="/fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert/daylily-omics-analysis"
run_root="$analysis_root/results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert"
merge_log="$analysis_root/logs/bclconvert/run_bclconvert.merge_lanes.log"

echo "time=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
df -h /fsx
echo "squeue:"
squeue -h -o '%i %P %C %t %N %m %M %j' || true
echo "run_dir_projection_links:"
find "$analysis_root/config" -maxdepth 3 -type l -printf '%p -> %l\n' | sort || true
echo "fastq_dir_listing:"
find "$run_root/fastqs" -maxdepth 1 -type f -printf '%f\n' 2>/dev/null | wc -l || true
echo "lane_fastq_dirs:"
find "$run_root/lane_fastqs" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null | sort || true
echo "merge_log_tail:"
if [[ -f "$merge_log" ]]; then
  tail -n 80 "$merge_log"
else
  echo "merge log missing: $merge_log"
fi
