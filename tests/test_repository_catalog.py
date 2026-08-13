from __future__ import annotations

import json
import shlex
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from daylily_ec.cli import app
from daylily_ec.repositories import load_repository_catalog

runner = CliRunner()


DAYOA_BLESSED_TAG = "14.0.9"
PRODUCTION_DAYOA_TAG = "14.0.9"
PREVIOUS_PRODUCTION_DAYOA_TAG = "13.4.31"
SOLO_KITCHEN_SINK_DAYOA_TAG = PRODUCTION_DAYOA_TAG
DRAGEN_DAYOA_REF = DAYOA_BLESSED_TAG
REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "config" / "daylily_pipeline_command_catalog.yaml"
PACKAGED_CATALOG_PATH = (
    REPO_ROOT
    / "daylily_ec"
    / "resources"
    / "payload"
    / "config"
    / "daylily_pipeline_command_catalog.yaml"
)
OLD_CATALOG_LINK = REPO_ROOT / "config" / "daylily_available_repositories.yaml"
OLD_PACKAGED_CATALOG_LINK = (
    REPO_ROOT
    / "daylily_ec"
    / "resources"
    / "payload"
    / "config"
    / "daylily_available_repositories.yaml"
)
UNVALIDATED_COMMAND_IDS = {
    "simple-test",
    "illumina_run_qc_bclconvert",
    "all_metagenomic_pipelines",
    "ultima_snv_alignstats_kitchensink",
    "ont_snv_alignstats_kitchensink",
    "hybrid_ilmn_ont_hiomr",
    "hybrid_ilmn_ont_hiomr_kitchensink",
    "hiomr2",
    "hybrid_ilmn_ont_hiomr2_kitchensink_inflection_analytical",
    "package_inflection_hybrid_data",
    "betelgeuser_hiomr_prod_v1",
    "inflection-bjuice-product-v0.2",
    "hiomr2_slim_kitchensink_mega",
    "sentdhiomr2_nicu_fastq_recoverability-hg002-z-hg002-analysis-unit-5x5x",
    "illumina_pangenome_snv",
    "illumina_dragen_pangenome_snv_concordance",
    "ultima_pangenome_snv",
}
SIMPLE_TEST_DY_COMMAND = "source dyoainit; dy-a local hg38; dy-r -p -k -j 1 help"


def _minimal_run_catalog_yaml(
    *,
    profile_id: str = "illumina_run_directory",
    profile_mode: str = "run_dra_required",
    run_context_columns: str = "[RUNID, SOURCE_S3_URI, MOUNT_ID]",
) -> str:
    source_fsx_prefix = (
        "/fsx/run_dir_mounts/{MOUNT_ID}/"
        if profile_mode == "run_dra_required"
        else "/fsx/references/example-runs/run1/"
    )
    run_dra_columns = (
        "    run_context_source_s3_column: SOURCE_S3_URI\n"
        "    run_context_mount_id_column: MOUNT_ID\n"
        if profile_mode == "run_dra_required"
        else ""
    )
    return f"""
command_catalog_version: 2
default_repository: repo
input_contracts:
  run_context:
    description: "Run context."
    source_table:
      path: config/runs.tsv
      required_columns: {run_context_columns}
test_data_locations:
  - location_id: default_run_data
    description: "Run data."
    mount_path: /fsx/control_data
    data_root: /fsx/control_data/run_data
    s3_uri: s3://example-control/run_data/
    applies_to_command_classes: [run_analysis]
test_data_profiles:
  {profile_id}:
    description: "Run profile."
    source_mount_mode: {profile_mode}
    source_s3_uri_template: s3://example-runs/run1/
    source_fsx_prefix: {source_fsx_prefix}
{run_dra_columns.rstrip()}
    locations: [default_run_data]
repositories:
  repo:
    clone_transport: https
    auth_mode: none
    https_url: https://example.invalid/repo.git
    default_ref: main
    relative_path: repo
    analysis_commands:
      - command_id: run_cmd
        type: prod
        validated_version: main
        test_data_profile: {profile_id}
        display_name: Run Command
        datasource: Illumina
        launcher: workflow_launch
        command_class: run_analysis
        input_contract: run_context
        requires_staging: false
        requires_run_mount: true
        targets: [produce_illumina_run_qc]
        genome: hg38
        jobs: 1
        aligners: []
        dedupers: []
        snv_callers: []
        sv_callers: []
        dy_command: bin/day_run produce_illumina_run_qc
        dryrun_dy_command: bin/day_run produce_illumina_run_qc -n
        compatible_platforms: [ILMN]
        compatible_cluster_types: [daywgs]
        compatible_data_modes: [run_directory_mount]
"""


