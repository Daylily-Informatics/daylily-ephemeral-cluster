#!/bin/bash

# RHEL8/DRAGEN variant of the production Daylily ParallelCluster node
# configuration script. Runs as a ParallelCluster OnNodeConfigured action.

. "/etc/parallelcluster/cfnconfig"

set -Eeuo pipefail
shopt -s nullglob

export HOME="${HOME:-/root}"

timestamp="$(date +"%Y%m%d_%H%M%S")"
node_type="${cfn_node_type:-unknown}"
slurm_partition="${cfn_scheduler_queue_name:-${cfn_queue_name:-}}"
compute_resource="${cfn_scheduler_compute_resource_name:-${cfn_compute_resource_name:-}}"
node_type_slug="$(echo "${node_type}" | tr '[:upper:]' '[:lower:]')"
local_log_dir="/var/log/daylily"
local_log_fn="${local_log_dir}/$(hostname)_${node_type_slug}_${timestamp}_rhel8_dragen_configure.log"
mkdir -p "${local_log_dir}"
exec > >(tee -a "${local_log_fn}") 2>&1
trap 'rc=$?; echo "[$(date +%Y%m%d_%H%M%S)] ERROR rc=${rc} line=${LINENO}: ${BASH_COMMAND}"; exit ${rc}' ERR

touch "/tmp/$(hostname).dragen_configureBEGIN"

region="${1:?region argument is required}"
boot_s3_uri="${2:?cluster boot-config S3 URI is required}"
boot_s3_uri="${boot_s3_uri%/}"
storage_mode="${3:?storage mode argument is required; use fsx or nofsx}"
case "${storage_mode}" in
  fsx|nofsx) ;;
  *)
    echo "ERROR: unsupported DRAGEN node configuration storage mode: ${storage_mode}" >&2
    echo "Expected third arg to be exactly 'fsx' or 'nofsx'." >&2
    exit 64
    ;;
esac

references_root="/fsx/references"
runtime_assets_root="${references_root}/runtime_assets"
environment_cache_root="/fsx/resources/environments"
work_root="/fsx/work"
run_mounts_root="/fsx/run_dir_mounts"
reference_wait_timeout_seconds=3600
reference_wait_interval_seconds=15
sbatch_wrapper_sha256="690b8ce1de6f7afd6aed754a50315dbde440fbcad1432743a415b6a7ef43e301"
sleep_test_sha256="024531fc67ad8052a1660173d2b94ce83290baa63606099e887b0846aa3a4fae"
spot_lifecycle_state_dir="/var/lib/daylily/spot_lifecycle"
spot_lifecycle_state_file="${spot_lifecycle_state_dir}/metadata.env"

echo "[$timestamp] Running post_install_rhel8_dragen.sh ${region} ${boot_s3_uri} ${storage_mode} on $(hostname) as ${node_type}"
echo "[$timestamp] Local log: ${local_log_fn}"

if [ "${storage_mode}" = "fsx" ]; then
  start_wait="$(date +%s)"
  until [ -d /fsx ]; do
    elapsed="$(($(date +%s) - start_wait))"
    if [ "${elapsed}" -ge 600 ]; then
      echo "ERROR: /fsx mount is missing after 600s in fsx mode" >&2
      ls -la / >&2 || true
      exit 1
    fi
    echo "Waiting for /fsx mount (${elapsed}/600s)"
    sleep 10
  done
  install -d -m 1777 /fsx/logs
  fsx_log_fn="/fsx/logs/$(hostname)_${node_type_slug}_${timestamp}_rhel8_dragen_configure.log"
  exec > >(tee -a "${local_log_fn}" "${fsx_log_fn}") 2>&1
  echo "[$timestamp] FSx log: ${fsx_log_fn}"
fi

append_once() {
  local line="$1"
  local file="$2"
  grep -Fxq "$line" "$file" 2>/dev/null || echo "$line" >> "$file"
}

metadata() {
  local path="$1"
  local token
  token="$(curl -fsS -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")"
  curl -fsS -H "X-aws-ec2-metadata-token: ${token}" "http://169.254.169.254/latest/meta-data/${path}"
}

