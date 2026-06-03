#!/usr/bin/env bash
set -euo pipefail

session=ccv20260529r32_illumina_hg002_kitchensink_multiqc
repo="/fsx/analysis_results/ubuntu/${session}/daylily-omics-analysis"
cd "${repo}"

show_files() {
  local title="$1"
  shift
  echo "## ${title}"
  find "$@" -maxdepth 4 -type f -printf '%T@ %s %p\n' 2>/dev/null | sort -nr | head -n 60 || true
}

show_tail() {
  local title="$1"
  shift
  echo "## ${title}"
  while IFS= read -r path; do
    echo "### ${path}"
    tail -n 80 "${path}" | cut -c1-420 || true
  done < <(find "$@" -maxdepth 4 -type f \( -name '*.log' -o -name '*.err' -o -name '*.out' \) 2>/dev/null | sort | head -n 20)
}

show_files "goleft files" \
  results/day/hg38/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ/align/sent/dmd/alignqc/goleft \
  results/day/hg38/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ/align/sent/na/alignqc/goleft
show_tail "goleft logs" \
  results/day/hg38/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ/align/sent/dmd/alignqc/goleft \
  results/day/hg38/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ/align/sent/na/alignqc/goleft

show_files "mosdepth files" \
  results/day/hg38/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ/align/sent/dmd/alignqc/mosdepth \
  results/day/hg38/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ/align/sent/na/alignqc/mosdepth
show_tail "mosdepth logs" \
  results/day/hg38/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ/align/sent/dmd/alignqc/mosdepth \
  results/day/hg38/JEMILMN0P1-HG002-0p1x-1-D0-PF-ILMN-NOVASEQ/align/sent/na/alignqc/mosdepth

echo "## contam identity files"
find results/day/hg38 -type f -path '*contam*identity*' -printf '%T@ %s %p\n' 2>/dev/null | sort -nr | head -n 80 || true
echo "## contam identity log tails"
while IFS= read -r path; do
  echo "### ${path}"
  tail -n 80 "${path}" | cut -c1-420 || true
done < <(find results/day/hg38 -type f \( -path '*contam*identity*log*' -o -path '*contam*identity*.log' \) 2>/dev/null | sort | head -n 20)

echo "## vep cache directories"
find /fsx/references/runtime_assets/tool_specific_resources/vep -maxdepth 5 -type d -printf '%p\n' 2>/dev/null | sort | head -n 120 || true
echo "## vep logs"
while IFS= read -r path; do
  echo "### ${path}"
  tail -n 60 "${path}" | cut -c1-420 || true
done < <(find results/day/hg38 -type f -path '*vep*log*' 2>/dev/null | sort | head -n 20)
