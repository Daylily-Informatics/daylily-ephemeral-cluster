#!/usr/bin/env bash
set -euo pipefail

session="ccv20260529r26_illumina_hg002_kitchensink_multiqc"
repo="/fsx/analysis_results/ubuntu/${session}/daylily-omics-analysis"
main_log="$repo/.snakemake/log/2026-05-30T065050.641034.snakemake.log"

echo "## main log targeted ranges"
for range in 372,436 482,522 1368,1404 1424,1450 1544,1574 3648,3674 3734,3770 4864,4894 4918,4948 5498,5510; do
  echo "### lines $range"
  sed -n "${range}p" "$main_log" | cut -c1-420
done

echo "## missing value search"
grep -RIn 'missing value for --sex\|requires an argument\|unrecognized option\|failed to write unmapped FASTQ\|no hets found\|IndexError' "$repo" 2>/dev/null | head -n 120 | cut -c1-420 || true

echo "## failed rule logs by name"
for path in \
  "$repo/logs/slurm/goleft" \
  "$repo/logs/slurm/mosdepth" \
  "$repo/logs/slurm/fastqc_subsampled" \
  "$repo/logs/slurm/seqfu" \
  "$repo/logs/slurm/read_haps_contam_identity" \
  "$repo/logs/slurm/haplocheck_vcf_contam_identity" \
  "$repo/logs/slurm/vep_concat_fofn"; do
  test -d "$path" || continue
  echo "### $path"
  find "$path" -type f -printf '%T@ %p\n' | sort -nr | head -n 4 | awk '{print $2}' | while read -r log; do
    echo "--- $log"
    tail -n 45 "$log" | cut -c1-420
  done
done
