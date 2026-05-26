from __future__ import annotations

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, wait_for_ssm_online


PROFILE = "lsmc"
REGION = "us-west-2"
CLUSTER = "tstClu-4-1-1c"

SCRIPT = r"""
set -euo pipefail
echo "probe_started=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "user=$(whoami)"
echo "host=$(hostname)"
echo "pwd=$(pwd)"
echo "PATH=$PATH"
echo "--- df ---"
df -h /fsx
echo "--- mounts ---"
findmnt /fsx || true
findmnt /data || true
echo "--- tools ---"
command -v day-clone
command -v dyec
command -v sbatch
command -v squeue
command -v sinfo
echo "--- slurm partitions ---"
sinfo -h -o '%P|%a|%D|%c|%m|%G'
echo "--- slurm queue ---"
squeue -h || true
echo "--- data dirs ---"
ls -ld /fsx /data /fsx/data /fsx/analysis_results || true
echo "--- versions ---"
dyec version || true
echo "probe_completed=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
"""


target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=600, poll_interval=10)
result = run_shell(
    target.instance_id,
    REGION,
    SCRIPT,
    profile=PROFILE,
    timeout=300,
    poll_interval=5,
    comment=f"Probe {CLUSTER} headnode",
)
print(result.stdout)
if result.stderr:
    print("--- stderr ---")
    print(result.stderr)
