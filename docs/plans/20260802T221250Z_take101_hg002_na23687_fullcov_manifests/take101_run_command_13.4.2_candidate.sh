#!/usr/bin/env bash

if [[ $# -ne 1 || ( "$1" != "dry" && "$1" != "live" ) ]]; then
  echo "usage: source take101_run_command_13.4.2_candidate.sh <dry|live>" >&2
  return 64 2>/dev/null || exit 64
fi
if [[ "${DAY_PROJECT:-}" != "RnD" || "${DAYLILY_COST_CENTER:-}" != "RnD" ]]; then
  echo "Take101 requires DAY_PROJECT=RnD and DAYLILY_COST_CENTER=RnD" >&2
  return 65 2>/dev/null || exit 65
fi

take101_mode="$1"
take101_log="/fsx/analysis_results/preval-hiomr2/take101/daylily-omics-analysis/take101_hg002_na23687_fullcov_13.4.2_candidate_${take101_mode}_20260802.log"
take101_rc="/home/ubuntu/take101_hg002_na23687_fullcov_13.4.2_candidate_${take101_mode}_20260802.rc"
take101_extra=()
if [[ "$take101_mode" == "dry" ]]; then
  take101_extra=(-n)
fi

dy-r \
  produce_sentdhiomr2_kitchensink \
  produce_sentdhiomr2_nicu_research \
  produce_sentdhiomr2_jasmine_sentieon_validation \
  produce_sentdhiomr2_jasmine_sharded_per_sample \
  produce_sentdhiomr2_truvari_sv_benchmarks \
  produce_sentdhiomr2_jasmine_le50_rtg_concordance \
  produce_sentdhiomr2_inflection_analytical_package \
  results/day/hg38/reports/DAY_final_multiqc.html \
  --configfile config/hiomr2_take101_hg002_na23687_fullcov.yaml \
  --config \
    genome_build=hg38 \
    'aligners=["sentmm2ont"]' \
    'dedupers=["na"]' \
    'snv_callers=["sentdhiomr2"]' \
    'sv_callers=[]' \
    'htd_callers=["smn12"]' \
    use_fq_data_starting_hrs=0 \
    use_fq_data_up_to_hrs=25 \
  -j 333 -p -k -T 1 --rerun-triggers mtime \
  "${take101_extra[@]}" \
  >"$take101_log" 2>&1
take101_status=$?
printf 'TAKE101_%s_RC=%s\n' "${take101_mode^^}" "$take101_status" >"$take101_rc"
unset take101_extra take101_log take101_mode take101_rc take101_status
return 0 2>/dev/null || exit 0
