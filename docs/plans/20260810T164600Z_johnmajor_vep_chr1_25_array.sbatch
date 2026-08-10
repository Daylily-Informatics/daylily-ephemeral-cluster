#!/usr/bin/env bash
#SBATCH --job-name=vep_sqjx8366_chr
#SBATCH --partition=i96nvme
#SBATCH --cpus-per-task=1
#SBATCH --time=1-00:00:00
#SBATCH --array=1-25%25
#SBATCH --output=/fsx/tmp/vep_johnmajor_sqjx8366_chr1_25_20260810T164600Z/logs/chr%a.%j.out
#SBATCH --error=/fsx/tmp/vep_johnmajor_sqjx8366_chr1_25_20260810T164600Z/logs/chr%a.%j.err

set -euo pipefail
RUN=/fsx/tmp/vep_johnmajor_sqjx8366_chr1_25_20260810T164600Z
INPUT=/fsx/tmp/vep_johnmajor_sqjx8366_20260810T132200Z/input.vcf.gz
CHR=${SLURM_ARRAY_TASK_ID}
OUT="$RUN/shards/chr${CHR}.vep114.GRCh38.vcf.gz"
export SINGULARITY_CACHEDIR="${TMPDIR:-/tmp}/singularity-cache"
export APPTAINER_CACHEDIR="$SINGULARITY_CACHEDIR"
mkdir -p "$SINGULARITY_CACHEDIR"
gzip -dc "$INPUT" | awk -v chr="$CHR" 'BEGIN { FS=OFS="\t" } /^#/ || $1 == chr' | \
  singularity exec --bind /fsx:/fsx docker://ensemblorg/ensembl-vep:release_114.2 \
  vep --offline --cache --dir_cache /fsx/references/runtime_assets/tool_specific_resources/vep \
      --species homo_sapiens --assembly GRCh38 --format vcf --vcf --input_file STDIN \
      --output_file "$OUT" --compress_output bgzip --force_overwrite --fork 1 --allow_non_variant
test -s "$OUT"
