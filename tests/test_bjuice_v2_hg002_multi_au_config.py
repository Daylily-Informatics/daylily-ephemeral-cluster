from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path

import pytest

from daylily_ec.bjuice_preval_config import BjuiceConfigError
from daylily_ec.bjuice_v2_hg002_multi_au_config import (
    AU_MATRIX,
    DIRECT_ILMN_COVERAGE_RECEIPT_SCHEMA,
    RETARGET_PLAN_SCHEMA,
    _format_subsample_pct,
    generate_bjuice_v2_hg002_multi_au_manifests,
)
from daylily_ec.manifest_set import EUID_FIELDS, identity_status, load_manifest_set


ILMN_RUN_ID = "20260618-LH01106-0011-A23MFMCLT3"
ONT_RUNS = (
    ("20260616-0040-3B-PBK89197-822a87b5", "barcode14"),
    ("20260616-0041-3C-PBK89101-bd86eaac", "barcode14"),
    ("20260616-0042-3D-PBK89102-cc11dd22", "barcode14"),
)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_tsv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _coverage_receipt(path: Path, coverage: str = "20") -> Path:
    _write_json(
        path,
        {
            "schema": DIRECT_ILMN_COVERAGE_RECEIPT_SCHEMA,
            "sample_id": "HG002",
            "status": "terminal",
            "ilmn_direct_coverage_x": coverage,
        },
    )
    return path


def _source_inputs(root: Path) -> dict[str, Path]:
    source_manifest = root / "source_manifest_resolved.json"
    source_payload = {
        "schema": "ursa.bjuice_hybrid_source_manifest.v1",
        "sources": [
            {"source_id": "ilmn-source", "uri": f"s3://fixture/illumina/{ILMN_RUN_ID}/"},
            *[
                {"source_id": f"ont-source-{index}", "uri": f"s3://fixture/pca100/2026/{run_id}/"}
                for index, (run_id, _barcode) in enumerate(ONT_RUNS, start=1)
            ],
        ],
        "runs": [
            {
                "run_id": ILMN_RUN_ID,
                "platform": "ILMN",
                "prefix_source_id": "ilmn-source",
                "position_id": "L001-L008",
            },
            *[
                {
                    "run_id": run_id,
                    "platform": "ONT",
                    "prefix_source_id": f"ont-source-{index}",
                    "position_id": f"FC{index}",
                }
                for index, (run_id, _barcode) in enumerate(ONT_RUNS, start=1)
            ],
        ],
        "mappings": [
            {"sample_id": "HG002", "run_id": run_id, "barcode": barcode}
            for run_id, barcode in ONT_RUNS
        ],
    }
    _write_json(source_manifest, source_payload)

    run_evidence = root / "run_evidence_v2.json"
    _write_json(run_evidence, {"schema": "ursa.bjuice_hybrid_run_evidence.v2"})

    matrix = root / "library_run_matrix.tsv"
    _write_tsv(
        matrix,
        [
            "specimenExternalName",
            "libType",
            "specimenEUID",
            "sampleEUID",
            "libraryEUID",
            "ONT RunEUID",
            "LIBPREP",
            "AMPLIFICATION_TYPE",
        ],
        [
            {
                "specimenExternalName": "HG002",
                "libType": "ILMN",
                "specimenEUID": "Z-reused-fixture-euid",
                "sampleEUID": "Z-reused-fixture-euid",
                "libraryEUID": "Z-reused-fixture-euid",
                "ONT RunEUID": "",
                "LIBPREP": "UNKNOWN",
                "AMPLIFICATION_TYPE": "WGS",
            },
            {
                "specimenExternalName": "HG002",
                "libType": "ONT",
                "specimenEUID": "Z-reused-fixture-euid",
                "sampleEUID": "Z-reused-fixture-euid",
                "libraryEUID": "Z-reused-fixture-euid",
                "ONT RunEUID": "Z-reused-fixture-euid",
                "LIBPREP": "UNKNOWN",
                "AMPLIFICATION_TYPE": "WGS",
            },
        ],
    )

    sample_metadata = root / "sample_metadata.tsv"
    metadata_row = {
        "SAMPLEID": "HG002",
        "SAMPLESOURCE": "research",
        "SAMPLE_TYPE": "gdna",
        "SAMPLECLASS": "research",
        "SAMPLEUSE": "posControl",
        "ORDER_TYPE": "RESEARCH",
        "CONCORDANCE_CONTROL_PATH": "/refs/HG002",
        "IS_POSITIVE_CONTROL": "true",
        "IS_NEGATIVE_CONTROL": "false",
        "TUM_NRM_SAMPLEID_MATCH": "na",
        "EXTERNAL_SAMPLE_ID": "HG002",
        "IDDNA_UID": "",
        "TRUTH_DATA_DIR": "/truth/HG002",
        "BIOLOGICAL_SEX": "male",
        "N_X": "1",
        "N_Y": "1",
        "BWA_KMER": "19",
        "DEEP_MODEL": "WGS",
        "MERGE_SINGLE": "single",
    }
    _write_tsv(sample_metadata, list(metadata_row), [metadata_row])

    units = root / "legacy_units.tsv"
    units_row = {
        "SAMPLEID": "HG002",
        "SAMPLEUSE": "posControl",
        "ORDER_TYPE": "RESEARCH",
        "BWA_KMER": "19",
        "DEEP_MODEL": "WGS",
        "MERGE_SINGLE": "single",
    }
    _write_tsv(units, list(units_row), [units_row])
    return {
        "source_manifest_json": source_manifest,
        "run_evidence_json": run_evidence,
        "library_run_matrix_tsv": matrix,
        "sample_metadata_tsv": sample_metadata,
        "legacy_units_tsv": units,
    }


