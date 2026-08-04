#!/usr/bin/env bash
set -euo pipefail

cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate >/dev/null

dyec export \
  --cluster preval-hiomr2 \
  --source-path /analysis_results/preval-hiomr2/remaining-giab/ \
  --destination-s3-uri s3://lsmc-ssf-sequencing-data/derived/preval-hiomr2/remaining-giab/ \
  --region us-west-2 \
  --profile lsmc \
  --output-dir docs/plans/20260804T185300Z_remaining_giab_final_report_reconciliation_export \
  --timeout-seconds 7200
