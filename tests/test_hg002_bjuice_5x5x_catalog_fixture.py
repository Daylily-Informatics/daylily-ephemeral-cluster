from __future__ import annotations

import json
from pathlib import Path

from daylily_ec.manifest_set import load_manifest_set
from daylily_ec.repositories import load_repository_catalog

REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_BJUICE_BUILD = "18.0.50"
SOURCE_CATALOG = REPO_ROOT / "config/daylily_pipeline_command_catalog.yaml"
PACKAGED_CATALOG = (
    REPO_ROOT / "daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml"
)
FIXTURE_ROOT = (
    REPO_ROOT
    / "daylily_ec/resources/payload/examples/staging/"
    / "hg002_bjuice_verified_5x5x_fastq"
)


def test_hg002_bjuice_catalog_uses_verified_5x5x_fixture() -> None:
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()
    catalog = load_repository_catalog(SOURCE_CATALOG)
    command = catalog.get_command_for_dyec_build(
        "inflection-bjuice-product-v0.2", HISTORICAL_BJUICE_BUILD
    )
    profile = catalog.test_data_profiles[command.test_data_profile]

    assert "inflection-bjuice-product-v0.2" not in {
        item.command_id for item in catalog.commands()
    }

    assert command.test_data_profile == "hg002_bjuice_verified_5x5x_fastq"
    assert command.manifest_dir_template.endswith("/hg002_bjuice_verified_5x5x_fastq")
    assert command.targets == [
        "produce_sentdhiomr2_slim_kitchensink_mega",
        "produce_sentdhiomr2_inflection_analytical_package",
    ]
    assert command.genome == "hg38"
    assert command.jobs == 333
    assert command.dy_command.endswith("-j 333 -T 0 -p --rerun-triggers mtime")
    assert " -k " not in command.dy_command
    assert not command.dy_command.endswith(" -n")
    assert command.dryrun_dy_command == f"{command.dy_command} -n"
    assert command.runtime_parameters == {}
    assert "produce_sentdhiomr2_inflection_analytical_package" in command.dy_command
    assert "hiomr2_inflection_package_mode=analytical" in command.dy_command
    assert "seqone_delivery_batch_id=$ANALYSIS_ID" in command.dy_command
    assert "HIOMR2_SEQONE_V2_CONFIG_FILE" not in command.dy_command
    assert "SEQONE_DELIVERY_BATCH_ID" not in command.dy_command
    assert "--configfile config/hg002_bjuice_5x5x_hiomr2.yaml" in command.dy_command
    assert "use_fq_data_starting_hrs" not in command.dy_command
    assert "use_fq_data_up_to_hrs" not in command.dy_command
    assert "all supplied FASTQs are used" in command.description
    assert "full-coverage inputs must not be substituted" in command.description.casefold()
    assert "schema-2.2 analytical Inflection package" in command.description
    assert profile.source_s3_uri_template.endswith("/bjuice_preval_2026/HG002/")
    assert any("f35e79a5601271f6" in note for note in profile.source_notes)


def test_inflection_v09_slim_clone_changes_only_the_input_contract() -> None:
    catalog = load_repository_catalog(SOURCE_CATALOG)
    full = catalog.get_command("inflection-bjuice-product-v0.9")
    slim = catalog.get_command("inflection-bjuice-product-v0.9-slim-5x5x-validation")

    assert slim.type == "test"
    assert slim.validation_pending is True
    assert slim.validated_version == "unvalidated"
    assert slim.test_data_profile == "hg002_bjuice_verified_5x5x_fastq"
    assert slim.manifest_dir_template == "examples/staging/hg002_bjuice_verified_5x5x_fastq"
    assert slim.requires_run_mount is False
    assert full.test_data_profile == "hg002_bjuice_v2_full_preval_run_mounts"
    assert full.requires_run_mount is True

    assert slim.targets == full.targets
    assert slim.dy_command == full.dy_command
    assert slim.dryrun_dy_command == full.dryrun_dy_command
    assert slim.runtime_parameters == full.runtime_parameters
    assert slim.git_tag == full.git_tag == "16.0.5"
    assert slim.return_results is False
    assert "schema" in slim.description
    assert "identical calls" in slim.description


def test_hg002_bjuice_fixture_topology_and_input_identities() -> None:
    manifest = load_manifest_set(FIXTURE_ROOT)
    assert {name: len(rows) for name, rows in manifest.rows.items()} == {
        "specimens.tsv": 1,
        "samples.tsv": 1,
        "libraries.tsv": 1,
        "sequencing_inputs.tsv": 2,
        "analysis_units.tsv": 1,
        "analysis_unit_inputs.tsv": 2,
    }

    inputs = {row["MODALITY"]: row for row in manifest.rows["sequencing_inputs.tsv"]}
    assert inputs["sr"]["ILMN_R1_PATH"].endswith("/illumina/HG002_BJUICEPREVAL_ILMN_5x_R1.fastq.gz")
    assert inputs["sr"]["ILMN_R2_PATH"].endswith("/illumina/HG002_BJUICEPREVAL_ILMN_5x_R2.fastq.gz")
    assert inputs["lr"]["ONT_R1_PATH"].endswith("/ont/HG002_BJUICEPREVAL_ONT_5x.fastq.gz")

    identity = json.loads((FIXTURE_ROOT / "input_identity.json").read_text())
    by_role = {item["role"]: item for item in identity["inputs"]}
    assert by_role["illumina_r1"]["bytes"] == 3_899_321_181
    assert by_role["illumina_r2"]["bytes"] == 4_000_405_121
    assert by_role["ont"]["bytes"] == 15_086_588_357
    assert by_role["ont"]["sha256"] == (
        "f35e79a5601271f6503455a952cc04892f452b078ad45941cbf27ae77f4ed45b"
    )
    assert by_role["ont"]["uncompressed_fastq_sha256"] == (
        "7441b3018d02fe6c0c318bf2904ae7d7bb5c08093ddaa3bbd7e876b3e4ec8be0"
    )
    assert by_role["ont"]["read_count"] == 1_963_980
    assert by_role["ont"]["sequenced_bases"] == 14_805_689_859
    assert by_role["ont"]["measured_depth"] == 4.794169766
    assert by_role["ont"]["sampling"] == {
        "method": "deterministic_source_prefix_by_estimated_read_count",
        "source_read_count": 7_759_331,
        "source_measured_depth": 19.7617,
        "target_read_count": 1_963_980,
        "tool": "seqkit",
        "version": "2.13.0",
        "package_sha256": ("538ff4ab33819598e45939fe36ea7f4505afba62e90a7cbd95c6f63493aee6d4"),
        "compression_tool": "pigz 2.6",
        "compression_level": 1,
        "rebuild_receipt_schema": "lsmc.hg002_bjuice_ont_5x_prefix96/1.0",
    }
