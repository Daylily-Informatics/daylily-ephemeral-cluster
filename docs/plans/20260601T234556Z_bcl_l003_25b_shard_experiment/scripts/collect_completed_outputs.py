#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, wait_for_ssm_online

PROFILE = os.environ.get("PROFILE", "lsmc")
REGION = os.environ.get("REGION", "us-west-2")
CLUSTER = os.environ.get("CLUSTER", "dyec5117")
EXP_STAMP = os.environ.get("EXP_STAMP", "20260601T234556Z")
EXP_DIR = Path(os.environ.get("EXP_DIR", f"docs/plans/{EXP_STAMP}_bcl_l003_25b_shard_experiment"))
METADATA_DIR = EXP_DIR / "metadata"
BENCH_OUT = Path(os.environ.get("BENCH_OUT", "bench_expts"))


def sanitize(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")


def arm_sort_key(arm: str) -> tuple[int, int, str]:
    if arm == "whole_lane":
        return (0, 0, arm)
    if arm.startswith("whole_lane"):
        return (0, 1, arm)
    match = re.match(r"shard0*([0-9]+)(?:_|$)", arm)
    if match:
        return (1, int(match.group(1)), arm)
    return (2, 0, arm)


def read_analysis_ids() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for path in sorted(METADATA_DIR.glob("analysis_id_*.txt")):
        arm = path.name.removeprefix("analysis_id_").removesuffix(".txt")
        analysis_id = path.read_text(encoding="utf-8").strip()
        if analysis_id:
            rows.append((arm, analysis_id))
    return sorted(rows, key=lambda item: arm_sort_key(item[0]))


def read_status(arm: str) -> dict[str, object]:
    path = METADATA_DIR / f"status_{arm}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def split_benchmarks(stdout: str) -> list[tuple[str, str]]:
    benchmarks: list[tuple[str, str]] = []
    current_name: str | None = None
    current_lines: list[str] = []
    for line in stdout.splitlines():
        if line.startswith("__BENCH_FILE__\t"):
            if current_name is not None:
                benchmarks.append((current_name, "\n".join(current_lines).rstrip("\n") + "\n"))
            current_name = line.split("\t", 1)[1]
            current_lines = []
            continue
        if current_name is not None:
            current_lines.append(line)
    if current_name is not None:
        benchmarks.append((current_name, "\n".join(current_lines).rstrip("\n") + "\n"))
    return benchmarks


def main() -> int:
    arms = read_analysis_ids()
    if not arms:
        raise SystemExit(f"No analysis_id_*.txt files found under {METADATA_DIR}")

    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=180)

    BENCH_OUT.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, str]] = []
    deletion_rows: list[dict[str, str]] = []

    for arm, analysis_id in arms:
        status = read_status(arm)
        exit_code = status.get("exit_code")
        completed_at = str(status.get("completed_at") or "")
        started_at = str(status.get("started_at") or "")
        analysis_dir = f"/fsx/analysis_results/ubuntu/{analysis_id}"
        remote_root = f"{analysis_dir}/daylily-omics-analysis"
        script = f"""
set -euo pipefail
ANALYSIS_DIR={analysis_dir!r}
ROOT={remote_root!r}
if [[ ! -d "$ROOT" ]]; then
  echo "missing_root=$ROOT" >&2
  exit 0
fi
analysis_bytes="$(du -sb "$ANALYSIS_DIR" | awk '{{print $1}}')"
printf '__ANALYSIS_BYTES__\\t%s\\n' "$analysis_bytes"
find "$ROOT" -type f -name '*.bench.tsv' | sort | while read -r f; do
  rel="${{f#$ROOT/}}"
  printf '__BENCH_FILE__\\t%s\\n' "$rel"
  cat "$f"
done
"""
        result = run_shell(
            target.instance_id,
            REGION,
            script,
            profile=PROFILE,
            timeout=300,
            comment=f"Collect all Snakemake benchmark TSVs for {arm}",
        )
        (BENCH_OUT / f"{sanitize(arm)}__collect.stdout.txt").write_text(result.stdout, encoding="utf-8")
        (BENCH_OUT / f"{sanitize(arm)}__collect.stderr.txt").write_text(result.stderr, encoding="utf-8")
        analysis_bytes = 0
        for line in result.stdout.splitlines():
            if line.startswith("__ANALYSIS_BYTES__\t"):
                analysis_bytes = int(line.split("\t", 1)[1])
                break
        bench_count = 0
        for rel_path, content in split_benchmarks(result.stdout):
            local_name = f"{sanitize(arm)}__{sanitize(rel_path)}"
            if not local_name.endswith(".tsv"):
                local_name += ".tsv"
            local_path = BENCH_OUT / local_name
            local_path.write_text(content, encoding="utf-8")
            bench_count += 1
            manifest_rows.append(
                {
                    "arm": arm,
                    "analysis_id": analysis_id,
                    "exit_code": "" if exit_code is None else str(exit_code),
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "remote_root": remote_root,
                    "remote_benchmark": f"{remote_root}/{rel_path}",
                    "local_benchmark": str(local_path),
                    "local_bytes": str(local_path.stat().st_size),
                }
            )
        deletion_rows.append(
            {
                "arm": arm,
                "analysis_id": analysis_id,
                "exit_code": "" if exit_code is None else str(exit_code),
                "completed_at": completed_at,
                "benchmarks_collected": str(bench_count),
                "analysis_bytes": str(analysis_bytes),
                "analysis_gib": f"{analysis_bytes / 1024**3:.6f}",
                "deletion_path": analysis_dir,
                "repo_path": remote_root,
            }
        )

    with (BENCH_OUT / "manifest.tsv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "arm",
            "analysis_id",
            "exit_code",
            "started_at",
            "completed_at",
            "remote_root",
            "remote_benchmark",
            "local_benchmark",
            "local_bytes",
        ]
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fields)
        writer.writeheader()
        writer.writerows(manifest_rows)

    with (BENCH_OUT / "deletion_candidates.tsv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "arm",
            "analysis_id",
            "exit_code",
            "completed_at",
            "benchmarks_collected",
            "analysis_bytes",
            "analysis_gib",
            "deletion_path",
            "repo_path",
        ]
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fields)
        writer.writeheader()
        writer.writerows(deletion_rows)

    print(f"benchmarks_collected={len(manifest_rows)}")
    print(f"arms={','.join(arm for arm, _ in arms)}")
    print(f"manifest={BENCH_OUT / 'manifest.tsv'}")
    print(f"deletion_candidates={BENCH_OUT / 'deletion_candidates.tsv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
