from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from daylily_ec.cli import app
from daylily_ec.repositories import load_repository_catalog


runner = CliRunner()


DAYOA_BLESSED_TAG = "10.0.64"
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
    "ultima_snv_alignstats_kitchensink",
    "ont_snv_alignstats_kitchensink",
    "hybrid_ilmn_ont_snv_kitchensink",
    "inflection-bjuice-product-v0.1",
    "illumina_pangenome_snv",
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

    assert catalog.command_catalog_version == 2
    manifest_contract = catalog.input_contracts["sample_manifest"]
    assert [location.location_id for location in catalog.test_data_locations] == [
        "default_reference_reads_slim",
        "default_control_reads_slim",
        "default_control_run_data",
    ]
    assert catalog.test_data_locations[0].mount_path == "/fsx/references"
    assert (
        catalog.test_data_locations[0].data_root
        == "/fsx/references/genomic_data/organism_reads_slim"
    )
    assert "default reference mount" in catalog.test_data_locations[0].description
    default_reads = catalog.test_data_profiles["default_reads_slim"]
    assert default_reads.source_mount_mode == "default_mounted"
    assert (
        default_reads.source_s3_uri_template
        == "s3://lsmc-dayoa-references-usw2/genomic_data/organism_reads_slim/"
    )
    assert default_reads.source_fsx_prefix == (
        "/fsx/references/genomic_data/organism_reads_slim/"
    )
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
    assert {report.report_kind for report in run_qc_command.artifact_registration.multiqc_reports} == {
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

    registration_argv = multiqc_command.launch_argv(
        analysis_id="run-1",
        executing_entity="johnm",
        export_destination_s3_uri="s3://bucket/derived/johnm/run-1/",
        export_trigger="on-success",
        artifact_registration_command_id=multiqc_command.command_id,
        dewey_url="https://dewey.example",
        dewey_token_env="DEWEY_TOKEN",
        dewey_analysis_dir_external_object_id="M-RGX-9S3G",
        dewey_run_artifact_euid="M-DGX-9SD7",
        dewey_ursa_analysis_euid="M-RGX-9S3G",
    )
    assert "--artifact-registration-command-id" in registration_argv
    assert "illumina_snv_alignstats_relatedness_vep_multiqc" in registration_argv
    assert "--dewey-url" in registration_argv
    assert "--dewey-token-env" in registration_argv
    assert "--dewey-analysis-dir-external-object-id" in registration_argv
    assert "M-DGX-9SD7" in registration_argv

    with pytest.raises(ValueError, match="dewey_url and dewey_token_env"):
        multiqc_command.launch_argv(
            analysis_id="run-1",
            executing_entity="johnm",
            export_destination_s3_uri="s3://bucket/derived/johnm/run-1/",
            export_trigger="on-success",
            artifact_registration_command_id=multiqc_command.command_id,
        )

    with pytest.raises(ValueError, match="artifact_registration_command_id"):
        multiqc_command.launch_argv(
            analysis_id="run-1",
            executing_entity="johnm",
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


def test_repository_catalog_commands_have_run_metadata() -> None:
    catalog = load_repository_catalog(CATALOG_PATH)

    command_ids = {command.command_id for command in catalog.commands()}
    assert {
        "simple-test",
        "illumina_snv_alignstats",
        "illumina_snv_alignstats_relatedness_vep_multiqc",
        "illumina_hg002_kitchensink_multiqc",
        "ultima_snv_alignstats",
        "ultima_snv_alignstats_kitchensink",
        "ont_snv_alignstats",
        "ont_snv_alignstats_kitchensink",
        "pacbio_snv_alignstats",
        "roche_snv_alignstats",
        "hybrid_ilmn_ont_snv",
        "hybrid_ilmn_ont_snv_kitchensink",
        "illumina_pangenome_snv",
        "ultima_pangenome_snv",
        "complete_genomics_mgi_snv_concordance",
    } <= command_ids

    for command in catalog.commands():
        if not command.validation_runs:
            assert command.command_id in UNVALIDATED_COMMAND_IDS
            continue
        assert len(command.validation_runs) == 1
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
            assert command.git_tag == DAYOA_BLESSED_TAG
            assert (
                command.input_requirements.required_source_columns
                or command.input_requirements.accepted_source_column_sets
            )
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
        assert command.git_tag == DAYOA_BLESSED_TAG
        assert (
            command.input_requirements.required_source_columns
            or command.input_requirements.accepted_source_column_sets
        )

    complete_genomics = catalog.get_command("complete_genomics_mgi_snv_concordance")
    assert complete_genomics.type == "dev"
    assert complete_genomics.compatible_platforms == ["CG/MGI"]
    assert complete_genomics.compatible_cluster_types == ["daywgs"]
    assert complete_genomics.compatible_data_modes == ["complete_genomics_solo"]
    assert complete_genomics.aligners == ["sentcg"]
    assert complete_genomics.dedupers == ["dmd"]
    assert "produce_cgt7p_snv_vcf" in complete_genomics.dy_command
    assert "produce_sentcg_align" in complete_genomics.dy_command
    assert "produce_dmd_dedup_cram" in complete_genomics.dy_command
    assert "produce_smd_dedup_cram" not in complete_genomics.dy_command
    assert "aligners=['sentcg']" not in complete_genomics.dy_command

    illumina_pangenome = catalog.get_command("illumina_pangenome_snv")
    assert illumina_pangenome.type == "dev"
    assert illumina_pangenome.git_tag == DAYOA_BLESSED_TAG
    assert illumina_pangenome.genome == "hg38_broad"
    assert illumina_pangenome.targets == ["produce_sentpg_snv_vcf"]
    assert illumina_pangenome.snv_callers == ["sentpg"]
    assert illumina_pangenome.compatible_platforms == ["ILMN"]
    assert illumina_pangenome.compatible_cluster_types == ["daywgs"]
    assert illumina_pangenome.compatible_data_modes == ["ilmn_solo"]

    ultima_pangenome = catalog.get_command("ultima_pangenome_snv")
    assert ultima_pangenome.type == "dev"
    assert ultima_pangenome.git_tag == DAYOA_BLESSED_TAG
    assert ultima_pangenome.genome == "hg38_broad"
    assert ultima_pangenome.targets == ["produce_pangenome_ug_vcf"]
    assert ultima_pangenome.aligners == ["pangenome_ug"]
    assert ultima_pangenome.snv_callers == ["sentpg"]
    assert ultima_pangenome.compatible_platforms == ["ULTIMA"]
    assert ultima_pangenome.compatible_cluster_types == ["daywgs"]
    assert ultima_pangenome.compatible_data_modes == ["ultima_solo"]

    hybrid_ilmn_ont = catalog.get_command("hybrid_ilmn_ont_snv")
    assert hybrid_ilmn_ont.aligners == ["sent"]
    assert hybrid_ilmn_ont.dedupers == ["dmd"]
    assert hybrid_ilmn_ont.snv_callers == ["sentdhiomr"]
    assert hybrid_ilmn_ont.sv_callers == ["sentdhiomr"]
    assert "produce_sentdhiomr_sv" in hybrid_ilmn_ont.dy_command
    assert "produce_sentdhiomr_snv_vcf" in hybrid_ilmn_ont.dy_command
    assert "produce_sentdhiom_sv" not in hybrid_ilmn_ont.dy_command
    assert "produce_sentdhiom_snv_vcf" not in hybrid_ilmn_ont.dy_command
    assert "dedupers=[" in hybrid_ilmn_ont.dy_command
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
    assert illumina_kitchensink.jobs == 200
    assert illumina_kitchensink.aligners == ["sent"]
    assert illumina_kitchensink.dedupers == ["dmd"]
    assert illumina_kitchensink.snv_callers == ["sentd"]
    assert illumina_kitchensink.sv_callers == []
    assert 'htd_callers=["cyrius"]' in illumina_kitchensink.dy_command
    assert "--rerun-triggers mtime" in illumina_kitchensink.dy_command
    assert "produce_metagenomics" in illumina_kitchensink.dy_command
    assert "produce_multiqc_all" in illumina_kitchensink.dy_command
    assert "results/day/hg38/reports/DAY_final_multiqc.html" in illumina_kitchensink.dy_command
    assert "results/day/hg38/reports/dayoa_evidence_manifest.json" in illumina_kitchensink.dy_command
    assert "produce_global_contam_check" not in illumina_kitchensink.dy_command
    assert "contam_identity" not in illumina_kitchensink.dy_command

    ultima_kitchensink = catalog.get_command("ultima_snv_alignstats_kitchensink")
    assert ultima_kitchensink.validation_runs == []
    assert ultima_kitchensink.targets == [
        "produce_alignstats",
        "produce_na_dedup_cram",
        "produce_sentdug_snv_vcf",
        "produce_snv_concordances",
        "produce_relatedness",
        "produce_vep",
        "produce_multiqc_all",
    ]
    assert ultima_kitchensink.aligners == ["ug"]
    assert ultima_kitchensink.dedupers == ["na"]
    assert ultima_kitchensink.snv_callers == ["sentdug"]
    assert "produce_multiqc_all" in ultima_kitchensink.dy_command
    assert "multiqc_qc=" in ultima_kitchensink.dy_command
    assert "enable_tools" in ultima_kitchensink.dy_command

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
    assert ont_kitchensink.targets == [
        "produce_alignstats",
        "produce_na_dedup_cram",
        "produce_sentdont_snv_vcf",
        "produce_snv_concordances",
        "produce_relatedness",
        "produce_vep",
        "produce_multiqc_all",
        "results/day/hg38_broad/reports/DAY_final_multiqc.html",
        "results/day/hg38_broad/reports/dayoa_evidence_manifest.json",
    ]
    assert ont_kitchensink.jobs == 250
    assert ont_kitchensink.aligners == ["ont"]
    assert ont_kitchensink.dedupers == ["na"]
    assert ont_kitchensink.snv_callers == ["sentdont"]
    assert "produce_sentmm2ont_align" not in ont_kitchensink.dy_command
    assert "produce_na_dedup_cram" in ont_kitchensink.dy_command
    assert "--rerun-triggers mtime" in ont_kitchensink.dy_command
    assert "--rerun-triggers mtime -n" in ont_kitchensink.dryrun_dy_command
    assert " -j 250 " in ont_kitchensink.dy_command
    assert "produce_multiqc_all" in ont_kitchensink.dy_command
    assert "results/day/hg38_broad/reports/DAY_final_multiqc.html" in ont_kitchensink.dy_command
    assert "results/day/hg38_broad/reports/dayoa_evidence_manifest.json" in ont_kitchensink.dy_command
    assert "multiqc_qc=" in ont_kitchensink.dy_command

    hybrid_kitchensink = catalog.get_command("hybrid_ilmn_ont_snv_kitchensink")
    assert hybrid_kitchensink.validation_runs == []
    assert hybrid_kitchensink.targets == [
        "produce_snv_concordances",
        "produce_sentdhiomr_sv",
        "produce_sentdhiomr_snv_vcf",
        "produce_relatedness",
        "produce_vep",
        "produce_multiqc_all",
    ]
    assert hybrid_kitchensink.aligners == ["sent"]
    assert hybrid_kitchensink.dedupers == ["dmd"]
    assert hybrid_kitchensink.snv_callers == ["sentdhiomr"]
    assert hybrid_kitchensink.sv_callers == ["sentdhiomr"]
    assert "produce_sentdhiomr_sv" in hybrid_kitchensink.dy_command
    assert "produce_sentdhiomr_snv_vcf" in hybrid_kitchensink.dy_command
    assert "produce_sentdhiom_sv" not in hybrid_kitchensink.dy_command
    assert "produce_sentdhiom_snv_vcf" not in hybrid_kitchensink.dy_command
    assert "produce_multiqc_all" in hybrid_kitchensink.dy_command
    assert "multiqc_qc=" in hybrid_kitchensink.dy_command
    assert ["ILMN_R1_FQ", "ILMN_R2_FQ", "ONT_R1_FQ"] in (
        hybrid_kitchensink.input_requirements.accepted_source_column_sets
    )

    inflection_bjuice = catalog.get_command("inflection-bjuice-product-v0.1")
    assert inflection_bjuice.validation_runs == []
    assert inflection_bjuice.targets == [
        "produce_sent_align",
        "produce_dmd_dedup_cram",
        "produce_sentdhiomr_snv_vcf",
        "produce_sentdhiomr_sv",
        "produce_sentdhiomr_cnv",
        "produce_sentdhiomr_segdup",
        "produce_sentdhiomr_mito",
        "produce_expansionhunter",
        "produce_alignstats",
    ]
    assert inflection_bjuice.jobs == 250
    assert inflection_bjuice.aligners == ["sent"]
    assert inflection_bjuice.dedupers == ["dmd"]
    assert inflection_bjuice.snv_callers == ["sentdhiomr"]
    assert inflection_bjuice.sv_callers == ["sentdhiomr"]
    assert ["ILMN_R1_FQ", "ILMN_R2_FQ", "ONT_R1_FQ"] in (
        inflection_bjuice.input_requirements.accepted_source_column_sets
    )
    assert "produce_sentdhiomr_segdup" in inflection_bjuice.dy_command
    assert 'sentdhiomr={"segdup_genes":"CYP11B1,NCF1,SMN1"}' in (inflection_bjuice.dy_command)
    assert 'aligners=["sent"]' in inflection_bjuice.dy_command
    assert 'dedupers=["dmd"]' in inflection_bjuice.dy_command
    assert 'snv_callers=["sentdhiomr"]' in inflection_bjuice.dy_command
    assert 'sv_callers=["sentdhiomr"]' in inflection_bjuice.dy_command
    assert " -j 250 -p -k --rerun-triggers mtime -T 0" in inflection_bjuice.dy_command
    assert inflection_bjuice.dryrun_dy_command.endswith(" -n")

    simple_test = catalog.get_command("simple-test")
    assert simple_test.command_class == "utility"
    assert simple_test.input_contract == "none"
    assert simple_test.requires_staging is False
    assert simple_test.requires_run_mount is False
    assert simple_test.targets == ["help"]
    assert simple_test.genome == "hg38"
    assert simple_test.jobs == 1
    assert simple_test.dy_command == SIMPLE_TEST_DY_COMMAND
    assert simple_test.dryrun_dy_command == simple_test.dy_command
    simple_launch_argv = simple_test.launch_argv(
        analysis_id="simple-test",
        executing_entity="johnm",
    )
    assert "--dy-command" in simple_launch_argv
    assert simple_test.dy_command in simple_launch_argv
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
        "samples_table": ".test_data/data/samples.tsv",
        "units_table": ".test_data/data/units.tsv",
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
    assert "samples_table=.test_data/data/samples.tsv" in dy_command
    assert "units_table=.test_data/data/units.tsv" in dy_command
    assert dy_command.endswith(
        "--config run_context_file=config/runs.tsv "
        "samples_table=.test_data/data/samples.tsv "
        "units_table=.test_data/data/units.tsv"
    )

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
    assert ont.targets == ["produce_ont_run_qc"]
    ont_argv = ont.launch_argv(
        analysis_id="ont-run-qc",
        executing_entity="johnm",
        run_context_file="config/runs.tsv",
        dry_run=True,
    )
    ont_dy_command = ont_argv[ont_argv.index("--dy-command") + 1]
    assert "produce_ont_run_qc" in ont_dy_command
    assert "produce_ont_run_qc_and_demux_multiqc" not in ont_dy_command
    assert "run_context_file=config/runs.tsv" in ont_dy_command

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
        "/fsx/references/genomic_data/organism_reads_slim"
    )
    assert payload["test_data_profiles"]["default_reads_slim"]["source_mount_mode"] == (
        "default_mounted"
    )
    assert payload["test_data_profiles"]["illumina_run_directory"]["source_mount_mode"] == (
        "run_dra_required"
    )
    assert "default reference mount" in payload["test_data_locations"][0]["description"]
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
