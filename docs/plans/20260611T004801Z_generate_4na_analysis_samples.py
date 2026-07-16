#!/usr/bin/env python3
"""Generate intended 4NA chip-pair analysis_samples.tsv inputs.

This does not stage data or launch workflows. It rewrites the prior validated
4NA chip-pair unit table into eight single-sample manifests that can be used
once the required read-only/pass-through source paths exist on dyecX4.
"""

from __future__ import annotations

import csv
import pathlib


SOURCE_UNITS = pathlib.Path(
    "docs/plans/20260605T000000Z_hyb_only_mounted_fastq_kitchensink_logs/"
    "hybrid_hiomr_na4_ds20x_split_config/20260606T153500Z_hybrid_hiomr_na4_ds20x_split_units.tsv"
)
OUTPUT_ROOT = pathlib.Path(
    "docs/plans/20260611T004801Z_dyecX4_4na_smn12_export_cleanup_logs/4na_inputs"
)
ILMN_MOUNT_ROOT = "/fsx/run_dir_mounts/4na-ilmn-ds20x-realcopy"
STAMP = "20260611T004801Z"


SAMPLE_META = {
    "NA00232": {"experiment": "SMN", "external": "NA00232"},
    "NA09677": {"experiment": "SMN", "external": "NA09677"},
    "NA03986": {"experiment": "DMPK", "external": "NA03986"},
    "NA05164": {"experiment": "DMPK", "external": "NA05164"},
}


HEADER = [
    "RUN_ID",
    "SAMPLE_ID",
    "EXPERIMENTID",
    "SAMPLE_TYPE",
    "LIB_PREP",
    "SEQ_VENDOR",
    "SEQ_PLATFORM",
    "LANE",
    "SEQBC_ID",
    "PATH_TO_CONCORDANCE_DATA_DIR",
    "ILMN_R1_FQ",
    "ILMN_R2_FQ",
    "ONT_R1_FQ",
    "ONT_R2_FQ",
    "ONT_FLOWCELL_ID",
    "STAGE_DIRECTIVE",
    "SUBSAMPLE_PCT",
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


def rewrite_ilmn_path(path: str) -> str:
    basename = pathlib.PurePosixPath(path).name
    if not basename:
        raise ValueError(f"Cannot rewrite empty ILMN path: {path!r}")
    return f"{ILMN_MOUNT_ROOT}/{basename}"


def chip_pair_slug(value: str) -> str:
    return value.replace("-", "")


def main() -> int:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    rows = []
    with SOURCE_UNITS.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for unit in reader:
            sample_id = unit["SAMPLEID"]
            if sample_id not in SAMPLE_META:
                raise SystemExit(f"Unexpected sample in source units: {sample_id}")
            chip_pair = unit["LANEID"]
            analysis_id = (
                f"hybonly_hybrid_hiomr_smn12_gba_{sample_id.lower()}_"
                f"{chip_pair_slug(chip_pair)}_dryrun_{STAMP}"
            )
            row = {
                "RUN_ID": unit["RUNID"],
                "SAMPLE_ID": sample_id,
                "EXPERIMENTID": unit["EXPERIMENTID"],
                "SAMPLE_TYPE": "gdna",
                "LIB_PREP": unit["LIBPREP"],
                "SEQ_VENDOR": unit["SEQ_VENDOR"],
                "SEQ_PLATFORM": unit["SEQ_PLATFORM"],
                "LANE": chip_pair,
                "SEQBC_ID": unit["BARCODEID"],
                "PATH_TO_CONCORDANCE_DATA_DIR": "na",
                "ILMN_R1_FQ": rewrite_ilmn_path(unit["ILMN_R1_PATH"]),
                "ILMN_R2_FQ": rewrite_ilmn_path(unit["ILMN_R2_PATH"]),
                "ONT_R1_FQ": unit["ONT_R1_PATH"],
                "ONT_R2_FQ": "",
                "ONT_FLOWCELL_ID": chip_pair,
                "STAGE_DIRECTIVE": "pass_through",
                "SUBSAMPLE_PCT": unit.get("SUBSAMPLE_PCT") or "na",
                "SAMPLEUSE": unit.get("SAMPLEUSE") or "sample",
                "BWA_KMER": unit.get("BWA_KMER") or "19",
                "DEEP_MODEL": unit.get("DEEP_MODEL") or "WGS",
                "IS_POS_CTRL": "false",
                "IS_NEG_CTRL": "false",
                "TUM_NRM_SAMPLEID_MATCH": "na",
                "N_X": "1",
                "N_Y": "1",
                "EXTERNAL_SAMPLE_ID": SAMPLE_META[sample_id]["external"],
            }
            analysis_dir = OUTPUT_ROOT / analysis_id
            analysis_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = analysis_dir / "analysis_samples.tsv"
            with manifest_path.open("w", newline="") as out_handle:
                writer = csv.DictWriter(out_handle, fieldnames=HEADER, delimiter="\t")
                writer.writeheader()
                writer.writerow(row)
            rows.append(
                {
                    "analysis_id": analysis_id,
                    "sample_id": sample_id,
                    "chip_pair": chip_pair,
                    "analysis_samples": str(manifest_path),
                    "ilmn_r1": row["ILMN_R1_FQ"],
                    "ilmn_r2": row["ILMN_R2_FQ"],
                    "ont_fastq_count": str(row["ONT_R1_FQ"].count(".fastq.gz")),
                    "dy_command": (
                        "dy-r produce_smn12_orthogonal_calls produce_htd_calls "
                        "produce_sentdhiomr_segdup -p -T 0 -k -j 500 -n"
                    ),
                }
            )

    summary_path = OUTPUT_ROOT / "4na_intended_analyses.tsv"
    with summary_path.open("w", newline="") as handle:
        fields = [
            "analysis_id",
            "sample_id",
            "chip_pair",
            "analysis_samples",
            "ilmn_r1",
            "ilmn_r2",
            "ont_fastq_count",
            "dy_command",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    print(summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
