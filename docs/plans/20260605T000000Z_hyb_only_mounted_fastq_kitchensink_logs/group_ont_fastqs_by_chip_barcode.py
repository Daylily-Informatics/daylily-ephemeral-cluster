#!/usr/bin/env python3
import csv
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "ont_analysis_samples.tsv"
OUTPUT = ROOT / "ont_analysis_samples_by_chip_barcode.tsv"
SUMMARY = ROOT / "ont_analysis_samples_by_chip_barcode.summary.tsv"


def barcode_base(seqbc_id: str) -> str:
    parts = seqbc_id.replace("-", "_").split("_")
    if len(parts) < 2:
        raise SystemExit(f"Cannot derive barcode+chip from SEQBC_ID={seqbc_id!r}")
    return f"{parts[0]}_{parts[1]}"


def main() -> None:
    with INPUT.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames:
            raise SystemExit(f"Missing header in {INPUT}")
        fieldnames = reader.fieldnames
        groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
        for row in reader:
            key = (
                row["RUN_ID"],
                row["SAMPLE_ID"],
                row["EXPERIMENTID"],
                row["SAMPLE_TYPE"],
                row["LIB_PREP"],
                row["SEQ_VENDOR"],
                row["SEQ_PLATFORM"],
                row["LANE"],
                barcode_base(row["SEQBC_ID"]),
            )
            groups[key].append(row)

    output_rows = []
    summary_rows = []
    for key in sorted(groups):
        rows = groups[key]
        first = dict(rows[0])
        paths = sorted(row["ONT_R1_FQ"] for row in rows if row["ONT_R1_FQ"])
        if not paths:
            raise SystemExit(f"No ONT_R1_FQ paths for group {key}")
        if any("," in path for path in paths):
            raise SystemExit(f"Unexpected comma inside ONT_R1_FQ path for group {key}")
        first["SEQBC_ID"] = key[-1]
        first["ONT_R1_FQ"] = ",".join(paths)
        first["ONT_R2_FQ"] = ""
        output_rows.append(first)
        summary_rows.append(
            {
                "chip": first["LANE"],
                "sample": first["SAMPLE_ID"],
                "experiment": first["EXPERIMENTID"],
                "seqbc_id": first["SEQBC_ID"],
                "fastq_count": str(len(paths)),
                "first_fastq": paths[0],
                "last_fastq": paths[-1],
            }
        )

    with OUTPUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(output_rows)

    with SUMMARY.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "chip",
                "sample",
                "experiment",
                "seqbc_id",
                "fastq_count",
                "first_fastq",
                "last_fastq",
            ],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"input_rows={sum(len(rows) for rows in groups.values())}")
    print(f"grouped_rows={len(output_rows)}")
    print(f"output={OUTPUT}")
    print(f"summary={SUMMARY}")


if __name__ == "__main__":
    main()
