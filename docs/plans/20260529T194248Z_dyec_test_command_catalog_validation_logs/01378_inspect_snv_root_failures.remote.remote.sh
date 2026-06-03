#!/usr/bin/env bash
set -euo pipefail

sessions=(
  ccv20260529r6_ultima_snv_alignstats
  ccv20260529r6_ont_snv_alignstats
  ccv20260529r6_pacbio_snv_alignstats
)

for session in "${sessions[@]}"; do
  repo="/fsx/analysis_results/ubuntu/${session}/daylily-omics-analysis"
  echo "## ${session}"
  if [[ ! -d "${repo}" ]]; then
    echo "MISSING_REPO ${repo}"
    continue
  fi
  echo "### status"
  cat "/home/ubuntu/daylily-runs/${session}/status.json" 2>/dev/null || true
  echo "### SNV rule logs"
  find "${repo}/results" "${repo}/logs/slurm" -type f \
    \( -name '*snv*.log' -o -name '*snv*.err' -o -name '*sent*.err' -o -name '*sent*.out' \) \
    -printf '%T@ %s %p\n' 2>/dev/null | sort -nr | head -n 40
  while IFS= read -r log_path; do
    echo "--- ${log_path}"
    grep -nEi 'ERROR|failed|exception|traceback|license|denied|killed|cannot|missing|not produced|exit code|assert|segmentation|permission|No such file|No space|out.of.memory|oom' "${log_path}" | tail -n 80 || true
    echo "--- tail ${log_path}"
    tail -n 80 "${log_path}" | cut -c1-420 || true
  done < <(
    find "${repo}/results" "${repo}/logs/slurm" -type f \
      \( -name '*snv*.log' -o -name '*snv*.err' -o -name '*sent*.err' \) \
      -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk '{print $2}' | head -n 12
  )
done
