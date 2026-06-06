#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
mkdir -p /fsx/scratch/ONT/manifests /fsx/scratch/ONT/logs /fsx/scratch/ONT/tmp
ONT_LOG=/fsx/scratch/ONT/logs/stage_commands.log
printf 'start_ont\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$ONT_LOG"
df -h /fsx | tee -a "$ONT_LOG"
for d in /fsx/run_dir_mounts/ont-4coriells-chip1 /fsx/run_dir_mounts/ont-4coriells-chip2 /fsx/run_dir_mounts/ont-4coriells-chip3 /fsx/run_dir_mounts/ont-4coriells-chip4; do test -d "$d"; done

build_ont_sample() {
  local sample="$1" panel="$2" barcode="$3" output_name="$4" expected_count="$5"; shift 5
  local final="/fsx/scratch/ONT/${output_name}"
  local tmp="/fsx/scratch/ONT/tmp/${output_name}.tmp.$$"
  local manifest="/fsx/scratch/ONT/manifests/${sample}.sources.tsv"
  local paths="/fsx/scratch/ONT/tmp/${sample}.paths.$$"
  printf 'sample\tbarcode\tchip\tpath\tbytes\n' > "$manifest"
  : > "$paths"
  local chip root found path size
  for chip in "$@"; do
    root="/fsx/run_dir_mounts/ont-4coriells-${chip}/fastq_pass/${barcode}"
    test -d "$root"
    while IFS= read -r path; do
      size=$(stat -c '%s' "$path")
      printf '%s\t%s\t%s\t%s\t%s\n' "$sample" "$barcode" "$chip" "$path" "$size" >> "$manifest"
      printf '%s\n' "$path" >> "$paths"
    done < <(find "$root" -maxdepth 1 -type f \( -name '*.fastq.gz' -o -name '*.fq.gz' \) | sort)
  done
  found=$(wc -l < "$paths" | tr -d ' ')
  if [[ "$found" != "$expected_count" ]]; then
    printf 'ERROR\t%s\texpected_count=%s\tfound=%s\n' "$sample" "$expected_count" "$found" | tee -a "$ONT_LOG"
    exit 2
  fi
  printf 'CMD\t%s\tcat %s sources to %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$found" "$final" | tee -a "$ONT_LOG"
  rm -f "$tmp"
  while IFS= read -r path; do cat -- "$path" >> "$tmp"; done < "$paths"
  mv -f "$tmp" "$final"
  gzip -t "$final"
  printf 'DONE\t%s\t%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$sample" "$final" "$(stat -c '%s' "$final")" | tee -a "$ONT_LOG"
  rm -f "$paths"
}

build_ont_sample 'NA00232' 'SMN' 'barcode18' 'NA00232_SMN_R1_all.fastq.gz' '219' 'chip1' 'chip2' 'chip4'
build_ont_sample 'NA09677' 'SMN' 'barcode19' 'NA09677_SMN_R1_all.fastq.gz' '228' 'chip1' 'chip2' 'chip3' 'chip4'
build_ont_sample 'NA03986' 'DMPK' 'barcode20' 'NA03986_DMPK_R1_all.fastq.gz' '219' 'chip1' 'chip2' 'chip4'
build_ont_sample 'NA05164' 'DMPK' 'barcode21' 'NA05164_DMPK_R1_all.fastq.gz' '219' 'chip1' 'chip2' 'chip4'
df -h /fsx | tee -a "$ONT_LOG"
printf 'finish_ont\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$ONT_LOG"
