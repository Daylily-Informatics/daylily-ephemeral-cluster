#!/bin/bash

# Source me!

mine_pool_ip=$1
wallet=$2
ncpu=$(nproc)

# Auto-detect number of CPUs and total memory
total_memory_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
total_memory_gb=$(echo "$total_memory_kb / 1024 / 1024" | bc)
huge_pages_count=$((2 * ncpus))  # Use 2GB per CPU for nr_hugepages


cd /fsx
mkdir -p miners/$(hostname)
cd miners/$(hostname)

# Skip the build process if xmrig is already present
if [[ -f ./xmrig ]]; then
    echo "XMRig already present, skipping build."
else
    sudo apt update
    sudo DEBIAN_FRONTEND=noninteractive apt install -y git build-essential cmake libuv1-dev libssl-dev libhwloc-dev \
    emacs tmux parallel fd-find glances htop libjemalloc-dev libmimalloc-dev msr-tools numactl

    sudo modprobe msr && sudo wrmsr -a 0xc0011020 0

    echo "vm.hugetlb_shm_group=$(id -g)" | sudo tee -a /etc/sysctl.conf
    echo "vm.nr_hugepages=$huge_pages_count" | sudo tee -a /etc/sysctl.conf
    sudo sh -c 'echo "* hard memlock unlimited" >> /etc/security/limits.conf'
    sudo sh -c 'echo "* soft memlock unlimited" >> /etc/security/limits.conf'
    sudo sysctl -p

    git clone https://github.com/xmrig/xmrig.git
    cd xmrig

    mkdir build
    cd build
    cmake ..
    make -j$(nproc)
fi
sudo chmod u-s ./xmrig

# Set memory and thread usage based on hardware
export MIMALLOC_LARGE_OS_PAGES=1
export MIMALLOC_RESERVE_HUGE_OS_PAGES=40
export OMP_NUM_THREADS=$ncpus
export OMP_PROC_BIND=close
export OMP_PLACES=cores
export OMP_DYNAMIC=FALSE
export OMP_SCHEDULE=static
export OMP_WAIT_POLICY=ACTIVE
export OMP_MAX_ACTIVE_LEVELS=1



chown -R ubuntu:ubuntu .
chown -R ubuntu:ubuntu ./


# Run XMRig as a daemon using nohup and redirect output to log file
## remove numactl --interleave=all from nice
su -c "nohup  nice -n 19 ./xmrig --huge-pages --cpu-priority=0 -o $mine_pool_ip -u $wallet -p "$(hostname)"  --donate-level 1 --cpu-max-threads-hint=90 --threads=$ncpus --retries=3 &" ubuntu


# Inform the user that XMRig is running in the background
echo "XMRig is now running in the background as a daemon. Logs are being written to xmrig.log."
echo "To stop XMRig, you can use 'killall xmrig' or 'pkill xmrig'."

exit 0
