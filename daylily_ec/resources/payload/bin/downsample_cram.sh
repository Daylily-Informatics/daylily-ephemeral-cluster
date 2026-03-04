#!/bin/bash

# Usage: ./downsample_cram.sh <seed> <downsample_frac> <ref.fa> <input.cram> <output.cram> <threads>

set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "Usage: $0 <seed> <downsample_frac> <ref.fa> <input.cram> <output.cram> <threads>"
  exit 0
fi

if [[ "$#" -ne 6 ]]; then
  echo "Usage: $0 <seed> <downsample_frac> <ref.fa> <input.cram> <output.cram> <threads>"
  exit 1
fi

SEED=$1
DOWNSAMPLE_FRAC=$2
REF_FA=$3
INPUT_CRAM=$4
OUTPUT_CRAM=$5
THREADS=$6

# Check for samtools availability
if ! command -v samtools &> /dev/null; then
  echo "Error: samtools is not installed or not in PATH."
  exit 1
fi

# Downsample the CRAM file
echo "Downsampling ${INPUT_CRAM} to ${OUTPUT_CRAM} at fraction ${DOWNSAMPLE_FRAC} (seed ${SEED})..."
samtools view -@ "${THREADS}" -s "${SEED}.${DOWNSAMPLE_FRAC}" -C -T "${REF_FA}" -o "${OUTPUT_CRAM}" "${INPUT_CRAM}"

# Index the new CRAM file
echo "Indexing ${OUTPUT_CRAM}..."
samtools index -@ "${THREADS}" "${OUTPUT_CRAM}"

echo "Done. Output written to ${OUTPUT_CRAM}" 
