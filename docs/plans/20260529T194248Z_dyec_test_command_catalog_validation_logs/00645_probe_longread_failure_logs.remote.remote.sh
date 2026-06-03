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
  echo "--- sentieon and concordance logs ---"
  find results logs -type f \( -path '*snv*log*' -o -path '*vcfeval*log*' -o -path '*sent*d*err' \) \
    | sort \
    | while read -r log; do
        if grep -Eiq 'error|failed|assertion|exception|traceback|exit code|no such|fatal' "$log"; then
          echo "### $log"
          tail -120 "$log"
        fi
      done
done