def test_repository_catalog_loads_initial_blessed_command() -> None:
    catalog = load_repository_catalog(CATALOG_PATH)
    command = catalog.get_command("illumina_snv_alignstats")

    assert catalog.command_catalog_version == 6
    released_build = catalog.commands_for_dyec_build("16.1.81")
    assert {command.command_id for command in released_build} == {
        "illumina_hg002_kitchensink_multiqc",
        "ultima_snv_alignstats_kitchensink",
        "ont_snv_alignstats_kitchensink",
        "complete_genomics_cg_snv_concordance",
        "illumina_run_qc",
        "ont_run_qc",
        "ultima_run_qc",
        "inflection-bjuice-product-v0.2",
        "sentdhiomr2_nicu_fastq_recoverability-hg002-z-hg002-analysis-unit-5x5x",
    }
    assert {command.type for command in released_build} == {"prod", "research"}
    assert sum(command.type == "prod" for command in released_build) == 8
    assert {command.git_tag for command in released_build} == {"13.4.30"}
    assert {command.repository for command in released_build} == {"daylily-omics-analysis"}
    historical_cg = catalog.get_command_for_dyec_build(
        "complete_genomics_cg_snv_concordance", "16.1.81"
    )
    assert "produce_multiqc_all" not in historical_cg.targets
    previous_build = catalog.commands_for_dyec_build("16.1.82")
    assert {command.git_tag for command in previous_build} == {PREVIOUS_PRODUCTION_DAYOA_TAG}
    current_build = catalog.commands_for_dyec_build()
    assert {command.command_id for command in current_build} == {
        command.command_id for command in catalog.commands()
    }
    assert len(current_build) == 29
    assert {command.git_tag for command in current_build} == {PRODUCTION_DAYOA_TAG}
    assert {command.repository for command in current_build} == {"daylily-omics-analysis"}
    older_release = catalog.commands_for_dyec_build("16.1.85")
    assert {command.git_tag for command in older_release} == {"13.4.33"}
    previous_release = catalog.commands_for_dyec_build("16.1.86")
    assert {command.git_tag for command in previous_release} == {"13.4.34"}
    prior_major_release = catalog.commands_for_dyec_build("17.0.0")
    assert {command.git_tag for command in prior_major_release} == {"14.0.0"}
    previous_major_patch = catalog.commands_for_dyec_build("17.0.1")
    assert {command.git_tag for command in previous_major_patch} == {"14.0.2"}
    previous_catalog_patch = catalog.commands_for_dyec_build("17.0.2")
    assert {command.git_tag for command in previous_catalog_patch} == {"14.0.3"}
    previous_compression_patch = catalog.commands_for_dyec_build("17.0.3")
    assert {command.git_tag for command in previous_compression_patch} == {"14.0.4"}
    previous_jasmine_patch = catalog.commands_for_dyec_build("17.0.4")
    assert {command.git_tag for command in previous_jasmine_patch} == {"14.0.6"}
    previous_fastqc_patch = catalog.commands_for_dyec_build("17.0.5")
    assert {command.git_tag for command in previous_fastqc_patch} == {"14.0.7"}
    previous_fastqc_java_patch = catalog.commands_for_dyec_build("17.0.6")
    assert {command.git_tag for command in previous_fastqc_java_patch} == {"14.0.8"}
    released_build = catalog.commands_for_dyec_build("17.0.7")
    assert [command.model_dump() for command in released_build] == [
        command.model_dump() for command in current_build
    ]
    current_cg = catalog.get_command_for_dyec_build("complete_genomics_cg_snv_concordance")
    assert "produce_multiqc_all" in current_cg.targets
    assert catalog.result_export is not None
    assert any(
        "DYEC must wait for a successful controller exit" in step
        for step in catalog.result_export.post_controller_protocol
    )
    assert "--mode export" in catalog.result_export.manual_visit_command
    assert "--intent" in catalog.result_export.manual_visit_command
    assert "dyec export" in catalog.result_export.manual_export_command
    assert '"$ANALYSIS_ROOT"' in catalog.result_export.manual_export_command
    assert "--delete-data-in-file-system" not in catalog.result_export.manual_export_command
    assert catalog.result_export.preserves_fsx_by_default is True
    manifest_contract = catalog.input_contracts["sample_manifest"]
    assert [location.location_id for location in catalog.test_data_locations] == [
        "default_reference_reads_slim",
        "default_control_reads_slim",
        "default_control_run_data",
    ]
    assert catalog.test_data_locations[0].mount_path == "/fsx/data"
    assert catalog.test_data_locations[0].data_root == "/fsx/data/genomic_data/organism_reads_slim"
    assert "default /fsx/data path" in catalog.test_data_locations[0].description
    default_reads = catalog.test_data_profiles["default_reads_slim"]
    assert default_reads.source_mount_mode == "default_mounted"
    assert (
        default_reads.source_s3_uri_template
        == "s3://lsmc-dayoa-references-usw2/genomic_data/organism_reads_slim/"
    )
    assert default_reads.source_fsx_prefix == ("/fsx/data/genomic_data/organism_reads_slim/")
    assert default_reads.run_context_source_s3_column == ""
    assert default_reads.run_context_mount_id_column == ""
    assert manifest_contract.source_table is not None
    assert manifest_contract.source_table.path == "analysis_samples.tsv"
    assert manifest_contract.source_table.required_columns == [
        "RUN_ID",
        "SAMPLE_ID",
        "EXPERIMENTID",
        "SAMPLE_TYPE",
        "LIB_PREP",
        "SEQ_VENDOR",
        "SEQ_PLATFORM",
        "LANE",
        "SEQBC_ID",
    ]
    assert manifest_contract.generated_tables["samples_tsv"].path == "config/samples.tsv"
    assert manifest_contract.generated_tables["samples_tsv"].required_columns == [
        "SAMPLEID",
        "SAMPLESOURCE",
        "SAMPLECLASS",
        "BIOLOGICAL_SEX",
        "CONCORDANCE_CONTROL_PATH",
        "IS_POSITIVE_CONTROL",
        "IS_NEGATIVE_CONTROL",
        "SAMPLE_TYPE",
        "TUM_NRM_SAMPLEID_MATCH",
        "EXTERNAL_SAMPLE_ID",
        "N_X",
        "N_Y",
        "TRUTH_DATA_DIR",
    ]
    assert manifest_contract.generated_tables["units_tsv"].path == "config/units.tsv"
    assert "RUNID" in manifest_contract.generated_tables["units_tsv"].required_columns
    assert "SAMPLEID" in manifest_contract.generated_tables["units_tsv"].required_columns
    assert "ONT_CRAM" in manifest_contract.generated_tables["units_tsv"].required_columns
    assert command.repository == "daylily-omics-analysis"
    assert command.command_class == "sample_analysis"
    assert command.input_contract == "sample_manifest"
    assert command.requires_staging is True
    assert command.requires_run_mount is False
    assert command.runtime_parameters == {}
    assert command.input_requirements.required_source_columns == [
        "ILMN_R1_FQ",
        "ILMN_R2_FQ",
    ]
    assert command.datasource == "Illumina"
    assert command.targets == [
        "produce_sent_align",
        "produce_dmd_dedup_cram",
        "produce_sentd_snv_vcf",
        "produce_snv_concordances",
        "produce_alignstats",
    ]
    assert command.aligners == ["sent"]
    assert command.dedupers == ["dmd"]
    assert command.snv_callers == ["sentd"]
    assert command.sv_callers == []
    assert command.git_tag == DAYOA_BLESSED_TAG
    assert len(command.validation_runs) == 1
    validation_run = command.validation_runs[0]
    assert validation_run.run_id == "tstver411b_dayoa_catalog_recipe_validation"
    assert validation_run.dayec_tag == "4.1.3"
    assert validation_run.dayec_commit == "012a3b5b30d2e69a07aa80dd4c224ad1ee26d3a4"
    assert validation_run.dayoa_tag == "1.0.21"
    assert validation_run.dayoa_commit == "c2ffe93f246ff19c346f0a99e04fddc9e2712ff3"
    assert validation_run.status == "success"
    assert validation_run.dryrun_status == "success"
    assert validation_run.live_status == "success"
    assert command.compatible_platforms == ["ILMN"]
    assert command.compatible_cluster_types == ["daywgs"]
    assert command.compatible_data_modes == ["ilmn_solo"]
    assert "bin/day_run" in command.dy_command
    assert command.dryrun_dy_command.endswith(" -n")
    assert command.artifact_registration is None

    multiqc_command = catalog.get_command("illumina_snv_alignstats_relatedness_vep_multiqc")
    assert multiqc_command.artifact_registration is not None
    assert multiqc_command.artifact_registration.enabled is True
    assert (
        multiqc_command.artifact_registration.evidence_manifest_path
        == "results/day/{genome}/reports/dayoa_evidence_manifest.json"
    )
    assert multiqc_command.artifact_registration.manifest_source == "dayoa_manifest"
    assert "multiqc_html" in multiqc_command.artifact_registration.include_classifications
    assert "alignment_cram" in multiqc_command.artifact_registration.include_classifications
    assert "samples_manifest" in multiqc_command.artifact_registration.include_classifications
    assert "units_manifest" in multiqc_command.artifact_registration.include_classifications
    assert "config/samples.tsv" in multiqc_command.artifact_registration.include_paths
    assert "config/units.tsv" in multiqc_command.artifact_registration.include_paths
    assert multiqc_command.artifact_registration.multiqc_reports[0].report_kind == "final"
    assert multiqc_command.artifact_registration.identity.analysis_euid == "{analysis_id}"

    plain_run_qc_command = catalog.get_command("illumina_run_qc")
    assert plain_run_qc_command.jobs == 20
    assert plain_run_qc_command.runtime_parameters == {
        "run_context_file": "config/runs.tsv",
        "run_context_only": "true",
    }
    assert "bclconvert" not in plain_run_qc_command.dy_command.lower()
    assert plain_run_qc_command.artifact_registration is not None
    assert plain_run_qc_command.artifact_registration.manifest_source == "s3_inventory"
    assert plain_run_qc_command.artifact_registration.allow_s3_body_sha256 is True
    assert plain_run_qc_command.artifact_registration.s3_body_sha256_max_bytes == 50_000_000
    assert {
        report.report_kind for report in plain_run_qc_command.artifact_registration.multiqc_reports
    } == {"run_qc_illumina"}
    assert "config/samples.tsv" not in plain_run_qc_command.artifact_registration.include_paths
    assert "config/units.tsv" not in plain_run_qc_command.artifact_registration.include_paths

    run_qc_command = catalog.get_command("illumina_run_qc_bclconvert")
    assert run_qc_command.artifact_registration is not None
    assert run_qc_command.artifact_registration.manifest_source == "s3_inventory"
    assert {
        report.report_kind for report in run_qc_command.artifact_registration.multiqc_reports
    } == {
        "bclconvert",
        "run_qc_illumina",
    }

    launch_argv = command.launch_argv(
        analysis_id="run-1",
        executing_entity="johnm",
        cluster="cluster-a",
    )
    assert "--dy-command" in launch_argv
    assert "--analysis-id" in launch_argv
    assert "run-1" in launch_argv
    assert "--executing-entity" in launch_argv
    assert "johnm" in launch_argv
    assert "--git-tag" in launch_argv
    assert DAYOA_BLESSED_TAG in launch_argv

    export_argv = command.launch_argv(
        analysis_id="run-1",
        executing_entity="johnm",
        export_destination_s3_uri="s3://bucket/derived/johnm/run-1/",
        export_trigger="all",
        delete_on_export_success=True,
        replace_existing_analysis_dir=True,
    )
    assert "--export-destination-s3-uri" in export_argv
    assert "s3://bucket/derived/johnm/run-1/" in export_argv
    assert "--export-trigger" in export_argv
    assert "all" in export_argv
    assert "--delete-on-export-success" in export_argv
    assert "--replace-existing-analysis-dir" in export_argv

    with pytest.raises(TypeError):
        multiqc_command.launch_argv(
            analysis_id="run-1",
            executing_entity="johnm",
            export_destination_s3_uri="s3://bucket/derived/johnm/run-1/",
            export_trigger="on-success",
            artifact_registration_command_id=multiqc_command.command_id,
            dewey_url="https://dewey.example",
            dewey_token_env="DEWEY_TOKEN",
        )

    with pytest.raises(ValueError, match="export_trigger"):
        command.launch_argv(
            analysis_id="run-1",
            executing_entity="johnm",
            export_destination_s3_uri="s3://bucket/derived/johnm/run-1/",
        )

    with pytest.raises(ValueError, match="delete_on_export_success"):
        command.launch_argv(
            analysis_id="run-1",
            executing_entity="johnm",
            delete_on_export_success=True,
        )


def test_catalog_cli_uses_current_unless_numeric_snapshot_is_requested() -> None:
    current_result = runner.invoke(
        app,
        ["--json", "catalog", "list", "--config", str(CATALOG_PATH)],
    )
    released_result = runner.invoke(
        app,
        [
            "--json",
            "catalog",
            "list",
            "--config",
            str(CATALOG_PATH),
            "--dyec-version",
            "16.1.82",
        ],
    )

    assert current_result.exit_code == 0, current_result.output
    assert released_result.exit_code == 0, released_result.output
    current_payload = json.loads(current_result.stdout)
    released_payload = json.loads(released_result.stdout)
    assert current_payload["dyec_version"] == "current"
    assert {command["git_tag"] for command in current_payload["commands"]} == {
        PRODUCTION_DAYOA_TAG
    }
    assert released_payload["dyec_version"] == "16.1.82"
    assert {command["git_tag"] for command in released_payload["commands"]} == {"13.4.31"}


