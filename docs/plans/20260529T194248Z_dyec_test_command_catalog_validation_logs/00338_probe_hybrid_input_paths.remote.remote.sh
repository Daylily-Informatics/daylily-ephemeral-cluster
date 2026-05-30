#!/usr/bin/env bash
set -euo pipefail

paths=(
  /fsx/references/genomic_data/organism_reads_slim/cram/H_sapiens/giab/agbt_2026/ont/HG003_5x.cleaned.cram
  /fsx/references/genomic_data/organism_reads_slim/cram/H_sapiens/giab/agbt_2026/ont/HG003_5x.cleaned.cram.crai
  /fsx/references/genomic_data/organism_reads_slim/cram/H_sapiens/giab/agbt_2026/ug/HG003_5x.cleaned.cram
  /fsx/references/genomic_data/organism_reads_slim/cram/H_sapiens/giab/agbt_2026/ug/HG003_5x.cleaned.cram.crai
)

echo "=== path stats ==="
for path in "${paths[@]}"; do
  if [[ -e "$path" ]]; then
    stat -c '%n size=%s mode=%A user=%U group=%G target=%N' "$path"
  else
    echo "MISSING $path"
  fi
done

echo "=== quickcheck ==="
for path in "${paths[@]}"; do
  [[ "$path" == *.cram ]] || continue
  if samtools quickcheck "$path"; then
    echo "OK $path"
  else
    echo "FAIL $path"
  fi
done

echo "=== analysis manifests ==="
for analysis in \
  ccv20260529r7_hybrid_ilmn_ont_snv \
  ccv20260529r7_hybrid_ilmn_ont_snv_kitchensink \
  ccv20260529r9_hybrid_ultima_ont_snv
do
  repo="/fsx/analysis_results/ubuntu/${analysis}/daylily-omics-analysis"
  echo "--- $analysis ---"
  if [[ -d "$repo" ]]; then
    sed -n '1,4p' "$repo/config/samples.tsv" || true
    sed -n '1,4p' "$repo/config/units.tsv" || true
  else
    echo "MISSING_REPO $repo"
  fi
done

echo "=== live slurm ==="
squeue -o '%i|%T|%M|%D|%R|%j' || true
