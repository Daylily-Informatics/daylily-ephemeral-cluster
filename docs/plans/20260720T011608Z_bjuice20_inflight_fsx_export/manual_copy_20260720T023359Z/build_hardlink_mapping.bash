#!/usr/bin/env bash
set -Eeuo pipefail

FAILURE_LIST="${1:?failure-list path is required}"
MAPPING_PATH="${2:?mapping output path is required}"
SOURCE_ROOT="/fsx/analysis_results/ifx-p2-1000-120-0715/bjuiceprevalanalysis-complete"
SOURCE_REL_ROOT="analysis_results/ifx-p2-1000-120-0715/bjuiceprevalanalysis-complete/"

line_count="$(wc -l < "${FAILURE_LIST}" | tr -d ' ')"
if [[ "${line_count}" != "36" ]]; then
  printf 'ERROR expected 36 failure rows, found %s\n' "${line_count}" >&2
  exit 2
fi

printf 'source_relative_path\tdestination_relative_path\tbytes\tinode\tlink_count\thsm_state\n' > "${MAPPING_PATH}"

while IFS=, read -r relative_path report_status report_error; do
  case "${relative_path}" in
    "${SOURCE_REL_ROOT}"*) ;;
    *)
      printf 'ERROR path outside approved root: %s\n' "${relative_path}" >&2
      exit 2
      ;;
  esac
  case "${relative_path}" in
    *.cram|*.cram.crai) ;;
    *)
      printf 'ERROR path is not an approved CRAM/CRAI artifact: %s\n' "${relative_path}" >&2
      exit 2
      ;;
  esac
  if [[ "${report_status}" != "failed" || "${report_error}" != "S3Error" ]]; then
    printf 'ERROR unexpected failure classification for %s\n' "${relative_path}" >&2
    exit 2
  fi

  destination_relative_path="${relative_path#"${SOURCE_REL_ROOT}"}"
  destination_path="${SOURCE_ROOT}/${destination_relative_path}"
  if [[ ! -f "${destination_path}" || -L "${destination_path}" ]]; then
    printf 'ERROR package artifact is not a regular non-symlink file: %s\n' "${destination_path}" >&2
    exit 2
  fi

  inode="$(stat -c '%i' "${destination_path}")"
  link_count="$(stat -c '%h' "${destination_path}")"
  bytes="$(stat -c '%s' "${destination_path}")"
  if [[ "${link_count}" != "2" ]]; then
    printf 'ERROR expected exactly two hard links for inode %s, found %s\n' "${inode}" "${link_count}" >&2
    exit 2
  fi

  mapfile -t matching_paths < <(find "${SOURCE_ROOT}" -xdev -type f -inum "${inode}" -printf '%P\n')
  if [[ "${#matching_paths[@]}" != "2" ]]; then
    printf 'ERROR expected two paths for inode %s, found %s\n' "${inode}" "${#matching_paths[@]}" >&2
    exit 2
  fi

  source_relative_path=""
  for candidate in "${matching_paths[@]}"; do
    if [[ "${candidate}" != "${destination_relative_path}" ]]; then
      source_relative_path="${candidate}"
    fi
  done
  if [[ -z "${source_relative_path}" ]]; then
    printf 'ERROR no distinct hard-link source found for %s\n' "${destination_relative_path}" >&2
    exit 2
  fi

  source_path="${SOURCE_ROOT}/${source_relative_path}"
  if [[ "$(stat -c '%i' "${source_path}")" != "${inode}" || "$(stat -c '%s' "${source_path}")" != "${bytes}" ]]; then
    printf 'ERROR hard-link identity changed for %s\n' "${destination_relative_path}" >&2
    exit 2
  fi
  hsm_state="$(lfs hsm_state "${source_path}")"
  if [[ "${hsm_state}" != *"exists archived"* || "${hsm_state}" == *"dirty"* ]]; then
    printf 'ERROR source hard link is not cleanly archived: %s\n' "${hsm_state}" >&2
    exit 2
  fi

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    "${source_relative_path}" "${destination_relative_path}" "${bytes}" \
    "${inode}" "${link_count}" "exists archived" >> "${MAPPING_PATH}"
done < "${FAILURE_LIST}"

mapped_count="$(( $(wc -l < "${MAPPING_PATH}") - 1 ))"
if [[ "${mapped_count}" != "36" ]]; then
  printf 'ERROR expected 36 mappings, found %s\n' "${mapped_count}" >&2
  exit 2
fi

printf 'MAPPING_GZIP_BASE64=%s\n' "$(gzip -c "${MAPPING_PATH}" | base64 -w0)"
