from __future__ import annotations

import json
from pathlib import Path

import pytest

from daylily_ec.analysis_recovery import (
    RECOVERY_SOURCE_SCHEMA,
    RECOVERY_SPEC_SCHEMA,
    AnalysisRecoveryError,
    load_recovery_source,
    materialize_recovery_source,
    sha256_file,
    snapshot_artifacts,
)


def _source_fixture(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    artifact = (
        source
        / "daylily-omics-analysis"
        / "results"
        / "day"
        / "hg38"
        / "AU-1"
        / "AU-1.g.vcf.gz"
    )
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"genuine-complete-gvcf\n")
    spec = tmp_path / "recovery-spec.json"
    payload = {
        "schema": RECOVERY_SPEC_SCHEMA,
        "source_analysis_root": str(source),
        "artifact_count": 1,
        "topology": {
            "expected_analysis_units": ["AU-1", "AU-2"],
            "recompute_analysis_units": ["AU-2"],
            "reused_analysis_units": ["AU-1"],
            "required_roles_per_reused_analysis_unit": ["hybrid_gvcf"],
            "required_global_roles": [],
        },
        "artifacts": [
            {
                "analysis_unit_uid": "AU-1",
                "complete": True,
                "path": "daylily-omics-analysis/results/day/hg38/AU-1/AU-1.g.vcf.gz",
                "role": "hybrid_gvcf",
            }
        ],
    }
    spec.write_text(json.dumps(payload), encoding="utf-8")
    return source, spec


def _write_manifest(tmp_path: Path) -> tuple[Path, dict]:
    source, spec = _source_fixture(tmp_path)
    payload = snapshot_artifacts(analysis_root=source, spec_path=spec)
    manifest = tmp_path / "recovery-source.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return manifest, payload


def test_snapshot_artifacts_binds_only_explicit_complete_paths(tmp_path: Path) -> None:
    manifest, payload = _write_manifest(tmp_path)

    artifact = payload["artifacts"][0]
    assert payload["schema"] == RECOVERY_SOURCE_SCHEMA
    assert payload["artifact_count"] == 1
    assert artifact["complete"] is True
    assert artifact["size_bytes"] > 0
    assert len(artifact["sha256"]) == 64
    assert load_recovery_source(manifest, verify_source=True)["artifact_count"] == 1


def test_snapshot_rejects_missing_required_role(tmp_path: Path) -> None:
    source, spec = _source_fixture(tmp_path)
    payload = json.loads(spec.read_text(encoding="utf-8"))
    payload["topology"]["required_roles_per_reused_analysis_unit"].append("rsr_cram")
    spec.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(AnalysisRecoveryError, match="missing required roles"):
        snapshot_artifacts(analysis_root=source, spec_path=spec)


def test_snapshot_rejects_recomputed_au_ownership(tmp_path: Path) -> None:
    source, spec = _source_fixture(tmp_path)
    payload = json.loads(spec.read_text(encoding="utf-8"))
    payload["artifacts"][0]["analysis_unit_uid"] = "AU-2"
    spec.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(AnalysisRecoveryError, match="not a reused analysis unit"):
        snapshot_artifacts(analysis_root=source, spec_path=spec)


def test_materialization_copies_and_rehashes_without_symlinks(tmp_path: Path) -> None:
    manifest, payload = _write_manifest(tmp_path)
    destination = tmp_path / "destination"
    (destination / "daylily-omics-analysis").mkdir(parents=True)

    receipt = materialize_recovery_source(
        manifest,
        destination_analysis_root=destination,
    )

    relative = payload["artifacts"][0]["path"]
    copied = destination / relative
    assert receipt["status"] == "complete"
    assert receipt["copy_method"] == "shutil.copy2"
    assert receipt["fallback_used"] is False
    assert copied.is_file() and not copied.is_symlink()
    assert sha256_file(copied) == payload["artifacts"][0]["sha256"]
    assert (destination / ".dayoa_agent/recovery/materialization.json").is_file()


def test_materialization_rejects_hash_drift_and_leaves_destination_empty(
    tmp_path: Path,
) -> None:
    manifest, payload = _write_manifest(tmp_path)
    source = Path(payload["source_analysis_root"]) / payload["artifacts"][0]["path"]
    source.write_bytes(b"changed\n")
    destination = tmp_path / "destination"
    (destination / "daylily-omics-analysis").mkdir(parents=True)

    with pytest.raises(AnalysisRecoveryError, match="hash drift"):
        materialize_recovery_source(manifest, destination_analysis_root=destination)

    assert not (destination / payload["artifacts"][0]["path"]).exists()


def test_materialization_refuses_existing_destination(tmp_path: Path) -> None:
    manifest, payload = _write_manifest(tmp_path)
    destination = tmp_path / "destination"
    existing = destination / payload["artifacts"][0]["path"]
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"unrelated\n")

    with pytest.raises(AnalysisRecoveryError, match="already contains"):
        materialize_recovery_source(manifest, destination_analysis_root=destination)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("created_at", "2026-08-26T12:00:00", "include a timezone"),
        ("source_analysis_root", "relative/source", "canonical and absolute"),
        ("artifact_count", True, "artifact_count differs"),
    ],
)
def test_recovery_source_rejects_untyped_or_noncanonical_root_fields(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    manifest, _payload = _write_manifest(tmp_path)
    raw = json.loads(manifest.read_text(encoding="utf-8"))
    raw[field] = value
    manifest.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(AnalysisRecoveryError, match=message):
        load_recovery_source(manifest, verify_source=False)


def test_recovery_source_rejects_non_string_topology_or_artifact_fields(
    tmp_path: Path,
) -> None:
    manifest, _payload = _write_manifest(tmp_path)
    raw = json.loads(manifest.read_text(encoding="utf-8"))
    raw["topology"]["expected_analysis_units"][0] = 1
    manifest.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(AnalysisRecoveryError, match="non-string"):
        load_recovery_source(manifest, verify_source=False)

    manifest, _payload = _write_manifest(tmp_path / "second")
    raw = json.loads(manifest.read_text(encoding="utf-8"))
    raw["artifacts"][0]["size_bytes"] = "23"
    manifest.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(AnalysisRecoveryError, match="size is invalid"):
        load_recovery_source(manifest, verify_source=False)
