#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from daylily_ec.aws.ssm import (
    resolve_headnode_instance_id,
    run_shell,
    wait_for_ssm_online,
    write_remote_text,
)


PROFILE = os.environ.get("PROFILE", "lsmc")
REGION = os.environ.get("REGION", "us-west-2")
CLUSTER = os.environ.get("CLUSTER", "dyec5117")
EXP_DIR = Path(
    os.environ.get(
        "EXP_DIR",
        "docs/plans/20260602T115314Z_bcl_full_25b_shard008_experiment",
    )
)
REMOTE_PROBE = "/home/ubuntu/daylily-runs/bcl25b_full_shard008_retry1_20260602T115314Z/node_load_io_compact.py"


COMPUTE_PROBE = r'''
import os
import socket
import subprocess
import time

def read_cpu():
    vals = [int(x) for x in open("/proc/stat", encoding="utf-8").readline().split()[1:]]
    return sum(vals), vals[3] + vals[4]

def read_net():
    rx = tx = 0
    for line in open("/proc/net/dev", encoding="utf-8").read().splitlines()[2:]:
        iface, data = line.split(":", 1)
        if iface.strip() == "lo":
            continue
        vals = data.split()
        rx += int(vals[0])
        tx += int(vals[8])
    return rx, tx

def read_disk():
    r = w = 0
    for line in open("/proc/diskstats", encoding="utf-8"):
        vals = line.split()
        if len(vals) < 14 or vals[2].startswith(("loop", "ram")):
            continue
        r += int(vals[5]) * 512
        w += int(vals[9]) * 512
    return r, w

cpu0, idle0 = read_cpu()
rx0, tx0 = read_net()
rd0, wr0 = read_disk()
time.sleep(3)
cpu1, idle1 = read_cpu()
rx1, tx1 = read_net()
rd1, wr1 = read_disk()
dt = cpu1 - cpu0
didle = idle1 - idle0
cpu_busy = "NA" if dt <= 0 else f"{100 * (dt - didle) / dt:.1f}"
mem = {}
for line in open("/proc/meminfo", encoding="utf-8"):
    key, val = line.split(":", 1)
    if key in ("MemTotal", "MemAvailable"):
        mem[key] = int(val.split()[0])
proc = subprocess.check_output(["ps", "-eo", "comm=,pcpu="], text=True)
cpu_by_comm = {}
count_by_comm = {}
for line in proc.splitlines():
    parts = line.split()
    if len(parts) != 2:
        continue
    comm, pcpu = parts
    cpu_by_comm[comm] = cpu_by_comm.get(comm, 0.0) + float(pcpu)
    count_by_comm[comm] = count_by_comm.get(comm, 0) + 1
interesting = ["bcl-convert", "python", "singularity", "bash", "snakemake"]
print("\t".join([
    socket.gethostname(),
    open("/proc/loadavg", encoding="utf-8").read().split()[0],
    open("/proc/loadavg", encoding="utf-8").read().split()[1],
    open("/proc/loadavg", encoding="utf-8").read().split()[2],
    str(os.cpu_count()),
    cpu_busy,
    f"{mem.get('MemAvailable', 0)/1024/1024:.1f}",
    f"{(rx1-rx0)/3/1024/1024:.1f}",
    f"{(tx1-tx0)/3/1024/1024:.1f}",
    f"{(rd1-rd0)/3/1024/1024:.1f}",
    f"{(wr1-wr0)/3/1024/1024:.1f}",
] + [f"{name}_cpu={cpu_by_comm.get(name, 0.0):.1f}" for name in interesting]
  + [f"{name}_n={count_by_comm.get(name, 0)}" for name in interesting]))
'''


HEADNODE_PROBE = f'''
import base64
import datetime
import shlex
import subprocess

compute_code = base64.b64decode({base64.b64encode(COMPUTE_PROBE.encode("utf-8")).decode("ascii")!r}).decode("utf-8")
compute_b64 = base64.b64encode(compute_code.encode("utf-8")).decode("ascii")
remote_cmd = "python3 -c " + shlex.quote("import base64; exec(base64.b64decode(%r))" % compute_b64)

print("timestamp_utc\\t" + datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z")
squeue = subprocess.run(
    ["squeue", "-h", "-o", "%N", "-p", "i192mem"],
    text=True,
    capture_output=True,
)
nodes = []
for line in squeue.stdout.splitlines():
    for node in line.split(","):
        if node and node not in nodes:
            nodes.append(node)
nodes = sorted(nodes)
print("node\\tload1\\tload5\\tload15\\tnproc\\tcpu_busy_pct_3s\\tmem_avail_gib\\tnet_rx_mib_s\\tnet_tx_mib_s\\tblk_read_mib_s\\tblk_write_mib_s\\tbcl_cpu\\tpython_cpu\\tsingularity_cpu\\tbash_cpu\\tsnakemake_cpu\\tbcl_n\\tpython_n\\tsingularity_n\\tbash_n\\tsnakemake_n")
for node in nodes:
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", node, remote_cmd],
        text=True,
        capture_output=True,
        timeout=20,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        print(proc.stdout.strip())
    else:
        print(f"{{node}}\\tERROR\\t{{proc.returncode}}\\t{{proc.stderr.strip().replace(chr(9), ' ')}}")
'''


def main() -> int:
    out_dir = EXP_DIR / "live_status"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=180)
    write_remote_text(target.instance_id, REGION, REMOTE_PROBE, HEADNODE_PROBE, profile=PROFILE)
    result = run_shell(
        target.instance_id,
        REGION,
        f"python3 {REMOTE_PROBE}",
        profile=PROFILE,
        timeout=180,
        comment="Compact read-only load and IO snapshot for active BCL shard nodes",
    )
    (out_dir / "node_load_io_compact.tsv").write_text(result.stdout, encoding="utf-8")
    (out_dir / "node_load_io_compact.stderr.txt").write_text(result.stderr, encoding="utf-8")
    (out_dir / "node_load_io_compact.ssm.json").write_text(
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
