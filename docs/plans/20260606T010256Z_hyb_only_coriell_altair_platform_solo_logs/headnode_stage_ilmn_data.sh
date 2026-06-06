#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
mkdir -p /fsx/scratch/ILMN/logs /fsx/scratch/ILMN/tmp
ILMN_LOG=/fsx/scratch/ILMN/logs/stage_commands.log
printf 'start_ilmn\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$ILMN_LOG"
df -h /fsx | tee -a "$ILMN_LOG"
test -d /fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq

printf 'sample\tsource\tdest\tbytes\n' > /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-a_S1_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-a_S1_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG001-a_S1_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-a_S1_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG001-a_S1_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG001-a_S1_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG001-a_S1_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG001-a_S1_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG001' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-a_S1_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG001-a_S1_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG001-a_S1_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-a_S1_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-a_S1_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG001-a_S1_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-a_S1_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG001-a_S1_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG001-a_S1_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG001-a_S1_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG001-a_S1_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG001' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-a_S1_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG001-a_S1_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG001-a_S1_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-b_S2_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-b_S2_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG001-b_S2_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-b_S2_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG001-b_S2_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG001-b_S2_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG001-b_S2_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG001-b_S2_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG001' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-b_S2_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG001-b_S2_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG001-b_S2_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-b_S2_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-b_S2_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG001-b_S2_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-b_S2_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG001-b_S2_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG001-b_S2_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG001-b_S2_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG001-b_S2_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG001' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-b_S2_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG001-b_S2_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG001-b_S2_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-c_S3_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-c_S3_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG001-c_S3_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-c_S3_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG001-c_S3_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG001-c_S3_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG001-c_S3_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG001-c_S3_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG001' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-c_S3_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG001-c_S3_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG001-c_S3_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-c_S3_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-c_S3_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG001-c_S3_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-c_S3_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG001-c_S3_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG001-c_S3_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG001-c_S3_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG001-c_S3_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG001' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG001-c_S3_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG001-c_S3_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG001-c_S3_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-a_S4_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-a_S4_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG002-a_S4_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-a_S4_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG002-a_S4_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG002-a_S4_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG002-a_S4_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG002-a_S4_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG002' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-a_S4_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG002-a_S4_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG002-a_S4_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-a_S4_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-a_S4_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG002-a_S4_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-a_S4_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG002-a_S4_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG002-a_S4_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG002-a_S4_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG002-a_S4_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG002' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-a_S4_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG002-a_S4_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG002-a_S4_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-b_S5_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-b_S5_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG002-b_S5_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-b_S5_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG002-b_S5_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG002-b_S5_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG002-b_S5_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG002-b_S5_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG002' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-b_S5_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG002-b_S5_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG002-b_S5_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-b_S5_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-b_S5_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG002-b_S5_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-b_S5_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG002-b_S5_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG002-b_S5_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG002-b_S5_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG002-b_S5_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG002' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-b_S5_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG002-b_S5_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG002-b_S5_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-c_S6_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-c_S6_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG002-c_S6_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-c_S6_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG002-c_S6_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG002-c_S6_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG002-c_S6_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG002-c_S6_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG002' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-c_S6_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG002-c_S6_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG002-c_S6_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-c_S6_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-c_S6_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG002-c_S6_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-c_S6_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG002-c_S6_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG002-c_S6_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG002-c_S6_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG002-c_S6_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG002' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG002-c_S6_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG002-c_S6_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG002-c_S6_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-a_S7_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-a_S7_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG003-a_S7_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-a_S7_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG003-a_S7_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG003-a_S7_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG003-a_S7_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG003-a_S7_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG003' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-a_S7_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG003-a_S7_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG003-a_S7_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-a_S7_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-a_S7_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG003-a_S7_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-a_S7_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG003-a_S7_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG003-a_S7_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG003-a_S7_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG003-a_S7_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG003' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-a_S7_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG003-a_S7_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG003-a_S7_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-b_S8_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-b_S8_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG003-b_S8_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-b_S8_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG003-b_S8_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG003-b_S8_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG003-b_S8_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG003-b_S8_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG003' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-b_S8_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG003-b_S8_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG003-b_S8_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-b_S8_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-b_S8_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG003-b_S8_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-b_S8_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG003-b_S8_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG003-b_S8_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG003-b_S8_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG003-b_S8_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG003' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-b_S8_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG003-b_S8_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG003-b_S8_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-c_S9_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-c_S9_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG003-c_S9_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-c_S9_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG003-c_S9_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG003-c_S9_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG003-c_S9_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG003-c_S9_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG003' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-c_S9_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG003-c_S9_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG003-c_S9_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-c_S9_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-c_S9_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG003-c_S9_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-c_S9_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG003-c_S9_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG003-c_S9_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG003-c_S9_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG003-c_S9_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG003' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG003-c_S9_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG003-c_S9_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG003-c_S9_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-a_S10_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-a_S10_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG004-a_S10_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-a_S10_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG004-a_S10_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG004-a_S10_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG004-a_S10_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG004-a_S10_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG004' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-a_S10_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG004-a_S10_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG004-a_S10_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-a_S10_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-a_S10_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG004-a_S10_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-a_S10_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG004-a_S10_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG004-a_S10_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG004-a_S10_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG004-a_S10_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG004' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-a_S10_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG004-a_S10_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG004-a_S10_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-b_S11_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-b_S11_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG004-b_S11_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-b_S11_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG004-b_S11_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG004-b_S11_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG004-b_S11_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG004-b_S11_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG004' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-b_S11_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG004-b_S11_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG004-b_S11_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-b_S11_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-b_S11_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG004-b_S11_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-b_S11_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG004-b_S11_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG004-b_S11_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG004-b_S11_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG004-b_S11_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG004' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-b_S11_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG004-b_S11_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG004-b_S11_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-c_S12_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-c_S12_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG004-c_S12_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-c_S12_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG004-c_S12_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG004-c_S12_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG004-c_S12_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG004-c_S12_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG004' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-c_S12_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG004-c_S12_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG004-c_S12_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-c_S12_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-c_S12_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG004-c_S12_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-c_S12_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG004-c_S12_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG004-c_S12_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG004-c_S12_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG004-c_S12_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG004' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG004-c_S12_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG004-c_S12_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG004-c_S12_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-a_S13_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-a_S13_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG005-a_S13_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-a_S13_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG005-a_S13_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG005-a_S13_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG005-a_S13_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG005-a_S13_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG005' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-a_S13_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG005-a_S13_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG005-a_S13_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-a_S13_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-a_S13_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG005-a_S13_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-a_S13_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG005-a_S13_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG005-a_S13_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG005-a_S13_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG005-a_S13_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG005' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-a_S13_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG005-a_S13_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG005-a_S13_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-b_S14_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-b_S14_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG005-b_S14_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-b_S14_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG005-b_S14_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG005-b_S14_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG005-b_S14_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG005-b_S14_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG005' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-b_S14_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG005-b_S14_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG005-b_S14_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-b_S14_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-b_S14_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG005-b_S14_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-b_S14_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG005-b_S14_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG005-b_S14_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG005-b_S14_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG005-b_S14_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG005' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-b_S14_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG005-b_S14_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG005-b_S14_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-c_S15_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-c_S15_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG005-c_S15_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-c_S15_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG005-c_S15_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG005-c_S15_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG005-c_S15_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG005-c_S15_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG005' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-c_S15_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG005-c_S15_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG005-c_S15_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-c_S15_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-c_S15_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG005-c_S15_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-c_S15_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG005-c_S15_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG005-c_S15_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG005-c_S15_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG005-c_S15_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG005' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG005-c_S15_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG005-c_S15_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG005-c_S15_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-a_S16_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-a_S16_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG006-a_S16_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-a_S16_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG006-a_S16_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG006-a_S16_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG006-a_S16_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG006-a_S16_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG006' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-a_S16_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG006-a_S16_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG006-a_S16_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-a_S16_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-a_S16_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG006-a_S16_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-a_S16_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG006-a_S16_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG006-a_S16_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG006-a_S16_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG006-a_S16_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG006' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-a_S16_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG006-a_S16_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG006-a_S16_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-b_S17_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-b_S17_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG006-b_S17_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-b_S17_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG006-b_S17_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG006-b_S17_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG006-b_S17_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG006-b_S17_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG006' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-b_S17_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG006-b_S17_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG006-b_S17_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-b_S17_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-b_S17_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG006-b_S17_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-b_S17_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG006-b_S17_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG006-b_S17_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG006-b_S17_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG006-b_S17_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG006' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-b_S17_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG006-b_S17_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG006-b_S17_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-c_S18_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-c_S18_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG006-c_S18_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-c_S18_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG006-c_S18_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG006-c_S18_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG006-c_S18_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG006-c_S18_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG006' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-c_S18_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG006-c_S18_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG006-c_S18_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-c_S18_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-c_S18_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG006-c_S18_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-c_S18_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG006-c_S18_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG006-c_S18_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG006-c_S18_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG006-c_S18_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG006' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG006-c_S18_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG006-c_S18_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG006-c_S18_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-a_S19_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-a_S19_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG007-a_S19_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-a_S19_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG007-a_S19_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG007-a_S19_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG007-a_S19_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG007-a_S19_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG007' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-a_S19_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG007-a_S19_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG007-a_S19_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-a_S19_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-a_S19_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG007-a_S19_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-a_S19_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG007-a_S19_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG007-a_S19_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG007-a_S19_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG007-a_S19_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG007' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-a_S19_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG007-a_S19_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG007-a_S19_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-b_S20_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-b_S20_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG007-b_S20_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-b_S20_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG007-b_S20_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG007-b_S20_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG007-b_S20_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG007-b_S20_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG007' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-b_S20_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG007-b_S20_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG007-b_S20_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-b_S20_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-b_S20_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG007-b_S20_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-b_S20_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG007-b_S20_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG007-b_S20_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG007-b_S20_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG007-b_S20_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG007' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-b_S20_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG007-b_S20_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG007-b_S20_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-c_S21_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-c_S21_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG007-c_S21_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-c_S21_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG007-c_S21_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG007-c_S21_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG007-c_S21_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG007-c_S21_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG007' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-c_S21_R1_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG007-c_S21_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG007-c_S21_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-c_S21_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-c_S21_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG007-c_S21_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-c_S21_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/Altair-HG007-c_S21_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/Altair-HG007-c_S21_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/Altair-HG007-c_S21_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/Altair-HG007-c_S21_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'HG007' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/Altair-HG007-c_S21_R2_001.fastq.gz' '/fsx/scratch/ILMN/Altair-HG007-c_S21_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/Altair-HG007-c_S21_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA00232-SMN_S46_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA00232-SMN_S46_R1_001.fastq.gz' '/fsx/scratch/ILMN/NA00232-SMN_S46_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA00232-SMN_S46_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/NA00232-SMN_S46_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/NA00232-SMN_S46_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/NA00232-SMN_S46_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/NA00232-SMN_S46_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'NA00232' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA00232-SMN_S46_R1_001.fastq.gz' '/fsx/scratch/ILMN/NA00232-SMN_S46_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/NA00232-SMN_S46_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA00232-SMN_S46_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA00232-SMN_S46_R2_001.fastq.gz' '/fsx/scratch/ILMN/NA00232-SMN_S46_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA00232-SMN_S46_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/NA00232-SMN_S46_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/NA00232-SMN_S46_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/NA00232-SMN_S46_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/NA00232-SMN_S46_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'NA00232' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA00232-SMN_S46_R2_001.fastq.gz' '/fsx/scratch/ILMN/NA00232-SMN_S46_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/NA00232-SMN_S46_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA03986-DMPK_S48_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA03986-DMPK_S48_R1_001.fastq.gz' '/fsx/scratch/ILMN/NA03986-DMPK_S48_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA03986-DMPK_S48_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/NA03986-DMPK_S48_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/NA03986-DMPK_S48_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/NA03986-DMPK_S48_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/NA03986-DMPK_S48_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'NA03986' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA03986-DMPK_S48_R1_001.fastq.gz' '/fsx/scratch/ILMN/NA03986-DMPK_S48_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/NA03986-DMPK_S48_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA03986-DMPK_S48_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA03986-DMPK_S48_R2_001.fastq.gz' '/fsx/scratch/ILMN/NA03986-DMPK_S48_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA03986-DMPK_S48_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/NA03986-DMPK_S48_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/NA03986-DMPK_S48_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/NA03986-DMPK_S48_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/NA03986-DMPK_S48_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'NA03986' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA03986-DMPK_S48_R2_001.fastq.gz' '/fsx/scratch/ILMN/NA03986-DMPK_S48_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/NA03986-DMPK_S48_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA05164-DMPK_S49_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA05164-DMPK_S49_R1_001.fastq.gz' '/fsx/scratch/ILMN/NA05164-DMPK_S49_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA05164-DMPK_S49_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/NA05164-DMPK_S49_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/NA05164-DMPK_S49_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/NA05164-DMPK_S49_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/NA05164-DMPK_S49_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'NA05164' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA05164-DMPK_S49_R1_001.fastq.gz' '/fsx/scratch/ILMN/NA05164-DMPK_S49_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/NA05164-DMPK_S49_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA05164-DMPK_S49_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA05164-DMPK_S49_R2_001.fastq.gz' '/fsx/scratch/ILMN/NA05164-DMPK_S49_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA05164-DMPK_S49_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/NA05164-DMPK_S49_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/NA05164-DMPK_S49_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/NA05164-DMPK_S49_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/NA05164-DMPK_S49_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'NA05164' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA05164-DMPK_S49_R2_001.fastq.gz' '/fsx/scratch/ILMN/NA05164-DMPK_S49_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/NA05164-DMPK_S49_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA09677-SMN_S47_R1_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA09677-SMN_S47_R1_001.fastq.gz' '/fsx/scratch/ILMN/NA09677-SMN_S47_R1_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA09677-SMN_S47_R1_001.fastq.gz' '/fsx/scratch/ILMN/tmp/NA09677-SMN_S47_R1_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/NA09677-SMN_S47_R1_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/NA09677-SMN_S47_R1_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/NA09677-SMN_S47_R1_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'NA09677' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA09677-SMN_S47_R1_001.fastq.gz' '/fsx/scratch/ILMN/NA09677-SMN_S47_R1_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/NA09677-SMN_S47_R1_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
test -s '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA09677-SMN_S47_R2_001.fastq.gz'
printf 'CMD\t%s\tcp -- %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA09677-SMN_S47_R2_001.fastq.gz' '/fsx/scratch/ILMN/NA09677-SMN_S47_R2_001.fastq.gz' | tee -a "$ILMN_LOG"
cp -- '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA09677-SMN_S47_R2_001.fastq.gz' '/fsx/scratch/ILMN/tmp/NA09677-SMN_S47_R2_001.fastq.gz.tmp.$$'
mv -f '/fsx/scratch/ILMN/tmp/NA09677-SMN_S47_R2_001.fastq.gz.tmp.$$' '/fsx/scratch/ILMN/NA09677-SMN_S47_R2_001.fastq.gz'
gzip -t '/fsx/scratch/ILMN/NA09677-SMN_S47_R2_001.fastq.gz'
printf '%s\t%s\t%s\t%s\n' 'NA09677' '/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA09677-SMN_S47_R2_001.fastq.gz' '/fsx/scratch/ILMN/NA09677-SMN_S47_R2_001.fastq.gz' "$(stat -c '%s' '/fsx/scratch/ILMN/NA09677-SMN_S47_R2_001.fastq.gz')" >> /fsx/scratch/ILMN/logs/source_manifest.tsv
df -h /fsx | tee -a "$ILMN_LOG"
printf 'finish_ilmn\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$ILMN_LOG"
