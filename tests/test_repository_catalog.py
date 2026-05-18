from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from daylily_ec.cli import app
from daylily_ec.repositories import load_repository_catalog


runner = CliRunner()


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "config" / "daylily_available_repositories.yaml"
PACKAGED_CATALOG_PATH = (
    REPO_ROOT
    / "daylily_ec"
    / "resources"
    / "payload"
    / "config"
    / "daylily_available_repositories.yaml"
)


def test_repository_catalog_loads_initial_blessed_command() -> None:
    catalog = load_repository_catalog(CATALOG_PATH)
    command = catalog.get_command("illumina_snv_alignstats")

    assert catalog.command_catalog_version == 2
    manifest_contract = catalog.input_contracts["sample_manifest"]
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
    assert command.git_tag == "1.0.11"
    assert command.compatible_platforms == ["ILMN"]
    assert command.compatible_data_modes == ["ilmn_solo"]
    assert "bin/day_run" in command.dy_command
    assert command.dryrun_dy_command.endswith(" -n")

    launch_argv = command.launch_argv(destination="run-1", cluster="cluster-a")
    assert "--dy-command" in launch_argv
    assert "--git-tag" in launch_argv
    assert "1.0.11" in launch_argv


def test_repository_catalog_commands_have_run_metadata() -> None:
    catalog = load_repository_catalog(CATALOG_PATH)

    command_ids = {command.command_id for command in catalog.commands()}
    assert {
        "illumina_snv_alignstats",
        "illumina_snv_alignstats_relatedness_vep_multiqc",
        "ultima_snv_alignstats",
        "ont_snv_alignstats",
        "pacbio_snv_alignstats",
        "roche_snv_alignstats",
        "hybrid_ilmn_ont_snv",
        "hybrid_ultima_ont_snv",
        "complete_genomics_mgi_snv_concordance",
    } <= command_ids

    for command in catalog.commands():
        if command.command_class != "sample_analysis":
            continue
        assert command.dy_command.startswith("bin/day_run ")
        assert command.dryrun_dy_command.startswith("bin/day_run ")
        assert command.dryrun_dy_command.endswith(" -n")
        assert command.compatible_platforms
        assert command.compatible_data_modes
        assert command.git_tag == "1.0.11"
        assert (
            command.input_requirements.required_source_columns
            or command.input_requirements.accepted_source_column_sets
        )

    complete_genomics = catalog.get_command("complete_genomics_mgi_snv_concordance")
    assert complete_genomics.compatible_platforms == ["CG/MGI"]
    assert complete_genomics.compatible_data_modes == ["complete_genomics_solo"]
    assert complete_genomics.aligners == ["sentcg"]
    assert complete_genomics.dedupers == ["dmd"]
    assert "produce_cgt7p_snv_vcf" in complete_genomics.dy_command
    assert "produce_sentcg_align" in complete_genomics.dy_command
    assert "produce_dmd_dedup_cram" in complete_genomics.dy_command
    assert "produce_smd_dedup_cram" not in complete_genomics.dy_command
    assert "aligners=['sentcg']" not in complete_genomics.dy_command

    hybrid_ilmn_ont = catalog.get_command("hybrid_ilmn_ont_snv")
    assert hybrid_ilmn_ont.aligners == ["sent"]
    assert hybrid_ilmn_ont.dedupers == ["dmd"]
    assert "sentdhiom" in hybrid_ilmn_ont.snv_callers
    assert "dedupers=[" in hybrid_ilmn_ont.dy_command

    hybrid_ultima_ont = catalog.get_command("hybrid_ultima_ont_snv")
    assert hybrid_ultima_ont.aligners == ["ug"]
    assert hybrid_ultima_ont.dedupers == ["na"]

    for command in catalog.commands():
        if command.command_class != "sample_analysis":
            continue
        assert not (set(command.dedupers) & {"dppl", "dppl_sent", "smd"})
        assert not (set(command.aligners) & {"sentdhiom", "sentdhuom"})

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

    ont = catalog.get_command("ont_snv_alignstats")
    assert ont.aligners == ["ont"]
    assert "produce_sentdont_snv_vcf" in ont.dy_command
    assert "produce_sentmm2ont_align" not in ont.dy_command
    assert "produce_na_dedup_cram" not in ont.dy_command
    assert ["ONT_CRAM", "ONT_CRAM_ALIGNER", "ONT_CRAM_SNV_CALLER"] in (
        ont.input_requirements.accepted_source_column_sets
    )


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
    assert command.runtime_parameters == {"run_context_file": "config/runs.tsv"}
    assert command.input_requirements.required_run_context_values == {"PLATFORM": "ILMN"}
    assert command.targets == ["produce_illumina_run_qc"]
    assert command.compatible_platforms == ["ILMN"]

    with pytest.raises(ValueError, match="run_context_file is required"):
        command.launch_argv(destination="s3://bucket/results")

    launch_argv = command.launch_argv(
        destination="s3://bucket/results",
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
    assert dy_command.endswith("--config run_context_file=config/runs.tsv")


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
        "        compatible_data_modes: [ilmn_solo]\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="command_class"):
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
    assert payload["input_contracts"]["sample_manifest"]["source_table"][
        "required_columns"
    ] == [
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
    assert payload["commands"][0]["command_class"] == "sample_analysis"
    assert payload["commands"][0]["input_requirements"]["required_source_columns"] == [
        "ILMN_R1_FQ",
        "ILMN_R2_FQ",
    ]
