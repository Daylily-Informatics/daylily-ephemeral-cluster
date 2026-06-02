#!/usr/bin/env python3
from __future__ import annotations

import csv
import math
import os
import re
from pathlib import Path
from statistics import median

RUNID = os.environ.get("RUNID", "20260514_LH01106_0009_B23TVLGLT4")
EXP_STAMP = os.environ.get("EXP_STAMP", "20260601T234556Z")
EXP_DIR = Path(os.environ.get("EXP_DIR", f"docs/plans/{EXP_STAMP}_bcl_l003_25b_shard_experiment"))
DERIVED_DIR = EXP_DIR / "derived"
REPORT = EXP_DIR / "report.md"
LANE_TILE_COUNT = int(os.environ.get("LANE_TILE_COUNT", "784"))

ARM_CAPACITY = {
    "whole_lane": (8, 1536, 8),
}


def as_float(value: str | None) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def parse_tile_span(path: Path) -> tuple[str, int | None, int | None, int]:
    name = path.name
    match = re.search(r"L003\.([0-9]{4})_tiles([0-9]+)-([0-9]+)\.bench\.tsv$", name)
    if match:
        start = int(match.group(2))
        end = int(match.group(3))
        return match.group(1), start, end, end - start + 1
    return "lane", None, None, LANE_TILE_COUNT


def shard_level_for_arm(arm: str) -> str:
    if arm == "whole_lane" or arm.startswith("whole_lane_"):
        return "lane"
    match = re.match(r"shard0*([0-9]+)(?:_|$)", arm)
    if not match:
        return ""
    return str(int(match.group(1)))


def arm_sort_key(arm: str) -> tuple[int, int | str]:
    if arm == "whole_lane":
        return (0, 0)
    level = shard_level_for_arm(arm)
    if level.isdigit():
        return (1, int(level), arm)
    return (2, 0, arm)


def full8_capacity_for_arm(arm: str) -> tuple[int, int, int]:
    if arm == "whole_lane" or arm.startswith("whole_lane_"):
        return (8, 1536, 8)
    if arm in ARM_CAPACITY:
        return ARM_CAPACITY[arm]
    level = shard_level_for_arm(arm)
    if not level.isdigit():
        return (0, 0, 0)
    jobs = int(level) * 8
    threads = jobs * 48
    nodes = math.ceil(threads / 192)
    return jobs, threads, nodes


def read_task_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    harvest_root = EXP_DIR / "harvested_benchmarks"
    for arm_dir in sorted(harvest_root.iterdir() if harvest_root.exists() else []):
        bench_dir = arm_dir / "benchmarks"
        if not bench_dir.is_dir():
            continue
        for bench_path in sorted(bench_dir.glob("run_bclconvert.L003*.bench.tsv")):
            with bench_path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle, delimiter="\t")
                for raw in reader:
                    shard_index, tile_start, tile_end, tile_count = parse_tile_span(bench_path)
                    seconds = as_float(raw.get("s") or raw.get("seconds"))
                    threads = as_float(raw.get("snakemake_threads") or raw.get("threads"))
                    cpu_time = as_float(raw.get("cpu_time"))
                    eff = 0.0
                    if seconds > 0 and threads > 0:
                        eff = (cpu_time / (seconds * threads)) * 100.0
                    rows.append(
                        {
                            "arm": arm_dir.name,
                            "shard_level": shard_level_for_arm(arm_dir.name),
                            "shard_index": shard_index,
                            "tile_start": "" if tile_start is None else str(tile_start),
                            "tile_end": "" if tile_end is None else str(tile_end),
                            "tile_count": str(tile_count),
                            "seconds": f"{seconds:.6f}",
                            "minutes": f"{seconds / 60.0:.6f}",
                            "task_cost": f"{as_float(raw.get('task_cost')):.6f}",
                            "snakemake_threads": f"{threads:.0f}",
                            "allocated_vcpu_hours": f"{seconds * threads / 3600.0:.6f}",
                            "actual_cpu_hours": f"{cpu_time / 3600.0:.6f}",
                            "avg_cpu_cores": f"{cpu_time / seconds:.6f}" if seconds > 0 else "0.000000",
                            "requested_cpu_efficiency_pct": f"{eff:.6f}",
                            "max_rss_gib": f"{as_float(raw.get('max_rss')) / 1024.0:.6f}",
                            "io_in": f"{as_float(raw.get('io_in')):.6f}",
                            "io_out": f"{as_float(raw.get('io_out')):.6f}",
                            "hostname": raw.get("hostname", ""),
                            "instance_type": raw.get("instance_type", ""),
                            "spot_cost": raw.get("spot_cost", ""),
                            "bench_path": str(bench_path),
                        }
                    )
    return rows


