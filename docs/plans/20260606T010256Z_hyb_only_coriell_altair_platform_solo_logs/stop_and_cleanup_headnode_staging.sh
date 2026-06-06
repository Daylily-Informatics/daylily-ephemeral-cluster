#!/usr/bin/env bash
set -euo pipefail
printf 'start_cleanup\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo 'before_processes'
ps -u ubuntu -f | grep -E 'hyb_only_stage_(ont|ilmn)|hybonly_stage_(ont|ilmn)|gzip -t /fsx/scratch/(ONT|ILMN)|cat -- /fsx/run_dir_mounts/ont|cp -- /fsx/run_dir_mounts/ilmn' | grep -v grep || true
for s in \
  hybonly_stage_ont_20260606T010256Z \
  hybonly_stage_ilmn_20260606T010256Z \
  hybonly_stage_ilmn_parallel_20260606T010256Z; do
  if tmux has-session -t "$s" 2>/dev/null; then
    tmux kill-session -t "$s"
    printf 'killed_tmux\t%s\n' "$s"
  else
    printf 'tmux_absent\t%s\n' "$s"
  fi
done
pkill -u ubuntu -f '/home/ubuntu/hyb_only_stage_ont_data_20260606T010256Z.sh' || true
pkill -u ubuntu -f '/home/ubuntu/hyb_only_stage_ilmn_data_20260606T010256Z.sh' || true
pkill -u ubuntu -f '/home/ubuntu/hyb_only_stage_ilmn_parallel_20260606T010256Z.sh' || true
pkill -u ubuntu -f 'gzip -t /fsx/scratch/ONT/' || true
pkill -u ubuntu -f 'gzip -t /fsx/scratch/ILMN/' || true
pkill -u ubuntu -f 'cat -- /fsx/run_dir_mounts/ont-4coriells-' || true
pkill -u ubuntu -f 'cp -- /fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/' || true
sleep 3
echo 'after_processes'
ps -u ubuntu -f | grep -E 'hyb_only_stage_(ont|ilmn)|hybonly_stage_(ont|ilmn)|gzip -t /fsx/scratch/(ONT|ILMN)|cat -- /fsx/run_dir_mounts/ont|cp -- /fsx/run_dir_mounts/ilmn' | grep -v grep || true
echo 'before_du'
du -sh /fsx/scratch/ONT /fsx/scratch/ILMN 2>/dev/null || true
rm -rf /fsx/scratch/ONT /fsx/scratch/ILMN
sync || true
echo 'after_ls'
ls -ld /fsx/scratch/ONT /fsx/scratch/ILMN 2>/dev/null || true
echo 'df'
df -h /fsx
echo 'active_run_dir_mounts'
find /fsx/run_dir_mounts -maxdepth 1 -mindepth 1 -type d -printf '%f\t%p\n' | sort || true
printf 'finish_cleanup\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
