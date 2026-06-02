#!/usr/bin/env zsh
set -euo pipefail

PROFILE="${PROFILE:-lsmc}"
REGION="${REGION:-us-west-2}"
CLUSTER="${CLUSTER:-dyec5117}"
DAYOA_TAG="${DAYOA_TAG:-2.0.34}"
RUNID="${RUNID:-20260514_LH01106_0009_B23TVLGLT4}"
EXP_STAMP="${EXP_STAMP:-20260601T234556Z}"
ANALYSIS_STAMP="${ANALYSIS_STAMP:-$EXP_STAMP}"
EXP_DIR="${EXP_DIR:-docs/plans/${EXP_STAMP}_bcl_l003_25b_shard_experiment}"
RUN_CONTEXT="${RUN_CONTEXT:-${EXP_DIR}/runs_l003.tsv}"
LOG_DIR="${EXP_DIR}/command_logs"
METADATA_DIR="${EXP_DIR}/metadata"

mkdir -p "$LOG_DIR" "$METADATA_DIR"

if [[ -f ./activate ]]; then
  source ./activate >/dev/null
fi

log_name() {
  local label="$1"
  printf "%s/%s_%s" "$LOG_DIR" "$(date -u +%Y%m%dT%H%M%SZ)" "$label"
}

run_logged() {
  local label="$1"
  shift
  local base
  base="$(log_name "$label")"
  printf "%s\n" "$*" > "${base}.cmd.txt"
  "$@" > "${base}.stdout.txt" 2> "${base}.stderr.txt"
}

analysis_id_for_arm() {
  local arm="$1"
  printf "bcl25b_l003_%s_%s" "$arm" "$ANALYSIS_STAMP"
}

dy_command_for_arm() {
  local shard_level="$1"
  local jobs="$2"
  local shared_thread_odirect_output="${SHARED_THREAD_ODIRECT_OUTPUT:-false}"
  local merge_lane_fastqs="${MERGE_LANE_FASTQS:-false}"
  local tile_parallel_tiles="${TILE_PARALLEL_TILES:-8}"
  local tile_conversion_threads="${TILE_CONVERSION_THREADS:-2}"
  local tile_compression_threads="${TILE_COMPRESSION_THREADS:-24}"
  local tile_decompression_threads="${TILE_DECOMPRESSION_THREADS:-8}"
  local tile_shard_threads="${TILE_SHARD_THREADS:-48}"
  printf "bin/day_run produce_bclconvert_fastqs -p -j %s -k --config run_context_file=config/runs.tsv bootstrap_bclconvert=true bclconvert='{\"barcode_mismatches_index1\":\"0\",\"barcode_mismatches_index2\":\"0\",\"compression_threads\":\"64\",\"conversion_threads\":\"4\",\"decompression_threads\":\"32\",\"fastq_gzip_compression_level\":\"1\",\"force\":\"true\",\"merge_lane_fastqs\":\"%s\",\"num_unknown_barcodes_reported\":\"1000\",\"output_legacy_stats\":\"true\",\"parallel_tiles\":\"24\",\"partition\":\"i192mem\",\"sample_sheet_settings\":\"{}\",\"sample_sheet_settings_by_lane\":\"{}\",\"shared_thread_odirect_output\":\"%s\",\"threads\":\"192\",\"tile_compression_threads\":\"%s\",\"tile_conversion_threads\":\"%s\",\"tile_decompression_threads\":\"%s\",\"tile_parallel_tiles\":\"%s\",\"tile_shard_lanes\":\"L003\",\"tile_shard_level\":\"%s\",\"tile_shard_mem_mb\":\"180000\",\"tile_shard_threads\":\"%s\",\"tmpdir\":\"/dev/shm\"}'" "$jobs" "$merge_lane_fastqs" "$shared_thread_odirect_output" "$tile_compression_threads" "$tile_conversion_threads" "$tile_decompression_threads" "$tile_parallel_tiles" "$shard_level" "$tile_shard_threads"
}

