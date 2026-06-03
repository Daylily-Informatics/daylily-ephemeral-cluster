set -euo pipefail
repo=/fsx/analysis_results/ubuntu/ccv20260529r40_illumina_hg002_kitchensink_multiqc/daylily-omics-analysis
cd "$repo"
log=.snakemake/log/2026-05-30T102941.838238.snakemake.log
for pat in 'Error in rule' 'RuleException' 'Job failed' 'exited with' 'non-zero exit status' 'MissingOutputException' 'FailedRuleException' 'Complete log'; do
  echo "=== PATTERN $pat ==="
  grep -n -B4 -A25 "$pat" "$log" | tail -160 || true
done
echo '=== last 260 lines ==='
tail -260 "$log" | sed -n '1,260p'
echo '=== likely failed rule logs recent ==='
find results/day/hg38 -type f -mmin -20 \( -name '*.log' -o -name '*.err' -o -name '*.out' \) -print 2>/dev/null | sort | while read -r f; do
  if grep -qiE 'error|exception|traceback|failed|non-zero|missing|killed|oom|slurmstepd' "$f"; then
    echo "--- $f ---"
    tail -80 "$f" || true
  fi
done