def test_hiomr2_catalog_selects_native_tiddit_and_paired_library_summary() -> None:
    catalog = load_repository_catalog(CATALOG_PATH)
    command = catalog.get_command("hiomr2")

    assert command.snv_callers == ["sentdhiomr2"]
    assert command.sv_callers == ["tiddit"]
    assert command.targets.count("produce_sentdhiomr2_tiddit_sv_vcf") == 1
    assert 'sv_callers=["tiddit"]' in command.dy_command
    assert " produce_tiddit_sv_vcf " not in command.dy_command
    for expected in (
        '"aligner":"sentdhiomr2_sr","deduper":"smd"',
        '"aligner":"sentdhiomr2_lr","deduper":"na"',
        '"contamination_method":"site_mix"',
    ):
        assert expected in command.dy_command
        assert expected in command.dryrun_dy_command

    argv = shlex.split(command.dy_command)
    multiqc_arg = next(arg for arg in argv if arg.startswith("multiqc_qc="))
    multiqc_qc = json.loads(multiqc_arg.split("=", 1)[1])
    assert multiqc_qc["library_summary"] == {
        "primary_alignments": {
            "sr": {"aligner": "sentdhiomr2_sr", "deduper": "smd"},
            "ont": {"aligner": "sentdhiomr2_lr", "deduper": "na"},
        },
        "contamination_method": "site_mix",
    }


