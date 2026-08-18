from __future__ import annotations

import copy
import csv
import json
from collections import Counter
from pathlib import Path

import pytest
import yaml

from daylily_ec.bjuice_preval_config import BjuiceConfigError
from daylily_ec.bjuice_validation_config import (
    CROSSWALK_COLUMNS,
    EXPECTED_MAPPED_ROWS,
    EXPECTED_ONT_ROWS,
    EXPECTED_PAIRED_ROWS,
    EXPECTED_SOURCE_COUNT,
    ONT_FASTQ_RE,
    SOURCE_INVENTORY_SCHEMA,
    _ilmn_selection,
    _list_s3_object_records,
    _ont_selection,
    _source_spec,
    _unique_decoder_match,
    load_crosswalk,
    validate_crosswalk_rows,
)
from daylily_ec.manifest_set import EUID_FIELDS, load_manifest_set

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT / "docs" / "jem" / "bjuice_validation"
CONFIG_ROOT = DATA_ROOT / "configs"
EXPECTED_BUNDLES = {
    "bundle1a": 32,
    "bundle1b": 32,
    "bundle2": 19,
    "bundle3": 17,
    "bundle4": 31,
}


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _inventory() -> dict:
    return json.loads((DATA_ROOT / "source_inventory.json").read_text(encoding="utf-8"))


def test_reviewed_crosswalk_has_exact_workbook_totals_and_one_sided_rows() -> None:
    path = DATA_ROOT / "sample_crosswalk.tsv"
    header = path.read_text(encoding="utf-8").splitlines()[0].split("\t")
    assert tuple(header) == CROSSWALK_COLUMNS
    rows = load_crosswalk(path)
    assert Counter(int(row["LOGICAL_RUN"]) for row in rows) == EXPECTED_MAPPED_ROWS
    assert (
        Counter(int(row["LOGICAL_RUN"]) for row in rows if row["PAIRING_STATUS"] == "PAIRED")
        == EXPECTED_PAIRED_ROWS
    )
    assert Counter(int(row["LOGICAL_RUN"]) for row in rows if row["ONT_ALIAS"]) == EXPECTED_ONT_ROWS
    assert Counter(row["PAIRING_STATUS"] for row in rows) == {
        "PAIRED": 99,
        "ILMN_ONLY": 29,
        "ONT_ONLY": 29,
    }
    assert not any(row["BIOLOGICAL_SAMPLE"].upper() == "NTC" for row in rows)


def test_inventory_contains_all_roots_exact_inputs_and_launch_blocker() -> None:
    inventory = _inventory()
    assert inventory["schema"] == SOURCE_INVENTORY_SCHEMA
    assert inventory["summary"]["source_count"] == EXPECTED_SOURCE_COUNT
    assert inventory["summary"]["mapped_rows"] == 157
    assert inventory["summary"]["paired_rows"] == 99
    assert inventory["summary"]["oow_done_sources"] == []
    assert len(inventory["summary"]["oow_missing_sources"]) == EXPECTED_SOURCE_COUNT
    assert len(inventory["sources"]) == EXPECTED_SOURCE_COUNT
    assert all(source["object_count"] > 0 for source in inventory["sources"].values())
    assert all(source["total_bytes"] > 0 for source in inventory["sources"].values())

    for selection in inventory["selections"].values():
        for ilmn in selection["ilmn"].values():
            assert ilmn["lanes"]
            assert [item["lane"] for item in ilmn["r1"]] == [item["lane"] for item in ilmn["r2"]]
            for item in [*ilmn["r1"], *ilmn["r2"]]:
                assert item["size"] > 0
                assert item["s3_uri"].startswith("s3://lsmc-ssf-sequencing-data/basecalls/")
                assert item["mount_path"].startswith("/fsx/run_dir_mounts/")
        ont = selection.get("ont")
        if not ont:
            continue
        assert ont["window_hours_present"] == list(range(24))
        assert ont["window_fastq_count"] == 24
        assert ont["window_total_bytes"] > 0
        for item in ont["fastqs"]:
            uri = item["s3_uri"]
            assert f"/fastq_pass/{ont['barcode']}/" in uri
            match = ONT_FASTQ_RE.fullmatch(Path(uri).name)
            assert match
            assert match.group("flowcell") == ont["flowcell_id"]
            assert match.group("barcode") == ont["barcode"]


def test_inventory_records_every_intentional_fastq_exclusion_class() -> None:
    sources = _inventory()["sources"]
    assert sources["ilmn-run1a"]["fastq_selection_summary"]["unselected_sample_ids"] == [
        "NTC",
        "Undetermined",
    ]
    assert sources["ilmn-run4"]["fastq_selection_summary"]["unselected_sample_ids"] == [
        "20260717-1",
        "20260717-2",
        "20260717-3",
        "20260717-4",
        "20260722-1",
        "20260722-2",
        "20260722-3",
        "20260722-4",
        "NTC",
        "Undetermined",
    ]
    for source in sources.values():
        summary = source["fastq_selection_summary"]
        assert summary["candidate_fastq_count"] >= summary["selected_fastq_count"]
        assert summary["unselected_fastq_count"] == (
            summary["candidate_fastq_count"] - summary["selected_fastq_count"]
        )


