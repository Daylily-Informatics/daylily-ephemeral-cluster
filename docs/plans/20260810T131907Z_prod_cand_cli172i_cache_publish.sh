#!/usr/bin/env bash
set -Eeuo pipefail

umask 077
export AWS_PROFILE="lsmc"
export AWS_DEFAULT_REGION="us-west-2"
export AWS_PAGER=""

name="0233798f12c3ebe5938ba5446a32e9ef_"
relay_bucket="lsmc-ssf-sequencing-data"
relay_prefix="derived/validation/prod-cand-260809-init-test-x2-20260810/cache-promotion/20260810T131907Z/cached_envs/conda"
dest_bucket="lsmc-dayoa-references-usw2"
dest_prefix="runtime_assets/cached_envs/conda"
state_dir="/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260810T131907Z_prod_cand_cli172i_cache_publish_state"
status_file="${state_dir}/status"
rc_file="${state_dir}/rc"
manifest="${state_dir}/canonical_publish_manifest.tsv"

if [[ -e "${state_dir}" ]]; then
  echo "ERROR_STATE_DIR_EXISTS ${state_dir}" >&2
  exit 10
fi
mkdir -p "${state_dir}"
printf 'RUNNING\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "${status_file}"
printf 'kind\tname\tsource\tdestination\tcompleted_utc\n' > "${manifest}"

tmp_root="$(mktemp -d /tmp/dayoa-cli172i-cache-publish.XXXXXX)"
finish() {
  local rc=$?
  local state="FAILED"
  if [[ ${rc} -eq 0 ]]; then
    state="SUCCESS"
  fi
  rm -f -- "${tmp_root}/${name}.yaml"
  rmdir -- "${tmp_root}"
  printf '%s\t%s\trc=%s\n' "${state}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${rc}" > "${status_file}"
  printf '%s\n' "${rc}" > "${rc_file}"
  printf 'CLI172I_CANONICAL_PUBLISH_%s\t%s\trc=%s\n' "${state}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${rc}"
}
trap finish EXIT

dest_uri="s3://${dest_bucket}/${dest_prefix}/${name}/"
relay_uri="s3://${relay_bucket}/${relay_prefix}/${name}/"
dest_count="$(aws s3api list-objects-v2 --bucket "${dest_bucket}" --prefix "${dest_prefix}/${name}/" --max-keys 1 --query KeyCount --output text)"
[[ "${dest_count}" == "0" ]] || {
  printf 'ERROR_DEST_PREFIX_COLLISION\t%s\t%s\n' "${name}" "${dest_count}" >&2
  exit 21
}
set +e
head_output="$(aws s3api head-object --bucket "${dest_bucket}" --key "${dest_prefix}/${name}.yaml" 2>&1)"
head_rc=$?
set -e
if [[ ${head_rc} -eq 0 ]]; then
  printf 'ERROR_DEST_YAML_COLLISION\t%s\n' "${name}" >&2
  exit 22
fi
if ! grep -Eq '\(404\)|Not Found' <<<"${head_output}"; then
  printf 'ERROR_DEST_YAML_HEAD\t%s\t%s\n' "${name}" "${head_output}" >&2
  exit 23
fi

wait_deadline=$((SECONDS + 7200))
while true; do
  set +e
  relay_head_output="$(aws s3api head-object --bucket "${relay_bucket}" --key "${relay_prefix}/${name}.yaml" 2>&1)"
  relay_head_rc=$?
  set -e
  if [[ ${relay_head_rc} -eq 0 ]]; then
    break
  fi
  if ! grep -Eq '\(404\)|Not Found' <<<"${relay_head_output}"; then
    printf 'ERROR_RELAY_YAML_HEAD\t%s\t%s\n' "${name}" "${relay_head_output}" >&2
    exit 24
  fi
  if (( SECONDS >= wait_deadline )); then
    printf 'ERROR_RELAY_WAIT_TIMEOUT\t%s\n' "${name}" >&2
    exit 25
  fi
  printf 'WAIT_RELAY_COMPLETE\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${name}"
  sleep 15
done

relay_count="$(aws s3api list-objects-v2 --bucket "${relay_bucket}" --prefix "${relay_prefix}/${name}/" --max-keys 1 --query KeyCount --output text)"
[[ "${relay_count}" != "0" ]]
aws s3 sync --only-show-errors "${relay_uri}" "${dest_uri}"

diff_file="${state_dir}/${name}.post_publish_dryrun.txt"
aws s3 sync --dryrun "${relay_uri}" "${dest_uri}" > "${diff_file}"
if [[ -s "${diff_file}" ]]; then
  printf 'ERROR_POST_PUBLISH_DIFF\t%s\t%s\n' "${name}" "${diff_file}" >&2
  exit 26
fi

local_yaml="${tmp_root}/${name}.yaml"
aws s3 cp --only-show-errors "s3://${relay_bucket}/${relay_prefix}/${name}.yaml" "${local_yaml}"
aws s3api put-object --bucket "${dest_bucket}" --key "${dest_prefix}/${name}.yaml" --body "${local_yaml}" --if-none-match '*' --checksum-algorithm SHA256 >/dev/null
remote_yaml_bytes="$(aws s3api head-object --bucket "${dest_bucket}" --key "${dest_prefix}/${name}.yaml" --query ContentLength --output text)"
local_yaml_bytes="$(stat -f %z "${local_yaml}")"
[[ "${remote_yaml_bytes}" == "${local_yaml_bytes}" ]]

completed="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'conda\t%s\t%s\t%s\t%s\n' "${name}" "${relay_uri}" "${dest_uri}" "${completed}" >> "${manifest}"
printf 'CLI172I_CANONICAL_PUBLISH_VERIFIED\t%s\t%s\n' "${completed}" "${name}"

