#!/usr/bin/env bash
set -euo pipefail

echo "=== hg002 read_haps prechecks ==="
hg_repo="/fsx/analysis_results/ubuntu/ccv20260530r48_illumina_hg002_kitchensink_multiqc/daylily-omics-analysis"
cd "$hg_repo"
for p in \
  /fsx/references/runtime_assets/tool_specific_resources/read_haps/read_haps \
  /fsx/references/runtime_assets/tool_specific_resources/read_haps/high_quality_markers_deCODE_2015.txt.gz \
  results/day/hg38/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ/align/sent/dmd/compat_bam/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ.sent.dmd.legacy_compat.bam \
  results/day/hg38/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ/align/sent/dmd/snv/sentd/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ.sent.dmd.sentd.snv.sort.vcf.gz; do
  echo "--- $p"
  if [[ -e "$p" ]]; then
    ls -lh "$p"
    if [[ -x "$p" ]]; then echo executable=yes; else echo executable=no; fi
  else
    echo MISSING
  fi
done
echo "=== hg002 variant probe ==="
set +o pipefail
gzip -cd results/day/hg38/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ/align/sent/dmd/snv/sentd/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ.sent.dmd.sentd.snv.sort.vcf.gz | grep -m 3 -v '^#' || true
set -o pipefail

echo "=== hybrid ultima stage1 log errors ==="
hu_log="/fsx/analysis_results/ubuntu/ccv20260530r48_hybrid_ultima_ont_snv/daylily-omics-analysis/results/day/hg38_broad/TVBHUO5X5X-HG003-UG5x-ONT5x-1-D0-PF-UG-ULTIMA/align/ug/na/snv/sentdhuomr/log/TVBHUO5X5X-HG003-UG5x-ONT5x-1-D0-PF-UG-ULTIMA.ug.na.1-24.stage1.log"
grep -nEi 'error|fail|assert|killed|terminate|truncated|quickcheck|no space|cannot|exception|warning' "$hu_log" | tail -n 80 || true
echo "=== hybrid ultima stage1 log tail ==="
tail -n 180 "$hu_log" || true
echo "=== hybrid ultima tmp files ==="
find /fsx/analysis_results/ubuntu/ccv20260530r48_hybrid_ultima_ont_snv/daylily-omics-analysis/results/day/hg38_broad/TVBHUO5X5X-HG003-UG5x-ONT5x-1-D0-PF-UG-ULTIMA/align/ug/na/snv/sentdhuomr/vcfs/1-24/tmp -maxdepth 1 -type f \
  -printf '%s %TY-%Tm-%TdT%TH:%TM:%TS %p\n' | sort || true
