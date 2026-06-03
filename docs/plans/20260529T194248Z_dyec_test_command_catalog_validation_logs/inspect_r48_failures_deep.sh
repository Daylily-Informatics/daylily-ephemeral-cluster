#!/usr/bin/env bash
set -euo pipefail

echo "=== hg002 read_haps slurm files ==="
hg_repo="/fsx/analysis_results/ubuntu/ccv20260530r48_illumina_hg002_kitchensink_multiqc/daylily-omics-analysis"
cd "$hg_repo"
find .snakemake logs results -type f 2>/dev/null \
  \( -name '*3613*' -o -name '*3649*' -o -iname '*read_haps*' \) \
  -printf '%s %TY-%Tm-%TdT%TH:%TM:%TS %p\n' | sort || true
for f in $(find .snakemake logs results -type f 2>/dev/null \
  \( -name '*3613*' -o -name '*3649*' -o -iname '*read_haps*' \) | sort); do
  echo "--- $hg_repo/$f"
  sed -n '1,220p' "$f" || true
done

echo "=== hybrid ultima stage1 files ==="
hu_repo="/fsx/analysis_results/ubuntu/ccv20260530r48_hybrid_ultima_ont_snv/daylily-omics-analysis"
cd "$hu_repo"
find results .snakemake logs -type f 2>/dev/null \
  \( -name '*stage1.log' -o -name '*3873*' -o -name '*sentdhuomr_stage1*' \) \
  -printf '%s %TY-%Tm-%TdT%TH:%TM:%TS %p\n' | sort || true
for f in $(find results .snakemake logs -type f 2>/dev/null \
  \( -name '*stage1.log' -o -name '*3873*' -o -name '*sentdhuomr_stage1*' \) | sort); do
  echo "--- $hu_repo/$f"
  tail -n 220 "$f" || true
done

echo "=== hybrid ultima output integrity ==="
find results/day -path '*sentdhuomr/vcfs/1-24/tmp/*' -maxdepth 12 -type f \
  -printf '%s %TY-%Tm-%TdT%TH:%TM:%TS %p\n' 2>/dev/null | sort | tail -n 80 || true
