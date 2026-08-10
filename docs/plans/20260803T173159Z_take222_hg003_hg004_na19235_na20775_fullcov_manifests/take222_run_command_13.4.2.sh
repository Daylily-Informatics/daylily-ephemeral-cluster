#!/usr/bin/env bash

if [[ $# -ne 1 || ( "$1" != "dry" && "$1" != "live" ) ]]; then
  echo "usage: source take222_run_command_13.4.2.sh <dry|live>" >&2
  return 64 2>/dev/null || exit 64
fi
if [[ "${DAY_PROJECT:-}" != "RnD" || "${DAYLILY_COST_CENTER:-}" != "RnD" ]]; then
  echo "Take222 requires DAY_PROJECT=RnD and DAYLILY_COST_CENTER=RnD" >&2
  return 65 2>/dev/null || exit 65
fi
if [[ "${SEQONE_DELIVERY_BATCH_ID:-}" != "take222" ]]; then
  echo "Take222 requires SEQONE_DELIVERY_BATCH_ID=take222" >&2
  return 66 2>/dev/null || exit 66
fi

take222_mode="$1"
take222_log="/fsx/analysis_results/preval-hiomr2/take222/daylily-omics-analysis/take222_hg003_hg004_na19235_na20775_fullcov_13.4.2_${take222_mode}_20260803.log"
take222_rc="/home/ubuntu/take222_hg003_hg004_na19235_na20775_fullcov_13.4.2_${take222_mode}_20260803.rc"
take222_extra=()
if [[ "$take222_mode" == "dry" ]]; then
  take222_extra=(-n)
fi

DAY_CONTAINERIZED=true dy-r \
  produce_sentdhiomr2_kitchensink \
  produce_sentdhiomr2_nicu_research \
  produce_sentdhiomr2_jasmine_sharded_per_sample \
  produce_sentdhiomr2_inflection_analytical_package \
  results/day/hg38/reports/DAY_final_multiqc.html \
  --configfile config/hiomr2_take222_hg003_hg004_na19235_na20775_fullcov.yaml \
  --config \
    genome_build=hg38 \
    'aligners=["sentmm2ont"]' \
    'dedupers=["na"]' \
    'snv_callers=["sentdhiomr2"]' \
    'sv_callers=[]' \
    'htd_callers=["smn12"]' \
    hiomr2_inflection_package_mode=analytical \
    use_fq_data_starting_hrs=0 \
    use_fq_data_up_to_hrs=25 \
    seqone_delivery_batch_id=take222 \
  -j 444 -p -T 1 -k --rerun-triggers mtime \
  "${take222_extra[@]}" \
  >"$take222_log" 2>&1
take222_status=$?
printf 'TAKE222_%s_RC=%s\n' "${take222_mode^^}" "$take222_status" >"$take222_rc"
unset take222_extra take222_log take222_mode take222_rc take222_status
return 0 2>/dev/null || exit 0
