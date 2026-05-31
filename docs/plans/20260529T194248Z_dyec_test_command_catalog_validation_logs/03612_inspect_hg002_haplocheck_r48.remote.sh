#!/usr/bin/env bash
set -euo pipefail
repo="/fsx/analysis_results/ubuntu/ccv20260530r48_illumina_hg002_kitchensink_multiqc/daylily-omics-analysis"
cd "$repo"
echo "=== patched rule markers ==="
grep -n "UNSUPPORTED_REFERENCE\|NO_VARIANTS: haplocheck\|haplocheck_rc" workflow/rules/contam_identity.smk || true
echo "=== haplocheck output files ==="
base="results/day/hg38/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ/align/sent/dmd/snv/sentd/contam_identity/haplocheck/vcf"
find "$base" -maxdepth 2 -type f -printf '%s %p\n' | sort -n | tail -n 30 || true
echo "=== haplocheck log tail ==="
tail -n 80 "$base/logs/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ.sent.dmd.sentd.haplocheck.vcf.log" || true
echo "=== declared outputs ==="
for f in \
  "$base/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ.sent.dmd.sentd.haplocheck.contamination.txt" \
  "$base/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ.sent.dmd.sentd.haplocheck.contamination.raw.txt" \
  "$base/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ.sent.dmd.sentd.haplocheck.report.html"; do
  echo "--- $f"
  if [[ -e "$f" ]]; then
    ls -lh "$f"
    sed -n '1,8p' "$f" || true
  else
    echo "MISSING"
  fi
done
echo "=== latest snakemake log tail ==="
latest="$(ls -t .snakemake/log/*.snakemake.log | head -n 1)"
echo "$latest"
tail -n 160 "$latest"
