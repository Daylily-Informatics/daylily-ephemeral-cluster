"""Regression coverage for DYEC's strict project-local invocation context."""

from __future__ import annotations

import json
import os
from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace

import click
import pytest
import yaml
from typer.main import get_command
from typer.testing import CliRunner

import daylily_ec.cli as cli_module
from daylily_ec.cli import app
from daylily_ec.cli_context import (
    CONTEXT_FIELDS,
    CONTEXT_FILENAME,
    ContextConfigError,
    clear_local_context,
    load_local_context,
    update_local_context,
)

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[1]


def _activate_dayec_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")


def _write_context(path: Path, **values: object) -> None:
    (path / CONTEXT_FILENAME).write_text(
        yaml.safe_dump(values, sort_keys=False),
        encoding="utf-8",
    )


def _walk_commands(command: click.Command, path: tuple[str, ...] = ()):
    if isinstance(command, click.Group):
        for name, child in command.commands.items():
            yield from _walk_commands(child, (*path, name))
        return
    yield path, command


def test_context_module_lifecycle_overwrite_and_empty_file_removal(tmp_path: Path) -> None:
    context, affected, present = update_local_context(
        updates={
            "aws_profile": "local",
            "aws_region": "us-west-2",
            "aws_region_az": "us-west-2d",
            "cluster_admin_email": "operator@example.org",
        },
        cwd=tmp_path,
    )
    assert present is True
    assert affected == CONTEXT_FIELDS
    assert context.populated_values() == {
        "aws_profile": "local",
        "aws_region": "us-west-2",
        "aws_region_az": "us-west-2d",
        "cluster_admin_email": "operator@example.org",
    }

    context, affected, present = update_local_context(
        updates={"aws_profile": "replacement", "aws_region": "   "},
        cwd=tmp_path,
    )
    assert present is True
    assert affected == ("aws_profile", "aws_region")
    assert context.populated_values() == {
        "aws_profile": "replacement",
        "aws_region_az": "us-west-2d",
        "cluster_admin_email": "operator@example.org",
    }

    context, affected, present = clear_local_context(fields=(), cwd=tmp_path)
    assert affected == CONTEXT_FIELDS
    assert present is False
    assert context.populated_values() == {}
    assert not (tmp_path / CONTEXT_FILENAME).exists()


def test_set_and_unset_vars_preserve_unspecified_values_and_ignore_file(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        [
            "set-vars",
            "--profile",
            "local",
            "--region",
            "us-west-2",
            "--region-az",
            "us-west-2d",
            "--cluster-admin-email",
            "operator@example.org",
        ],
    )
    assert result.exit_code == 0, result.output
    assert yaml.safe_load((tmp_path / CONTEXT_FILENAME).read_text(encoding="utf-8")) == {
        "aws_profile": "local",
        "aws_region": "us-west-2",
        "aws_region_az": "us-west-2d",
        "cluster_admin_email": "operator@example.org",
    }

    result = runner.invoke(app, ["set-vars", "--profile", "replacement"])
    assert result.exit_code == 0, result.output
    context = load_local_context()
    assert context.aws_profile == "replacement"
    assert context.aws_region == "us-west-2"

    result = runner.invoke(app, ["set-vars", "--region", ""])
    assert result.exit_code == 0, result.output
    assert load_local_context().aws_region is None

    result = runner.invoke(app, ["unset-vars", "--profile", "--cluster-admin-email"])
    assert result.exit_code == 0, result.output
    context = load_local_context()
    assert context.aws_profile is None
    assert context.cluster_admin_email is None
    assert context.aws_region_az == "us-west-2d"

    result = runner.invoke(app, ["unset-vars"])
    assert result.exit_code == 0, result.output
    assert not (tmp_path / CONTEXT_FILENAME).exists()
    assert CONTEXT_FILENAME in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("aws_profile: [unterminated\n", "Invalid YAML"),
        ("unknown: value\n", "unsupported field"),
        ("aws_profile: 7\n", "must be a string"),
        ("aws_profile: null\n", "must be a string"),
    ],
)
def test_context_rejects_malformed_unknown_and_non_string_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    contents: str,
    message: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / CONTEXT_FILENAME).write_text(contents, encoding="utf-8")

    result = runner.invoke(app, ["set-vars", "--profile", "replacement"])
    assert result.exit_code == 2
    assert message in result.output
    with pytest.raises(ContextConfigError, match=message):
        load_local_context()


