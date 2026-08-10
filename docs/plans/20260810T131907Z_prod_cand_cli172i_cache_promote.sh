#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

name="0233798f12c3ebe5938ba5446a32e9ef_"
conda_root="/fsx/resources/environments/conda/ubuntu/ip-10-0-0-13"
relay_bucket="lsmc-ssf-sequencing-data"
relay_prefix="derived/validation/prod-cand-260809-init-test-x2-20260810/cache-promotion/20260810T131907Z/cached_envs/conda"
state_dir="/home/ubuntu/.cache/daylily/cache-promotion/20260810T131907Z"
status_file="${state_dir}/status"
rc_file="${state_dir}/rc"
manifest="${state_dir}/promotion_manifest.tsv"
aws_config="${state_dir}/aws_config"

if [[ -e "${state_dir}" ]]; then
  echo "ERROR_STATE_DIR_EXISTS ${state_dir}" >&2
  exit 10
fi
mkdir -p "${state_dir}"
printf 'RUNNING\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "${status_file}"
printf 'kind\tname\tsource\tsource_bytes\tdestination\tcompleted_utc\n' > "${manifest}"

printf '%s\n' \
  '[default]' \
  'retry_mode = standard' \
  'max_attempts = 10' \
  's3 =' \
  '    max_concurrent_requests = 4' \
  '    multipart_threshold = 64MB' \
  '    multipart_chunksize = 64MB' \
  > "${aws_config}"
export AWS_CONFIG_FILE="${aws_config}"
export AWS_DEFAULT_REGION="us-west-2"
export AWS_PAGER=""

finish() {
  local rc=$?
  local state="FAILED"
  if [[ ${rc} -eq 0 ]]; then
    state="SUCCESS"
  fi
  printf '%s\t%s\trc=%s\n' "${state}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${rc}" > "${status_file}"
  printf '%s\n' "${rc}" > "${rc_file}"
  printf 'CLI172I_CACHE_PROMOTION_%s\t%s\trc=%s\n' "${state}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${rc}"
}
trap finish EXIT

if pgrep -af 'conda env create|mamba.*create|micromamba.*create|apptainer.*pull|singularity.*pull|apptainer.*build|singularity.*build' >/dev/null; then
  echo "ERROR_CACHE_BUILD_PROCESS_ACTIVE" >&2
  exit 11
fi
if ! squeue -u ubuntu -h -t RUNNING | grep -q .; then
  echo "ERROR_NO_RUNNING_SLURM_JOB" >&2
  exit 12
fi

env_dir="${conda_root}/${name}"
yaml="${env_dir}.yaml"
[[ "${name}" =~ ^[0-9a-f]{32}_$ ]]
[[ -d "${env_dir}" && ! -L "${env_dir}" ]]
[[ -f "${env_dir}/conda-meta/history" ]]
[[ -f "${yaml}" && ! -L "${yaml}" ]]

dest_uri="s3://${relay_bucket}/${relay_prefix}/${name}/"
key_count="$(aws s3api list-objects-v2 --bucket "${relay_bucket}" --prefix "${relay_prefix}/${name}/" --max-keys 1 --query KeyCount --output text)"
[[ "${key_count}" == "0" ]] || {
  printf 'ERROR_RELAY_PREFIX_COLLISION\t%s\t%s\n' "${name}" "${key_count}" >&2
  exit 21
}
set +e
head_output="$(aws s3api head-object --bucket "${relay_bucket}" --key "${relay_prefix}/${name}.yaml" 2>&1)"
head_rc=$?
set -e
if [[ ${head_rc} -eq 0 ]]; then
  printf 'ERROR_RELAY_YAML_COLLISION\t%s\n' "${name}" >&2
  exit 22
fi
if ! grep -Eq '\(404\)|Not Found' <<<"${head_output}"; then
  printf 'ERROR_RELAY_YAML_HEAD\t%s\t%s\n' "${name}" "${head_output}" >&2
  exit 23
fi

source_bytes="$(du -sb "${env_dir}" | awk '{print $1}')"
printf 'ENV_START\t%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${name}" "${source_bytes}"
aws s3 sync --only-show-errors --follow-symlinks "${env_dir}/" "${dest_uri}"

diff_file="${state_dir}/${name}.post_upload_dryrun.txt"
aws s3 sync --dryrun --follow-symlinks "${env_dir}/" "${dest_uri}" > "${diff_file}"
if [[ -s "${diff_file}" ]]; then
  printf 'ERROR_POST_UPLOAD_DIFF\t%s\t%s\n' "${name}" "${diff_file}" >&2
  exit 24
fi

aws s3api put-object --bucket "${relay_bucket}" --key "${relay_prefix}/${name}.yaml" --body "${yaml}" --if-none-match '*' --checksum-algorithm SHA256 >/dev/null
remote_yaml_bytes="$(aws s3api head-object --bucket "${relay_bucket}" --key "${relay_prefix}/${name}.yaml" --query ContentLength --output text)"
local_yaml_bytes="$(stat -c %s "${yaml}")"
[[ "${remote_yaml_bytes}" == "${local_yaml_bytes}" ]]

completed="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'conda\t%s\t%s\t%s\t%s\t%s\n' "${name}" "${env_dir}" "${source_bytes}" "${dest_uri}" "${completed}" >> "${manifest}"
printf 'CLI172I_CACHE_PROMOTION_VERIFIED\t%s\t%s\n' "${completed}" "${name}"
