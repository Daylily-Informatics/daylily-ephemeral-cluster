#!/usr/bin/env python3
"""Build one exact runtime subset from the validated 20-subject manifests."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


MANIFESTS = (
    "specimens",
    "samples",
    "libraries",
    "sequencing_inputs",
    "analysis_units",
    "analysis_unit_inputs",
)
EXPECTED_FULL_COUNTS = {
    "specimens": 20,
    "samples": 20,
    "libraries": 40,
    "sequencing_inputs": 80,
    "analysis_units": 20,
    "analysis_unit_inputs": 80,
}
FASTQ_COLUMNS = (
    "ILMN_R1_PATH",
    "ILMN_R2_PATH",
    "PACBIO_R1_PATH",
    "PACBIO_R2_PATH",
    "ONT_R1_PATH",
    "ONT_R2_PATH",
    "UG_R1_PATH",
    "UG_R2_PATH",
)
ONT_CHUNK_RE = re.compile(r"_(\d+)\.fastq\.gz$")
HG003_RUNTIME_RUN_ALIASES = {
    "20260618_LH01106_0011_A23MFMCLT3": "20260618-LH01106-0011-A23MFMCLT3",
    "20260616_0040_3B_PBK89197_822a87b5": "20260616-0040-3B-PBK89197-822a87b5",
    "20260616_0041_3C_PBK89101_bd86eaac": "20260616-0041-3C-PBK89101-bd86eaac",
    "20260616_0048_3A_PBM08268_14b096e3": "20260616-0048-3A-PBM08268-14b096e3",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader.fieldnames or ()), list(reader)


def write_tsv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def split_paths(value: str) -> list[str]:
    return [path for path in value.split(",") if path]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-dir", type=Path, required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--sample", required=True)
    parser.add_argument("--ilmn-subsample-pct", required=True)
    parser.add_argument("--ont-start-hour", type=int, required=True)
    parser.add_argument("--ont-end-hour", type=int, required=True)
    args = parser.parse_args()

    if args.ont_start_hour < 0 or args.ont_end_hour <= args.ont_start_hour:
        raise ValueError("invalid half-open ONT hour window")

    full_summary = json.loads((args.full_dir / "generation_summary.json").read_text())
    if full_summary["counts"] != EXPECTED_FULL_COUNTS:
        raise ValueError(f"unexpected full manifest counts: {full_summary['counts']}")

    columns: dict[str, list[str]] = {}
    full: dict[str, list[dict[str, str]]] = {}
    for manifest in MANIFESTS:
        path = args.full_dir / f"{manifest}.tsv"
        if sha256(path) != full_summary["output_sha256"][path.name]:
            raise ValueError(f"full manifest checksum drift: {path}")
        columns[manifest], full[manifest] = read_tsv(path)

    analysis_units = [
        dict(row)
        for row in full["analysis_units"]
        if row["SAMPLEID"] == args.sample
    ]
    if len(analysis_units) != 1:
        raise ValueError(f"expected one analysis unit for {args.sample}")
    analysis_units[0]["SUBSAMPLE_PCT"] = args.ilmn_subsample_pct
    analysis_units[0]["ONT_SUBSAMPLE_PCT"] = ""
    analysis_unit_ids = {row["ANALYSIS_UNIT_UID"] for row in analysis_units}

    analysis_unit_inputs = [
        row
        for row in full["analysis_unit_inputs"]
        if row["ANALYSIS_UNIT_UID"] in analysis_unit_ids
    ]
    sequencing_input_ids = {
        row["SEQUENCING_INPUT_UID"] for row in analysis_unit_inputs
    }
    sequencing_inputs = [
        dict(row)
        for row in full["sequencing_inputs"]
        if row["SEQUENCING_INPUT_UID"] in sequencing_input_ids
    ]
    if {row["SEQUENCING_INPUT_UID"] for row in sequencing_inputs} != sequencing_input_ids:
        raise ValueError("runtime sequencing-input join coverage mismatch")

    source_runids = {row["RUNID"] for row in sequencing_inputs}
    if args.sample != "HG003" or source_runids != set(HG003_RUNTIME_RUN_ALIASES):
        raise ValueError(
            f"unexpected runtime run IDs for explicit HG003 aliases: {source_runids}"
        )
    run_aliases: list[dict[str, str]] = []
    for row in sequencing_inputs:
        source_runid = row["RUNID"]
        runtime_runid = HG003_RUNTIME_RUN_ALIASES[source_runid]
        row["RUNID"] = runtime_runid
        row["SEQUENCING_INPUT_COMMENT"] += f"; source RUNID {source_runid}"
        run_aliases.append(
            {
                "sequencing_run_euid": row["SEQUENCING_RUN_EUID"],
                "source_runid": source_runid,
                "runtime_runid": runtime_runid,
            }
        )
    if any(re.search(r"[._]", item["runtime_runid"]) for item in run_aliases):
        raise ValueError(f"runtime RUNID alias violates DayOA SQ/RU constraints: {run_aliases}")

    library_ids = {row["LIBRARY_ID"] for row in sequencing_inputs}
    libraries = [
        row
        for row in full["libraries"]
        if row["LIBRARY_ID"] in library_ids and row["SAMPLEID"] == args.sample
    ]
    samples = [row for row in full["samples"] if row["SAMPLEID"] == args.sample]
    specimen_ids = {row["SPECIMEN_ID"] for row in samples}
    specimens = [
        row for row in full["specimens"] if row["SPECIMEN_ID"] in specimen_ids
    ]

    runtime = {
        "specimens": specimens,
        "samples": samples,
        "libraries": libraries,
        "sequencing_inputs": sequencing_inputs,
        "analysis_units": analysis_units,
        "analysis_unit_inputs": analysis_unit_inputs,
    }
    expected_runtime_counts = {
        "specimens": 1,
        "samples": 1,
        "libraries": 2,
        "sequencing_inputs": 4,
        "analysis_units": 1,
        "analysis_unit_inputs": 4,
    }
    observed_counts = {name: len(rows) for name, rows in runtime.items()}
    if observed_counts != expected_runtime_counts:
        raise ValueError(f"runtime count mismatch: {observed_counts}")

    full_paths: list[str] = []
    ilmn_paths: list[str] = []
    ont_paths: list[str] = []
    ont_selected_by_run: dict[str, int] = {}
    selected_ont_paths: list[str] = []
    for row in sequencing_inputs:
        for column in FASTQ_COLUMNS:
            paths = split_paths(row[column])
            full_paths.extend(paths)
            if column in {"ILMN_R1_PATH", "ILMN_R2_PATH"}:
                ilmn_paths.extend(paths)
            if column == "ONT_R1_PATH" and paths:
                ont_paths.extend(paths)
                selected = []
                for path in paths:
                    match = ONT_CHUNK_RE.search(path)
                    if match is None:
                        raise ValueError(f"unparseable ONT chunk hour: {path}")
                    hour = int(match.group(1))
                    if args.ont_start_hour <= hour < args.ont_end_hour:
                        selected.append(path)
                ont_selected_by_run[row["SEQUENCING_RUN_EUID"]] = len(selected)
                selected_ont_paths.extend(selected)

    if len(full_paths) != len(set(full_paths)):
        raise ValueError("runtime paths are not unique")
    if len(ilmn_paths) != 16 or len(ont_paths) != 438:
        raise ValueError(
            f"unexpected HG003 full paths: ILMN={len(ilmn_paths)}, ONT={len(ont_paths)}"
        )
    if len(ont_selected_by_run) != 3 or set(ont_selected_by_run.values()) != {8}:
        raise ValueError(f"unexpected per-run ONT selection: {ont_selected_by_run}")

    args.runtime_dir.mkdir(parents=True, exist_ok=True)
    output_hashes: dict[str, str] = {}
    for manifest in MANIFESTS:
        path = args.runtime_dir / f"{manifest}.tsv"
        write_tsv(path, columns[manifest], runtime[manifest])
        output_hashes[path.name] = sha256(path)

    full_paths_path = args.runtime_dir / "input_paths.txt"
    full_paths_path.write_text("\n".join(sorted(full_paths)) + "\n")
    effective_paths_path = args.runtime_dir / "effective_input_paths.txt"
    effective_paths = sorted(ilmn_paths + selected_ont_paths)
    effective_paths_path.write_text("\n".join(effective_paths) + "\n")

    summary = {
        "schema": "dayoa.bjuiceprevalanalysis.runtime_subset.v1",
        "sample": args.sample,
        "source_generation_summary_sha256": sha256(
            args.full_dir / "generation_summary.json"
        ),
        "counts": observed_counts,
        "ont_hour_window": {
            "interval": "half-open",
            "timestamp_source": "chunk-hour",
            "start": args.ont_start_hour,
            "end": args.ont_end_hour,
        },
        "analysis_downsampling": {
            "SUBSAMPLE_PCT": args.ilmn_subsample_pct,
            "ONT_SUBSAMPLE_PCT": "",
        },
        "run_aliases": sorted(run_aliases, key=lambda item: item["sequencing_run_euid"]),
        "path_counts": {
            "full_total": len(full_paths),
            "ilmn": len(ilmn_paths),
            "ont_full": len(ont_paths),
            "ont_selected": len(selected_ont_paths),
            "effective_total": len(effective_paths),
            "ont_selected_by_run_euid": ont_selected_by_run,
        },
        "input_paths_sha256": sha256(full_paths_path),
        "effective_input_paths_sha256": sha256(effective_paths_path),
        "output_sha256": output_hashes,
    }
    (args.runtime_dir / "runtime_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
