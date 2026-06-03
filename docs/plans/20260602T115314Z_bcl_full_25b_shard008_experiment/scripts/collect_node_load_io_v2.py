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
REMOTE_PROBE = "/home/ubuntu/daylily-runs/bcl25b_full_shard008_retry1_20260602T115314Z/node_load_io_probe.py"


COMPUTE_PROBE = r'''
import os
import socket
import subprocess
import time

def read_cpu():
    fields = open("/proc/stat", encoding="utf-8").readline().split()[1:]
    vals = [int(x) for x in fields]
    total = sum(vals)
    idle = vals[3] + vals[4]
    return total, idle

def read_net():
    rx = 0
    tx = 0
    for line in open("/proc/net/dev", encoding="utf-8").read().splitlines()[2:]:
        iface, data = line.split(":", 1)
        if iface.strip() == "lo":
            continue
        vals = data.split()
        rx += int(vals[0])
        tx += int(vals[8])
    return rx, tx

def read_disk():
    r = 0
    w = 0
    for line in open("/proc/diskstats", encoding="utf-8"):
        vals = line.split()
        if len(vals) < 14:
            continue
        name = vals[2]
        if name.startswith(("loop", "ram")):
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
print(f"hostname\t{socket.gethostname()}")
print(f"loadavg\t{open('/proc/loadavg', encoding='utf-8').read().strip()}")
print(f"nproc\t{os.cpu_count()}")
print(f"cpu_busy_pct_3s\t{cpu_busy}")
mem = {}
for line in open("/proc/meminfo", encoding="utf-8"):
    key, val = line.split(":", 1)
    if key in ("MemTotal", "MemAvailable"):
        mem[key] = int(val.split()[0])
print(f"memtotal_kib\t{mem.get('MemTotal', 0)}")
print(f"memavailable_kib\t{mem.get('MemAvailable', 0)}")
print(f"net_mib_per_s_3s\trx={(rx1-rx0)/3/1024/1024:.1f}\ttx={(tx1-tx0)/3/1024/1024:.1f}")
print(f"block_mib_per_s_3s\tread={(rd1-rd0)/3/1024/1024:.1f}\twrite={(wr1-wr0)/3/1024/1024:.1f}")
try:
    df = subprocess.check_output(["df", "-h", "/fsx", "/dev/shm", "/tmp"], text=True)
    for line in df.splitlines():
        print("df\t" + line)
except Exception as exc:
    print(f"df_error\t{exc}")
try:
    ps = subprocess.check_output(["ps", "-eo", "pid,comm,pcpu,pmem,args", "--sort=-pcpu"], text=True)
    for line in ps.splitlines()[:8]:
        print("ps\t" + line)
except Exception as exc:
    print(f"ps_error\t{exc}")
'''


HEADNODE_PROBE = f'''
import base64
import datetime
import shlex
import subprocess

compute_code = base64.b64decode({base64.b64encode(COMPUTE_PROBE.encode("utf-8")).decode("ascii")!r}).decode("utf-8")
compute_b64 = base64.b64encode(compute_code.encode("utf-8")).decode("ascii")
remote_cmd = "python3 -c " + shlex.quote("import base64; exec(base64.b64decode(%r))" % compute_b64)

print("__HEADNODE__")
print(subprocess.check_output(["hostname"], text=True).strip())
print(datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z")
print("__SQUEUE__")
squeue = subprocess.run(
    ["squeue", "-h", "-o", "%i\\t%P\\t%T\\t%M\\t%N\\t%j", "-p", "i192mem"],
    text=True,
    capture_output=True,
)
print(squeue.stdout, end="")
if squeue.stderr:
    print(squeue.stderr, end="")
nodes = []
for line in squeue.stdout.splitlines():
    parts = line.split("\\t")
    if len(parts) >= 5 and parts[4]:
        for node in parts[4].split(","):
            if node and node not in nodes:
                nodes.append(node)
nodes = sorted(nodes)
print("__NODES__")
for node in nodes:
    print(node)
print("__NODE_SNAPSHOTS__")
for node in nodes:
    print(f"__NODE__\\t{{node}}")
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", node, remote_cmd],
        text=True,
        capture_output=True,
        timeout=25,
    )
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print("stderr\\t" + proc.stderr.replace("\\n", "\\nstderr\\t"), end="")
    print(f"exit_code\\t{{proc.returncode}}")
'''


def main() -> int:
    out_dir = EXP_DIR / "live_status"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=180)
    write_remote_text(
        target.instance_id,
        REGION,
        REMOTE_PROBE,
        HEADNODE_PROBE,
        profile=PROFILE,
    )
    result = run_shell(
        target.instance_id,
        REGION,
        f"python3 {REMOTE_PROBE}",
        profile=PROFILE,
        timeout=240,
        comment="Read-only load and IO snapshot for active BCL shard nodes",
    )
    (out_dir / "node_load_io_v2.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (out_dir / "node_load_io_v2.stderr.txt").write_text(result.stderr, encoding="utf-8")
    (out_dir / "node_load_io_v2.ssm.json").write_text(
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
