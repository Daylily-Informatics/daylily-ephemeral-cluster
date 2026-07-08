#!/usr/bin/env bash
set -euo pipefail

cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate >/dev/null

RUN_ID=20260707T144453Z
CLUSTER=cmdcat-103-all-20260707
PROFILE=lsmc
REGION=us-west-2
S3_ROOT=s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/${RUN_ID}
LOG_ROOT=docs/plans/${RUN_ID}_success_exports
mkdir -p "${LOG_ROOT}"

export_one() {
  local command_id="$1"
  local session="$2"
  local outdir="${LOG_ROOT}/${command_id}"
  local source_path="/fsx/analysis_results/ubuntu/${session}"
  local dest="${S3_ROOT}/ubuntu/${session}/"
  mkdir -p "${outdir}"
  {
    date -u
    printf 'command_id=%s\n' "${command_id}"
    printf 'session=%s\n' "${session}"
    printf 'source_path=%s\n' "${source_path}"
    printf 'destination_s3_uri=%s\n' "${dest}"
    dyec export \
      --profile "${PROFILE}" \
      --region "${REGION}" \
      --cluster "${CLUSTER}" \
      --source-path "${source_path}" \
      --destination-s3-uri "${dest}" \
      --output-dir "${outdir}" \
      --timeout-seconds 7200
    date -u
  } 2>&1 | tee "${outdir}/export.log"
}

export_one simple-test ccv_live_simple-test_20260707T190607Z
export_one illumina_snv_alignstats ccv_live_illumina_snv_alignstats_20260707T165057Z
export_one illumina_snv_alignstats_relatedness_vep_multiqc ccv_live_illumina_snv_alignstats_relatedness_vep_multiqc_20260707T165057Z
export_one illumina_hg002_kitchensink_multiqc ccv_live_illumina_hg002_kitchensink_multiqc_20260707T185605Z
export_one illumina_pangenome_snv ccv_live_illumina_pangenome_snv_20260707T190607Z
export_one ultima_snv_alignstats ccv_live_ultima_snv_alignstats_20260707T190607Z
export_one ultima_snv_alignstats_kitchensink ccv_live_ultima_snv_alignstats_kitchensink_20260707T190607Z
export_one ultima_pangenome_snv ccv_live_ultima_pangenome_snv_20260707T190607Z
export_one ont_snv_alignstats ccv_live_ont_snv_alignstats_20260707T165057Z
export_one ont_snv_alignstats_kitchensink ccv_live_ont_snv_alignstats_kitchensink_20260707T165057Z
export_one pacbio_snv_alignstats ccv_live_pacbio_snv_alignstats_20260707T190607Z
export_one roche_snv_alignstats ccv_live_roche_snv_alignstats_20260707T190607Z
export_one hybrid_ilmn_ont_snv ccv_live_hybrid_ilmn_ont_snv_20260707T211600Z
export_one hybrid_ilmn_ont_snv_kitchensink ccv_live_hybrid_ilmn_ont_snv_kitchensink_20260707T203440Z
export_one complete_genomics_mgi_snv_concordance ccv_live_complete_genomics_mgi_snv_concordance_20260707T165057Z
export_one illumina_run_qc ccv_live_illumina_run_qc_20260707T165057Z
export_one ont_run_qc ccv_live_ont_run_qc_20260707T170900Z
export_one ultima_run_qc ccv_live_ultima_run_qc_20260707T171700Z