preflight() {
  run_logged git_rev git rev-parse HEAD
  run_logged git_status git status --short --branch
  run_logged dyec_version dyec --json version
  run_logged cluster_describe dyec --json cluster describe --profile "$PROFILE" --region "$REGION" --cluster "$CLUSTER"
  cp "${LOG_DIR}"/*_cluster_describe.stdout.txt "${METADATA_DIR}/cluster_describe.json"
  run_logged mounts_verify dyec --json mounts verify --profile "$PROFILE" --region "$REGION" --cluster "$CLUSTER" --mount-id "$RUNID" --platform ILMN --timeout-seconds 600
  cp "${LOG_DIR}"/*_mounts_verify.stdout.txt "${METADATA_DIR}/mounts_verify.json"
  python "${EXP_DIR}/scripts/remote_metadata.py"
}

launch_arm() {
  local arm="$1"
  local shard_level="$2"
  local jobs="$3"
  local analysis_id
  local dy_command
  analysis_id="$(analysis_id_for_arm "$arm")"
  dy_command="$(dy_command_for_arm "$shard_level" "$jobs")"
  printf "%s\n" "$analysis_id" > "${METADATA_DIR}/analysis_id_${arm}.txt"
  printf "%s\n" "$dy_command" > "${METADATA_DIR}/dy_command_${arm}.txt"
  run_logged "launch_${arm}" python -m daylily_ec.cli workflow launch --profile "$PROFILE" --region "$REGION" --cluster "$CLUSTER" --repository daylily-omics-analysis --analysis-id "$analysis_id" --executing-entity ubuntu --session-name "$analysis_id" --git-tag "$DAYOA_TAG" --run-context-file "$RUN_CONTEXT" --dy-command "$dy_command"
}

status_arm() {
  local arm="$1"
  local analysis_id
  analysis_id="$(analysis_id_for_arm "$arm")"
  run_logged "status_${arm}" dyec --json workflow status --profile "$PROFILE" --region "$REGION" --cluster "$CLUSTER" --session "$analysis_id"
}

logs_arm() {
  local arm="$1"
  local lines="${2:-200}"
  local analysis_id
  analysis_id="$(analysis_id_for_arm "$arm")"
  run_logged "logs_${arm}" dyec workflow logs --profile "$PROFILE" --region "$REGION" --cluster "$CLUSTER" --session "$analysis_id" --lines "$lines"
}

monitor_arm() {
  local arm="$1"
  local analysis_id
  local latest
  local wf_status
  local exit_code
  analysis_id="$(analysis_id_for_arm "$arm")"
  while true; do
    status_arm "$arm" || true
    latest="$(ls -t "${LOG_DIR}"/*"_status_${arm}.stdout.txt" 2>/dev/null | head -n 1 || true)"
    if [[ -n "$latest" ]]; then
      cp "$latest" "${METADATA_DIR}/status_${arm}.json"
      wf_status="$(python -c 'import json,sys; p=json.load(open(sys.argv[1])); print(str(p.get("status") or p.get("state") or p.get("workflow_status") or ""))' "$latest" 2>/dev/null || true)"
      exit_code="$(python -c 'import json,sys; p=json.load(open(sys.argv[1])); print(str(p.get("exit_code") if p.get("exit_code") is not None else ""))' "$latest" 2>/dev/null || true)"
      case "$wf_status" in
        SUCCESS|COMPLETED|complete|completed|success)
          logs_arm "$arm" 300 || true
          return 0
          ;;
        FAILED|FAIL|ERROR|failed|fail|error)
          logs_arm "$arm" 500 || true
          return 2
          ;;
      esac
      if [[ "$exit_code" != "" && "$exit_code" != "None" ]]; then
        logs_arm "$arm" 300 || true
        if [[ "$exit_code" == "0" ]]; then
          return 0
        fi
        return 2
      fi
    fi
    sleep 120
  done
}

harvest_arm() {
  local arm="$1"
  ARM="$arm" python "${EXP_DIR}/scripts/harvest_arm.py"
}

fsx_check() {
  local arm="$1"
  ARM="$arm" python "${EXP_DIR}/scripts/check_fsx_capacity.py"
}

summarize() {
  python "${EXP_DIR}/scripts/summarize_benchmarks.py"
}

case "${1:-}" in
  preflight)
    preflight
    ;;
  launch)
    launch_arm "$2" "$3" "$4"
    ;;
  status)
    status_arm "$2"
    ;;
  logs)
    logs_arm "$2" "${3:-200}"
    ;;
  monitor)
    monitor_arm "$2"
    ;;
  harvest)
    harvest_arm "$2"
    ;;
  fsx-check)
    fsx_check "$2"
    ;;
  summarize)
    summarize
    ;;
  *)
    echo "Usage: $0 preflight | launch ARM SHARD_LEVEL JOBS | status ARM | logs ARM [LINES] | monitor ARM | harvest ARM | fsx-check ARM | summarize" >&2
    exit 64
    ;;
esac
