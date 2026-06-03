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
echo "== nonempty run_bclconvert slurm files =="
find logs/slurm/run_bclconvert_tile_shard -type f -size +0 -printf '%s\\t%p\\n' | sort -n | tail -120 || true
echo
echo "== compact grep across run_bclconvert slurm files =="
grep -R -H -n -E 'error|Error|ERROR|failed|FAILED|Killed|OOM|Out Of Memory|No space|watchdog|timed out|timeout|cancelled|CANCELLED|exited|non-zero|Command exited|slurmstepd|Job.*failed|exit code' logs/slurm/run_bclconvert_tile_shard 2>/dev/null | tail -200 || true
echo
echo "== selected failure file tails =="
for f in \\
  logs/slurm/run_bclconvert_tile_shard/run_bclconvert_tile_shard.run_bclconvert_L002_0002_tiles0099-0196.14.err \\
  logs/slurm/run_bclconvert_tile_shard/run_bclconvert_tile_shard.run_bclconvert_L002_0002_tiles0099-0196.14.out \\
  logs/slurm/run_bclconvert_tile_shard/run_bclconvert_tile_shard.run_bclconvert_L008_0006_tiles0491-0588.72.err \\
  logs/slurm/run_bclconvert_tile_shard/run_bclconvert_tile_shard.run_bclconvert_L008_0006_tiles0491-0588.72.out
do
  echo "-- $f --"
  if [ -f "$f" ]; then
    tail -80 "$f"
  else
    echo "MISSING"
  fi
done
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
        timeout=120,
        comment="Compact selected Slurm BCL failure diagnostics",
    )
    (out_dir / "compact_slurm_failures.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (out_dir / "compact_slurm_failures.stderr.txt").write_text(result.stderr, encoding="utf-8")
    (out_dir / "compact_slurm_failures.ssm.json").write_text(
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
