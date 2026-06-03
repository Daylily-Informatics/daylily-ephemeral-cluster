#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import csv
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, wait_for_ssm_online

PROFILE = os.environ.get("PROFILE", "lsmc")
REGION = os.environ.get("REGION", "us-west-2")
CLUSTER = os.environ.get("CLUSTER", "dyec5117")
EXP_STAMP = os.environ.get("EXP_STAMP", "20260601T234556Z")
ANALYSIS_STAMP = os.environ.get("ANALYSIS_STAMP", EXP_STAMP)
EXP_DIR = Path(os.environ.get("EXP_DIR", f"docs/plans/{EXP_STAMP}_bcl_l003_25b_shard_experiment"))
ARM = os.environ["ARM"]
GIB = 1024**3


def fallback_max_output_bytes() -> int:
    candidates = Path("bench_expts/deletion_candidates.tsv")
    if not candidates.is_file():
        return 0
    rows = csv.DictReader(candidates.open(encoding="utf-8"), delimiter="\t")
    sizes: list[int] = []
    for row in rows:
        value = str(row.get("analysis_bytes") or "").strip()
        if value.isdigit():
            sizes.append(int(value))
    return max(sizes, default=0)


def parse_result(stdout: str) -> dict[str, object]:
    result: dict[str, object] = {"arm": ARM}
    output_sizes: list[dict[str, object]] = []
    for line in stdout.splitlines():
        if line.startswith("df_bytes\t"):
            _, size, used, avail, pcent, mount = line.split("\t", 5)
            result.update(
                {
                    "fsx_size_gib": int(size) / GIB,
                    "fsx_used_gib": int(used) / GIB,
                    "fsx_available_gib": int(avail) / GIB,
                    "fsx_use_pct": pcent,
                    "fsx_mount": mount,
                }
            )
        elif line.startswith("output_bytes\t"):
            _, size, path = line.split("\t", 2)
            output_sizes.append({"bytes": int(size), "path": path})
    result["existing_output_sizes"] = output_sizes
    max_existing = max((int(item["bytes"]) for item in output_sizes), default=0)
    baseline_source = "existing_outputs"
    if max_existing == 0:
        max_existing = fallback_max_output_bytes()
        baseline_source = "bench_expts/deletion_candidates.tsv"
    required = int(max_existing * 1.10)
    available = int(float(result.get("fsx_available_gib", 0.0)) * GIB)
    result["max_existing_output_gib"] = max_existing / GIB
    result["capacity_baseline_source"] = baseline_source
    result["required_available_gib"] = required / GIB
    result["fsx_capacity_ok"] = bool(required and available >= required)
    return result


def main() -> None:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=180)
    script = f"""
set -euo pipefail
echo "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
df -B1 /fsx | awk 'NR==2 {{ printf "df_bytes\\t%s\\t%s\\t%s\\t%s\\t%s\\n", $2, $3, $4, $5, $6 }}'
df -h /fsx | awk 'NR==2 {{ printf "df_human\\t%s\\t%s\\t%s\\t%s\\t%s\\n", $2, $3, $4, $5, $6 }}'
for d in /fsx/analysis_results/ubuntu/bcl25b_l003_*_{ANALYSIS_STAMP}/daylily-omics-analysis; do
  [ -d "$d" ] || continue
  bytes=$(du -sB1 "$d" | awk '{{print $1}}')
  printf 'output_bytes\\t%s\\t%s\\n' "$bytes" "$d"
done
"""
    remote = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        timeout=600,
        comment=f"Check FSx capacity before {ARM}",
    )
    result = parse_result(remote.stdout)
    metadata = EXP_DIR / "metadata"
    metadata.mkdir(parents=True, exist_ok=True)
    (metadata / f"fsx_capacity_prelaunch_{ARM}.stdout.txt").write_text(remote.stdout, encoding="utf-8")
    (metadata / f"fsx_capacity_prelaunch_{ARM}.stderr.txt").write_text(remote.stderr, encoding="utf-8")
    (metadata / f"fsx_capacity_prelaunch_{ARM}.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result.get("fsx_capacity_ok"):
        raise SystemExit("FSx capacity check failed: available space is below 1.10x the largest existing experiment output.")


if __name__ == "__main__":
    main()
