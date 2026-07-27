#!/usr/bin/env python3
"""Materialize a complete HG003-only DayOA six-manifest workset.

The source is the reviewed Bjuice Preval-20 manifest directory. This script
preserves its source-owned fields and filters only by existing foreign-key
relationships; it never invents IDs or input paths.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


MANIFESTS = (
    "specimens",
    "samples",
    "libraries",
    "sequencing_inputs",
    "analysis_units",
    "analysis_unit_inputs",
)


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader.fieldnames or []), list(reader)


def write_rows(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample", default="HG003")
    args = parser.parse_args()

    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise SystemExit(f"output directory must be empty: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    source = {}
    for name in MANIFESTS:
        source[name] = read_rows(args.source_dir / f"{name}.tsv")

    specimen_fields, specimen_rows = source["specimens"]
    specimen_rows = [row for row in specimen_rows if row["SPECIMEN_ID"] == args.sample]
    if len(specimen_rows) != 1:
        raise SystemExit("expected exactly one HG003 specimen row")

    sample_fields, sample_rows = source["samples"]
    sample_rows = [row for row in sample_rows if row["SAMPLEID"] == args.sample]
    if len(sample_rows) != 1 or sample_rows[0]["SPECIMEN_ID"] != args.sample:
        raise SystemExit("expected one HG003 sample linked to the HG003 specimen")

    library_fields, library_rows = source["libraries"]
    library_rows = [row for row in library_rows if row["SAMPLEID"] == args.sample]
    library_ids = {row["LIBRARY_ID"] for row in library_rows}
    if library_ids != {"HG003-ILMN", "HG003-ONT"}:
        raise SystemExit(f"unexpected HG003 library set: {sorted(library_ids)}")

    input_fields, input_rows = source["sequencing_inputs"]
    input_rows = [row for row in input_rows if row["LIBRARY_ID"] in library_ids]
    input_ids = {row["SEQUENCING_INPUT_UID"] for row in input_rows}
    if not input_ids:
        raise SystemExit("no HG003 sequencing inputs found")

    unit_fields, unit_rows = source["analysis_units"]
    unit_rows = [row for row in unit_rows if row["SAMPLEID"] == args.sample]
    if len(unit_rows) != 1:
        raise SystemExit("expected exactly one HG003 analysis unit")
    unit_ids = {row["ANALYSIS_UNIT_UID"] for row in unit_rows}

    unit_input_fields, unit_input_rows = source["analysis_unit_inputs"]
    unit_input_rows = [
        row
        for row in unit_input_rows
        if row["ANALYSIS_UNIT_UID"] in unit_ids
        and row["SEQUENCING_INPUT_UID"] in input_ids
    ]
    if {row["SEQUENCING_INPUT_UID"] for row in unit_input_rows} != input_ids:
        raise SystemExit("analysis-unit input links do not cover every retained input")

    for name, fields, rows in (
        ("specimens", specimen_fields, specimen_rows),
        ("samples", sample_fields, sample_rows),
        ("libraries", library_fields, library_rows),
        ("sequencing_inputs", input_fields, input_rows),
        ("analysis_units", unit_fields, unit_rows),
        ("analysis_unit_inputs", unit_input_fields, unit_input_rows),
    ):
        write_rows(args.output_dir / f"{name}.tsv", fields, rows)


if __name__ == "__main__":
    main()