def read_named_benchmark_rows(pattern: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    harvest_root = EXP_DIR / "harvested_benchmarks"
    for arm_dir in sorted(harvest_root.iterdir() if harvest_root.exists() else []):
        bench_dir = arm_dir / "benchmarks"
        if not bench_dir.is_dir():
            continue
        for bench_path in sorted(bench_dir.glob(pattern)):
            with bench_path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle, delimiter="\t")
                for raw in reader:
                    seconds = as_float(raw.get("s") or raw.get("seconds"))
                    threads = as_float(raw.get("snakemake_threads") or raw.get("threads"))
                    cpu_time = as_float(raw.get("cpu_time"))
                    eff = (cpu_time / (seconds * threads) * 100.0) if seconds > 0 and threads > 0 else 0.0
                    rows.append(
                        {
                            "arm": arm_dir.name,
                            "task": bench_path.name.removesuffix(".bench.tsv"),
                            "seconds": f"{seconds:.6f}",
                            "minutes": f"{seconds / 60.0:.6f}",
                            "task_cost": f"{as_float(raw.get('task_cost')):.6f}",
                            "snakemake_threads": f"{threads:.0f}",
                            "allocated_vcpu_hours": f"{seconds * threads / 3600.0:.6f}",
                            "actual_cpu_hours": f"{cpu_time / 3600.0:.6f}",
                            "avg_cpu_cores": f"{cpu_time / seconds:.6f}" if seconds > 0 else "0.000000",
                            "requested_cpu_efficiency_pct": f"{eff:.6f}",
                            "max_rss_gib": f"{as_float(raw.get('max_rss')) / 1024.0:.6f}",
                            "io_in": f"{as_float(raw.get('io_in')):.6f}",
                            "io_out": f"{as_float(raw.get('io_out')):.6f}",
                            "hostname": raw.get("hostname", ""),
                            "instance_type": raw.get("instance_type", ""),
                            "spot_cost": raw.get("spot_cost", ""),
                            "bench_path": str(bench_path),
                        }
                    )
    return rows


def no_benchmark_arms(tasks: list[dict[str, str]]) -> list[str]:
    harvested = EXP_DIR / "harvested_benchmarks"
    if not harvested.exists():
        return []
    arms_with_tasks = {row["arm"] for row in tasks}
    missing: list[str] = []
    for arm_dir in sorted(path for path in harvested.iterdir() if path.is_dir()):
        if arm_dir.name in arms_with_tasks:
            continue
        if (arm_dir / "log_extracts.txt").exists() or (arm_dir / "harvest.stdout.txt").exists():
            missing.append(arm_dir.name)
    return missing


