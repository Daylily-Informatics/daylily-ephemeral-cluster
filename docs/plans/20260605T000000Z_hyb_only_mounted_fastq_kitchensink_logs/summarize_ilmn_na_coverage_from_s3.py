#!/usr/bin/env python3
"""Print ILMN coverage for the four matching NA samples from exported S3 alignstats."""

from __future__ import annotations

import csv
import io
import subprocess
import sys


S3_URI = (
    "s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/"
    "hybonly_ilmn_kitchensink_mounted_20260606T053415Z/daylily-omics-analysis/"
    "results/day/hg38/other_reports/alignstats_combo_mqc.tsv"
)
SAMPLES = {"NA00232", "NA09677", "NA03986", "NA05164"}


def main() -> int:
    proc = subprocess.run(
        ["aws", "s3", "cp", S3_URI, "-"],
        check=True,
        env={**__import__("os").environ, "AWS_PROFILE": "lsmc"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    rows = []
    reader = csv.DictReader(io.StringIO(proc.stdout), delimiter="\t")
    for row in reader:
        base_sample = row["base_sample"]
        sample = next((candidate for candidate in SAMPLES if candidate in base_sample), None)
        if not sample:
            continue
        rows.append(
            {
                "sample": sample,
                "base_sample": base_sample,
                "aligner": row["aligner"],
                "deduper": row["deduper"],
                "mean_cov_x": float(row["WgsCoverageMean"]),
                "median_cov_x": float(row["WgsCoverageMedian"]),
                "mapped_gb": int(row["MappedBases"]) / 1e9,
                "yield_gb": int(row["YieldBases"]) / 1e9,
                "mapped_reads_m": int(row["MappedReads"]) / 1e6,
                "yield_reads_m": int(row["YieldReads"]) / 1e6,
                "pct_10x": float(row["WgsCoverageBases10Pct"]),
                "pct_20x": float(row["WgsCoverageBases20Pct"]),
                "pct_30x": float(row["WgsCoverageBases30Pct"]),
            }
        )
    if {row["sample"] for row in rows} != SAMPLES:
        found = sorted({row["sample"] for row in rows})
        raise SystemExit(f"expected {sorted(SAMPLES)}, found {found}")
    rows.sort(key=lambda row: row["sample"])
    print(f"source={S3_URI}")
    print(
        "sample\tmean_cov_x\tmedian_cov_x\tmapped_Gb\tyield_Gb\t"
        "mapped_reads_M\tyield_reads_M\t10x_pct\t20x_pct\t30x_pct\taligner\tdeduper\tbase_sample"
    )
    for row in rows:
        print(
            f"{row['sample']}\t{row['mean_cov_x']:.2f}\t{row['median_cov_x']:.0f}\t"
            f"{row['mapped_gb']:.2f}\t{row['yield_gb']:.2f}\t"
            f"{row['mapped_reads_m']:.2f}\t{row['yield_reads_m']:.2f}\t"
            f"{row['pct_10x']:.2f}\t{row['pct_20x']:.2f}\t{row['pct_30x']:.2f}\t"
            f"{row['aligner']}\t{row['deduper']}\t"
            f"{row['base_sample']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
