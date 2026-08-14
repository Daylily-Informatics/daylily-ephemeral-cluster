from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from daylily_ec.identity_receipts import (
    IdentityReceiptError,
    apply,
    evidence,
    plan,
    status,
    validate,
    write_payload,
)
from daylily_ec.manifest_set import (
    MANIFEST_NAMES,
    ManifestSetError,
    identity_status,
    load_manifest_set,
    selected_input_details,
)


def _write(path: Path, columns: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(rows)


def six_manifests(root: Path, *, delivery: bool = False) -> Path:
    root.mkdir()
    _write(root / "specimens.tsv", ["SPECIMEN_ID", "SPECIMEN_EUID"], [["SP1", "Z-SP-1"]])
    _write(
        root / "samples.tsv",
        ["SAMPLEID", "SPECIMEN_ID", "SAMPLE_EUID"],
        [["SA1", "SP1", "Z-SA-1"]],
    )
    _write(
        root / "libraries.tsv",
        ["LIBRARY_ID", "SAMPLEID", "LIBRARY_EUID"],
        [["L1", "SA1", "Z-L-1"], ["L2", "SA1", "Z-L-2"]],
    )
    _write(
        root / "sequencing_inputs.tsv",
        [
            "SEQUENCING_INPUT_UID",
            "LIBRARY_ID",
            "MODALITY",
            "LAYOUT",
            "ILMN_R1_PATH",
            "ILMN_R2_PATH",
            "ONT_R1_PATH",
        ],
        [
            ["I1", "L1", "sr", "paired_fastq", "/data/i1_R1.fastq.gz", "/data/i1_R2.fastq.gz", ""],
            ["I2", "L2", "lr", "single_fastq", "", "", "/data/i2.fastq.gz"],
        ],
    )
    _write(
        root / "analysis_units.tsv",
        [
            "ANALYSIS_UNIT_UID",
            "SAMPLEID",
            "ANALYSIS_UNIT_EUID",
            "DELIVERY_EUID",
            "DELIVERY_PROFILE",
        ],
        [["AU1", "SA1", "Z-AU-1", "Z-D-1", "inflection" if delivery else ""]],
    )
    _write(
        root / "analysis_unit_inputs.tsv",
        ["ANALYSIS_UNIT_UID", "SEQUENCING_INPUT_UID", "ROLE", "INPUT_ORDINAL"],
        [["AU1", "I1", "sr", "1"], ["AU1", "I2", "lr", "2"]],
    )
    return root


def test_load_six_manifests_preserves_plural_lineage(tmp_path: Path) -> None:
    manifests = load_manifest_set(six_manifests(tmp_path / "m"))
    assert tuple(manifests.paths) == MANIFEST_NAMES
    details = selected_input_details(manifests)["AU1"]
    assert details["library_ids"] == ["L1", "L2"]
    assert [row["role"] for row in details["sequencing_inputs"]] == ["sr", "lr"]
    assert identity_status(manifests)["customer_release_eligible_units"] == 0
    assert validate(manifests.root)["invariants"]["network_accessed"] is False


def test_reused_z_euids_remain_test_only_fixture_values(tmp_path: Path) -> None:
    """A deliberately duplicated Z-* value is valid test data, not live identity."""

    root = six_manifests(tmp_path / "reused-z")
    repeated = "Z-reused-fixture-euid"
    _write(root / "specimens.tsv", ["SPECIMEN_ID", "SPECIMEN_EUID"], [["SP1", repeated]])
    _write(root / "samples.tsv", ["SAMPLEID", "SPECIMEN_ID", "SAMPLE_EUID"], [["SA1", "SP1", repeated]])
    _write(
        root / "libraries.tsv",
        ["LIBRARY_ID", "SAMPLEID", "LIBRARY_EUID"],
        [["L1", "SA1", repeated], ["L2", "SA1", repeated]],
    )
    _write(
        root / "analysis_units.tsv",
        ["ANALYSIS_UNIT_UID", "SAMPLEID", "ANALYSIS_UNIT_EUID", "DELIVERY_EUID"],
        [["AU1", "SA1", repeated, repeated]],
    )

    status = identity_status(load_manifest_set(root))

    assert all(counts["owner_issued"] == 0 for counts in status["fields"].values())
    assert status["analysis_units"][0]["customer_release_eligible"] is False
    assert "SPECIMEN_EUID" in status["analysis_units"][0]["test_identity_fields"]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda root: (root / "units.tsv").write_text("x\n", encoding="utf-8"), "legacy"),
        (lambda root: (root / "libraries.tsv").unlink(), "missing required"),
        (
            lambda root: (root / "analysis_unit_inputs.tsv").write_text(
                "ANALYSIS_UNIT_UID\tSEQUENCING_INPUT_UID\tROLE\tINPUT_ORDINAL\n"
                "AU1\tI1\tbad\t1\n",
                encoding="utf-8",
            ),
            "ROLE",
        ),
    ],
)
def test_manifest_contract_rejects_incomplete_or_legacy(
    tmp_path: Path, mutation, message: str
) -> None:
    root = six_manifests(tmp_path / "m")
    mutation(root)
    with pytest.raises(ManifestSetError, match=message):
        load_manifest_set(root)


