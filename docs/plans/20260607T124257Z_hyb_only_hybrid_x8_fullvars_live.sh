#!/usr/bin/env bash
set -euo pipefail

SESSION="hyb_x8_fullvars_5017_20260607T124257Z"

LIVE_CMD="dy-r produce_sentdhiomr_snv_vcf produce_sentdhiomr_sv produce_sentdhiomr_cnv produce_sentdhiomr_segdup produce_sentdhiomr_mito produce_expansionhunter produce_smn12 produce_tiddit_sv_vcf produce_alignstats -p -k -j 400 --rerun-triggers mtime --config 'aligners=[\"sent\"]' 'dedupers=[\"dmd\"]' 'snv_callers=[\"sentdhiomr\"]' 'sv_callers=[\"tiddit\"]' 'htd_callers=[\"smn12\"]'"

tmux send-keys -t "${SESSION}" -- "${LIVE_CMD}; echo __HYB_X8_LIVE_RC__:\$?" Enter
tmux capture-pane -p -t "${SESSION}" | tail -60
