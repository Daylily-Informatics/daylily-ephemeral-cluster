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
echo "== failed shard rule logs and BCL logs =="
for shard in \\
  L008.0007_tiles0589-0686 \\
  L002.0005_tiles0393-0490 \\
  L005.0002_tiles0099-0196
do
  lane="${{shard%%.*}}"
  rest="${{shard#*.}}"
  echo "## $shard"
  echo "-- BCL log tail --"
  bcl="results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/logs/run_bclconvert.${{shard}}.log"
  if [ -f "$bcl" ]; then
    tail -220 "$bcl"
  else
    echo "MISSING $bcl"
  fi
  echo "-- benchmark if any --"
  bench="results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/benchmarks/run_bclconvert.${{shard}}.bench.tsv"
  if [ -f "$bench" ]; then
    cat "$bench"
  else
    echo "MISSING $bench"
  fi
  echo "-- output/report presence --"
  find "results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/tile_fastqs/${{lane}}/${{rest}}" -maxdepth 3 -type f 2>/dev/null | sed -n '1,40p' || true
  find "results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert/tile_reports/${{lane}}/${{rest}}" -maxdepth 3 -type f 2>/dev/null | sed -n '1,40p' || true
  echo
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
        comment="Read-only terminal failed BCL shard logs",
    )
    (out_dir / "terminal_failed_bcl_logs.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (out_dir / "terminal_failed_bcl_logs.stderr.txt").write_text(result.stderr, encoding="utf-8")
    (out_dir / "terminal_failed_bcl_logs.ssm.json").write_text(
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