resolve_cluster_name_for_tags() {
  if [ -n "${cfn_cluster_name:-}" ]; then
    echo "${cfn_cluster_name}"
    return 0
  fi
  if [ -n "${stack_name:-}" ]; then
    echo "${stack_name}"
    return 0
  fi
  echo "ERROR: unable to resolve cluster name from /etc/parallelcluster/cfnconfig" >&2
  return 1
}

repair_compute_cluster_tags() {
  if [ "${node_type}" != "ComputeFleet" ]; then
    return 0
  fi
  local cluster_name_for_tags
  local instance_id
  cluster_name_for_tags="$(resolve_cluster_name_for_tags)"
  instance_id="$(metadata instance-id)"
  if [ -z "${region}" ] || [ -z "${instance_id}" ]; then
    echo "ERROR: region or instance id missing; cannot repair compute cluster tags" >&2
    exit 1
  fi
  aws ec2 create-tags \
    --resources "${instance_id}" \
    --tags \
      Key=parallelcluster:cluster-name,Value="${cluster_name_for_tags}" \
      Key=aws-parallelcluster-clustername,Value="${cluster_name_for_tags}" \
    --region "${region}"
}

wait_for_dir() {
  local path="$1"
  local label="$2"
  local timeout_seconds="$3"
  local interval_seconds="$4"
  local start
  local elapsed

  start="$(date +%s)"
  until [ -d "${path}" ]; do
    elapsed="$(($(date +%s) - start))"
    if [ "${elapsed}" -ge "${timeout_seconds}" ]; then
      echo "ERROR: expected ${label} is missing after ${timeout_seconds}s: ${path}" >&2
      local parent_dir
      parent_dir="$(dirname "${path}")"
      if [ -e "${parent_dir}" ]; then
        ls -la "${parent_dir}" >&2 || true
      fi
      exit 1
    fi
    echo "Waiting for ${label}: ${path} (${elapsed}/${timeout_seconds}s)"
    sleep "${interval_seconds}"
  done
}

install_required_rhel_packages() {
  local marker="/var/lib/daylily/rhel8_dragen_packages_done"
  if [ -f "${marker}" ]; then
    echo "RHEL package marker exists: ${marker}"
    return 0
  fi

  install -d -m 0755 /var/lib/daylily
  if ! rpm -qa >/dev/null 2>&1; then
    echo "RHEL rpm database validation failed; rebuilding rpmdb before dnf install."
    rm -f /var/lib/rpm/__db*
    rpm --rebuilddb
    rpm -qa >/dev/null
    dnf clean all
  fi
  dnf -y install \
    atop \
    bzip2 \
    cronie \
    emacs-nox \
    findutils \
    git \
    gzip \
    java-11-openjdk \
    jq \
    numactl \
    procps-ng \
    rsync \
    tar \
    tmux \
    unzip \
    util-linux \
    wget \
    which \
    xz \
    zip
  touch "${marker}"
}

ensure_user() {
  local user_name="$1"
  local group_name="$2"
  local home_dir="$3"
  if ! getent group "${group_name}" >/dev/null; then
    groupadd "${group_name}"
  fi
  if ! id "${user_name}" >/dev/null 2>&1; then
    useradd --create-home --home-dir "${home_dir}" --gid "${group_name}" --groups wheel "${user_name}"
  fi
}

configure_rclone_if_available() {
  if ! command -v rclone >/dev/null 2>&1; then
    echo "RHEL package set does not provide rclone; skipping rclone.conf creation."
    return 0
  fi
  mkdir -p "${HOME}/.config/rclone"
  cat <<EOF > "${HOME}/.config/rclone/rclone.conf"
[daylily]
type = s3
provider = AWS
env_auth = true
region = ${region}
EOF
}

