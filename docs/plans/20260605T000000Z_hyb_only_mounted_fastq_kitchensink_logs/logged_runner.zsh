#!/usr/bin/env zsh
set -uo pipefail

CMD_LOG="/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/ONT_ILMN_SOLO_CMD_LOG.md"
LOG_DIR="/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260605T000000Z_hyb_only_mounted_fastq_kitchensink_logs"
IDX_FILE="${LOG_DIR}/.cmd_idx"

mkdir -p "${LOG_DIR}"
if [[ ! -f "${IDX_FILE}" ]]; then
  print -r -- "999" > "${IDX_FILE}"
fi

_md_escape() {
  printf '%s' "$1" | perl -0pe 's/\r?\n/\\n/g; s/\|/\\|/g'
}

run_logged() {
  local label="$1"
  local classification="$2"
  local purpose="$3"
  local rollback_needed="$4"
  local rollback_action="$5"
  local notes="$6"
  shift 6
  local command="$*"
  local current_idx
  current_idx="$(cat "${IDX_FILE}")"
  local idx=$((current_idx + 1))
  print -r -- "${idx}" > "${IDX_FILE}"
  local start
  start="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  local safe_label
  safe_label="$(printf '%s' "${label}" | tr -c 'A-Za-z0-9_.-' '_')"
  local stdout_log="${LOG_DIR}/$(printf '%05d' "${idx}")_${safe_label}.stdout.txt"
  local stderr_log="${LOG_DIR}/$(printf '%05d' "${idx}")_${safe_label}.stderr.txt"
  local cwd
  cwd="$(pwd)"
  print -r -- "[RUN ${idx}] ${label}: ${command}"
  eval "${command}" > "${stdout_log}" 2> "${stderr_log}"
  local rc=$?
  {
    printf '| %s | %s | %s | local | %s | %s | %s | %s | %s | %s | %s | %s | %s |\n' \
      "${idx}" \
      "$(_md_escape "${start}")" \
      "$(_md_escape "${cwd}")" \
      "$(_md_escape "${purpose}")" \
      "$(_md_escape "${command}")" \
      "${rc}" \
      "$(_md_escape "${stdout_log}")" \
      "$(_md_escape "${stderr_log}")" \
      "$(_md_escape "${classification}")" \
      "$(_md_escape "${rollback_needed}")" \
      "$(_md_escape "${rollback_action}")" \
      "$(_md_escape "${notes}")"
  } >> "${CMD_LOG}"
  print -r -- "[RC ${idx}] ${rc}"
  if [[ -s "${stdout_log}" ]]; then
    print -r -- "[STDOUT ${idx}]"
    tail -n 120 "${stdout_log}" || true
  fi
  if [[ "${rc}" -ne 0 ]]; then
    print -r -- "[STDERR ${idx}]"
    tail -n 80 "${stderr_log}" || true
  fi
  return "${rc}"
}
