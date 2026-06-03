#!/usr/bin/env python3
from __future__ import annotations

import os
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


def split_files(text: str, marker: str) -> dict[str, str]:
    files: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith(marker):
            current = line[len(marker) :].strip()
            files[current] = []
            continue
        if current is not None:
            files[current].append(line)
    return {name: "\n".join(lines).rstrip("\n") + "\n" for name, lines in files.items()}


def main() -> None:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=180)
    remote_root = f"/fsx/analysis_results/ubuntu/{ANALYSIS_ID}/daylily-omics-analysis"
    bcl_dir = f"{remote_root}/results/runs/{RUNID}/bclconvert"
    script = f"""
set -euo pipefail
BCL_DIR={bcl_dir!r}
if [[ ! -d "$BCL_DIR" ]]; then
  echo "missing_bcl_dir=$BCL_DIR" >&2
  exit 2
fi
echo "__PATHS_START__"
printf "remote_root=%s\\n" {remote_root!r}
printf "bcl_dir=%s\\n" "$BCL_DIR"
find "$BCL_DIR" -maxdepth 2 -type d | sort
echo "__PATHS_END__"
echo "__BENCHMARKS_START__"
find "$BCL_DIR/benchmarks" -maxdepth 1 -type f \( -name 'run_bclconvert.L003*.bench.tsv' -o -name 'merge_bclconvert_tile_shards.L003.bench.tsv' -o -name 'run_bclconvert.lane_fastqs_ready.bench.tsv' \) | sort | while read -r f; do
  echo "__BENCH_FILE__ $f"
  cat "$f"
done
echo "__BENCHMARKS_END__"
echo "__LOG_EXTRACTS_START__"
find "$BCL_DIR/logs" -maxdepth 1 -type f -name 'run_bclconvert.L003*.log' | sort | while read -r f; do
  echo "__LOG_FILE__ $f"
  grep -E 'host=|threads=|sample_sheet=|input_dir=|output_dir=|tile_regex=|bcl_only_lane=|bcl-convert|BCL Convert|command|SoftwareVersion|ERROR|Error|WARNING|Warning' "$f" | sed -n '1,160p' || true
  echo "__LOG_TAIL__ $f"
  tail -n 80 "$f" || true
done
echo "__LOG_EXTRACTS_END__"
echo "__FASTQ_SIZES_START__"
find "$BCL_DIR" -type f \\( -name '*.fastq.gz' -o -name '*.fq.gz' -o -name '*.fastq' -o -name '*.fq' \\) -printf '%s\\t%p\\n' | sort -k2,2 || true
echo "__FASTQ_SIZES_END__"
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        timeout=240,
        comment=f"Harvest BCL benchmarks for {ARM}",
    )
    arm_dir = EXP_DIR / "harvested_benchmarks" / ARM
    bench_dir = arm_dir / "benchmarks"
    arm_dir.mkdir(parents=True, exist_ok=True)
    bench_dir.mkdir(parents=True, exist_ok=True)
    (arm_dir / "harvest.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (arm_dir / "harvest.stderr.txt").write_text(result.stderr, encoding="utf-8")

    bench_section = result.stdout.split("__BENCHMARKS_START__", 1)[-1].split(
        "__BENCHMARKS_END__", 1
    )[0]
    for remote_name, content in split_files(bench_section, "__BENCH_FILE__").items():
        local_name = Path(remote_name).name
        (bench_dir / local_name).write_text(content, encoding="utf-8")

    paths = result.stdout.split("__PATHS_START__", 1)[-1].split("__PATHS_END__", 1)[0]
    (arm_dir / "remote_paths.txt").write_text(paths.strip() + "\n", encoding="utf-8")
    logs = result.stdout.split("__LOG_EXTRACTS_START__", 1)[-1].split(
        "__LOG_EXTRACTS_END__", 1
    )[0]
    (arm_dir / "log_extracts.txt").write_text(logs.strip() + "\n", encoding="utf-8")
    if "__FASTQ_SIZES_START__" in result.stdout and "__FASTQ_SIZES_END__" in result.stdout:
        fastqs = result.stdout.split("__FASTQ_SIZES_START__", 1)[1].split(
            "__FASTQ_SIZES_END__", 1
        )[0]
        (arm_dir / "fastq_sizes.tsv").write_text(fastqs.strip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