log_spot_price() {
  local instance_type
  local instance_id
  local availability_zone
  local spot_price
  local log_file
  local recorded_at
  local recorded_at_epoch

  instance_type="$(metadata instance-type)"
  instance_id="$(metadata instance-id)"
  availability_zone="$(metadata placement/availability-zone)"
  spot_price="$(aws ec2 describe-spot-price-history \
    --instance-types "${instance_type}" \
    --region "${region}" \
    --availability-zone "${availability_zone}" \
    --product-description "Linux/UNIX" \
    --query 'SpotPriceHistory[0].SpotPrice' \
    --output text)"

  if [ "${storage_mode}" = "fsx" ]; then
    log_file="/fsx/scratch/$(hostname)_spot_price.log"
  else
    log_file="/var/log/daylily/$(hostname)_spot_price.log"
  fi
  recorded_at="$(date -u '+%Y-%m-%d %H:%M:%S')"
  recorded_at_epoch="$(date -u +%s)"
  echo "${recorded_at} - Node type: ${node_type}, Partition: ${slurm_partition}, Compute resource: ${compute_resource}, Hostname: $(hostname), Instance id: ${instance_id}, Region: ${region}, AZ: ${availability_zone}, Instance type: ${instance_type}, Spot price: ${spot_price} USD/hour" >> "${log_file}"

  install -d -m 0755 "${spot_lifecycle_state_dir}"
  {
    printf 'NODE_TYPE=%s\n' "${node_type}"
    printf 'SLURM_PARTITION=%s\n' "${slurm_partition}"
    printf 'COMPUTE_RESOURCE=%s\n' "${compute_resource}"
    printf 'HOSTNAME=%s\n' "$(hostname)"
    printf 'INSTANCE_ID=%s\n' "${instance_id}"
    printf 'REGION=%s\n' "${region}"
    printf 'AVAILABILITY_ZONE=%s\n' "${availability_zone}"
    printf 'INSTANCE_TYPE=%s\n' "${instance_type}"
    printf 'SPOT_PRICE=%s\n' "${spot_price}"
    printf 'LOG_FILE=%s\n' "${log_file}"
    printf 'START_RECORDED_AT=%s\n' "${recorded_at}"
    printf 'START_RECORDED_AT_EPOCH=%s\n' "${recorded_at_epoch}"
  } > "${spot_lifecycle_state_file}"
  chmod 0644 "${spot_lifecycle_state_file}"
}

install_spot_lifecycle_hooks() {
  if [ "${node_type}" != "ComputeFleet" ]; then
    echo "Spot lifecycle shutdown logging is enabled only on ComputeFleet nodes; skipping for ${node_type}."
    return 0
  fi
  if [ ! -s "${spot_lifecycle_state_file}" ]; then
    echo "ERROR: spot lifecycle metadata was not persisted: ${spot_lifecycle_state_file}" >&2
    exit 1
  fi

  install -d -m 0755 /opt/daylily/bin "${spot_lifecycle_state_dir}" /var/log/daylily
  cat > /opt/daylily/bin/daylily-spot-lifecycle-event <<'EOF'
#!/bin/bash
set -Eeuo pipefail

event="${1:?event argument is required}"
shutdown_reason="${2:-}"
state_file="/var/lib/daylily/spot_lifecycle/metadata.env"
state_dir="/var/lib/daylily/spot_lifecycle"
error_log="/var/log/daylily/spot_lifecycle_shutdown_errors.log"

if [ ! -s "${state_file}" ]; then
  printf '%s ERROR: missing spot lifecycle state: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "${state_file}" >> "${error_log}"
  exit 0
fi

# shellcheck disable=SC1090
source "${state_file}"

recorded_at="$(date -u '+%Y-%m-%d %H:%M:%S')"
recorded_at_epoch="$(date -u +%s)"
line="${recorded_at} - Event: ${event}, Node type: ${NODE_TYPE}, Partition: ${SLURM_PARTITION}, Compute resource: ${COMPUTE_RESOURCE}, Hostname: ${HOSTNAME}, Instance id: ${INSTANCE_ID}, Region: ${REGION}, AZ: ${AVAILABILITY_ZONE}, Instance type: ${INSTANCE_TYPE}, Spot price: ${SPOT_PRICE} USD/hour, Recorded epoch: ${recorded_at_epoch}"

case "${event}" in
  interruption_notice)
    interruption_action=""
    interruption_time=""
    if [ -s "${state_dir}/interruption_action" ]; then
      read -r interruption_action < "${state_dir}/interruption_action"
    fi
    if [ -s "${state_dir}/interruption_time" ]; then
      read -r interruption_time < "${state_dir}/interruption_time"
    fi
    if [ -z "${interruption_action}" ] || [ -z "${interruption_time}" ]; then
      printf '%s ERROR: interruption_notice missing action/time metadata\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" >> "${error_log}"
      exit 1
    fi
    line="${line}, Interruption action: ${interruption_action}, Interruption time: ${interruption_time}"
    ;;
  shutdown)
    if [ -z "${shutdown_reason}" ]; then
      shutdown_reason="systemd-stop"
    fi
    line="${line}, Shutdown reason: ${shutdown_reason}"
    ;;
  *)
    printf '%s ERROR: unsupported spot lifecycle event: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "${event}" >> "${error_log}"
    exit 1
    ;;
