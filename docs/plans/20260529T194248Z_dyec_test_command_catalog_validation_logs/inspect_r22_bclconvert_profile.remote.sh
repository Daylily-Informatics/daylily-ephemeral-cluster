set -euo pipefail
aid=ccv20260529r22_illumina_bclconvert
repo="/fsx/analysis_results/ubuntu/${aid}/daylily-omics-analysis"
echo "tmux_log_head:"
sed -n '1,180p' "/home/ubuntu/daylily-runs/${aid}/tmux.log" || true
echo "rule_config_paths:"
find "$repo" -path "*/rule_config.yaml" -print 2>/dev/null || true
echo "bclconvert_blocks:"
while IFS= read -r cfg; do
  echo "--- ${cfg}"
  grep -n -A24 -B2 'bclconvert:' "$cfg" || true
done < <(find "$repo" -path "*/rule_config.yaml" -print 2>/dev/null)
echo "run_bclconvert_log_head:"
sed -n '1,120p' "$repo/results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/logs/run_bclconvert.log" 2>/dev/null || true
