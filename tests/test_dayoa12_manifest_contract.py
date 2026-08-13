from __future__ import annotations

import csv
from pathlib import Path

import pytest

import daylily_ec.cli  # noqa: F401 - initialize workflow imports before catalog model
import daylily_ec.stage_samples as stage
from daylily_ec.cli import _validate_sample_command_input_requirements
from daylily_ec.repositories import load_repository_catalog
from daylily_ec.scripts.common import CommandError
from daylily_ec.scripts.daylily_run_omics_analysis_headnode import parse_remote_config

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "config/daylily_pipeline_command_catalog.yaml"


def _read_one(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert len(rows) == 1
    return rows[0]


def _source_manifest(
    tmp_path: Path,
    *,
    specimen_euid: str = "fixture-specimen-owned-001",
    analysis_unit_uid: str = "analysis-unit-001",
) -> Path:
    row = {
        "SPECIMEN_ID": "specimen-001",
        "SPECIMEN_EUID": specimen_euid,
        "SAMPLEID": "sample-001",
        "SAMPLE_EUID": "fixture-sample-owned-001",
        "ANALYSIS_UNIT_UID": analysis_unit_uid,
        "LIBRARY_EUID": "fixture-library-owned-001",
        "INFLECTION_DELIVERY_ID": "delivery-001",
        "RUN_ID": "run-001",
        "EXPERIMENTID": "full",
        "SAMPLE_TYPE": "gdna",
        "SAMPLESOURCE": "blood",
        "SPECIMEN_TYPE": "whole_blood",
        "SAMPLECLASS": "research",
        "SAMPLEUSE": "positive_control",
        "ORDER_TYPE": "positive_control",
        "BIOLOGICAL_SEX": "male",
        "LIB_PREP": "PCRFREE",
        "SEQ_VENDOR": "ILMN",
        "SEQ_PLATFORM": "NOVASEQ",
        "LANE": "1",
        "SEQBC_ID": "barcode-001",
        "ILMN_R1_FQ": "/fsx/references/fixture_R1.fastq.gz",
        "ILMN_R2_FQ": "/fsx/references/fixture_R2.fastq.gz",
        "STAGE_DIRECTIVE": "pass_through",
        "IS_POS_CTRL": "true",
        "IS_NEG_CTRL": "false",
        "EXTERNAL_SAMPLE_ID": "HG003",
        "EXTERNAL_SPECIMEN_ID": "HG003",
        "N_X": "1",
        "N_Y": "1",
    }
    path = tmp_path / "analysis_samples.tsv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row), delimiter="\t")
        writer.writeheader()
        writer.writerow(row)
    return path


def test_dayoa12_config_only_writes_exact_three_manifest_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = _source_manifest(tmp_path)
    output = tmp_path / "generated"
    monkeypatch.setattr(stage, "check_source_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(stage, "detect_giab_roi_dirs", lambda *args, **kwargs: [])

    rc = stage.main(
        [
            str(source),
            "--manifest-contract",
            "dayoa12",
            "--config-only",
            "--config-dir",
            str(output),
            "--reference-s3-uri",
            "s3://references",
            "--control-data-s3-uri",
            "s3://controls",
            "--stage-s3-uri",
            "s3://stage",
            "--profile",
            "fixture",
        ]
    )

    assert rc == 0
    specimens = list(output.glob("*_specimens.tsv"))
    samples = list(output.glob("*_samples.tsv"))
    libraries = list(output.glob("*_libraries.tsv"))
    assert len(specimens) == len(samples) == len(libraries) == 1
    assert not list(output.glob("*_units.tsv"))
    specimen = _read_one(specimens[0])
    sample = _read_one(samples[0])
    library = _read_one(libraries[0])
    assert specimen["SPECIMEN_EUID"] == "fixture-specimen-owned-001"
    assert sample["SAMPLE_EUID"] == "fixture-sample-owned-001"
    assert library["LIBRARY_EUID"] == "fixture-library-owned-001"
    assert library["ANALYSIS_UNIT_UID"] == "analysis-unit-001"
    assert library["INFLECTION_DELIVERY_ID"] == "delivery-001"
    assert "ULTIMA_SUBSAMPLE_PCT" not in library
    assert "ONT_SUBSAMPLE_PCT" not in library
    assert specimen["SPECIMEN_ID"] == sample["SPECIMEN_ID"] == "specimen-001"
    assert sample["SAMPLEID"] == library["SAMPLEID"] == "sample-001"


def test_dayoa12_rejects_populated_library_fields_missing_from_pinned_schema(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = _source_manifest(tmp_path)
    with source.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    rows[0]["ONT_SUBSAMPLE_PCT"] = "0.5"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    monkeypatch.setattr(stage, "check_source_path", lambda *args, **kwargs: None)

    report, generated = stage.precheck_manifest(
        source,
        reference_s3_uri="s3://references",
        aws_env={},
        debug=False,
        manifest_contract="dayoa12",
    )

    assert generated == []
    assert any("DayOA 12.0.2 libraries schema" in issue.message for issue in report.issues)


def test_dayoa12_preserves_blank_conditional_euid_without_inference(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = _source_manifest(tmp_path, specimen_euid="")
    monkeypatch.setattr(stage, "check_source_path", lambda *args, **kwargs: None)

    output = tmp_path / "generated"
    monkeypatch.setattr(stage, "detect_giab_roi_dirs", lambda *args, **kwargs: [])
    rc = stage.main(
        [
            str(source),
            "--manifest-contract",
            "dayoa12",
            "--config-only",
            "--config-dir",
            str(output),
            "--reference-s3-uri",
            "s3://references",
            "--control-data-s3-uri",
            "s3://controls",
            "--stage-s3-uri",
            "s3://stage",
            "--profile",
            "fixture",
        ]
    )

    assert rc == 0
    assert _read_one(next(output.glob("*_specimens.tsv")))["SPECIMEN_EUID"] == ""


def test_dayoa12_rejects_silent_identity_whitespace_rewrite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = _source_manifest(tmp_path, specimen_euid=" fixture-specimen-owned-001")
    monkeypatch.setattr(stage, "check_source_path", lambda *args, **kwargs: None)

    report, rows = stage.precheck_manifest(
        source,
        reference_s3_uri="s3://references",
        aws_env={},
        debug=False,
        manifest_contract="dayoa12",
    )

    assert rows == []
    assert any("byte-exact" in issue.message for issue in report.issues)


def test_dayoa12_preserves_blank_analysis_unit_for_dayoa_construction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = _source_manifest(tmp_path, analysis_unit_uid="")
    output = tmp_path / "generated"
    monkeypatch.setattr(stage, "check_source_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(stage, "detect_giab_roi_dirs", lambda *args, **kwargs: [])

    rc = stage.main(
        [
            str(source),
            "--manifest-contract",
            "dayoa12",
            "--config-only",
            "--config-dir",
            str(output),
            "--reference-s3-uri",
            "s3://references",
            "--control-data-s3-uri",
            "s3://controls",
            "--stage-s3-uri",
            "s3://stage",
            "--profile",
            "fixture",
        ]
    )

    assert rc == 0
    assert _read_one(next(output.glob("*_libraries.tsv")))["ANALYSIS_UNIT_UID"] == ""


def test_dayoa13_catalog_commands_reject_legacy_manifest_paths() -> None:
    command = load_repository_catalog(CATALOG).get_command("hybrid_ilmn_ont_hiomr_kitchensink")
    assert command.input_contract == "six_manifest"
    with pytest.raises(ValueError, match="require manifest_dir"):
        command.launch_argv(
            analysis_id="analysis-001",
            executing_entity="cluster-001",
            samples_file="samples.tsv",
            units_file="units.tsv",
        )


def test_dayoa13_launch_transports_exact_six_manifest_directory() -> None:
    command = load_repository_catalog(CATALOG).get_command("hybrid_ilmn_ont_hiomr_kitchensink")
    argv = command.launch_argv(
        analysis_id="analysis-001",
        executing_entity="cluster-001",
        manifest_dir="/input/manifests",
    )

    assert argv[argv.index("--manifest-dir") + 1] == "/input/manifests"
    assert argv[argv.index("--input-contract") + 1] == "six_manifest"
    assert "--specimens-file" not in argv
    assert "--samples-file" not in argv
    assert "--libraries-file" not in argv
    assert "--units-file" not in argv


def test_headnode_remote_config_requires_exact_dayoa12_triple() -> None:
    remote = parse_remote_config(
        "\n".join(
            [
                "__DAYLILY_STAGE_DIR__=/fsx/stage",
                "__DAYLILY_STAGE_SPECIMENS__=/fsx/stage/specimens.tsv",
                "__DAYLILY_STAGE_SAMPLES__=/fsx/stage/samples.tsv",
                "__DAYLILY_STAGE_LIBRARIES__=/fsx/stage/libraries.tsv",
            ]
        ),
        input_contract="sample_manifest_v12",
    )

    assert remote.specimens_path == "/fsx/stage/specimens.tsv"
    assert remote.samples_path == "/fsx/stage/samples.tsv"
    assert remote.libraries_path == "/fsx/stage/libraries.tsv"
    assert remote.units_path == ""

    with pytest.raises(CommandError, match="legacy units.tsv is not accepted"):
        parse_remote_config(
            "\n".join(
                [
                    "__DAYLILY_STAGE_DIR__=/fsx/stage",
                    "__DAYLILY_STAGE_SAMPLES__=/fsx/stage/samples.tsv",
                    "__DAYLILY_STAGE_UNITS__=/fsx/stage/units.tsv",
                ]
            ),
            input_contract="sample_manifest_v12",
        )


def test_inflection_v02_resolves_the_hiomr2_analytical_alias_contract() -> None:
    catalog = load_repository_catalog(CATALOG)
    command = catalog.get_command("inflection-bjuice-product-v0.2")
    assert command.git_tag == "14.0.8"
    assert command.input_contract == "six_manifest"
    assert command.input_requirements.required_source_columns == []
    assert command.targets == [
        "produce_sentdhiomr2_slim_kitchensink_mega",
        "produce_sentdhiomr2_inflection_analytical_package",
    ]
    assert command.runtime_parameters == {}
    assert "seqone_delivery_batch_id=$ANALYSIS_ID" in command.dy_command
    assert "hiomr2_inflection_package_mode=analytical" in command.dy_command
    assert "HIOMR2_SEQONE_V2_CONFIG_FILE" not in command.dy_command
    assert "SEQONE_DELIVERY_BATCH_ID" not in command.dy_command
    assert "--configfile config/hg002_bjuice_5x5x_hiomr2.yaml" in command.dy_command
    assert command.return_results is False
    assert "use_fq_data_starting_hrs" not in command.dy_command
    assert "use_fq_data_up_to_hrs" not in command.dy_command
    assert " -j 333 -T 0 -p " in command.dy_command
    assert "produce_sentdhiomr2_slim_kitchensink_mega" in command.dy_command
    assert "produce_sentdhiomr2_nicu_research" not in command.dy_command
    assert "produce_sentdhiomr2_jasmine_sharded_per_sample" not in command.dy_command
    assert command.jobs == 333
    assert command.restart_times == 1
    assert command.dryrun_dy_command == f"{command.dy_command} -n"
    assert "produce_inflection_delivery_set" not in command.dy_command
    with pytest.raises(KeyError):
        catalog.get_command("inflection-bjuice-product-v0.1")


def test_inflection_v02_runtime_preflight_does_not_require_legacy_delivery_identity(
    tmp_path: Path,
) -> None:
    command = load_repository_catalog(CATALOG).get_command("inflection-bjuice-product-v0.2")
    source = tmp_path / "analysis_samples.tsv"
    source.write_text(
        "ILMN_R1_FQ\tILMN_R2_FQ\tONT_R1_FQ\n"
        "/fsx/r1.fastq.gz\t/fsx/r2.fastq.gz\t/fsx/lr.fastq.gz\n",
        encoding="utf-8",
    )
    _validate_sample_command_input_requirements(source, command)