def summarize(tasks: list[dict[str, str]]) -> list[dict[str, str]]:
    summaries: list[dict[str, str]] = []
    for arm in sorted({row["arm"] for row in tasks}, key=arm_sort_key):
        arm_rows = [row for row in tasks if row["arm"] == arm]
        if not arm_rows:
            continue
        seconds = [as_float(row["seconds"]) for row in arm_rows]
        max_seconds = max(seconds)
        median_seconds = median(seconds)
        task_cost = sum(as_float(row["task_cost"]) for row in arm_rows)
        allocated = sum(as_float(row["allocated_vcpu_hours"]) for row in arm_rows)
        actual = sum(as_float(row["actual_cpu_hours"]) for row in arm_rows)
        max_rss = max(as_float(row["max_rss_gib"]) for row in arm_rows)
        slowest = arm_rows[seconds.index(max_seconds)]
        tail_ratio = max_seconds / median_seconds if median_seconds else math.inf
        jobs, threads, nodes = full8_capacity_for_arm(arm)
        summaries.append(
            {
                "arm": arm,
                "shard_level": arm_rows[0]["shard_level"],
                "demux_tasks": str(len(arm_rows)),
                "tiles_covered": str(sum(int(row["tile_count"]) for row in arm_rows)),
                "critical_wall_seconds": f"{max_seconds:.6f}",
                "critical_wall_minutes": f"{max_seconds / 60.0:.6f}",
                "total_task_runtime_minutes": f"{sum(seconds) / 60.0:.6f}",
                "total_task_cost": f"{task_cost:.6f}",
                "allocated_vcpu_hours": f"{allocated:.6f}",
                "cpu_time_hours": f"{actual:.6f}",
                "requested_cpu_efficiency_pct": f"{(actual / allocated * 100.0) if allocated else 0.0:.6f}",
                "max_rss_gib": f"{max_rss:.6f}",
                "io_in": f"{sum(as_float(row['io_in']) for row in arm_rows):.6f}",
                "io_out": f"{sum(as_float(row['io_out']) for row in arm_rows):.6f}",
                "hostnames": ",".join(sorted({row["hostname"] for row in arm_rows if row["hostname"]})),
                "slowest_hostname": slowest["hostname"],
                "slowest_task_minutes": f"{max_seconds / 60.0:.6f}",
                "tail_ratio_vs_median": f"{tail_ratio:.6f}",
                "instance_types": ",".join(sorted({row["instance_type"] for row in arm_rows if row["instance_type"]})),
                "full8_parallel_wall_minutes": f"{max_seconds / 60.0:.6f}",
                "full8_serial_wall_minutes": f"{max_seconds * 8.0 / 60.0:.6f}",
                "full8_cost": f"{task_cost * 8.0:.6f}",
                "full8_jobs": str(jobs),
                "full8_threads": str(threads),
                "full8_nodes_192vcpu": str(nodes),
            }
        )
    return summaries


def write_tsv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def decision_text(summaries: list[dict[str, str]]) -> str:
    by_arm = {row["arm"]: row for row in summaries}
    if "shard004" not in by_arm or "shard008" not in by_arm:
        return "shard016 decision pending: shard004 and shard008 summaries are both required."
    shard004_wall = as_float(by_arm["shard004"]["critical_wall_seconds"])
    shard008_wall = as_float(by_arm["shard008"]["critical_wall_seconds"])
    shard004_cost = as_float(by_arm["shard004"]["total_task_cost"])
    shard008_cost = as_float(by_arm["shard008"]["total_task_cost"])
    faster_pct = (1.0 - (shard008_wall / shard004_wall)) * 100.0 if shard004_wall else 0.0
    cost_ok = shard008_cost <= shard004_cost * 1.5 if shard004_cost else False
    tail_ok = as_float(by_arm["shard008"]["tail_ratio_vs_median"]) <= 1.5
    cpu_ok = as_float(by_arm["shard008"]["requested_cpu_efficiency_pct"]) >= (
        as_float(by_arm["shard004"]["requested_cpu_efficiency_pct"]) * 0.5
    )
    eligible = faster_pct >= 10.0 and cost_ok and tail_ok and cpu_ok
    return (
        f"shard016 eligible={str(eligible).lower()}; "
        f"shard008_vs_shard004_faster_pct={faster_pct:.3f}; "
        f"cost_ok={str(cost_ok).lower()}; tail_ok={str(tail_ok).lower()}; "
        f"cpu_ok={str(cpu_ok).lower()}."
    )