def _fake_s3_listing(*, s3_client, prefix_uri: str) -> list[str]:  # noqa: ANN001
    del s3_client
    if prefix_uri.endswith(f"/{ILMN_RUN_ID}/"):
        return [
            f"s3://fixture/illumina/{ILMN_RUN_ID}/Analysis/1/Data/HG002_S1_L001_R1_001.fastq.gz",
            f"s3://fixture/illumina/{ILMN_RUN_ID}/Analysis/1/Data/HG002_S1_L001_R2_001.fastq.gz",
        ]
    for run_id, barcode in ONT_RUNS:
        if prefix_uri.endswith(f"/{run_id}/"):
            return [f"s3://fixture/pca100/2026/{run_id}/fastq_pass/{barcode}/part.fastq.gz"]
    raise AssertionError(prefix_uri)


def _generate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, coverage: str = "20"):
    import daylily_ec.bjuice_v2_hg002_multi_au_config as module

    monkeypatch.setattr(module, "_list_s3_objects", _fake_s3_listing)
    inputs = _source_inputs(tmp_path)
    receipt = _coverage_receipt(tmp_path / "direct_coverage_receipt.json", coverage)
    return generate_bjuice_v2_hg002_multi_au_manifests(
        output_dir=tmp_path / "output",
        **inputs,
        direct_ilmn_coverage_x=coverage,
        direct_ilmn_coverage_evidence=receipt,
        profile=None,
        region=None,
    )


