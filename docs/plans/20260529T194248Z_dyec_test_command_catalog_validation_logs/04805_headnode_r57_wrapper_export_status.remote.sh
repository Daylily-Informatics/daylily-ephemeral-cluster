set -euo pipefail
analysis_id=ccv20260530r57_illumina_run_qc_bclconvert
repo_dir="/fsx/analysis_results/ubuntu/${analysis_id}/daylily-omics-analysis"
status_file="/home/ubuntu/daylily-runs/${analysis_id}/status.json"
run_id=20260514_LH01106_0009_B23TVLGLT4
link_path="${repo_dir}/config/run_dir_links/${run_id}"

echo '=== now ==='
date -u +%Y-%m-%dT%H:%M:%SZ
echo '=== status.json ==='
if [[ -f "$status_file" ]]; then
  cat "$status_file"
else
  echo "missing ${status_file}"
fi
echo '=== slurm ==='
squeue -h -o '%i|%P|%T|%M|%D|%R|%j' || true
echo '=== fsx ==='
df -hT /fsx /dev/shm /
echo '=== controller processes ==='
ps -eo pid,ppid,stat,pcpu,pmem,etime,cmd --sort=-pcpu \
  | grep -E "${analysis_id}|snakemake|day_run|dyec export|fsx_export|dra" \
  | grep -v grep || true
echo '=== run-dir projection link ==='
if [[ -L "$link_path" ]]; then
  echo "link_present ${link_path} -> $(readlink "$link_path")"
elif [[ -e "$link_path" ]]; then
  echo "non_link_present ${link_path}"
else
  echo "link_absent ${link_path}"
fi
echo '=== latest snakemake log tail ==='
if [[ -d "${repo_dir}/.snakemake/log" ]]; then
  latest_log=$(find "${repo_dir}/.snakemake/log" -maxdepth 1 -type f -printf '%T@ %p\n' | sort -n | tail -n 1 | cut -d' ' -f2-)
  echo "latest_log=${latest_log}"
  tail -n 80 "$latest_log"
else
  echo "missing ${repo_dir}/.snakemake/log"
fi
echo '=== tmux log tail ==='
tmux_log="/home/ubuntu/daylily-runs/${analysis_id}/tmux.log"
if [[ -f "$tmux_log" ]]; then
  tail -n 120 "$tmux_log"
else
  echo "missing ${tmux_log}"
fi
echo '=== export files ==='
find "/fsx/analysis_results/ubuntu/${analysis_id}" -maxdepth 4 \
  \( -name 'fsx_export.yaml' -o -name '*export*receipt*' -o -name '*export*.json' -o -name '*export*.log' \) \
  -printf '%TY-%Tm-%TdT%TH:%TM:%TS %p\n' 2>/dev/null | sort | tail -n 80 || true
