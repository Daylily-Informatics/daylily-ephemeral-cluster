#!/usr/bin/env bash
set -euo pipefail

session=ccv20260529r32_illumina_hg002_kitchensink_multiqc
repo="/fsx/analysis_results/ubuntu/${session}/daylily-omics-analysis"
run_dir="/home/ubuntu/daylily-runs/${session}"

echo "## status"
if [[ -f "${run_dir}/status.json" ]]; then
  cat "${run_dir}/status.json" | cut -c1-360
fi

echo "## latest snakemake logs"
find "${repo}/.snakemake/log" -type f -printf '%T@ %s %p\n' 2>/dev/null | sort -nr | head -n 8

echo "## latest snakemake grep"
while IFS= read -r log_path; do
  echo "### ${log_path}"
  grep -nE 'ERROR|Error|Exception|Traceback|WorkflowError|RuleException|MissingInput|MissingOutput|MissingRule|SyntaxError|NameError|failed|Failed|returned non-zero|No such file|No space|Killed|exit code|assert|Config file|KeyError|ValueError|ImportError' "${log_path}" | tail -n 80 || true
  echo "--- final 80"
  tail -n 80 "${log_path}" | cut -c1-420
done < <(find "${repo}/.snakemake/log" -type f -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk '{print $2}' | head -n 3)

echo "## recent result logs names"
find "${repo}/results" -type f \( -name '*.log' -o -name '*.err' -o -name '*.out' \) -printf '%T@ %s %p\n' 2>/dev/null | sort -nr | head -n 30

echo "## recent result log greps"
while IFS= read -r log_path; do
  echo "### ${log_path}"
  grep -nEi 'ERROR|failed|exception|traceback|license|denied|killed|cannot|missing|not produced|exit code|assert|No such file|No space|oom|segmentation|Config file|KeyError|ValueError|ImportError' "${log_path}" | tail -n 30 || true
done < <(find "${repo}/results" -type f \( -name '*.log' -o -name '*.err' -o -name '*.out' \) -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk '{print $2}' | head -n 30)

echo "## high-level outputs"
for path in \
  "${repo}/results/day/hg38/other_reports/giab_concordance_mqc.tsv" \
  "${repo}/results/day/hg38/multiqc_report.html" \
  "${repo}/results/day/hg38/other_reports/contam_identity_mqc.tsv" \
  "${repo}/results/day/hg38/other_reports/vep_mqc.tsv"; do
  if [[ -e "${path}" ]]; then
    ls -lh "${path}"
  else
    echo "MISSING ${path}"
  fi
done
