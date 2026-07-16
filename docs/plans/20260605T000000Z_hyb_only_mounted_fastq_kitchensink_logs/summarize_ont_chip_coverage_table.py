#!/usr/bin/env python3
"""Print a compact ONT chip/barcode coverage table from alignstats."""

from __future__ import annotations

import csv
import sys

from daylily_ec.aws.ssm import run_shell


INSTANCE_ID = "i-05374380b57fad901"
REGION = "us-west-2"
PROFILE = "lsmc"
SUMMARY = "/fsx/analysis_results/ubuntu/hybonly_ont_chipbarcode_limited_live_20260606T090222Z/daylily-omics-analysis/results/day/hg38_broad/other_reports/alignstats_combo_mqc.tsv"


REMOTE_SCRIPT = f"""
set -euo pipefail
summary={SUMMARY!r}
test -s "$summary"
python3 - <<'PY'
from __future__ import annotations

import csv
import pathlib

summary = pathlib.Path({SUMMARY!r})
rows = []
with summary.open(newline="") as handle:
    reader = csv.DictReader(handle, delimiter="\\t")
    for row in reader:
        parts = row["base_sample"].split("-")
        if len(parts) < 8 or parts[0] != "ONT" or parts[1] != "4Coriells":
            raise SystemExit(f"unexpected sample name: {{row['base_sample']}}")
        rows.append({{
            "chip": parts[2],
            "sample": parts[3],
            "target": parts[4],
            "barcode": parts[6],
            "coverage_x": float(row["WgsCoverageMean"]),
            "median_x": float(row["WgsCoverageMedian"]),
            "mapped_gb": int(row["MappedBases"]) / 1e9,
            "yield_gb": int(row["YieldBases"]) / 1e9,
            "mapped_reads_m": int(row["MappedReads"]) / 1e6,
            "yield_reads_m": int(row["YieldReads"]) / 1e6,
            "pct_10x": float(row["WgsCoverageBases10Pct"]),
            "pct_20x": float(row["WgsCoverageBases20Pct"]),
        }})

rows.sort(key=lambda row: (row["barcode"], row["chip"]))
print("chip\\tbarcode\\tsample\\ttarget\\tmean_cov_x\\tmedian_cov_x\\tmapped_Gb\\tyield_Gb\\tmapped_reads_M\\tyield_reads_M\\t10x_pct\\t20x_pct")
for row in rows:
    print(
        f"{{row['chip']}}\\t{{row['barcode']}}\\t{{row['sample']}}\\t{{row['target']}}\\t"
        f"{{row['coverage_x']:.2f}}\\t{{row['median_x']:.0f}}\\t"
        f"{{row['mapped_gb']:.2f}}\\t{{row['yield_gb']:.2f}}\\t"
        f"{{row['mapped_reads_m']:.2f}}\\t{{row['yield_reads_m']:.2f}}\\t"
        f"{{row['pct_10x']:.2f}}\\t{{row['pct_20x']:.2f}}"
    )

print("")
print("sample\\tbarcode\\tchips\\ttotal_mapped_Gb\\ttotal_yield_Gb\\tcoverage_x_sum_approx")
for sample in sorted({{row["sample"] for row in rows}}):
    srows = [row for row in rows if row["sample"] == sample]
    barcodes = ",".join(sorted({{row["barcode"] for row in srows}}))
    chips = ",".join(row["chip"] for row in srows)
    print(
        f"{{sample}}\\t{{barcodes}}\\t{{chips}}\\t"
        f"{{sum(row['mapped_gb'] for row in srows):.2f}}\\t"
        f"{{sum(row['yield_gb'] for row in srows):.2f}}\\t"
        f"{{sum(row['coverage_x'] for row in srows):.2f}}"
    )
PY
"""


def main() -> int:
    result = run_shell(
        INSTANCE_ID,
        REGION,
        REMOTE_SCRIPT,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=180,
        comment="print compact ONT chip barcode coverage table",
    )
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    return int(result.response_code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
