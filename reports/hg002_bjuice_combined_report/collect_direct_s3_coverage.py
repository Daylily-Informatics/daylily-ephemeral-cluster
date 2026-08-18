#!/usr/bin/env python3
"""Collect the bounded native-SR, RSR, and LR Mosdepth evidence directly from S3.

The report's coverage coordinates are deliberately taken from the native
short-read and long-read summaries.  RSR is collected beside them solely for
the requested audit table; it must never be used as the Illumina coordinate.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
import tempfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path


E1_ROOT = (
    "s3://lsmc-dayoa-analysis-results-usw2/derived/bjuice-v2-multi-analysis-unit/"
    "prod-cand-1703/prod-cand-1703-hg002-bjuice-v2-multiau-20260814T114522Z/"
    "daylily-omics-analysis"
)
E3_ROOT = (
    "s3://lsmc-dayoa-analysis-results-usw2/derived/bjuice-v2-multi-analysis-unit/"
    "prod-cand-1703/prod-cand-1703-hg002-bjuice-4au-kitchensink-20260817T025004Z/"
    "daylily-omics-analysis"
)
P1_ROOT = (
    "s3://lsmc-ssf-sequencing-data/derived/pcand-18022/"
    "pcand18022-bjuice-preval6-15014-dry-20260817t112900z/daylily-omics-analysis"
)


ROWS = (
    ("E1", "p5xp5", "HG002-082hc3dnbehb1c", "0.5", "0.5", E1_ROOT, "43.73", "8.54", "0.57"),
    ("E1", "1x1", "HG002-98xq4xrqz7dwy9", "1", "1", E1_ROOT, "43.73", "9.85", "1.16"),
    ("E1", "3x3", "HG002-871vyxbnp4n81v", "3", "3", E1_ROOT, "43.73", "11.93", "4.09"),
    ("E1", "5x5", "HG002-vqs89p8gahfwf9", "5", "5", E1_ROOT, "43.73", "12.71", "6.20"),
    ("E1", "10x5", "HG002-fjg1n22920ymw4", "10", "5", E1_ROOT, "43.73", "13.65", "9.67"),
    ("E1", "15x5", "HG002-bq765db79mczvn", "15", "5", E1_ROOT, "43.73", "14.01", "11.43"),
    ("E1", "15x10", "HG002-f277f1cckvy1xb", "15", "10", E1_ROOT, "43.73", "13.65", "9.67"),
    ("E3", "10xby10x", "HG002-nxw0jbvh1h5mqx", "9.85", "9.67", E3_ROOT, "10.81", "3.72", "9.67"),
    ("E3", "12xby12x", "HG002-nfjdv62wjc8dwr", "12.71", "11.43", E3_ROOT, "13.83", "4.77", "11.43"),
    ("E3", "20xby15x", "HG002-wesenyqd5xz29g", "20", "15", E3_ROOT, "21.33", "7.36", "14.71"),
    ("E3", "30xby15x", "HG002-q73e7s390m0hjt", "30", "15", E3_ROOT, "31.12", "10.50", "14.71"),
    ("P1", "fullcov", "HG002-qvmjccyp5fr1y3", "NA", "NA", P1_ROOT, "43.73", "14.01", "11.43"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", default="lsmc")
    parser.add_argument("--region", default="us-west-2")
    return parser.parse_args()


def summary_uri(root: str, runtime_au: str, family: str) -> str:
    names = {
        "sr": f"{runtime_au}.sentdhiomr2sr.smd.mosdepth.summary.txt",
        "rsr": f"{runtime_au}.sentdhiomr2rsr.na.mosdepth.summary.txt",
        "lr": f"{runtime_au}.sentdhiomr2lr.na.mosdepth.summary.txt",
    }
    directories = {
        "sr": "align/sentdhiomr2sr/smd/alignqc/mosdepth",
        "rsr": "align/sentdhiomr2rsr/na/alignqc/mosdepth",
        "lr": "align/sentdhiomr2lr/na/alignqc/mosdepth",
    }
    return f"{root}/results/day/hg38/{runtime_au}/{directories[family]}/{names[family]}"


def download(uri: str, destination: Path, profile: str, region: str) -> bytes:
    completed = subprocess.run(
        [
            "aws",
            "s3",
            "cp",
            "--only-show-errors",
            "--no-progress",
            "--profile",
            profile,
            "--region",
            region,
            uri,
            str(destination),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise RuntimeError(f"S3 read failed for {uri}: {completed.stderr.strip()}")
    return destination.read_bytes()


def mosdepth_total_mean(contents: bytes, uri: str) -> str:
    rows = list(csv.DictReader(contents.decode().splitlines(), delimiter="\t"))
    totals = [row for row in rows if row.get("chrom") == "total"]
    if len(totals) != 1 or not totals[0].get("mean"):
        raise ValueError(f"{uri}: expected exactly one Mosdepth total mean row")
    return totals[0]["mean"]


def main() -> None:
    args = parse_args()
    captured_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    output_rows: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="hg002-bjuice-direct-s3-") as temporary:
        temporary_path = Path(temporary)
        for experiment, au, runtime_au, target_ilmn, target_ont, root, expected_sr, expected_rsr, expected_lr in ROWS:
            readings: dict[str, str] = {}
            row: dict[str, str] = {
                "captured_at_utc": captured_at,
                "experiment": experiment,
                "au": au,
                "analysis_unit_uid": runtime_au,
                "target_ilmn_x": target_ilmn,
                "target_ont_x": target_ont,
                "source_s3_root": root,
            }
            for family, column in (("sr", "measured_sr_ilmn_x"), ("rsr", "measured_rsr_ilmn_x"), ("lr", "measured_lr_ont_x")):
                uri = summary_uri(root, runtime_au, family)
                contents = download(uri, temporary_path / f"{experiment}_{au}_{family}.summary.txt", args.profile, args.region)
                readings[family] = mosdepth_total_mean(contents, uri)
                row[column] = readings[family]
                row[f"{family}_summary_s3_uri"] = uri
                row[f"{family}_summary_sha256"] = hashlib.sha256(contents).hexdigest()
            if tuple(readings[family] for family in ("sr", "rsr", "lr")) != (expected_sr, expected_rsr, expected_lr):
                raise ValueError(
                    f"{experiment}:{au}: direct S3 coverage changed; expected "
                    f"SR={expected_sr}, RSR={expected_rsr}, LR={expected_lr}; got {readings}"
                )
            output_rows.append(row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "captured_at_utc",
        "experiment",
        "au",
        "analysis_unit_uid",
        "target_ilmn_x",
        "measured_sr_ilmn_x",
        "measured_rsr_ilmn_x",
        "target_ont_x",
        "measured_lr_ont_x",
        "source_s3_root",
        "sr_summary_s3_uri",
        "sr_summary_sha256",
        "rsr_summary_s3_uri",
        "rsr_summary_sha256",
        "lr_summary_s3_uri",
        "lr_summary_sha256",
    ]
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"wrote {len(output_rows)} direct-S3 coverage rows to {args.output}")


if __name__ == "__main__":
    main()