esac

if ! printf '%s\n' "${line}" >> "${LOG_FILE}"; then
  printf '%s ERROR: failed writing lifecycle event to %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "${LOG_FILE}" >> "${error_log}"
fi
EOF
  chmod 0755 /opt/daylily/bin/daylily-spot-lifecycle-event

  cat > /opt/daylily/bin/daylily-spot-interruption-watch <<'EOF'
#!/bin/bash
set -Eeuo pipefail

state_dir="/var/lib/daylily/spot_lifecycle"
notice_marker="${state_dir}/interruption_notice_logged"

imds_token() {
  curl -fsS -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600"
}

while true; do
  token="$(imds_token)"
  if body="$(curl -fsS -H "X-aws-ec2-metadata-token: ${token}" "http://169.254.169.254/latest/meta-data/spot/instance-action" 2>/dev/null)"; then
    action="$(printf '%s\n' "${body}" | sed -n 's/.*"action"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
    interruption_time="$(printf '%s\n' "${body}" | sed -n 's/.*"time"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
    if [ -z "${action}" ] || [ -z "${interruption_time}" ]; then
      echo "ERROR: IMDS spot instance-action did not include action and time: ${body}" >&2
      exit 1
    fi
    if [ ! -f "${notice_marker}" ]; then
      printf '%s\n' "${action}" > "${state_dir}/interruption_action"
      printf '%s\n' "${interruption_time}" > "${state_dir}/interruption_time"
      /opt/daylily/bin/daylily-spot-lifecycle-event interruption_notice
      touch "${notice_marker}"
    fi
  fi
  sleep 5
done
EOF
  chmod 0755 /opt/daylily/bin/daylily-spot-interruption-watch

  cat > /etc/systemd/system/daylily-spot-lifecycle-shutdown.service <<'EOF'
[Unit]
Description=Daylily spot lifecycle shutdown logger
DefaultDependencies=no
Before=shutdown.target reboot.target halt.target poweroff.target umount.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/true
ExecStop=/opt/daylily/bin/daylily-spot-lifecycle-event shutdown systemd-stop
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

  cat > /etc/systemd/system/daylily-spot-interruption-watch.service <<'EOF'
[Unit]
Description=Daylily spot interruption watcher
After=network-online.target daylily-spot-lifecycle-shutdown.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/opt/daylily/bin/daylily-spot-interruption-watch
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable --now daylily-spot-lifecycle-shutdown.service
  systemctl enable --now daylily-spot-interruption-watch.service
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

