#!/usr/bin/env bash
set -euo pipefail

SESSION="hyb_x8_fullvars_5017_20260607T124257Z"
ANALYSIS="hybonly_hybrid_hiomr_na4_ds20x_x8_fullvars_5017_20260607T124257Z"
REPO="/fsx/analysis_results/hyb-only/${ANALYSIS}/daylily-omics-analysis"
S3_PREFIX="s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/config_snapshots/20260607T124257Z/hybrid_x8_fullvars_5017"

DRY_CMD="dy-r produce_sentdhiomr_snv_vcf produce_sentdhiomr_sv produce_sentdhiomr_cnv produce_sentdhiomr_segdup produce_sentdhiomr_mito produce_expansionhunter produce_smn12 produce_tiddit_sv_vcf produce_alignstats -p -k -j 400 --rerun-triggers mtime -n --config 'aligners=[\"sent\"]' 'dedupers=[\"dmd\"]' 'snv_callers=[\"sentdhiomr\"]' 'sv_callers=[\"tiddit\"]' 'htd_callers=[\"smn12\"]'"

tmux kill-session -t "${SESSION}" 2>/dev/null || true
rm -rf --one-file-system /fsx/analysis_results/ubuntu/config
tmux new-session -d -s "${SESSION}" bash -il

queue() {
    tmux send-keys -t "${SESSION}" -- "$1" Enter
    sleep 0.15
}

queue "cd ${REPO}"
queue "pwd; git rev-parse HEAD; git describe --tags --exact-match HEAD || true"
queue "mkdir -p config"
queue "aws s3 cp ${S3_PREFIX}/samples.tsv config/samples.tsv; echo __SAMPLES_CP_RC__:\$?"
queue "aws s3 cp ${S3_PREFIX}/units.tsv config/units.tsv; echo __UNITS_CP_RC__:\$?"
queue "printf __CONFIG_LINES__\\ ; wc -l config/samples.tsv config/units.tsv"
queue "printf __UNIT_ROWS__\\ ; awk 'END{print NR-1}' config/units.tsv"
queue "printf __FSX_STAGING_LINES__\\ ; grep -c '/fsx/staging' config/units.tsv || true"
queue "printf __DS20X_LINES__\\ ; grep -c '/fsx/analysis_results/4_nas_ds_to_20x' config/units.tsv || true"
queue "printf __ONT_MOUNT_LINES__\\ ; grep -c '/fsx/run_dir_mounts/ont-4coriells' config/units.tsv || true"
queue "cut -f1-5 config/units.tsv"
queue "source dyoainit; echo __SOURCE_DYOAINIT_RC__:\$?"
queue "dy-a slurm hg38_broad; echo __DYA_RC__:\$?"
queue "${DRY_CMD}; echo __HYB_X8_DRY_RC__:\$?"

tmux list-sessions | grep "${SESSION}"
