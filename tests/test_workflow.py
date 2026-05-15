"""Tests for CP-017: Wire Workflow + Swap Entrypoint.

Tests cover:
1. _extract_selected helper
2. _noop_heartbeat_result helper
3. run_preflight_only function
4. run_create_workflow function (early exits)
5. Module exports
6. Exit code constants
7. configure_headnode function
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import daylily_ec.aws.cloudformation as cloudformation
import daylily_ec.aws.context as aws_context
import daylily_ec.aws.ec2 as aws_ec2
import daylily_ec.aws.heartbeat as aws_heartbeat
import daylily_ec.aws.iam as aws_iam
from daylily_ec.aws.ssm import SsmCommandFailedError, SsmCommandResult
import daylily_ec.aws.spot_pricing as spot_pricing
import daylily_ec.config.triplets as triplets
import daylily_ec.pcluster.monitor as pcluster_monitor
import daylily_ec.pcluster.runner as pcluster_runner
import daylily_ec.render.renderer as renderer
import daylily_ec.workflow.create_cluster as create_cluster_module
from daylily_ec.config.models import ConfigFile
from daylily_ec.state.models import CheckResult, CheckStatus, PreflightReport
from daylily_ec.state import store as state_store
from daylily_ec.workflow.create_cluster import (
    EXIT_AWS_FAILURE,
    EXIT_DRIFT,
    EXIT_SUCCESS,
    EXIT_TOOLCHAIN,
    EXIT_VALIDATION_FAILURE,
    _build_connection_command,
    _is_valid_fsx_size,
    _is_valid_headnode_instance_type,
    _extract_selected,
    _resolve_fsx_size,
    _resolve_headnode_instance_type,
    _noop_heartbeat_result,
    _require_values,
    _resolve_cluster_name,
    _resolve_config_value,
    _resolve_post_create_inputs,
    configure_headnode,
    make_repository_catalog_preflight_step,
    run_preflight,
    _validate_cluster_name,
)


# ── Exit code constants ─────────────────────────────────────────────────


class TestExitCodes:
    def test_exit_success(self):
        assert EXIT_SUCCESS == 0

    def test_exit_validation_failure(self):
        assert EXIT_VALIDATION_FAILURE == 1

    def test_exit_aws_failure(self):
        assert EXIT_AWS_FAILURE == 2

    def test_exit_drift(self):
        assert EXIT_DRIFT == 3

    def test_exit_toolchain(self):
        assert EXIT_TOOLCHAIN == 4


# ── _extract_selected ───────────────────────────────────────────────────


class TestExtractSelected:
    def test_found(self):
        report = PreflightReport(
            checks=[
                CheckResult(
                    id="s3.bucket_select",
                    status=CheckStatus.PASS,
                    details={"selected": "my-bucket-name"},
                ),
            ],
        )
        assert _extract_selected(report, "s3.bucket_select", "selected") == "my-bucket-name"

    def test_not_found_check(self):
        report = PreflightReport(
            checks=[
                CheckResult(id="other.check", status=CheckStatus.PASS),
            ],
        )
        assert _extract_selected(report, "s3.bucket_select", "selected") == ""

    def test_missing_detail_key(self):
        report = PreflightReport(
            checks=[
                CheckResult(
                    id="s3.bucket_select",
                    status=CheckStatus.PASS,
                    details={"region": "us-west-2"},
                ),
            ],
        )
        assert _extract_selected(report, "s3.bucket_select", "selected") == ""

    def test_empty_report(self):
        report = PreflightReport()
        assert _extract_selected(report, "any", "key") == ""


# ── _noop_heartbeat_result ──────────────────────────────────────────────


class TestNoopHeartbeatResult:
    def test_attributes(self):
        result = _noop_heartbeat_result()
        assert result.success is False
        assert result.topic_arn == ""
        assert result.schedule_name == ""
        assert result.role_arn == ""
        assert result.error == "skipped"


class TestRepositoryCatalogPreflight:
    def test_valid_checked_in_catalog_passes(self):
        catalog_path = (
            Path(__file__).resolve().parents[1] / "config" / ("daylily_available_repositories.yaml")
        )
        report = PreflightReport()

        result = make_repository_catalog_preflight_step(catalog_path)(report)

        check = result.checks[-1]
        assert check.id == "config.repository_catalog"
        assert check.status == CheckStatus.PASS
        assert check.details["path"] == str(catalog_path)
        assert check.details["repository_count"] >= 1
        assert check.details["command_count"] >= 1

    def test_malformed_catalog_fails_with_headnode_day_clone_context(self, tmp_path):
        catalog_path = tmp_path / "daylily_available_repositories.yaml"
        catalog_path.write_text(
            "command_catalog_version: [unterminated\n",
            encoding="utf-8",
        )
        report = PreflightReport()

        result = make_repository_catalog_preflight_step(catalog_path)(report)

        check = result.checks[-1]
        assert check.id == "config.repository_catalog"
        assert check.status == CheckStatus.FAIL
        assert check.details["path"] == str(catalog_path)
        assert "while parsing a flow sequence" in check.details["error"]
        assert "Headnode configuration would fail" in check.remediation
        assert "day-clone consumes this file" in check.remediation

    def test_malformed_catalog_short_circuits_preflight_pipeline(self, monkeypatch, tmp_path):
        catalog_path = tmp_path / "daylily_available_repositories.yaml"
        catalog_path.write_text(
            "command_catalog_version: [unterminated\n",
            encoding="utf-8",
        )
        called = False

        def later_step(report: PreflightReport) -> PreflightReport:
            nonlocal called
            called = True
            return report

        monkeypatch.setattr(
            create_cluster_module,
            "write_preflight_report",
            lambda report: None,
        )

        result = run_preflight(
            PreflightReport(),
            steps=[make_repository_catalog_preflight_step(catalog_path), later_step],
        )

        assert called is False
        assert result.failed_checks[0].id == "config.repository_catalog"


class TestWorkflowResolutionHelpers:
    def test_resolve_config_value_uses_default_non_interactive(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"cluster_name": ["PROMPTUSER", "majors-cluster", ""]},
                    "template_defaults": {},
                }
            }
        )

        value = _resolve_config_value(
            cfg,
            "cluster_name",
            "Cluster name",
            non_interactive=True,
            default_fallback="prod",
        )

        assert value == "majors-cluster"

    @patch("daylily_ec.workflow.create_cluster.typer.prompt", return_value="chosen-cluster")
    def test_resolve_config_value_prompts_interactively(self, mock_prompt):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"cluster_name": ["PROMPTUSER", "majors-cluster", ""]},
                    "template_defaults": {},
                }
            }
        )

        value = _resolve_config_value(
            cfg,
            "cluster_name",
            "Cluster name",
            non_interactive=False,
            default_fallback="prod",
        )

        assert value == "chosen-cluster"
        mock_prompt.assert_called_once()

    def test_require_values_reports_missing_labels(self):
        msg = _require_values({"bucket": "b", "public subnet": "", "IAM policy ARN": ""})
        assert msg == "Missing required values: public subnet, IAM policy ARN"

    def test_post_create_inputs_default_allowed_budget_user_is_ubuntu(self):
        cfg = ConfigFile.model_validate(
            {"ephemeral_cluster": {"config": {}, "template_defaults": {}}}
        )

        values = _resolve_post_create_inputs(
            cfg,
            non_interactive=True,
            budget_email_default="ops@example.com",
            allowed_budget_users_default="ubuntu",
        )

        assert values.allowed_budget_users == "ubuntu"

    def test_build_connection_command_uses_ssm_helper(self):
        cmd = _build_connection_command(
            "majors-cluster",
            region="us-west-2",
            profile="lsmc",
        )
        assert (
            cmd
            == "daylily-ssh-into-headnode --profile lsmc --region us-west-2 --cluster majors-cluster"
        )

    def test_is_valid_fsx_size(self):
        for size in ("1200", "2400", "4800", "7200", "9600", "12000", "14400"):
            assert _is_valid_fsx_size(size) is True
        for size in ("3600", "6000", "1250", "abc", "0"):
            assert _is_valid_fsx_size(size) is False

    def test_resolve_fsx_size_uses_valid_default(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"fsx_fs_size": ["PROMPTUSER", "4800", ""]},
                    "template_defaults": {},
                }
            }
        )

        assert _resolve_fsx_size(cfg, non_interactive=True) == "4800"

    @pytest.mark.parametrize("default_value", ["3600", "6000", "1250"])
    def test_resolve_fsx_size_rejects_invalid_default(self, default_value):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"fsx_fs_size": ["PROMPTUSER", default_value, ""]},
                    "template_defaults": {},
                }
            }
        )

        with patch("daylily_ec.workflow.create_cluster.typer.echo"):
            with pytest.raises(ValueError, match=rf"Invalid FSx size '{default_value}'"):
                _resolve_fsx_size(cfg, non_interactive=True)

    def test_resolve_fsx_size_prompts_with_menu(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"fsx_fs_size": ["PROMPTUSER", "", ""]},
                    "template_defaults": {},
                }
            }
        )

        with (
            patch(
                "daylily_ec.workflow.create_cluster.typer.prompt", return_value="2"
            ) as mock_prompt,
            patch("daylily_ec.workflow.create_cluster.typer.echo") as mock_echo,
        ):
            assert _resolve_fsx_size(cfg, non_interactive=False) == "2400"

        assert [call.args[0] for call in mock_echo.call_args_list] == [
            "Choose FSx Lustre file system size (GiB).",
            "Smallest allowed sizes:",
            "  [1] 1200",
            "  [2] 2400",
            "  [3] 4800",
            "  [4] 7200",
            "  [5] 9600",
            "  [6] 12000",
            "  [7] 14400",
        ]
        mock_prompt.assert_called_once()

    def test_resolve_fsx_size_accepts_explicit_valid_size(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"fsx_fs_size": ["PROMPTUSER", "", ""]},
                    "template_defaults": {},
                }
            }
        )

        with (
            patch(
                "daylily_ec.workflow.create_cluster.typer.prompt", return_value="9600"
            ) as mock_prompt,
            patch("daylily_ec.workflow.create_cluster.typer.echo"),
        ):
            assert _resolve_fsx_size(cfg, non_interactive=False) == "9600"

        mock_prompt.assert_called_once()

    def test_valid_headnode_instance_types_are_ordered_smallest_to_largest(self):
        assert _is_valid_headnode_instance_type("r7i.2xlarge") is True
        assert _is_valid_headnode_instance_type("r7i.16xlarge") is True
        assert _is_valid_headnode_instance_type("m5.xlarge") is False

    def test_resolve_headnode_instance_type_uses_approved_configured_value(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"headnode_instance_type": ["USESETVALUE", "", "r7i.8xlarge"]},
                    "template_defaults": {},
                }
            }
        )

        assert _resolve_headnode_instance_type(cfg, non_interactive=True) == "r7i.8xlarge"

    def test_resolve_headnode_instance_type_rejects_unapproved_value(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"headnode_instance_type": ["USESETVALUE", "", "m5.xlarge"]},
                    "template_defaults": {},
                }
            }
        )

        with pytest.raises(ValueError, match="approved headnode instance types"):
            _resolve_headnode_instance_type(cfg, non_interactive=True)

    def test_resolve_headnode_instance_type_prompts_with_approved_menu(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"headnode_instance_type": ["PROMPTUSER", "r7i.2xlarge", ""]},
                    "template_defaults": {},
                }
            }
        )

        with (
            patch(
                "daylily_ec.workflow.create_cluster.typer.prompt",
                return_value="3",
            ) as mock_prompt,
            patch("daylily_ec.workflow.create_cluster.typer.echo") as mock_echo,
        ):
            assert _resolve_headnode_instance_type(cfg, non_interactive=False) == "r7i.8xlarge"

        assert [call.args[0] for call in mock_echo.call_args_list] == [
            "Choose headnode instance type (approved types, smallest to largest).",
            "  [1] r7i.2xlarge (default)",
            "  [2] r7i.4xlarge",
            "  [3] r7i.8xlarge",
            "  [4] r7i.16xlarge",
        ]
        mock_prompt.assert_called_once()


class TestClusterNameValidation:
    @pytest.mark.parametrize(
        "cluster_name",
        ["frz-260509", "cluster1", "A2345", "a-1-b"],
    )
    def test_cluster_names_allow_numbers_after_first_character(self, cluster_name):
        assert _validate_cluster_name(cluster_name) == cluster_name

    @pytest.mark.parametrize(
        ("cluster_name", "message"),
        [
            ("260509-frz", "start with a letter"),
            ("frz_260509", "contain only letters, digits, and hyphens"),
            ("frz", "5-25 characters"),
            ("frz-260509-abcdefghijklmnop", "5-25 characters"),
        ],
    )
    def test_invalid_cluster_names_fail_with_actionable_rules(self, cluster_name, message):
        with pytest.raises(ValueError, match=message):
            _validate_cluster_name(cluster_name)

    def test_resolve_cluster_name_rejects_invalid_config_before_aws(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"cluster_name": ["USESETVALUE", "", "260509-frz"]},
                    "template_defaults": {},
                }
            }
        )

        with pytest.raises(ValueError, match="start with a letter"):
            _resolve_cluster_name(cfg, non_interactive=True)

    @patch("daylily_ec.aws.context.AWSContext.build")
    def test_create_workflow_rejects_invalid_cluster_name_before_aws(
        self, mock_build, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        config_path = tmp_path / "invalid_cluster.yaml"
        config_path.write_text(
            "\n".join(
                [
                    "ephemeral_cluster:",
                    "  config:",
                    "    cluster_name: [USESETVALUE, '', 260509-frz]",
                    "  template_defaults: {}",
                ]
            ),
            encoding="utf-8",
        )

        from daylily_ec.workflow.create_cluster import run_create_workflow

        rc = run_create_workflow(
            "us-west-2b",
            profile="test",
            config_path=str(config_path),
            non_interactive=True,
        )

        assert rc == EXIT_VALIDATION_FAILURE
        mock_build.assert_not_called()


# ── Module exports ──────────────────────────────────────────────────────


class TestWorkflowExports:
    def test_exports(self):
        import daylily_ec.workflow as wf

        assert hasattr(wf, "run_create_workflow")
        assert hasattr(wf, "run_preflight_only")
        assert hasattr(wf, "run_preflight")
        assert hasattr(wf, "should_abort")
        assert hasattr(wf, "exit_code_for")
        assert hasattr(wf, "EXIT_SUCCESS")
        assert hasattr(wf, "EXIT_VALIDATION_FAILURE")
        assert hasattr(wf, "EXIT_AWS_FAILURE")
        assert hasattr(wf, "EXIT_DRIFT")
        assert hasattr(wf, "EXIT_TOOLCHAIN")


# ── run_preflight_only — AWS context failure ────────────────────────────


class TestRunPreflightOnly:
    @patch("daylily_ec.aws.context.AWSContext.build")
    def test_aws_context_failure(self, mock_build, tmp_path, monkeypatch):
        """AWS context build failure returns EXIT_AWS_FAILURE."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.setenv("AWS_PROFILE", "test")
        mock_build.side_effect = RuntimeError("no creds")

        from daylily_ec.workflow.create_cluster import run_preflight_only

        rc = run_preflight_only("us-west-2b", profile="test")
        assert rc == EXIT_AWS_FAILURE


