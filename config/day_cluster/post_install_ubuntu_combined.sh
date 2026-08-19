#!/bin/bash

# built upon: https://github.com/Daylily-Informatics/aws-parallelcluster-cost-allocation-tags
# MIT No Attribution

# The script configures the Slurm cluster after the deployment.

# This initializes many useful env vars (cfn_node_type, stack_name, region, etc) need to use this more correctly below
. "/etc/parallelcluster/cfnconfig"

set -Ee -o pipefail

# ParallelCluster compute custom actions may run without HOME in the environment.
export HOME="${HOME:-/root}"

timestamp=$(date +"%Y%m%d_%H%M%S")
node_type="${cfn_node_type:-unknown}"
slurm_partition="${cfn_scheduler_queue_name:-${cfn_queue_name:-}}"
compute_resource="${cfn_scheduler_compute_resource_name:-${cfn_compute_resource_name:-}}"
node_type_slug="$(echo "${node_type}" | tr '[:upper:]' '[:lower:]')"
local_log_dir="/var/log/daylily"
local_log_fn="${local_log_dir}/$(hostname)_${node_type_slug}_${timestamp}_postinstall.log"
mkdir -p "${local_log_dir}"
if [ -d /fsx ]; then
  install -d -m 1777 /fsx/logs
  fsx_log_fn="/fsx/logs/$(hostname)_${node_type_slug}_${timestamp}.log"
  exec > >(tee -a "${local_log_fn}" "${fsx_log_fn}") 2>&1
else
  exec > >(tee -a "${local_log_fn}") 2>&1
fi
trap 'rc=$?; echo "[$(date +%Y%m%d_%H%M%S)] ERROR rc=${rc} line=${LINENO}: ${BASH_COMMAND}"; exit ${rc}' ERR

touch /tmp/$(hostname).postinstallBEGIN

region="$1"
boot_s3_uri="${2%/}"  # s3://.../cluster_boot_config
spot_price_warn_threshold="${3:?spot price warn threshold argument is required}"
python3 - "${spot_price_warn_threshold}" <<'PY'
import sys

try:
    value = float(sys.argv[1])
except ValueError as exc:
    raise SystemExit(f"spot price warn threshold must be numeric: {sys.argv[1]!r}") from exc
if value <= 0:
    raise SystemExit(f"spot price warn threshold must be > 0: {value}")
PY
runtime_assets_root="/fsx/references/runtime_assets"
references_root="/fsx/references"
reference_compat_root="/fsx/data"
environment_cache_root="/fsx/resources/environments"
work_root="/fsx/work"
run_mounts_root="/fsx/run_dir_mounts"
apptainer_deb="${runtime_assets_root}/cached_envs/apptainer_1.4.5_amd64.deb"
apptainer_deb_sha256="70f19af846501acfbc2e42e7cfeee9ee11ddbbfa1c3502d0d99cde34e8e0af05"
reference_wait_timeout_seconds=1800
reference_wait_interval_seconds=30
spot_lifecycle_state_dir="/var/lib/daylily/spot_lifecycle"
spot_lifecycle_state_file="${spot_lifecycle_state_dir}/metadata.env"

echo "[$timestamp] Running post_install_ubuntu_combined.sh ${region} ${boot_s3_uri} ${spot_price_warn_threshold} on $(hostname) as ${node_type}"
echo "[$timestamp] Local log: ${local_log_fn}"
if [ "${fsx_log_fn:-}" ]; then
  echo "[$timestamp] FSx log: ${fsx_log_fn}"
fi

aws configure set region $region

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

