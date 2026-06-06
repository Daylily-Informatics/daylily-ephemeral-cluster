#!/usr/bin/env bash
set -euo pipefail

ps -u ubuntu -o pid=,ppid=,args= \
  | awk '/cp -- \/fsx\/run_dir_mounts\/ilmn-lh01121-b23ww2nlt4-fastq/ && /tmp\.\$\$/ && $2 == 1 {print $1}' \
  > /tmp/hyb_only_orphan_ilmn_cp_pids.txt
cat /tmp/hyb_only_orphan_ilmn_cp_pids.txt
if [ -s /tmp/hyb_only_orphan_ilmn_cp_pids.txt ]; then
  xargs kill < /tmp/hyb_only_orphan_ilmn_cp_pids.txt
fi
sleep 2
ps -u ubuntu -o pid=,ppid=,args= \
  | awk '/cp -- \/fsx\/run_dir_mounts\/ilmn-lh01121-b23ww2nlt4-fastq/ && /tmp\.\$\$/ {print}' || true
