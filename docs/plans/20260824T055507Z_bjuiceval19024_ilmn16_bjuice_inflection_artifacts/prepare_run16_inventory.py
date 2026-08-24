#!/usr/bin/env python3
"""Build the exact Run 4 source inventory for bjuiceval-19024.

The source crosswalk controls AU pairings. Existing audited selections control
file choice. Three explicitly recorded Run 4 ILMN selections are supplied by
the live headnode inventory captured for this task. Every S3 URI is rebased to
one of the two exact read-only DRA mount roots; no path discovery is performed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


TARGET_ILMN_RUN = "20260722_LH01106_0016_A23WW3YLT4"
ILMN_S3_PREFIX = (
    "s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/"
)
ILMN_MOUNT_PREFIX = "/fsx/run_dir_mounts/hybrid-crosswalk-ilmn-2026/"
ONT_S3_PREFIX = (
    "s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/"
)
ONT_MOUNT_PREFIX = "/fsx/run_dir_mounts/hybrid-crosswalk-ont-pca100/"

MISSING_SAMPLE_NAMES = {
    "spec_60": "BUCCAL1",
    "spec_68": "BUCCAL2",
    "spec_75": "BUCCAL3",
}

ILMN_RUN_RE = re.compile(r"/((?:20)[0-9]{6}_LH[0-9]+_[0-9]+_[A-Z0-9]+)/")
ONT_RUN_RE = re.compile(r"/((?:20)[0-9]{6}_ONT_BGS_[^/]+)/")
BARCODE_RE = re.compile(r"/(barcode[0-9]+)/")
MISSING_FASTQ_RE = re.compile(
    r"/(?P<sample>BUCCAL[123])_S(?P<sample_number>37|38|39)_"
    r"L(?P<lane>[0-9]{3})_R(?P<mate>[12])_001\.fastq\.gz$"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def equivalent(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return json.dumps(left, sort_keys=True, separators=(",", ":")) == json.dumps(
        right, sort_keys=True, separators=(",", ":")
    )


def rebase_s3_uri(uri: str, *, s3_prefix: str, mount_prefix: str) -> str:
    if not uri.startswith(s3_prefix):
        raise ValueError(f"source URI leaves exact DRA prefix: {uri}")
    return mount_prefix + uri.removeprefix(s3_prefix)


def rebase_items(
    items: list[Mapping[str, Any]], *, s3_prefix: str, mount_prefix: str
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for source in items:
        item = deepcopy(dict(source))
        uri = str(item.get("s3_uri", ""))
        item["mount_path"] = rebase_s3_uri(
            uri, s3_prefix=s3_prefix, mount_prefix=mount_prefix
        )
        result.append(item)
    return result


def index_prior_inventory(
    inventory: Mapping[str, Any],
) -> tuple[dict[tuple[str, str], Mapping[str, Any]], dict[tuple[str, str], Mapping[str, Any]]]:
    ilmn_index: dict[tuple[str, str], Mapping[str, Any]] = {}
    ont_index: dict[tuple[str, str], Mapping[str, Any]] = {}
    for selection in inventory.get("selections", {}).values():
        for ilmn in selection.get("ilmn", {}).values():
            key = (str(ilmn["run_id"]), str(ilmn["sample_id"]))
            prior = ilmn_index.get(key)
            if prior is not None and not equivalent(prior, ilmn):
                raise ValueError(f"conflicting prior ILMN selections for {key}")
            ilmn_index[key] = ilmn
        ont = selection.get("ont")
        if not ont:
            continue
        fastqs = list(ont.get("fastqs", []))
        if not fastqs:
            raise ValueError(f"prior ONT selection has no FASTQs: {ont}")
        barcode_match = BARCODE_RE.search(str(fastqs[0].get("s3_uri", "")))
        if not barcode_match:
            raise ValueError(f"prior ONT selection has no barcode path: {fastqs[0]}")
        key = (str(ont["run_id"]), barcode_match.group(1))
        prior = ont_index.get(key)
        if prior is not None and not equivalent(prior, ont):
            raise ValueError(f"conflicting prior ONT selections for {key}")
        ont_index[key] = ont
    return ilmn_index, ont_index


def build_missing_ilmn(path: Path) -> dict[str, dict[str, Any]]:
    rows = load_tsv(path)
    if len(rows) != 48:
        raise ValueError(f"missing ILMN inventory must have 48 rows; found {len(rows)}")
    grouped: dict[str, list[dict[str, str]]] = {}
    seen_paths: set[str] = set()
    for row in rows:
        library_id = row["ILMN_LIB_ID"]
        expected_sample = MISSING_SAMPLE_NAMES.get(library_id)
        if expected_sample is None or row["SAMPLE_NAME"] != expected_sample:
            raise ValueError(f"unexpected missing-library mapping: {row}")
        path_value = row["MOUNT_PATH"]
        if not path_value.startswith(ILMN_MOUNT_PREFIX):
            raise ValueError(f"missing ILMN path leaves exact DRA root: {path_value}")
        if path_value in seen_paths:
            raise ValueError(f"duplicate missing ILMN path: {path_value}")
        seen_paths.add(path_value)
        if int(row["SIZE_BYTES"]) <= 0:
            raise ValueError(f"missing ILMN path is empty: {path_value}")
        match = MISSING_FASTQ_RE.search(path_value)
        if not match or match.group("sample") != expected_sample:
            raise ValueError(f"missing ILMN filename differs from mapping: {path_value}")
        grouped.setdefault(library_id, []).append(row)

    result: dict[str, dict[str, Any]] = {}
    for library_id, expected_sample in MISSING_SAMPLE_NAMES.items():
        selected = grouped.get(library_id, [])
        if len(selected) != 16:
            raise ValueError(
                f"{library_id} must have 8 lanes x 2 mates; found {len(selected)}"
            )
        mates: dict[str, list[dict[str, Any]]] = {"1": [], "2": []}
        for row in selected:
            match = MISSING_FASTQ_RE.search(row["MOUNT_PATH"])
            if match is None:
                raise AssertionError("validated FASTQ no longer matches")
            relative = row["MOUNT_PATH"].removeprefix(ILMN_MOUNT_PREFIX)
            item = {
                "lane": match.group("lane"),
                "last_modified": f"epoch:{row['MTIME_EPOCH']}",
                "mount_path": row["MOUNT_PATH"],
                "s3_uri": ILMN_S3_PREFIX + relative,
                "size": int(row["SIZE_BYTES"]),
            }
            mates[match.group("mate")].append(item)
        for mate in ("1", "2"):
            mates[mate].sort(key=lambda item: str(item["lane"]))
            lanes = [str(item["lane"]) for item in mates[mate]]
            if lanes != [f"{lane:03d}" for lane in range(1, 9)]:
                raise ValueError(f"{library_id} mate {mate} lanes are not 001-008: {lanes}")
        result[library_id] = {
            "lanes": [f"{lane:03d}" for lane in range(1, 9)],
            "r1": mates["1"],
            "r2": mates["2"],
            "run_id": TARGET_ILMN_RUN,
            "sample_id": library_id,
            "sample_name": expected_sample,
            "source_id": "hybrid-crosswalk-ilmn-2026",
            "selection_evidence": "task live headnode inventory plus corrected TSV and Run 4 SampleSheet",
        }
    return result


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    prior = json.loads(args.source_inventory.read_text(encoding="utf-8"))
    ilmn_index, ont_index = index_prior_inventory(prior)
    missing_ilmn = build_missing_ilmn(args.missing_ilmn_inventory)
    corrected = load_tsv(args.corrected)
    rows = [row for row in corrected if row.get("ilmn_run") == "16"]
    if len(rows) != 40 or len({row["unit_id"] for row in rows}) != 40:
        raise ValueError("corrected Run 4 cohort must contain 40 distinct display AU rows")

    selections: dict[str, dict[str, Any]] = {}
    prior_ilmn_count = 0
    live_ilmn_count = 0
    ont_runs: dict[str, int] = {}
    for source_line, row in (
        (line, row) for line, row in enumerate(corrected, start=2) if row["ilmn_run"] == "16"
    ):
        if row["confidence"] != "ok" or row["ilmn_ok"] != "TRUE" or row["ont_ok"] != "TRUE":
            raise ValueError(f"corrected line {source_line} is not approved/readable")
        ilmn_match = ILMN_RUN_RE.search(row["ilmn_fastq_dir"])
        ont_match = ONT_RUN_RE.search(row["ont_fastq_pass_s3"])
        if not ilmn_match or not ont_match:
            raise ValueError(f"corrected line {source_line} lacks a physical run URI")
        ilmn_run = ilmn_match.group(1)
        ont_run = ont_match.group(1)
        if ilmn_run != TARGET_ILMN_RUN:
            raise ValueError(f"corrected line {source_line} left Run 4: {ilmn_run}")

        ilmn_source = ilmn_index.get((ilmn_run, row["ilmn_lib_id"]))
        if ilmn_source is None:
            ilmn_source = missing_ilmn.get(row["ilmn_lib_id"])
            if ilmn_source is None:
                raise ValueError(f"corrected line {source_line} has no exact ILMN selection")
            live_ilmn_count += 1
        else:
            prior_ilmn_count += 1
        ilmn = deepcopy(dict(ilmn_source))
        ilmn["r1"] = rebase_items(
            list(ilmn["r1"]), s3_prefix=ILMN_S3_PREFIX, mount_prefix=ILMN_MOUNT_PREFIX
        )
        ilmn["r2"] = rebase_items(
            list(ilmn["r2"]), s3_prefix=ILMN_S3_PREFIX, mount_prefix=ILMN_MOUNT_PREFIX
        )
        if len(ilmn["r1"]) != 8 or len(ilmn["r2"]) != 8:
            raise ValueError(f"corrected line {source_line} does not have 8 ILMN lane pairs")
        if any(
            not str(item["s3_uri"]).startswith(row["ilmn_fastq_dir"])
            for mate in ("r1", "r2")
            for item in ilmn[mate]
        ):
            raise ValueError(f"corrected line {source_line} ILMN selection leaves row prefix")

        ont_source = ont_index.get((ont_run, row["ont_barcode"]))
        if ont_source is None:
            raise ValueError(f"corrected line {source_line} has no exact ONT selection")
        ont = deepcopy(dict(ont_source))
        ont["fastqs"] = rebase_items(
            list(ont["fastqs"]), s3_prefix=ONT_S3_PREFIX, mount_prefix=ONT_MOUNT_PREFIX
        )
        if any(
            not str(item["s3_uri"]).startswith(row["ont_fastq_pass_s3"])
            for item in ont["fastqs"]
        ):
            raise ValueError(f"corrected line {source_line} ONT selection leaves row prefix")
        if str(ont.get("flowcell_id")) not in row["ont_chips"].split(";"):
            raise ValueError(f"corrected line {source_line} ONT flowcell leaves row chip set")
        hours = {int(item["hour"]) for item in ont["fastqs"]}
        if not set(range(24)).issubset(hours):
            raise ValueError(f"corrected line {source_line} ONT selection lacks hours 0-23")
        ont_runs[ont_run] = ont_runs.get(ont_run, 0) + 1

        selection_key = f"run16-line{source_line:03d}-{row['unit_id']}"
        selections[selection_key] = {
            "biological_sample": row["canonical"],
            "corrected_source_line": source_line,
            "corrected_unit_id": row["unit_id"],
            "ilmn": {"ilmn-run16": ilmn},
            "logical_run": 4,
            "ont": ont,
        }

    if len(selections) != 40:
        raise ValueError(f"prepared inventory must have 40 selections; found {len(selections)}")
    if prior_ilmn_count != 37 or live_ilmn_count != 3:
        raise ValueError(
            f"expected 37 prior + 3 live ILMN selections; got {prior_ilmn_count} + {live_ilmn_count}"
        )

    return {
        "schema": "dyec.bjuiceval19024_run16_source_inventory.v1",
        "generated_at": args.generated_at,
        "cluster": "bjuiceval-19024",
        "crosswalk": str(args.corrected),
        "crosswalk_sha256": sha256(args.corrected),
        "prior_source_inventory": str(args.source_inventory),
        "prior_source_inventory_sha256": sha256(args.source_inventory),
        "missing_ilmn_inventory": str(args.missing_ilmn_inventory),
        "missing_ilmn_inventory_sha256": sha256(args.missing_ilmn_inventory),
        "dra_mappings": [
            {
                "association_id": "dra-0699649d249652226",
                "platform": "ILMN",
                "read_only": True,
                "s3_prefix": ILMN_S3_PREFIX,
                "mount_prefix": ILMN_MOUNT_PREFIX,
            },
            {
                "association_id": "dra-0fe499a0851d5c3ff",
                "platform": "ONT",
                "read_only": True,
                "s3_prefix": ONT_S3_PREFIX,
                "mount_prefix": ONT_MOUNT_PREFIX,
            },
        ],
        "selections": selections,
        "summary": {
            "analysis_unit_count": len(selections),
            "prior_audited_ilmn_count": prior_ilmn_count,
            "live_audited_ilmn_count": live_ilmn_count,
            "audited_ont_count": len(selections),
            "ont_physical_run_counts": dict(sorted(ont_runs.items())),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corrected", type=Path, required=True)
    parser.add_argument("--source-inventory", type=Path, required=True)
    parser.add_argument("--missing-ilmn-inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--generated-at", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError(f"output already exists: {args.output}")
    result = prepare(args)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "output_sha256": sha256(args.output),
                "status": "CONFIG_COMPLETE",
                "summary": result["summary"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
