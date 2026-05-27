#!/usr/bin/env python3
"""Build Altair reanalysis input manifests and the Run 2 index report."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import boto3


PROFILE = "lsmc"
REGION = "us-west-2"
BUCKET = "lsmc-ssf-sequencing-data"
BASE_PREFIX = "basecalls/lsmc/ssf-hq/LH01106/2026"
REFERENCE_BUCKET = "s3://lsmc-dayoa-omics-analysis-us-west-2"
GIAB_TRUTH_BASE = (
    "/fsx/data/genomic_data/organism_annotations/H_sapiens/hg38/"
    "controls/giab/snv/v4.2.1"
)
ONT_30X_CRAM = (
    "/fsx/data/genomic_data/organism_reads/H_sapiens/giab/agbt_2026/"
    "ont/HG003_30x.cleaned.cram"
)
RUNS = {
    "20260512_LH01106_0006_A23K3H2LT4": {
        "analysis_id": "re-ana-20260512_LH01106_0006_A23K3H2LT4",
        "run_name": "20260512_ILMN_Altair_Run_1",
    },
    "20260514_LH01106_0009_B23TVLGLT4": {
        "analysis_id": "re-ana-20260514_LH01106_0009_B23TVLGLT4",
        "run_name": "20260514_ILMN_Altair_Run_3",
    },
}
RUN2 = "20260512_LH01106_0007_B23K5JKLT4"
OUT_ROOT = Path("tmp/altair-reanalysis")

MANIFEST_HEADER = [
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
    "ILMN_R1_FQ",
    "ILMN_R2_FQ",
    "ONT_CRAM",
    "ONT_CRAM_ALIGNER",
    "ONT_CRAM_SNV_CALLER",
    "STAGE_DIRECTIVE",
    "STAGE_TARGET",
    "MOUNT_ID",
    "MOUNT_SOURCE_S3_URI",
    "MOUNT_FSX_PATH",
    "DATA_LOCALITY",
    "SUBSAMPLE_PCT",
    "SAMPLEUSE",
    "BWA_KMER",
    "DEEP_MODEL",
    "IS_POS_CTRL",
    "IS_NEG_CTRL",
    "N_X",
    "N_Y",
    "EXTERNAL_SAMPLE_ID",
]

FASTQ_RE = re.compile(r"^(?P<sample>.+)_S[0-9]+_L(?P<lane>[0-9]{3})_R(?P<read>[12])_001\.fastq\.gz$")

GIAB_SEX = {
    "HG001": ("female", "2", "0"),
    "HG002": ("male", "1", "1"),
    "HG003": ("male", "1", "1"),
    "HG004": ("female", "2", "0"),
    "HG005": ("male", "1", "1"),
    "HG006": ("male", "1", "1"),
    "HG007": ("female", "2", "0"),
}


@dataclass(frozen=True)
class SampleRow:
    sample_id: str
    index: str
    index2: str


def s3_client():
    return boto3.Session(profile_name=PROFILE, region_name=REGION).client("s3")


def get_text(s3, key: str) -> str:
    return s3.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode("utf-8")


def read_samplesheet(s3, run_id: str) -> tuple[str, list[SampleRow]]:
    text = get_text(s3, f"{BASE_PREFIX}/{run_id}/SampleSheet.csv")
    lines = text.splitlines()
    run_name = ""
    for line in lines:
        if line.startswith("RunName,"):
            run_name = line.split(",", 1)[1].strip()
            break
    start = lines.index("[BCLConvert_Data]") + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("[")), len(lines))
    rows = [
        SampleRow(row["Sample_ID"], row["Index"], row["Index2"])
        for row in csv.DictReader(lines[start:end])
        if row.get("Sample_ID")
    ]
    return run_name, rows


def list_fastqs(s3, run_id: str) -> dict[str, dict[str, dict[str, str]]]:
    fastq_prefix = f"{BASE_PREFIX}/{run_id}/Analysis/1/Data/BCLConvert/fastq/"
    by_sample: dict[str, dict[str, dict[str, str]]] = defaultdict(lambda: defaultdict(dict))
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=fastq_prefix):
        for obj in page.get("Contents", []):
            name = obj["Key"].rsplit("/", 1)[-1]
            match = FASTQ_RE.match(name)
            if not match:
                continue
            if name.startswith("Undetermined_"):
                continue
            by_sample[match.group("sample")][match.group("lane")][match.group("read")] = (
                f"/fsx/run_dir_mounts/{run_id}/Analysis/1/Data/BCLConvert/fastq/{name}"
            )
    return by_sample


def sample_base(sample_id: str) -> str:
    return sample_id.split("-", 1)[0]


def truth_path(base: str) -> str:
    return f"{GIAB_TRUTH_BASE}/{base}/" if base in GIAB_SEX else "na"


def metadata_for(sample_id: str) -> dict[str, str]:
    base = sample_base(sample_id)
    sex, n_x, n_y = GIAB_SEX.get(base, ("na", "na", "na"))
    is_giab = base in GIAB_SEX
    source = "buccal" if sample_id.startswith("BUCCAL") else ("blood" if is_giab else "unknown")
    return {
        "SAMPLESOURCE": source,
        "SAMPLECLASS": "research",
        "BIOLOGICAL_SEX": sex,
        "SAMPLE_TYPE": "gdna",
        "PATH_TO_CONCORDANCE_DATA_DIR": truth_path(base),
        "CONCORDANCE_CONTROL_PATH": truth_path(base),
        "TRUTH_DATA_DIR": truth_path(base),
        "SAMPLEUSE": "posControl" if is_giab else "sample",
        "IS_POS_CTRL": "true" if is_giab else "false",
        "IS_NEG_CTRL": "false",
        "N_X": n_x,
        "N_Y": n_y,
        "EXTERNAL_SAMPLE_ID": base if is_giab else sample_id,
    }


def validate_pairs(sample_id: str, lanes: dict[str, dict[str, str]]) -> tuple[list[str], list[str]]:
    lane_ids = sorted(lanes)
    if lane_ids != [f"{idx:03d}" for idx in range(1, 9)]:
        raise SystemExit(f"{sample_id}: expected L001-L008, observed {lane_ids}")
    r1s: list[str] = []
    r2s: list[str] = []
    for lane in lane_ids:
        reads = lanes[lane]
        if set(reads) != {"1", "2"}:
            raise SystemExit(f"{sample_id} lane {lane}: expected R1/R2, observed {sorted(reads)}")
        r1 = reads["1"]
        r2 = reads["2"]
        if r1.replace("_R1_", "_R2_") != r2:
            raise SystemExit(f"{sample_id} lane {lane}: R1/R2 filenames are out of order")
        r1s.append(r1)
        r2s.append(r2)
    return r1s, r2s


def build_manifest(s3, run_id: str, analysis_id: str, *, hybrid_hg003_only: bool = False) -> dict[str, object]:
    run_name, samplesheet_rows = read_samplesheet(s3, run_id)
    non_ntc = [row for row in samplesheet_rows if row.sample_id != "NTC"]
    fastqs = list_fastqs(s3, run_id)
    out_dir = OUT_ROOT / analysis_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "analysis_samples.tsv"
    rows_written = 0
    pair_counts: dict[str, int] = {}
    wanted = [row for row in non_ntc if not hybrid_hg003_only or row.sample_id == "HG003-a"]
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_HEADER, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for ss_row in wanted:
            if ss_row.sample_id not in fastqs:
                raise SystemExit(f"{run_id} {ss_row.sample_id}: no FASTQs found")
            r1s, r2s = validate_pairs(ss_row.sample_id, fastqs[ss_row.sample_id])
            meta = metadata_for(ss_row.sample_id)
            row = {
                "RUN_ID": run_id,
                "SAMPLE_ID": ss_row.sample_id,
                "EXPERIMENTID": run_name,
                "LIB_PREP": "PF",
                "SEQ_VENDOR": "ILMN",
                "SEQ_PLATFORM": "NOVASEQX",
                "LANE": "0",
                "SEQBC_ID": ss_row.sample_id,
                "ILMN_R1_FQ": ",".join(r1s),
                "ILMN_R2_FQ": ",".join(r2s),
                "ONT_CRAM": ONT_30X_CRAM if hybrid_hg003_only else "",
                "ONT_CRAM_ALIGNER": "ont" if hybrid_hg003_only else "",
                "ONT_CRAM_SNV_CALLER": "sentdont" if hybrid_hg003_only else "",
                "STAGE_DIRECTIVE": "pass_through" if hybrid_hg003_only else "mounted_readonly",
                "STAGE_TARGET": "/data/staged_sample_data",
                "MOUNT_ID": run_id,
                "MOUNT_SOURCE_S3_URI": f"s3://{BUCKET}/{BASE_PREFIX}/{run_id}/",
                "MOUNT_FSX_PATH": f"/fsx/run_dir_mounts/{run_id}/",
                "DATA_LOCALITY": "pass_through" if hybrid_hg003_only else "mounted_readonly",
                "SUBSAMPLE_PCT": "na",
                "BWA_KMER": "19",
                "DEEP_MODEL": "WGS",
                **meta,
            }
            writer.writerow(row)
            rows_written += 1
            pair_counts[ss_row.sample_id] = len(r1s)
    return {
        "run_id": run_id,
        "run_name": run_name,
        "analysis_id": analysis_id,
        "manifest": str(out_path),
        "rows": rows_written,
        "non_ntc_tags": len(non_ntc),
        "pair_counts": pair_counts,
    }


def read_csv_from_s3(s3, key: str) -> list[dict[str, str]]:
    return list(csv.DictReader(get_text(s3, key).splitlines()))


def index_pairs_from_samplesheet(rows: Iterable[SampleRow]) -> set[str]:
    return {f"{row.index}+{row.index2}" for row in rows}


def build_run2_report(s3) -> dict[str, object]:
    run_name, rows = read_samplesheet(s3, RUN2)
    expected = index_pairs_from_samplesheet(rows)
    top_unknown_key = f"{BASE_PREFIX}/{RUN2}/Analysis/1/Data/Demux/Top_Unknown_Barcodes.csv"
    demux_key = f"{BASE_PREFIX}/{RUN2}/Analysis/1/Data/Demux/Demultiplex_Stats.csv"
    top_unknown = read_csv_from_s3(s3, top_unknown_key)
    demux = read_csv_from_s3(s3, demux_key)
    unknown_pairs = {f"{row['index']}+{row['index2']}" for row in top_unknown}
    overlap = sorted(expected & unknown_pairs)
    lane_counts: Counter[str] = Counter()
    lane_top5: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in top_unknown:
        lane = f"L{int(row['Lane']):03d}"
        lane_counts[lane] += int(row["# Reads"])
        if len(lane_top5[lane]) < 5:
            lane_top5[lane].append(
                {
                    "pair": f"{row['index']}+{row['index2']}",
                    "reads": row["# Reads"],
                    "pct_unknown": row["% of Unknown Barcodes"],
                }
            )
    assigned_reads = sum(
        int(row["# Reads"])
        for row in demux
        if row.get("SampleID") != "Undetermined" and row.get("# Reads", "0").isdigit()
    )
    report_path = OUT_ROOT / f"{RUN2}_unexpected_index_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Run 2 Unexpected Index Report",
        "",
        f"- Run: `{RUN2}`",
        f"- RunName: `{run_name}`",
        f"- SampleSheet expected pairs: `{len(expected)}`",
        f"- Top unknown barcode rows: `{len(top_unknown)}`",
        f"- Exact overlap with expected pairs: `{len(overlap)}`",
        f"- Assigned non-Undetermined reads in Demultiplex_Stats.csv: `{assigned_reads}`",
        "",
        "## Lane Top Unknown Barcode Pairs",
        "",
        "| Lane | Top unknown pairs | Top-unknown row read sum |",
        "|---|---|---:|",
    ]
    for lane in sorted(lane_top5):
        pairs = "<br>".join(
            f"`{entry['pair']}` ({entry['reads']}, {entry['pct_unknown']})"
            for entry in lane_top5[lane]
        )
        lines.append(f"| `{lane}` | {pairs} | {lane_counts[lane]} |")
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            "Run 2 named-sample workflows must not be launched from the SampleSheet tags: BCLConvert reports "
            "essentially all reads as unknown barcode reads, and the reported unknown barcode pairs have no "
            "exact overlap with the expected SampleSheet index pairs.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "run_id": RUN2,
        "run_name": run_name,
        "report": str(report_path),
        "expected_pairs": len(expected),
        "top_unknown_rows": len(top_unknown),
        "exact_overlap": len(overlap),
        "assigned_non_undetermined_reads": assigned_reads,
        "lane_unknown_read_sums": dict(sorted(lane_counts.items())),
    }


def main() -> None:
    s3 = s3_client()
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, object]] = []
    for run_id, cfg in RUNS.items():
        summaries.append(build_manifest(s3, run_id, cfg["analysis_id"]))
    hybrid_id = "re-ana-20260514_LH01106_0009_B23TVLGLT4-HG003-hybrid-ilmn-ont"
    summaries.append(build_manifest(s3, "20260514_LH01106_0009_B23TVLGLT4", hybrid_id, hybrid_hg003_only=True))
    summaries.append(build_run2_report(s3))
    summary_path = OUT_ROOT / "manifest_build_summary.json"
    summary_path.write_text(json.dumps(summaries, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(summary_path)
    for item in summaries:
        print(json.dumps(item, sort_keys=True))


if __name__ == "__main__":
    main()
