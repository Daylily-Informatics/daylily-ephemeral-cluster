#!/usr/bin/env bash
set -euo pipefail

run_dir="/home/ubuntu/daylily-runs/ccv20260530r42_bclconvert_rc0_recheck"
session="ccv20260530r42_bclconvert_rc0_recheck"

echo "time=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "tmux:"
tmux has-session -t "=${session}" 2>/dev/null && echo running || echo absent
echo "status:"
cat "${run_dir}/status.json" || true
echo
echo "squeue:"
squeue -h -o '%i %P %C %t %N %m %M %j' || true
echo "log_tail:"
tail -n 160 "${run_dir}/tmux.log" || true