def test_dyec_environment_variables_are_not_read_or_written(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    for name, value in {
        "DYEC_AWS_PROFILE": "ignored-profile",
        "DYEC_AWS_REGION": "eu-west-1",
        "DYEC_AWS_REGION_AZ": "eu-west-1a",
        "DYEC_CLUSTER_ADMIN_EMAIL": "ignored@example.org",
    }.items():
        monkeypatch.setenv(name, value)
    context = load_local_context()
    assert context.populated_values() == {}

    _activate_dayec_runtime(monkeypatch)
    from daylily_ec.workflow import create_cluster

    calls: dict[str, object] = {}

    def fake_run_create_workflow(region_az: str, **kwargs) -> int:
        calls["region_az"] = region_az
        calls.update(kwargs)
        return 0

    monkeypatch.setattr(create_cluster, "run_create_workflow", fake_run_create_workflow)
    result = runner.invoke(app, ["create"])
    assert result.exit_code == 0, result.output
    assert calls["region_az"] == cli_module.DEFAULT_CREATE_REGION_AZ
    assert calls["profile"] is None
    assert calls["budget_email_fallback"] is None
    assert {
        name: os.environ[name]
        for name in (
            "DYEC_AWS_PROFILE",
            "DYEC_AWS_REGION",
            "DYEC_AWS_REGION_AZ",
            "DYEC_CLUSTER_ADMIN_EMAIL",
        )
    } == {
        "DYEC_AWS_PROFILE": "ignored-profile",
        "DYEC_AWS_REGION": "eu-west-1",
        "DYEC_AWS_REGION_AZ": "eu-west-1a",
        "DYEC_CLUSTER_ADMIN_EMAIL": "ignored@example.org",
    }


def test_local_context_precedence_fills_required_and_optional_command_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_context(
        tmp_path,
        aws_profile="local-profile",
        aws_region="us-west-2",
        aws_region_az="us-west-2d",
        cluster_admin_email="local@example.org",
    )
    _activate_dayec_runtime(monkeypatch)

    import daylily_ec.aws.pricing_snapshots as pricing_module
    from daylily_ec import run_mounts
    from daylily_ec.workflow import create_cluster

    create_calls: list[tuple[str, dict[str, object]]] = []
    mount_calls: list[dict[str, object]] = []
    validation_calls: list[dict[str, object]] = []
    pcluster_calls: list[tuple[list[str], str, str]] = []
    pricing_calls: list[dict[str, object]] = []

    def fake_run_create_workflow(region_az: str, **kwargs) -> int:
        create_calls.append((region_az, kwargs))
        return 0

    def fake_list_run_mounts(**kwargs):
        mount_calls.append(kwargs)
        return []

    def fake_validate(mode: str, **kwargs) -> None:
        validation_calls.append({"mode": mode, **kwargs})

    def fake_pcluster_json(argv, *, profile: str, region: str):
        pcluster_calls.append((argv, profile, region))
        return {"clusters": []}

    def fake_collect_pricing_snapshot(**kwargs):
        pricing_calls.append(kwargs)
        return SimpleNamespace(to_dict=lambda: {"ok": True})

    monkeypatch.setattr(create_cluster, "run_create_workflow", fake_run_create_workflow)
    monkeypatch.setattr(run_mounts, "list_run_mounts", fake_list_run_mounts)
    monkeypatch.setattr(cli_module, "_run_aws_validate_command", fake_validate)
    monkeypatch.setattr(cli_module, "_run_pcluster_json", fake_pcluster_json)
    monkeypatch.setattr(
        pricing_module,
        "collect_pricing_snapshot",
        fake_collect_pricing_snapshot,
    )

    result = runner.invoke(app, ["create"])
    assert result.exit_code == 0, result.output
    assert create_calls[-1] == (
        "us-west-2d",
        {
            "profile": "local-profile",
            "config_path": None,
            "cluster_type": "intel",
            "pass_on_warn": False,
            "debug": False,
            "non_interactive": False,
            "disable_budget_enforcement": False,
            "budget_project": None,
            "global_spot_max_cost": 9.99,
            "spot_cost_limit_pct": 1.70,
            "write_spot_pricing_warn_threshold": 8.0,
            "repo_overrides": None,
            "regional_cluster_cap": None,
            "acknowledge_regional_cap_increase": False,
            "acknowledge_regional_cap_risk": False,
            "slurm_accounting": "on",
            "fail_on_sacct_error": False,
            "create_slurm_accounting_if_missing": False,
            "acknowledge_slurm_accounting_create_cost": False,
            "budget_email_override": None,
            "budget_email_fallback": "local@example.org",
        },
    )

    result = runner.invoke(app, ["mounts", "list"])
    assert result.exit_code == 0, result.output
    assert mount_calls == [
        {
            "cluster_name": None,
            "fsx_file_system_id": None,
            "region": "us-west-2",
            "profile": "local-profile",
            "purpose": None,
        }
    ]

    result = runner.invoke(app, ["aws", "validate", "all"])
    assert result.exit_code == 0, result.output
    assert validation_calls == [
        {
            "mode": "all",
            "profile": "local-profile",
            "region_az": "us-west-2d",
            "config": None,
            "gap_analysis": None,
        }
    ]

    result = runner.invoke(app, ["cluster", "list"])
    assert result.exit_code == 0, result.output
    assert pcluster_calls == [
        (["pcluster", "list-clusters", "--region", "us-west-2"], "local-profile", "us-west-2")
    ]

    result = runner.invoke(
        app,
        ["pricing", "snapshot", "--partition", "i192", "--target-capacity-vcpus", "1"],
    )
    assert result.exit_code == 0, result.output
    assert pricing_calls == [
        {
            "regions": ["us-west-2"],
            "partitions": ["i192"],
            "cluster_config_path": None,
            "profile": "local-profile",
            "target_capacity_vcpus": 1,
        }
    ]

    result = runner.invoke(
        app,
        [
            "create",
            "--profile",
            "explicit-profile",
            "--region-az",
            "us-east-1a",
            "--admin-email",
            "explicit@example.org",
        ],
    )
    assert result.exit_code == 0, result.output
    explicit_region_az, explicit_kwargs = create_calls[-1]
    assert explicit_region_az == "us-east-1a"
    assert explicit_kwargs["profile"] == "explicit-profile"
    assert explicit_kwargs["budget_email_override"] == "explicit@example.org"
    assert explicit_kwargs["budget_email_fallback"] == "local@example.org"


def test_required_options_keep_the_prior_missing_option_failure_without_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DYEC_AWS_REGION_AZ", "ignored-region-az")
    monkeypatch.setenv("DYEC_AWS_PROFILE", "ignored-profile")

    preflight = runner.invoke(app, ["preflight"])
    assert preflight.exit_code == 2
    assert "Missing option --region-az" in preflight.output

    validate = runner.invoke(app, ["aws", "validate", "all"])
    assert validate.exit_code == 2
    assert "Missing option --profile" in validate.output


def test_optional_profile_preserves_existing_aws_profile_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _activate_dayec_runtime(monkeypatch)
    monkeypatch.setenv("AWS_PROFILE", "legacy-profile")
    monkeypatch.setenv("DYEC_AWS_PROFILE", "ignored-profile")
    calls: list[dict[str, object]] = []

    def fake_run(args, **kwargs):
        calls.append(kwargs["env"])
        return CompletedProcess(args=args, returncode=0, stdout='{"clusters": []}', stderr="")

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)
    result = runner.invoke(app, ["cluster-info", "--region", "us-west-2"])
    assert result.exit_code == 0, result.output
    assert calls[0]["AWS_PROFILE"] == "legacy-profile"


