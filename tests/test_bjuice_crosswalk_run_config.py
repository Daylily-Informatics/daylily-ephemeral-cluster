from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from daylily_ec.bjuice_crosswalk_run_config import materialize_bjuice_crosswalk_run
from daylily_ec.bjuice_preval_config import BjuiceConfigError
from daylily_ec.bjuice_validation_config import CROSSWALK_COLUMNS

ATTACHMENT_COLUMNS = (
    "unit_id",
    "canonical",
    "ilmn_run",
    "ilmn_lib_id",
    "ilmn_ok",
    "ont_run",
    "ont_lib_name",
    "ont_barcode",
    "ont_set",
    "ont_chips",
    "ont_ok",
)


def _write_tsv(path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _fastq(*, chip: str, barcode: str, hour: int) -> dict[str, object]:
    name = f"{chip}_pass_{barcode}_11c4b124_951b2393_{hour}.fastq.gz"
    uri = f"s3://fixture/basecalls/lsmc/ssf-hq/pca100/2025/Run2_Set6/no_sample_id/fastq_pass/{barcode}/{name}"
    return {"s3_uri": uri, "mount_path": f"/stale/{name}", "size": hour + 1, "hour": hour}


def _fixture_inputs(root: Path) -> dict[str, Path]:
    attachment_rows: list[dict[str, str]] = []
    crosswalk_rows: list[dict[str, str]] = []
    selections: dict[str, object] = {}
    for index in range(20):
        is_hg002 = index == 0
        sample = "HG002" if is_hg002 else f"S{index:02d}"
        ilmn_sample = "HG002-b" if is_hg002 else f"{sample}-b"
        barcode = "barcode72" if is_hg002 else f"barcode{index:02d}"
        chips = ("PBK89749", "PBK89870", "PBK91510") if is_hg002 else (f"PBK9{index:04d}",)
        attachment_rows.append(
            {
                "unit_id": f"unit-{index:02d}",
                "canonical": sample,
                "ilmn_run": "13",
                "ilmn_lib_id": ilmn_sample,
                "ilmn_ok": "TRUE",
                "ont_run": "Run2",
                "ont_lib_name": sample,
                "ont_barcode": barcode,
                "ont_set": "6",
                "ont_chips": ";".join(chips),
                "ont_ok": "TRUE",
            }
        )
        ilmn_id, ont_id = f"I{index:02d}", f"O{index:02d}"
        for row_id in (ilmn_id, ont_id):
            row = {column: "" for column in CROSSWALK_COLUMNS}
            row.update(
                {
                    "CROSSWALK_ROW_ID": row_id,
                    "WORKBOOK_ROW": str(index + 1),
                    "LOGICAL_RUN": "2",
                    "CANONICAL_SAMPLE_RAW": sample,
                    "BIOLOGICAL_SAMPLE": sample,
                    "ILMN_ALIAS": f"ILMN-{ilmn_sample}",
                    "ILMN_FASTQ_SAMPLE_ID": ilmn_sample,
                    "ONT_ALIAS": f"ONT-{sample}",
                    "ONT_DECODER_ALIAS": sample,
                    "ONT_DECODER_ORDINAL": str(index + 1),
                    "ONT_SET": "6",
                    "ONT_CHIP": "18",
                    "ONT_POSITION": "3B",
                    "ONT_BARCODE": barcode,
                    "MATERIAL_CLASS": "GIAB" if is_hg002 else "RESEARCH",
                    "PAIRING_STATUS": "PAIRED",
                    "REVIEW_STATUS": "REVIEWED",
                }
            )
            crosswalk_rows.append(row)
        ilmn_base = "s3://fixture/basecalls/lsmc/ssf-hq/LH01106/2026/ILMN13/Analysis/1/Data"
        selections[ilmn_id] = {
            "biological_sample": sample,
            "ilmn": {
                "ilmn-run2": {
                    "source_id": "ilmn-run2",
                    "sample_id": ilmn_sample,
                "run_id": "ILMN13",
                "lanes": ["001"],
                "contributing_data": {
                    "illumina_flowcells": [
                        {
                            "flowcell_id": "B23M753LT3",
                            "type": "WGS",
                            "lanes_used": ["001"],
                            "fastq_count": 2,
                            "pass_filter_reads": 200,
                        }
                    ]
                },
                    "r1": [
                        {
                            "s3_uri": f"{ilmn_base}/{ilmn_sample}_S1_L001_R1_001.fastq.gz",
                            "mount_path": "/stale/r1",
                            "size": 100,
                        }
                    ],
                    "r2": [
                        {
                            "s3_uri": f"{ilmn_base}/{ilmn_sample}_S1_L001_R2_001.fastq.gz",
                            "mount_path": "/stale/r2",
                            "size": 100,
                        }
                    ],
                }
            },
            "pairing_status": "PAIRED",
        }
        selections[ont_id] = {
            "biological_sample": sample,
            "ont": {
                "source_id": "ont-run2-set6",
                "barcode": barcode,
                "position": "3B",
                "run_id": "Run2_Set6",
                "set_number": 6,
                "flowcell_id": chips[0],
                "contributing_data": {
                    "ont_cells": [
                        {
                            "chip_id": chip,
                            "type": "WGS",
                            "runtime_hours": 25,
                            "total_fastq_count": 25 if is_hg002 else 1,
                            "selected_fastq_count": 25 if is_hg002 else 1,
                            "selected_pass_filter_reads": 100,
                        }
                        for chip in chips
                    ]
                },
                "fastqs": [
                    _fastq(chip=chip, barcode=barcode, hour=hour)
                    for chip in chips
                    for hour in range(25 if is_hg002 else 1)
                ],
            },
            "pairing_status": "PAIRED",
        }
    attachment = root / "attachment.tsv"
    internal_crosswalk = root / "internal_crosswalk.tsv"
    inventory = root / "source_inventory.json"
    _write_tsv(attachment, ATTACHMENT_COLUMNS, attachment_rows)
    _write_tsv(internal_crosswalk, CROSSWALK_COLUMNS, crosswalk_rows)
    inventory.write_text(json.dumps({"selections": selections}, indent=2) + "\n", encoding="utf-8")
    return {
        "attachment": attachment,
        "internal_crosswalk": internal_crosswalk,
        "source_inventory": inventory,
    }


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def test_materializer_aggregates_three_hg002_b_chips_and_blanks_hour_slicing(
    tmp_path: Path,
) -> None:
    inputs = _fixture_inputs(tmp_path)
    result = materialize_bjuice_crosswalk_run(
        run_number="13",
        **inputs,
        ilmn_mount="/fsx/run_dir_mounts/hybrid-crosswalk-ilmn-2026",
        ont_mount="/fsx/run_dir_mounts/hybrid-crosswalk-ont-pca100",
        output_dir=tmp_path / "output",
    )

    receipt = result["receipt"]
    units = _read_tsv(tmp_path / "output" / "analysis_units.tsv")
    inputs_rows = _read_tsv(tmp_path / "output" / "sequencing_inputs.tsv")
    links = _read_tsv(tmp_path / "output" / "analysis_unit_inputs.tsv")
    hg002_ont = next(
        row for row in inputs_rows if row["SEQUENCING_INPUT_UID"].endswith("unit-00-ONT")
    )

    assert receipt["topology"]["analysis_unit_count"] == 20
    assert receipt["topology"]["analysis_unit_input_count"] == 40
    assert len(receipt["joins"]) == 20
    assert len(links) == 40
    assert all(not row["ONT_FQ_START_HOUR"] and not row["ONT_FQ_END_HOUR"] for row in units)
    assert receipt["runtime_yaml_sha256"]
    assert receipt["contributing_data_receipt"] == "config/contributing_data_receipt.v1.json"
    assert receipt["selection_contract"]["ont_hour_slicing"] == "blank_full_input"
    runtime = yaml.safe_load(
        (tmp_path / "output" / receipt["runtime_yaml"]).read_text(encoding="utf-8")
    )
    assert "ont_fastq_hour_window_mode" not in runtime
    assert len(hg002_ont["ONT_R1_PATH"].split(",")) == 75
    assert {
        path.split("/")[-1].split("_", 1)[0] for path in hg002_ont["ONT_R1_PATH"].split(",")
    } == {
        "PBK89749",
        "PBK89870",
        "PBK91510",
    }
    hg002_join = receipt["joins"][0]
    assert hg002_join["ont_fastq_count"] == 75
    assert [item["fastq_count"] for item in hg002_join["chip_receipt"]] == [25, 25, 25]
    assert hg002_ont["ONT_R1_PATH"].startswith(
        "/fsx/run_dir_mounts/hybrid-crosswalk-ont-pca100/2025/"
    )
    contributing = json.loads(
        (tmp_path / "output" / "config" / "contributing_data_receipt.v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert contributing["schema_version"] == "dayoa.contributing_data.v1"
    assert set(contributing) == {"schema_version", "manifest_sha256", "analysis_units"}
    assert contributing["manifest_sha256"] == receipt["topology"]["manifest_hashes"]
    assert len(contributing["analysis_units"]) == 20
    assert [cell["selected_fastq_count"] for cell in contributing["analysis_units"][0]["ont_cells"]] == [
        25,
        25,
        25,
    ]
    assert contributing["analysis_units"][0]["ont_cells"][0]["selection_start_hour"] is None
    assert set(contributing["analysis_units"][0]) == {
        "analysis_unit_uid",
        "illumina_flowcells",
        "ont_cells",
    }
    assert set(contributing["analysis_units"][0]["illumina_flowcells"][0]) == {
        "sequencing_input_uid",
        "flowcell_id",
        "type",
        "lanes_used",
        "fastq_count",
        "pass_filter_reads",
    }
    assert set(contributing["analysis_units"][0]["ont_cells"][0]) == {
        "sequencing_input_uid",
        "chip_id",
        "type",
        "runtime_hours",
        "total_fastq_count",
        "selection_start_hour",
        "selection_stop_hour",
        "selected_fastq_count",
        "selected_pass_filter_reads",
    }
    runtime = yaml.safe_load(
        (tmp_path / "output" / receipt["runtime_yaml"]).read_text(encoding="utf-8")
    )
    assert runtime["bjuice_workflow_config_file"] == "config/dyec_runtime_config.yaml"
    assert runtime["multiqc_qc"]["contributing_data"] == {
        "enabled": True,
        "receipt": "config/contributing_data_receipt.v1.json",
        "sr_alignment": {"aligner": "sentdhiomr2sr", "deduper": "smd"},
    }


def test_materializer_fails_closed_when_a_declared_hg002_chip_is_missing(tmp_path: Path) -> None:
    inputs = _fixture_inputs(tmp_path)
    inventory = json.loads(inputs["source_inventory"].read_text(encoding="utf-8"))
    fastqs = inventory["selections"]["O00"]["ont"]["fastqs"]
    inventory["selections"]["O00"]["ont"]["fastqs"] = [
        item for item in fastqs if "PBK91510_" not in item["s3_uri"]
    ]
    inputs["source_inventory"].write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(
        BjuiceConfigError, match="missing verified FASTQs for declared chips: PBK91510"
    ):
        materialize_bjuice_crosswalk_run(
            run_number="13",
            **inputs,
            ilmn_mount="/fsx/run_dir_mounts/hybrid-crosswalk-ilmn-2026",
            ont_mount="/fsx/run_dir_mounts/hybrid-crosswalk-ont-pca100",
            output_dir=tmp_path / "output",
        )


def test_materializer_preserves_multiple_illumina_flowcells_per_au(tmp_path: Path) -> None:
    inputs = _fixture_inputs(tmp_path)
    inventory = json.loads(inputs["source_inventory"].read_text(encoding="utf-8"))
    inventory["selections"]["I00"]["ilmn"]["ilmn-run2"]["lanes"] = ["001", "002"]
    inventory["selections"]["I00"]["ilmn"]["ilmn-run2"]["contributing_data"][
        "illumina_flowcells"
    ] = [
        {
            "flowcell_id": "B23M753LT3",
            "type": "WGS",
            "lanes_used": ["001"],
            "fastq_count": 1,
            "pass_filter_reads": 100,
        },
        {
            "flowcell_id": "B23M754LT3",
            "type": "WGS",
            "lanes_used": ["002"],
            "fastq_count": 1,
            "pass_filter_reads": 100,
        },
    ]
    inputs["source_inventory"].write_text(
        json.dumps(inventory, indent=2) + "\n", encoding="utf-8"
    )

    result = materialize_bjuice_crosswalk_run(
        run_number="13",
        **inputs,
        ilmn_mount="/fsx/run_dir_mounts/hybrid-crosswalk-ilmn-2026",
        ont_mount="/fsx/run_dir_mounts/hybrid-crosswalk-ont-pca100",
        output_dir=tmp_path / "output",
    )

    contributing_path = tmp_path / "output" / result["receipt"]["contributing_data_receipt"]
    contributing = json.loads(contributing_path.read_text(encoding="utf-8"))
    flowcells = contributing["analysis_units"][0]["illumina_flowcells"]
    assert [item["flowcell_id"] for item in flowcells] == ["B23M753LT3", "B23M754LT3"]
    assert [item["lanes_used"] for item in flowcells] == [["001"], ["002"]]
    assert sum(item["fastq_count"] for item in flowcells) == 2


def test_materializer_rejects_ont_total_that_exceeds_full_input_selection(tmp_path: Path) -> None:
    inputs = _fixture_inputs(tmp_path)
    inventory = json.loads(inputs["source_inventory"].read_text(encoding="utf-8"))
    inventory["selections"]["O00"]["ont"]["contributing_data"]["ont_cells"][0][
        "total_fastq_count"
    ] = 26
    inputs["source_inventory"].write_text(
        json.dumps(inventory, indent=2) + "\n", encoding="utf-8"
    )

    with pytest.raises(BjuiceConfigError, match="ONT contributing FASTQ count mismatch"):
        materialize_bjuice_crosswalk_run(
            run_number="13",
            **inputs,
            ilmn_mount="/fsx/run_dir_mounts/hybrid-crosswalk-ilmn-2026",
            ont_mount="/fsx/run_dir_mounts/hybrid-crosswalk-ont-pca100",
            output_dir=tmp_path / "output",
        )


def test_materializer_fails_closed_when_the_internal_crosswalk_is_incomplete(tmp_path: Path) -> None:
    inputs = _fixture_inputs(tmp_path)
    rows = [row for row in _read_tsv(inputs["internal_crosswalk"]) if row["CROSSWALK_ROW_ID"] != "O00"]
    _write_tsv(inputs["internal_crosswalk"], CROSSWALK_COLUMNS, rows)

    with pytest.raises(BjuiceConfigError, match="absent from internal crosswalk"):
        materialize_bjuice_crosswalk_run(
            run_number="13",
            **inputs,
            ilmn_mount="/fsx/run_dir_mounts/hybrid-crosswalk-ilmn-2026",
            ont_mount="/fsx/run_dir_mounts/hybrid-crosswalk-ont-pca100",
            output_dir=tmp_path / "output",
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda inventory: inventory["selections"]["O00"]["ont"].__setitem__("set_number", 5),
            "ONT set or barcode mismatch",
        ),
        (
            lambda inventory: inventory["selections"]["O00"]["ont"].__setitem__(
                "run_id", "another-run"
            ),
            "ONT run/path mismatch",
        ),
        (
            lambda inventory: inventory["selections"]["O00"]["ont"]["fastqs"][0].__setitem__(
                "s3_uri",
                inventory["selections"]["O00"]["ont"]["fastqs"][0]["s3_uri"].replace(
                    "barcode72", "barcode71"
                ),
            ),
            "ONT barcode/path mismatch",
        ),
        (
            lambda inventory: inventory["selections"]["O00"]["ont"]["fastqs"].append(
                dict(inventory["selections"]["O00"]["ont"]["fastqs"][0])
            ),
            "duplicate ONT FASTQ",
        ),
        (
            lambda inventory: inventory["selections"]["O00"]["ont"]["fastqs"][0].__setitem__(
                "size", 0
            ),
            "ONT FASTQ size must be greater than zero",
        ),
        (
            lambda inventory: inventory["selections"]["O00"]["ont"]["fastqs"][0].__setitem__(
                "s3_uri",
                inventory["selections"]["O00"]["ont"]["fastqs"][0]["s3_uri"].replace(
                    ".fastq.gz", ".not-fastq.gz"
                ),
            ),
            "ONT FASTQ outside its exact barcode",
        ),
        (
            lambda inventory: inventory["selections"]["I00"]["ilmn"]["ilmn-run2"]["r1"][0].__setitem__(
                "fastq_header", {"sample_id": "HG002-b", "lane": "001", "mate": "2"}
            ),
            "FASTQ header evidence does not match",
        ),
    ],
)
def test_materializer_rejects_malformed_or_duplicate_inventory_evidence(
    tmp_path: Path, mutation, message: str
) -> None:
    inputs = _fixture_inputs(tmp_path)
    inventory = json.loads(inputs["source_inventory"].read_text(encoding="utf-8"))
    mutation(inventory)
    inputs["source_inventory"].write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(BjuiceConfigError, match=message):
        materialize_bjuice_crosswalk_run(
            run_number="13",
            **inputs,
            ilmn_mount="/fsx/run_dir_mounts/hybrid-crosswalk-ilmn-2026",
            ont_mount="/fsx/run_dir_mounts/hybrid-crosswalk-ont-pca100",
            output_dir=tmp_path / "output",
        )


def test_materializer_rejects_nonempty_output_and_is_deterministic(tmp_path: Path) -> None:
    inputs = _fixture_inputs(tmp_path)
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "existing.txt").write_text("do not overwrite\n", encoding="utf-8")
    with pytest.raises(BjuiceConfigError, match="output directory is not empty"):
        materialize_bjuice_crosswalk_run(
            run_number="13",
            **inputs,
            ilmn_mount="/fsx/run_dir_mounts/hybrid-crosswalk-ilmn-2026",
            ont_mount="/fsx/run_dir_mounts/hybrid-crosswalk-ont-pca100",
            output_dir=occupied,
        )

    first = materialize_bjuice_crosswalk_run(
        run_number="13",
        **inputs,
        ilmn_mount="/fsx/run_dir_mounts/hybrid-crosswalk-ilmn-2026",
        ont_mount="/fsx/run_dir_mounts/hybrid-crosswalk-ont-pca100",
        output_dir=tmp_path / "first",
    )
    second = materialize_bjuice_crosswalk_run(
        run_number="13",
        **inputs,
        ilmn_mount="/fsx/run_dir_mounts/hybrid-crosswalk-ilmn-2026",
        ont_mount="/fsx/run_dir_mounts/hybrid-crosswalk-ont-pca100",
        output_dir=tmp_path / "second",
    )
    assert first["receipt"] == second["receipt"]
    assert first["receipt"]["contributing_data_receipt_sha256"] == second["receipt"][
        "contributing_data_receipt_sha256"
    ]