@pytest.mark.parametrize(("bundle_id", "expected_aus"), EXPECTED_BUNDLES.items())
def test_generated_bundle_has_exact_hybrid_topology_and_runtime(
    bundle_id: str, expected_aus: int
) -> None:
    bundle_dir = CONFIG_ROOT / bundle_id
    manifests = load_manifest_set(bundle_dir)
    assert len(manifests.rows["analysis_units.tsv"]) == expected_aus
    assert len(manifests.rows["libraries.tsv"]) == expected_aus * 2
    assert len(manifests.rows["sequencing_inputs.tsv"]) == expected_aus * 2
    assert len(manifests.rows["analysis_unit_inputs.tsv"]) == expected_aus * 2

    links_by_unit: dict[str, list[dict[str, str]]] = {}
    for link in manifests.rows["analysis_unit_inputs.tsv"]:
        links_by_unit.setdefault(link["ANALYSIS_UNIT_UID"], []).append(link)
    assert all(
        sorted((row["ROLE"], row["INPUT_ORDINAL"]) for row in links)
        == [
            ("lr", "2"),
            ("sr", "1"),
        ]
        for links in links_by_unit.values()
    )
    for unit in manifests.rows["analysis_units.tsv"]:
        assert unit["SUBSAMPLE_PCT"] == ""
        assert unit["ONT_SUBSAMPLE_PCT"] == ""
        assert unit["ONT_FQ_START_HOUR"] == "0"
        assert unit["ONT_FQ_END_HOUR"] == "24"

    for name, fields in EUID_FIELDS.items():
        assert all(not row.get(field, "") for row in manifests.rows[name] for field in fields)
    input_rows = manifests.rows["sequencing_inputs.tsv"]
    for source in input_rows:
        if source["MODALITY"] == "sr":
            r1 = source["ILMN_R1_PATH"].split(",")
            r2 = source["ILMN_R2_PATH"].split(",")
            assert r1 and len(r1) == len(r2)
            assert all(path.endswith(".fastq.gz") for path in [*r1, *r2])
        else:
            paths = source["ONT_R1_PATH"].split(",")
            assert paths
            assert all("/fastq_pass/barcode" in path for path in paths)
            assert source["ONT_R2_PATH"] == ""

    runtime_path = bundle_dir / f"bjuice_validation_{bundle_id}_hiomr2.yaml"
    runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
    assert runtime["ont_fastq_hour_window_mode"] == "per_analysis_unit"
    assert runtime["sentdhiomr2"]["hg38_sentdhiomr2_chrms"] == "1-25"
    assert set(runtime["sentdhiomr2"]["lr_input_mode_by_sample"]) == {
        row["SAMPLEID"] for row in manifests.rows["samples.tsv"]
    }
    assert set(runtime["sentdhiomr2"]["lr_input_mode_by_sample"].values()) == {"fastq"}
    assert runtime["sentdhiomr2_slim_consensus"]["enabled"] is True
    assert runtime["sentdhiomr2_nicu_research"]["enabled"] is False
    assert runtime["sentdhiomr2_jasmine"]["enabled"] is False
    expected_truth = (
        {"HG002"} if "HG002" in runtime["sentdhiomr2"]["lr_input_mode_by_sample"] else set()
    )
    assert set(runtime["truvari_sv_benchmark"]["truthsets"]) == expected_truth

    receipt = json.loads((bundle_dir / "generation_receipt.json").read_text(encoding="utf-8"))
    assert receipt["configuration_status"] == "CONFIG_COMPLETE"
    assert receipt["launch_status"] == "LAUNCH_BLOCKED"
    assert receipt["topology"]["analysis_unit_count"] == expected_aus
    assert receipt["topology"]["manifest_hashes"] == manifests.hashes
    assert "CANONICAL_OWY_OOW_DONE_MISSING" in receipt["launch_blockers"]
    assert "produce_sentdhiomr2_slim_kitchensink_mega" in receipt["saved_dy_r_command"]
    assert "produce_sentdhiomr2_inflection_analytical_package" in receipt["saved_dy_r_command"]
    assert "snakemake" not in receipt["saved_dy_r_command"].lower()


def test_bundle1_variants_share_ont_and_use_disjoint_ilmn_roots() -> None:
    one_a = _rows(CONFIG_ROOT / "bundle1a" / "sequencing_inputs.tsv")
    one_b = _rows(CONFIG_ROOT / "bundle1b" / "sequencing_inputs.tsv")
    ont_a = sorted(row["ONT_R1_PATH"] for row in one_a if row["MODALITY"] == "lr")
    ont_b = sorted(row["ONT_R1_PATH"] for row in one_b if row["MODALITY"] == "lr")
    ilmn_a = sorted(row["ILMN_R1_PATH"] for row in one_a if row["MODALITY"] == "sr")
    ilmn_b = sorted(row["ILMN_R1_PATH"] for row in one_b if row["MODALITY"] == "sr")
    assert ont_a == ont_b
    assert set(ilmn_a).isdisjoint(ilmn_b)
    assert all("20260624_LH01106_0012_A23WW3CLT4" in path for path in ilmn_a)
    assert all("20260629_LH01106_0014_B23WV5HLT4" in path for path in ilmn_b)


