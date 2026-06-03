#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
import os
import re
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, wait_for_ssm_online

PROFILE = os.environ.get("PROFILE", "lsmc")
REGION = os.environ.get("REGION", "us-west-2")
CLUSTER = os.environ.get("CLUSTER", "dyec5117")
RUNID = os.environ.get("RUNID", "20260514_LH01106_0009_B23TVLGLT4")
EXP_STAMP = os.environ.get("EXP_STAMP", "20260601T234556Z")
EXP_DIR = Path(os.environ.get("EXP_DIR", f"docs/plans/{EXP_STAMP}_bcl_l003_25b_shard_experiment"))
DERIVED_DIR = EXP_DIR / "derived"
HARVEST_ROOT = EXP_DIR / "harvested_benchmarks"
METADATA_DIR = EXP_DIR / "metadata"
GIB = 1024**3


def as_float(value: str | None) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def shard_level_for_arm(arm: str) -> str:
    if arm == "whole_lane" or arm.startswith("whole_lane_"):
        return "lane"
    match = re.match(r"shard0*([0-9]+)(?:_|$)", arm)
    if match:
        return str(int(match.group(1)))
    return ""


def arm_sort_key(arm: str) -> tuple[int, int | str]:
    if arm == "whole_lane":
        return (0, 0)
    level = shard_level_for_arm(arm)
    if level.isdigit():
        return (1, int(level), arm)
    return (2, 0, arm)


def read_benchmark_rows() -> dict[str, list[dict[str, str]]]:
    by_arm: dict[str, list[dict[str, str]]] = {}
    for arm_dir in sorted(HARVEST_ROOT.iterdir() if HARVEST_ROOT.exists() else []):
        bench_dir = arm_dir / "benchmarks"
        if not bench_dir.is_dir():
            continue
        for bench_path in sorted(bench_dir.glob("run_bclconvert.L003*.bench.tsv")):
            with bench_path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle, delimiter="\t"):
                    by_arm.setdefault(arm_dir.name, []).append(row)
    return by_arm


def analysis_id_for_arm(arm: str) -> str | None:
    path = METADATA_DIR / f"analysis_id_{arm}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return None


def bcl_dir_for_arm(arm: str) -> str | None:
    remote_paths = HARVEST_ROOT / arm / "remote_paths.txt"
    if remote_paths.exists():
        for line in remote_paths.read_text(encoding="utf-8").splitlines():
            if line.startswith("bcl_dir="):
                return line.split("=", 1)[1]
    analysis_id = analysis_id_for_arm(arm)
    if analysis_id:
        return f"/fsx/analysis_results/ubuntu/{analysis_id}/daylily-omics-analysis/results/runs/{RUNID}/bclconvert"
    return None


def discover_arms(extra_arms: list[str]) -> list[str]:
    arms = set(extra_arms)
    if HARVEST_ROOT.exists():
        arms.update(path.name for path in HARVEST_ROOT.iterdir() if path.is_dir())
    arms.update(path.name.removeprefix("analysis_id_").removesuffix(".txt") for path in METADATA_DIR.glob("analysis_id_*.txt"))
    return sorted(arms, key=arm_sort_key)


def fetch_fastq_sizes(arms: list[str]) -> None:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=180)
    for arm in arms:
        bcl_dir = bcl_dir_for_arm(arm)
        if not bcl_dir:
            continue
        script = f"""
set -euo pipefail
BCL_DIR={bcl_dir!r}
if [[ ! -d "$BCL_DIR" ]]; then
  echo "missing_bcl_dir=$BCL_DIR" >&2
  exit 0
fi
find "$BCL_DIR" -type f \\( -name '*.fastq.gz' -o -name '*.fq.gz' -o -name '*.fastq' -o -name '*.fq' \\) -printf '%s\\t%p\\n' | sort -k2,2
"""
        result = run_shell(
            target.instance_id,
            REGION,
            script,
            profile=PROFILE,
            timeout=300,
            comment=f"Measure BCL FASTQ sizes for {arm}",
        )
        arm_dir = HARVEST_ROOT / arm
        arm_dir.mkdir(parents=True, exist_ok=True)
        (arm_dir / "fastq_sizes.tsv").write_text(result.stdout, encoding="utf-8")
        (arm_dir / "fastq_sizes.stderr.txt").write_text(result.stderr, encoding="utf-8")


