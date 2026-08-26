from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

import daylily_ec.cli as cli_module
from daylily_ec.analysis_recovery import RECOVERY_SOURCE_SCHEMA, RECOVERY_SPEC_SCHEMA
from daylily_ec.cli import app
from daylily_ec.repositories import CURRENT_DYEC_BUILD, load_repository_catalog

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CATALOG = ROOT / "config/daylily_pipeline_command_catalog.yaml"
PACKAGED_CATALOG = (
    ROOT / "daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml"
)
COMMAND_ID = "bloodbridge-bjuice-inflection-artifact-recovery"
runner = CliRunner()


def _write_recovery_source(path: Path) -> None:
    payload = {
        "schema": RECOVERY_SOURCE_SCHEMA,
        "created_at": "2026-08-26T12:00:00+00:00",
        "source_analysis_root": "/fsx/analysis_results/bjuiceval-19024/source-analysis",
        "source_spec_sha256": "a" * 64,
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
                "size_bytes": 17,
                "sha256": "b" * 64,
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_local_snapshot_fixture(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "analysis_results" / "bjuiceval-19024" / "source-analysis"
    artifact = (
        source
        / "daylily-omics-analysis/results/day/hg38/AU-1/AU-1.g.vcf.gz"
    )
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"complete-gvcf\n")
    spec = tmp_path / "recovery-spec.json"
    spec.write_text(
        json.dumps(
            {
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
                        "path": (
                            "daylily-omics-analysis/results/day/hg38/"
                            "AU-1/AU-1.g.vcf.gz"
                        ),
                        "role": "hybrid_gvcf",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return source, spec


def test_release_snapshot_is_exact_and_recovery_command_is_strict() -> None:
    assert CURRENT_DYEC_BUILD == "19.0.31"
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()
    raw = yaml.safe_load(SOURCE_CATALOG.read_text(encoding="utf-8"))
    assert raw["repositories"]["daylily-omics-analysis"]["default_ref"] == "16.0.7"
    assert COMMAND_ID not in raw["dyec_builds"]["19.0.30"].get("aliases", {})

    catalog = load_repository_catalog(SOURCE_CATALOG)
    command = catalog.get_command_for_dyec_build(COMMAND_ID, "19.0.31")
    assert command.git_tag == "16.0.7"
    assert command.artifact_recovery_required is True
    assert command.runtime_config_target == "config/dyec_runtime_config.yaml"
    assert command.jobs == 444
    assert command.targets == [
        "produce_sentdhiomr2_slim_kitchensink_mega",
        "produce_sentdhiomr2_inflection_analytical_package",
    ]
    assert command.dryrun_dy_command == command.dy_command + " -n"
    assert " -j 444 -T 1 -p -k " in command.dy_command
    assert "--rerun-triggers mtime" in command.dy_command


def test_catalog_command_requires_both_explicit_recovery_inputs() -> None:
    command = load_repository_catalog(SOURCE_CATALOG).get_command_for_dyec_build(
        COMMAND_ID, "19.0.31"
    )
    common = {
        "analysis_id": "fresh-analysis",
        "executing_entity": "bjuiceval-19024",
        "manifest_dir": "/tmp/manifests",
        "runtime_config_file": "/tmp/bloodbridge.yaml",
        "cost_center": "bjuiceval-19024-ccenter",
    }
    with pytest.raises(ValueError, match="requires artifact_recovery_manifest"):
        command.launch_argv(**common)

    argv = command.launch_argv(
        **common,
        artifact_recovery_manifest="/tmp/recovery-source.json",
        dry_run=True,
    )
    assert argv[argv.index("--artifact-recovery-manifest") + 1] == (
        "/tmp/recovery-source.json"
    )
    assert argv[argv.index("--runtime-config-file") + 1] == "/tmp/bloodbridge.yaml"
    assert "--dry-run" in argv
    assert "--replace-existing-analysis-dir" not in argv

    with pytest.raises(ValueError, match="fresh, absent"):
        command.launch_argv(
            **common,
            artifact_recovery_manifest="/tmp/recovery-source.json",
            replace_existing_analysis_dir=True,
        )


def test_public_workflow_launch_forwards_validated_recovery_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import daylily_ec.manifest_set as manifest_set_module
    import daylily_ec.scripts.daylily_run_omics_analysis_headnode as launch_module

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    runtime_config = tmp_path / "bloodbridge.yaml"
    runtime_config.write_text("sentdhiomr2: {}\n", encoding="utf-8")
    recovery = tmp_path / "recovery-source.json"
    _write_recovery_source(recovery)
    calls: dict[str, list[str]] = {}

    monkeypatch.setattr(manifest_set_module, "load_manifest_set", lambda _path: object())
    monkeypatch.setattr(cli_module, "_warn_if_dayec_env_inactive", lambda: None)
    monkeypatch.setattr(
        launch_module,
        "main",
        lambda argv: calls.setdefault("argv", list(argv)) and 0,
    )

    result = runner.invoke(
        app,
        [
            "workflow",
            "launch",
            "--profile",
            "lsmc",
            "--region",
            "us-west-2",
            "--cluster",
            "bjuiceval-19024",
            "--analysis-id",
            "fresh-analysis",
            "--executing-entity",
            "bjuiceval-19024",
            "--git-tag",
            "16.0.7",
            "--manifest-dir",
            str(manifest_dir),
            "--runtime-config-file",
            str(runtime_config),
            "--artifact-recovery-manifest",
            str(recovery),
            "--cost-center",
            "bjuiceval-19024-ccenter",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    argv = calls["argv"]
    assert argv[argv.index("--artifact-recovery-manifest") + 1] == str(recovery)
    assert argv[argv.index("--runtime-config-file") + 1] == str(runtime_config)


def test_public_workflow_launch_rejects_recovery_overwrite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import daylily_ec.manifest_set as manifest_set_module

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    recovery = tmp_path / "recovery-source.json"
    _write_recovery_source(recovery)
    monkeypatch.setattr(manifest_set_module, "load_manifest_set", lambda _path: object())
    monkeypatch.setattr(cli_module, "_warn_if_dayec_env_inactive", lambda: None)

    result = runner.invoke(
        app,
        [
            "workflow",
            "launch",
            "--profile",
            "lsmc",
            "--region",
            "us-west-2",
            "--cluster",
            "bjuiceval-19024",
            "--analysis-id",
            "fresh-analysis",
            "--git-tag",
            "16.0.7",
            "--manifest-dir",
            str(manifest_dir),
            "--artifact-recovery-manifest",
            str(recovery),
            "--replace-existing-analysis-dir",
        ],
    )

    assert result.exit_code != 0
    assert "fresh, absent analysis capsule" in result.output


def test_public_snapshot_artifacts_writes_a_new_bound_manifest(tmp_path: Path) -> None:
    source, spec = _write_local_snapshot_fixture(tmp_path)
    output = tmp_path / "recovery-source.json"

    result = runner.invoke(
        app,
        [
            "--json",
            "analysis",
            "snapshot-artifacts",
            "--analysis-root",
            str(source),
            "--spec-file",
            str(spec),
            "--output-file",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    durable = json.loads(output.read_text(encoding="utf-8"))
    assert payload == durable
    assert payload["schema"] == RECOVERY_SOURCE_SCHEMA
    assert payload["artifact_count"] == 1
    assert payload["artifacts"][0]["size_bytes"] == len(b"complete-gvcf\n")
    assert len(payload["artifacts"][0]["sha256"]) == 64
    assert list((source / ".dayoa_agent/visits").glob("*.jsonl"))

    repeated = runner.invoke(
        app,
        [
            "analysis",
            "snapshot-artifacts",
            "--analysis-root",
            str(source),
            "--spec-file",
            str(spec),
            "--output-file",
            str(output),
        ],
    )
    assert repeated.exit_code != 0
    assert "refusing to overwrite" in repeated.output
