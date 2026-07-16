#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

bucket="lsmc-dayoa-references-usw2"
dest_prefix="runtime_assets/cached_envs"
conda_root="/fsx/resources/environments/conda/ubuntu/ip-10-0-0-22"
state_dir="/home/ubuntu/.cache/daylily/cache-promotion/20260716T022601Z"
manifest="${state_dir}/promotion_manifest.tsv"
status_file="${state_dir}/status"
rc_file="${state_dir}/rc"
aws_config="${state_dir}/aws_config"

mkdir -p "${state_dir}"
rm -f "${rc_file}"
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
  006efecfc3daf71d6e8891c8c5ec264e_
  0305ee2e0cf74ce3b5ebed91f8dc94a5_
  06953e3f381c391f984f782b21b9d543_
  0980c3945506ecfe0a3eccf79bbab0f4_
  1639057e83945a2943775982a7969933_
  30e61a2dc39d32749b2851fe08f1743a_
  38ded4f03b978d40a3ef9f7e9be498b4_
  3923c3190c5cf1716e7831acf8ef0441_
  519f82430c4bfa01b8224f13fd1aefb5_
  59542afef44767b88a4ac894bfb19812_
  6dbf8ec337fc9fc05441f68fb3af67ac_
  94dcae0c033f0b59e9e0c3192024612f_
  9c24da75d9c05fbc2e1c5c34d0ce0a62_
  a4227e5a83b9623c5c90f45f821fd559_
  bba811144d767ed3dd48f622d65d7594_
  c62a55f9f4dec85e2c5a054c4d72a6f8_
  c8d70b7965aeb5c50c5da862c810d183_
  d08982b3a831bcf512944528e46e2c82_
)

printf 'CACHE_PROMOTION_START\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'SOURCE_CONDA_ROOT\t%s\n' "${conda_root}"
printf 'DESTINATION\ts3://%s/%s/\n' "${bucket}" "${dest_prefix}"

# Revalidate the complete immutable snapshot and all collision gates before the
# first object is written.
for name in "${names[@]}"; do
  [[ "${name}" =~ ^[0-9a-f]{32}_$ ]]
  env_dir="${conda_root}/${name}"
  yaml="${env_dir}.yaml"
  [[ -f "${env_dir}/conda-meta/history" ]]
  [[ -f "${yaml}" ]]

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
  if aws s3api head-object \
    --bucket "${bucket}" \
    --key "${dest_prefix}/conda/${name}.yaml" >/dev/null 2>&1; then
    printf 'ERROR_YAML_COLLISION\t%s\n' "${name}" >&2
    exit 22
  fi
done

printf 'PREFLIGHT_COMPLETE\tconda=%s\n' "${#names[@]}"

for name in "${names[@]}"; do
  env_dir="${conda_root}/${name}"
  yaml="${env_dir}.yaml"
  dest_uri="s3://${bucket}/${dest_prefix}/conda/${name}/"
  source_bytes="$(du -sb "${env_dir}" | awk '{print $1}')"
  printf 'ENV_START\t%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${name}" "${source_bytes}"

  # The exact hash prefix was proven empty above. A serial sync retains the
  # historical cache layout while limiting concurrent FSx metadata reads.
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

# Real images are cache misses. Seeded symlinks are deliberately excluded.
mapfile -d '' real_images < <(
  find /fsx/resources/environments/containers \
    -type f \( -name '*.simg' -o -name '*.sif' \) -print0 2>/dev/null | sort -z
)
printf 'REAL_CONTAINER_IMAGES\t%s\n' "${#real_images[@]}"
for image in "${real_images[@]}"; do
  name="$(basename "${image}")"
  size="$(stat -c %s "${image}")"
  [[ "${size}" -gt 0 ]]
  key="${dest_prefix}/containers/${name}"
  if aws s3api head-object --bucket "${bucket}" --key "${key}" >/dev/null 2>&1; then
    printf 'ERROR_CONTAINER_COLLISION\t%s\n' "${key}" >&2
    exit 24
  fi
  if [[ "${size}" -ge 5368709120 ]]; then
    printf 'ERROR_CONTAINER_TOO_LARGE_FOR_CONDITIONAL_PUT\t%s\t%s\n' "${image}" "${size}" >&2
    exit 25
  fi
  aws s3api put-object \
    --bucket "${bucket}" \
    --key "${key}" \
    --body "${image}" \
    --if-none-match '*' \
    --checksum-algorithm SHA256 >/dev/null
  remote_size="$(aws s3api head-object --bucket "${bucket}" --key "${key}" --query ContentLength --output text)"
  [[ "${remote_size}" == "${size}" ]]
  completed="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'container\t%s\t%s\t%s\ts3://%s/%s\t%s\n' \
    "${name}" "${image}" "${size}" "${bucket}" "${key}" "${completed}" >> "${manifest}"
  printf 'CONTAINER_COMPLETE\t%s\t%s\n' "${completed}" "${name}"
done

printf 'CACHE_PROMOTION_VERIFIED\t%s\tconda=%s\tcontainers=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${#names[@]}" "${#real_images[@]}"