def fetch_fastq_totals(arms: list[str]) -> None:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=180)
    for arm in arms:
        bcl_dir = bcl_dir_for_arm(arm)
        if not bcl_dir:
            continue
        script = f"""
set -euo pipefail
BCL_DIR={bcl_dir!r}
if [[ ! -d "$BCL_DIR" ]]; then
  echo "missing_bcl_dir=$BCL_DIR" >&2
  exit 0
fi
printf 'scope\\tfastq_files\\tfastq_bytes\\tundetermined_fastq_files\\tundetermined_fastq_bytes\\n'
for scope in lane_fastqs tile_fastqs all; do
  case "$scope" in
    lane_fastqs) root="$BCL_DIR/lane_fastqs" ;;
    tile_fastqs) root="$BCL_DIR/tile_fastqs" ;;
    all) root="$BCL_DIR" ;;
  esac
  fastq_files=0
  fastq_bytes=0
  undetermined_fastq_files=0
  undetermined_fastq_bytes=0
  if [[ -d "$root" ]]; then
    while IFS= read -r -d '' f; do
      size="$(stat -c%s "$f")"
      fastq_files=$((fastq_files + 1))
      fastq_bytes=$((fastq_bytes + size))
      case "$(basename "$f")" in
        Undetermined*)
          undetermined_fastq_files=$((undetermined_fastq_files + 1))
          undetermined_fastq_bytes=$((undetermined_fastq_bytes + size))
          ;;
      esac
    done < <(find "$root" -type f \\( -name '*.fastq.gz' -o -name '*.fq.gz' -o -name '*.fastq' -o -name '*.fq' \\) -print0)
  fi
  printf '%s\\t%s\\t%s\\t%s\\t%s\\n' "$scope" "$fastq_files" "$fastq_bytes" "$undetermined_fastq_files" "$undetermined_fastq_bytes"
done
"""
        result = run_shell(
            target.instance_id,
            REGION,
            script,
            profile=PROFILE,
            timeout=300,
            comment=f"Measure compact BCL FASTQ totals for {arm}",
        )
        arm_dir = HARVEST_ROOT / arm
        arm_dir.mkdir(parents=True, exist_ok=True)
        (arm_dir / "fastq_totals.tsv").write_text(result.stdout, encoding="utf-8")
        (arm_dir / "fastq_totals.stderr.txt").write_text(result.stderr, encoding="utf-8")