def _retarget_plan(path: Path) -> Path:
    rows = [
        ("p5xp5", "0.5", "8.54", "0.011433798307", "0.000669426130", "0.5", 0, 1),
        ("1x1", "1", "9.85", "0.022867596615", "0.002321583412", "1", 0, 2),
        ("3x3", "3", "11.93", "0.068602789846", "0.017251330221", "3", 0, 5),
        ("5x5", "5", "12.71", "0.114337983077", "0.044979537009", "5", 0, 9),
        ("10x5", "10", "13.65", "0.228675966155", "0.167528180333", "5", 0, 9),
        ("15x5", "15", "14.01", "0.343013949233", "0.367252622305", "5", 0, 9),
        ("15x10", "15", "13.65", "0.343013949233", "0.376938405750", "10", 0, 20),
    ]
    _write_json(
        path,
        {
            "schema": RETARGET_PLAN_SCHEMA,
            "sample_id": "HG002",
            "source_analysis_id": "prior-hg002-bjuice-v2",
            "analysis_units": [
                {
                    "label": label,
                    "target_ilmn_coverage_x": target_ilmn,
                    "prior_measured_ilmn_coverage_x": prior_coverage,
                    "prior_subsample_pct": prior_pct,
                    "subsample_pct": new_pct,
                    "target_ont_coverage_x": target_ont,
                    "ont_fq_start_hour": start_hour,
                    "ont_fq_end_hour": end_hour,
                }
                for (
                    label,
                    target_ilmn,
                    prior_coverage,
                    prior_pct,
                    new_pct,
                    target_ont,
                    start_hour,
                    end_hour,
                ) in rows
            ],
        },
    )
    return path


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def test_generator_writes_exact_seven_au_matrix_and_blanks_live_euids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _generate(tmp_path, monkeypatch)
    units = _read_tsv(result.output_dir / "analysis_units.tsv")

    assert [row["ANALYSIS_UNIT_UID"] for row in units] == [
        "HG002-p5xp5",
        "HG002-1x1",
        "HG002-3x3",
        "HG002-5x5",
        "HG002-10x5",
        "HG002-15x5",
        "HG002-15x10",
    ]
    assert [row["SUBSAMPLE_PCT"] for row in units] == [
        "0.025000000000",
        "0.050000000000",
        "0.150000000000",
        "0.250000000000",
        "0.500000000000",
        "0.750000000000",
        "0.750000000000",
    ]
    assert [(row["ONT_FQ_START_HOUR"], row["ONT_FQ_END_HOUR"]) for row in units] == [
        ("0", "1"),
        ("0", "2"),
        ("0", "7"),
        ("0", "11"),
        ("0", "19"),
        ("0", "24"),
        ("0", "19"),
    ]
    assert len(_read_tsv(result.output_dir / "analysis_unit_inputs.tsv")) == 28

    manifest_set = load_manifest_set(result.output_dir)
    for filename, fields in EUID_FIELDS.items():
        for row in manifest_set.rows[filename]:
            assert all(row.get(field, "") == "" for field in fields)
    status = identity_status(manifest_set)
    assert all(counts["test"] == 0 for counts in status["fields"].values())
    assert all(counts["owner_issued"] == 0 for counts in status["fields"].values())

    receipt = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    assert receipt["direct_ilmn_coverage_x"] == "20"
    assert receipt["subsample_rounding"] == {"decimal_places": 12, "mode": "ROUND_DOWN"}
    assert [row["analysis_unit_uid"] for row in receipt["analysis_units"]] == [
        f"HG002-{label}" for label, _target, _start, _end in AU_MATRIX
    ]
    assert "Z-reused-fixture-euid" not in result.receipt_path.read_text(encoding="utf-8")


def test_round_down_is_explicit_and_not_bankers_rounding() -> None:
    assert _format_subsample_pct(
        target_x=Decimal("1"),
        coverage_x=Decimal("6"),
        au_label="fixture",
    ) == "0.166666666666"


def test_generator_applies_strict_measured_coverage_retarget_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import daylily_ec.bjuice_v2_hg002_multi_au_config as module

    monkeypatch.setattr(module, "_list_s3_objects", _fake_s3_listing)
    inputs = _source_inputs(tmp_path)
    receipt = _coverage_receipt(tmp_path / "direct_coverage_receipt.json", "20")
    plan = _retarget_plan(tmp_path / "retarget_plan.json")
    result = generate_bjuice_v2_hg002_multi_au_manifests(
        output_dir=tmp_path / "output",
        **inputs,
        direct_ilmn_coverage_x="20",
        direct_ilmn_coverage_evidence=receipt,
        retarget_plan_json=plan,
        profile=None,
        region=None,
    )
    units = _read_tsv(result.output_dir / "analysis_units.tsv")
    assert [row["SUBSAMPLE_PCT"] for row in units] == [
        "0.000669426130",
        "0.002321583412",
        "0.017251330221",
        "0.044979537009",
        "0.167528180333",
        "0.367252622305",
        "0.376938405750",
    ]
    assert [(row["ONT_FQ_START_HOUR"], row["ONT_FQ_END_HOUR"]) for row in units] == [
        ("0", "1"), ("0", "2"), ("0", "5"), ("0", "9"),
        ("0", "9"), ("0", "9"), ("0", "20"),
    ]
    generated_receipt = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    assert generated_receipt["retarget_plan"]["schema"] == RETARGET_PLAN_SCHEMA
    assert generated_receipt["retarget_plan"]["mode"] == "per_au_measured_coverage_one_step_correction"


