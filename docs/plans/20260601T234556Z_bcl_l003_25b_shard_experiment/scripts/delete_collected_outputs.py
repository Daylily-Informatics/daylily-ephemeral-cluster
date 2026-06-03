#!/usr/bin/env python3
from __future__ import annotations

import csv
import os
import re
import shlex
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, wait_for_ssm_online

PROFILE = os.environ.get("PROFILE", "lsmc")
REGION = os.environ.get("REGION", "us-west-2")
CLUSTER = os.environ.get("CLUSTER", "dyec5117")
DELETION_CANDIDATES = Path(os.environ.get("DELETION_CANDIDATES", "bench_expts/deletion_candidates.tsv"))

EXPECTED_RE = re.compile(r"^/fsx/analysis_results/ubuntu/bcl25b_l003_[A-Za-z0-9_]+_20260602T000733Z$")


def read_paths() -> list[str]:
    if not DELETION_CANDIDATES.is_file():
        raise SystemExit(f"Missing deletion candidate manifest: {DELETION_CANDIDATES}")
    rows = list(csv.DictReader(DELETION_CANDIDATES.open(encoding="utf-8"), delimiter="\t"))
    paths = [row["deletion_path"].strip() for row in rows]
    if len(paths) != 7:
        raise SystemExit(f"Expected exactly 7 deletion paths, found {len(paths)}")
    if len(set(paths)) != len(paths):
        raise SystemExit("Deletion manifest contains duplicate paths")
    bad = [path for path in paths if not EXPECTED_RE.match(path)]
    if bad:
        raise SystemExit("Refusing to delete unexpected paths:\n" + "\n".join(bad))
    return paths


def main() -> int:
    paths = read_paths()
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=180)
    quoted_paths = " ".join(shlex.quote(path) for path in paths)
    script = f"""
set -euo pipefail
echo "__DF_BEFORE__"
df -h /fsx
for p in {quoted_paths}; do
  if [[ -e "$p" ]]; then
    printf '__DELETE__\\t%s\\t%s\\n' "$(du -sb "$p" | awk '{{print $1}}')" "$p"
    rm -rf -- "$p"
  else
    printf '__MISSING_BEFORE__\\t%s\\n' "$p"
  fi
done
echo "__VERIFY__"
for p in {quoted_paths}; do
  if [[ -e "$p" ]]; then
    printf '__STILL_EXISTS__\\t%s\\n' "$p"
  else
    printf '__DELETED__\\t%s\\n' "$p"
  fi
done
echo "__DF_AFTER__"
df -h /fsx
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        timeout=1800,
        comment="Delete harvested BCL benchmark experiment analysis directories",
    )
    out_dir = DELETION_CANDIDATES.parent
    (out_dir / "delete_collected_outputs.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (out_dir / "delete_collected_outputs.stderr.txt").write_text(result.stderr, encoding="utf-8")
    print(result.stdout, end="")
    print(result.stderr, end="")
    if "__STILL_EXISTS__" in result.stdout:
        raise SystemExit("One or more deletion targets still exist after rm -rf")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
