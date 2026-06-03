#!/usr/bin/env bash
set -euo pipefail

nodes=(i192mem-dy-all-9 i192mem-dy-all-10)
for node in "${nodes[@]}"; do
  echo "=== $node ==="
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$node" 'set -euo pipefail
    hostname
    date -Is
    uptime || true
    df -h /fsx /dev/shm || true
    test -d /fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4 && echo run_mount=yes || echo run_mount=no
    systemctl is-active slurmd || true
    systemctl --no-pager --full status slurmd | sed -n "1,35p" || true
    ps -eo pid,ppid,stat,pcpu,pmem,etime,cmd --sort=-pcpu | head -n 25
    sudo journalctl -u slurmd -n 40 --no-pager || true
  ' || true
done
