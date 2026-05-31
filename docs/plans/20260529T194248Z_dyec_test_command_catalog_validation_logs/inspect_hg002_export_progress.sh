#!/usr/bin/env bash
set -euo pipefail

run=/home/ubuntu/daylily-runs/ccv20260530r50_illumina_hg002_kitchensink_multiqc
echo "=== export files ==="
find "$run/export" -maxdepth 3 -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' 2>/dev/null | sort || true
echo "=== export logs/tails ==="
for f in "$run"/export/* "$run"/export/*/*; do
  [ -f "$f" ] || continue
  echo "--- $f ---"
  tail -80 "$f" || true
done
echo "=== s3 prefix sample/count ==="
AWS_PROFILE=lsmc aws s3 ls s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/ccv20260530r50_illumina_hg002_kitchensink_multiqc/ --recursive --summarize --human-readable --region us-west-2 | tail -20 || true