def fastq_totals_for_arm(arm: str) -> dict[str, str]:
    totals_path = HARVEST_ROOT / arm / "fastq_totals.tsv"
    if totals_path.exists():
        lines = [
            line
            for line in totals_path.read_text(encoding="utf-8").splitlines()
            if line.startswith("scope\t") or line.startswith(("lane_fastqs\t", "tile_fastqs\t", "all\t"))
        ]
        rows = {
            row["scope"]: row
            for row in csv.DictReader(lines, delimiter="\t")
        }
        lane = rows.get("lane_fastqs", {})
        tile = rows.get("tile_fastqs", {})
        all_fastqs = rows.get("all", {})
        unmerged = tile if int(tile.get("fastq_files") or 0) else lane
        unmerged_bytes = int(unmerged.get("fastq_bytes") or 0)
        unmerged_undetermined_bytes = int(unmerged.get("undetermined_fastq_bytes") or 0)
        return {
            "lane_fastq_files": str(int(lane.get("fastq_files") or 0)),
            "lane_fastq_gib": f"{int(lane.get('fastq_bytes') or 0) / GIB:.6f}",
            "all_fastq_files": str(int(all_fastqs.get("fastq_files") or 0)),
            "all_fastq_gib": f"{int(all_fastqs.get('fastq_bytes') or 0) / GIB:.6f}",
            "unmerged_fastq_files": str(int(unmerged.get("fastq_files") or 0)),
            "unmerged_fastq_gib": f"{unmerged_bytes / GIB:.6f}",
            "unmerged_undetermined_fastq_files": str(int(unmerged.get("undetermined_fastq_files") or 0)),
            "unmerged_undetermined_fastq_gib": f"{unmerged_undetermined_bytes / GIB:.6f}",
            "unmerged_assigned_fastq_gib": f"{(unmerged_bytes - unmerged_undetermined_bytes) / GIB:.6f}",
        }
    path = HARVEST_ROOT / arm / "fastq_sizes.tsv"
    lane_bytes = 0
    all_bytes = 0
    lane_files = 0
    all_files = 0
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            if "\t" not in line:
                continue
            size_text, file_path = line.split("\t", 1)
            if not size_text.isdigit():
                continue
            size = int(size_text)
            all_bytes += size
            all_files += 1
            if "/lane_fastqs/" in file_path:
                lane_bytes += size
                lane_files += 1
    return {
        "lane_fastq_files": str(lane_files),
        "lane_fastq_gib": f"{lane_bytes / GIB:.6f}",
        "all_fastq_files": str(all_files),
        "all_fastq_gib": f"{all_bytes / GIB:.6f}",
        "unmerged_fastq_files": "0",
        "unmerged_fastq_gib": "0.000000",
        "unmerged_undetermined_fastq_files": "0",
        "unmerged_undetermined_fastq_gib": "0.000000",
        "unmerged_assigned_fastq_gib": "0.000000",
    }


def summarize_arm(arm: str, rows: list[dict[str, str]]) -> dict[str, str]:
    seconds = [as_float(row.get("s") or row.get("seconds")) for row in rows]
    threads = [as_float(row.get("snakemake_threads") or row.get("threads")) for row in rows]
    cpu_time = [as_float(row.get("cpu_time")) for row in rows]
    max_rss_gib = [as_float(row.get("max_rss")) / 1024.0 for row in rows]
    io_in = [as_float(row.get("io_in")) for row in rows]
    io_out = [as_float(row.get("io_out")) for row in rows]
    total_cost = sum(as_float(row.get("task_cost")) for row in rows)
    total_vcpu = sum(threads)
    allocated_vcpu_hours = sum(sec * thr / 3600.0 for sec, thr in zip(seconds, threads))
    total_runtime = sum(seconds)
    total_cpu_time = sum(cpu_time)
    avg_cpu_cores = total_cpu_time / total_runtime if total_runtime else 0.0
    avg_cpu_eff = (total_cpu_time / sum(sec * thr for sec, thr in zip(seconds, threads)) * 100.0) if allocated_vcpu_hours else 0.0
    return {
        "arm": arm,
        "shard_level": shard_level_for_arm(arm),
        "demux_tasks": str(len(rows)),
        "total_vcpu": f"{total_vcpu:.0f}",
        "allocated_vcpu_hours": f"{allocated_vcpu_hours:.6f}",
        "total_cost": f"{total_cost:.6f}",
        "cost_per_total_vcpu": f"{(total_cost / total_vcpu) if total_vcpu else 0.0:.8f}",
        "cost_per_allocated_vcpu_hour": f"{(total_cost / allocated_vcpu_hours) if allocated_vcpu_hours else 0.0:.8f}",
        "critical_wall_minutes": f"{(max(seconds) / 60.0) if seconds else 0.0:.6f}",
        "avg_task_minutes": f"{(sum(seconds) / len(seconds) / 60.0) if seconds else 0.0:.6f}",
        "avg_cpu_cores": f"{avg_cpu_cores:.6f}",
        "avg_cpu_efficiency_pct": f"{avg_cpu_eff:.6f}",
        "avg_max_rss_gib": f"{(sum(max_rss_gib) / len(max_rss_gib)) if max_rss_gib else 0.0:.6f}",
        "max_rss_gib": f"{max(max_rss_gib) if max_rss_gib else 0.0:.6f}",
        "avg_io_in": f"{(sum(io_in) / len(io_in)) if io_in else 0.0:.6f}",
        "avg_io_out": f"{(sum(io_out) / len(io_out)) if io_out else 0.0:.6f}",
        "total_io_in": f"{sum(io_in):.6f}",
        "total_io_out": f"{sum(io_out):.6f}",
        "instance_types": ",".join(sorted({row.get("instance_type", "") for row in rows if row.get("instance_type", "")})),
        "hostnames": ",".join(sorted({row.get("hostname", "") for row in rows if row.get("hostname", "")})),
        **fastq_totals_for_arm(arm),
    }


