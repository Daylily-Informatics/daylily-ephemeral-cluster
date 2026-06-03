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
ANALYSIS = "bcl25b_full_shard008_retry1_20260602T115314Z"
REPO = f"/fsx/analysis_results/ubuntu/{ANALYSIS}/daylily-omics-analysis"


REMOTE_SCRIPT = f"""set -euo pipefail
cd {REPO}
echo "timestamp_utc $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "repo {REPO}"
echo
echo "== workflow status file =="
if [ -f /home/ubuntu/daylily-runs/{ANALYSIS}/status.json ]; then
  cat /home/ubuntu/daylily-runs/{ANALYSIS}/status.json
fi
echo
echo "== current squeue failed/retry targets =="
squeue -h -o '%i|%T|%M|%N|%j' | grep -E 'L008_0006|L002_0002|run_bclconvert_tile_shard' | tail -80 || true
echo
echo "== recent controller error lines =="
if [ -f /home/ubuntu/daylily-runs/{ANALYSIS}/tmux.log ]; then
  grep -n -E 'Error in rule|cluster_jobid|non-zero|failed|FAILED|CANCELLED|TIMEOUT|Out Of Memory|oom|No space|watchdog' /home/ubuntu/daylily-runs/{ANALYSIS}/tmux.log | tail -120 || true
fi
echo
echo "== relevant BCL Convert log tails =="
for log in \\
  results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/logs/run_bclconvert.L008.0006_tiles0491-0588.log \\
  results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/logs/run_bclconvert.L002.0002_tiles0099-0196.log
do
  echo "-- $log --"
  if [ -f "$log" ]; then
    tail -160 "$log"
  else
    echo "MISSING"
  fi
done
echo
echo "== matching slurm/snakemake logs =="
find . -type f \\( -iname '*slurm*' -o -path '*/.snakemake/*' -o -path './logs/*' \\) \\
  | grep -E '(^|[^0-9])(95|96|209|210)([^0-9]|$)|L008.*0006|L002.*0002' \\
  | sort \\
  | head -100 || true
echo
echo "== slurm error/out summaries =="
if [ -d logs/slurm/run_bclconvert_tile_shard ]; then
  find logs/slurm/run_bclconvert_tile_shard -type f \\( -name '*.err' -o -name '*.out' \\) -print0 \\
    | xargs -0 grep -H -n -E 'error|Error|ERROR|failed|FAILED|Killed|OOM|Out Of Memory|No space|watchdog|timed out|timeout|cancelled|CANCELLED|exited|non-zero|Command exited' \\
    | tail -240 || true
fi
echo
echo "== selected slurm file tails =="
for f in \\
  logs/slurm/run_bclconvert_tile_shard/run_bclconvert_tile_shard.run_bclconvert_L002_0002_tiles0099-0196.14.err \\
  logs/slurm/run_bclconvert_tile_shard/run_bclconvert_tile_shard.run_bclconvert_L002_0002_tiles0099-0196.14.out \\
  logs/slurm/run_bclconvert_tile_shard/run_bclconvert_tile_shard.run_bclconvert_L008_0006_tiles0491-0588.72.err \\
  logs/slurm/run_bclconvert_tile_shard/run_bclconvert_tile_shard.run_bclconvert_L008_0006_tiles0491-0588.72.out
do
  echo "-- $f --"
  if [ -f "$f" ]; then
    tail -120 "$f"
  else
    echo "MISSING"
  fi
done
echo
echo "== sacct for visible job ids =="
if command -v sacct >/dev/null 2>&1; then
  sacct -j 95,96,209,210 --format=JobID,JobName%55,State,ExitCode,Elapsed,MaxRSS,NodeList -P || true
else
  echo "sacct missing"
fi
"""


def main() -> int:
    out_dir = EXP_DIR / "live_status"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=180)
    result = run_shell(
        target.instance_id,
        REGION,
        REMOTE_SCRIPT,
        profile=PROFILE,
        timeout=180,
        comment="Read-only failed BCL shard diagnostics",
    )
    (out_dir / "failed_job_diagnostics.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (out_dir / "failed_job_diagnostics.stderr.txt").write_text(result.stderr, encoding="utf-8")
    (out_dir / "failed_job_diagnostics.ssm.json").write_text(
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
