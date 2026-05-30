#!/usr/bin/env bash
set -euo pipefail

session=ccv20260529r31_illumina_hg002_kitchensink_multiqc_dryrun
repo="/fsx/analysis_results/ubuntu/${session}/daylily-omics-analysis"

echo "## session ${session}"
echo "## repo ${repo}"

if [[ ! -d "${repo}" ]]; then
  echo "MISSING_REPO ${repo}"
  exit 0
fi

echo "## sentinel files"
find "/fsx/analysis_results/ubuntu/${session}" -maxdepth 3 -type f \
  \( -name 'daylily.failed_run' -o -name 'daylily.completed_run' -o -name 'status.json' -o -name '*.log' \) \
  -printf '%T@ %s %p\n' 2>/dev/null | sort -nr | head -n 80 || true

echo "## command wrapper logs"
for path in \
  "${repo}/day_cmd.log" \
  "${repo}/unlock_fails.log" \
  "${repo}/logs/about.log" \
  "${repo}/logs/daylily_cmd.log" \
  "${repo}/logs/status.log"; do
  if [[ -f "${path}" ]]; then
    echo "### ${path}"
    tail -n 260 "${path}" | cut -c1-420 || true
  fi
done

echo "## snakemake logs"
if [[ -d "${repo}/.snakemake/log" ]]; then
  find "${repo}/.snakemake/log" -type f -printf '%T@ %s %p\n' | sort -nr | head -n 20
else
  echo "NO_SNAKEMAKE_LOG_DIR"
fi

echo "## focused errors"
if [[ -d "${repo}/.snakemake/log" ]]; then
  while IFS= read -r log_path; do
    echo "### ${log_path}"
    grep -nE 'ERROR|Error|Exception|Traceback|WorkflowError|RuleException|MissingInput|MissingOutput|SyntaxError|NameError|failed|failed_run|exiting|No rule|target|unexpected|repair' "${log_path}" | tail -n 120 || true
    echo "--- tail ${log_path}"
    tail -n 220 "${log_path}" | cut -c1-420 || true
  done < <(find "${repo}/.snakemake/log" -type f -printf '%T@ %p\n' | sort -nr | awk '{print $2}' | head -n 8)
fi

echo "## runtime repair strings"
grep -R -nE 'Runtime patch|NO_VARIANTS|vep_concat_fofn|haplocheck_vcf_contam_identity|read_haps_contam_identity|goleft indexcov' "${repo}" \
  --include='*.smk' --include='*.log' --include='*.out' --include='*.err' 2>/dev/null | head -n 200 || true
