#!/usr/bin/env python3
"""Build NA00232/NA09677 chip1-only hybrid HioMR config using 20x ILMN FASTQs."""

from __future__ import annotations

import csv
from pathlib import Path


LOG_DIR = Path(
    "/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/"
    "20260605T000000Z_hyb_only_mounted_fastq_kitchensink_logs"
)
ONT_UNITS = LOG_DIR / "ont_config_by_chip_barcode/20260606T083347Z_63d147c7_units.tsv"
ILMN_SAMPLES = LOG_DIR / "ilmn_config/20260606T053415Z_2cb106be_samples.tsv"
UNIT_TEMPLATE = LOG_DIR / (
    "hybrid_hiomr_na2_chip12_fastq_config/"
    "20260606T120700Z_hybrid_hiomr_na2_chip12_units.tsv"
)
OUT_DIR = LOG_DIR / "hybrid_hiomr_na2_chip1_ds20x_test_config"
STAMP = "20260606T160602Z"

SAMPLES = ["NA00232", "NA09677"]
BARCODE_BY_SAMPLE = {"NA00232": "barcode18-chip1", "NA09677": "barcode19-chip1"}
ILMN_FASTQS = {
    "NA00232": (
        "/fsx/analysis_results/4_nas_ds_to_20x/NA00232-SMN_S46_ds20x_R1_001.fastq.gz",
        "/fsx/analysis_results/4_nas_ds_to_20x/NA00232-SMN_S46_ds20x_R2_001.fastq.gz",
    ),
    "NA09677": (
        "/fsx/analysis_results/4_nas_ds_to_20x/NA09677-SMN_S47_ds20x_R1_001.fastq.gz",
        "/fsx/analysis_results/4_nas_ds_to_20x/NA09677-SMN_S47_ds20x_R2_001.fastq.gz",
    ),
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


def csv_paths(value: str) -> list[str]:
    return [part for part in value.split(",") if part]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sample_fields, sample_rows_all = read_tsv(ILMN_SAMPLES)
    unit_fields, unit_template_rows = read_tsv(UNIT_TEMPLATE)
    _, ont_units = read_tsv(ONT_UNITS)

    samples_by_id = {row["SAMPLEID"]: row for row in sample_rows_all}
    templates_by_sample = {row["SAMPLEID"]: row for row in unit_template_rows}
    ont_chip1_by_sample = {
        row["SAMPLEID"]: row
        for row in ont_units
        if row.get("SAMPLEID") in SAMPLES and row.get("LANEID") == "chip1"
    }
    missing = sorted(set(SAMPLES) - set(samples_by_id))
    if missing:
        raise SystemExit(f"missing sample rows: {missing}")
    missing = sorted(set(SAMPLES) - set(templates_by_sample))
    if missing:
        raise SystemExit(f"missing unit templates: {missing}")
    missing = sorted(set(SAMPLES) - set(ont_chip1_by_sample))
    if missing:
        raise SystemExit(f"missing chip1 ONT rows: {missing}")

    sample_rows = [samples_by_id[sample] for sample in SAMPLES]
    unit_rows: list[dict[str, str]] = []
    manifest_rows: list[dict[str, str]] = []

    for sample in SAMPLES:
        out = {field: "" for field in unit_fields}
        out.update(templates_by_sample[sample])
        ont_paths = sorted(csv_paths(ont_chip1_by_sample[sample]["ONT_R1_PATH"]))
        if not ont_paths:
            raise SystemExit(f"{sample} has no chip1 ONT FASTQs")
        if any(not path.startswith("/fsx/run_dir_mounts/ont-4coriells-chip1/") for path in ont_paths):
            raise SystemExit(f"{sample} has non-chip1 ONT path")
        ilmn_r1, ilmn_r2 = ILMN_FASTQS[sample]
        out.update(
            {
                "RUNID": "HYB-4Coriells-chip1-ds20x",
                "SAMPLEID": sample,
                "EXPERIMENTID": "SMN",
                "LANEID": "chip1",
                "BARCODEID": BARCODE_BY_SAMPLE[sample],
                "LIBPREP": "PF",
                "SEQ_VENDOR": "ILMN",
                "SEQ_PLATFORM": "NOVASEQ",
                "ILMN_R1_PATH": ilmn_r1,
                "ILMN_R2_PATH": ilmn_r2,
                "ONT_R1_PATH": ",".join(ont_paths),
                "ONT_R2_PATH": "na",
                "ONT_CRAM": "",
                "ONT_CRAM_ALIGNER": "",
                "ONT_CRAM_SNV_CALLER": "",
                "DEEP_MODEL": "WGS",
                "BWA_KMER": "19",
                "SAMPLEUSE": "sample",
                "SUBSAMPLE_PCT": "na",
            }
        )
        unit_rows.append(out)
        manifest_rows.append(
            {
                "sample": sample,
                "runid": out["RUNID"],
                "lane": out["LANEID"],
                "barcode": out["BARCODEID"],
                "ilmn_r1": ilmn_r1,
                "ilmn_r2": ilmn_r2,
                "ont_fastq_count": str(len(ont_paths)),
                "ont_r1_csv": out["ONT_R1_PATH"],
            }
        )

    samples_path = OUT_DIR / f"{STAMP}_hybrid_hiomr_na2_chip1_ds20x_test_samples.tsv"
    units_path = OUT_DIR / f"{STAMP}_hybrid_hiomr_na2_chip1_ds20x_test_units.tsv"
    manifest_path = OUT_DIR / f"{STAMP}_hybrid_hiomr_na2_chip1_ds20x_test_manifest.tsv"
    write_tsv(samples_path, sample_fields, sample_rows)
    write_tsv(units_path, unit_fields, unit_rows)
    write_tsv(
        manifest_path,
        ["sample", "runid", "lane", "barcode", "ilmn_r1", "ilmn_r2", "ont_fastq_count", "ont_r1_csv"],
        manifest_rows,
    )
    print(f"samples={samples_path}")
    print(f"units={units_path}")
    print(f"manifest={manifest_path}")
    print(f"sample_rows={len(sample_rows)}")
    print(f"unit_rows={len(unit_rows)}")
    for row in manifest_rows:
        print(
            "summary\t{sample}\t{lane}\t{barcode}\tont_fastqs={ont_fastq_count}\t"
            "ilmn_r1={ilmn_r1}\tilmn_r2={ilmn_r2}".format(**row)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
