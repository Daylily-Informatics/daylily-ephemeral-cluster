#!/usr/bin/env bash
set -euo pipefail

printf 'SECTION\tfield1\tfield2\tfield3\tfield4\tfield5\tfield6\n'
printf 'META\tdate_utc\t%s\t\t\t\t\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'META\thostname\t%s\t\t\t\t\n' "$(hostname)"
printf 'META\twhoami\t%s\t\t\t\t\n' "$(whoami)"
df -h /fsx | awk 'NR==1 {print "DF\t"$0} NR>1 {print "DF\t"$0}'

declare -A ONT_SAMPLE_BY_BARCODE=(
  [barcode18]=NA00232
  [barcode19]=NA09677
  [barcode20]=NA03986
  [barcode21]=NA05164
)

for chip in chip1 chip2 chip3 chip4; do
  root="/fsx/run_dir_mounts/ont-4coriells-${chip}/fastq_pass"
  if [[ ! -d "${root}" ]]; then
    printf 'MISSING_ONT_ROOT\t%s\t%s\t\t\t\t\n' "${chip}" "${root}"
    continue
  fi
  for barcode in barcode18 barcode19 barcode20 barcode21; do
    sample="${ONT_SAMPLE_BY_BARCODE[$barcode]}"
    dir="${root}/${barcode}"
    if [[ ! -d "${dir}" ]]; then
      printf 'MISSING_ONT_BARCODE\t%s\t%s\t%s\t%s\t\t\n' "${chip}" "${barcode}" "${sample}" "${dir}"
      continue
    fi
    find "${dir}" -type f \( -name '*.fastq.gz' -o -name '*.fq.gz' \) -printf "ONT\t${chip}\t${barcode}\t${sample}\t%p\t%s\n" | sort
  done
done

ilmn_root="/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq"
if [[ ! -d "${ilmn_root}" ]]; then
  printf 'MISSING_ILMN_ROOT\t%s\t\t\t\t\t\n' "${ilmn_root}"
else
  find "${ilmn_root}" -type f \( -name '*.fastq.gz' -o -name '*.fq.gz' \) -printf '%f\t%p\t%s\n' \
    | awk -F '\t' '
      $1 ~ /NA00232-SMN/ || $1 ~ /NA09677-SMN/ || $1 ~ /NA03986-DMPK/ || $1 ~ /NA05164-DMPK/ || $1 ~ /HG003/ {
        print "ILMN\t"$1"\t"$2"\t"$3"\t\t"
      }' \
    | sort
fi
