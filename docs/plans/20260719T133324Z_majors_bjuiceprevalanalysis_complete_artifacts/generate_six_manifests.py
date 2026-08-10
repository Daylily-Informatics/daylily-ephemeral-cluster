#!/usr/bin/env python3
"""Generate exact DayOA 13.0.10 six manifests for Bjuice prevalidation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import OrderedDict
from pathlib import Path


MANIFESTS = (
    "specimens",
    "samples",
    "libraries",
    "sequencing_inputs",
    "analysis_units",
    "analysis_unit_inputs",
)
PRIMARY_KEYS = {
    "specimens": ("SPECIMEN_ID",),
    "samples": ("SAMPLEID",),
    "libraries": ("LIBRARY_ID",),
    "sequencing_inputs": ("SEQUENCING_INPUT_UID",),
    "analysis_units": ("ANALYSIS_UNIT_UID",),
    "analysis_unit_inputs": ("ANALYSIS_UNIT_UID", "INPUT_ORDINAL"),
}
EXPECTED_MATRIX_SHA256 = (
    "3da41aca4f567a560981b2029e873cf5dfc7624ebf8bcf6a1378d5514107d92f"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def template_columns(repo: Path, ref: str, manifest: str) -> list[str]:
    text = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "show",
            f"{ref}:config/templates/{manifest}.tsv",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return text.splitlines()[0].split("\t")


def write_tsv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=columns,
            delimiter="\t",
            lineterminator="\n",
            extrasaction="raise",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def split_paths(value: str) -> list[str]:
    paths = [item for item in value.split(",") if item]
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate path within one legacy manifest cell")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--first-samples", type=Path, required=True)
    parser.add_argument("--first-units", type=Path, required=True)
    parser.add_argument("--second-samples", type=Path, required=True)
    parser.add_argument("--second-units", type=Path, required=True)
    parser.add_argument("--resolved-source", type=Path, required=True)
    parser.add_argument("--reviewed-planner-bundle", type=Path, required=True)
    parser.add_argument("--dayoa-repo", type=Path, required=True)
    parser.add_argument("--dayoa-ref", default="13.0.10")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    observed_matrix_sha = sha256(args.matrix)
    if observed_matrix_sha != EXPECTED_MATRIX_SHA256:
        raise ValueError(
            f"matrix checksum drift: {observed_matrix_sha} != {EXPECTED_MATRIX_SHA256}"
        )

    matrix_rows = read_tsv(args.matrix)
    grouped: OrderedDict[str, dict[str, object]] = OrderedDict()
    ntc_rows = 0
    for row in matrix_rows:
        name = row["specimenExternalName"]
        if name == "NTC":
            ntc_rows += 1
            continue
        if not (name.startswith("HG") or name.startswith("NA")):
            raise ValueError(f"unexpected biological external name: {name}")
        record = grouped.setdefault(
            name,
            {
                "specimen_euid": row["specimenEUID"],
                "sample_euid": row["sampleEUID"],
                "libraries": {},
            },
        )
        if record["specimen_euid"] != row["specimenEUID"]:
            raise ValueError(f"specimen EUID drift for {name}")
        if record["sample_euid"] != row["sampleEUID"]:
            raise ValueError(f"sample EUID drift for {name}")
        libraries = record["libraries"]
        assert isinstance(libraries, dict)
        if row["libType"] in libraries:
            raise ValueError(f"duplicate {row['libType']} matrix row for {name}")
        libraries[row["libType"]] = row

    if len(grouped) != 20 or ntc_rows != 2:
        raise ValueError(
            f"expected 20 biological identities and 2 excluded NTC rows; "
            f"found {len(grouped)} and {ntc_rows}"
        )
    for name, record in grouped.items():
        if set(record["libraries"]) != {"ILMN", "ONT"}:
            raise ValueError(f"expected ILMN and ONT library rows for {name}")

    metadata_rows = read_tsv(args.first_samples) + read_tsv(args.second_samples)
    unit_rows = read_tsv(args.first_units) + read_tsv(args.second_units)
    metadata = {row["SAMPLEID"]: row for row in metadata_rows}
    units = {row["SAMPLEID"]: row for row in unit_rows}
    expected_names = set(grouped)
    if set(metadata) != expected_names:
        raise ValueError(
            f"sample metadata mismatch: missing={sorted(expected_names-set(metadata))}, "
            f"extra={sorted(set(metadata)-expected_names)}"
        )
    if set(units) != expected_names:
        raise ValueError(
            f"legacy unit mismatch: missing={sorted(expected_names-set(units))}, "
            f"extra={sorted(set(units)-expected_names)}"
        )

    planner_bundle = json.loads(args.reviewed_planner_bundle.read_text())
    order_types: dict[str, str] = {}
    for operation in planner_bundle["atlas_plan"]["operations"]:
        if operation["object_kind"] != "patient_order_hybrid_order_test":
            continue
        request = operation["apply_request"]["json_body"]
        name = request["metadata"]["sample_id"]
        order_type = request["order_type"]
        if name in order_types:
            raise ValueError(f"duplicate reviewed planner ORDER_TYPE for {name}")
        order_types[name] = order_type
    if set(order_types) != expected_names:
        raise ValueError(
            "reviewed planner sample mismatch: "
            f"missing={sorted(expected_names-set(order_types))}, "
            f"extra={sorted(set(order_types)-expected_names)}"
        )

    resolved = json.loads(args.resolved_source.read_text())
    mapping_index: dict[tuple[str, str], str] = {}
    for mapping in resolved["mappings"]:
        key = (mapping["sample_id"], mapping["run_id"])
        if key in mapping_index:
            raise ValueError(f"duplicate resolved ONT mapping: {key}")
        if mapping["status"] != "externally_reviewed":
            raise ValueError(f"mapping is not externally reviewed: {key}")
        mapping_index[key] = mapping["barcode"]

    specimens: list[dict[str, str]] = []
    samples: list[dict[str, str]] = []
    libraries: list[dict[str, str]] = []
    sequencing_inputs: list[dict[str, str]] = []
    analysis_units: list[dict[str, str]] = []
    analysis_unit_inputs: list[dict[str, str]] = []
    path_summary: dict[str, dict[str, object]] = {}
    all_paths: list[str] = []

    for name, identity in grouped.items():
        meta = metadata[name]
        legacy = units[name]
        matrix_libraries = identity["libraries"]
        assert isinstance(matrix_libraries, dict)
        ilmn_matrix = matrix_libraries["ILMN"]
        ont_matrix = matrix_libraries["ONT"]

        specimen_euid = str(identity["specimen_euid"])
        sample_euid = str(identity["sample_euid"])
        ilmn_library_euid = ilmn_matrix["libraryEUID"]
        ont_library_euid = ont_matrix["libraryEUID"]
        for euid in (
            specimen_euid,
            sample_euid,
            ilmn_library_euid,
            ont_library_euid,
        ):
            if not euid.startswith("M-"):
                raise ValueError(f"non-persisted identity for {name}: {euid}")

        sample_use_values = {
            value for value in (meta["SAMPLEUSE"], legacy["SAMPLEUSE"]) if value
        }
        if len(sample_use_values) != 1:
            raise ValueError(
                f"expected one exact legacy SAMPLEUSE for {name}; "
                f"found {sorted(sample_use_values)}"
            )
        sample_use = next(iter(sample_use_values))

        specimens.append(
            {
                "SPECIMEN_ID": name,
                "SPECIMEN_EUID": specimen_euid,
                "SAMPLESOURCE": meta["SAMPLESOURCE"],
                "SPECIMEN_TYPE": meta["SAMPLE_TYPE"],
                "EXTERNAL_SPECIMEN_ID": name,
                "BIOLOGICAL_SEX": meta["BIOLOGICAL_SEX"],
                "N_X": meta["N_X"],
                "N_Y": meta["N_Y"],
                "SPECIMEN_COMMENT": (
                    f"Bjuice prevalidation biological specimen {name}; "
                    f"persisted specimen EUID {specimen_euid}"
                ),
            }
        )
        samples.append(
            {
                "SAMPLEID": name,
                "SAMPLE_EUID": sample_euid,
                "SPECIMEN_ID": name,
                "SAMPLECLASS": meta["SAMPLECLASS"],
                "SAMPLE_TYPE": meta["SAMPLE_TYPE"],
                "SAMPLEUSE": sample_use,
                "ORDER_TYPE": order_types[name],
                "CONCORDANCE_CONTROL_PATH": meta["CONCORDANCE_CONTROL_PATH"],
                "IS_POSITIVE_CONTROL": meta["IS_POSITIVE_CONTROL"],
                "IS_NEGATIVE_CONTROL": meta["IS_NEGATIVE_CONTROL"],
                "TUM_NRM_SAMPLEID_MATCH": meta["TUM_NRM_SAMPLEID_MATCH"],
                "EXTERNAL_SAMPLE_ID": name,
                "IDDNA_UID": meta["IDDNA_UID"],
                "TRUTH_DATA_DIR": meta["TRUTH_DATA_DIR"],
                "SAMPLE_COMMENT": (
                    f"Bjuice prevalidation extracted material {name}; "
                    f"persisted sample EUID {sample_euid}"
                ),
            }
        )

        ilmn_library_id = f"{name}-ILMN"
        ont_library_id = f"{name}-ONT"
        libraries.extend(
            [
                {
                    "LIBRARY_ID": ilmn_library_id,
                    "LIBRARY_EUID": ilmn_library_euid,
                    "SAMPLEID": name,
                    "LIBPREP": legacy["LIBPREP"],
                    "AMPLIFICATION_TYPE": "WGS",
                    "LIBRARY_COMMENT": (
                        f"{name} ILMN library; persisted library EUID "
                        f"{ilmn_library_euid}"
                    ),
                },
                {
                    "LIBRARY_ID": ont_library_id,
                    "LIBRARY_EUID": ont_library_euid,
                    "SAMPLEID": name,
                    "LIBPREP": legacy["LIBPREP"],
                    "AMPLIFICATION_TYPE": "WGS",
                    "LIBRARY_COMMENT": (
                        f"{name} ONT library; persisted library EUID "
                        f"{ont_library_euid}"
                    ),
                },
            ]
        )

        ilmn_r1 = split_paths(legacy["ILMN_R1_PATH"])
        ilmn_r2 = split_paths(legacy["ILMN_R2_PATH"])
        ont_paths = split_paths(legacy["ONT_R1_PATH"])
        if len(ilmn_r1) != len(ilmn_r2) or not ilmn_r1:
            raise ValueError(f"invalid ILMN lane pairs for {name}")
        ilmn_run = ilmn_matrix["ILMN RunName"]
        if any(ilmn_run not in path for path in ilmn_r1 + ilmn_r2):
            raise ValueError(f"ILMN path outside matrix run for {name}")

        ilmn_uid = f"{name}-ILMN-{ilmn_library_euid}"
        sequencing_inputs.append(
            {
                "SEQUENCING_INPUT_UID": ilmn_uid,
                "POOL_TUBE_EUID": "",
                "SEQUENCING_RUN_EUID": ilmn_matrix["ILMN RunEUID"],
                "SOURCE_ARTIFACT_EUID": "",
                "LIBRARY_ID": ilmn_library_id,
                "MODALITY": "sr",
                "LAYOUT": "paired_fastq",
                "RUNID": ilmn_run,
                "EXPERIMENTID": "bjuiceprevalanalysis-complete",
                "LANEID": "L001-L008",
                "BARCODEID": name,
                "SEQ_PLATFORM": "NOVASEQ",
                "SEQ_VENDOR": "ILMN",
                "ILMN_R1_PATH": ",".join(ilmn_r1),
                "ILMN_R2_PATH": ",".join(ilmn_r2),
                "SEQUENCING_INPUT_COMMENT": (
                    f"{name} ILMN input; library {ilmn_library_euid}; "
                    f"run {ilmn_matrix['ILMN RunEUID']}; instrument "
                    f"{ilmn_matrix['ILMN SequencerName']}"
                ),
            }
        )

        run_names = ont_matrix["ONT RunName"].split(";")
        run_euids = ont_matrix["ONT RunEUID"].split(";")
        sequencers = ont_matrix["ONT SequencerName"].split(";")
        if not (len(run_names) == len(run_euids) == len(sequencers) == 3):
            raise ValueError(f"expected three ONT runs for {name}")
        assigned_ont_paths: list[str] = []
        analysis_unit_uid = f"BJUICEPREVAL-COMPLETE-{name}-HIOMRS"
        analysis_unit_inputs.append(
            {
                "ANALYSIS_UNIT_UID": analysis_unit_uid,
                "SEQUENCING_INPUT_UID": ilmn_uid,
                "ROLE": "sr",
                "INPUT_ORDINAL": "1",
            }
        )
        ont_counts: dict[str, int] = {}
        for ordinal, (run_name, run_euid, sequencer) in enumerate(
            zip(run_names, run_euids, sequencers), start=2
        ):
            run_paths = [path for path in ont_paths if run_name in path]
            if not run_paths:
                raise ValueError(f"no ONT paths for {name} run {run_name}")
            assigned_ont_paths.extend(run_paths)
            ont_counts[run_name] = len(run_paths)
            barcode = mapping_index[(name, run_name)]
            ont_uid = f"{name}-ONT-{ont_library_euid}-{run_euid}"
            sequencing_inputs.append(
                {
                    "SEQUENCING_INPUT_UID": ont_uid,
                    "POOL_TUBE_EUID": "",
                    "SEQUENCING_RUN_EUID": run_euid,
                    "SOURCE_ARTIFACT_EUID": "",
                    "LIBRARY_ID": ont_library_id,
                    "MODALITY": "lr",
                    "LAYOUT": "single_fastq",
                    "RUNID": run_name,
                    "EXPERIMENTID": "bjuiceprevalanalysis-complete",
                    "LANEID": run_name.split("_")[2],
                    "BARCODEID": barcode,
                    "SEQ_PLATFORM": "PROMETHION",
                    "SEQ_VENDOR": "ONT",
                    "ONT_R1_PATH": ",".join(run_paths),
                    "ONT_R2_PATH": "",
                    "SEQUENCING_INPUT_COMMENT": (
                        f"{name} ONT input {barcode}; library {ont_library_euid}; "
                        f"run {run_euid}; instrument {sequencer}"
                    ),
                }
            )
            analysis_unit_inputs.append(
                {
                    "ANALYSIS_UNIT_UID": analysis_unit_uid,
                    "SEQUENCING_INPUT_UID": ont_uid,
                    "ROLE": "lr",
                    "INPUT_ORDINAL": str(ordinal),
                }
            )

        if sorted(assigned_ont_paths) != sorted(ont_paths):
            raise ValueError(f"ONT run partition does not preserve all paths for {name}")
        all_paths.extend(ilmn_r1 + ilmn_r2 + ont_paths)
        path_summary[name] = {
            "ilmn_r1": len(ilmn_r1),
            "ilmn_r2": len(ilmn_r2),
            "ont_total": len(ont_paths),
            "ont_by_run": ont_counts,
        }
        analysis_units.append(
            {
                "ANALYSIS_UNIT_UID": analysis_unit_uid,
                "ANALYSIS_UNIT_EUID": "",
                "SAMPLEID": name,
                "DELIVERY_EUID": "",
                "DELIVERY_PROFILE": "",
                "CUSTOMER_DELIVERY_ID": "",
                "SUBSAMPLE_PCT": "",
                "ONT_SUBSAMPLE_PCT": "",
                "ALIGNED_REF_UID": "",
                "BWA_KMER": legacy["BWA_KMER"],
                "DEEP_MODEL": legacy["DEEP_MODEL"],
                "MERGE_SINGLE": "single",
                "ANALYSIS_UNIT_COMMENT": (
                    f"Complete full-input HIOMRS analysis for {name}; "
                    f"specimen {specimen_euid}; sample {sample_euid}; "
                    f"libraries {ilmn_library_euid} and {ont_library_euid}"
                ),
            }
        )

    if len(all_paths) != len(set(all_paths)):
        raise ValueError("input paths are not globally unique across biological identities")

    rows_by_manifest = {
        "specimens": specimens,
        "samples": samples,
        "libraries": libraries,
        "sequencing_inputs": sequencing_inputs,
        "analysis_units": analysis_units,
        "analysis_unit_inputs": analysis_unit_inputs,
    }
    for manifest, rows in rows_by_manifest.items():
        rows.sort(key=lambda row: tuple(row[key] for key in PRIMARY_KEYS[manifest]))
    expected_counts = {
        "specimens": 20,
        "samples": 20,
        "libraries": 40,
        "sequencing_inputs": 80,
        "analysis_units": 20,
        "analysis_unit_inputs": 80,
    }
    observed_counts = {name: len(rows) for name, rows in rows_by_manifest.items()}
    if observed_counts != expected_counts:
        raise ValueError(f"manifest count mismatch: {observed_counts}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_hashes = {}
    for manifest in MANIFESTS:
        path = args.output_dir / f"{manifest}.tsv"
        write_tsv(
            path,
            template_columns(args.dayoa_repo, args.dayoa_ref, manifest),
            rows_by_manifest[manifest],
        )
        output_hashes[path.name] = sha256(path)

    input_paths_path = args.output_dir / "input_paths.txt"
    input_paths_path.write_text("\n".join(sorted(all_paths)) + "\n")

    summary = {
        "schema": "dayoa.bjuiceprevalanalysis_complete.generation.v1",
        "dayoa_ref": args.dayoa_ref,
        "matrix_sha256": observed_matrix_sha,
        "source_sha256": {
            str(path): sha256(path)
            for path in (
                args.first_samples,
                args.first_units,
                args.second_samples,
                args.second_units,
                args.resolved_source,
                args.reviewed_planner_bundle,
            )
        },
        "excluded_external_names": ["NTC"],
        "biological_names": list(grouped),
        "counts": observed_counts,
        "path_counts": path_summary,
        "total_unique_input_paths": len(all_paths),
        "input_paths_sha256": sha256(input_paths_path),
        "output_sha256": output_hashes,
    }
    (args.output_dir / "generation_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