resolve_cluster_cache_namespace() {
  local stack_id
  local stack_generation
  if [ -z "${stack_name:-}" ]; then
    echo "ERROR: stack_name is required from /etc/parallelcluster/cfnconfig for the DayOA cache namespace" >&2
    return 1
  fi
  if [[ ! "${stack_name}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
    echo "ERROR: invalid ParallelCluster stack_name for the DayOA cache namespace: ${stack_name}" >&2
    return 1
  fi
  stack_id="$(aws cloudformation describe-stacks \
    --region "${region}" \
    --stack-name "${stack_name}" \
    --query 'Stacks[0].StackId' \
    --output text)"
  if [[ ! "${stack_id}" =~ ^arn:aws[^:]*:cloudformation:[^:]+:[0-9]+:stack/${stack_name}/[0-9a-f-]+$ ]]; then
    echo "ERROR: unable to resolve an immutable CloudFormation stack generation for ${stack_name}: ${stack_id}" >&2
    return 1
  fi
  stack_generation="${stack_id##*/}"
  printf '%s-%s\n' "${stack_name}" "${stack_generation}"
}

repair_compute_cluster_tags() {
  if [ "${cfn_node_type:-}" != "ComputeFleet" ]; then
    return 0
  fi
  local cluster_name_for_tags
  local token
  local instance_id
  cluster_name_for_tags="$(resolve_cluster_name_for_tags)"
  token="$(curl -fsS -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")"
  instance_id="$(curl -fsS -H "X-aws-ec2-metadata-token: ${token}" http://169.254.169.254/latest/meta-data/instance-id)"
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

repair_compute_cluster_tags

# Configure rclone to use AWS environment credentials in the current region
mkdir -p "$HOME/.config/rclone"
cat <<EOF > "$HOME/.config/rclone/rclone.conf"
[daylily]
type = s3
provider = AWS
env_auth = true
region = $region
EOF

# for sentieon
ulimit -n 16384

# Function to log spot price
log_spot_price() {

  TOKEN=$(curl -X PUT 'http://169.254.169.254/latest/api/token' -H 'X-aws-ec2-metadata-token-ttl-seconds: 21600')
  instance_type=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-type)
  instance_id=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
  availability_zone=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/availability-zone)

  # Get the current spot price for the running instance type in the specific AZ
  spot_price=$(aws ec2 describe-spot-price-history \
    --instance-types "$instance_type" \
    --region "$region" \
    --availability-zone "$availability_zone" \
    --product-description "Linux/UNIX" \
    --query 'SpotPriceHistory[0].SpotPrice' \
    --output text)

  # Log the spot price and AZ to a file in the FSx scratch directory
  log_file="/fsx/scratch/$(hostname)_spot_price.log"
  warn_log_file="/fsx/scratch/spot_price_warn_exception_messages.log"
  recorded_at="$(date -u '+%Y-%m-%d %H:%M:%S')"
  recorded_at_epoch="$(date -u +%s)"
  echo "${recorded_at} - Node type: ${node_type}, Partition: ${slurm_partition}, Compute resource: ${compute_resource}, Hostname: $(hostname), Instance id: ${instance_id}, Region: $region, AZ: $availability_zone, Instance type: $instance_type, Spot price: $spot_price USD/hour" >> "$log_file"
  write_spot_price_warn_exception \
    "${spot_price}" \
    "${spot_price_warn_threshold}" \
    "${warn_log_file}" \
    "${recorded_at}" \
    "${recorded_at_epoch}" \
    "${node_type}" \
    "${slurm_partition}" \
    "${compute_resource}" \
    "$(hostname)" \
    "${instance_id}" \
    "${region}" \
    "${availability_zone}" \
    "${instance_type}" \
    "${log_file}" \
    "$(resolve_cluster_name_for_tags)"

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

write_spot_price_warn_exception() {
  local spot_price="$1"
  local threshold="$2"
  local warn_log_file="$3"
  local recorded_at="$4"
  local recorded_at_epoch="$5"
  local current_node_type="$6"
  local current_partition="$7"
  local current_compute_resource="$8"
  local current_hostname="$9"
  local current_instance_id="${10}"
  local current_region="${11}"
  local current_availability_zone="${12}"
  local current_instance_type="${13}"
  local source_log_file="${14}"
  local current_cluster="${15}"

  if [ "${current_node_type}" != "ComputeFleet" ]; then
    return 0
  fi
  install -d -m 1777 "$(dirname "${warn_log_file}")"
  python3 - \
    "${spot_price}" \
    "${threshold}" \
    "${warn_log_file}" \
    "${recorded_at}" \
    "${recorded_at_epoch}" \
    "${current_node_type}" \
    "${current_partition}" \
    "${current_compute_resource}" \
    "${current_hostname}" \
    "${current_instance_id}" \
    "${current_region}" \
    "${current_availability_zone}" \
    "${current_instance_type}" \
    "${source_log_file}" \
    "${current_cluster}" <<'PY'
import json
import sys

spot_price = float(sys.argv[1])
threshold = float(sys.argv[2])
if spot_price <= threshold:
    raise SystemExit(0)

path = sys.argv[3]
row = {
    "schema_version": "dyec.spot_price_warn_exception.v1",
    "recorded_at": sys.argv[4],
    "recorded_at_epoch": sys.argv[5],
    "event": "node_start",
    "node_type": sys.argv[6],
    "slurm_partition": sys.argv[7],
    "compute_resource": sys.argv[8],
    "hostname": sys.argv[9],
    "instance_id": sys.argv[10],
    "region": sys.argv[11],
    "availability_zone": sys.argv[12],
    "instance_type": sys.argv[13],
    "spot_price_usd_per_hour": spot_price,
    "warn_threshold_usd_per_hour": threshold,
    "source_log_file": sys.argv[14],
    "cluster": sys.argv[15],
}
with open(path, "a", encoding="utf-8") as handle:
    handle.write(json.dumps(row, sort_keys=True) + "\n")
PY
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

install_sentieon_license_client_profile() {
  cat <<'EOF' > /etc/profile.d/daylily-sentieon-license.sh
# Managed by DAY-EC node setup. Sentieon clients use the dedicated regional service.
export SENTIEON_LICENSE="license.sentieon.lsmc.bio:8990"
EOF
  chmod 0644 /etc/profile.d/daylily-sentieon-license.sh
  stat -c "Sentieon license client profile: %A %U:%G %n" \
    /etc/profile.d/daylily-sentieon-license.sh
}

link_cached_entries() {
  local source_dir="$1"
  local dest_dir="$2"
  local requirement="${3:-required}"

  install -d -m 1777 "$dest_dir"
  shopt -s nullglob
  local source_paths=("${source_dir}"/*)
  shopt -u nullglob
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
  local start
  local elapsed
  start="$(date +%s)"
  echo "Waiting for required DayOA role entries from FSx DRAs"
  while true; do
    if [ -s "${apptainer_deb}" ] \
      && [ -s "${runtime_assets_root}/tool_specific_resources/cromwell_87.jar" ] \
      && [ -s "${runtime_assets_root}/tool_specific_resources/womtool_87.jar" ] \
      && [ -d "${references_root}/genomic_data" ]; then
      echo "Required DayOA role entries are visible"
      return 0
    fi

    elapsed="$(($(date +%s) - start))"
    if [ "${elapsed}" -ge "${reference_wait_timeout_seconds}" ]; then
      echo "ERROR: required DayOA role entries did not appear within ${reference_wait_timeout_seconds}s" >&2
      ls -la /fsx "${references_root}" "${runtime_assets_root}" "${runtime_assets_root}/cached_envs" "${runtime_assets_root}/tool_specific_resources" >&2 || true
      exit 1
    fi
    echo "DayOA role entries not visible yet after ${elapsed}s; sleeping ${reference_wait_interval_seconds}s"
    sleep "${reference_wait_interval_seconds}"
  done
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

prepare_reference_compat_symlink() {
  if [ -e "${reference_compat_root}" ] && [ ! -L "${reference_compat_root}" ]; then
    if [ "$(readlink -f "${reference_compat_root}")" != "${references_root}" ]; then
      echo "ERROR: reference compatibility path ${reference_compat_root} does not resolve to ${references_root}" >&2
      exit 1
    fi
  else
    ln -sfn "${references_root}" "${reference_compat_root}"
  fi

  if [ "$(readlink -f "${reference_compat_root}")" != "${references_root}" ]; then
    echo "ERROR: reference compatibility path ${reference_compat_root} does not resolve to ${references_root}" >&2
    exit 1
  fi
  stat -c "Reference compatibility path: %N" "${reference_compat_root}"
}

prepare_common_writable_dirs() {
  install -d -m 1777 /tmp/jobs
  if [ -d /fsx ]; then
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
  install -d -m 0775 -o ubuntu -g ubuntu /fsx/analysis_results/cromwell_executions
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
  stat -c "Writable DayOA result directory: %A %U:%G %n" \
    /fsx/analysis_results/ubuntu \
    /fsx/analysis_results/cromwell_executions \
    /fsx/analysis_results/daylily
  stat -c "Writable DayOA work directory: %A %U:%G %n" \
    "${work_root}/ubuntu" \
    "${work_root}/ubuntu/containers" \
    "${work_root}/ubuntu/nextflow" \
    "${work_root}/ubuntu/sarek" \
    "${work_root}/daylily" \
    "${work_root}/daylily/containers" \
    "${work_root}/daylily/nextflow" \
    "${work_root}/daylily/sarek"
}

prepare_dayoa_environment_cache() {
  local cluster_cache_namespace
  cluster_cache_namespace="$(resolve_cluster_cache_namespace)"
  local user_name

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

  for user_name in ubuntu daylily; do
    install -d -m 1777 \
      "${environment_cache_root}/conda/${user_name}/${cluster_cache_namespace}" \
      "${environment_cache_root}/containers/${user_name}/${cluster_cache_namespace}"
    if find "${environment_cache_root}/conda/${user_name}/${cluster_cache_namespace}" \
      -mindepth 1 -maxdepth 1 -type l -print -quit | grep -q .; then
      echo "ERROR: legacy linked Conda environments are forbidden in the cluster-scoped cache: ${environment_cache_root}/conda/${user_name}/${cluster_cache_namespace}" >&2
      exit 1
    fi
    link_cached_entries \
      "${runtime_assets_root}/cached_envs/containers" \
      "${environment_cache_root}/containers/${user_name}/${cluster_cache_namespace}" \
      optional
  done

  stat -c "Writable DayOA cache directory: %A %U:%G %n" \
    "${environment_cache_root}" \
    "${environment_cache_root}/apptainer" \
    "${environment_cache_root}/apptainer/cache/net" \
    "${environment_cache_root}/conda" \
    "${environment_cache_root}/containers" \
    "${environment_cache_root}/nextflow" \
    "${environment_cache_root}/conda/ubuntu/${cluster_cache_namespace}" \
    "${environment_cache_root}/containers/ubuntu/${cluster_cache_namespace}" \
    "${environment_cache_root}/conda/daylily/${cluster_cache_namespace}" \
    "${environment_cache_root}/containers/daylily/${cluster_cache_namespace}"
}

install_headnode_runtime_cache_profile() {
  local cluster_cache_namespace
  cluster_cache_namespace="$(resolve_cluster_cache_namespace)"
  cat > /etc/profile.d/daylily-cluster-cache-namespace.sh <<EOF
# Managed by DAY-EC node setup. ParallelCluster stack names are stable across node replacement.
export DAYOA_CLUSTER_CACHE_NAMESPACE="${cluster_cache_namespace}"
EOF
  chmod 0644 /etc/profile.d/daylily-cluster-cache-namespace.sh
  stat -c "DayOA cluster cache namespace profile: %A %U:%G %n" \
    /etc/profile.d/daylily-cluster-cache-namespace.sh

  cat <<'EOF' > /etc/profile.d/daylily-runtime-cache.sh
# Managed by DAY-EC headnode setup.
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
  stat -c "DayOA runtime cache profile: %A %U:%G %n" /etc/profile.d/daylily-runtime-cache.sh
}

install_s3_executable() {
  local s3_key="$1"
  local destination="$2"
  local temp_path

  temp_path="$(mktemp "${destination}.download.XXXXXX")"
  aws s3 cp "${boot_s3_uri}/${s3_key}" "${temp_path}"
  install -m 0755 "${temp_path}" "${destination}"
  rm -f "${temp_path}"
}

install_slurm_submission_policy() {
  install -d -m 0755 /opt/daylily/bin
  install_s3_executable \
    "install_slurm_job_submit_policy.sh" \
    /opt/daylily/bin/install_slurm_job_submit_policy
  /opt/daylily/bin/install_slurm_job_submit_policy "${region}" "${boot_s3_uri}"
}

install_slurm_job_hooks() {
  local prolog_dir="/opt/slurm/etc/scripts/prolog.d"
  local epilog_dir="/opt/slurm/etc/scripts/epilog.d"

  install -d -m 0755 "${prolog_dir}" "${epilog_dir}"
  cat <<'EOF' > "${prolog_dir}/50_daylily_job_tags"
#!/bin/bash
set -euo pipefail
install -d -m 1777 /tmp/jobs
echo "${SLURM_JOB_USER}" >> /tmp/jobs/jobs_users
echo "${SLURM_JOBID}" >> /tmp/jobs/jobs_ids
EOF

  cat <<'EOF' > "${epilog_dir}/50_daylily_job_tags"
#!/bin/bash
set -euo pipefail
sed -i "0,/${SLURM_JOB_USER}/d" /tmp/jobs/jobs_users 2>/dev/null || true
sed -i "0,/${SLURM_JOBID}/d" /tmp/jobs/jobs_ids 2>/dev/null || true
EOF

  chmod 0755 \
    "${prolog_dir}/50_daylily_job_tags" \
    "${epilog_dir}/50_daylily_job_tags"
}

install_global_pygraphviz() {
  python3 -m pip install --upgrade "pygraphviz==2.0.1"
  python3 - <<'PY'
import pygraphviz
print(f"pygraphviz global import OK: {pygraphviz.__version__}")
PY
}

# GLOBAL ACTIONS HeadNode and ComputeFleet

prepare_common_writable_dirs
wait_for_reference_data
make_role_data_read_only
prepare_reference_compat_symlink
install_sentieon_license_client_profile

# Configure hugepages and namespaces (common to both head and compute nodes)
echo "vm.nr_hugepages=2048" | tee -a /etc/sysctl.conf
echo "vm.hugetlb_shm_group=27" | tee -a /etc/sysctl.conf
echo "kernel.unprivileged_userns_clone=1" | tee /etc/sysctl.d/00-local-userns.conf
echo "user.max_user_namespaces=15076" | tee -a /etc/sysctl.conf
sysctl -p

# Ensure the user exists
adduser --uid 1002 --disabled-password --gecos "" daylily || echo "daylily user add failed"

log_spot_price
install_spot_lifecycle_hooks

# Update and install necessary packages
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y tmux emacs rclone parallel atop htop glances fd-find ripgrep docker.io \
                    build-essential libssl-dev uuid-dev libgpgme-dev squashfs-tools \
                    libseccomp-dev pkg-config openjdk-11-jdk wget unzip nasm yasm isal \
                    fuse2fs gocryptfs cpulimit golang-go numactl graphviz graphviz-dev python3-pip \
                    ca-certificates fonts-liberation libasound2 libatk-bridge2.0-0 \
                    libatk1.0-0 libc6 libcairo2 libcups2 libdbus-1-3 libexpat1 \
                    libfontconfig1 libgbm1 libglib2.0-0 libgtk-3-0 libnspr4 libnss3 \
                    libpango-1.0-0 libpangocairo-1.0-0 libstdc++6 libx11-6 \
                    libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 libxext6 \
                    libxfixes3 libxi6 libxrandr2 libxrender1 libxss1 libxtst6 xdg-utils
install_global_pygraphviz

# Install Apptainer from the FSx/S3-backed cache. Do not depend on live Launchpad/PPA reachability.
if [ ! -s "${apptainer_deb}" ]; then
  echo "ERROR: cached Apptainer deb not found: ${apptainer_deb}" >&2
  echo "Expected S3 source under runtime assets cached_envs/$(basename "${apptainer_deb}")" >&2
  exit 1
fi
echo "${apptainer_deb_sha256}  ${apptainer_deb}" | sha256sum -c -
apt-get install -y "${apptainer_deb}"
if command -v apptainer >/dev/null 2>&1 && ! command -v singularity >/dev/null 2>&1; then
  ln -sfn "$(command -v apptainer)" /usr/local/bin/singularity
fi
command -v apptainer
command -v singularity

# Install Cromwell and Go (using cached versions)
ln -sfn "${runtime_assets_root}/tool_specific_resources/cromwell_87.jar" /usr/local/bin/cromwell.jar
ln -sfn "${runtime_assets_root}/tool_specific_resources/womtool_87.jar" /usr/local/bin/womtool.jar
chmod a+r /usr/local/bin/cromwell.jar /usr/local/bin/womtool.jar


if [ "${cfn_node_type}" == "HeadNode" ];then

  echo "[$(date +%Y%m%d_%H%M%S)] Running HeadNode post-install actions"

  prepare_dayoa_environment_cache
  prepare_headnode_writable_dirs
  install_headnode_runtime_cache_profile
  echo "DayOA Conda environments use an empty cluster-scoped writable cache; container and Nextflow caches are seeded from ${runtime_assets_root}/cached_envs into ${environment_cache_root}"


  if [ ! -e /opt/slurm/sbin/sbatch ]; then
    mv /opt/slurm/bin/sbatch /opt/slurm/sbin/sbatch
  else
    echo "Original sbatch already present: /opt/slurm/sbin/sbatch"
  fi
  install_s3_executable "sbatch" /opt/slurm/bin/sbatch

  if [ ! -e /opt/slurm/sbin/srun ]; then
    mv /opt/slurm/bin/srun /opt/slurm/sbin/srun
  else
    echo "Original srun already present: /opt/slurm/sbin/srun"
  fi
  ln -sfn /opt/slurm/bin/sbatch /opt/slurm/bin/srun

  install_s3_executable "sleep_test.sh" /opt/slurm/bin/sleep_test.sh
  install_slurm_submission_policy
  touch /tmp/$(hostname).postslurmcfg
  
fi

# Tagging and Budget Bits

install -d -m 0755 /opt/slurm/sbin

# Cron script used to update the instance tags
cat <<'EOF' > /opt/slurm/sbin/check_tags.sh
#!/bin/bash

source /etc/profile
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
region=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region)
aws configure set region $region

update=0
tag_userid=""
tag_jobid=""

if [ ! -f /tmp/jobs/jobs_users ] || [ ! -f /tmp/jobs/jobs_ids ]; then
  exit 0
fi

active_users=$(cat /tmp/jobs/jobs_users | sort | uniq )
active_jobs=$(cat /tmp/jobs/jobs_ids | sort )
echo $active_users > /tmp/jobs/tmp_jobs_users
echo $active_jobs > /tmp/jobs/tmp_jobs_ids

if [ ! -f /tmp/jobs/tag_userid ] || [ ! -f /tmp/jobs/tag_jobid ]; then

  echo $active_users > /tmp/jobs/tag_userid
  echo $active_jobs > /tmp/jobs/tag_jobid
  update=1

else

  active_users=$(cat /tmp/jobs/tmp_jobs_users)
  active_jobs=$(cat /tmp/jobs/tmp_jobs_ids)
  tag_userid=$(cat /tmp/jobs/tag_userid)
  tag_jobid=$(cat /tmp/jobs/tag_jobid)
  
  if [ "${active_users}" != "${tag_userid}" ]; then
    tag_userid="${active_users}"
    echo ${tag_userid} > /tmp/jobs/tag_userid
    update=1
  fi
  
  if [ "${active_jobs}" != "${tag_jobid}" ]; then
    tag_jobid="${active_jobs}"
    echo ${tag_jobid} > /tmp/jobs/tag_jobid
    update=1
  fi

fi

if [ ${update} -eq 1 ]; then
  
  # Instance ID

  TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
  MyInstID=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
  tag_userid=$(cat /tmp/jobs/tag_userid)
  tag_jobid=$(cat /tmp/jobs/tag_jobid)
  aws ec2 create-tags --resources ${MyInstID} --tags Key=aws-parallelcluster-username,Value="${tag_userid}" --region ${region}
  aws ec2 create-tags --resources ${MyInstID} --tags Key=aws-parallelcluster-jobid,Value="${tag_jobid}" --region ${region}
fi

EOF

chmod a+x /opt/slurm/sbin/check_tags.sh

install_slurm_job_hooks

if [ "${cfn_node_type}" == "ComputeFleet" ];then

  # Create the folder used to save jobs information

  mkdir -p /tmp/jobs

  # Configure the script to run every minute
  echo "
* * * * * /opt/slurm/sbin/check_tags.sh
" | crontab -
fi



echo "Expanding /dev/shm to 80% of total memory"
# Calculate 80% of total memory
TOTAL_MEM=$(grep MemTotal /proc/meminfo | awk '{print $2}')  # in KB
SHM_SIZE_KB=$((TOTAL_MEM * 80 / 100))  # 80% of total memory

# Convert KB to MB
SHM_SIZE_MB=$((SHM_SIZE_KB / 1024))

# Remount /dev/shm with the new size
mount -o remount,size=${SHM_SIZE_MB}M /dev/shm

# Verify new size
echo "/dev/shm resized to 80% of total memory ( ${SHM_SIZE_MB} mb ) :"
df -h /dev/shm


# Finalization
touch /tmp/$(hostname).postinstallcomplete
echo "Post-installation complete."
exit 0
