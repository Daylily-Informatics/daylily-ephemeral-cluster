#!/usr/bin/env bash
set -euo pipefail
echo 'before_remaining'
ps -u ubuntu -f | grep -E 'hyb_only_stage_(ont|ilmn)|hybonly_stage_(ont|ilmn)|gzip -t /fsx/scratch/(ONT|ILMN)|cat -- /fsx/run_dir_mounts/ont|cp -- /fsx/run_dir_mounts/ilmn' | grep -v grep || true
ps -u ubuntu -o pid=,args= \
  | awk '/cat -- \/fsx\/run_dir_mounts\/ont-4coriells-/ {print $1}' \
  | xargs -r kill -9
ps -u ubuntu -o pid=,args= \
  | awk '/gzip -t \/fsx\/scratch\/(ONT|ILMN)\// {print $1}' \
  | xargs -r kill -9
ps -u ubuntu -o pid=,args= \
  | awk '/cp -- \/fsx\/run_dir_mounts\/ilmn-lh01121-b23ww2nlt4-fastq\// {print $1}' \
  | xargs -r kill -9
sleep 2
echo 'after_remaining'
ps -u ubuntu -f | grep -E 'hyb_only_stage_(ont|ilmn)|hybonly_stage_(ont|ilmn)|gzip -t /fsx/scratch/(ONT|ILMN)|cat -- /fsx/run_dir_mounts/ont|cp -- /fsx/run_dir_mounts/ilmn' | grep -v grep || true
echo 'scratch_dirs'
ls -ld /fsx/scratch/ONT /fsx/scratch/ILMN 2>/dev/null || true
echo 'df'
df -h /fsx
