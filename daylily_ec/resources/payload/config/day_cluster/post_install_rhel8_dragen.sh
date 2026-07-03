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

exec > >(tee -a "${local_log_fn}") 2>&1
trap 'rc=$?; echo "[$(date +%Y%m%d_%H%M%S)] ERROR rc=${rc} line=${LINENO}: ${BASH_COMMAND}"; exit ${rc}' ERR

wait_for_dir() {
  local path="$1"
  local label="$2"
  local timeout_seconds="$3"
  local interval_seconds="$4"
  local waited_seconds=0

  until [ -d "${path}" ]; do
    if [ "${waited_seconds}" -ge "${timeout_seconds}" ]; then
      echo "ERROR: expected ${label} is missing after ${timeout_seconds}s: ${path}" >&2
      local parent_dir
      parent_dir="$(dirname "${path}")"
      if [ -e "${parent_dir}" ]; then
        ls -la "${parent_dir}" >&2 || true
      fi
      exit 1
    fi
    echo "Waiting for ${label}: ${path} (${waited_seconds}/${timeout_seconds}s)"
    sleep "${interval_seconds}"
    waited_seconds=$((waited_seconds + interval_seconds))
  done
}

wait_for_dir /fsx "/fsx mount" 600 10

install -d -m 1777 /fsx/logs
fsx_log_fn="/fsx/logs/$(hostname)_${node_type_slug}_${timestamp}_dragen_postinstall.log"
exec > >(tee -a "${local_log_fn}" "${fsx_log_fn}") 2>&1

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

wait_for_dir "${references_root}" "reference DRA path" 3600 15
wait_for_dir "${runtime_assets_root}" "runtime assets path" 3600 15

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

disable_slurm_partition_exclusivity() {
  local slurm_conf="/opt/slurm/etc/slurm.conf"
  if [ ! -f "${slurm_conf}" ]; then
    echo "ERROR: Slurm config not found while disabling partition exclusivity: ${slurm_conf}" >&2
    exit 1
  fi

  echo "ALERT WARNING: Enforcing non-exclusive Slurm scheduling in ${slurm_conf}; PartitionName lines will use OverSubscribe=YES and SelectTypeParameters=CR_CPU_Memory."
  python3 - "${slurm_conf}" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").splitlines()
rewritten = []
has_select_type_parameters = False
for line in lines:
    if line.startswith("SelectTypeParameters="):
        rewritten.append("SelectTypeParameters=CR_CPU_Memory")
        has_select_type_parameters = True
        continue
    if line.startswith("PartitionName="):
        fields = line.split()
        saw_oversubscribe = False
        next_fields = []
        for field in fields:
            if field.startswith("OverSubscribe="):
                next_fields.append("OverSubscribe=YES")
                saw_oversubscribe = True
            else:
                next_fields.append(field)
        if not saw_oversubscribe:
            next_fields.append("OverSubscribe=YES")
        rewritten.append(" ".join(next_fields))
        continue
    rewritten.append(line)
if not has_select_type_parameters:
    rewritten.append("SelectTypeParameters=CR_CPU_Memory")
path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
PY

  if grep -Eq '^PartitionName=.*OverSubscribe=EXCLUSIVE' "${slurm_conf}"; then
    echo "ERROR: exclusive Slurm partition allocation survived boot rewrite in ${slurm_conf}" >&2
    grep -E '^PartitionName=' "${slurm_conf}" >&2
    exit 1
  fi
  grep -E '^(SelectTypeParameters=|PartitionName=)' "${slurm_conf}" || true
}

ensure_user ubuntu ubuntu /home/ubuntu
ensure_user daylily daylily /home/daylily

install -d -m 1777 /tmp/jobs /fsx/scratch /fsx/tmp "${work_root}" "${run_mounts_root}" "${environment_cache_root}"
install -d -m 0777 /fsx/analysis_results
install -d -m 0775 -o ubuntu -g ubuntu /fsx/analysis_results/ubuntu /fsx/analysis_results/cromwell_executions
install -d -m 0775 -o daylily -g daylily /fsx/analysis_results/daylily
install -d -m 0775 -o ubuntu -g ubuntu "${work_root}/ubuntu"
install -d -m 0775 -o daylily -g daylily "${work_root}/daylily"

if [ "${node_type}" != "ComputeFleet" ]; then
  disable_slurm_partition_exclusivity
  systemctl restart slurmctld
fi

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
