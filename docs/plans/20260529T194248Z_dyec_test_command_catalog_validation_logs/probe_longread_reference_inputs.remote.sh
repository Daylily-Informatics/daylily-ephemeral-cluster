set -euo pipefail
ref=/fsx/references/genomic_data/organism_references/H_sapiens/hg38_broad/Homo_sapiens_assembly38.fasta
samtools_bin="$(find /fsx/resources/environments/conda/ubuntu -path '*/bin/samtools' -type f | head -1)"
if [[ -z "$samtools_bin" ]]; then
  echo "ERROR: no samtools binary found under /fsx/resources/environments/conda/ubuntu" >&2
  exit 2
fi
echo "samtools=$samtools_bin"
echo "reference=$ref"
for path in \
  /fsx/references/genomic_data/organism_reads_slim/cram/H_sapiens/giab/agbt_2026/ug/HG003_5x.cleaned.cram \
  /fsx/references/genomic_data/organism_reads_slim/cram/H_sapiens/giab/agbt_2026/ont/HG003_5x.cleaned.cram \
  /fsx/references/genomic_data/organism_reads_slim/bam/H_sapiens/giab/agbt_2026/pacbio/HG003_5x.cleaned.bam; do
  echo "=== $path ==="
  ls -lh "$path" "$path".* 2>/dev/null || true
  if [[ -s "$path" ]]; then
    "$samtools_bin" quickcheck -v "$path" || true
    "$samtools_bin" idxstats "$path" | awk 'NR<=8 {print} END {print "idxstats_rows=" NR}'
    "$samtools_bin" view -c -T "$ref" "$path" chr20 || true
    "$samtools_bin" view -H "$path" | awk '$1=="@SQ"{print $2; if(++n==8) exit}'
  fi
done
echo "=== nearby long-read candidates ==="
find /fsx/references/genomic_data/organism_reads_slim -type f \( -name '*HG003*cram' -o -name '*HG003*bam' \) | sort