def test_repository_catalog_commands_have_run_metadata() -> None:
    catalog = load_repository_catalog(CATALOG_PATH)

    production_ids = {
        command.command_id for command in catalog.commands() if command.type == "prod"
    }
    assert production_ids == {
        "illumina_run_qc",
        "ont_run_qc",
        "ultima_run_qc",
        "illumina_hg002_kitchensink_multiqc",
        "ont_snv_alignstats_kitchensink",
        "ultima_snv_alignstats_kitchensink",
        "complete_genomics_cg_snv_concordance",
        "inflection-bjuice-product-v0.2",
        "hiomr2_slim_kitchensink_mega",
    }
    recoverability = catalog.get_command(
        "sentdhiomr2_nicu_fastq_recoverability-hg002-z-hg002-analysis-unit-5x5x"
    )
    assert recoverability.type == "research"
    assert "produce_sentdhiomr2_nicu_fastq_recoverability" in recoverability.dy_command
    for command_id in production_ids:
        command = catalog.get_command(command_id)
        assert "nicu_fastq_recoverability" not in command.dy_command
    hiomr2_mega_ids = {
        "inflection-bjuice-product-v0.2",
        "hiomr2_slim_kitchensink_mega",
    }
    for command_id in hiomr2_mega_ids:
        command = catalog.get_command(command_id)
        assert "produce_sentdhiomr2_slim_kitchensink_mega" in command.dy_command
        assert "produce_sentdhiomr2_nicu_research" not in command.dy_command
    for command_id in production_ids - hiomr2_mega_ids:
        command = catalog.get_command(command_id)
        assert "produce_sentdhiomr2_nicu_research" not in command.dy_command

    command_ids = {command.command_id for command in catalog.commands()}
    assert {
        "simple-test",
        "illumina_snv_alignstats",
        "illumina_snv_alignstats_relatedness_vep_multiqc",
        "all_metagenomic_pipelines",
        "illumina_hg002_kitchensink_multiqc",
        "ultima_snv_alignstats",
        "ultima_snv_alignstats_kitchensink",
        "complete_genomics_cg_snv_concordance",
        "ont_snv_alignstats",
        "ont_snv_alignstats_kitchensink",
        "pacbio_snv_alignstats",
        "roche_snv_alignstats",
        "hybrid_ilmn_ont_hiomr",
        "hybrid_ilmn_ont_hiomr_kitchensink",
        "illumina_pangenome_snv",
        "illumina_dragen_pangenome_snv_concordance",
        "ultima_pangenome_snv",
        "complete_genomics_cg_snv_concordance",
    } <= command_ids

    for command in catalog.commands():
        if not command.validation_runs:
            assert command.command_id in UNVALIDATED_COMMAND_IDS
            continue
        expected_validation_runs = 2 if command.command_id == "ultima_run_qc" else 1
        assert len(command.validation_runs) == expected_validation_runs
        validation_run = command.validation_runs[0]
        if validation_run.run_id == "dayoa_2017_hg002_kitchensink_j200_readhapsfix2_151101":
            assert command.command_id == "illumina_hg002_kitchensink_multiqc"
            assert validation_run.cluster == "goodole3"
            assert validation_run.region == "us-west-2"
            assert validation_run.dayec_tag == "5.0.20-dev"
            assert validation_run.dayoa_tag == "2.0.19"
            assert validation_run.dayoa_commit == "b377b8b557306fbb6832763a39661ce36d6f4bbd"
            assert validation_run.status == "success"
            assert validation_run.dryrun_status == "success"
            assert validation_run.live_status == "success"
            assert "produce_metagenomics" in validation_run.tested_command
            assert "produce_multiqc_all" in validation_run.tested_command
            assert command.dy_command.startswith("bin/day_run ")
            assert command.dryrun_dy_command.startswith("bin/day_run ")
            assert command.dryrun_dy_command.endswith(" -n")
            assert command.compatible_platforms
            assert command.compatible_cluster_types == ["daywgs"]
            assert command.compatible_data_modes
            assert command.git_tag == SOLO_KITCHEN_SINK_DAYOA_TAG
            assert (
                command.input_requirements.required_source_columns
                or command.input_requirements.accepted_source_column_sets
            )
            continue
        if validation_run.run_id == "preval_ilmn_run_qc_rnd_final_20260727T053100Z":
            assert command.command_id == "illumina_run_qc"
            assert validation_run.cluster == "preval-hiomr2"
            assert validation_run.region == "us-west-2"
            assert validation_run.dayec_tag == "15.0.0"
            assert validation_run.dayoa_tag == "13.0.53"
            assert validation_run.status == "success"
            assert validation_run.dryrun_status == "success"
            assert validation_run.live_status == "success"
            assert validation_run.live_analysis_id == validation_run.run_id
            assert "run_context_only=true" in validation_run.tested_command
            assert "bclconvert" not in validation_run.tested_command.lower()
            continue
        assert validation_run.run_id == "tstver411b_dayoa_catalog_recipe_validation"
        assert validation_run.report_path == "docs/tstver411b_command_catalog_test_results.md"
        assert (
            validation_run.ledger_path
            == "docs/plans/20260525T063158Z_tstver411b_dayoa_catalog_recipe_validation_ledger.md"
        )
        assert validation_run.cluster == "tstVer4-1-1b"
        assert validation_run.region == "us-west-2"
        assert validation_run.region_az == "us-west-2d"
        assert validation_run.dayec_tag == "4.1.3"
        assert validation_run.dayoa_tag == "1.0.21"
        assert validation_run.dayoa_commit == "c2ffe93f246ff19c346f0a99e04fddc9e2712ff3"
        assert validation_run.tested_command.startswith("bin/day_run ")
        assert validation_run.status in {"success", "failed", "blocked"}
        assert validation_run.dryrun_status in {"success", "failed", "blocked"}
        assert validation_run.live_status in {"success", "failed", "blocked", "not_run"}
        if command.command_class != "sample_analysis":
            continue
        assert command.dy_command.startswith("bin/day_run ")
        assert command.dryrun_dy_command.startswith("bin/day_run ")
        assert command.dryrun_dy_command.endswith(" -n")
        assert command.compatible_platforms
        assert command.compatible_cluster_types == ["daywgs"]
        assert command.compatible_data_modes
        expected_tag = (
            SOLO_KITCHEN_SINK_DAYOA_TAG
            if command.command_id == "complete_genomics_cg_snv_concordance"
            else DAYOA_BLESSED_TAG
        )
        assert command.git_tag == expected_tag
        assert (
            command.input_requirements.required_source_columns
            or command.input_requirements.accepted_source_column_sets
        )

    complete_genomics = catalog.get_command("complete_genomics_cg_snv_concordance")
    assert complete_genomics.type == "prod"
    assert complete_genomics.input_contract == "six_manifest"
    assert complete_genomics.sample_manifest_template == ""
    assert (
        complete_genomics.manifest_dir_template
        == "examples/staging/complete_genomics_solo_six_manifest_v1"
    )
    assert complete_genomics.staging_receipt_required is True
    assert complete_genomics.jobs == 333

    for command_id in (
        "illumina_hg002_kitchensink_multiqc",
        "ont_snv_alignstats_kitchensink",
        "ultima_snv_alignstats_kitchensink",
        "complete_genomics_cg_snv_concordance",
    ):
        command = catalog.get_command(command_id)
        assert command.validated_version == SOLO_KITCHEN_SINK_DAYOA_TAG
        assert command.git_tag == SOLO_KITCHEN_SINK_DAYOA_TAG
    assert complete_genomics.compatible_platforms == ["CG"]
    assert complete_genomics.compatible_cluster_types == ["daywgs"]
    assert complete_genomics.compatible_data_modes == ["complete_genomics_solo"]
    assert complete_genomics.aligners == ["sentcg"]
    assert complete_genomics.dedupers == ["dmd"]
    assert "produce_cgt7p_snv_vcf" in complete_genomics.dy_command
    assert "produce_sentcg_align" in complete_genomics.dy_command
    assert "produce_dmd_dedup_cram" in complete_genomics.dy_command
    assert "produce_multiqc_all" in complete_genomics.targets
    assert "produce_multiqc_all" in complete_genomics.dy_command
    assert "produce_multiqc_all" in complete_genomics.dryrun_dy_command
    assert "produce_smd_dedup_cram" not in complete_genomics.dy_command
    assert "aligners=['sentcg']" not in complete_genomics.dy_command
    assert " -j 333 -T 0 " in complete_genomics.dy_command
    assert " -k " not in complete_genomics.dy_command

    illumina_pangenome = catalog.get_command("illumina_pangenome_snv")
    assert illumina_pangenome.type == "dev"
    assert illumina_pangenome.git_tag == DAYOA_BLESSED_TAG
    assert illumina_pangenome.genome == "hg38"
    assert illumina_pangenome.targets == ["produce_sentpg_snv_vcf"]
    assert illumina_pangenome.snv_callers == ["sentpg"]
    assert illumina_pangenome.compatible_platforms == ["ILMN"]
    assert illumina_pangenome.compatible_cluster_types == ["daywgs"]
    assert illumina_pangenome.compatible_data_modes == ["ilmn_solo"]

    dragen_pangenome = catalog.get_command("illumina_dragen_pangenome_snv_concordance")
    assert dragen_pangenome.type == "dev"
    assert dragen_pangenome.git_tag == DRAGEN_DAYOA_REF
    assert dragen_pangenome.test_data_profile == "default_reads_slim"
    assert dragen_pangenome.genome == "hg38"
    assert dragen_pangenome.day_profile == "slurm_rhel"
    assert dragen_pangenome.default_activation is False
    assert dragen_pangenome.targets == [
        "produce_drgpg_snv_vcf",
        "produce_snv_concordances",
    ]
    assert dragen_pangenome.aligners == ["drbwa"]
    assert dragen_pangenome.dedupers == ["na"]
    assert dragen_pangenome.snv_callers == ["drgpg"]
    assert dragen_pangenome.compatible_platforms == ["ILMN"]
    assert dragen_pangenome.compatible_cluster_types == ["dragen"]
    assert dragen_pangenome.compatible_data_modes == ["ilmn_solo"]
    assert dragen_pangenome.input_requirements.required_source_columns == [
        "ILMN_R1_FQ",
        "ILMN_R2_FQ",
    ]
    assert dragen_pangenome.dy_command.startswith("source dyoainit;")
    assert "dy-a slurm_rhel hg38" in dragen_pangenome.dy_command
    assert "dy-r produce_drgpg_snv_vcf produce_snv_concordances" in dragen_pangenome.dy_command
    assert "produce_drgpg_snv_vcf" in dragen_pangenome.dy_command
    assert "produce_snv_concordances" in dragen_pangenome.dy_command
    assert 'aligners=["drbwa"]' in dragen_pangenome.dy_command
    assert 'dedupers=["na"]' in dragen_pangenome.dy_command
    assert 'snv_callers=["drgpg"]' in dragen_pangenome.dy_command

    ultima_pangenome = catalog.get_command("ultima_pangenome_snv")
    assert ultima_pangenome.type == "dev"
    assert ultima_pangenome.git_tag == DAYOA_BLESSED_TAG
    assert ultima_pangenome.genome == "hg38"
    assert ultima_pangenome.targets == ["produce_pangenome_ug_vcf"]
    assert ultima_pangenome.aligners == ["pangenome_ug"]
    assert ultima_pangenome.snv_callers == ["sentpg"]
    assert ultima_pangenome.compatible_platforms == ["ULTIMA"]

    bclconvert = catalog.get_command("illumina_bclconvert")
    assert bclconvert.type == "research"
    assert bclconvert.command_class == "run_analysis"
    assert bclconvert.requires_run_mount is True

    run_qc_bclconvert = catalog.get_command("illumina_run_qc_bclconvert")
    assert run_qc_bclconvert.type == "research"
    assert run_qc_bclconvert.command_class == "run_analysis"
    assert run_qc_bclconvert.requires_run_mount is True
    assert ultima_pangenome.compatible_cluster_types == ["daywgs"]
    assert ultima_pangenome.compatible_data_modes == ["ultima_solo"]

    hybrid_ilmn_ont = catalog.get_command("hybrid_ilmn_ont_hiomr")
    assert hybrid_ilmn_ont.sample_manifest_template == ""
    assert hybrid_ilmn_ont.manifest_dir_template == "examples/staging/hg003_hiomrs_1x_raw_fastq"
    assert hybrid_ilmn_ont.test_data_profile == "hg003_hiomrs_1x_raw_fastq"
    assert hybrid_ilmn_ont.aligners == ["sentmm2ont"]
    assert hybrid_ilmn_ont.dedupers == ["na"]
    assert hybrid_ilmn_ont.snv_callers == ["sentdhiomr"]
    assert hybrid_ilmn_ont.sv_callers == []
    assert hybrid_ilmn_ont.targets == [
        "produce_sentdhiomr_snv_vcf",
        "produce_sentdhiomr_sv",
        "produce_sentdhiomr_cnv",
        "produce_snv_concordances",
    ]
    assert hybrid_ilmn_ont.dy_command.startswith("dy-r produce_sentdhiomr_snv_vcf ")
    assert 'dedupers=["na"]' in hybrid_ilmn_ont.dy_command
    assert ["ILMN_R1_FQ", "ILMN_R2_FQ", "ONT_R1_FQ"] in (
        hybrid_ilmn_ont.input_requirements.accepted_source_column_sets
    )

    for command in catalog.commands():
        if command.command_class != "sample_analysis":
            continue
        assert not (set(command.dedupers) & {"dppl", "dppl_sent", "smd"})
        assert not (set(command.aligners) & {"sentdhiom", "sentdhuom"})
        assert "sentdhiom" not in set(command.snv_callers) - {"sentdhiomr"}
        assert "sentdhiom" not in set(command.sv_callers) - {"sentdhiomr"}
        assert "sentdhuom" not in set(command.snv_callers) - {"sentdhuomr"}
        assert "sentdhuom" not in set(command.sv_callers) - {"sentdhuomr"}
        assert "produce_sentdhiom_sv" not in command.dy_command
        assert "produce_sentdhiom_snv_vcf" not in command.dy_command
        assert "produce_sentdhuom_snv_vcf" not in command.dy_command

    vep_multiqc = catalog.get_command("illumina_snv_alignstats_relatedness_vep_multiqc")
    assert vep_multiqc.targets == [
        "produce_sent_align",
        "produce_dmd_dedup_cram",
        "produce_sentd_snv_vcf",
        "produce_alignstats",
        "produce_snv_concordances",
        "produce_relatedness",
        "produce_vep",
        "produce_multiqc_all",
    ]
    assert "multiqc_qc=" in vep_multiqc.dy_command
    assert "enable_tools" in vep_multiqc.dy_command

    illumina_kitchensink = catalog.get_command("illumina_hg002_kitchensink_multiqc")
    assert illumina_kitchensink.targets == [
        "produce_sent_align",
        "produce_dmd_dedup_cram",
        "produce_sentd_snv_vcf",
        "produce_alignstats",
        "produce_snv_concordances",
        "produce_relatedness",
        "produce_gatk_contam_estimate",
        "produce_site_mix_contam_estimate",
        "produce_vep",
        "produce_expansionhunter",
        "produce_htd_calls",
        "produce_metagenomics",
        "produce_multiqc_all",
        "results/day/hg38/reports/DAY_final_multiqc.html",
        "results/day/hg38/reports/dayoa_evidence_manifest.json",
    ]
    assert illumina_kitchensink.genome == "hg38"
    assert illumina_kitchensink.jobs == 333
    assert illumina_kitchensink.input_contract == "six_manifest"
    assert illumina_kitchensink.sample_manifest_template == ""
    assert illumina_kitchensink.manifest_dir_template == ""
    assert illumina_kitchensink.aligners == ["sent"]
    assert illumina_kitchensink.dedupers == ["dmd"]
    assert illumina_kitchensink.snv_callers == ["sentd"]
    assert illumina_kitchensink.sv_callers == []
    assert 'htd_callers=["cyrius"]' in illumina_kitchensink.dy_command
    assert "--rerun-triggers mtime" in illumina_kitchensink.dy_command
    assert " -j 333 -p -T 0 " in illumina_kitchensink.dy_command
    assert " -k " not in illumina_kitchensink.dy_command
    assert "produce_metagenomics" in illumina_kitchensink.dy_command
    assert "produce_multiqc_all" in illumina_kitchensink.dy_command
    assert "results/day/hg38/reports/DAY_final_multiqc.html" in illumina_kitchensink.dy_command
    assert (
        "results/day/hg38/reports/dayoa_evidence_manifest.json" in illumina_kitchensink.dy_command
    )
    assert "produce_global_contam_check" not in illumina_kitchensink.dy_command
    assert "contam_identity" not in illumina_kitchensink.dy_command

    metagenomics = catalog.get_command("all_metagenomic_pipelines")
    assert metagenomics.type == "research"
    assert metagenomics.targets == ["produce_metagenomics"]
    assert metagenomics.sample_manifest_template == (
        "examples/staging/ilmn_hg003_5x_solo/analysis_samples_manifest.tsv"
    )
    assert metagenomics.genome == "hg38"
    assert metagenomics.jobs == 100
    assert metagenomics.aligners == ["sent"]
    assert metagenomics.dedupers == ["dmd"]
    assert metagenomics.snv_callers == []
    assert metagenomics.sv_callers == []
    assert "produce_metagenomics" in metagenomics.dy_command
    assert 'multiqc_qc={"enable_tools":["metagenomics"]}' in metagenomics.dy_command

    ultima_kitchensink = catalog.get_command("ultima_snv_alignstats_kitchensink")
    assert ultima_kitchensink.validation_runs == []
    assert ultima_kitchensink.input_contract == "six_manifest"
    assert ultima_kitchensink.sample_manifest_template == ""
    assert ultima_kitchensink.manifest_dir_template == ""
    assert ultima_kitchensink.targets == [
        "produce_alignstats",
        "produce_na_dedup_cram",
        "produce_sentdug_snv_vcf",
        "produce_snv_concordances",
        "produce_relatedness",
        "produce_vep",
        "produce_metagenomics",
        "produce_multiqc_all",
    ]
    assert ultima_kitchensink.aligners == ["ug"]
    assert ultima_kitchensink.dedupers == ["na"]
    assert ultima_kitchensink.snv_callers == ["sentdug"]
    assert ultima_kitchensink.jobs == 333
    assert 'aligners=["ug"]' in ultima_kitchensink.dy_command
    assert " -j 333 -T 0 " in ultima_kitchensink.dy_command
    assert " -k " not in ultima_kitchensink.dy_command
    assert "produce_multiqc_all" in ultima_kitchensink.dy_command
    assert "multiqc_qc=" in ultima_kitchensink.dy_command
    assert "enable_tools" in ultima_kitchensink.dy_command
    assert "produce_metagenomics" in ultima_kitchensink.dy_command
    assert 'multiqc_qc={"enable_tools":["vep","metagenomics"]}' in (ultima_kitchensink.dy_command)

    ont = catalog.get_command("ont_snv_alignstats")
    assert ont.aligners == ["ont"]
    assert "produce_sentdont_snv_vcf" in ont.dy_command
    assert "produce_sentmm2ont_align" not in ont.dy_command
    assert "produce_na_dedup_cram" not in ont.dy_command
    assert ["ONT_CRAM", "ONT_CRAM_ALIGNER", "ONT_CRAM_SNV_CALLER"] in (
        ont.input_requirements.accepted_source_column_sets
    )

    ont_kitchensink = catalog.get_command("ont_snv_alignstats_kitchensink")
    assert ont_kitchensink.validation_runs == []
    assert ont_kitchensink.input_contract == "six_manifest"
    assert ont_kitchensink.sample_manifest_template == ""
    assert ont_kitchensink.manifest_dir_template == ""
    assert ont_kitchensink.targets == [
        "produce_alignstats",
        "produce_na_dedup_cram",
        "produce_sentdont_snv_vcf",
        "produce_snv_concordances",
        "produce_relatedness",
        "produce_vep",
        "produce_metagenomics",
        "produce_multiqc_all",
        "results/day/hg38/reports/DAY_final_multiqc.html",
        "results/day/hg38/reports/dayoa_evidence_manifest.json",
    ]
    assert ont_kitchensink.jobs == 333
    assert ont_kitchensink.aligners == ["ont"]
    assert ont_kitchensink.dedupers == ["na"]
    assert ont_kitchensink.snv_callers == ["sentdont"]
    assert "produce_sentmm2ont_align" not in ont_kitchensink.dy_command
    assert "produce_na_dedup_cram" in ont_kitchensink.dy_command
    assert "--rerun-triggers mtime" in ont_kitchensink.dy_command
    assert "--rerun-triggers mtime -n" in ont_kitchensink.dryrun_dy_command
    assert " -j 333 -T 0 " in ont_kitchensink.dy_command
    assert " -k " not in ont_kitchensink.dy_command
    assert 'aligners=["ont"]' in ont_kitchensink.dy_command
    assert "produce_multiqc_all" in ont_kitchensink.dy_command
    assert "results/day/hg38/reports/DAY_final_multiqc.html" in ont_kitchensink.dy_command
    assert "results/day/hg38/reports/dayoa_evidence_manifest.json" in ont_kitchensink.dy_command
    assert "multiqc_qc=" in ont_kitchensink.dy_command
    assert "produce_metagenomics" in ont_kitchensink.dy_command
    assert 'multiqc_qc={"enable_tools":["vep","metagenomics"]}' in (ont_kitchensink.dy_command)

    hybrid_kitchensink = catalog.get_command("hybrid_ilmn_ont_hiomr_kitchensink")
    assert hybrid_kitchensink.sample_manifest_template == ""
    assert hybrid_kitchensink.manifest_dir_template == "examples/staging/hg003_hiomrs_1x_raw_fastq"
    assert hybrid_kitchensink.test_data_profile == "hg003_hiomrs_1x_raw_fastq"
    assert hybrid_kitchensink.validation_runs == []
    assert hybrid_kitchensink.targets[:5] == [
        "produce_sentdhiomr_snv_vcf",
        "produce_sentdhiomr_sv",
        "produce_sentdhiomr_cnv",
        "produce_sentdhiomr_mito",
        "produce_sentdhiomr_segdup",
    ]
    assert "produce_tiddit_sv_vcf" in hybrid_kitchensink.targets
    assert "produce_smn12_orthogonal_calls" in hybrid_kitchensink.targets
    assert "produce_multiqc_all" in hybrid_kitchensink.targets
    assert hybrid_kitchensink.aligners == ["sentmm2ont"]
    assert hybrid_kitchensink.dedupers == ["na"]
    assert hybrid_kitchensink.snv_callers == ["sentdhiomr"]
    assert hybrid_kitchensink.sv_callers == ["tiddit"]
    assert hybrid_kitchensink.jobs == 500
    assert hybrid_kitchensink.keep_going is True
    assert hybrid_kitchensink.restart_times == 0
    assert hybrid_kitchensink.dy_command.startswith("dy-r produce_sentdhiomr_snv_vcf ")
    assert "produce_tiddit_sv_vcf" in hybrid_kitchensink.dy_command
    assert "produce_smn12_orthogonal_calls" in hybrid_kitchensink.dy_command
    assert "produce_multiqc_all" in hybrid_kitchensink.dy_command
    assert "produce_gatk_contam_estimate" in hybrid_kitchensink.dy_command
    assert "produce_site_mix_contam_estimate" in hybrid_kitchensink.dy_command
    assert 'dedupers=["na"]' in hybrid_kitchensink.dy_command
    assert 'aligners=["sentmm2ont"]' in hybrid_kitchensink.dy_command
    assert 'snv_callers=["sentdhiomr"]' in hybrid_kitchensink.dy_command
    assert 'sv_callers=["tiddit"]' in hybrid_kitchensink.dy_command
    assert 'htd_callers=["smn12"]' in hybrid_kitchensink.dy_command
    assert "multiqc_qc=" in hybrid_kitchensink.dy_command
    assert "produce_metagenomics" in hybrid_kitchensink.dy_command
    expected_flags = "-j 500 -p -k -T 0 --rerun-triggers mtime --rerun-incomplete"
    assert hybrid_kitchensink.dy_command.endswith(expected_flags)
    assert hybrid_kitchensink.dryrun_dy_command.endswith(f"{expected_flags} -n")
    for excluded in ("produce_hiomrs", "manta", "truvari", "dmd", "kraken", "sourmash"):
        assert excluded not in hybrid_kitchensink.dy_command.lower()
    assert ["ILMN_R1_FQ", "ILMN_R2_FQ", "ONT_R1_FQ"] in (
        hybrid_kitchensink.input_requirements.accepted_source_column_sets
    )

    # HIOMR2 kitchen-sink variants intentionally select only SMNCopyNumber.
    for command_id in (
        "hiomr2",
        "hybrid_ilmn_ont_hiomr2_kitchensink_inflection_analytical",
        "inflection-bjuice-product-v0.2",
        "hiomr2_slim_kitchensink_mega",
    ):
        hiomr2_kitchensink = catalog.get_command(command_id)
        for command in (
            hiomr2_kitchensink.dy_command,
            hiomr2_kitchensink.dryrun_dy_command,
        ):
            assert command.count("htd_callers=") == 1
            assert 'htd_callers=["smn12"]' in command
            for excluded_special_caller in (
                "gauchian",
                "cyrius",
                "smaca",
                "sma_finder",
                "hapsma",
                "parascopy",
            ):
                assert excluded_special_caller not in command

    # The two catalogued HIOMR2 + Inflection workflow tests intentionally
    # demonstrate a quick multi-chromosome range.  DayOA's numeric scope maps
    # 23=X, 24=Y, and 25=M/MT, so full production coverage is 1-25.
    hiomr2_test_scope = 'sentdhiomr2={"hg38_sentdhiomr2_chrms":"19-20"}'
    for command_id in (
        "hybrid_ilmn_ont_hiomr2_kitchensink_inflection_analytical",
        "inflection-bjuice-product-v0.2",
        "hiomr2_slim_kitchensink_mega",
    ):
        hiomr2_kitchensink = catalog.get_command(command_id)
        assert hiomr2_kitchensink.dy_command.count(hiomr2_test_scope) == 1
        assert hiomr2_kitchensink.dryrun_dy_command.count(hiomr2_test_scope) == 1
        assert "replace 19-20 with 1-25" in hiomr2_kitchensink.description
        assert "23=X, 24=Y, and 25=M/MT" in hiomr2_kitchensink.description

    package_inflection = catalog.get_command("package_inflection_hybrid_data")
    assert package_inflection.type == "dev"
    assert package_inflection.validated_version == DAYOA_BLESSED_TAG
    assert package_inflection.git_tag == DAYOA_BLESSED_TAG
    assert package_inflection.input_contract == "six_manifest"
    assert package_inflection.targets == ["produce_sentdhiomr2_inflection_seqone_v2"]
    assert package_inflection.jobs == 400
    assert package_inflection.keep_going is True
    assert package_inflection.restart_times == 0
    assert package_inflection.aligners == ["sentmm2ont"]
    assert package_inflection.dedupers == ["na"]
    assert package_inflection.snv_callers == ["sentdhiomr2"]
    assert package_inflection.sv_callers == []
    assert package_inflection.return_results is False
    assert package_inflection.dy_command.startswith(
        "DAY_CONTAINERIZED=true dy-r produce_sentdhiomr2_inflection_seqone_v2"
    )
    assert "HIOMR2_SEQONE_V2_CONFIG_FILE:?" in package_inflection.dy_command
    assert "hiomr2_inflection_package_mode=seqone_v2" in package_inflection.dy_command
    assert package_inflection.dryrun_dy_command == f"{package_inflection.dy_command} -n"
    assert "produce_hiomrs" not in package_inflection.targets
    assert ["ILMN_R1_FQ", "ILMN_R2_FQ", "ONT_R1_FQ"] in (
        package_inflection.input_requirements.accepted_source_column_sets
    )

    inflection_bjuice = catalog.get_command("inflection-bjuice-product-v0.2")
    hiomr2_slim = catalog.get_command("hiomr2_slim_kitchensink_mega")
    hiomr2_analytical = catalog.get_command(
        "hybrid_ilmn_ont_hiomr2_kitchensink_inflection_analytical"
    )
    assert inflection_bjuice.sample_manifest_template == ""
    assert inflection_bjuice.validation_runs == []
    assert inflection_bjuice.test_data_profile == "hg002_bjuice_verified_5x5x_fastq"
    assert (
        inflection_bjuice.manifest_dir_template
        == "examples/staging/hg002_bjuice_verified_5x5x_fastq"
    )
    bjuice_profile = catalog.test_data_profiles[inflection_bjuice.test_data_profile]
    assert bjuice_profile.source_s3_uri_template.endswith("/bjuice_preval_2026/HG002/")
    assert any("f35e79a5601271f6" in note for note in bjuice_profile.source_notes)
    assert (
        "full-coverage inputs must not be substituted" in inflection_bjuice.description.casefold()
    )
    assert inflection_bjuice.targets == [
        "produce_sentdhiomr2_slim_kitchensink_mega",
        "produce_sentdhiomr2_inflection_analytical_package",
    ]
    assert hiomr2_slim.targets == ["produce_sentdhiomr2_slim_kitchensink_mega"]
    assert hiomr2_slim.dy_command != inflection_bjuice.dy_command
    assert hiomr2_slim.dryrun_dy_command != inflection_bjuice.dryrun_dy_command
    assert hiomr2_slim.test_data_profile == inflection_bjuice.test_data_profile
    assert hiomr2_slim.git_tag == PRODUCTION_DAYOA_TAG
    assert "standalone NICU FASTQ recoverability producer is deliberately excluded" in (
        hiomr2_slim.description
    )
    assert inflection_bjuice.targets != hiomr2_analytical.targets
    assert inflection_bjuice.jobs == 333
    assert inflection_bjuice.restart_times == 1
    assert inflection_bjuice.aligners == ["sentmm2ont"]
    assert inflection_bjuice.dedupers == ["na"]
    assert inflection_bjuice.snv_callers == ["sentdhiomr2"]
    assert inflection_bjuice.sv_callers == []
    assert ["ILMN_R1_FQ", "ILMN_R2_FQ", "ONT_R1_FQ"] in (
        inflection_bjuice.input_requirements.accepted_source_column_sets
    )
    assert inflection_bjuice.dy_command != hiomr2_analytical.dy_command
    assert "produce_sentdhiomr2_slim_kitchensink_mega" in inflection_bjuice.dy_command
    assert "produce_sentdhiomr2_inflection_analytical_package" in (inflection_bjuice.dy_command)
    assert "produce_sentdhiomr2_inflection_analytical_package" not in (hiomr2_slim.dy_command)
    for unwanted in (
        "produce_sentdhiomr2_nicu_research",
        "produce_sentdhiomr2_jasmine_sharded_per_sample",
        "manta",
        "dysgu",
        "severus",
        "survivor",
        "octopusv",
        "sniffles1",
        "iris",
    ):
        assert unwanted not in inflection_bjuice.dy_command.casefold()
        assert unwanted not in hiomr2_slim.dy_command.casefold()
    assert "produce_sentdhiomr2_inflection_seqone_v2" not in inflection_bjuice.dy_command
    assert "produce_sentdhiomr2_segdup_smn12_multiqc" not in inflection_bjuice.dy_command
    assert "-j 333 -T 0 -p" in inflection_bjuice.dy_command
    assert " -k " not in inflection_bjuice.dy_command
    assert inflection_bjuice.runtime_parameters == {}
    assert "SEQONE_DELIVERY_BATCH_ID" not in inflection_bjuice.dy_command
    assert "HIOMR2_SEQONE_V2_CONFIG_FILE" not in inflection_bjuice.dy_command
    assert "--configfile config/hg002_bjuice_5x5x_hiomr2.yaml" in inflection_bjuice.dy_command
    assert "hiomr2_inflection_package_mode=analytical" in inflection_bjuice.dy_command
    assert "seqone_delivery_batch_id=$ANALYSIS_ID" in inflection_bjuice.dy_command
    assert inflection_bjuice.return_results is False
    assert hiomr2_analytical.return_results is False
    assert "use_fq_data_starting_hrs" not in inflection_bjuice.dy_command
    assert "use_fq_data_up_to_hrs" not in inflection_bjuice.dy_command
    assert "all supplied FASTQs are used" in inflection_bjuice.description
    assert "produce_inflection_delivery_set" not in inflection_bjuice.dy_command
    assert 'aligners=["sentmm2ont"]' in inflection_bjuice.dy_command
    assert 'dedupers=["na"]' in inflection_bjuice.dy_command
    assert 'snv_callers=["sentdhiomr2"]' in inflection_bjuice.dy_command
    assert " -j 333 -T 0 -p " in inflection_bjuice.dy_command
    assert inflection_bjuice.genome == "hg38"
    assert inflection_bjuice.dryrun_dy_command == f"{inflection_bjuice.dy_command} -n"
    inflection_launch_argv = inflection_bjuice.launch_argv(
        analysis_id="test-chr19and20",
        executing_entity="prod-cand-260809",
        manifest_dir="/tmp/hg002-bjuice-six-manifest",
        dry_run=True,
    )
    rendered_inflection_command = inflection_launch_argv[
        inflection_launch_argv.index("--dy-command") + 1
    ]
    assert "$ANALYSIS_ID" not in rendered_inflection_command
    assert "seqone_delivery_batch_id=test-chr19and20" in rendered_inflection_command
    current_set = catalog.dyec_builds["current"]
    alias = current_set.aliases["inflection-bjuice-product-v0.2"]
    assert alias.alias_of == "hiomr2_slim_kitchensink_mega"
    assert alias.extend is not None
    assert alias.replace is None
    assert alias.extend.targets == ["produce_sentdhiomr2_inflection_analytical_package"]
    assert [(item.key, item.value, item.environment) for item in alias.extend.config] == [
        ("hiomr2_inflection_package_mode", "analytical", None),
        ("seqone_delivery_batch_id", None, "ANALYSIS_ID"),
    ]
    with pytest.raises(KeyError):
        catalog.get_command("hiomr2_slim_kitchensink_mega_inflection_analytical")

    simple_test = catalog.get_command("simple-test")
    assert simple_test.command_class == "utility"
    assert simple_test.input_contract == "none"
    assert simple_test.requires_staging is False
    assert simple_test.requires_run_mount is False
    assert simple_test.targets == ["help"]
    assert simple_test.genome == "hg38"
    assert simple_test.jobs == 1
    assert simple_test.keep_going is True
    assert simple_test.restart_times == 1
    assert simple_test.dy_command == SIMPLE_TEST_DY_COMMAND
    assert simple_test.dryrun_dy_command == simple_test.dy_command
    simple_launch_argv = simple_test.launch_argv(
        analysis_id="simple-test",
        executing_entity="johnm",
    )
    assert "--dy-command" in simple_launch_argv
    simple_effective = simple_launch_argv[simple_launch_argv.index("--dy-command") + 1]
    assert simple_effective.startswith(simple_test.dy_command)
    assert "--produce-analysis-artifact-manifest true" in simple_effective
    assert "--produce-rulegraph true" in simple_effective
    assert "--produce-filegraph false" in simple_effective
    assert "--produce-dag false" in simple_effective
    assert "--no-input-staging" in simple_launch_argv
    assert "--no-default-activation" in simple_launch_argv
    assert "--bootstrap-test-config" in simple_launch_argv
    assert "--stage-dir" not in simple_launch_argv
    assert "--run-context-file" not in simple_launch_argv


