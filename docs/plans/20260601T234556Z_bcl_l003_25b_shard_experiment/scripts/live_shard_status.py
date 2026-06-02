#!/usr/bin/env python3
from __future__ import annotations

import csv
import os
from io import StringIO
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, wait_for_ssm_online

PROFILE = os.environ.get("PROFILE", "lsmc")
REGION = os.environ.get("REGION", "us-west-2")
CLUSTER = os.environ.get("CLUSTER", "dyec5117")
RUNID = os.environ.get("RUNID", "20260514_LH01106_0009_B23TVLGLT4")
EXP_STAMP = os.environ.get("EXP_STAMP", "20260601T234556Z")
ANALYSIS_STAMP = os.environ.get("ANALYSIS_STAMP", EXP_STAMP)
EXP_DIR = Path(os.environ.get("EXP_DIR", f"docs/plans/{EXP_STAMP}_bcl_l003_25b_shard_experiment"))
ARM = os.environ["ARM"]
ANALYSIS_ID = f"bcl25b_l003_{ARM}_{ANALYSIS_STAMP}"


def section(text: str, name: str) -> str:
    start = f"__{name}_START__"
    end = f"__{name}_END__"
    if start not in text or end not in text:
        return ""
    return text.split(start, 1)[1].split(end, 1)[0].strip()


def parse_benchmarks(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    current: str | None = None
    payload: list[str] = []
    for line in text.splitlines():
        if line.startswith("__BENCH__ "):
            if current and payload:
                rows.extend(rows_for_benchmark(current, "\n".join(payload)))
            current = line.split(" ", 1)[1]
            payload = []
        elif current is not None:
            payload.append(line)
    if current and payload:
        rows.extend(rows_for_benchmark(current, "\n".join(payload)))
    return rows


def rows_for_benchmark(name: str, payload: str) -> list[dict[str, str]]:
    reader = csv.DictReader(StringIO(payload), delimiter="\t")
    out: list[dict[str, str]] = []
    for row in reader:
        row["benchmark"] = name
        out.append(row)
    return out


def shard_from_benchmark(name: str) -> str:
    stem = name.removesuffix(".bench.tsv")
    return stem.removeprefix("run_bclconvert.L003.")


def main() -> None:
    out_dir = EXP_DIR / "live_status"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=180)
    remote_root = f"/fsx/analysis_results/ubuntu/{ANALYSIS_ID}/daylily-omics-analysis"
    bcl_dir = f"{remote_root}/results/runs/{RUNID}/bclconvert"
    script = f"""
set -euo pipefail
BCL_DIR={bcl_dir!r}
date -u +%Y-%m-%dT%H:%M:%SZ
if [[ ! -d "$BCL_DIR" ]]; then
  echo "missing_bcl_dir=$BCL_DIR" >&2
  exit 2
fi
echo "__BENCHMARKS_START__"
if [[ -d "$BCL_DIR/benchmarks" ]]; then
  find "$BCL_DIR/benchmarks" -maxdepth 1 -type f -name 'run_bclconvert.L003*.bench.tsv' | sort | while read -r f; do
    echo "__BENCH__ $(basename "$f")"
    cat "$f"
  done
fi
echo "__BENCHMARKS_END__"
echo "__SHARDS_START__"
if [[ -d "$BCL_DIR/tile_fastqs/L003" ]]; then
  find "$BCL_DIR/tile_fastqs/L003" -mindepth 1 -maxdepth 1 -type d | sort | while read -r d; do
    shard="$(basename "$d")"
    fastq_count="$(find "$d" -type f \\( -name '*.fastq.gz' -o -name '*.fq.gz' -o -name '*.fastq' -o -name '*.fq' \\) | wc -l | tr -d ' ')"
    fastq_bytes="$(find "$d" -type f \\( -name '*.fastq.gz' -o -name '*.fq.gz' -o -name '*.fastq' -o -name '*.fq' \\) -printf '%s\\n' | awk '{{s += $1}} END {{printf "%.0f", s}}')"
    newest_epoch="$(find "$d" -type f -printf '%T@\\n' | sort -n | tail -1 || true)"
    echo "$shard	$fastq_count	$fastq_bytes	$newest_epoch"
  done
fi
echo "__SHARDS_END__"
echo "__DONE_START__"
if [[ -d "$BCL_DIR/tile_reports/L003" ]]; then
  find "$BCL_DIR/tile_reports/L003" -mindepth 2 -maxdepth 2 -type f -name bclconvert.done -printf '%h\\t%TY-%Tm-%TdT%TH:%TM:%TSZ\\n' | sort
fi
echo "__DONE_END__"
echo "__LOGS_START__"
if [[ -d "$BCL_DIR/logs" ]]; then
  find "$BCL_DIR/logs" -maxdepth 1 -type f -name 'run_bclconvert.L003*.log' | sort | while read -r f; do
    echo "__LOG__ $(basename "$f") $(stat -c '%s %y' "$f")"
    grep -E 'host=|threads=|tile_regex=|bcl-convert|BCL Convert|ERROR|Error|WARNING|Warning|Completed|completed|Elapsed|elapsed' "$f" | tail -40 || true
  done
fi
echo "__LOGS_END__"
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        timeout=180,
        comment=f"Live BCL shard status for {ARM}",
    )
    raw_path = out_dir / f"{ARM}.raw.txt"
    raw_path.write_text(result.stdout, encoding="utf-8")
    (out_dir / f"{ARM}.stderr.txt").write_text(result.stderr, encoding="utf-8")

    rows = parse_benchmarks(section(result.stdout, "BENCHMARKS"))
    if rows:
      with (out_dir / f"{ARM}.completed_shards.tsv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ["shard", "seconds", "hms", "cpu_efficiency", "hostname", "task_cost", "benchmark"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in sorted(rows, key=lambda item: item["benchmark"]):
            writer.writerow(
                {
                    "shard": shard_from_benchmark(row["benchmark"]),
                    "seconds": row.get("s", ""),
                    "hms": row.get("h:m:s", ""),
                    "cpu_efficiency": row.get("cpu_efficiency", ""),
                    "hostname": row.get("hostname", ""),
                    "task_cost": row.get("task_cost", ""),
                    "benchmark": row["benchmark"],
                }
            )

    shard_lines = section(result.stdout, "SHARDS")
    if shard_lines:
        (out_dir / f"{ARM}.partial_fastq_shards.tsv").write_text(
            "shard\tfastq_files\tfastq_bytes\tnewest_file_epoch\n" + shard_lines + "\n",
            encoding="utf-8",
        )

    print(raw_path)
    if rows:
        print(out_dir / f"{ARM}.completed_shards.tsv")
    if shard_lines:
        print(out_dir / f"{ARM}.partial_fastq_shards.tsv")


if __name__ == "__main__":
    main()
