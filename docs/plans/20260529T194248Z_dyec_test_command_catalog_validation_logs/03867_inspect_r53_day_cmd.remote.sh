#!/usr/bin/env bash
set -euo pipefail

repo=/fsx/analysis_results/ubuntu/ccv20260530r53_complete_genomics_mgi_snv_concordance_dryrun/daylily-omics-analysis
cd "$repo"

echo "=== day_cmd.log ==="
cat day_cmd.log || true

echo "=== unlock_fails.log ==="
cat unlock_fails.log || true

echo "=== snakemake logs ==="
for log in .snakemake/log/*.snakemake.log; do
  echo "--- $log ---"
  cat "$log"
done

echo "=== dy-r aliases ==="
type dy-r || true
type day-run || true