def test_repository_catalog_run_analysis_commands_require_run_context() -> None:
    catalog = load_repository_catalog(CATALOG_PATH)

    command = catalog.get_command("illumina_run_qc")
    run_context_contract = catalog.input_contracts["run_context"]
    assert run_context_contract.source_table is not None
    assert run_context_contract.source_table.path == "config/runs.tsv"
    assert run_context_contract.source_table.required_columns == [
        "RUNID",
        "PLATFORM",
        "RUN_DIR",
        "SOURCE_S3_URI",
        "MOUNT_ID",
        "SAMPLE_SHEET",
        "BASECALLING_STATE",
        "RUN_STATUS",
        "OUTPUT_ROOT",
        "REGION",
        "PROFILE",
    ]
    assert command.command_class == "run_analysis"
    assert command.input_contract == "run_context"
    assert command.requires_staging is False
    assert command.requires_run_mount is True
    run_profile = catalog.test_data_profiles[command.test_data_profile]
    assert run_profile.source_mount_mode == "run_dra_required"
    assert run_profile.source_s3_uri_template == (
        "s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/"
        "20260514_LH01106_0009_B23TVLGLT4/"
    )
    assert run_profile.source_fsx_prefix == "/fsx/run_dir_mounts/{MOUNT_ID}/"
    assert run_profile.run_context_source_s3_column == "SOURCE_S3_URI"
    assert run_profile.run_context_mount_id_column == "MOUNT_ID"
    assert command.runtime_parameters == {
        "run_context_file": "config/runs.tsv",
        "run_context_only": "true",
    }
    assert command.input_requirements.required_run_context_values == {"PLATFORM": "ILMN"}
    assert command.targets == ["produce_illumina_run_qc"]
    assert command.compatible_platforms == ["ILMN"]
    assert command.compatible_cluster_types == ["daywgs"]

    with pytest.raises(ValueError, match="run_context_file is required"):
        command.launch_argv(analysis_id="run-qc", executing_entity="johnm")

    launch_argv = command.launch_argv(
        analysis_id="run-qc",
        executing_entity="johnm",
        run_context_file="config/runs.tsv",
        dry_run=True,
    )
    assert "--stage-dir" not in launch_argv
    assert "--run-context-file" in launch_argv
    assert launch_argv[launch_argv.index("--run-context-file") + 1] == "config/runs.tsv"
    assert "--dy-command" in launch_argv
    dy_command = launch_argv[launch_argv.index("--dy-command") + 1]
    assert "produce_illumina_run_qc" in dy_command
    assert "run_context_file=config/runs.tsv" in dy_command
    assert "run_context_only=true" in dy_command
    assert "samples_table=" not in dy_command
    assert "units_table=" not in dy_command
    assert "--config run_context_file=config/runs.tsv run_context_only=true" in dy_command
    assert "--produce-analysis-artifact-manifest true" in dy_command
    assert "--produce-rulegraph true" in dy_command

    combined = catalog.get_command("illumina_run_qc_bclconvert")
    assert combined.command_class == "run_analysis"
    assert combined.targets == ["produce_illumina_run_qc_and_bclconvert"]
    assert combined.runtime_parameters == {
        "run_context_file": "config/runs.tsv",
        "bootstrap_bclconvert": "true",
    }
    combined_argv = combined.launch_argv(
        analysis_id="run-qc-bclconvert",
        executing_entity="johnm",
        run_context_file="config/runs.tsv",
        dry_run=True,
    )
    combined_dy_command = combined_argv[combined_argv.index("--dy-command") + 1]
    assert "produce_illumina_run_qc_and_bclconvert" in combined_dy_command
    assert "bootstrap_bclconvert=true" in combined_dy_command
    assert "bclconvert/samples.tsv" not in combined_dy_command
    assert "bclconvert/units.tsv" not in combined_dy_command

    ont = catalog.get_command("ont_run_qc")
    assert ont.validated_version == PRODUCTION_DAYOA_TAG
    assert ont.git_tag == PRODUCTION_DAYOA_TAG
    assert ont.targets == ["produce_ont_run_qc_and_demux_multiqc"]
    assert ont.runtime_parameters == {
        "run_context_file": "config/runs.tsv",
        "run_context_only": "true",
    }
    ont_argv = ont.launch_argv(
        analysis_id="ont-run-qc",
        executing_entity="johnm",
        run_context_file="config/runs.tsv",
        dry_run=True,
    )
    ont_dy_command = ont_argv[ont_argv.index("--dy-command") + 1]
    assert "produce_ont_run_qc_and_demux_multiqc" in ont_dy_command
    assert "--produce-analysis-artifact-manifest true" in ont_dy_command
    assert "--produce-rulegraph true" in ont_dy_command
    assert ont.genome == "hg38"
    assert ont.jobs == 6
    assert "run_context_file=config/runs.tsv" in ont_dy_command
    assert "run_context_only=true" in ont_dy_command
    assert "samples_table=" not in ont_dy_command
    assert "units_table=" not in ont_dy_command

    ultima = catalog.get_command("ultima_run_qc")
    assert ultima.validated_version == PRODUCTION_DAYOA_TAG
    assert ultima.git_tag == PRODUCTION_DAYOA_TAG
    assert ultima.runtime_parameters == {
        "run_context_file": "config/runs.tsv",
        "run_context_only": "true",
    }
    ultima_argv = ultima.launch_argv(
        analysis_id="ultima-run-qc",
        executing_entity="johnm",
        run_context_file="config/runs.tsv",
        dry_run=True,
    )
    ultima_dy_command = ultima_argv[ultima_argv.index("--dy-command") + 1]
    assert "produce_ultima_run_qc" in ultima_dy_command
    assert "run_context_file=config/runs.tsv" in ultima_dy_command
    assert "run_context_only=true" in ultima_dy_command
    assert "samples_table=" not in ultima_dy_command
    assert "units_table=" not in ultima_dy_command
    assert ultima.validation_runs[-1].status == "success"
    assert ultima.validation_runs[-1].live_status == "success"

    ultima_profile = catalog.test_data_profiles["ultima_run_directory"]
    assert ultima_profile.run_context_values == {
        "METRICS_PATH": ".test_data/data/ultima_run_qc/ultima_demux_summary_mqc.tsv"
    }


