#!/usr/bin/env python3
"""Build the exact remaining-BJuice plus HG002 5x/5x six-manifest set."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


FULL_SAMPLES = (
    "HG001",
    "HG005",
    "HG006",
    "HG007",
    "NA05067",
    "NA10798",
    "NA13189",
    "NA14732",
    "NA14733",
    "NA15603",
    "NA15848",
    "NA15849",
    "NA20027",
    "NA20230",
)

SLIM_SAMPLE = "HG002"
SLIM_AU = "HG002-BJUICE-ILMN5X-ONT5X-1340"
ONT_CHUNK_RE = re.compile(r"_(\d+)[.]fastq[.]gz$")


def read_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames is None:
            raise ValueError(f"Missing TSV header: {path}")
        return list(reader.fieldnames), list(reader)


def write_table(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            delimiter="\t",
            lineterminator="\n",
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)


def blank(fields: list[str], **values: str) -> dict[str, str]:
    unknown = set(values) - set(fields)
    if unknown:
        raise ValueError(f"Fields absent from source contract: {sorted(unknown)}")
    row = {field: "" for field in fields}
    row.update(values)
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    tables = {
        name: read_table(args.source_dir / f"{name}.tsv")
        for name in (
            "specimens",
            "samples",
            "libraries",
            "sequencing_inputs",
            "analysis_units",
            "analysis_unit_inputs",
        )
    }
    selected = set(FULL_SAMPLES)

    specimen_fields, specimen_rows = tables["specimens"]
    specimen_rows = [row for row in specimen_rows if row["SPECIMEN_ID"] in selected]
    specimen_rows.append(
        blank(
            specimen_fields,
            SPECIMEN_ID=SLIM_SAMPLE,
            SAMPLESOURCE="blood",
            SPECIMEN_TYPE="blood",
            EXTERNAL_SPECIMEN_ID=SLIM_SAMPLE,
            BIOLOGICAL_SEX="male",
            N_X="1",
            N_Y="1",
            SPECIMEN_COMMENT=(
                "HG002 BJuice prevalence accepted approximately 5x Illumina plus "
                "deterministic ONT 5x RnD validation; no owner-issued EUID supplied"
            ),
        )
    )

    sample_fields, sample_rows = tables["samples"]
    sample_rows = [row for row in sample_rows if row["SAMPLEID"] in selected]
    hg002_truth = (
        "/fsx/references/genomic_data/organism_annotations/H_sapiens/hg38/"
        "controls/giab/snv/v4.2.1/HG002/"
    )
    sample_rows.append(
        blank(
            sample_fields,
            SAMPLEID=SLIM_SAMPLE,
            SPECIMEN_ID=SLIM_SAMPLE,
            SAMPLECLASS="research",
            SAMPLE_TYPE="gdna",
            SAMPLEUSE="posControl",
            ORDER_TYPE="positive_control",
            CONCORDANCE_CONTROL_PATH=hg002_truth,
            IS_POSITIVE_CONTROL="true",
            IS_NEGATIVE_CONTROL="false",
            EXTERNAL_SAMPLE_ID=SLIM_SAMPLE,
            TRUTH_DATA_DIR=hg002_truth,
            SAMPLE_COMMENT=(
                "HG002 GIAB positive-control sample for accepted approximately 5x "
                "Illumina plus 5x ONT RnD validation; local analytical package only"
            ),
        )
    )

    library_fields, library_rows = tables["libraries"]
    library_rows = [row for row in library_rows if row["SAMPLEID"] in selected]
    library_rows.extend(
        (
            blank(
                library_fields,
                LIBRARY_ID="HG002-BJUICE-ONT5X-LIB",
                SAMPLEID=SLIM_SAMPLE,
                LIBPREP="ONT",
                AMPLIFICATION_TYPE="WGS",
                LIBRARY_COMMENT=(
                    "HG002 BJuice ONT physical library represented by the "
                    "deterministic 5x FASTQ derivative"
                ),
            ),
            blank(
                library_fields,
                LIBRARY_ID="HG002-ILMN5X-LIB",
                SAMPLEID=SLIM_SAMPLE,
                LIBPREP="PF",
                AMPLIFICATION_TYPE="WGS",
                LIBRARY_COMMENT=(
                    "HG002 NovaSeqX TruSeq PCR-free physical library represented by "
                    "the materialized 5x paired FASTQs"
                ),
            ),
        )
    )

    sequencing_fields, sequencing_rows = tables["sequencing_inputs"]
    selected_libraries = {row["LIBRARY_ID"] for row in library_rows if row["SAMPLEID"] in selected}
    sequencing_rows = [
        row for row in sequencing_rows if row["LIBRARY_ID"] in selected_libraries
    ]
    for row in sequencing_rows:
        if row["MODALITY"] != "lr":
            continue
        original_paths = [path.strip() for path in row["ONT_R1_PATH"].split(",")]
        kept_paths = []
        for path in original_paths:
            match = ONT_CHUNK_RE.search(path)
            if match is None:
                raise ValueError(
                    f"Full-coverage ONT path lacks required chunk-hour suffix: {path}"
                )
            if 0 <= int(match.group(1)) < 25:
                kept_paths.append(path)
        if not kept_paths:
            raise ValueError(
                f"ONT [0,25) manifest prefilter kept no paths for "
                f"{row['SEQUENCING_INPUT_UID']}"
            )
        row["ONT_R1_PATH"] = ",".join(kept_paths)
        row["SEQUENCING_INPUT_COMMENT"] = (
            row["SEQUENCING_INPUT_COMMENT"].rstrip()
            + f"; exact manifest prefilter kept {len(kept_paths)}/{len(original_paths)} "
            "FASTQs with chunk-hour suffix in [0,25)"
        )
    sequencing_rows.extend(
        (
            blank(
                sequencing_fields,
                SEQUENCING_INPUT_UID="HG002-BJUICE-ONT5X-SEED1340",
                LIBRARY_ID="HG002-BJUICE-ONT5X-LIB",
                MODALITY="lr",
                LAYOUT="single_fastq",
                RUNID="HG002-BJUICE-ONT-5X-SEED1340",
                EXPERIMENTID="ILMN5x-ONT5x-1340",
                LANEID="1",
                BARCODEID="D0",
                SEQ_PLATFORM="ONT",
                SEQ_VENDOR="ONT",
                ONT_R1_PATH=(
                    "/fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/"
                    "giab/bjuice_preval_2026/HG002/ont/downsampled/"
                    "HG002_BJUICEPREVAL_ONT_5x.seqkit-sample-seed1340.fastq.gz"
                ),
                SEQUENCING_INPUT_COMMENT=(
                    "Deterministic read-level approximately 5x HG002 BJuice ONT FASTQ; "
                    "seed 1340; source preserved unchanged"
                ),
            ),
            blank(
                sequencing_fields,
                SEQUENCING_INPUT_UID="HG002-ILMN5X-NOVASEQX",
                LIBRARY_ID="HG002-ILMN5X-LIB",
                MODALITY="sr",
                LAYOUT="paired_fastq",
                RUNID="HG002-ILMN-5X-NOVASEQX",
                EXPERIMENTID="ILMN5x-ONT5x-1340",
                LANEID="1",
                BARCODEID="D0",
                SEQ_PLATFORM="NOVASEQ",
                SEQ_VENDOR="ILMN",
                ILMN_R1_PATH=(
                    "/fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/"
                    "giab/NovaSeqX_WHGS_TruSeqPF_HG002-007/downsampled/"
                    "HG002_5x_R1.fastq.gz"
                ),
                ILMN_R2_PATH=(
                    "/fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/"
                    "giab/NovaSeqX_WHGS_TruSeqPF_HG002-007/downsampled/"
                    "HG002_5x_R2.fastq.gz"
                ),
                SEQUENCING_INPUT_COMMENT=(
                    "Accepted approximately 5x HG002 paired Illumina FASTQs; measured "
                    "5.862704556x; 60,277,137 reads per mate"
                ),
            ),
        )
    )

    unit_fields, source_units = tables["analysis_units"]
    old_units = {row["ANALYSIS_UNIT_UID"]: row for row in source_units}
    full_uid_map: dict[str, str] = {}
    unit_rows: list[dict[str, str]] = []
    for sample in FULL_SAMPLES:
        matches = [row for row in source_units if row["SAMPLEID"] == sample]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one source analysis unit for {sample}: {matches}")
        source = dict(matches[0])
        old_uid = source["ANALYSIS_UNIT_UID"]
        new_uid = f"BJUICEPREVAL-REMAINING-{sample}-HIOMR2-1345"
        full_uid_map[old_uid] = new_uid
        source["ANALYSIS_UNIT_UID"] = new_uid
        source["ANALYSIS_UNIT_COMMENT"] = (
            f"Remaining BJuice prevalence full-coverage ILMN plus ONT [0,25) "
            f"HIOMR2 13.4.5 analysis for {sample}"
        )
        unit_rows.append(source)
    unit_rows.append(
        blank(
            unit_fields,
            ANALYSIS_UNIT_UID=SLIM_AU,
            SAMPLEID=SLIM_SAMPLE,
            DELIVERY_PROFILE="local",
            ALIGNED_REF_UID="hg38",
            BWA_KMER="19",
            DEEP_MODEL="WGS",
            ANALYSIS_UNIT_COMMENT=(
                "HG002 accepted approximately 5x Illumina plus deterministic 5x "
                "BJuice ONT HIOMR2 13.4.5 analytical-package validation"
            ),
        )
    )

    input_fields, source_links = tables["analysis_unit_inputs"]
    input_rows: list[dict[str, str]] = []
    for row in source_links:
        if row["ANALYSIS_UNIT_UID"] not in full_uid_map:
            continue
        mapped = dict(row)
        mapped["ANALYSIS_UNIT_UID"] = full_uid_map[row["ANALYSIS_UNIT_UID"]]
        input_rows.append(mapped)
    input_rows.extend(
        (
            blank(
                input_fields,
                ANALYSIS_UNIT_UID=SLIM_AU,
                SEQUENCING_INPUT_UID="HG002-ILMN5X-NOVASEQX",
                ROLE="sr",
                INPUT_ORDINAL="1",
            ),
            blank(
                input_fields,
                ANALYSIS_UNIT_UID=SLIM_AU,
                SEQUENCING_INPUT_UID="HG002-BJUICE-ONT5X-SEED1340",
                ROLE="lr",
                INPUT_ORDINAL="2",
            ),
        )
    )

    outputs = {
        "specimens": (specimen_fields, specimen_rows),
        "samples": (sample_fields, sample_rows),
        "libraries": (library_fields, library_rows),
        "sequencing_inputs": (sequencing_fields, sequencing_rows),
        "analysis_units": (unit_fields, unit_rows),
        "analysis_unit_inputs": (input_fields, input_rows),
    }
    for name, (fields, rows) in outputs.items():
        write_table(args.output_dir / f"{name}.tsv", fields, rows)

    if len(unit_rows) != 15:
        raise ValueError(f"Expected 15 analysis units, found {len(unit_rows)}")
    if set(old_units) & set(full_uid_map.values()):
        raise ValueError("New analysis-unit identifiers collide with source identifiers")
    print(
        "built manifests: "
        + " ".join(f"{name}={len(rows)}" for name, (_, rows) in outputs.items())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