def test_manifest_contract_rejects_cross_sample_and_noncontiguous_inputs(tmp_path: Path) -> None:
    root = six_manifests(tmp_path / "cross")
    _write(root / "samples.tsv", ["SAMPLEID", "SPECIMEN_ID"], [["SA1", "SP1"], ["SA2", "SP1"]])
    _write(root / "libraries.tsv", ["LIBRARY_ID", "SAMPLEID"], [["L1", "SA1"], ["L2", "SA2"]])
    with pytest.raises(ManifestSetError, match="do not resolve"):
        load_manifest_set(root)


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (
            [["I1", "L1", "ILMN", "paired_fastq", "/r1", "/r2", ""]],
            "MODALITY",
        ),
        (
            [["I1", "L1", "sr", "single_fastq", "/r1", "/r2", ""]],
            "LAYOUT must be paired_fastq",
        ),
        (
            [["I1", "L1", "sr", "paired_fastq", "/r1", "/r2", "/ont"]],
            "exactly one source bundle",
        ),
    ],
)
def test_manifest_contract_requires_exact_source_bundle(
    tmp_path: Path, rows: list[list[str]], message: str
) -> None:
    root = six_manifests(tmp_path / "m")
    _write(
        root / "sequencing_inputs.tsv",
        [
            "SEQUENCING_INPUT_UID",
            "LIBRARY_ID",
            "MODALITY",
            "LAYOUT",
            "ILMN_R1_PATH",
            "ILMN_R2_PATH",
            "ONT_R1_PATH",
        ],
        rows,
    )
    _write(
        root / "analysis_unit_inputs.tsv",
        ["ANALYSIS_UNIT_UID", "SEQUENCING_INPUT_UID", "ROLE", "INPUT_ORDINAL"],
        [["AU1", "I1", "sr", "1"]],
    )
    with pytest.raises(ManifestSetError, match=message):
        load_manifest_set(root)


@pytest.mark.parametrize("blank", ["", "na", "none", "null", "NA", "NoNe", "NULL"])
def test_source_bundle_primary_uses_dayoa_blank_sentinels(tmp_path: Path, blank: str) -> None:
    root = six_manifests(tmp_path / "m")
    _write(
        root / "sequencing_inputs.tsv",
        [
            "SEQUENCING_INPUT_UID",
            "LIBRARY_ID",
            "MODALITY",
            "LAYOUT",
            "ILMN_R1_PATH",
            "ONT_R1_PATH",
        ],
        [["I1", "L1", "sr", "single_fastq", "/data/real.fastq.gz", blank]],
    )
    _write(
        root / "analysis_unit_inputs.tsv",
        ["ANALYSIS_UNIT_UID", "SEQUENCING_INPUT_UID", "ROLE", "INPUT_ORDINAL"],
        [["AU1", "I1", "sr", "1"]],
    )

    manifests = load_manifest_set(root)

    assert manifests.rows["sequencing_inputs.tsv"][0]["ILMN_R1_PATH"] == ("/data/real.fastq.gz")


@pytest.mark.parametrize("blank", ["", "na", "none", "null", "NA", "NoNe", "NULL"])
def test_source_bundle_secondary_uses_dayoa_blank_sentinels(tmp_path: Path, blank: str) -> None:
    root = six_manifests(tmp_path / "m")
    _write(
        root / "sequencing_inputs.tsv",
        [
            "SEQUENCING_INPUT_UID",
            "LIBRARY_ID",
            "MODALITY",
            "LAYOUT",
            "ILMN_R1_PATH",
            "ILMN_R2_PATH",
        ],
        [["I1", "L1", "sr", "single_fastq", "/data/real_R1.fastq.gz", blank]],
    )
    _write(
        root / "analysis_unit_inputs.tsv",
        ["ANALYSIS_UNIT_UID", "SEQUENCING_INPUT_UID", "ROLE", "INPUT_ORDINAL"],
        [["AU1", "I1", "sr", "1"]],
    )

    load_manifest_set(root)


