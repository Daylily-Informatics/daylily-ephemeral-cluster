#!/bin/bash

set -Eeuo pipefail

region="${1:?region argument is required}"
boot_s3_uri="${2:?cluster boot-config S3 URI is required}"
spot_price_warn_threshold="${3:?spot price warn threshold argument is required}"
storage_mode="${4:?storage mode argument is required}"
license_secret_arn="${5:?license secret ARN argument is required}"
base_script="$(mktemp /tmp/daylily-rhel8-node-config.XXXXXX)"
credential_tmp=""

cleanup() {
  rm -f "${base_script}"
  if [ -n "${credential_tmp}" ]; then
    rm -f "${credential_tmp}"
  fi
}
trap cleanup EXIT

aws s3 cp \
  "${boot_s3_uri%/}/post_install_rhel8_dragen.sh" \
  "${base_script}" \
  --region "${region}" \
  --only-show-errors
chmod 0700 "${base_script}"
"${base_script}" \
  "${region}" \
  "${boot_s3_uri}" \
  "${spot_price_warn_threshold}" \
  "${storage_mode}"

if ! id ubuntu >/dev/null 2>&1; then
  echo "ERROR: ubuntu user is missing after node configuration" >&2
  exit 1
fi

credential_dir="/home/ubuntu/.config/dragen"
credential_path="${credential_dir}/lic_creds.txt"
install -d -m 0700 -o ubuntu -g ubuntu "${credential_dir}"
credential_tmp="$(mktemp "${credential_dir}/lic_creds.txt.XXXXXX")"
chmod 0600 "${credential_tmp}"

secret_value="$(
  aws secretsmanager get-secret-value \
    --secret-id "${license_secret_arn}" \
    --region "${region}" \
    --query SecretString \
    --output text
)"
if [ -z "${secret_value}" ] || [ "${secret_value}" = "None" ]; then
  echo "ERROR: license secret is missing or empty" >&2
  exit 1
fi
printf '%s' "${secret_value}" > "${credential_tmp}"
unset secret_value
chown ubuntu:ubuntu "${credential_tmp}"
mv -f "${credential_tmp}" "${credential_path}"
credential_tmp=""
chmod 0600 "${credential_path}"

credential_size="$(stat -c '%s' "${credential_path}")"
if [ "${credential_size}" -le 0 ]; then
  echo "ERROR: hydrated license credential file is empty" >&2
  exit 1
fi
echo "Hydrated license credential metadata: path=${credential_path} mode=600 size=${credential_size}"
