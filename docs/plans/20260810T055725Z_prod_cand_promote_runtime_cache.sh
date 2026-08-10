#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

bucket="lsmc-ssf-sequencing-data"
dest_prefix="derived/validation/prod-cand-260809-init-test-x2-20260810/cache-promotion/20260810T055725Z/cached_envs"
conda_root="/fsx/resources/environments/conda/ubuntu/ip-10-0-0-13"
state_dir="/home/ubuntu/.cache/daylily/cache-promotion/20260810T055725Z"
manifest="${state_dir}/promotion_manifest.tsv"
status_file="${state_dir}/status"
rc_file="${state_dir}/rc"
aws_config="${state_dir}/aws_config"

if [[ -e "${state_dir}" ]]; then
  echo "ERROR_STATE_DIR_EXISTS ${state_dir}" >&2
  exit 10
fi
mkdir -p "${state_dir}"
printf 'RUNNING\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "${status_file}"
printf 'kind\tname\tsource\tsource_bytes\tdestination\tcompleted_utc\n' > "${manifest}"

cat > "${aws_config}" <<'EOF'
[default]
retry_mode = standard
max_attempts = 10
s3 =
    max_concurrent_requests = 4
    multipart_threshold = 64MB
    multipart_chunksize = 64MB
EOF
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
  printf 'CACHE_PROMOTION_%s\t%s\trc=%s\n' "${state}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${rc}"
}
trap finish EXIT

names=(
  082c686fea1dcb2e746ed6db73354d1a_
  36d377f2690370c395cad3d44fcb97ff_
  3a4066336aa1dec4d6bc615e5e6cbb16_
  41bdd5851090dbb2336356a3f0be2473_
  4ff65c6aaa4e6658e7c422971c95ee85_
  766fb474be68885012083f6c622f6179_
  88aa4998af771810a00fe2cb10e21246_
  92f8bbc953659a4d8cf233a75d457e3f_
  957e87d5fe4ac8a44e5724ce50a149a1_
  9a8eaaa988c7096ecb77708fde347089_
  a443e7e684bb6c610530885db6664055_
  af0132e7fe10ee4cd05c1b877bcd09e8_
  b26a7b457aa6640a1af9af0f76be96a2_
  b3a9d533cd18cabddbe62f2713320a54_
  bf30457594bff473900e8811233cd47a_
  bf9ae2783a216ee7f6faf43a364179db_
  c2e451114a625144ab03840e398ea712_
  c9170b1232ccf7ec20f43ced852fb8c2_
  caa10c232eb19f6543aa45820fda8f74_
  cba901145cdb176cc8ee56f2aac12b87_
  ccc71549f5b9bbb8371ee8cfe43bf60c_
  cda71b1de49e4d37d9611dd7d2715e4b_
  ce665216e6cf27f7dd1729335b653c5b_
  d4b04c8d5d3069cacc630f531de5d173_
  d64dacd09ba579b5d7cacdfc400033c5_
  d8d3b1575e41db2f7ea52b3fb3531258_
  dccc9356e3c60edb825fa3a21a2296ae_
  df47ac2d26fef6f0eace26f819bda392_
  e64cde7284147387e31d87ada68f2d1c_
  ec5a7de2ea751bbceef716fb67d26c3a_
)

printf 'CACHE_PROMOTION_START\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'SOURCE_CONDA_ROOT\t%s\n' "${conda_root}"
printf 'DESTINATION\ts3://%s/%s/\n' "${bucket}" "${dest_prefix}"

if pgrep -af 'conda env create|mamba.*create|micromamba.*create|apptainer.*pull|singularity.*pull|apptainer.*build|singularity.*build' >/dev/null; then
  echo "ERROR_CACHE_BUILD_PROCESS_ACTIVE" >&2
  exit 11
fi
if ! squeue -u ubuntu -h -t RUNNING | grep -q .; then
  echo "ERROR_NO_RUNNING_SLURM_JOB" >&2
  exit 12
fi

for name in "${names[@]}"; do
  [[ "${name}" =~ ^[0-9a-f]{32}_$ ]]
  env_dir="${conda_root}/${name}"
  yaml="${env_dir}.yaml"
  [[ -d "${env_dir}" && ! -L "${env_dir}" ]]
  [[ -f "${env_dir}/conda-meta/history" ]]
  [[ -f "${yaml}" && ! -L "${yaml}" ]]

  key_count="$(aws s3api list-objects-v2 \
    --bucket "${bucket}" \
    --prefix "${dest_prefix}/conda/${name}/" \
    --max-keys 1 \
    --query KeyCount \
    --output text)"
  if [[ "${key_count}" != "0" ]]; then
    printf 'ERROR_PREFIX_COLLISION\t%s\t%s\n' "${name}" "${key_count}" >&2
    exit 21
  fi
  set +e
  head_output="$(aws s3api head-object \
    --bucket "${bucket}" \
    --key "${dest_prefix}/conda/${name}.yaml" 2>&1)"
  head_rc=$?
  set -e
  if [[ ${head_rc} -eq 0 ]]; then
    printf 'ERROR_YAML_COLLISION\t%s\n' "${name}" >&2
    exit 22
  fi
  if ! grep -Eq '\(404\)|Not Found' <<<"${head_output}"; then
    printf 'ERROR_YAML_HEAD\t%s\t%s\n' "${name}" "${head_output}" >&2
    exit 24
  fi
done

printf 'PREFLIGHT_COMPLETE\tconda=%s\tcontainers=0\n' "${#names[@]}"

for name in "${names[@]}"; do
  env_dir="${conda_root}/${name}"
  yaml="${env_dir}.yaml"
  dest_uri="s3://${bucket}/${dest_prefix}/conda/${name}/"
  source_bytes="$(du -sb "${env_dir}" | awk '{print $1}')"
  printf 'ENV_START\t%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${name}" "${source_bytes}"

  aws s3 sync \
    --only-show-errors \
    --follow-symlinks \
    "${env_dir}/" \
    "${dest_uri}"

  diff_file="${state_dir}/${name}.post_upload_dryrun.txt"
  aws s3 sync \
    --dryrun \
    --follow-symlinks \
    "${env_dir}/" \
    "${dest_uri}" > "${diff_file}"
  if [[ -s "${diff_file}" ]]; then
    printf 'ERROR_POST_UPLOAD_DIFF\t%s\t%s\n' "${name}" "${diff_file}" >&2
    exit 23
  fi

  aws s3api put-object \
    --bucket "${bucket}" \
    --key "${dest_prefix}/conda/${name}.yaml" \
    --body "${yaml}" \
    --if-none-match '*' \
    --checksum-algorithm SHA256 >/dev/null
  remote_yaml_bytes="$(aws s3api head-object \
    --bucket "${bucket}" \
    --key "${dest_prefix}/conda/${name}.yaml" \
    --query ContentLength \
    --output text)"
  local_yaml_bytes="$(stat -c %s "${yaml}")"
  [[ "${remote_yaml_bytes}" == "${local_yaml_bytes}" ]]

  completed="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'conda\t%s\t%s\t%s\t%s\t%s\n' \
    "${name}" "${env_dir}" "${source_bytes}" "${dest_uri}" "${completed}" >> "${manifest}"
  printf 'ENV_COMPLETE\t%s\t%s\n' "${completed}" "${name}"
done

printf 'CACHE_PROMOTION_VERIFIED\t%s\tconda=%s\tcontainers=0\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${#names[@]}"
