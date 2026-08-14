from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

import daylily_ec.workflow.export_data  # noqa: F401 - establishes workflow import order
import daylily_ec.repositories as repos


def _fails(model, **kwargs) -> None:
    with pytest.raises(ValidationError):
        model(**kwargs)


def test_repository_small_model_validation_edges() -> None:
    _fails(repos.AnalysisCommandFeature, display_name="", targets=[])
    _fails(repos.AnalysisCommandFeature, display_name="x", targets=[""])
    _fails(repos.TableSchema, path="x", required_columns=[""])
    _fails(repos.TableSchema, path="x", required_columns=["a", "a"])
    _fails(
        repos.InputContractDefinition,
        generated_tables={"": {"path": "x", "required_columns": ["a"]}},
    )
    _fails(repos.CommandInputRequirements, required_source_columns=[""])
    _fails(repos.CommandInputRequirements, required_source_columns=["a", "a"])
    _fails(repos.CommandInputRequirements, accepted_source_column_sets=[[""]])
    _fails(repos.CommandInputRequirements, accepted_source_column_sets=[["a", "a"]])
    _fails(repos.CommandInputRequirements, required_run_context_values={"": "x"})
    _fails(
        repos.TestDataLocation,
        location_id="x",
        description="x",
        mount_path="/x",
        data_root="/x",
        applies_to_command_classes=[""],
    )
    _fails(
        repos.TestDataLocation,
        location_id="x",
        description="x",
        mount_path="/x",
        data_root="/x",
        applies_to_command_classes=["unknown"],
    )


