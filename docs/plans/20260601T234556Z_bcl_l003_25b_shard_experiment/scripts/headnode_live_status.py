#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, wait_for_ssm_online

PROFILE = os.environ.get("PROFILE", "lsmc")
REGION = os.environ.get("REGION", "us-west-2")
CLUSTER = os.environ.get("CLUSTER", "dyec5117")
EXP_STAMP = os.environ.get("EXP_STAMP", "20260601T234556Z")
EXP_DIR = Path(os.environ.get("EXP_DIR", f"docs/plans/{EXP_STAMP}_bcl_l003_25b_shard_experiment"))


def main() -> None:
    out_dir = EXP_DIR / "live_status"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=180)
    script = """
set -euo pipefail
echo "__HOST_START__"
date -u +%Y-%m-%dT%H:%M:%SZ
hostname
id
echo "__HOST_END__"
echo "__SQUEUE_START__"
if command -v squeue >/dev/null 2>&1; then
  squeue -o '%.18i %.9P %.32j %.8u %.2t %.12M %.12l %.6D %R'
else
  echo "squeue not found"
fi
echo "__SQUEUE_END__"
echo "__PS_START__"
ps -eo pid,ppid,user,stat,lstart,etime,cmd --sort=start_time \
  | grep -E 'snakemake|day_run|bcl-convert|singularity|slurmstepd|bcl25b_l003|run_bclconvert' \
  | grep -v grep || true
echo "__PS_END__"
echo "__TMUX_START__"
if command -v tmux >/dev/null 2>&1; then
  tmux list-sessions 2>/dev/null || true
else
  echo "tmux not found"
fi
echo "__TMUX_END__"
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        timeout=120,
        comment="Read-only BCL experiment headnode queue and process status",
    )
    (out_dir / "headnode_live_status.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (out_dir / "headnode_live_status.stderr.txt").write_text(result.stderr, encoding="utf-8")
    print(result.stdout)
    if result.stderr:
        print(result.stderr)


if __name__ == "__main__":
    main()
