#!/usr/bin/env python3
import csv
from collections import defaultdict
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parent
OBJECTS_TSV = LOG_DIR / "gate0_source_objects.tsv"
OUT_DIR = LOG_DIR / "analysis_inputs"

HEADER = [
    "RUN_ID",
    "SAMPLE_ID",
    "EXPERIMENTID",
    "SAMPLESOURCE",
    "SAMPLECLASS",
    "BIOLOGICAL_SEX",
    "SAMPLE_TYPE",
    "LIB_PREP",
    "SEQ_VENDOR",
    "SEQ_PLATFORM",
    "LANE",
    "SEQBC_ID",
    "PATH_TO_CONCORDANCE_DATA_DIR",
    "CONCORDANCE_CONTROL_PATH",
    "TRUTH_DATA_DIR",
    "R1_FQ",
    "R2_FQ",
    "ILMN_R1_FQ",
    "ILMN_R2_FQ",
    "CG_R1_FQ",
    "CG_R2_FQ",
    "PACBIO_R1_FQ",
    "PACBIO_R2_FQ",
    "ONT_R1_FQ",
    "ONT_R2_FQ",
    "ONT_FASTQ_PREFIX",
    "ONT_FLOWCELL_ID",
    "UG_R1_FQ",
    "UG_R2_FQ",
    "ULTIMA_CRAM",
    "ULTIMA_CRAM_ALIGNER",
    "ULTIMA_CRAM_SNV_CALLER",
    "ULTIMA_SUBSAMPLE_PCT",
    "ONT_CRAM",
    "ONT_CRAM_ALIGNER",
    "ONT_CRAM_SNV_CALLER",
    "ONT_SUBSAMPLE_PCT",
    "PB_BAM",
    "PB_BAM_ALIGNER",
    "PB_BAM_SNV_CALLER",
    "ONT_BAM",
    "ONT_BAM_ALIGNER",
    "ONT_BAM_SNV_CALLER",
    "ROCHE_BAM",
    "ROCHE_BAM_ALIGNER",
    "ROCHE_BAM_SNV_CALLER",
    "ROCHE_DOWNSAMPLE_RATIO",
    "STAGE_DIRECTIVE",
    "STAGE_TARGET",
    "SUBSAMPLE_PCT",
    "ILMN_TRIM_READ_LENGTH",
    "LONGREADTRIM_READ_LENGTH",
    "LONGREADTRIM_MODE",
    "SAMPLEUSE",
    "BWA_KMER",
    "DEEP_MODEL",
    "IS_POS_CTRL",
    "IS_NEG_CTRL",
    "TUM_NRM_SAMPLEID_MATCH",
    "N_X",
    "N_Y",
    "EXTERNAL_SAMPLE_ID",
]


def base_row(sample, experiment, vendor, platform, lib_prep, seqbc):
    row = {field: "" for field in HEADER}
    row.update(
        {
            "RUN_ID": "hyb-only-platform-solo",
            "SAMPLE_ID": sample,
            "EXPERIMENTID": experiment,
            "SAMPLESOURCE": "gdna",
            "SAMPLECLASS": "research",
            "BIOLOGICAL_SEX": "na",
            "SAMPLE_TYPE": "gdna",
            "LIB_PREP": lib_prep,
            "SEQ_VENDOR": vendor,
            "SEQ_PLATFORM": platform,
            "LANE": "0",
            "SEQBC_ID": seqbc,
            "PATH_TO_CONCORDANCE_DATA_DIR": "na",
            "CONCORDANCE_CONTROL_PATH": "na",
            "TRUTH_DATA_DIR": "na",
            "STAGE_DIRECTIVE": "pass_through",
            "SUBSAMPLE_PCT": "na",
            "SAMPLEUSE": "research",
            "BWA_KMER": "19",
            "DEEP_MODEL": "WGS" if vendor == "ILMN" else "ONT_R104",
            "IS_POS_CTRL": "false",
            "IS_NEG_CTRL": "false",
            "TUM_NRM_SAMPLEID_MATCH": "na",
            "N_X": "0",
            "N_Y": "0",
            "EXTERNAL_SAMPLE_ID": sample,
        }
    )
    return row


def write_tsv(path, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUT_DIR.mkdir(exist_ok=True)
    objects = list(csv.DictReader(OBJECTS_TSV.open(), delimiter="\t"))

    ont_specs = [
        ("NA00232", "SMN", "barcode18", "/fsx/scratch/ONT/NA00232_SMN_R1_all.fastq.gz"),
        ("NA09677", "SMN", "barcode19", "/fsx/scratch/ONT/NA09677_SMN_R1_all.fastq.gz"),
        ("NA03986", "DMPK", "barcode20", "/fsx/scratch/ONT/NA03986_DMPK_R1_all.fastq.gz"),
        ("NA05164", "DMPK", "barcode21", "/fsx/scratch/ONT/NA05164_DMPK_R1_all.fastq.gz"),
    ]
    ont_rows = []
    for sample, panel, barcode, fastq in ont_specs:
        row = base_row(sample, f"{panel}_ONT_allchips", "ONT", "PROMETHION", "SQK-LSK114", barcode)
        row["ONT_R1_FQ"] = fastq
        row["ONT_FLOWCELL_ID"] = "multi-chip"
        ont_rows.append(row)
    write_tsv(OUT_DIR / "ont_analysis_samples.tsv", ont_rows)

    ilmn_pairs = defaultdict(dict)
    for obj in objects:
        if obj["platform"] != "ILMN":
            continue
        name = obj["uri"].rsplit("/", 1)[-1]
        sample = obj["sample"]
        read = "R1" if "_R1_" in name else "R2" if "_R2_" in name else ""
        if not read:
            continue
        lib = name.split("_R", 1)[0]
        ilmn_pairs[(sample, lib)][read] = f"/fsx/scratch/ILMN/{name}"

    ilmn_rows = []
    for (sample, lib), pair in sorted(ilmn_pairs.items()):
        if set(pair) != {"R1", "R2"}:
            raise SystemExit(f"incomplete ILMN pair for {sample} {lib}: {pair}")
        seqbc = lib.replace(sample, "").strip("-_") or lib
        row = base_row(sample, lib, "ILMN", "NOVASEQ", "PF", seqbc)
        row["ILMN_R1_FQ"] = pair["R1"]
        row["ILMN_R2_FQ"] = pair["R2"]
        ilmn_rows.append(row)
    write_tsv(OUT_DIR / "ilmn_analysis_samples.tsv", ilmn_rows)

    with (OUT_DIR / "analysis_inputs_summary.tsv").open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["platform", "rows", "samples"])
        writer.writerow(["ONT", len(ont_rows), ",".join(row["SAMPLE_ID"] for row in ont_rows)])
        writer.writerow(["ILMN", len(ilmn_rows), ",".join(sorted({row["SAMPLE_ID"] for row in ilmn_rows}))])


if __name__ == "__main__":
    main()