def _profile(**overrides):
    data = {
        "description": "profile",
        "source_mount_mode": "none",
        "source_s3_uri_template": "",
        "source_fsx_prefix": "",
        "locations": [],
        "run_context_source_s3_column": "",
        "run_context_mount_id_column": "",
        "run_context_values": {},
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize(
    "overrides",
    [
        {"source_mount_mode": "bad"},
        {"locations": [""]},
        {"locations": ["a", "a"]},
        {"locations": ["loc"]},
        {"source_s3_uri_template": "s3://x"},
        {"source_fsx_prefix": "/x"},
        {"run_context_source_s3_column": "source"},
        {"run_context_values": {"x": "y"}},
        {"source_mount_mode": "default_mounted"},
        {"source_mount_mode": "default_mounted", "locations": ["loc"]},
        {
            "source_mount_mode": "default_mounted",
            "locations": ["loc"],
            "source_s3_uri_template": "s3://x",
        },
        {
            "source_mount_mode": "default_mounted",
            "locations": ["loc"],
            "source_s3_uri_template": "s3://x",
            "source_fsx_prefix": "/x",
            "run_context_source_s3_column": "source",
        },
        {
            "source_mount_mode": "default_mounted",
            "locations": ["loc"],
            "source_s3_uri_template": "s3://x",
            "source_fsx_prefix": "/x",
            "run_context_values": {"x": "y"},
        },
        {"source_mount_mode": "explicit_run_mounts"},
        {
            "source_mount_mode": "explicit_run_mounts",
            "source_s3_uri_template": "s3://x",
        },
        {
            "source_mount_mode": "explicit_run_mounts",
            "source_s3_uri_template": "s3://x",
            "source_fsx_prefix": "/x",
            "locations": ["loc"],
        },
        {
            "source_mount_mode": "explicit_run_mounts",
            "source_s3_uri_template": "s3://x",
            "source_fsx_prefix": "/x",
            "run_context_source_s3_column": "SOURCE_S3_URI",
        },
        {"source_mount_mode": "run_dra_required"},
        {"source_mount_mode": "run_dra_required", "source_s3_uri_template": "s3://x"},
        {
            "source_mount_mode": "run_dra_required",
            "source_s3_uri_template": "s3://x",
            "source_fsx_prefix": "/x",
        },
        {
            "source_mount_mode": "run_dra_required",
            "source_s3_uri_template": "s3://x",
            "source_fsx_prefix": "/x",
            "run_context_source_s3_column": "source",
        },
    ],
)
def test_data_profile_contract_errors(overrides) -> None:
    _fails(repos.TestDataProfile, **_profile(**overrides))


def test_explicit_run_mount_profile_is_a_non_run_context_sample_contract() -> None:
    profile = repos.TestDataProfile.model_validate(
        _profile(
            source_mount_mode="explicit_run_mounts",
            source_s3_uri_template="s3://fixture/bjuice/",
            source_fsx_prefix="/fsx/run_dir_mounts/",
        )
    )

    assert profile.source_mount_mode == "explicit_run_mounts"
    assert profile.locations == []


def _policy(**overrides):
    data = {
        "enabled": False,
        "manifest_source": "dayoa_manifest",
        "evidence_manifest_path": "manifest.json",
        "include_classifications": [],
        "include_paths": [],
        "parser_family_hint": "none",
        "multiqc_report_kind": "none",
        "multiqc_version": "1",
        "identity": {"analysis_euid": "analysis", "run_euid": "run"},
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize(
    "overrides",
    [
        {"manifest_source": "bad"},
        {"include_paths": [""]},
        {"include_paths": ["a", "a"]},
        {"evidence_manifest_path": "/absolute"},
        {"include_paths": ["a/../b"]},
        {"enabled": True},
        {"s3_body_sha256_max_bytes": 0},
        {"enabled": True, "include_paths": ["x"], "parser_family_hint": "multiqc"},
        {
            "multiqc_reports": [
                {"report_kind": "same", "html_path": "a", "data_dir_path": "b"},
                {"report_kind": "same", "html_path": "c", "data_dir_path": "d"},
            ]
        },
    ],
)
def test_artifact_policy_errors(overrides) -> None:
    _fails(repos.ArtifactRegistrationPolicy, **_policy(**overrides))


def test_multiqc_paths_and_validation_status_errors() -> None:
    _fails(
        repos.ArtifactRegistrationMultiQCReport, report_kind="x", html_path="/x", data_dir_path="d"
    )
    _fails(
        repos.ArtifactRegistrationMultiQCReport,
        report_kind="x",
        html_path="x",
        data_dir_path="a/../d",
    )
    base = {
        key: "x"
        for key in (
            "run_id",
            "generated_at",
            "report_path",
            "ledger_path",
            "cluster",
            "region",
            "region_az",
            "dayec_tag",
            "dayec_commit",
            "dayoa_tag",
            "dayoa_commit",
            "tested_command",
        )
    }
    _fails(
        repos.CommandValidationRun,
        **base,
        status="bad",
        dryrun_status="success",
        live_status="success",
    )


def test_analysis_command_model_and_launch_error_branches() -> None:
    catalog = repos.load_repository_catalog()
    sample = catalog.get_command("illumina_snv_alignstats")
    run = catalog.get_command("illumina_run_qc")
    utility = catalog.get_command("simple-test")

    base = sample.model_dump()
    mutations = [
        {"type": "bad"},
        {"targets": [""]},
        {"runtime_parameters": {"": "x"}},
        {"sample_manifest_template": "/absolute"},
        {"manifest_dir_template": "/absolute"},
        {"manifest_dir_template": "examples/six"},
        {"launcher": "bad"},
        {"command_class": "bad"},
        {"input_contract": "bad"},
        {"input_contract": "none"},
        {"requires_staging": False},
        {"compatible_platforms": []},
        {"compatible_cluster_types": []},
        {"compatible_cluster_types": ["bad"]},
        {"compatible_data_modes": []},
        {"default_activation": False},
        {"day_profile": "local"},
    ]
    for mutation in mutations:
        with pytest.raises(ValidationError):
            repos.AnalysisCommand.model_validate({**deepcopy(base), **mutation})

    assert repos.AnalysisCommand.model_validate(
        {**deepcopy(base), "requires_run_mount": True}
    ).requires_run_mount is True

    six_manifest = catalog.get_command("hybrid_ilmn_ont_hiomr")
    with pytest.raises(ValidationError, match="must use manifest_dir_template"):
        repos.AnalysisCommand.model_validate(
            {**six_manifest.model_dump(), "sample_manifest_template": "examples/legacy.tsv"}
        )

    with pytest.raises(KeyError, match="Unknown optional feature"):
        sample.with_features(["missing"])
    assert sample.incompatible_modes([sample.compatible_data_modes[0], "unknown"]) == ["unknown"]

    common = {"analysis_id": "analysis", "executing_entity": "alice"}
    for kwargs in [
        {"export_trigger": "bad"},
        {"export_destination_s3_uri": "s3://b/k"},
        {"delete_on_export_success": True},
        {"run_context_file": "context.tsv"},
        {"samples_file": "samples.tsv"},
    ]:
        with pytest.raises(ValueError):
            sample.launch_argv(**common, **kwargs)

    for removed in (
        {"artifact_registration_command_id": "cmd"},
        {"dewey_url": "url"},
        {"dewey_analysis_dir_external_object_id": "one"},
    ):
        with pytest.raises(TypeError):
            sample.launch_argv(**common, **removed)
    with pytest.raises(ValueError, match="run_context_file is required"):
        run.launch_argv(**common)
    with pytest.raises(ValueError, match="only valid for run_analysis"):
        utility.launch_argv(**common, run_context_file="context.tsv")
    with pytest.raises(ValueError, match="stage_dir is only valid"):
        utility.launch_argv(**common, stage_dir="/stage")


def test_repository_definition_auth_contract() -> None:
    base = dict(
        display_name="repo",
        clone_transport="https",
        auth_mode="aws_deploy_key",
        https_url="https://example/repo",
        default_ref="main",
        relative_path="repo",
    )
    _fails(repos.RepositoryDefinition, **base)
    _fails(repos.RepositoryDefinition, **{**base, "clone_transport": "ssh", "ssh_url": None})
