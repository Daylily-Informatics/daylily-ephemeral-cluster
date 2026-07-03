#!/bin/bash

. "/etc/parallelcluster/cfnconfig"

set -Eeuo pipefail

export HOME="${HOME:-/root}"

timestamp="$(date +"%Y%m%d_%H%M%S")"
node_type="${cfn_node_type:-unknown}"
node_type_slug="$(echo "${node_type}" | tr '[:upper:]' '[:lower:]')"
local_log_dir="/var/log/daylily"
local_log_fn="${local_log_dir}/$(hostname)_${node_type_slug}_${timestamp}_dragen_postinstall.log"
mkdir -p "${local_log_dir}"

if [ ! -d /fsx ]; then
  exec > >(tee -a "${local_log_fn}") 2>&1
  echo "ERROR: expected /fsx mount is missing"
  exit 1
fi

install -d -m 1777 /fsx/logs
fsx_log_fn="/fsx/logs/$(hostname)_${node_type_slug}_${timestamp}_dragen_postinstall.log"
exec > >(tee -a "${local_log_fn}" "${fsx_log_fn}") 2>&1
trap 'rc=$?; echo "[$(date +%Y%m%d_%H%M%S)] ERROR rc=${rc} line=${LINENO}: ${BASH_COMMAND}"; exit ${rc}' ERR

region="$1"
boot_s3_uri="${2%/}"
references_root="/fsx/references"
runtime_assets_root="${references_root}/runtime_assets"
work_root="/fsx/work"
run_mounts_root="/fsx/run_dir_mounts"
environment_cache_root="/fsx/resources/environments"

echo "[$timestamp] Running post_install_rhel8_dragen.sh ${region} ${boot_s3_uri} on $(hostname) as ${node_type}"
echo "[$timestamp] Local log: ${local_log_fn}"
echo "[$timestamp] FSx log: ${fsx_log_fn}"

aws configure set region "${region}"

if [ ! -d "${references_root}" ]; then
  echo "ERROR: expected reference DRA path is missing: ${references_root}" >&2
  exit 1
fi

if [ ! -d "${runtime_assets_root}" ]; then
  echo "ERROR: expected runtime assets path is missing: ${runtime_assets_root}" >&2
  exit 1
fi

ensure_user() {
  local user_name="$1"
  local primary_group="$2"
  local home_dir="$3"
  if ! getent group "${primary_group}" >/dev/null; then
    groupadd "${primary_group}"
  fi
  if ! id "${user_name}" >/dev/null 2>&1; then
    useradd --create-home --home-dir "${home_dir}" --gid "${primary_group}" --groups wheel "${user_name}"
  fi
}

ensure_user ubuntu ubuntu /home/ubuntu
ensure_user daylily daylily /home/daylily

install -d -m 1777 /tmp/jobs /fsx/scratch /fsx/tmp "${work_root}" "${run_mounts_root}" "${environment_cache_root}"
install -d -m 0777 /fsx/analysis_results
install -d -m 0775 -o ubuntu -g ubuntu /fsx/analysis_results/ubuntu /fsx/analysis_results/cromwell_executions
install -d -m 0775 -o daylily -g daylily /fsx/analysis_results/daylily
install -d -m 0775 -o ubuntu -g ubuntu "${work_root}/ubuntu"
install -d -m 0775 -o daylily -g daylily "${work_root}/daylily"

cat <<'EOF' > /etc/profile.d/daylily-rhel8-dragen.sh
export DAYLILY_WORK_ROOT="${DAYLILY_WORK_ROOT:-/fsx/work/${USER}}"
export DAYLILY_APPTAINER_CACHE="${DAYLILY_APPTAINER_CACHE:-/fsx/resources/environments/apptainer}"
export DAYLILY_NEXTFLOW_SEED_CACHE="${DAYLILY_NEXTFLOW_SEED_CACHE:-/fsx/resources/environments/nextflow}"
EOF
chmod 0644 /etc/profile.d/daylily-rhel8-dragen.sh

if [ "${node_type}" = "ComputeFleet" ]; then
  if ! command -v dragen >/dev/null 2>&1; then
    echo "ERROR: dragen command is not on PATH for compute node $(hostname)" >&2
    exit 1
  fi
  dragen --version
else
  echo "Skipping dragen command validation on non-compute node type ${node_type}"
fi

stat -c "DRAGEN bootstrap path: %A %U:%G %n" \
  /fsx \
  "${references_root}" \
  /fsx/scratch \
  /fsx/tmp \
  /fsx/analysis_results \
  "${work_root}" \
  "${run_mounts_root}" \
  "${environment_cache_root}"

touch "/tmp/$(hostname).dragen_postinstallDONE"
echo "[$(date +%Y%m%d_%H%M%S)] post_install_rhel8_dragen.sh complete"
