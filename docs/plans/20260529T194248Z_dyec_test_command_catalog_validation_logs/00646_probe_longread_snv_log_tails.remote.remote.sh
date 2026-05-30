set -euo pipefail
base=/fsx/analysis_results/ubuntu
for analysis in \
  ccv20260529r6_ultima_snv_alignstats \
  ccv20260529r6_ont_snv_alignstats \
  ccv20260529r6_pacbio_snv_alignstats \
  ccv20260529r9_hybrid_ultima_ont_snv; do
  repo="$base/$analysis/daylily-omics-analysis"
  echo "=== $analysis ==="
  if [[ ! -d "$repo" ]]; then
    echo "MISSING repo $repo"
    continue
  fi
  cd "$repo"
  find results/day -type f \( -name '*.snv.log' -o -name '*stage1.log' -o -name '*stage3.log' \) | sort
  for log in $(find results/day -type f \( -name '*.snv.log' -o -name '*stage1.log' -o -name '*stage3.log' \) | sort | head -12); do
    echo "### $log"
    tail -50 "$log"
  done
done
