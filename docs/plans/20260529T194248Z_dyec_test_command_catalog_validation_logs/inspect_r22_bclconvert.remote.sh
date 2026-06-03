set -euo pipefail
aid=ccv20260529r22_illumina_bclconvert
repo="/fsx/analysis_results/ubuntu/${aid}/daylily-omics-analysis"
echo "aid=${aid}"
echo "repo=${repo}"
if [[ -f "/home/ubuntu/daylily-runs/${aid}/status.json" ]]; then
  echo "status_json:"
  cat "/home/ubuntu/daylily-runs/${aid}/status.json"
fi
if [[ -d "$repo" ]]; then
  echo "bclconvert_profile:"
  awk '
    /^  bclconvert:/ {show=1}
    show {print}
    show && NF && $0 !~ /^ / && $0 !~ /^  bclconvert:/ {exit}
  ' "$repo/profiles/local/hg38_broad_slurm/rule_config.yaml" || true
  echo "recent_bcl_logs:"
  find "$repo" -path "*/logs/*" -type f -name "*bclconvert*" -print -exec tail -n 60 {} \; 2>/dev/null || true
fi
echo "slurm_queue:"
squeue -o "%.18i %.20P %.8T %.10M %.9l %.6D %.20j" || true
echo "scratch_usage:"
du -sh /fsx/scratch/dayoa_bclconvert 2>/dev/null || true
find /fsx/scratch/dayoa_bclconvert -maxdepth 2 -mindepth 1 -type d -print -exec du -sh {} \; 2>/dev/null | head -n 80 || true
echo "analysis_usage:"
du -sh "/fsx/analysis_results/ubuntu/${aid}" 2>/dev/null || true
