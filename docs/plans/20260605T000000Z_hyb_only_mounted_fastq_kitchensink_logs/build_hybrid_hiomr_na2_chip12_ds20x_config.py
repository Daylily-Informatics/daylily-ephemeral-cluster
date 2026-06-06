#!/usr/bin/env python3
"""Build NA00232/NA09677 hybrid HioMR config with ds20x ILMN FASTQs and ONT chip1+chip2 FASTQs."""

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
OUT_DIR = LOG_DIR / "hybrid_hiomr_na2_chip12_ds20x_config"
STAMP = "20260606T123500Z"
DS_ROOT = "/fsx/analysis_results/4_nas_ds_to_20x"

NA_ORDER = ["NA00232", "NA09677"]
CHIPS = ["chip1", "chip2"]
TARGET_BY_SAMPLE = {"NA00232": "SMN", "NA09677": "SMN"}
DS_FASTQS = {
    "NA00232": (
        f"{DS_ROOT}/NA00232-SMN_S46_ds20x_R1_001.fastq.gz",
        f"{DS_ROOT}/NA00232-SMN_S46_ds20x_R2_001.fastq.gz",
    ),
    "NA09677": (
        f"{DS_ROOT}/NA09677-SMN_S47_ds20x_R1_001.fastq.gz",
        f"{DS_ROOT}/NA09677-SMN_S47_ds20x_R2_001.fastq.gz",
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
    return sorted(part for part in value.split(",") if part)


def require_ont_run_mount_paths(paths: list[str], label: str) -> None:
    bad = [path for path in paths if not path.startswith("/fsx/run_dir_mounts/")]
    if bad:
        raise SystemExit(f"{label} has non-run-mount ONT paths: {bad[:3]}")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sample_fields, sample_rows_all = read_tsv(ILMN_SAMPLES)
    unit_fields, ilmn_units = read_tsv(ILMN_UNITS)
    _, ont_units = read_tsv(ONT_UNITS)

    samples_by_id = {row["SAMPLEID"]: row for row in sample_rows_all}
    ilmn_by_sample = {row["SAMPLEID"]: row for row in ilmn_units if row.get("SAMPLEID") in NA_ORDER}
    if set(ilmn_by_sample) != set(NA_ORDER):
        raise SystemExit(f"missing ILMN template rows: {sorted(set(NA_ORDER) - set(ilmn_by_sample))}")

    ont_by_sample_chip = {
        (row["SAMPLEID"], row["LANEID"]): row
        for row in ont_units
        if row.get("SAMPLEID") in NA_ORDER and row.get("LANEID") in CHIPS
    }
    expected = {(sample, chip) for sample in NA_ORDER for chip in CHIPS}
    if set(ont_by_sample_chip) != expected:
        raise SystemExit(f"missing ONT rows: {sorted(expected - set(ont_by_sample_chip))}")

    sample_rows = [samples_by_id[sample] for sample in NA_ORDER]
    hybrid_rows: list[dict[str, str]] = []
    manifest_rows: list[dict[str, str]] = []

    for sample in NA_ORDER:
        ilmn = ilmn_by_sample[sample]
        ds_r1, ds_r2 = DS_FASTQS[sample]
        ont_paths: list[str] = []
        chip_counts: dict[str, int] = {}
        for chip in CHIPS:
            paths = csv_paths(ont_by_sample_chip[(sample, chip)]["ONT_R1_PATH"])
            chip_counts[chip] = len(paths)
            require_ont_run_mount_paths(paths, f"{sample} {chip}")
            ont_paths.extend(paths)
        ont_paths = sorted(ont_paths)

        out = {field: "" for field in unit_fields}
        out.update(ilmn)
        out["RUNID"] = "HYB-4Coriells-chip1-chip2-ds20x"
        out["SAMPLEID"] = sample
        out["EXPERIMENTID"] = TARGET_BY_SAMPLE[sample]
        out["LANEID"] = "chip1-chip2"
        out["BARCODEID"] = (
            "barcode18-chip1-chip2" if sample == "NA00232" else "barcode19-chip1-chip2"
        )
        out["SEQ_VENDOR"] = "ILMN"
        out["SEQ_PLATFORM"] = "NOVASEQ"
        out["ILMN_R1_PATH"] = ds_r1
        out["ILMN_R2_PATH"] = ds_r2
        out["ONT_R1_PATH"] = ",".join(ont_paths)
        out["ONT_R2_PATH"] = "na"
        out["ONT_CRAM"] = ""
        out["ONT_CRAM_ALIGNER"] = ""
        out["ONT_CRAM_SNV_CALLER"] = ""
        out["DEEP_MODEL"] = ilmn.get("DEEP_MODEL", "WGS") or "WGS"
        out["BWA_KMER"] = ilmn.get("BWA_KMER", "19") or "19"
        out["SAMPLEUSE"] = "sample"
        out["SUBSAMPLE_PCT"] = "na"
        hybrid_rows.append(out)

        manifest_rows.append(
            {
                "sample": sample,
                "target": TARGET_BY_SAMPLE[sample],
                "unit": out["LANEID"],
                "barcode": out["BARCODEID"],
                "ilmn_r1": out["ILMN_R1_PATH"],
                "ilmn_r2": out["ILMN_R2_PATH"],
                "ont_chips": ",".join(CHIPS),
                "ont_fastq_count": str(len(ont_paths)),
                "ont_chip1_fastq_count": str(chip_counts["chip1"]),
                "ont_chip2_fastq_count": str(chip_counts["chip2"]),
                "ont_r1_csv": out["ONT_R1_PATH"],
            }
        )

    samples_path = OUT_DIR / f"{STAMP}_hybrid_hiomr_na2_chip12_ds20x_samples.tsv"
    units_path = OUT_DIR / f"{STAMP}_hybrid_hiomr_na2_chip12_ds20x_units.tsv"
    manifest_path = OUT_DIR / f"{STAMP}_hybrid_hiomr_na2_chip12_ds20x_source_manifest.tsv"
    write_tsv(samples_path, sample_fields, sample_rows)
    write_tsv(units_path, unit_fields, hybrid_rows)
    write_tsv(
        manifest_path,
        [
            "sample",
            "target",
            "unit",
            "barcode",
            "ilmn_r1",
            "ilmn_r2",
            "ont_chips",
            "ont_fastq_count",
            "ont_chip1_fastq_count",
            "ont_chip2_fastq_count",
            "ont_r1_csv",
        ],
        manifest_rows,
    )

    print(f"samples={samples_path}")
    print(f"units={units_path}")
    print(f"manifest={manifest_path}")
    print(f"sample_rows={len(sample_rows)}")
    print(f"unit_rows={len(hybrid_rows)}")
    for row in manifest_rows:
        print(
            "summary\t{sample}\tunit={unit}\tont_chips={ont_chips}\t"
            "ont_fastqs={ont_fastq_count}\tilmn_r1={ilmn_r1}\tilmn_r2={ilmn_r2}".format(**row)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