def test_source_bundle_valid_secondary_path_requires_paired_layout(tmp_path: Path) -> None:
    root = six_manifests(tmp_path / "m")
    _write(
        root / "sequencing_inputs.tsv",
        [
            "SEQUENCING_INPUT_UID",
            "LIBRARY_ID",
            "MODALITY",
            "LAYOUT",
            "ILMN_R1_PATH",
            "ILMN_R2_PATH",
        ],
        [
            [
                "I1",
                "L1",
                "sr",
                "paired_fastq",
                "/data/real_R1.fastq.gz",
                "/data/real_R2.fastq.gz",
            ]
        ],
    )
    _write(
        root / "analysis_unit_inputs.tsv",
        ["ANALYSIS_UNIT_UID", "SEQUENCING_INPUT_UID", "ROLE", "INPUT_ORDINAL"],
        [["AU1", "I1", "sr", "1"]],
    )

    load_manifest_set(root)


def test_manifest_contract_requires_join_role_to_match_input_modality(tmp_path: Path) -> None:
    root = six_manifests(tmp_path / "m")
    _write(
        root / "analysis_unit_inputs.tsv",
        ["ANALYSIS_UNIT_UID", "SEQUENCING_INPUT_UID", "ROLE", "INPUT_ORDINAL"],
        [["AU1", "I1", "lr", "1"], ["AU1", "I2", "lr", "2"]],
    )
    with pytest.raises(ManifestSetError, match="ROLE must equal"):
        load_manifest_set(root)

    root = six_manifests(tmp_path / "order")
    _write(
        root / "analysis_unit_inputs.tsv",
        ["ANALYSIS_UNIT_UID", "SEQUENCING_INPUT_UID", "ROLE", "INPUT_ORDINAL"],
        [["AU1", "I1", "sr", "1"], ["AU1", "I2", "lr", "3"]],
    )
    with pytest.raises(ManifestSetError, match="not contiguous"):
        load_manifest_set(root)


def test_offline_plan_apply_and_replay_are_hash_bound(tmp_path: Path) -> None:
    root = six_manifests(tmp_path / "m")
    receipt = tmp_path / "owner.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": "dyec.identity_source_receipt.v1",
                "updates": [
                    {
                        "manifest": "specimens.tsv",
                        "key_value": "SP1",
                        "euid_field": "SPECIMEN_EUID",
                        "euid": "OWNER-SP-1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    # Existing test values cannot be silently replaced by an owner value.
    with pytest.raises(IdentityReceiptError, match="conflicts"):
        plan(root, identity_receipt=receipt)

    _write(root / "specimens.tsv", ["SPECIMEN_ID", "SPECIMEN_EUID"], [["SP1", ""]])
    payload = plan(root, identity_receipt=receipt)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(payload), encoding="utf-8")
    applied = apply(root, plan_path=plan_path, output_dir=tmp_path / "out")
    assert applied["updates_applied"] == 1
    assert load_manifest_set(tmp_path / "out").rows["specimens.tsv"][0]["SPECIMEN_EUID"] == "OWNER-SP-1"
    assert status(tmp_path / "out")["network_accessed"] is False
    assert evidence(tmp_path / "out")["provider_neutral"] is True

    (root / "specimens.tsv").write_text("SPECIMEN_ID\tSPECIMEN_EUID\nSP1\tCHANGED\n", encoding="utf-8")
    with pytest.raises(IdentityReceiptError, match="source hashes"):
        apply(root, plan_path=plan_path, output_dir=tmp_path / "out2")


def test_identity_receipt_rejects_test_euid_and_unsafe_fields(tmp_path: Path) -> None:
    root = six_manifests(tmp_path / "m")
    for update, message in (
        (
            {
                "manifest": "samples.tsv",
                "key_value": "SA1",
                "euid_field": "SAMPLE_EUID",
                "euid": "Z-NEW",
            },
            "Z-",
        ),
        (
            {
                "manifest": "samples.tsv",
                "key_value": "SA1",
                "euid_field": "DELIVERY_EUID",
                "euid": "OWNER-D-1",
            },
            "cannot set",
        ),
    ):
        receipt = tmp_path / "owner.json"
        receipt.write_text(
            json.dumps({"schema_version": "dyec.identity_source_receipt.v1", "updates": [update]}),
            encoding="utf-8",
        )
        with pytest.raises(IdentityReceiptError, match=message):
            plan(root, identity_receipt=receipt)


def test_apply_requires_empty_destination_and_valid_plan_hash(tmp_path: Path) -> None:
    root = six_manifests(tmp_path / "m")
    payload = plan(root)
    payload["network_accessed"] = True
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(IdentityReceiptError, match="hash"):
        apply(root, plan_path=plan_path, output_dir=tmp_path / "out")

    payload = plan(root)
    plan_path.write_text(json.dumps(payload), encoding="utf-8")
    out = tmp_path / "occupied"
    out.mkdir()
    (out / "x").write_text("x", encoding="utf-8")
    with pytest.raises(IdentityReceiptError, match="must be empty"):
        apply(root, plan_path=plan_path, output_dir=out)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("{", "unreadable"),
        ("[]", "must be an object"),
    ],
)
def test_identity_json_requires_readable_object(
    tmp_path: Path, payload: str, message: str
) -> None:
    root = six_manifests(tmp_path / "m")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(payload, encoding="utf-8")
    with pytest.raises(IdentityReceiptError, match=message):
        plan(root, identity_receipt=receipt)


