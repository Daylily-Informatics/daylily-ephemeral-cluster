#!/usr/bin/env bash
set -u

sessions=(
  ccv20260529r6_ultima_snv_alignstats
  ccv20260529r6_ont_snv_alignstats
  ccv20260529r6_pacbio_snv_alignstats
)

for session in "${sessions[@]}"; do
  repo="/fsx/analysis_results/ubuntu/${session}/daylily-omics-analysis"
  echo "## ${session}"
  find "${repo}/results" -type f \
    \( -path '*/snv/*/log/*' -o -path '*/snv/*/log/vcfs/*' \) \
    -printf '%T@ %s %p\n' 2>/dev/null | sort -nr | head -n 50
  while IFS= read -r log_path; do
    echo "--- ${log_path}"
    grep -nEi 'ERROR|failed|exception|traceback|license|denied|killed|cannot|missing|not produced|exit code|assert|No such file|No space|oom|Done|Completed|Version|sentieon' "${log_path}" | tail -n 120 || true
    echo "--- tail ${log_path}"
    tail -n 100 "${log_path}" | cut -c1-420 || true
  done < <(
    find "${repo}/results" -type f \
      \( -path '*/snv/*/log/*snv*.log' -o -path '*/snv/*/log/vcfs/*snv*.log' -o -path '*/snv/*/log/*merge*.log' \) \
      -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk '{print $2}' | head -n 8
  )
done
