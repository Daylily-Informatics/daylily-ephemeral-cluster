#!/usr/bin/env python3
"""Build ILMN-only manifests for the dragain12 Betelgeuse five-sample run."""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path


ILMN_ROOT = Path(
    "/fsx/run_dir_mounts/20260618_LH01106_0011_A23MFMCLT3_ilmn_fastq"
)
REFERENCE_ROOT = Path(
    "/fsx/references/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv"
)

TRUTH_SOURCES = {
    "HG002": {
        "giabHCv5q": {
            "bed": REFERENCE_ROOT / "v5.0q/HG002/giabHCv5q/HG002_GRCh38_v5.0q_smvar.benchmark.bed",
            "vcf.gz": REFERENCE_ROOT / "v5.0q/HG002/giabHCv5q/HG002_GRCh38_v5.0q_smvar.vcf.gz",
            "vcf.gz.tbi": REFERENCE_ROOT / "v5.0q/HG002/giabHCv5q/HG002_GRCh38_v5.0q_smvar.vcf.gz.tbi",
        },
    },
    "HG003": {
        "giabHC": {
            "bed": REFERENCE_ROOT / "v4.2.1/HG003/giabHC/HG003.bed",
            "vcf.gz": REFERENCE_ROOT / "v4.2.1/HG003/giabHC/HG003.vcf.gz",
            "vcf.gz.tbi": REFERENCE_ROOT / "v4.2.1/HG003/giabHC/HG003.vcf.gz.tbi",
        },
    },
}

SAMPLES = {
    "HG002": {
        "ilmn_index": "S15",
        "sex": "male",
        "source": "blood",
        "expected_smn": "2/2",
        "ilmn_bytes": (37003624993, 37335094934),
    },
    "HG003": {
        "ilmn_index": "S16",
        "sex": "male",
        "source": "blood",
        "expected_smn": "2/2",
        "ilmn_bytes": (38635607903, 38970470569),
    },
    "NA19235": {
        "ilmn_index": "S11",
        "sex": "female",
        "source": "unknown",
        "expected_smn": "4/0",
        "ilmn_bytes": (31787165597, 32061482369),
    },
    "NA20775": {
        "ilmn_index": "S12",
        "sex": "female",
        "source": "unknown",
        "expected_smn": "3/1",
        "ilmn_bytes": (37597192947, 37964051254),
    },
    "NA23687": {
        "ilmn_index": "S13",
        "sex": "female",
        "source": "unknown",
        "expected_smn": "1/2",
        "ilmn_bytes": (36627909063, 36845312328),
    },
}

SAMPLE_FIELDS = (
    "SAMPLEID", "SAMPLESOURCE", "SAMPLECLASS", "BIOLOGICAL_SEX",
    "CONCORDANCE_CONTROL_PATH", "IS_POSITIVE_CONTROL", "IS_NEGATIVE_CONTROL",
    "SAMPLE_TYPE", "TUM_NRM_SAMPLEID_MATCH", "EXTERNAL_SAMPLE_ID", "N_X", "N_Y",
    "TRUTH_DATA_DIR", "COMMENT",
)

UNIT_FIELDS = (
    "RUNID", "SAMPLEID", "EXPERIMENTID", "LANEID", "BARCODEID", "LIBPREP",
    "SEQ_VENDOR", "SEQ_PLATFORM", "ILMN_R1_PATH", "ILMN_R2_PATH",
    "PACBIO_R1_PATH", "PACBIO_R2_PATH", "ONT_R1_PATH", "ONT_R2_PATH",
    "UG_R1_PATH", "UG_R2_PATH", "SUBSAMPLE_PCT", "ILMN_TRIM_READ_LENGTH",
    "SAMPLEUSE", "BWA_KMER", "DEEP_MODEL", "ULTIMA_CRAM",
    "ULTIMA_CRAM_ALIGNER", "ULTIMA_CRAM_SNV_CALLER", "ONT_CRAM",
    "ONT_CRAM_ALIGNER", "ONT_CRAM_SNV_CALLER", "PB_BAM", "PB_BAM_ALIGNER",
    "PB_BAM_SNV_CALLER", "COMMENT",
)


def require_files(paths: list[Path], *, expected_bytes: int, label: str) -> None:
    actual_bytes = sum(path.stat().st_size for path in paths)
    if len(paths) != 8 or actual_bytes != expected_bytes:
        raise RuntimeError(
            f"{label}: expected count=8 bytes={expected_bytes}; "
            f"observed count={len(paths)} bytes={actual_bytes}"
        )