@pytest.mark.parametrize(
    ("receipt_payload", "message"),
    [
        ({"schema_version": "wrong", "updates": []}, "must use"),
        ({"schema_version": "dyec.identity_source_receipt.v1", "updates": {}}, "must be a list"),
        ({"schema_version": "dyec.identity_source_receipt.v1", "updates": ["bad"]}, "must be an object"),
        (
            {
                "schema_version": "dyec.identity_source_receipt.v1",
                "updates": [
                    {
                        "manifest": "samples.tsv",
                        "key_value": " ",
                        "euid_field": "SAMPLE_EUID",
                        "euid": "OWNER-SA-1",
                    }
                ],
            },
            "blank or whitespace",
        ),
        (
            {
                "schema_version": "dyec.identity_source_receipt.v1",
                "updates": [
                    {
                        "manifest": "analysis_unit_inputs.tsv",
                        "key_value": "AU1",
                        "euid_field": "ANY_EUID",
                        "euid": "OWNER-1",
                    }
                ],
            },
            "unsupported manifest",
        ),
        (
            {
                "schema_version": "dyec.identity_source_receipt.v1",
                "updates": [
                    {
                        "manifest": "samples.tsv",
                        "key_value": "ABSENT",
                        "euid_field": "SAMPLE_EUID",
                        "euid": "OWNER-SA-1",
                    }
                ],
            },
            "absent key",
        ),
    ],
)
def test_identity_receipt_shape_errors(
    tmp_path: Path, receipt_payload: dict[str, object], message: str
) -> None:
    root = six_manifests(tmp_path / "m")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps(receipt_payload), encoding="utf-8")
    with pytest.raises(IdentityReceiptError, match=message):
        plan(root, identity_receipt=receipt)


def test_identity_receipt_rejects_duplicate_update_and_wrong_plan_schema(tmp_path: Path) -> None:
    root = six_manifests(tmp_path / "m")
    _write(root / "specimens.tsv", ["SPECIMEN_ID", "SPECIMEN_EUID"], [["SP1", ""]])
    update = {
        "manifest": "specimens.tsv",
        "key_value": "SP1",
        "euid_field": "SPECIMEN_EUID",
        "euid": "OWNER-SP-1",
    }
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": "dyec.identity_source_receipt.v1",
                "updates": [update, update],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(IdentityReceiptError, match="duplicates"):
        plan(root, identity_receipt=receipt)

    bad_plan = tmp_path / "bad-plan.json"
    bad_plan.write_text(json.dumps({"schema_version": "wrong"}), encoding="utf-8")
    with pytest.raises(IdentityReceiptError, match="identity plan must use"):
        apply(root, plan_path=bad_plan, output_dir=tmp_path / "out")


def test_write_payload_persists_exact_json(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "evidence.json"
    write_payload({"schema_version": "test.v1", "network_accessed": False}, output)
    assert json.loads(output.read_text(encoding="utf-8")) == {
        "network_accessed": False,
        "schema_version": "test.v1",
    }