# ── run_create_workflow — AWS context failure ───────────────────────────


class TestRunCreateWorkflow:
    @patch("daylily_ec.aws.context.AWSContext.build")
    def test_aws_context_failure(self, mock_build, tmp_path, monkeypatch):
        """AWS context build failure returns EXIT_AWS_FAILURE."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.setenv("AWS_PROFILE", "test")
        mock_build.side_effect = RuntimeError("no creds")

        from daylily_ec.workflow.create_cluster import run_create_workflow

        rc = run_create_workflow("us-west-2b", profile="test", non_interactive=True)
        assert rc == EXIT_AWS_FAILURE

    def test_collects_budget_and_heartbeat_inputs_before_dry_run(self, tmp_path, monkeypatch):
        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=True,
            head_node_ip="54.1.2.3",
            say_available=False,
        )

        assert records["rc"] == EXIT_SUCCESS
        assert records["prompt_labels"] == [
            "Budget email",
            "Budget amount",
            "Global budget amount",
            "Allowed budget users",
            "Heartbeat email",
            "Heartbeat schedule",
            "Heartbeat scheduler role ARN (leave blank to skip)",
        ]

        dry_run_phase_index = records["events"].index(("phase", "DRY-RUN VALIDATION"))
        create_phase_index = records["events"].index(("phase", "CREATE CLUSTER"))
        resolve_role_index = records["events"].index(("resolve_scheduler_role", None))
        prompt_indices = [
            idx for idx, event in enumerate(records["events"]) if event[0] == "prompt"
        ]

        assert prompt_indices
        assert max(prompt_indices) < dry_run_phase_index
        assert create_phase_index < resolve_role_index
        assert records["global_budget_kwargs"]["email"] == "johnm@lsmc.com"
        assert records["global_budget_kwargs"]["amount"] == "200"
        assert records["global_budget_kwargs"]["allowed_users"] == "root"
        assert records["cluster_budget_kwargs"]["email"] == "johnm@lsmc.com"
        assert records["heartbeat_kwargs"]["email"] == "johnm@lsmc.com"
        assert records["heartbeat_kwargs"]["schedule_expression"] == "rate(60 minutes)"
        assert records["next_run_values"]["budget_email"] == "johnm@lsmc.com"
        assert records["next_run_values"]["heartbeat_email"] == "johnm@lsmc.com"
        assert records["next_run_values"]["heartbeat_schedule"] == "rate(60 minutes)"
        assert records["next_run_values"]["heartbeat_scheduler_role_arn"] == ""
        assert records["resolve_scheduler_role_kwargs"]["preconfigured"] == ""

    def test_prints_ssh_command_then_fin_and_runs_say_when_available(self, tmp_path, monkeypatch):
        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=True,
        )

        assert records["rc"] == EXIT_SUCCESS
        assert records["echoes"][-2:] == [
            "daylily-ssh-into-headnode --profile lsmc --region us-west-2 --cluster majors-cluster",
            "...fin!",
        ]
        assert records["subprocess_calls"] == [
            ["/bin/sh", "-lc", "command -v say >/dev/null 2>&1"],
            ["say", "Onward to daylily!"],
        ]

    def test_prints_describe_cluster_fallback_when_headnode_ip_is_missing(
        self, tmp_path, monkeypatch
    ):
        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=False,
        )

        assert records["rc"] == EXIT_SUCCESS
        assert records["echoes"][-2:] == [
            "daylily-ssh-into-headnode --profile lsmc --region us-west-2 --cluster majors-cluster",
            "...fin!",
        ]
        assert records["subprocess_calls"] == [["/bin/sh", "-lc", "command -v say >/dev/null 2>&1"]]


# ── configure_headnode ───────────────────────────────────────────────


class TestConfigureHeadnode:
    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    def test_success_path(self, mock_run_shell, mock_write_remote_text, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DAYLILY_EC_REPO_ROOT", raising=False)

        mock_run_shell.side_effect = [
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
        ]

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
        )
        assert ok is True
        assert mock_run_shell.call_count == 5
        assert [call.kwargs["timeout"] for call in mock_run_shell.call_args_list] == [
            None,
            None,
            None,
            None,
            None,
        ]
        tos_cmd = mock_run_shell.call_args_list[2].args[2]
        assert "conda tos accept --override-channels" in tos_cmd
        assert "https://repo.anaconda.com/pkgs/main" in tos_cmd
        assert "https://repo.anaconda.com/pkgs/r" in tos_cmd
        assert (
            "source ~/projects/daylily-ephemeral-cluster/activate"
            in mock_run_shell.call_args_list[3].args[2]
        )
        assert "bash -lc" in mock_run_shell.call_args_list[4].args[2]
        assert "script -q -c" in mock_run_shell.call_args_list[4].args[2]
        assert "whoami" in mock_run_shell.call_args_list[4].args[2]
        assert "stty -a" in mock_run_shell.call_args_list[4].args[2]
        assert "-ixon" in mock_run_shell.call_args_list[4].args[2]
        mock_write_remote_text.assert_not_called()

    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    def test_login_shell_validation_failure_is_fatal(
        self, mock_run_shell, mock_write_remote_text, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DAYLILY_EC_REPO_ROOT", raising=False)

        mock_run_shell.side_effect = [
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SsmCommandFailedError(
                "validation failed",
                SsmCommandResult(
                    command_id="cmd-1",
                    instance_id="i-abc123",
                    status="Failed",
                    response_code=1,
                    stdout="",
                    stderr="whoami: command not found",
                ),
            ),
        ]

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
        )
        assert ok is False
        assert mock_run_shell.call_count == 5
        mock_write_remote_text.assert_not_called()

    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    def test_conda_tos_acceptance_failure_is_fatal(
        self, mock_run_shell, mock_write_remote_text, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DAYLILY_EC_REPO_ROOT", raising=False)

        mock_run_shell.side_effect = [
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SsmCommandFailedError(
                "tos failed",
                SsmCommandResult(
                    command_id="cmd-1",
                    instance_id="i-abc123",
                    status="Failed",
                    response_code=1,
                    stdout="",
                    stderr="CondaToSNonInteractiveError",
                ),
            ),
        ]

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
        )
        assert ok is False
        assert mock_run_shell.call_count == 3
        mock_write_remote_text.assert_not_called()

    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    def test_step_failure_is_fatal(
        self, mock_run_shell, mock_write_remote_text, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DAYLILY_EC_REPO_ROOT", raising=False)

        mock_run_shell.side_effect = RuntimeError("boom")

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
        )
        assert ok is False
        mock_write_remote_text.assert_not_called()

    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    def test_repo_override_deployment_uses_remote_write(
        self, mock_run_shell, mock_write_remote_text, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DAYLILY_EC_REPO_ROOT", raising=False)

        mock_run_shell.side_effect = [
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
        ]

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
            repo_overrides={"daylily-omics-analysis": "feature/refactor"},
        )
        assert ok is True
        assert mock_run_shell.call_count == 5
        mock_write_remote_text.assert_called_once()

    @patch("daylily_ec.aws.ssm.write_remote_text", side_effect=RuntimeError("nope"))
    @patch("daylily_ec.aws.ssm.run_shell")
    def test_repo_override_write_failure_is_fatal(
        self, mock_run_shell, _mock_write_remote_text, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DAYLILY_EC_REPO_ROOT", raising=False)

        mock_run_shell.side_effect = [
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
        ]

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
            repo_overrides={"daylily-omics-analysis": "feature/refactor"},
        )
        assert ok is False

    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    def test_repo_override_requires_available_repo_config(
        self, mock_run_shell, mock_write_remote_text, tmp_path, monkeypatch
    ):
        import daylily_ec.resources as resources_module

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("DAYLILY_EC_REPO_ROOT", raising=False)
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "daylily_cli_global.yaml").write_text(
            "daylily: {}\n", encoding="utf-8"
        )
        monkeypatch.setattr(
            resources_module,
            "resource_path",
            lambda _rel: tmp_path / "missing_available_repositories.yaml",
        )

        mock_run_shell.side_effect = [
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
        ]

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
            repo_overrides={"daylily-omics-analysis": "feature/refactor"},
        )
        assert ok is False
        mock_write_remote_text.assert_not_called()

    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    @patch("daylily_ec.workflow.create_cluster.subprocess.run")
    def test_repo_checkout_uses_local_branch_and_refreshes_remote_checkout(
        self,
        mock_subprocess_run,
        mock_run_shell,
        mock_write_remote_text,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        monkeypatch.setenv("DAYLILY_EC_REPO_ROOT", str(repo_root))

        def fake_git_run(cmd, **_kwargs):
            if cmd == ["git", "-C", str(repo_root), "config", "--get", "remote.origin.url"]:
                return subprocess.CompletedProcess(cmd, 0, "https://example.com/daylily.git\n", "")
            if cmd == ["git", "-C", str(repo_root), "symbolic-ref", "--short", "HEAD"]:
                return subprocess.CompletedProcess(cmd, 0, "codex/ssh-to-ssm-refactor\n", "")
            if cmd == [
                "git",
                "-C",
                str(repo_root),
                "ls-remote",
                "--exit-code",
                "--heads",
                "origin",
                "codex/ssh-to-ssm-refactor",
            ]:
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    "abc\trefs/heads/codex/ssh-to-ssm-refactor\n",
                    "",
                )
            raise AssertionError(f"unexpected subprocess.run call: {cmd}")

        mock_subprocess_run.side_effect = fake_git_run
        mock_run_shell.side_effect = [
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
        ]

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
        )

        assert ok is True
        assert mock_run_shell.call_count == 5
        clone_cmd = mock_run_shell.call_args_list[0].args[2]
        assert "repo already cloned" not in clone_cmd
        assert "git clone https://example.com/daylily.git daylily-ephemeral-cluster" in clone_cmd
        assert "git fetch origin --tags --prune" in clone_cmd
        assert "git clean -fdx" in clone_cmd
        assert "git checkout -B daylily-managed origin/codex/ssh-to-ssm-refactor" in clone_cmd
        mock_write_remote_text.assert_not_called()

    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    @patch("daylily_ec.workflow.create_cluster.subprocess.run")
    @pytest.mark.parametrize(
        ("origin_url", "expected_url"),
        [
            (
                "git@github.com:Daylily-Informatics/daylily-ephemeral-cluster.git\n",
                "https://github.com/Daylily-Informatics/daylily-ephemeral-cluster.git",
            ),
            (
                "ssh://git@github.com/Daylily-Informatics/daylily-ephemeral-cluster.git\n",
                "https://github.com/Daylily-Informatics/daylily-ephemeral-cluster.git",
            ),
        ],
    )
    def test_repo_checkout_normalizes_github_ssh_origin_for_headnode_clone(
        self,
        mock_subprocess_run,
        mock_run_shell,
        mock_write_remote_text,
        origin_url,
        expected_url,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        monkeypatch.setenv("DAYLILY_EC_REPO_ROOT", str(repo_root))

        def fake_git_run(cmd, **_kwargs):
            if cmd == ["git", "-C", str(repo_root), "config", "--get", "remote.origin.url"]:
                return subprocess.CompletedProcess(cmd, 0, origin_url, "")
            if cmd == ["git", "-C", str(repo_root), "symbolic-ref", "--short", "HEAD"]:
                return subprocess.CompletedProcess(cmd, 0, "codex/https-headnode-clone\n", "")
            if cmd == [
                "git",
                "-C",
                str(repo_root),
                "ls-remote",
                "--exit-code",
                "--heads",
                "origin",
                "codex/https-headnode-clone",
            ]:
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    "abc\trefs/heads/codex/https-headnode-clone\n",
                    "",
                )
            raise AssertionError(f"unexpected subprocess.run call: {cmd}")

        mock_subprocess_run.side_effect = fake_git_run
        mock_run_shell.side_effect = [
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
            SimpleNamespace(stdout="", stderr=""),
        ]

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
        )

        assert ok is True
        clone_cmd = mock_run_shell.call_args_list[0].args[2]
        assert f"git clone {expected_url} daylily-ephemeral-cluster" in clone_cmd
        assert "git@github.com" not in clone_cmd
        assert "ssh://git@github.com" not in clone_cmd
        mock_write_remote_text.assert_not_called()

    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    @patch("daylily_ec.workflow.create_cluster.subprocess.run")
    def test_repo_checkout_rejects_unsupported_ssh_origin_for_headnode_clone(
        self,
        mock_subprocess_run,
        mock_run_shell,
        mock_write_remote_text,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        monkeypatch.setenv("DAYLILY_EC_REPO_ROOT", str(repo_root))

        def fake_git_run(cmd, **_kwargs):
            if cmd == ["git", "-C", str(repo_root), "config", "--get", "remote.origin.url"]:
                return subprocess.CompletedProcess(
                    cmd, 0, "git@gitlab.example.com:org/repo.git\n", ""
                )
            raise AssertionError(f"unexpected subprocess.run call: {cmd}")

        mock_subprocess_run.side_effect = fake_git_run

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
        )

        assert ok is False
        mock_run_shell.assert_not_called()
        mock_write_remote_text.assert_not_called()

    @patch("daylily_ec.aws.ssm.write_remote_text")
    @patch("daylily_ec.aws.ssm.run_shell")
    @patch("daylily_ec.workflow.create_cluster.subprocess.run")
    def test_repo_checkout_branch_must_be_published(
        self,
        mock_subprocess_run,
        mock_run_shell,
        mock_write_remote_text,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        monkeypatch.setenv("DAYLILY_EC_REPO_ROOT", str(repo_root))

        def fake_git_run(cmd, **_kwargs):
            if cmd == ["git", "-C", str(repo_root), "config", "--get", "remote.origin.url"]:
                return subprocess.CompletedProcess(cmd, 0, "https://example.com/daylily.git\n", "")
            if cmd == ["git", "-C", str(repo_root), "symbolic-ref", "--short", "HEAD"]:
                return subprocess.CompletedProcess(cmd, 0, "feature/local-only\n", "")
            if cmd == [
                "git",
                "-C",
                str(repo_root),
                "ls-remote",
                "--exit-code",
                "--heads",
                "origin",
                "feature/local-only",
            ]:
                return subprocess.CompletedProcess(cmd, 2, "", "fatal: not found")
            raise AssertionError(f"unexpected subprocess.run call: {cmd}")

        mock_subprocess_run.side_effect = fake_git_run

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="test",
        )

        assert ok is False
        mock_run_shell.assert_not_called()
        mock_write_remote_text.assert_not_called()


# ── configure_headnode export ────────────────────────────────────────


class TestConfigureHeadnodeExport:
    def test_exported_from_workflow(self):
        import daylily_ec.workflow as wf

        assert hasattr(wf, "configure_headnode")


def _build_workflow_config(template_path: Path) -> ConfigFile:
    return ConfigFile.model_validate(
        {
            "ephemeral_cluster": {
                "config": {
                    "cluster_name": ["USESETVALUE", "", "majors-cluster"],
                    "max_count_8I": ["USESETVALUE", "", "1"],
                    "max_count_128I": ["USESETVALUE", "", "1"],
                    "max_count_192I": ["USESETVALUE", "", "1"],
                    "cluster_template_yaml": ["USESETVALUE", "", str(template_path)],
                    "fsx_fs_size": ["USESETVALUE", "", "2400"],
                    "enable_detailed_monitoring": ["USESETVALUE", "", "false"],
                    "delete_local_root": ["USESETVALUE", "", "false"],
                    "auto_delete_fsx": ["USESETVALUE", "", "Delete"],
                    "enforce_budget": ["USESETVALUE", "", "true"],
                    "spot_instance_allocation_strategy": [
                        "USESETVALUE",
                        "",
                        "capacity-optimized",
                    ],
                    "headnode_instance_type": ["USESETVALUE", "", "r7i.2xlarge"],
                    "budget_email": ["PROMPTUSER", "johnm@lsmc.com", ""],
                    "budget_amount": ["PROMPTUSER", "200", ""],
                    "global_budget_amount": ["PROMPTUSER", "200", ""],
                    "allowed_budget_users": ["PROMPTUSER", "root", ""],
                    "heartbeat_email": ["PROMPTUSER", "johnm@lsmc.com", ""],
                    "heartbeat_schedule": ["PROMPTUSER", "rate(60 minutes)", ""],
                    "heartbeat_scheduler_role_arn": ["PROMPTUSER", "", ""],
                },
                "template_defaults": {},
            }
        }
    )


def _run_stubbed_create_workflow(
    tmp_path: Path,
    monkeypatch,
    *,
    interactive: bool,
    head_node_ip: str | None,
    say_available: bool,
) -> dict[str, object]:
    template_path = tmp_path / "template.yaml"
    template_path.write_text("Region: REGSUB_REGION\n", encoding="utf-8")

    records: dict[str, object] = {
        "events": [],
        "echoes": [],
        "prompt_labels": [],
        "subprocess_calls": [],
    }
    cfg = _build_workflow_config(template_path)

    class FakeAWSContext:
        profile = "lsmc"
        region = "us-west-2"
        account_id = "123456789012"
        iam_username = "root"
        caller_arn = "arn:aws:iam::123456789012:root"

        def __init__(self) -> None:
            shared_client = object()
            self._clients = {
                "ec2": shared_client,
                "iam": shared_client,
                "budgets": shared_client,
                "s3": shared_client,
                "sns": shared_client,
                "scheduler": shared_client,
            }

        def client(self, service_name: str):
            return self._clients[service_name]

    aws_ctx_instance = FakeAWSContext()

    def fake_build(_cls, region_az: str, profile: str | None = None):
        assert region_az == "us-west-2d"
        assert profile == "lsmc"
        return aws_ctx_instance

    def fake_prompt(label: str, default=None):
        _ = default
        records["prompt_labels"].append(label)
        records["events"].append(("prompt", label))
        answers = {
            "Budget email": "johnm@lsmc.com",
            "Budget amount": "200",
            "Global budget amount": "200",
            "Allowed budget users": "root",
            "Heartbeat email": "johnm@lsmc.com",
            "Heartbeat schedule": "rate(60 minutes)",
            "Heartbeat scheduler role ARN (leave blank to skip)": "",
        }
        return answers[label]

    def fake_run_preflight(report: PreflightReport, **_kwargs):
        report.checks.append(
            CheckResult(
                id="s3.bucket_select",
                status=CheckStatus.PASS,
                details={"selected": "bucket-a"},
            )
        )
        return report

    def fake_phase(title: str):
        records["events"].append(("phase", title))

    def fake_success_panel(title: str, body: str):
        records["events"].append(("success_panel", title))
        records["success_panel"] = (title, body)

    def fake_echo(message: str):
        records["echoes"].append(message)

    def fake_create_cluster(*_args, **_kwargs):
        records["events"].append(("create_cluster", None))
        return SimpleNamespace(success=True, returncode=0, stderr="", message="")

    def fake_resolve_scheduler_role(*_args, **kwargs):
        records["events"].append(("resolve_scheduler_role", None))
        records["resolve_scheduler_role_kwargs"] = kwargs
        return (
            "arn:aws:iam::123456789012:role/eventbridge-scheduler-to-sns",
            "existing_role:eventbridge-scheduler-to-sns",
        )

    def fake_ensure_global_budget(*_args, **kwargs):
        records["global_budget_kwargs"] = kwargs
        return "daylily-global"

    def fake_ensure_cluster_budget(*_args, **kwargs):
        records["cluster_budget_kwargs"] = kwargs
        return "da-us-west-2d-majors-cluster"

    def fake_ensure_heartbeat(*_args, **kwargs):
        records["heartbeat_kwargs"] = kwargs
        return SimpleNamespace(
            success=True,
            topic_arn="arn:aws:sns:us-west-2:123456789012:daylily",
            schedule_name="daylily-majors-cluster-heartbeat",
            role_arn=kwargs["role_arn"],
        )

    def fake_write_next_run_template(_cfg, final_values, dest):
        records["next_run_values"] = dict(final_values)
        Path(dest).write_text("next-run\n", encoding="utf-8")
        return Path(dest)

    def fake_subprocess_run(cmd, **kwargs):
        _ = kwargs
        records["subprocess_calls"].append(list(cmd))
        if cmd == ["/bin/sh", "-lc", "command -v say >/dev/null 2>&1"]:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0 if say_available else 1,
                stdout="",
                stderr="",
            )
        if cmd == ["say", "Onward to daylily!"]:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="",
                stderr="",
            )
        raise AssertionError(f"unexpected subprocess.run call: {cmd}")

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("DAY_CONTACT_EMAIL", "johnm@lsmc.com")
    monkeypatch.setattr(aws_context.AWSContext, "build", classmethod(fake_build))
    monkeypatch.setattr(triplets, "load_config", lambda _path: cfg)
    monkeypatch.setattr(create_cluster_module, "run_preflight", fake_run_preflight)
    monkeypatch.setattr(
        create_cluster_module,
        "should_abort",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        cloudformation,
        "ensure_pcluster_env_stack",
        lambda *_args, **_kwargs: SimpleNamespace(
            public_subnet_id="subnet-pub",
            private_subnet_id="subnet-priv",
            policy_arn="arn:policy:default",
        ),
    )
    monkeypatch.setattr(cloudformation, "derive_stack_name", lambda _region_az: "daylily-stack")
    monkeypatch.setattr(aws_ec2, "list_public_subnets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(aws_ec2, "list_private_subnets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        aws_ec2,
        "list_pcluster_tags_budget_policies",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        create_cluster_module,
        "configure_headnode",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(
        renderer,
        "write_init_artifacts",
        lambda *_args, **_kwargs: (
            str(tmp_path / "cluster.yaml.init"),
            str(tmp_path / "init-template.yaml"),
        ),
    )
    monkeypatch.setattr(spot_pricing, "apply_spot_prices", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        pcluster_runner,
        "dry_run_create",
        lambda *_args, **_kwargs: SimpleNamespace(success=True, message="", stderr=""),
    )
    monkeypatch.setattr(pcluster_runner, "should_break_after_dry_run", lambda: False)
    monkeypatch.setattr(pcluster_runner, "create_cluster", fake_create_cluster)
    monkeypatch.setattr(
        pcluster_monitor,
        "wait_for_creation",
        lambda *_args, **_kwargs: SimpleNamespace(
            success=True,
            elapsed_seconds=125.0,
            final_status="CREATE_COMPLETE",
            error="",
            head_node_ip=head_node_ip,
            head_node_instance_id="i-abc123",
        ),
    )
    import daylily_ec.aws.ssm as aws_ssm

    monkeypatch.setattr(aws_ssm, "wait_for_ssm_online", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(aws_iam, "resolve_scheduler_role", fake_resolve_scheduler_role)
    monkeypatch.setattr(aws_heartbeat, "ensure_heartbeat", fake_ensure_heartbeat)
    monkeypatch.setattr(create_cluster_module.ui, "phase", fake_phase)
    monkeypatch.setattr(create_cluster_module.ui, "step", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(create_cluster_module.ui, "ok", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(create_cluster_module.ui, "warn", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(create_cluster_module.ui, "info", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(create_cluster_module.ui, "detail", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(create_cluster_module.ui, "success_panel", fake_success_panel)
    monkeypatch.setattr(create_cluster_module.typer, "prompt", fake_prompt)
    monkeypatch.setattr(create_cluster_module.typer, "echo", fake_echo)
    monkeypatch.setattr(create_cluster_module.subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(triplets, "write_next_run_template", fake_write_next_run_template)
    monkeypatch.setattr(
        state_store,
        "write_state_record",
        lambda state: tmp_path / f"{state.cluster_name}.json",
    )
    monkeypatch.setattr(
        create_cluster_module,
        "write_state_record",
        lambda state: tmp_path / f"{state.cluster_name}.json",
    )
    monkeypatch.setattr(
        create_cluster_module,
        "_noop_heartbeat_result",
        lambda: SimpleNamespace(
            success=False,
            topic_arn="",
            schedule_name="",
            role_arn="",
            error="skipped",
        ),
    )

    import daylily_ec.aws.budgets as budgets

    monkeypatch.setattr(budgets, "ensure_global_budget", fake_ensure_global_budget)
    monkeypatch.setattr(budgets, "ensure_cluster_budget", fake_ensure_cluster_budget)

    records["rc"] = create_cluster_module.run_create_workflow(
        "us-west-2d",
        profile="lsmc",
        config_path=str(tmp_path / "config.yaml"),
        non_interactive=not interactive,
    )
    return records
