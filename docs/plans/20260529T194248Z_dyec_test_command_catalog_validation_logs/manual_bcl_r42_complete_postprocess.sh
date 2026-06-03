#!/usr/bin/env bash
set -euo pipefail

analysis_root="/fsx/analysis_results/ubuntu/ccv20260530r42_illumina_bclconvert/daylily-omics-analysis"
run_id="20260514_LH01106_0009_B23TVLGLT4"
bcl_root="results/runs/${run_id}/bclconvert"

echo "time=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
cd "$analysis_root"

echo "python=$(command -v python)"
python --version
echo "working_dir=$PWD"

mkdir -p "${bcl_root}/metrics"
python workflow/scripts/bclconvert_metrics_summary.py \
  --report-dir "${bcl_root}/fastqs/Reports" \
  --demux-out "${bcl_root}/metrics/demultiplex_stats.tsv" \
  --unknown-out "${bcl_root}/metrics/unknown_barcodes.tsv" \
  --hopping-out "${bcl_root}/metrics/index_hopping.tsv" \
  --fastq-manifest-out "${bcl_root}/metrics/fastq_manifest.tsv" \
  --rollup-json-out "${bcl_root}/metrics/rollup.json"

python workflow/scripts/bclconvert_fastq_list_to_units.py \
  --fastq-list "${bcl_root}/fastqs/Reports/fastq_list.csv" \
  --sample-sheet-rows "${bcl_root}/tables/samplesheet_rows.tsv" \
  --run-id "$run_id" \
  --libprep PCR-FREE \
  --seq-vendor ILMN \
  --seq-platform-override "" \
  --units-out "${bcl_root}/tables/generated.units.tsv"

echo "postprocess outputs:"
ls -lah "${bcl_root}/metrics" "${bcl_root}/tables"
echo "generated_units_head:"
head -5 "${bcl_root}/tables/generated.units.tsv"
echo "metrics_manifest_head:"
head -5 "${bcl_root}/metrics/fastq_manifest.tsv"
