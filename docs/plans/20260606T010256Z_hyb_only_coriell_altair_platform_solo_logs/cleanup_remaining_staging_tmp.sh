#!/usr/bin/env bash
set -euo pipefail
printf 'start_tmp_cleanup\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo 'before_processes'
ps -u ubuntu -f | grep -E 'hyb_only_stage_(ont|ilmn)|hybonly_stage_(ont|ilmn)|gzip -t /fsx/scratch/(ONT|ILMN)|cat -- /fsx/run_dir_mounts/ont|cp -- /fsx/run_dir_mounts/ilmn' | grep -v grep || true
echo 'before_tmp_matches'
find /fsx/scratch -maxdepth 4 \( \
  -path '/fsx/scratch/ONT' -o \
  -path '/fsx/scratch/ONT/*' -o \
  -path '/fsx/scratch/ILMN' -o \
  -path '/fsx/scratch/ILMN/*' -o \
  -name 'NA*_R1_all.fastq.gz.tmp.*' -o \
  -name 'Altair-HG*_R[12]_001.fastq.gz.tmp.*' -o \
  -name 'NA*-SMN_S*_R[12]_001.fastq.gz.tmp.*' -o \
  -name 'NA*-DMPK_S*_R[12]_001.fastq.gz.tmp.*' \
\) -print 2>/dev/null || true
rm -rf /fsx/scratch/ONT /fsx/scratch/ILMN
find /fsx/scratch -maxdepth 4 -type f \( \
  -name 'NA*_R1_all.fastq.gz.tmp.*' -o \
  -name 'Altair-HG*_R[12]_001.fastq.gz.tmp.*' -o \
  -name 'NA*-SMN_S*_R[12]_001.fastq.gz.tmp.*' -o \
  -name 'NA*-DMPK_S*_R[12]_001.fastq.gz.tmp.*' \
\) -delete 2>/dev/null || true
sync || true
echo 'after_tmp_matches'
find /fsx/scratch -maxdepth 4 \( \
  -path '/fsx/scratch/ONT' -o \
  -path '/fsx/scratch/ONT/*' -o \
  -path '/fsx/scratch/ILMN' -o \
  -path '/fsx/scratch/ILMN/*' -o \
  -name 'NA*_R1_all.fastq.gz.tmp.*' -o \
  -name 'Altair-HG*_R[12]_001.fastq.gz.tmp.*' -o \
  -name 'NA*-SMN_S*_R[12]_001.fastq.gz.tmp.*' -o \
  -name 'NA*-DMPK_S*_R[12]_001.fastq.gz.tmp.*' \
\) -print 2>/dev/null || true
echo 'after_processes'
ps -u ubuntu -f | grep -E 'hyb_only_stage_(ont|ilmn)|hybonly_stage_(ont|ilmn)|gzip -t /fsx/scratch/(ONT|ILMN)|cat -- /fsx/run_dir_mounts/ont|cp -- /fsx/run_dir_mounts/ilmn' | grep -v grep || true
echo 'df'
df -h /fsx
printf 'finish_tmp_cleanup\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
