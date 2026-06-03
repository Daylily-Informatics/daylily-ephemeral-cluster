#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import re
import shlex
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, wait_for_ssm_online


PROFILE = os.environ.get("PROFILE", "lsmc")
REGION = os.environ.get("REGION", "us-west-2")
CLUSTER = os.environ.get("CLUSTER", "dyec5117")
PRIOR_EXP_DIR = Path(
    os.environ.get(
        "PRIOR_EXP_DIR",
        "docs/plans/20260601T234556Z_bcl_l003_25b_shard_experiment",
    )
)
EXP_DIR = Path(
    os.environ.get(
        "EXP_DIR",
        "docs/plans/20260602T115314Z_bcl_full_25b_shard008_experiment",
    )
)
BENCH_OUT = Path(os.environ.get("BENCH_OUT", "bench_expts"))
DELETE = os.environ.get("DELETE_ANALYSIS_DIRS", "0") == "1"
REMOTE_PREFIX = "/fsx/analysis_results/ubuntu"
ANALYSIS_RE = re.compile(r"^bcl25b_l003_[A-Za-z0-9_]+_(?:20260601T234556Z|20260602T[0-9]{6}Z)$")


def sanitize(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")


def read_analysis_ids() -> dict[str, str]:
    ids: dict[str, str] = {}
    for path in sorted((PRIOR_EXP_DIR / "metadata").glob("analysis_id_*.txt")):
        arm = path.name.removeprefix("analysis_id_").removesuffix(".txt")
        analysis_id = path.read_text(encoding="utf-8").strip()
        if analysis_id:
            ids[arm] = analysis_id
    if not ids:
        raise SystemExit(f"No analysis ids found under {PRIOR_EXP_DIR / 'metadata'}")
    return ids


def read_successful_shards(analysis_ids: dict[str, str]) -> dict[str, str]:
    successful: dict[str, str] = {}
    for arm, analysis_id in analysis_ids.items():
        if not arm.startswith("shard"):
            continue
        status_path = PRIOR_EXP_DIR / "metadata" / f"status_{arm}.json"
        if not status_path.is_file():
            continue
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if status.get("exit_code") == 0:
            successful[arm] = analysis_id
    if not successful:
        raise SystemExit("No successful shard cases found from prior status JSON files")
    return successful


def split_benchmarks(stdout: str) -> list[tuple[str, str]]:
    benchmarks: list[tuple[str, str]] = []
    current: str | None = None
    lines: list[str] = []
    for line in stdout.splitlines():
        if line.startswith("__BENCH_FILE__\t"):
            if current is not None:
                benchmarks.append((current, "\n".join(lines).rstrip("\n") + "\n"))
            current = line.split("\t", 1)[1]
            lines = []
            continue
        if current is not None:
            lines.append(line)
    if current is not None:
        benchmarks.append((current, "\n".join(lines).rstrip("\n") + "\n"))
    return benchmarks


def main() -> int:
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    (EXP_DIR / "command_logs").mkdir(parents=True, exist_ok=True)
    BENCH_OUT.mkdir(parents=True, exist_ok=True)

    analysis_ids = read_analysis_ids()
    successful_shards = read_successful_shards(analysis_ids)
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=180)

    successful_payload = " ".join(
        f"{shlex.quote(arm)}={shlex.quote(analysis_id)}"
        for arm, analysis_id in sorted(successful_shards.items())
    )
    delete_flag = "1" if DELETE else "0"
    script = f"""
set -euo pipefail
REMOTE_PREFIX={shlex.quote(REMOTE_PREFIX)}
DELETE={delete_flag}
echo "__DF_BEFORE__"
df -h /fsx
echo "__REMOTE_BCL_DIRS__"
find "$REMOTE_PREFIX" -maxdepth 1 -mindepth 1 -type d -name 'bcl25b_l003_*' -printf '%f\\t%p\\n' | sort
echo "__UNKNOWN_BCL_DIRS__"
unknown=0
while IFS=$'\\t' read -r name path; do
  [[ -z "${{name:-}}" ]] && continue
  if [[ ! "$name" =~ ^bcl25b_l003_[A-Za-z0-9_]+_(20260601T234556Z|20260602T[0-9]{{6}}Z)$ ]]; then
    printf '%s\\t%s\\n' "$name" "$path"
    unknown=1
  fi
done < <(find "$REMOTE_PREFIX" -maxdepth 1 -mindepth 1 -type d -name 'bcl25b_l003_*' -printf '%f\\t%p\\n' | sort)
if [[ "$unknown" -ne 0 ]]; then
  echo "Refusing to proceed with unexpected bcl25b_l003 analysis directory names" >&2
  exit 10
fi
echo "__SUCCESSFUL_SHARD_BENCHMARKS__"
for pair in {successful_payload}; do
  arm="${{pair%%=*}}"
  analysis_id="${{pair#*=}}"
  root="$REMOTE_PREFIX/$analysis_id/daylily-omics-analysis"
  if [[ ! -d "$root" ]]; then
    printf '__MISSING_REMOTE_SUCCESSFUL_SHARD__\\t%s\\t%s\\n' "$arm" "$analysis_id"
    continue
  fi
  count=0
  while IFS= read -r f; do
    rel="${{f#$root/}}"
    printf '__BENCH_FILE__\\t%s\\t%s\\n' "$arm" "$rel"
    cat "$f"
    count=$((count + 1))
  done < <(find "$root" -type f -name '*.bench.tsv' | sort)
  printf '__REMOTE_BENCH_COUNT__\\t%s\\t%s\\n' "$arm" "$count"
  if [[ "$count" -eq 0 ]]; then
    echo "Refusing to delete existing successful shard dir without benchmark files: $analysis_id" >&2
    exit 11
  fi
done
echo "__DELETE_MANIFEST__"
find "$REMOTE_PREFIX" -maxdepth 1 -mindepth 1 -type d -name 'bcl25b_l003_*' -printf '%p\\n' | sort | while read -r p; do
  name="${{p##*/}}"
  if [[ ! "$name" =~ ^bcl25b_l003_[A-Za-z0-9_]+_(20260601T234556Z|20260602T[0-9]{{6}}Z)$ ]]; then
    echo "Unexpected path escaped unknown check: $p" >&2
    exit 12
  fi
  printf '%s\\t%s\\n' "$(du -sb "$p" | awk '{{print $1}}')" "$p"
done
if [[ "$DELETE" == "1" ]]; then
  echo "__DELETE_START__"
  find "$REMOTE_PREFIX" -maxdepth 1 -mindepth 1 -type d -name 'bcl25b_l003_*' -printf '%p\\n' | sort | while read -r p; do
    name="${{p##*/}}"
    if [[ ! "$name" =~ ^bcl25b_l003_[A-Za-z0-9_]+_(20260601T234556Z|20260602T[0-9]{{6}}Z)$ ]]; then
      echo "Unexpected path escaped delete check: $p" >&2
      exit 13
    fi
    rm -rf -- "$p"
    printf '__DELETED__\\t%s\\n' "$p"
  done
  echo "__VERIFY_AFTER_DELETE__"
  remaining="$(find "$REMOTE_PREFIX" -maxdepth 1 -mindepth 1 -type d -name 'bcl25b_l003_*' -printf '%p\\n' | sort)"
  if [[ -n "$remaining" ]]; then
    printf '%s\\n' "$remaining"
    exit 14
  fi
  echo "__DF_AFTER__"
  df -h /fsx
fi
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        timeout=1800,
        comment="Harvest successful shard benchmark TSVs and delete known BCL experiment analysis dirs",
    )

    log_base = EXP_DIR / "command_logs" / "harvest_successful_shards_and_delete"
    (log_base.with_suffix(".stdout.txt")).write_text(result.stdout, encoding="utf-8")
    (log_base.with_suffix(".stderr.txt")).write_text(result.stderr, encoding="utf-8")
    (log_base.with_suffix(".ssm.json")).write_text(
        json.dumps(
            {
                "command_id": result.command_id,
                "instance_id": result.instance_id,
                "status": result.status,
                "response_code": result.response_code,
                "delete": DELETE,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    if result.response_code != 0:
        print(result.stdout, end="")
        print(result.stderr, end="")
        return result.response_code

    manifest_rows: list[dict[str, str]] = []
    deleted_rows: list[dict[str, str]] = []
    current_arm: str | None = None
    current_rel: str | None = None
    content_lines: list[str] = []
    bench_rows: list[dict[str, str]] = []

    def flush_bench() -> None:
        nonlocal current_arm, current_rel, content_lines
        if current_arm is None or current_rel is None:
            return
        local_name = f"{sanitize(current_arm)}__{sanitize(current_rel)}"
        if not local_name.endswith(".tsv"):
            local_name += ".tsv"
        local_path = BENCH_OUT / local_name
        local_path.write_text("\n".join(content_lines).rstrip("\n") + "\n", encoding="utf-8")
        bench_rows.append(
            {
                "case": current_arm,
                "remote_benchmark": current_rel,
                "local_benchmark": str(local_path),
                "local_bytes": str(local_path.stat().st_size),
            }
        )
        current_arm = None
        current_rel = None
        content_lines = []

    in_manifest = False
    for line in result.stdout.splitlines():
        if line.startswith("__BENCH_FILE__\t"):
            flush_bench()
            _, arm, rel = line.split("\t", 2)
            current_arm = arm
            current_rel = rel
            content_lines = []
            in_manifest = False
            continue
        if line.startswith("__DELETE_MANIFEST__"):
            flush_bench()
            in_manifest = True
            continue
        if line.startswith("__DELETE_START__"):
            in_manifest = False
            continue
        if line.startswith("__DELETED__\t"):
            deleted_rows.append({"path": line.split("\t", 1)[1]})
            continue
        if current_arm is not None:
            content_lines.append(line)
            continue
        if in_manifest and line and not line.startswith("__"):
            parts = line.split("\t", 1)
            if len(parts) == 2:
                manifest_rows.append(
                    {
                        "analysis_bytes": parts[0],
                        "deletion_path": parts[1],
                        "analysis_id": Path(parts[1]).name,
                    }
                )
    flush_bench()

    with (BENCH_OUT / "successful_shard_benchmark_manifest.tsv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            delimiter="\t",
            fieldnames=["case", "remote_benchmark", "local_benchmark", "local_bytes"],
        )
        writer.writeheader()
        writer.writerows(bench_rows)

    with (BENCH_OUT / "deletion_manifest.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            delimiter="\t",
            fieldnames=["analysis_id", "analysis_bytes", "deletion_path"],
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    if DELETE:
        with (BENCH_OUT / "deleted_analysis_dirs.tsv").open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(handle, delimiter="\t", fieldnames=["path"])
            writer.writeheader()
            writer.writerows(deleted_rows)

    print(f"successful_shards={','.join(sorted(successful_shards))}")
    print(f"benchmarks_saved={len(bench_rows)}")
    print(f"deletion_paths={len(manifest_rows)}")
    print(f"deleted_paths={len(deleted_rows)}")
    print(f"delete={DELETE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