def atomic_write_tsv(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    partial = path.with_name(f"{path.name}.partial")
    if partial.exists():
        raise RuntimeError(f"refusing to overwrite partial file: {partial}")
    with partial.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(partial, path)


def stage_truth_controls(config_dir: Path) -> dict[str, str]:
    truth_root = config_dir / "concordance_controls"
    truth_paths: dict[str, str] = {}
    for sample, footprints in TRUTH_SOURCES.items():
        sample_root = truth_root / sample
        truth_paths[sample] = str(sample_root)
        for footprint, sources in footprints.items():
            footprint_dir = sample_root / footprint
            footprint_dir.mkdir(parents=True, exist_ok=True)
            for suffix, source in sources.items():
                if not source.is_file() or source.stat().st_size == 0:
                    raise RuntimeError(f"missing or empty truth source: {source}")
                link = footprint_dir / f"{sample}.{suffix}"
                if link.is_symlink():
                    if link.resolve(strict=True) != source.resolve(strict=True):
                        raise RuntimeError(f"truth link target mismatch: {link}")
                elif link.exists():
                    raise RuntimeError(f"truth destination is not a symlink: {link}")
                else:
                    link.symlink_to(source)
    return truth_paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-repo", required=True, type=Path)
    args = parser.parse_args()
    config_dir = args.analysis_repo.resolve() / "config"
    if not config_dir.is_dir():
        raise RuntimeError(f"analysis config directory does not exist: {config_dir}")
    truth_paths = stage_truth_controls(config_dir)

    sample_rows: list[dict[str, str]] = []
    unit_rows: list[dict[str, str]] = []
    inventory_rows: list[dict[str, str]] = []
    for sample, metadata in SAMPLES.items():
        r1 = sorted(ILMN_ROOT.glob(
            f"{sample}_{metadata['ilmn_index']}_L00[1-8]_R1_001.fastq.gz"
        ))
        r2 = sorted(ILMN_ROOT.glob(
            f"{sample}_{metadata['ilmn_index']}_L00[1-8]_R2_001.fastq.gz"
        ))
        require_files(r1, expected_bytes=metadata["ilmn_bytes"][0], label=f"{sample} ILMN R1")
        require_files(r2, expected_bytes=metadata["ilmn_bytes"][1], label=f"{sample} ILMN R2")

        truth = truth_paths.get(sample, "na")
        has_truth = sample in truth_paths
        sample_rows.append({
            "SAMPLEID": sample,
            "SAMPLESOURCE": str(metadata["source"]),
            "SAMPLECLASS": "research",
            "BIOLOGICAL_SEX": str(metadata["sex"]),
            "CONCORDANCE_CONTROL_PATH": truth,
            "IS_POSITIVE_CONTROL": str(has_truth).lower(),
            "IS_NEGATIVE_CONTROL": "false",
            "SAMPLE_TYPE": "gdna",
            "TUM_NRM_SAMPLEID_MATCH": "na",
            "EXTERNAL_SAMPLE_ID": sample,
            "N_X": "1" if metadata["sex"] == "male" else "na",
            "N_Y": "1" if metadata["sex"] == "male" else "na",
            "TRUTH_DATA_DIR": truth,
            "COMMENT": f"Betelgeuse full eight-lane ILMN; expected SMN1/SMN2={metadata['expected_smn']}",
        })
        unit_rows.append({
            "RUNID": "BETELGEUSE-ILMN",
            "SAMPLEID": sample,
            "EXPERIMENTID": "ILMNFULL",
            "LANEID": "ILMN8",
            "BARCODEID": "nobarcode",
            "LIBPREP": "UNKNOWN",
            "SEQ_VENDOR": "ILMN",
            "SEQ_PLATFORM": "NOVASEQ",
            "ILMN_R1_PATH": ",".join(map(str, r1)),
            "ILMN_R2_PATH": ",".join(map(str, r2)),
            "PACBIO_R1_PATH": "na", "PACBIO_R2_PATH": "na",
            "ONT_R1_PATH": "na", "ONT_R2_PATH": "na",
            "UG_R1_PATH": "na", "UG_R2_PATH": "na",
            "SUBSAMPLE_PCT": "1", "ILMN_TRIM_READ_LENGTH": "",
            "SAMPLEUSE": "sample", "BWA_KMER": "19", "DEEP_MODEL": "WGS",
            "ULTIMA_CRAM": "na", "ULTIMA_CRAM_ALIGNER": "na",
            "ULTIMA_CRAM_SNV_CALLER": "na", "ONT_CRAM": "na",
            "ONT_CRAM_ALIGNER": "na", "ONT_CRAM_SNV_CALLER": "na",
            "PB_BAM": "na", "PB_BAM_ALIGNER": "na", "PB_BAM_SNV_CALLER": "na",
            "COMMENT": "native DRAGEN and short-read callers; ILMN only",
        })
        inventory_rows.extend((
            {"sample": sample, "input": "ILMN-R1", "count": "8", "bytes": str(metadata["ilmn_bytes"][0])},
            {"sample": sample, "input": "ILMN-R2", "count": "8", "bytes": str(metadata["ilmn_bytes"][1])},
        ))

    atomic_write_tsv(config_dir / "samples.tsv", SAMPLE_FIELDS, sample_rows)
    atomic_write_tsv(config_dir / "units.tsv", UNIT_FIELDS, unit_rows)
    atomic_write_tsv(
        config_dir / "betelgeuse_ilmn_input_inventory.tsv",
        ("sample", "input", "count", "bytes"),
        inventory_rows,
    )
    print(f"wrote {len(sample_rows)} ILMN-only samples and units under {config_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
