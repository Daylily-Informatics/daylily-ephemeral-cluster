#!/usr/bin/env python3
"""Build private, direct-FASTQ DayOA manifests for native DRAGEN validation."""

from __future__ import annotations

import csv
from pathlib import Path


OUTPUT_DIR = Path(__file__).with_name("20260710T025221Z_dragen_input_manifests")
MOUNT_ROOT = Path(
    "/fsx/run_dir_mounts/20260618_LH01106_0011_A23MFMCLT3_ilmn_fastq"
)
REFERENCE_READ_ROOT = Path(
    "/fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/giab/"
    "NovaSeqX_WHGS_TruSeqPF_HG002-007/downsampled"
)
TRUTH_ROOT = Path(
    "/fsx/references/genomic_data/organism_annotations/H_sapiens/hg38/"
    "controls/giab/snv/v4.2.1"
)

SAMPLE_FIELDS = (
    "SAMPLEID",
    "SAMPLESOURCE",
    "SAMPLECLASS",
    "BIOLOGICAL_SEX",
    "CONCORDANCE_CONTROL_PATH",
    "IS_POSITIVE_CONTROL",
    "IS_NEGATIVE_CONTROL",
    "SAMPLE_TYPE",
    "TUM_NRM_SAMPLEID_MATCH",
    "EXTERNAL_SAMPLE_ID",
    "N_X",
    "N_Y",
    "TRUTH_DATA_DIR",
)
UNIT_FIELDS = (
    "RUNID",
    "SAMPLEID",
    "EXPERIMENTID",
    "LANEID",
    "BARCODEID",
    "LIBPREP",
    "SEQ_VENDOR",
    "SEQ_PLATFORM",
    "ILMN_R1_PATH",
    "ILMN_R2_PATH",
    "SAMPLEUSE",
    "BWA_KMER",
    "DEEP_MODEL",
    "analysis_unit_uid",
)

SAMPLE_METADATA = {
    "HG002": ("male", str(TRUTH_ROOT / "HG002"), "1", "1"),
    "HG003": ("male", str(TRUTH_ROOT / "HG003"), "1", "1"),
    "NA20775": ("unknown", "na", "na", "na"),
    "NA23687": ("unknown", "na", "na", "na"),
}
SAMPLE_SLOTS = {"HG003": "S16", "NA20775": "S12", "NA23687": "S13"}
EXPECTED_BYTES = {
    ("HG002", "R1"): 3_899_321_181,
    ("HG002", "R2"): 4_000_405_121,
    ("HG003", "R1"): 38_635_607_903,
    ("HG003", "R2"): 38_970_470_569,
    ("NA20775", "R1"): 37_597_192_947,
    ("NA20775", "R2"): 37_964_051_254,
    ("NA23687", "R1"): 36_627_909_063,
    ("NA23687", "R2"): 36_845_312_328,
}


def _reads(sample: str, read: str) -> list[str]:
    if sample == "HG002":
        return [str(REFERENCE_READ_ROOT / f"HG002_5x_{read}.fastq.gz")]
    slot = SAMPLE_SLOTS[sample]
    return [
        str(MOUNT_ROOT / f"{sample}_{slot}_L{lane:03d}_{read}_001.fastq.gz")
        for lane in range(1, 9)
    ]


def _write_tsv(path: Path, fields: tuple[str, ...], row: dict[str, str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)


def _dayoa_identifier(value: str) -> str:
    if "." in value or "_" in value:
        raise ValueError(f"DayOA identifier may not contain '.' or '_': {value}")
    return value


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    for sample, (sex, truth, n_x, n_y) in SAMPLE_METADATA.items():
        sample_dir = OUTPUT_DIR / sample
        sample_dir.mkdir(exist_ok=True)
        _write_tsv(
            sample_dir / "samples.tsv",
            SAMPLE_FIELDS,
            {
                "SAMPLEID": sample,
                "SAMPLESOURCE": "blood",
                "SAMPLECLASS": "research",
                "BIOLOGICAL_SEX": sex,
                "CONCORDANCE_CONTROL_PATH": truth,
                "IS_POSITIVE_CONTROL": "true",
                "IS_NEGATIVE_CONTROL": "false",
                "SAMPLE_TYPE": "gdna",
                "TUM_NRM_SAMPLEID_MATCH": "na",
                "EXTERNAL_SAMPLE_ID": sample,
                "N_X": n_x,
                "N_Y": n_y,
                "TRUTH_DATA_DIR": truth,
            },
        )
        _write_tsv(
            sample_dir / "units.tsv",
            UNIT_FIELDS,
            {
                "RUNID": _dayoa_identifier(
                    "HG002-5x" if sample == "HG002" else "20260618-LH01106-0011-A23MFMCLT3"
                ),
                "SAMPLEID": sample,
                "EXPERIMENTID": _dayoa_identifier("native-dragen"),
                "LANEID": _dayoa_identifier("ordered-fastq-list"),
                "BARCODEID": sample,
                "LIBPREP": "PCR-FREE",
                "SEQ_VENDOR": "ILMN",
                "SEQ_PLATFORM": "NOVASEQX",
                "ILMN_R1_PATH": ",".join(_reads(sample, "R1")),
                "ILMN_R2_PATH": ",".join(_reads(sample, "R2")),
                "SAMPLEUSE": "posControl",
                "BWA_KMER": "19",
                "DEEP_MODEL": "WGS",
                "analysis_unit_uid": sample,
            },
        )

    expected = OUTPUT_DIR / "expected_fastq_bytes.tsv"
    with expected.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(("sample", "read", "object_count", "expected_bytes"))
        for (sample, read), size in sorted(EXPECTED_BYTES.items()):
            writer.writerow((sample, read, len(_reads(sample, read)), size))


if __name__ == "__main__":
    main()