def test_every_registered_aws_context_option_is_wrapped() -> None:
    root = get_command(app)
    field_for_name = {
        "profile": "aws_profile",
        "region": "aws_region",
        "regions": "aws_region",
        "region_az": "aws_region_az",
    }
    for path, command in _walk_commands(root):
        if path in {("set-vars",), ("unset-vars",)}:
            continue
        specs = getattr(command.callback, "__dyec_context_specs__", ())
        wrapped_fields = {parameter: field for parameter, field, *_rest in specs}
        for option in command.params:
            if not isinstance(option, click.Option):
                continue
            if not {"--profile", "--region", "--region-az"}.intersection(option.opts):
                continue
            assert option.required is False, path
            assert wrapped_fields[option.name] == field_for_name[option.name], path


def test_root_verbose_precedes_json_stdout_and_reports_local_context(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_context(
        tmp_path,
        aws_profile="local-profile",
        aws_region="us-west-2",
        aws_region_az="  ",
        cluster_admin_email="operator@example.org",
    )

    result = runner.invoke(app, ["-v", "--json", "info"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["Pinned DayOA Version"] == "15.0.6"
    assert result.output.index("DYEC verbose:") < result.output.index("{")
    assert f"PWD: {tmp_path}" in result.stderr
    assert "Project path:" in result.stderr
    assert "Executable:" in result.stderr
    assert "Version:" in result.stderr
    assert f"Local context: {tmp_path / CONTEXT_FILENAME} (present)" in result.stderr
    assert "aws_profile: local-profile" in result.stderr
    assert "aws_region: us-west-2" in result.stderr
    assert "aws_region_az: unset" in result.stderr
    assert "cluster_admin_email: operator@example.org" in result.stderr