def test_generator_rejects_retarget_plan_fraction_that_does_not_match_measurement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import daylily_ec.bjuice_v2_hg002_multi_au_config as module

    monkeypatch.setattr(module, "_list_s3_objects", _fake_s3_listing)
    inputs = _source_inputs(tmp_path)
    receipt = _coverage_receipt(tmp_path / "direct_coverage_receipt.json", "20")
    plan = _retarget_plan(tmp_path / "retarget_plan.json")
    payload = json.loads(plan.read_text(encoding="utf-8"))
    payload["analysis_units"][0]["subsample_pct"] = "0.000669426131"
    _write_json(plan, payload)
    with pytest.raises(BjuiceConfigError, match="must equal prior_subsample_pct"):
        generate_bjuice_v2_hg002_multi_au_manifests(
            output_dir=tmp_path / "output",
            **inputs,
            direct_ilmn_coverage_x="20",
            direct_ilmn_coverage_evidence=receipt,
            retarget_plan_json=plan,
            profile=None,
            region=None,
        )


@pytest.mark.parametrize("coverage", ["", "0", "-1", "NaN", "Infinity", "not-a-number"])
def test_generator_rejects_invalid_direct_coverage_before_writing(
    tmp_path: Path, coverage: str
) -> None:
    output_dir = tmp_path / "output"
    with pytest.raises(BjuiceConfigError, match="coverage"):
        generate_bjuice_v2_hg002_multi_au_manifests(
            output_dir=output_dir,
            source_manifest_json=tmp_path / "missing-source.json",
            run_evidence_json=tmp_path / "missing-run-evidence.json",
            library_run_matrix_tsv=tmp_path / "missing-matrix.tsv",
            sample_metadata_tsv=tmp_path / "missing-metadata.tsv",
            legacy_units_tsv=tmp_path / "missing-units.tsv",
            direct_ilmn_coverage_x=coverage,
            direct_ilmn_coverage_evidence=tmp_path / "missing-coverage.json",
            profile=None,
            region=None,
        )
    assert not output_dir.exists()


def test_generator_rejects_target_above_verified_direct_coverage(tmp_path: Path) -> None:
    receipt = _coverage_receipt(tmp_path / "direct_coverage_receipt.json", "14.99")
    output_dir = tmp_path / "output"
    with pytest.raises(BjuiceConfigError, match="exceeds verified direct Illumina coverage"):
        generate_bjuice_v2_hg002_multi_au_manifests(
            output_dir=output_dir,
            source_manifest_json=tmp_path / "missing-source.json",
            run_evidence_json=tmp_path / "missing-run-evidence.json",
            library_run_matrix_tsv=tmp_path / "missing-matrix.tsv",
            sample_metadata_tsv=tmp_path / "missing-metadata.tsv",
            legacy_units_tsv=tmp_path / "missing-units.tsv",
            direct_ilmn_coverage_x="14.99",
            direct_ilmn_coverage_evidence=receipt,
            profile=None,
            region=None,
        )
    assert not output_dir.exists()


def test_generator_rejects_missing_direct_coverage_evidence(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    with pytest.raises(BjuiceConfigError, match="coverage evidence is missing"):
        generate_bjuice_v2_hg002_multi_au_manifests(
            output_dir=output_dir,
            source_manifest_json=tmp_path / "missing-source.json",
            run_evidence_json=tmp_path / "missing-run-evidence.json",
            library_run_matrix_tsv=tmp_path / "missing-matrix.tsv",
            sample_metadata_tsv=tmp_path / "missing-metadata.tsv",
            legacy_units_tsv=tmp_path / "missing-units.tsv",
            direct_ilmn_coverage_x="20",
            direct_ilmn_coverage_evidence=tmp_path / "missing-coverage.json",
            profile=None,
            region=None,
        )
    assert not output_dir.exists()


def test_generator_rejects_ambiguous_non_direct_coverage_evidence(tmp_path: Path) -> None:
    receipt = _coverage_receipt(tmp_path / "direct_coverage_receipt.json")
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    payload["hybrid_coverage_x"] = "24"
    _write_json(receipt, payload)
    with pytest.raises(BjuiceConfigError, match="ambiguous"):
        generate_bjuice_v2_hg002_multi_au_manifests(
            output_dir=tmp_path / "output",
            source_manifest_json=tmp_path / "missing-source.json",
            run_evidence_json=tmp_path / "missing-run-evidence.json",
            library_run_matrix_tsv=tmp_path / "missing-matrix.tsv",
            sample_metadata_tsv=tmp_path / "missing-metadata.tsv",
            legacy_units_tsv=tmp_path / "missing-units.tsv",
            direct_ilmn_coverage_x="20",
            direct_ilmn_coverage_evidence=receipt,
            profile=None,
            region=None,
        )
