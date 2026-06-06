#!/usr/bin/env python3
"""Build hybrid ILMN+ONT HIOMR config for the four Coriell/Altair NA samples."""

from __future__ import annotations

import csv
from pathlib import Path


LOG_DIR = Path(
    "/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/"
    "20260605T000000Z_hyb_only_mounted_fastq_kitchensink_logs"
)
ONT_UNITS = LOG_DIR / "ont_config_by_chip_barcode/20260606T083347Z_63d147c7_units.tsv"
ILMN_SAMPLES = LOG_DIR / "ilmn_config/20260606T053415Z_2cb106be_samples.tsv"
ILMN_UNITS = LOG_DIR / "ilmn_config/20260606T053415Z_2cb106be_units.tsv"
OUT_DIR = LOG_DIR / "hybrid_hiomr_na4_config"
STAMP = "20260606T105700Z"

ONT_ANALYSIS_BASE = (
    "/fsx/analysis_results/ubuntu/"
    "hybonly_ont_chipbarcode_limited_live_20260606T090222Z/"
    "daylily-omics-analysis/results/day/hg38_broad"
)

NA_ORDER = ["NA00232", "NA09677", "NA03986", "NA05164"]
TARGET_BY_SAMPLE = {
    "NA00232": "SMN",
    "NA09677": "SMN",
    "NA03986": "DMPK",
    "NA05164": "DMPK",
}
EXPECTED_CHIPS = {
    "NA00232": {"chip1", "chip2", "chip4"},
    "NA09677": {"chip1", "chip2", "chip3", "chip4"},
    "NA03986": {"chip1", "chip2", "chip4"},
    "NA05164": {"chip1", "chip2", "chip4"},
}


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader.fieldnames or []), list(reader)


def write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def old_ont_uid(row: dict[str, str]) -> str:
    parts = [
        row["RUNID"],
        row["SAMPLEID"],
        row["EXPERIMENTID"],
        row["LANEID"],
        row["BARCODEID"],
        row["LIBPREP"],
        row["SEQ_VENDOR"],
        row["SEQ_PLATFORM"],
    ]
    return "-".join(part for part in parts if part)


def ont_cram_path(row: dict[str, str]) -> str:
    uid = old_ont_uid(row)
    return f"{ONT_ANALYSIS_BASE}/{uid}/align/sentmm2ont/na/{uid}.sentmm2ont.na.cram"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sample_fields, sample_rows_all = read_tsv(ILMN_SAMPLES)
    unit_fields, ilmn_units = read_tsv(ILMN_UNITS)
    _, ont_units = read_tsv(ONT_UNITS)

    ilmn_by_sample = {
        row["SAMPLEID"]: row for row in ilmn_units if row.get("SAMPLEID") in NA_ORDER
    }
    if set(ilmn_by_sample) != set(NA_ORDER):
        raise SystemExit(f"missing ILMN rows: {sorted(set(NA_ORDER) - set(ilmn_by_sample))}")

    sample_rows = [row for row in sample_rows_all if row.get("SAMPLEID") in NA_ORDER]
    if [row["SAMPLEID"] for row in sample_rows] != ["NA00232", "NA03986", "NA05164", "NA09677"]:
        found = [row.get("SAMPLEID", "") for row in sample_rows]
        raise SystemExit(f"unexpected samples.tsv NA rows: {found}")

    ont_rows = [row for row in ont_units if row.get("SAMPLEID") in NA_ORDER]
    seen = {sample: set() for sample in NA_ORDER}
    for row in ont_rows:
        seen[row["SAMPLEID"]].add(row["LANEID"])
    if seen != EXPECTED_CHIPS:
        raise SystemExit(f"unexpected ONT chip layout: {seen}")

    hybrid_rows: list[dict[str, str]] = []
    for row in sorted(ont_rows, key=lambda r: (NA_ORDER.index(r["SAMPLEID"]), r["LANEID"])):
        sample = row["SAMPLEID"]
        ilmn = ilmn_by_sample[sample]
        out = {field: "" for field in unit_fields}
        out.update(row)
        out["RUNID"] = f"HYB-4Coriells-{row['LANEID']}"
        out["SEQ_VENDOR"] = "ILMN"
        out["SEQ_PLATFORM"] = "NOVASEQ"
        out["ILMN_R1_PATH"] = ilmn["ILMN_R1_PATH"]
        out["ILMN_R2_PATH"] = ilmn["ILMN_R2_PATH"]
        out["ONT_R1_PATH"] = ""
        out["ONT_R2_PATH"] = ""
        out["ONT_CRAM"] = ont_cram_path(row)
        out["ONT_CRAM_ALIGNER"] = "ont"
        out["ONT_CRAM_SNV_CALLER"] = "sentdont"
        out["DEEP_MODEL"] = ilmn.get("DEEP_MODEL", "WGS") or "WGS"
        out["BWA_KMER"] = ilmn.get("BWA_KMER", "19") or "19"
        out["SAMPLEUSE"] = "sample"
        out["SUBSAMPLE_PCT"] = "na"
        hybrid_rows.append(out)

    samples_path = OUT_DIR / f"{STAMP}_hybrid_hiomr_na4_samples.tsv"
    units_path = OUT_DIR / f"{STAMP}_hybrid_hiomr_na4_units.tsv"
    manifest_path = OUT_DIR / f"{STAMP}_hybrid_hiomr_na4_source_manifest.tsv"
    write_tsv(samples_path, sample_fields, sample_rows)
    write_tsv(units_path, unit_fields, hybrid_rows)

    manifest_fields = [
        "sample",
        "target",
        "chip",
        "barcode",
        "ilmn_r1",
        "ilmn_r2",
        "ont_cram",
        "ont_crai",
    ]
    manifest_rows = [
        {
            "sample": row["SAMPLEID"],
            "target": TARGET_BY_SAMPLE[row["SAMPLEID"]],
            "chip": row["LANEID"],
            "barcode": row["BARCODEID"],
            "ilmn_r1": row["ILMN_R1_PATH"],
            "ilmn_r2": row["ILMN_R2_PATH"],
            "ont_cram": row["ONT_CRAM"],
            "ont_crai": row["ONT_CRAM"] + ".crai",
        }
        for row in hybrid_rows
    ]
    write_tsv(manifest_path, manifest_fields, manifest_rows)

    print(f"samples={samples_path}")
    print(f"units={units_path}")
    print(f"manifest={manifest_path}")
    print(f"sample_rows={len(sample_rows)}")
    print(f"unit_rows={len(hybrid_rows)}")
    print("units_by_sample:")
    for sample in NA_ORDER:
        chips = [row["LANEID"] for row in hybrid_rows if row["SAMPLEID"] == sample]
        print(f"{sample}\t{','.join(chips)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
