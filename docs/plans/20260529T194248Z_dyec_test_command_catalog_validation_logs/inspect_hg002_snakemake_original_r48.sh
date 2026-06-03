#!/usr/bin/env bash
set -euo pipefail
repo="/fsx/analysis_results/ubuntu/ccv20260530r48_illumina_hg002_kitchensink_multiqc/daylily-omics-analysis"
cd "$repo"
echo "=== snakemake logs ==="
ls -ltr .snakemake/log/*.snakemake.log
for f in .snakemake/log/*.snakemake.log; do
  echo "=== grep error markers: $f ==="
  grep -nE "Error|RuleException|MissingOutput|failed|Failed|exit code|Traceback|Unlocking" "$f" | tail -n 120 || true
  echo "=== tail: $f ==="
  tail -n 180 "$f" || true
done
echo "=== suspicious rule log tails ==="
find results logs -type f \( -name '*.log' -o -name '*.err' -o -name '*.out' \) 2>/dev/null \
  | while read -r f; do
      if grep -qiE 'error|failed|traceback|exception|outside the range|missing' "$f"; then
        echo "--- $f"
        tail -n 30 "$f" || true
      fi
    done | tail -n 300
