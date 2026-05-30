#!/usr/bin/env bash
set -euo pipefail

session=ccv20260529r30_illumina_snv_alignstats_relatedness_vep_multiqc
run_dir="/home/ubuntu/daylily-runs/${session}"
analysis_dir="/fsx/analysis_results/ubuntu/${session}"

echo "## status"
cat "${run_dir}/status.json" 2>/dev/null || true
echo "## run dir"
find "${run_dir}" -maxdepth 3 -type f -printf '%T@ %s %p\n' | sort -nr | head -n 80
echo "## tmux tail"
tail -n 80 "${run_dir}/tmux.log" | cut -c1-420 || true
echo "## process tree"
ps -eo pid,ppid,stat,etime,pcpu,pmem,command | grep -F "${session}" | grep -v grep || true
echo "## analysis dir"
if [[ -e "${analysis_dir}" ]]; then
  du -sh "${analysis_dir}" 2>/dev/null || true
  find "${analysis_dir}" -maxdepth 2 -type d -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 30 || true
else
  echo "ABSENT ${analysis_dir}"
fi
