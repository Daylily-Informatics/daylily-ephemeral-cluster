#!/usr/bin/env bash
set -euo pipefail

session=ccv20260529r32_illumina_hg002_kitchensink_multiqc
repo="/fsx/analysis_results/ubuntu/${session}/daylily-omics-analysis"
run_dir="/home/ubuntu/daylily-runs/${session}"

echo "## session ${session}"
echo "## repo ${repo}"
echo "## run_dir ${run_dir}"

if [[ ! -d "${repo}" ]]; then
  echo "MISSING_REPO ${repo}"
  exit 0
fi

echo "## status and wrapper logs"
for path in \
  "${run_dir}/status.json" \
  "${run_dir}/tmux.log" \
  "${run_dir}/stdout.log" \
  "${run_dir}/stderr.log" \
  "${run_dir}/workflow.out" \
  "${run_dir}/workflow.err" \
  "${run_dir}/run.log" \
  "${run_dir}/command.sh" \
  "${repo}/day_cmd.log" \
  "${repo}/logs/daylily_cmd.log" \
  "${repo}/logs/status.log"; do
  if [[ -f "${path}" ]]; then
    echo "### ${path}"
    tail -n 320 "${path}" | cut -c1-520 || true
  fi
done

echo "## latest snakemake logs"
find "${repo}/.snakemake/log" -type f -printf '%T@ %s %p\n' 2>/dev/null | sort -nr | head -n 20 || true

echo "## snakemake focused errors"
while IFS= read -r log_path; do
  echo "### ${log_path}"
  grep -nE 'ERROR|Error|Exception|Traceback|WorkflowError|RuleException|MissingInput|MissingOutput|MissingRule|SyntaxError|NameError|failed|Failed|returned non-zero|No such file|No space|Killed|exit code|assert|Config file|KeyError|ValueError|ImportError' "${log_path}" | tail -n 160 || true
  echo "--- tail ${log_path}"
  tail -n 260 "${log_path}" | cut -c1-520 || true
done < <(find "${repo}/.snakemake/log" -type f -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk '{print $2}' | head -n 10)

echo "## recent result logs with errors"
while IFS= read -r log_path; do
  echo "### ${log_path}"
  grep -nEi 'ERROR|failed|exception|traceback|license|denied|killed|cannot|missing|not produced|exit code|assert|No such file|No space|oom|segmentation|Config file|KeyError|ValueError|ImportError' "${log_path}" | tail -n 100 || true
  echo "--- tail ${log_path}"
  tail -n 160 "${log_path}" | cut -c1-520 || true
done < <(find "${repo}/results" -type f \( -name '*.log' -o -name '*.err' -o -name '*.out' \) -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk '{print $2}' | head -n 40)

echo "## expected high-level outputs"
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
