#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, wait_for_ssm_online


PROFILE = os.environ.get("PROFILE", "lsmc")
REGION = os.environ.get("REGION", "us-west-2")
CLUSTER = os.environ.get("CLUSTER", "dyec5117")
EXP_DIR = Path(
    os.environ.get(
        "EXP_DIR",
        "docs/plans/20260602T115314Z_bcl_full_25b_shard008_experiment",
    )
)


def main() -> int:
    out_dir = EXP_DIR / "live_status"
    out_dir.mkdir(parents=True, exist_ok=True)

    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=180)

    remote_script = r'''
set -euo pipefail
echo "__HEADNODE__"
hostname
date -u +%Y-%m-%dT%H:%M:%SZ
echo "__SQUEUE__"
squeue -h -o '%i\t%P\t%T\t%M\t%N\t%j' -p i192mem || true
echo "__NODES__"
nodes="$(squeue -h -o '%N' -p i192mem | tr ',' '\n' | sed '/^$/d' | sort -u)"
printf '%s\n' "$nodes"
echo "__NODE_SNAPSHOTS__"
for node in $nodes; do
  printf '__NODE__\t%s\n' "$node"
  ssh -o BatchMode=yes -o ConnectTimeout=8 "$node" 'bash -lc '"'"'
set -euo pipefail
read_cpu() {
  awk "/^cpu / {print \$2+\$3+\$4+\$5+\$6+\$7+\$8, \$5+\$6}" /proc/stat
}
read_net() {
  awk "NR>2 {gsub(\":\",\"\",\$1); if (\$1 != \"lo\") {rx+=\$2; tx+=\$10}} END {printf \"%d %d\", rx, tx}" /proc/net/dev
}
read_disk() {
  awk "{r+=\$6*512; w+=\$10*512} END {printf \"%d %d\", r, w}" /proc/diskstats
}
read cput0 cpuidle0 < <(read_cpu)
read rx0 tx0 < <(read_net)
read rd0 wr0 < <(read_disk)
sleep 3
read cput1 cpuidle1 < <(read_cpu)
read rx1 tx1 < <(read_net)
read rd1 wr1 < <(read_disk)
dt=$((cput1-cput0))
didle=$((cpuidle1-cpuidle0))
if [[ "$dt" -gt 0 ]]; then cpu_busy=$(awk -v dt="$dt" -v idle="$didle" "BEGIN {printf \"%.1f\", 100*(dt-idle)/dt}"); else cpu_busy=NA; fi
printf "hostname\t%s\n" "$(hostname)"
printf "loadavg\t%s\n" "$(cat /proc/loadavg)"
printf "nproc\t%s\n" "$(nproc)"
printf "cpu_busy_pct_3s\t%s\n" "$cpu_busy"
awk "/MemTotal|MemAvailable/ {print tolower(\$1) \"\t\" \$2}" /proc/meminfo
df -h /fsx /dev/shm /tmp 2>/dev/null | awk "NR==1 {print \"df_header\t\" \$0; next} {print \"df\t\" \$0}"
awk -v rx0="$rx0" -v tx0="$tx0" -v rx1="$rx1" -v tx1="$tx1" "BEGIN {printf \"net_mib_per_s_3s\trx=%.1f\ttx=%.1f\n\", (rx1-rx0)/3/1024/1024, (tx1-tx0)/3/1024/1024}"
awk -v rd0="$rd0" -v wr0="$wr0" -v rd1="$rd1" -v wr1="$wr1" "BEGIN {printf \"block_mib_per_s_3s\tread=%.1f\twrite=%.1f\n\", (rd1-rd0)/3/1024/1024, (wr1-wr0)/3/1024/1024}"
ps -eo pid,comm,pcpu,pmem,args --sort=-pcpu | head -n 8 | sed "s/^/ps\t/"
'"'"'
done
'''

    result = run_shell(
        target.instance_id,
        REGION,
        remote_script,
        profile=PROFILE,
        timeout=180,
        comment="Read-only load and IO snapshot for active BCL shard nodes",
    )
    (out_dir / "node_load_io.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (out_dir / "node_load_io.stderr.txt").write_text(result.stderr, encoding="utf-8")
    (out_dir / "node_load_io.ssm.json").write_text(
        json.dumps(
            {
                "command_id": result.command_id,
                "instance_id": result.instance_id,
                "status": result.status,
                "response_code": result.response_code,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(result.stdout, end="")
    print(result.stderr, end="")
    return result.response_code


if __name__ == "__main__":
    raise SystemExit(main())
