#!/bin/bash

# Path to your XMRig binary and options
XMRIG_PATH_AND_OPTS=$1
# User running XMRig
USER="ubuntu"

# Function to start XMRig
start_xmrig() {
    if ! pgrep -u $USER xmrig > /dev/null; then
        echo "Starting XMRig with $1 threads..."
        export MINE_CPU=$1
        $XMRIG_PATH_AND_OPTS > /fsx/miners/logs/${hostname}_xmrig_run.log &
    fi
}

# Function to stop XMRig
stop_xmrig() {
    if pgrep -u $USER xmrig > /dev/null; then
        echo "Stopping XMRig..."
        pkill -u $USER xmrig
    fi
}

# Main logic
while true; do
    # Number of total CPUs
    total_cpus=$(nproc)

    # Get the total number of busy CPUs allocated by SLURM
    busy_cpus=$(squeue --noheader --format="%C" | awk '{s+=$1} END {print s}')
    busy_cpus=${busy_cpus:-0}  # Default to 0 if no jobs are running
    
    # Calculate available CPUs
    available_cpus=$((total_cpus - busy_cpus - 1))

    # Adjust XMRig based on available CPUs
    if [ "$available_cpus" -gt 0 ]; then
        start_xmrig "$available_cpus"
    else
        stop_xmrig
    fi

    # Sleep for a specified interval before checking again
    sleep 333

    stop_xmrig

done
