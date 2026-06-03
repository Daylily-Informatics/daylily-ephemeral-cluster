set -euo pipefail
repo=/fsx/analysis_results/ubuntu/ccv20260529r40_illumina_hg002_kitchensink_multiqc/daylily-omics-analysis
cd "$repo"
echo '=== main logs ==='
ls -lt .snakemake/log || true
for f in $(ls -t .snakemake/log/*.snakemake.log 2>/dev/null | head -5); do
  echo "=== $f tail ==="
  tail -120 "$f" || true
  echo "=== $f errors ==="
  grep -nEi 'error|exception|traceback|missingoutput|ruleexception|failed|non-zero|killed|oom|out.of.memory|slurmstepd|incomplete|latency' "$f" | tail -80 || true
done
