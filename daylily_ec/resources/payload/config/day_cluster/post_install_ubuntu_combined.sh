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
runtime_assets_root="/fsx/references/runtime_assets"
references_root="/fsx/references"
environment_cache_root="/fsx/resources/environments"
apptainer_deb="${runtime_assets_root}/cached_envs/apptainer_1.4.5_amd64.deb"
apptainer_deb_sha256="70f19af846501acfbc2e42e7cfeee9ee11ddbbfa1c3502d0d99cde34e8e0af05"
reference_wait_timeout_seconds=1800
reference_wait_interval_seconds=30
sbatch_wrapper_sha256="8c5d8eb0cb7f34784c872c4c70848fa442894165b7b5459cf6206a3f09c70369"
sleep_test_sha256="024531fc67ad8052a1660173d2b94ce83290baa63606099e887b0846aa3a4fae"
tailscale_authkey_ssm_parameter="/daylily/dayec/tailscale/headnode-authkey"

echo "[$timestamp] Running post_install_ubuntu_combined.sh ${region} ${boot_s3_uri} on $(hostname) as ${node_type}"
echo "[$timestamp] Local log: ${local_log_fn}"
if [ "${fsx_log_fn:-}" ]; then
  echo "[$timestamp] FSx log: ${fsx_log_fn}"
fi

aws configure set region $region

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
  echo "$(date '+%Y-%m-%d %H:%M:%S') - Region: $region, AZ: $availability_zone, Instance type: $instance_type, Spot price: $spot_price USD/hour" >> "$log_file"
}

