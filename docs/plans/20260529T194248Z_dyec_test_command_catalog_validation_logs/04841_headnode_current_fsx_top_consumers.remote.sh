set -euo pipefail
echo '=== now ==='
date -u +%Y-%m-%dT%H:%M:%SZ
echo '=== df ==='
df -hT /fsx /dev/shm /
echo '=== slurm ==='
squeue -h -o '%i|%P|%T|%M|%D|%R|%j' || true
echo '=== active validation processes ==='
ps -eo pid,ppid,stat,pcpu,pmem,etime,cmd --sort=-pcpu \
  | grep -E 'ccv202605|snakemake|day_run|dyec export|fsx_export|dra' \
  | grep -v grep || true
echo '=== /fsx top level ==='
du -xhd1 /fsx 2>/dev/null | sort -h | tail -30
echo '=== analysis_results ubuntu top ==='
du -xhd1 /fsx/analysis_results/ubuntu 2>/dev/null | sort -h | tail -40
echo '=== run dir mounts top ==='
if [[ -d /fsx/run_dir_mounts ]]; then
  du -xhd1 /fsx/run_dir_mounts 2>/dev/null | sort -h | tail -20
else
  echo missing /fsx/run_dir_mounts
fi
echo '=== staging top ==='
if [[ -d /fsx/staging ]]; then
  du -xhd2 /fsx/staging 2>/dev/null | sort -h | tail -30
else
  echo missing /fsx/staging
fi