def main() -> None:
    tasks = read_task_rows()
    merge_tasks = read_named_benchmark_rows("merge_bclconvert_tile_shards.L003.bench.tsv")
    ready_tasks = read_named_benchmark_rows("run_bclconvert.lane_fastqs_ready.bench.tsv")
    failed_or_missing = no_benchmark_arms(tasks)
    task_fields = [
        "arm",
        "shard_level",
        "shard_index",
        "tile_start",
        "tile_end",
        "tile_count",
        "seconds",
        "minutes",
        "task_cost",
        "snakemake_threads",
        "allocated_vcpu_hours",
        "actual_cpu_hours",
        "avg_cpu_cores",
        "requested_cpu_efficiency_pct",
        "max_rss_gib",
        "io_in",
        "io_out",
        "hostname",
        "instance_type",
        "spot_cost",
        "bench_path",
    ]
    summary_fields = [
        "arm",
        "shard_level",
        "demux_tasks",
        "tiles_covered",
        "critical_wall_seconds",
        "critical_wall_minutes",
        "total_task_runtime_minutes",
        "total_task_cost",
        "allocated_vcpu_hours",
        "cpu_time_hours",
        "requested_cpu_efficiency_pct",
        "max_rss_gib",
        "io_in",
        "io_out",
        "hostnames",
        "slowest_hostname",
        "slowest_task_minutes",
        "tail_ratio_vs_median",
        "instance_types",
        "full8_parallel_wall_minutes",
        "full8_serial_wall_minutes",
        "full8_cost",
        "full8_jobs",
        "full8_threads",
        "full8_nodes_192vcpu",
    ]
    named_task_fields = [
        "arm",
        "task",
        "seconds",
        "minutes",
        "task_cost",
        "snakemake_threads",
        "allocated_vcpu_hours",
        "actual_cpu_hours",
        "avg_cpu_cores",
        "requested_cpu_efficiency_pct",
        "max_rss_gib",
        "io_in",
        "io_out",
        "hostname",
        "instance_type",
        "spot_cost",
        "bench_path",
    ]
    summaries = summarize(tasks)
    write_tsv(DERIVED_DIR / "demux_task_benchmarks.tsv", tasks, task_fields)
    write_tsv(DERIVED_DIR / "case_summary.tsv", summaries, summary_fields)
    write_tsv(DERIVED_DIR / "merge_task_benchmarks.tsv", merge_tasks, named_task_fields)
    write_tsv(DERIVED_DIR / "lane_fastqs_ready_benchmarks.tsv", ready_tasks, named_task_fields)

    lines = [
        "# 25B NovaSeq X Lane003 BCL Convert Sharding Experiment Report",
        "",
        f"Run ID: `{RUNID}`",
        f"Experiment stamp: `{EXP_STAMP}`",
        "",
        "## BCL Convert Summary",
        "",
        "BCL Convert metrics exclude downstream tile-shard merge and lane-ready sentinel benchmarks.",
        "",
    ]
    if summaries:
        lines.append("| Arm | Shard level | Tasks | Critical wall min | Total task cost | CPU eff % | Max RSS GiB | Tail ratio | Full 8-lane cost | Full 8-lane parallel min |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for row in summaries:
            lines.append(
                f"| `{row['arm']}` | {row['shard_level']} | {row['demux_tasks']} | "
                f"{float(row['critical_wall_minutes']):.2f} | {float(row['total_task_cost']):.4f} | "
                f"{float(row['requested_cpu_efficiency_pct']):.1f} | {float(row['max_rss_gib']):.1f} | "
                f"{float(row['tail_ratio_vs_median']):.2f} | {float(row['full8_cost']):.4f} | "
                f"{float(row['full8_parallel_wall_minutes']):.2f} |"
            )
    else:
        lines.append("No benchmark rows harvested yet.")
    if failed_or_missing:
        lines.extend(
            [
                "",
                "## Arms Without BCL Benchmarks",
                "",
            ]
        )
        for arm in failed_or_missing:
            lines.append(
                f"- `{arm}` produced no `run_bclconvert.L003*.bench.tsv`; see "
                f"`harvested_benchmarks/{arm}/log_extracts.txt`."
            )
    lines.extend(["", "## shard016 Decision", "", decision_text(summaries), ""])
    if merge_tasks:
        lines.extend(["", "## Merge Benchmarks", ""])
        lines.append("| Arm | Merge min | Merge cost | CPU eff % | io_in | io_out |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for row in sorted(merge_tasks, key=lambda item: arm_sort_key(item["arm"])):
            lines.append(
                f"| `{row['arm']}` | {float(row['minutes']):.2f} | {float(row['task_cost']):.6f} | "
                f"{float(row['requested_cpu_efficiency_pct']):.2f} | {float(row['io_in']):.2f} | {float(row['io_out']):.2f} |"
            )
    REPORT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