append_once() {
  local line="$1"
  local file="$2"
  grep -Fxq "$line" "$file" 2>/dev/null || echo "$line" >> "$file"
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
      && [ -d "${runtime_assets_root}/cached_envs/conda" ] \
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

prepare_common_writable_dirs() {
  install -d -m 1777 /tmp/jobs
  if [ -d /fsx ]; then
    install -d -m 1777 /fsx/scratch /fsx/tmp "${environment_cache_root}"
    stat -c "Writable DayOA directory: %A %U:%G %n" /fsx/scratch /fsx/tmp "${environment_cache_root}"
  fi
}

prepare_headnode_writable_dirs() {
  install -d -m 0775 -o ubuntu -g ubuntu /fsx/analysis_results/ubuntu
  install -d -m 0775 -o ubuntu -g ubuntu /fsx/analysis_results/cromwell_executions
  install -d -m 0775 -o daylily -g daylily /fsx/analysis_results/daylily
  stat -c "Writable DayOA result directory: %A %U:%G %n" \
    /fsx/analysis_results/ubuntu \
    /fsx/analysis_results/cromwell_executions \
    /fsx/analysis_results/daylily
}

prepare_dayoa_environment_cache() {
  local host_name
  host_name="$(hostname)"
  local user_name

  install -d -m 1777 \
    "${environment_cache_root}/conda" \
    "${environment_cache_root}/containers"

  for user_name in ubuntu daylily; do
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

  stat -c "Writable DayOA cache directory: %A %U:%G %n" \
    "${environment_cache_root}" \
    "${environment_cache_root}/conda" \
    "${environment_cache_root}/containers" \
    "${environment_cache_root}/conda/ubuntu/${host_name}" \
    "${environment_cache_root}/containers/ubuntu/${host_name}" \
    "${environment_cache_root}/conda/daylily/${host_name}" \
    "${environment_cache_root}/containers/daylily/${host_name}"
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

install_tailscale_headnode() {
  if command -v tailscale >/dev/null 2>&1; then
    echo "Tailscale is already installed: $(command -v tailscale)"
    return 0
  fi

  if [ ! -r /etc/os-release ]; then
    echo "ERROR: /etc/os-release is required for Tailscale repository selection" >&2
    exit 1
  fi
  # shellcheck disable=SC1091
  . /etc/os-release
  if [ "${ID:-}" != "ubuntu" ] || [ "${VERSION_CODENAME:-}" != "jammy" ]; then
    echo "ERROR: DayEC Tailscale bootstrap expects Ubuntu jammy; got ${ID:-unknown}/${VERSION_CODENAME:-unknown}" >&2
    exit 1
  fi

  install -d -m 0755 /usr/share/keyrings
  curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/${VERSION_CODENAME}.noarmor.gpg" \
    -o /tmp/tailscale-archive-keyring.gpg
  install -m 0644 /tmp/tailscale-archive-keyring.gpg /usr/share/keyrings/tailscale-archive-keyring.gpg
  rm -f /tmp/tailscale-archive-keyring.gpg

  curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/${VERSION_CODENAME}.tailscale-keyring.list" \
    -o /tmp/tailscale.list
  install -m 0644 /tmp/tailscale.list /etc/apt/sources.list.d/tailscale.list
  rm -f /tmp/tailscale.list

  apt-get update
  apt-get install -y tailscale
}

tailscale_headnode_is_joined() {
  tailscale ip -4 >/dev/null 2>&1
}

configure_headnode_tailscale() {
  local authkey
  local tailscale_hostname
  local tailscale_up_rc

  echo "Configuring headnode Tailscale access"
  install_tailscale_headnode
  systemctl enable --now tailscaled

  if tailscale_headnode_is_joined; then
    echo "Tailscale is already joined on this headnode"
    return 0
  fi

  authkey="$(aws ssm get-parameter \
    --region "${region}" \
    --name "${tailscale_authkey_ssm_parameter}" \
    --with-decryption \
    --query 'Parameter.Value' \
    --output text)"
  if [ -z "${authkey}" ] || [ "${authkey}" = "None" ]; then
    echo "ERROR: empty Tailscale auth key from SSM parameter ${tailscale_authkey_ssm_parameter}" >&2
    exit 1
  fi

  tailscale_hostname="dayec-$(hostname)"
  set +e
  tailscale up \
    --auth-key="${authkey}" \
    --hostname="${tailscale_hostname}" \
    --accept-dns=false \
    --accept-routes=false
  tailscale_up_rc=$?
  set -e
  unset authkey
  if [ "${tailscale_up_rc}" -ne 0 ]; then
    echo "ERROR: tailscale up failed for headnode; verify SSM parameter ${tailscale_authkey_ssm_parameter} and tailnet ACL/tag policy" >&2
    exit "${tailscale_up_rc}"
  fi

  tailscale ip -4
}

# GLOBAL ACTIONS HeadNode and ComputeFleet

prepare_common_writable_dirs
wait_for_reference_data
make_role_data_read_only

# Configure hugepages and namespaces (common to both head and compute nodes)
echo "vm.nr_hugepages=2048" | tee -a /etc/sysctl.conf
echo "vm.hugetlb_shm_group=27" | tee -a /etc/sysctl.conf
echo "kernel.unprivileged_userns_clone=1" | tee /etc/sysctl.d/00-local-userns.conf
echo "user.max_user_namespaces=15076" | tee -a /etc/sysctl.conf
sysctl -p

# Ensure the user exists
adduser --uid 1002 --disabled-password --gecos "" daylily || echo "daylily user add failed"

log_spot_price

# Update and install necessary packages
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y tmux emacs rclone parallel atop htop glances fd-find ripgrep docker.io \
                    build-essential libssl-dev uuid-dev libgpgme-dev squashfs-tools \
                    libseccomp-dev pkg-config openjdk-11-jdk wget unzip nasm yasm isal \
                    fuse2fs gocryptfs cpulimit golang-go numactl

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
  

  prepare_headnode_writable_dirs
  prepare_dayoa_environment_cache
  echo "DayOA conda and container caches are seeded from ${runtime_assets_root}/cached_envs into ${environment_cache_root}"
  configure_headnode_tailscale


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


  # Restart SLURM Controller
  systemctl restart slurmctld
  touch /tmp/$(hostname).postslurmcfg
  
fi

# Tagging and Budget Bits

if [ "${cfn_node_type}" == "ComputeFleet" ];then

  # Create the folder used to save jobs information

  mkdir -p /tmp/jobs

  # Configure the script to run every minute
  echo "
* * * * * /opt/slurm/sbin/check_tags.sh
" | crontab -
  exit 0
else

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
tag_project=""

if [ ! -f /tmp/jobs/jobs_users ] || [ ! -f /tmp/jobs/jobs_ids ]; then
  exit 0
fi

active_users=$(cat /tmp/jobs/jobs_users | sort | uniq )
active_jobs=$(cat /tmp/jobs/jobs_ids | sort )
echo $active_users > /tmp/jobs/tmp_jobs_users
echo $active_jobs > /tmp/jobs/tmp_jobs_ids
if [ -f /tmp/jobs/jobs_projects ]; then
  active_projects=$(cat /tmp/jobs/jobs_projects | sort | uniq )
  echo $active_projects > /tmp/jobs/tmp_jobs_projects
fi


if [ ! -f /tmp/jobs/tag_userid ] || [ ! -f /tmp/jobs/tag_jobid ]; then

  echo $active_users > /tmp/jobs/tag_userid
  echo $active_jobs > /tmp/jobs/tag_jobid
  echo $active_projects > /tmp/jobs/tag_project
  update=1

else

  active_users=$(cat /tmp/jobs/tmp_jobs_users)
  active_jobs=$(cat /tmp/jobs/tmp_jobs_ids)
  if [ -f /tmp/jobs/tmp_jobs_projects ]; then
    active_projects=$(cat /tmp/jobs/tmp_jobs_projects)
  fi 
  tag_userid=$(cat /tmp/jobs/tag_userid)
  tag_jobid=$(cat /tmp/jobs/tag_jobid)
  if [ -f /tmp/jobs/tag_project ]; then
    tag_project=$(cat /tmp/jobs/tag_project)
  fi
  
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
  
  if [ "${active_projects}" != "${tag_project}" ]; then
    tag_project="${active_projects}"
    echo ${tag_project} > /tmp/jobs/tag_project
    update=1
  fi

fi

if [ ${update} -eq 1 ]; then
  
  # Instance ID

  TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
  MyInstID=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
  tag_userid=$(cat /tmp/jobs/tag_userid)
  tag_jobid=$(cat /tmp/jobs/tag_jobid)
  tag_project=$(cat /tmp/jobs/tag_project)
  aws ec2 create-tags --resources ${MyInstID} --tags Key=aws-parallelcluster-username,Value="${tag_userid}" --region ${region}
  aws ec2 create-tags --resources ${MyInstID} --tags Key=aws-parallelcluster-jobid,Value="${tag_jobid}" --region ${region}
  aws ec2 create-tags --resources ${MyInstID} --tags Key=aws-parallelcluster-project,Value="${tag_project}" --region ${region}  
fi

EOF

   chmod a+x /opt/slurm/sbin/check_tags.sh
   
   # Create Prolog and Epilog to tag the instances
   cat <<'EOF' > /opt/slurm/sbin/prolog.sh
#!/bin/bash

#slurm directory
export SLURM_ROOT=/opt/slurm
echo "${SLURM_JOB_USER}" >> /tmp/jobs/jobs_users
echo "${SLURM_JOBID}" >> /tmp/jobs/jobs_ids

#load the comment of the job.
Project=$($SLURM_ROOT/bin/scontrol show job ${SLURM_JOB_ID} | grep Comment | awk -F'=' '{print $2}')
Project_Tag=""
if [ ! -z "${Project}" ];then
  echo "${Project}" >> /tmp/jobs/jobs_projects
fi

EOF

   cat <<'EOF' > /opt/slurm/sbin/epilog.sh
#!/bin/bash
#slurm directory
export SLURM_ROOT=/opt/slurm
sed -i "0,/${SLURM_JOB_USER}/d" /tmp/jobs/jobs_users
sed -i "0,/${SLURM_JOBID}/d" /tmp/jobs/jobs_ids

#load the comment of the job.
Project=$($SLURM_ROOT/bin/scontrol show job ${SLURM_JOB_ID} | grep Comment | awk -F'=' '{print $2}')
Project_Tag=""
if [ ! -z "${Project}" ];then
  sed -i "0,/${Project}/d" /tmp/jobs/jobs_projects
fi

EOF

   chmod a+x /opt/slurm/sbin/prolog.sh
   chmod a+x /opt/slurm/sbin/epilog.sh
   
   # Configure slurm to use Prolog and Epilog
   append_once "PrologFlags=Alloc" /opt/slurm/etc/slurm.conf
   append_once "Prolog=/opt/slurm/sbin/prolog.sh" /opt/slurm/etc/slurm.conf
   append_once "Epilog=/opt/slurm/sbin/epilog.sh" /opt/slurm/etc/slurm.conf
   
   systemctl restart slurmctld
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
