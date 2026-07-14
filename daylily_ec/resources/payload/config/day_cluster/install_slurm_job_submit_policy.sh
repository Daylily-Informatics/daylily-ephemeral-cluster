#!/bin/bash

set -Eeuo pipefail

region="${1:?region argument is required}"
boot_s3_uri="${2:?cluster boot-config S3 URI is required}"
policy_tmp="$(mktemp /tmp/daylily-job-submit.XXXXXX.lua)"

cleanup() {
  rm -f "${policy_tmp}"
}
trap cleanup EXIT

aws s3 cp \
  "${boot_s3_uri%/}/job_submit.lua" \
  "${policy_tmp}" \
  --region "${region}" \
  --only-show-errors

if [ ! -s "${policy_tmp}" ]; then
  echo "ERROR: downloaded Slurm job-submit policy is empty: ${boot_s3_uri%/}/job_submit.lua" >&2
  exit 1
fi

install -d -o root -g root -m 0755 /opt/slurm/etc
install -o root -g root -m 0644 "${policy_tmp}" /opt/slurm/etc/job_submit.lua
stat -c "Slurm job-submit policy: %A %U:%G %s %n" /opt/slurm/etc/job_submit.lua
