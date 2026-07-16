#!/usr/bin/env python3
"""Summarize completed ONT chip+barcode alignstats coverage on the headnode."""

from __future__ import annotations

import json
import sys

from daylily_ec.aws.ssm import run_shell


INSTANCE_ID = "i-05374380b57fad901"
REGION = "us-west-2"
PROFILE = "lsmc"
BASE = "/fsx/analysis_results/ubuntu/hybonly_ont_chipbarcode_limited_live_20260606T090222Z/daylily-omics-analysis/results/day/hg38_broad"


REMOTE_SCRIPT = f"""
set -euo pipefail
base={BASE!r}
echo "BASE=$base"
echo "SUMMARY_FILES"
find "$base/other_reports" -maxdepth 1 -type f -name 'alignstats*.tsv' -print | sort || true
echo "ALIGNSTATS_JSON_FILES"
find "$base" -type f -path '*/alignqc/alignstats/*.alignstats.json' -print | sort
echo "ALIGNSTATS_TSV_FILES"
find "$base" -type f -path '*/alignqc/alignstats/*.alignstats.tsv' -print | sort
echo "OTHER_REPORT_HEADS"
for f in "$base"/other_reports/alignstats*.tsv; do
  [ -f "$f" ] || continue
  echo "FILE=$f"
  sed -n '1,8p' "$f"
done
echo "JSON_METRICS"
python3 - <<'PY'
from __future__ import annotations

import csv
import json
import pathlib
import re

base = pathlib.Path({BASE!r})
files = sorted(base.glob("*/align/*/*/alignqc/alignstats/*.alignstats.json"))
rows = []
for path in files:
    data = json.loads(path.read_text())
    rel = path.relative_to(base)
    parts = rel.parts
    sample = parts[0]
    aligner = parts[2]
    deduper = parts[3]
    row = {{"sample": sample, "aligner": aligner, "deduper": deduper, "json_path": str(path)}}

    def walk(prefix, value):
        if isinstance(value, dict):
            for key, subvalue in value.items():
                walk(f"{{prefix}}.{{key}}" if prefix else str(key), subvalue)
        elif isinstance(value, (int, float, str)):
            row[prefix] = value

    walk("", data)
    rows.append(row)

if not rows:
    raise SystemExit("no alignstats json files found")

interesting = []
patterns = [
    re.compile(r"coverage", re.I),
    re.compile(r"depth", re.I),
    re.compile(r"mean", re.I),
    re.compile(r"bases", re.I),
    re.compile(r"mapped", re.I),
]
for key in sorted({{k for row in rows for k in row}}):
    if key in {{"sample", "aligner", "deduper", "json_path"}}:
        continue
    if any(pattern.search(key) for pattern in patterns):
        interesting.append(key)

print("keys=" + ",".join(interesting))
writer = csv.DictWriter(
    __import__("sys").stdout,
    fieldnames=["sample", "aligner", "deduper"] + interesting,
    delimiter="\\t",
    extrasaction="ignore",
)
writer.writeheader()
for row in rows:
    writer.writerow(row)
PY
"""


def main() -> int:
    result = run_shell(
        INSTANCE_ID,
        REGION,
        REMOTE_SCRIPT,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="summarize ONT chip barcode alignstats coverage",
    )
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    return int(result.response_code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
