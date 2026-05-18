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
  mkdir -p /fsx/logs
  chmod -R a+wrx /fsx/logs
  fsx_log_fn="/fsx/logs/$(hostname)_${node_type_slug}_${timestamp}.log"
  exec > >(tee -a "${local_log_fn}" "${fsx_log_fn}") 2>&1
else
  exec > >(tee -a "${local_log_fn}") 2>&1
fi
trap 'rc=$?; echo "[$(date +%Y%m%d_%H%M%S)] ERROR rc=${rc} line=${LINENO}: ${BASH_COMMAND}"; exit ${rc}' ERR

touch /tmp/$(hostname).postinstallBEGIN

region="$1"
bucket="$2"  # specified in the cluster yaml, bucket-name, no s3:// prefix
apptainer_deb="/fsx/data/cached_envs/apptainer_1.4.5_amd64.deb"
apptainer_deb_sha256="70f19af846501acfbc2e42e7cfeee9ee11ddbbfa1c3502d0d99cde34e8e0af05"
reference_wait_timeout_seconds=1800
reference_wait_interval_seconds=30

echo "[$timestamp] Running post_install_ubuntu_combined.sh ${region} ${bucket} on $(hostname) as ${node_type}"
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

  mkdir -p "$dest_dir"
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
    fi
  done
}

wait_for_reference_data() {
  local start
  local elapsed
  start="$(date +%s)"
  echo "Waiting for required /fsx/data reference entries from the FSx DRA"
  while true; do
    if [ -s "${apptainer_deb}" ] \
      && [ -s /fsx/data/tool_specific_resources/cromwell_87.jar ] \
      && [ -s /fsx/data/tool_specific_resources/womtool_87.jar ] \
      && [ -d /fsx/data/cached_envs/conda ]; then
      echo "Required /fsx/data reference entries are visible"
      return 0
    fi

    elapsed="$(($(date +%s) - start))"
    if [ "${elapsed}" -ge "${reference_wait_timeout_seconds}" ]; then
      echo "ERROR: required /fsx/data reference entries did not appear within ${reference_wait_timeout_seconds}s" >&2
      ls -la /fsx /fsx/data /fsx/data/cached_envs /fsx/data/tool_specific_resources >&2 || true
      exit 1
    fi
    echo "Reference entries not visible yet after ${elapsed}s; sleeping ${reference_wait_interval_seconds}s"
    sleep "${reference_wait_interval_seconds}"
  done
}

make_reference_data_read_only() {
  if [ ! -d /fsx/data ]; then
    echo "ERROR: reference data directory not found: /fsx/data" >&2
    exit 1
  fi
  chmod a-w /fsx/data
  stat -c "Reference data permissions: %A %n" /fsx/data
}


# GLOBAL ACTIONS HeadNode and ComputeFleet

mkdir -p /tmp/jobs
chmod -R a+wrx /tmp/jobs
mkdir -p /fsx/scratch
chmod -R a+wrx /fsx/scratch
wait_for_reference_data
make_reference_data_read_only

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
apt-get install -y tmux emacs rclone parallel atop htop glances fd-find docker.io \
                    build-essential libssl-dev uuid-dev libgpgme-dev squashfs-tools \
                    libseccomp-dev pkg-config openjdk-11-jdk wget unzip nasm yasm isal \
                    fuse2fs gocryptfs cpulimit golang-go numactl

# Install Apptainer from the FSx/S3-backed cache. Do not depend on live Launchpad/PPA reachability.
if [ ! -s "${apptainer_deb}" ]; then
  echo "ERROR: cached Apptainer deb not found: ${apptainer_deb}" >&2
  echo "Expected S3 source: s3://${bucket}/data/cached_envs/$(basename "${apptainer_deb}")" >&2
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
ln -sfn /fsx/data/tool_specific_resources/cromwell_87.jar /usr/local/bin/cromwell.jar
ln -sfn /fsx/data/tool_specific_resources/womtool_87.jar /usr/local/bin/womtool.jar
chmod a+r /usr/local/bin/cromwell.jar /usr/local/bin/womtool.jar


if [ "${cfn_node_type}" == "HeadNode" ];then

  echo "[$(date +%Y%m%d_%H%M%S)] Running HeadNode post-install actions"
  

  # Create necessary directories
  mkdir -p /fsx/analysis_results/cromwell_executions  
  mkdir -p /fsx/analysis_results/ubuntu  
  mkdir -p /fsx/analysis_results/daylily              
  mkdir -p /fsx/tmp
  mkdir -p /fsx/scratch
  mkdir -p /fsx/resources/environments/containers/{ubuntu,daylily}/$(hostname)/
  mkdir -p /fsx/resources/environments/conda/{ubuntu,daylily}/$(hostname)/
  chmod -R a+wrx /fsx/analysis_results
  chmod -R a+wrx /fsx/scratch
  chmod -R a+wrx /fsx/tmp
  chmod -R a+wrx /fsx/resources


  # Copy cached data from S3

  link_cached_entries /fsx/data/cached_envs/conda /fsx/resources/environments/conda/ubuntu/$(hostname) required
  link_cached_entries /fsx/data/cached_envs/containers /fsx/resources/environments/containers/ubuntu/$(hostname) optional
  link_cached_entries /fsx/data/cached_envs/conda /fsx/resources/environments/conda/daylily/$(hostname) required
  link_cached_entries /fsx/data/cached_envs/containers /fsx/resources/environments/containers/daylily/$(hostname) optional


  if [ ! -e /opt/slurm/sbin/sbatch ]; then
    mv /opt/slurm/bin/sbatch /opt/slurm/sbin/sbatch
  else
    echo "Original sbatch already present: /opt/slurm/sbin/sbatch"
  fi
  aws s3 cp s3://${bucket}/cluster_boot_config/sbatch /opt/slurm/bin/sbatch
  chmod +x /opt/slurm/bin/sbatch

  if [ ! -e /opt/slurm/sbin/srun ]; then
    mv /opt/slurm/bin/srun /opt/slurm/sbin/srun
  else
    echo "Original srun already present: /opt/slurm/sbin/srun"
  fi
  ln -sfn /opt/slurm/bin/sbatch /opt/slurm/bin/srun

  aws s3 cp s3://${bucket}/cluster_boot_config/sleep_test.sh /opt/slurm/bin/sleep_test.sh
  chmod a+x /opt/slurm/bin/sleep_test.sh


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
