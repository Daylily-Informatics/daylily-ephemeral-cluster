#!/usr/bin/env bash
set -euo pipefail

repo="/fsx/analysis_results/ubuntu/ccv20260530r48_illumina_hg002_kitchensink_multiqc/daylily-omics-analysis"
cd "$repo"

echo "=== rule source markers ==="
grep -n "read_haps_rc\\|READ_HAPS_FAILED\\|NO_VARIANTS\\|rule read_haps_contam_identity" workflow/rules/contam_identity.smk || true

echo "=== rule source excerpt ==="
start="$(grep -n "rule read_haps_contam_identity" workflow/rules/contam_identity.smk | head -n 1 | cut -d: -f1 || true)"
if [[ -n "$start" ]]; then
  end=$((start + 90))
  sed -n "${start},${end}p" workflow/rules/contam_identity.smk
fi

echo "=== read_haps outputs ==="
find results/day/hg38 -path '*contam_identity/read_haps*' -type f -printf '%s %TY-%Tm-%TdT%TH:%TM:%TS %p\n' | sort || true

echo "=== read_haps log tails ==="
find results/day/hg38 -path '*contam_identity/read_haps/logs/*' -type f | sort | while read -r f; do
  echo "--- $f"
  tail -n 120 "$f" || true
done

echo "=== read_haps text outputs ==="
find results/day/hg38 -path '*contam_identity/read_haps/*.txt' -type f | sort | while read -r f; do
  echo "--- $f"
  ls -lh "$f"
  sed -n '1,30p' "$f" || true
done

echo "=== snakemake read_haps error context ==="
for f in .snakemake/log/*.snakemake.log; do
  echo "--- $f"
  grep -n -B20 -A80 "read_haps_contam_identity" "$f" || true
done