def test_repository_catalog_rejects_run_analysis_without_run_dra_profile(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad-run-profile.yaml"
    path.write_text(
        _minimal_run_catalog_yaml(
            profile_id="default_reads_slim",
            profile_mode="default_mounted",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="run_analysis but test_data_profile"):
        load_repository_catalog(path)


def test_repository_catalog_rejects_run_dra_profile_without_mount_columns(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad-run-columns.yaml"
    path.write_text(
        _minimal_run_catalog_yaml(run_context_columns="[RUNID, SOURCE_S3_URI]"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing required column\\(s\\): MOUNT_ID"):
        load_repository_catalog(path)


def test_repository_catalog_v1_migrates_to_sample_analysis(tmp_path: Path) -> None:
    path = tmp_path / "v1.yaml"
    path.write_text(
        "command_catalog_version: 1\n"
        "default_repository: repo\n"
        "repositories:\n"
        "  repo:\n"
        "    https_url: https://example.invalid/repo.git\n"
        "    default_ref: main\n"
        "    relative_path: repo\n"
        "    analysis_commands:\n"
        "      - command_id: sample_cmd\n"
        "        display_name: Sample Command\n"
        "        datasource: Illumina\n"
        "        launcher: workflow_launch\n"
        "        targets: [produce_alignstats]\n"
        "        genome: hg38\n"
        "        jobs: 1\n"
        "        aligners: [sent]\n"
        "        dedupers: [dmd]\n"
        "        snv_callers: [sentd]\n"
        "        sv_callers: []\n"
        "        dy_command: bin/day_run produce_alignstats\n"
        "        dryrun_dy_command: bin/day_run produce_alignstats -n\n"
        "        compatible_platforms: [ILMN]\n"
        "        compatible_data_modes: [ilmn_solo]\n",
        encoding="utf-8",
    )

    command = load_repository_catalog(path).get_command("sample_cmd")
    assert command.command_class == "sample_analysis"
    assert command.input_contract == "sample_manifest"
    assert command.requires_staging is True
    assert command.requires_run_mount is False
    assert command.runtime_parameters == {}
    assert command.input_requirements.required_source_columns == []
    assert command.compatible_cluster_types == ["daywgs"]


def test_repository_catalog_v2_requires_command_class(tmp_path: Path) -> None:
    path = tmp_path / "v2.yaml"
    path.write_text(
        "command_catalog_version: 2\n"
        "default_repository: repo\n"
        "repositories:\n"
        "  repo:\n"
        "    clone_transport: https\n"
        "    auth_mode: none\n"
        "    https_url: https://example.invalid/repo.git\n"
        "    default_ref: main\n"
        "    relative_path: repo\n"
        "    analysis_commands:\n"
        "      - command_id: sample_cmd\n"
        "        display_name: Sample Command\n"
        "        datasource: Illumina\n"
        "        launcher: workflow_launch\n"
        "        targets: [produce_alignstats]\n"
        "        genome: hg38\n"
        "        jobs: 1\n"
        "        aligners: [sent]\n"
        "        dedupers: [dmd]\n"
        "        snv_callers: [sentd]\n"
        "        sv_callers: []\n"
        "        dy_command: bin/day_run produce_alignstats\n"
        "        dryrun_dy_command: bin/day_run produce_alignstats -n\n"
        "        compatible_platforms: [ILMN]\n"
        "        compatible_cluster_types: [daywgs]\n"
        "        compatible_data_modes: [ilmn_solo]\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="command_class"):
        load_repository_catalog(path)


def test_repository_catalog_v3_requires_result_export_guidance(tmp_path: Path) -> None:
    path = tmp_path / "v3-without-export-guidance.yaml"
    path.write_text(
        _minimal_run_catalog_yaml().replace(
            "command_catalog_version: 2",
            "command_catalog_version: 3",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires result_export guidance"):
        load_repository_catalog(path)


def test_repository_catalog_v4_requires_dyec_builds(tmp_path: Path) -> None:
    path = tmp_path / "v4-without-builds.yaml"
    raw = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))
    del raw["dyec_builds"]
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="requires dyec_builds"):
        load_repository_catalog(path)


def test_repository_catalog_v5_requires_current_build(tmp_path: Path) -> None:
    path = tmp_path / "v5-without-current.yaml"
    raw = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))
    del raw["dyec_builds"]["current"]
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="requires dyec_builds.current"):
        load_repository_catalog(path)


def test_repository_catalog_rejects_unknown_cluster_type(tmp_path: Path) -> None:
    path = tmp_path / "bad-cluster-type.yaml"
    path.write_text(
        _minimal_run_catalog_yaml().replace(
            "compatible_cluster_types: [daywgs]",
            "compatible_cluster_types: [gpu]",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="compatible_cluster_types"):
        load_repository_catalog(path)


def test_repository_catalog_requires_catalog_version(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        "default_repository: repo\n"
        "repositories:\n"
        "  repo:\n"
        "    https_url: https://example.invalid/repo.git\n"
        "    default_ref: main\n"
        "    relative_path: repo\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="command_catalog_version"):
        load_repository_catalog(path)


def test_packaged_repository_catalog_matches_source_catalog() -> None:
    assert PACKAGED_CATALOG_PATH.read_text(encoding="utf-8") == CATALOG_PATH.read_text(
        encoding="utf-8"
    )


def test_legacy_catalog_filename_is_symlink_to_pipeline_command_catalog() -> None:
    assert OLD_CATALOG_LINK.is_symlink()
    assert OLD_CATALOG_LINK.resolve() == CATALOG_PATH
    assert OLD_PACKAGED_CATALOG_LINK.is_symlink()
    assert OLD_PACKAGED_CATALOG_LINK.resolve() == PACKAGED_CATALOG_PATH


def test_daylily_sarek_repository_uses_valid_pinned_ref() -> None:
    catalog = load_repository_catalog(CATALOG_PATH)
    repository = catalog.repositories["daylily-sarek"]

    assert repository.default_ref == "0.7.379"
    assert repository.analysis_commands == []


def test_repositories_commands_json_cli_lists_blessed_command() -> None:
    result = runner.invoke(
        app,
        [
            "repositories",
            "commands",
            "--config",
            str(CATALOG_PATH),
            "--command-id",
            "illumina_snv_alignstats",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["test_data_locations"][0]["data_root"] == (
        "/fsx/data/genomic_data/organism_reads_slim"
    )
    assert payload["test_data_profiles"]["default_reads_slim"]["source_mount_mode"] == (
        "default_mounted"
    )
    assert payload["test_data_profiles"]["illumina_run_directory"]["source_mount_mode"] == (
        "run_dra_required"
    )
    assert "default /fsx/data path" in payload["test_data_locations"][0]["description"]
    assert payload["input_contracts"]["sample_manifest"]["source_table"]["required_columns"] == [
        "RUN_ID",
        "SAMPLE_ID",
        "EXPERIMENTID",
        "SAMPLE_TYPE",
        "LIB_PREP",
        "SEQ_VENDOR",
        "SEQ_PLATFORM",
        "LANE",
        "SEQBC_ID",
    ]
    assert [item["command_id"] for item in payload["commands"]] == ["illumina_snv_alignstats"]
    assert payload["commands"][0]["compatible_platforms"] == ["ILMN"]
    assert payload["commands"][0]["compatible_cluster_types"] == ["daywgs"]
    assert payload["commands"][0]["command_class"] == "sample_analysis"
    assert payload["commands"][0]["input_requirements"]["required_source_columns"] == [
        "ILMN_R1_FQ",
        "ILMN_R2_FQ",
    ]


def test_catalog_build_snapshots_preserve_immutable_command_shapes(tmp_path) -> None:
    raw = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))
    raw["command_catalog_version"] = 4
    command = next(
        item
        for item in raw["repositories"]["daylily-omics-analysis"]["analysis_commands"]
        if item["command_id"] == "illumina_snv_alignstats"
    )
    snapshot = dict(command)
    snapshot["git_tag"] = "13.4.30"
    snapshot["validated_version"] = "13.4.30"
    snapshot["repository"] = "daylily-omics-analysis"
    snapshot["validation_evidence_s3_uri_prefix"] = "s3://validation-bucket/illumina/"
    raw["dyec_builds"] = {
        "16.1.81": {
            "repository": "daylily-omics-analysis",
            "dayoa_git_tags": ["13.4.30"],
            "commands": {"illumina_snv_alignstats": snapshot},
        }
    }
    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    catalog = load_repository_catalog(catalog_path)
    snapshot_command = catalog.get_command_for_dyec_build("illumina_snv_alignstats", "16.1.81")

    assert snapshot_command.git_tag == "13.4.30"
    assert snapshot_command.validation_evidence_s3_uri_prefix == "s3://validation-bucket/illumina/"
    assert [command.command_id for command in catalog.commands_for_dyec_build("16.1.81")] == [
        "illumina_snv_alignstats"
    ]
    with pytest.raises(KeyError, match="not eligible"):
        catalog.get_command_for_dyec_build("ont_snv_alignstats", "16.1.81")


def test_catalog_version_five_default_accessors_use_current(tmp_path) -> None:
    raw = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))
    top_level_command = next(
        item
        for item in raw["repositories"]["daylily-omics-analysis"]["analysis_commands"]
        if item["command_id"] == "illumina_snv_alignstats"
    )
    top_level_command["display_name"] = "Non-current repository row"
    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    catalog = load_repository_catalog(catalog_path)

    assert catalog.get_command("illumina_snv_alignstats").display_name != (
        "Non-current repository row"
    )
    assert catalog.get_command("illumina_snv_alignstats").model_dump() == (
        catalog.get_command_for_dyec_build("illumina_snv_alignstats").model_dump()
    )
