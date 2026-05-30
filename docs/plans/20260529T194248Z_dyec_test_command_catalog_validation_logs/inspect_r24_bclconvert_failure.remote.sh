set -euo pipefail
aid=ccv20260529r24_illumina_bclconvert
repo="/fsx/analysis_results/ubuntu/${aid}/daylily-omics-analysis"
echo "status:"
cat "/home/ubuntu/daylily-runs/${aid}/status.json" || true
echo "tmux_patch_lines:"
grep -nE 'BCL Convert|Patched|rule_config|Executing:|units.tsv|WorkflowError|RETURN CODE' "/home/ubuntu/daylily-runs/${aid}/tmux.log" || true
echo "config_units:"
if [[ -f "$repo/config/units.tsv" ]]; then
  wc -l "$repo/config/units.tsv"
  sed -n '1,5p' "$repo/config/units.tsv"
else
  echo "missing units.tsv"
fi
echo "active_bcl_config:"
grep -n -A28 -B2 '^bclconvert:' "$repo/config/day_profiles/slurm/rule_config.yaml" || true
echo "run_bclconvert_log:"
sed -n '1,120p' "$repo/results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/logs/run_bclconvert.log" 2>/dev/null || true
echo "scratch_tree:"
find /fsx/scratch/dayoa_bclconvert -maxdepth 3 -mindepth 1 -print -exec ls -ld {} \; 2>/dev/null | head -n 120 || true
