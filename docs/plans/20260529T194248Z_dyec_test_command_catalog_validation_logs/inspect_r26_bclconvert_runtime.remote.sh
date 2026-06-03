set -euo pipefail
aid=ccv20260529r26_illumina_bclconvert
repo="/fsx/analysis_results/ubuntu/${aid}/daylily-omics-analysis"
echo "status:"
cat "/home/ubuntu/daylily-runs/${aid}/status.json" || true
echo
echo "active_bcl_config:"
grep -n -A32 -B2 '^bclconvert:' "$repo/config/day_profiles/slurm/rule_config.yaml" || true
echo
echo "config_tables:"
ls -l "$repo/config"/{runs.tsv,samples.tsv,units.tsv} 2>/dev/null || true
if [[ -f "$repo/config/units.tsv" ]]; then
  wc -l "$repo/config/units.tsv"
  sed -n '1,8p' "$repo/config/units.tsv"
else
  echo "config/units.tsv missing"
fi
echo
echo "run_log_tail:"
tail -n 220 "$repo/results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/logs/run_bclconvert.log" 2>/dev/null || true
echo
echo "scratch_tree:"
find "$repo/.bclconvert_scratch" -maxdepth 3 -mindepth 1 -print -exec ls -ld {} \; 2>/dev/null | head -n 180 || true
echo
echo "slurm:"
squeue -o "%.18i %.9P %.12j %.8u %.2t %.10M %.6D %R" || true
sacct -j 2660 --format=JobID,JobName%40,State,ExitCode,Elapsed,AllocCPUS,NodeList -P 2>/dev/null || true
