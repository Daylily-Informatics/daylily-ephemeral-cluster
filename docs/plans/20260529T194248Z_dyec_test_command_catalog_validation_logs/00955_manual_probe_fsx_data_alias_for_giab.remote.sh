
set -euo pipefail
ls -ld /fsx /fsx/data /fsx/references || true
for p in \
  /fsx/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v5.0q/HG002/giabHCv5q/HG002_GRCh38_v5.0q_smvar.vcf.gz \
  /fsx/references/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v5.0q/HG002/giabHCv5q/HG002_GRCh38_v5.0q_smvar.vcf.gz \
  /fsx/references/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG002/giabHCv5q/HG002.vcf.gz; do
  printf '\npath=%s\n' "$p"
  if [ -e "$p" ]; then stat -Lc '%F %s %n -> %N' "$p"; else echo MISSING; fi
  ls -l "$p" || true
done
