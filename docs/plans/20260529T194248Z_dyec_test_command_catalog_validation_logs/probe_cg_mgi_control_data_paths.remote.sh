set -euo pipefail
echo "host=$(hostname)"
date -Is
for path in \
  /fsx/control_data \
  /fsx/references \
  /fsx/references/genomic_data/organism_reads/H_sapiens/giab/MGI/mgi_reads \
  /fsx/data/genomic_data/organism_reads/H_sapiens/giab/MGI/mgi_reads \
  /fsx/staging/staged_external_sequencing_data/remote_stage_20260530T065816Z_a3c70c2e
do
  echo "== $path =="
  if [[ -e "$path" || -L "$path" ]]; then
    ls -ld "$path"
    find "$path" -maxdepth 1 -type f -name 'ML150002521_L01_UDB-*' -printf '%f\t%s\n' 2>/dev/null | sort | head -n 40
  else
    echo "missing"
  fi
done
echo "== staged samples paths =="
find /fsx/staging/staged_external_sequencing_data/remote_stage_20260530T065816Z_a3c70c2e -maxdepth 1 -name '*_samples.tsv' -print -exec sed -n '1,3p' {} \;
echo "== staged units paths =="
find /fsx/staging/staged_external_sequencing_data/remote_stage_20260530T065816Z_a3c70c2e -maxdepth 1 -name '*_units.tsv' -print -exec sed -n '1,6p' {} \;
