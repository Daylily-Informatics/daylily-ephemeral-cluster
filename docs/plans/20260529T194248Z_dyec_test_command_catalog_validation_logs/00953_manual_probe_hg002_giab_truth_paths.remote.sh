
set -euo pipefail
base=/fsx/references/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv
want=$base/v4.2.1/HG002/giabHCv5q
printf 'want=%s\n' "$want"
ls -lah "$base" || true
ls -lah "$base/v4.2.1" || true
ls -lah "$base/v4.2.1/HG002" || true
ls -lah "$want" || true
printf '\nHG002 candidate files under giab snv:\n'
find "$base" -maxdepth 6 -type f \( -iname '*HG002*.vcf.gz' -o -iname '*HG002*.vcf.gz.tbi' -o -iname '*HG002*.bed' \) -printf '%p\t%s\n' | sort | head -n 200
printf '\ngiabHCv5q paths:\n'
find "$base" -maxdepth 8 -path '*giabHCv5q*' -printf '%y\t%p\t%s\n' | sort | head -n 200