def write_tsv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def print_markdown(rows: list[dict[str, str]]) -> None:
    fields = [
        ("arm", "Arm"),
        ("total_vcpu", "Total vCPU"),
        ("total_cost", "Cost"),
        ("cost_per_allocated_vcpu_hour", "$/vCPU-h"),
        ("avg_cpu_efficiency_pct", "Avg CPU eff %"),
        ("avg_max_rss_gib", "Avg RSS GiB"),
        ("avg_io_in", "Avg io_in"),
        ("avg_io_out", "Avg io_out"),
        ("instance_types", "Instances"),
        ("unmerged_fastq_gib", "Unmerged FASTQ GiB"),
        ("unmerged_undetermined_fastq_gib", "Unassigned GiB"),
        ("lane_fastq_gib", "Lane FASTQ GiB"),
    ]
    print("| " + " | ".join(label for _, label in fields) + " |")
    print("|" + "|".join("---" for _ in fields) + "|")
    for row in rows:
        values = []
        for key, _ in fields:
            value = row.get(key, "")
            if key in {
                "total_cost",
                "cost_per_allocated_vcpu_hour",
                "avg_cpu_efficiency_pct",
                "avg_max_rss_gib",
                "avg_io_in",
                "avg_io_out",
                "unmerged_fastq_gib",
                "unmerged_undetermined_fastq_gib",
                "lane_fastq_gib",
            }:
                value = f"{float(value):.4f}"
            values.append(value)
        print("| " + " | ".join(values) + " |")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-fastq-sizes", action="store_true")
    parser.add_argument("--fetch-fastq-totals", action="store_true")
    parser.add_argument("--arm", action="append", default=[])
    args = parser.parse_args()

    arms = discover_arms(args.arm)
    if args.fetch_fastq_sizes:
        fetch_fastq_sizes(arms)
    if args.fetch_fastq_sizes or args.fetch_fastq_totals:
        fetch_fastq_totals(arms)

    by_arm = read_benchmark_rows()
    rows = [summarize_arm(arm, by_arm[arm]) for arm in sorted(by_arm, key=arm_sort_key)]
    fields = [
        "arm",
        "shard_level",
        "demux_tasks",
        "total_vcpu",
        "allocated_vcpu_hours",
        "total_cost",
        "cost_per_total_vcpu",
        "cost_per_allocated_vcpu_hour",
        "critical_wall_minutes",
        "avg_task_minutes",
        "avg_cpu_cores",
        "avg_cpu_efficiency_pct",
        "avg_max_rss_gib",
        "max_rss_gib",
        "avg_io_in",
        "avg_io_out",
        "total_io_in",
        "total_io_out",
        "instance_types",
        "hostnames",
        "lane_fastq_files",
        "lane_fastq_gib",
        "all_fastq_files",
        "all_fastq_gib",
        "unmerged_fastq_files",
        "unmerged_fastq_gib",
        "unmerged_undetermined_fastq_files",
        "unmerged_undetermined_fastq_gib",
        "unmerged_assigned_fastq_gib",
    ]
    write_tsv(DERIVED_DIR / "shard_resource_table.tsv", rows, fields)
    print_markdown(rows)


if __name__ == "__main__":
    main()
