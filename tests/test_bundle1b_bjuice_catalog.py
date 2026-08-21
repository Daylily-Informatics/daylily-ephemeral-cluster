from __future__ import annotations

import hashlib
import json
import shlex
from pathlib import Path

import yaml
from typer.testing import CliRunner

from daylily_ec.cli import app
from daylily_ec.manifest_set import load_manifest_set
from daylily_ec.repositories import load_repository_catalog


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CATALOG = REPO_ROOT / "config" / "daylily_pipeline_command_catalog.yaml"
PACKAGED_CATALOG = (
    REPO_ROOT
    / "daylily_ec"
    / "resources"
    / "payload"
    / "config"
    / "daylily_pipeline_command_catalog.yaml"
)
BUNDLE_ROOT = REPO_ROOT / "docs" / "jem" / "bjuice_validation" / "configs" / "bundle1b"
RUNTIME_CONFIG = BUNDLE_ROOT / "bjuice_validation_bundle1b_hiomr2.yaml"
COMMAND_ID = "inflection-bjuice-bundle1b-product-v0.9"
runner = CliRunner()


def test_bundle1b_catalog_contract_and_truth_configuration() -> None:
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()
    manifests = load_manifest_set(BUNDLE_ROOT)
    assert {
        "specimens": len(manifests.rows["specimens.tsv"]),
        "samples": len(manifests.rows["samples.tsv"]),
        "libraries": len(manifests.rows["libraries.tsv"]),
        "sequencing_inputs": len(manifests.rows["sequencing_inputs.tsv"]),
        "analysis_units": len(manifests.rows["analysis_units.tsv"]),
        "analysis_unit_inputs": len(manifests.rows["analysis_unit_inputs.tsv"]),
    } == {
        "specimens": 28,
        "samples": 28,
        "libraries": 64,
        "sequencing_inputs": 64,
        "analysis_units": 32,
        "analysis_unit_inputs": 64,
    }
    runtime = yaml.safe_load(RUNTIME_CONFIG.read_text(encoding="utf-8"))
    assert runtime["ont_fastq_hour_window_mode"] == "per_analysis_unit"
    assert runtime["truvari_sv_benchmark"]["env_yaml"] == "../envs/truvari_v0.2.yaml"
    benchmark = runtime["truvari_sv_benchmark"]["truthsets"]["HG002"]["regions"]
    region = benchmark["giab_sv_v5_0q_hc"]
    for truth_key in ("truth_vcf", "truth_tbi", "truth_bed"):
        value = region[truth_key]
        assert value
        assert Path(value).is_absolute()
    hg002_rows = [
        row for row in manifests.rows["samples.tsv"] if row["SAMPLEID"] == "HG002"
    ]
    assert hg002_rows and all(row["TRUTH_DATA_DIR"] for row in hg002_rows)

    command = load_repository_catalog(SOURCE_CATALOG).get_command(COMMAND_ID)
    assert command.type == "test"
    assert command.test_data_profile == "bundle1b_full_au_run_mounts"
    assert command.runtime_config_target == "config/dyec_runtime_config.yaml"
    assert command.jobs == 456
    assert command.keep_going and command.restart_times == 1
    assert command.dryrun_dy_command == f"{command.dy_command} -n"
    assert "-T 1 -p -k" in command.dryrun_dy_command


def test_bundle1b_catalog_render_binds_runtime_config() -> None:
    result = runner.invoke(
        app,
        [
            "--json",
            "catalog",
            "render",
            COMMAND_ID,
            "--config",
            str(SOURCE_CATALOG),
            "--analysis-id",
            "pclu18045-bundle1b-render",
            "--executing-entity",
            "pclu-18045",
            "--cost-center",
            "pclu-18045-ccenter",
            "--manifest-dir",
            str(BUNDLE_ROOT),
            "--runtime-config-file",
            str(RUNTIME_CONFIG),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    rendered = json.loads(result.output)
    tokens = shlex.split(rendered["dy_command"])
    assert "--configfile" in tokens
    assert tokens[tokens.index("--configfile") + 1] == "config/dyec_runtime_config.yaml"
    assert "-n" in tokens
    assert tokens[tokens.index("-j") + 1] == "456"
    assert tokens[tokens.index("-T") + 1] == "1"
    assert "-p" in tokens and "-k" in tokens
    workflow_argv = rendered["workflow_argv"]
    assert workflow_argv[workflow_argv.index("--runtime-config-file") + 1] == str(RUNTIME_CONFIG)
    assert hashlib.sha256(RUNTIME_CONFIG.read_bytes()).hexdigest() == "276dd735b210a621ca65c84525f5a3bbc5d0114da7bbd78fc41096b19d18bb92"