def test_generated_artifacts_exclude_prohibited_sources_and_invented_euids() -> None:
    forbidden = ("preval", "migration-cleanup", "/.", "/fastq_fail/", "/unclassified/")
    for path in CONFIG_ROOT.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").lower()
        assert not any(value in text for value in forbidden)


def test_crosswalk_rejects_duplicate_barcodes_and_ambiguous_aliases() -> None:
    rows = load_crosswalk(DATA_ROOT / "sample_crosswalk.tsv")
    changed = copy.deepcopy(rows)
    run1_ont = [row for row in changed if row["LOGICAL_RUN"] == "1" and row["ONT_ALIAS"]]
    run1_ont[1]["ONT_BARCODE"] = run1_ont[0]["ONT_BARCODE"]
    with pytest.raises(BjuiceConfigError, match="duplicate ONT barcodes"):
        validate_crosswalk_rows(changed)

    ambiguous = {
        "row-a": {"ONT_ALIAS": "ONT-SAME", "BIOLOGICAL_SAMPLE": "A"},
        "row-b": {"ONT_ALIAS": "ONT-SAME", "BIOLOGICAL_SAMPLE": "B"},
    }
    with pytest.raises(BjuiceConfigError, match="ambiguous"):
        _unique_decoder_match(unmatched=ambiguous, decoder_alias="SAME", logical_run=1)


def test_ilmn_selection_rejects_unequal_mates() -> None:
    source = {
        "source_id": "ilmn-test",
        "run_id": "run",
        "s3_uri": "s3://bucket/root/",
        "mount_s3_uri": "s3://bucket/root/",
        "mount_path": "/fsx/run_dir_mounts/run",
        "_objects": [
            {
                "key": "root/Analysis/fastq/SAMPLE_S1_L001_R1_001.fastq.gz",
                "size": 10,
                "last_modified": "2026-01-01T00:00:00+00:00",
            }
        ],
    }
    with pytest.raises(BjuiceConfigError, match="unequal or missing R1/R2"):
        _ilmn_selection(source=source, row={"ILMN_FASTQ_SAMPLE_ID": "SAMPLE"})


def test_ont_selection_rejects_unexpected_fastq_name() -> None:
    source = {
        "source_id": "ont-test",
        "run_id": "run",
        "set_number": 1,
        "s3_uri": "s3://bucket/root/",
        "mount_s3_uri": "s3://bucket/root/",
        "mount_path": "/fsx/run_dir_mounts/ont",
        "flowcells_by_position": {
            "1A": {
                "flow_cell_id": "PBK00001",
                "protocol_short": "12345678",
                "acquisition_short": "abcdef01",
            }
        },
        "_objects": [
            {
                "key": "root/no_sample_id/fastq_pass/barcode01/not-a-fastq.fastq.gz",
                "size": 10,
                "last_modified": "2026-01-01T00:00:00+00:00",
            }
        ],
    }
    with pytest.raises(BjuiceConfigError, match="unexpected ONT FASTQ name"):
        _ont_selection(source=source, row={"ONT_POSITION": "1A", "ONT_BARCODE": "barcode01"})


def test_source_spec_rejects_unexpected_preval_path(tmp_path: Path) -> None:
    spec = json.loads((DATA_ROOT / "source_spec.json").read_text(encoding="utf-8"))
    spec["sources"][0]["s3_uri"] = (
        "s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/Bjuice-preval/"
    )
    candidate = tmp_path / "source_spec.json"
    candidate.write_text(json.dumps(spec), encoding="utf-8")
    with pytest.raises(BjuiceConfigError, match="prohibited source URI"):
        _source_spec(candidate)


def test_s3_listing_unit_uses_only_mocked_client() -> None:
    class FakePaginator:
        def paginate(self, **kwargs):
            assert kwargs == {"Bucket": "bucket", "Prefix": "root/"}
            return [
                {
                    "Contents": [
                        {
                            "Key": "root/file.fastq.gz",
                            "Size": 7,
                            "LastModified": "2026-01-01T00:00:00+00:00",
                            "ETag": '"abc"',
                        }
                    ]
                }
            ]

    class FakeS3Client:
        def get_paginator(self, name):
            assert name == "list_objects_v2"
            return FakePaginator()

    assert _list_s3_object_records(s3_client=FakeS3Client(), bucket="bucket", prefix="root/") == [
        {
            "key": "root/file.fastq.gz",
            "size": 7,
            "last_modified": "2026-01-01T00:00:00+00:00",
            "etag": "abc",
        }
    ]