link_cached_entries() {
  local source_dir="$1"
  local dest_dir="$2"
  local requirement="${3:-required}"

  install -d -m 1777 "${dest_dir}"
  local source_paths=("${source_dir}"/*)
  if [ "${#source_paths[@]}" -eq 0 ]; then
    if [ "${requirement}" = "optional" ]; then
      echo "No optional cached entries found under ${source_dir}; skipping"
      return 0
    fi
    echo "ERROR: no cached entries found under ${source_dir}" >&2
    exit 1
  fi

  for source_path in "${source_paths[@]}"; do
    local dest_path="${dest_dir}/$(basename "${source_path}")"
    if [ -e "${dest_path}" ] || [ -L "${dest_path}" ]; then
      echo "Cached entry already present, leaving in place: ${dest_path}"
    else
      ln -s "${source_path}" "${dest_path}"
      echo "Seeded cached entry: ${dest_path} -> ${source_path}"
    fi
  done
}

wait_for_reference_data() {
  echo "Waiting for required DayOA role entries from FSx DRAs"
  wait_for_dir "${references_root}" "reference DRA path" "${reference_wait_timeout_seconds}" "${reference_wait_interval_seconds}"
  wait_for_dir "${runtime_assets_root}" "runtime assets path" "${reference_wait_timeout_seconds}" "${reference_wait_interval_seconds}"
  wait_for_dir "${runtime_assets_root}/cached_envs/conda" "cached conda environments" "${reference_wait_timeout_seconds}" "${reference_wait_interval_seconds}"
  wait_for_dir "${references_root}/genomic_data" "genomic reference data" "${reference_wait_timeout_seconds}" "${reference_wait_interval_seconds}"
  wait_for_dir "${runtime_assets_root}/tool_specific_resources" "tool-specific runtime resources" "${reference_wait_timeout_seconds}" "${reference_wait_interval_seconds}"
  if [ ! -s "${runtime_assets_root}/tool_specific_resources/womtool_87.jar" ]; then
    echo "ERROR: womtool_87.jar missing under ${runtime_assets_root}/tool_specific_resources" >&2
    exit 1
  fi
}

make_role_data_read_only() {
  for role_root in "${references_root}" "${runtime_assets_root}"; do
    if [ ! -d "${role_root}" ]; then
      echo "ERROR: role data directory not found: ${role_root}" >&2
      exit 1
    fi
    chmod a-w "${role_root}"
    stat -c "Role data permissions: %A %n" "${role_root}"
  done
}

prepare_common_writable_dirs() {
  install -d -m 1777 /tmp/jobs
  if [ "${storage_mode}" = "fsx" ]; then
    install -d -m 1777 \
      /fsx/scratch \
      /fsx/tmp \
      "${work_root}" \
      "${run_mounts_root}" \
      "${environment_cache_root}"
    install -d -m 0777 /fsx/analysis_results
    chmod a+rwx /fsx/analysis_results
    stat -c "Writable DayOA directory: %A %U:%G %n" \
      /fsx/scratch \
      /fsx/tmp \
      "${work_root}" \
      "${run_mounts_root}" \
      "${environment_cache_root}" \
      /fsx/analysis_results
  fi
}

prepare_headnode_writable_dirs() {
  install -d -m 0775 -o ubuntu -g ubuntu /fsx/analysis_results/ubuntu
  install -d -m 0775 -o daylily -g daylily /fsx/analysis_results/daylily
  install -d -m 0775 -o ubuntu -g ubuntu \
    "${work_root}/ubuntu" \
    "${work_root}/ubuntu/containers" \
    "${work_root}/ubuntu/nextflow" \
    "${work_root}/ubuntu/sarek"
  install -d -m 0775 -o daylily -g daylily \
    "${work_root}/daylily" \
    "${work_root}/daylily/containers" \
    "${work_root}/daylily/nextflow" \
    "${work_root}/daylily/sarek"
}

prepare_dayoa_environment_cache() {
  local host_name
  local user_name

  host_name="$(hostname)"
  install -d -m 1777 \
    "${environment_cache_root}/apptainer" \
    "${environment_cache_root}/apptainer/cache" \
    "${environment_cache_root}/apptainer/cache/net" \
    "${environment_cache_root}/conda" \
    "${environment_cache_root}/containers" \
    "${environment_cache_root}/nextflow"

  link_cached_entries \
    "${runtime_assets_root}/cached_envs/apptainer_cache/cache/net" \
    "${environment_cache_root}/apptainer/cache/net" \
    optional

  link_cached_entries \
    "${runtime_assets_root}/cached_envs/nextflow" \
    "${environment_cache_root}/nextflow" \
    optional

  for user_name in ubuntu daylily ec2-user; do
    install -d -m 1777 \
      "${environment_cache_root}/conda/${user_name}/${host_name}" \
      "${environment_cache_root}/containers/${user_name}/${host_name}"
    link_cached_entries \
      "${runtime_assets_root}/cached_envs/conda" \
      "${environment_cache_root}/conda/${user_name}/${host_name}" \
      required
    link_cached_entries \
      "${runtime_assets_root}/cached_envs/containers" \
      "${environment_cache_root}/containers/${user_name}/${host_name}" \
      optional
  done
}

install_runtime_profiles() {
  cat <<'EOF' > /etc/profile.d/daylily-rhel8-dragen.sh
# Managed by DAY-EC RHEL8 DRAGEN node setup.
export PATH="/opt/edico/bin:${PATH}"
export DRAGEN_INSTALL_DIR="${DRAGEN_INSTALL_DIR:-/opt/edico}"
export DRAGEN_BIN_DIR="${DRAGEN_BIN_DIR:-/opt/edico/bin}"
EOF
  chmod 0644 /etc/profile.d/daylily-rhel8-dragen.sh

  cat <<'EOF' > /etc/profile.d/daylily-runtime-cache.sh
# Managed by DAY-EC node setup.
if [ -n "${USER:-}" ] && [ "${USER}" != "root" ] && [ -d /fsx/work ]; then
  export DAYLILY_WORK_ROOT="${DAYLILY_WORK_ROOT:-/fsx/work/${USER}}"
  export DAYLILY_APPTAINER_CACHE="${DAYLILY_APPTAINER_CACHE:-/fsx/resources/environments/apptainer}"
  export DAYLILY_CONTAINER_CACHE="${DAYLILY_CONTAINER_CACHE:-${DAYLILY_WORK_ROOT}/containers}"
  export DAYLILY_NEXTFLOW_CACHE="${DAYLILY_NEXTFLOW_CACHE:-${DAYLILY_WORK_ROOT}/nextflow}"
  export DAYLILY_NEXTFLOW_SEED_CACHE="${DAYLILY_NEXTFLOW_SEED_CACHE:-/fsx/resources/environments/nextflow}"
  export NXF_HOME="${NXF_HOME:-${DAYLILY_NEXTFLOW_CACHE}/home}"
  export NXF_WORK="${NXF_WORK:-${DAYLILY_NEXTFLOW_CACHE}/work}"
  export NXF_SINGULARITY_CACHEDIR="${NXF_SINGULARITY_CACHEDIR:-${DAYLILY_CONTAINER_CACHE}}"
  export NXF_APPTAINER_CACHEDIR="${NXF_APPTAINER_CACHEDIR:-${DAYLILY_CONTAINER_CACHE}}"
  export SINGULARITY_CACHEDIR="${SINGULARITY_CACHEDIR:-${DAYLILY_APPTAINER_CACHE}}"
  export APPTAINER_CACHEDIR="${APPTAINER_CACHEDIR:-${DAYLILY_APPTAINER_CACHE}}"
fi
EOF
  chmod 0644 /etc/profile.d/daylily-runtime-cache.sh
}

install_womtool_link() {
  local source_path="${runtime_assets_root}/tool_specific_resources/womtool_87.jar"
  if [ ! -s "${source_path}" ]; then
    echo "ERROR: womtool_87.jar missing under ${runtime_assets_root}/tool_specific_resources" >&2
    exit 1
  fi
  ln -sfn "${source_path}" /usr/local/bin/womtool.jar
  chmod a+r /usr/local/bin/womtool.jar
  echo "Linked Womtool: /usr/local/bin/womtool.jar -> ${source_path}"
}

install_apptainer_if_available() {
  local rpm_paths=("${runtime_assets_root}"/cached_envs/apptainer*.rpm)
  if command -v apptainer >/dev/null 2>&1; then
    echo "Apptainer already available: $(command -v apptainer)"
  elif [ "${#rpm_paths[@]}" -gt 0 ]; then
    dnf -y install "${rpm_paths[0]}"
  else
    echo "No RHEL Apptainer RPM found in ${runtime_assets_root}/cached_envs; leaving Apptainer uninstalled for this DRAGEN node."
  fi
  if command -v apptainer >/dev/null 2>&1 && ! command -v singularity >/dev/null 2>&1; then
    ln -sfn "$(command -v apptainer)" /usr/local/bin/singularity
  fi
}

install_verified_s3_executable() {
  local s3_key="$1"
  local destination="$2"
  local expected_sha256="$3"
  local temp_path

  temp_path="$(mktemp "${destination}.download.XXXXXX")"
  aws s3 cp "${boot_s3_uri}/${s3_key}" "${temp_path}"
  echo "${expected_sha256}  ${temp_path}" | sha256sum -c -
  install -m 0755 "${temp_path}" "${destination}"
  rm -f "${temp_path}"
}

install_tagging_script() {
  install -d -m 0755 /opt/slurm/sbin
  cat <<'EOF' > /opt/slurm/sbin/check_tags.sh
#!/bin/bash
set -euo pipefail

source /etc/profile || true
TOKEN=$(curl -fsS -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
region=$(curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region)
aws configure set region "$region"

update=0
active_users=""
active_jobs=""
tag_userid=""
tag_jobid=""

if [ ! -f /tmp/jobs/jobs_users ] || [ ! -f /tmp/jobs/jobs_ids ]; then
  exit 0
fi

active_users=$(sort -u /tmp/jobs/jobs_users | tr '\n' ' ' | sed 's/[[:space:]]*$//')
active_jobs=$(sort /tmp/jobs/jobs_ids | tr '\n' ' ' | sed 's/[[:space:]]*$//')
echo "$active_users" > /tmp/jobs/tmp_jobs_users
echo "$active_jobs" > /tmp/jobs/tmp_jobs_ids

if [ ! -f /tmp/jobs/tag_userid ] || [ ! -f /tmp/jobs/tag_jobid ]; then
  echo "$active_users" > /tmp/jobs/tag_userid
  echo "$active_jobs" > /tmp/jobs/tag_jobid
  update=1
else
  tag_userid=$(cat /tmp/jobs/tag_userid)
  tag_jobid=$(cat /tmp/jobs/tag_jobid)
  if [ "$active_users" != "$tag_userid" ]; then
    echo "$active_users" > /tmp/jobs/tag_userid
    update=1
  fi
  if [ "$active_jobs" != "$tag_jobid" ]; then
    echo "$active_jobs" > /tmp/jobs/tag_jobid
    update=1
  fi
fi

if [ "$update" -eq 1 ]; then
  TOKEN=$(curl -fsS -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
  MyInstID=$(curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
  aws ec2 create-tags --resources "$MyInstID" --tags Key=aws-parallelcluster-username,Value="$(cat /tmp/jobs/tag_userid)" --region "$region"
  aws ec2 create-tags --resources "$MyInstID" --tags Key=aws-parallelcluster-jobid,Value="$(cat /tmp/jobs/tag_jobid)" --region "$region"
fi
EOF
  chmod 0755 /opt/slurm/sbin/check_tags.sh
}

install_compute_tag_cron() {
  install_tagging_script
  systemctl enable --now crond
  echo "* * * * * /opt/slurm/sbin/check_tags.sh" | crontab -
}

install_headnode_slurm_wrappers() {
  install -d -m 0755 /opt/slurm/sbin

  if [ ! -e /opt/slurm/sbin/sbatch ]; then
    mv /opt/slurm/bin/sbatch /opt/slurm/sbin/sbatch
  else
    echo "Original sbatch already present: /opt/slurm/sbin/sbatch"
  fi
  install_verified_s3_executable "sbatch" /opt/slurm/bin/sbatch "${sbatch_wrapper_sha256}"

  if [ ! -e /opt/slurm/sbin/srun ]; then
    mv /opt/slurm/bin/srun /opt/slurm/sbin/srun
  else
    echo "Original srun already present: /opt/slurm/sbin/srun"
  fi
  ln -sfn /opt/slurm/bin/sbatch /opt/slurm/bin/srun
  install_verified_s3_executable "sleep_test.sh" /opt/slurm/bin/sleep_test.sh "${sleep_test_sha256}"
}

install_headnode_prolog_epilog() {
  install_tagging_script

  cat <<'EOF' > /opt/slurm/sbin/prolog.sh
#!/bin/bash
set -euo pipefail
export SLURM_ROOT=/opt/slurm
install -d -m 1777 /tmp/jobs
echo "${SLURM_JOB_USER}" >> /tmp/jobs/jobs_users
echo "${SLURM_JOBID}" >> /tmp/jobs/jobs_ids
EOF

  cat <<'EOF' > /opt/slurm/sbin/epilog.sh
#!/bin/bash
set -euo pipefail
export SLURM_ROOT=/opt/slurm
sed -i "0,/${SLURM_JOB_USER}/d" /tmp/jobs/jobs_users 2>/dev/null || true
sed -i "0,/${SLURM_JOBID}/d" /tmp/jobs/jobs_ids 2>/dev/null || true
EOF

  chmod 0755 /opt/slurm/sbin/prolog.sh /opt/slurm/sbin/epilog.sh
  disable_slurm_partition_exclusivity
  append_once "AccountingStoreFlags=job_comment" /opt/slurm/etc/slurm.conf
  append_once "PrologFlags=Alloc" /opt/slurm/etc/slurm.conf
  append_once "Prolog=/opt/slurm/sbin/prolog.sh" /opt/slurm/etc/slurm.conf
  append_once "Epilog=/opt/slurm/sbin/epilog.sh" /opt/slurm/etc/slurm.conf
}

configure_kernel_and_shm() {
  cat <<'EOF' >/etc/sysctl.d/90-daylily-rhel8-dragen.conf
vm.nr_hugepages=2048
vm.hugetlb_shm_group=27
kernel.unprivileged_userns_clone=1
user.max_user_namespaces=15076
EOF
  sysctl --system

  local total_mem
  local shm_size_kb
  local shm_size_mb
  total_mem="$(awk '/MemTotal/ {print $2}' /proc/meminfo)"
  shm_size_kb="$((total_mem * 80 / 100))"
  shm_size_mb="$((shm_size_kb / 1024))"
  mount -o remount,size="${shm_size_mb}M" /dev/shm
  df -h /dev/shm
}

validate_dragen_host() {
  case "${node_type}" in
    HeadNode)
      echo "Skipping DRAGEN host validation on HeadNode; DRAGEN is required only on ComputeFleet nodes."
      return 0
      ;;
    ComputeFleet)
      ;;
    *)
      echo "ERROR: unsupported ParallelCluster node type for DRAGEN validation: ${node_type}" >&2
      exit 1
      ;;
  esac

  if [ ! -x /opt/edico/bin/dragen ]; then
    echo "ERROR: /opt/edico/bin/dragen is missing or not executable on $(hostname)" >&2
    exit 1
  fi
  /opt/edico/bin/dragen --version
  if [ ! -e /dev/dragen ]; then
    echo "ERROR: /dev/dragen is missing on DRAGEN compute node $(hostname)" >&2
    exit 1
  fi
  ls -l /dev/dragen
}

aws configure set region "${region}"
repair_compute_cluster_tags
ulimit -n 16384

install_required_rhel_packages
configure_rclone_if_available
ensure_user ubuntu ubuntu /home/ubuntu
ensure_user daylily daylily /home/daylily
install_runtime_profiles
prepare_common_writable_dirs
configure_kernel_and_shm
log_spot_price
install_spot_lifecycle_hooks
validate_dragen_host

if [ "${storage_mode}" = "fsx" ]; then
  wait_for_reference_data
  make_role_data_read_only
  prepare_dayoa_environment_cache
  install_womtool_link
  install_apptainer_if_available
  echo "DayOA conda, container, and Nextflow caches are seeded from ${runtime_assets_root}/cached_envs into ${environment_cache_root}"
else
  echo "No-FSx DRAGEN mode selected; skipped FSx reference, cache, Womtool, and Apptainer setup."
fi

if [ "${node_type}" = "HeadNode" ]; then
  echo "[$(date +%Y%m%d_%H%M%S)] Running HeadNode RHEL8 DRAGEN configure actions"
  if [ "${storage_mode}" = "fsx" ]; then
    prepare_headnode_writable_dirs
  fi
  install_headnode_slurm_wrappers
  install_headnode_prolog_epilog
  systemctl restart slurmctld
  touch "/tmp/$(hostname).postslurmcfg"
elif [ "${node_type}" = "ComputeFleet" ]; then
  echo "[$(date +%Y%m%d_%H%M%S)] Running ComputeFleet RHEL8 DRAGEN configure actions"
  install_compute_tag_cron
else
  echo "Unknown ParallelCluster node type ${node_type}; common RHEL8 DRAGEN configuration complete."
fi

touch "/tmp/$(hostname).dragen_configureDONE"
echo "[$(date +%Y%m%d_%H%M%S)] post_install_rhel8_dragen.sh complete"
