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
from unittest.mock import MagicMock, patch

from daylily_ec.config.models import ConfigFile
from daylily_ec.state.models import CheckResult, CheckStatus, PreflightReport
from daylily_ec.workflow.create_cluster import (
    EXIT_AWS_FAILURE,
    EXIT_DRIFT,
    EXIT_SUCCESS,
    EXIT_TOOLCHAIN,
    EXIT_VALIDATION_FAILURE,
    _is_valid_fsx_size,
    _extract_selected,
    _resolve_fsx_size,
    _noop_heartbeat_result,
    _require_values,
    _resolve_config_value,
    _resolve_ssh_keypair,
    _ssh_cmd,
    configure_headnode,
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

    def test_resolve_ssh_keypair_auto_selects_single_candidate(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        pem = tmp_path / ".ssh" / "only-key.pem"
        pem.parent.mkdir(parents=True, exist_ok=True)
        pem.write_text("fake pem")

        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"ssh_key_name": ["PROMPTUSER", "", ""]},
                    "template_defaults": {},
                }
            }
        )
        ec2 = MagicMock()
        ec2.describe_key_pairs.return_value = {"KeyPairs": [{"KeyName": "only-key"}]}

        value = _resolve_ssh_keypair(cfg, ec2_client=ec2, non_interactive=True)
        assert value == "only-key"

    def test_require_values_reports_missing_labels(self):
        msg = _require_values(
            {"bucket": "b", "SSH keypair": "", "IAM policy ARN": ""}
        )
        assert msg == "Missing required values: SSH keypair, IAM policy ARN"

    def test_is_valid_fsx_size(self):
        assert _is_valid_fsx_size("1200") is True
        assert _is_valid_fsx_size("6000") is True
        assert _is_valid_fsx_size("1250") is False
        assert _is_valid_fsx_size("abc") is False
        assert _is_valid_fsx_size("0") is False

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

    def test_resolve_fsx_size_rejects_invalid_default(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"fsx_fs_size": ["PROMPTUSER", "1250", ""]},
                    "template_defaults": {},
                }
            }
        )

        with patch("daylily_ec.workflow.create_cluster.typer.echo"):
            try:
                _resolve_fsx_size(cfg, non_interactive=True)
            except ValueError as exc:
                assert "Invalid FSx size '1250'" in str(exc)
            else:
                raise AssertionError("Expected ValueError")

    @patch("daylily_ec.workflow.create_cluster.typer.prompt", return_value="2")
    def test_resolve_fsx_size_prompts_with_menu(self, mock_prompt):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {"fsx_fs_size": ["PROMPTUSER", "", ""]},
                    "template_defaults": {},
                }
            }
        )

        assert _resolve_fsx_size(cfg, non_interactive=False) == "2400"
        mock_prompt.assert_called_once()


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



# ── _ssh_cmd helper ──────────────────────────────────────────────────


class TestSshCmd:
    @patch("daylily_ec.workflow.create_cluster.subprocess.run")
    def test_ssh_cmd_builds_correct_command(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="ok", stderr="",
        )
        result = _ssh_cmd("/tmp/key.pem", "1.2.3.4", "echo hello", timeout=10)
        assert result.returncode == 0
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ssh"
        assert "-i" in cmd
        assert "/tmp/key.pem" in cmd
        assert "ubuntu@1.2.3.4" in cmd
        assert "echo hello" in cmd


# ── configure_headnode ───────────────────────────────────────────────


class TestConfigureHeadnode:
    @patch("daylily_ec.workflow.create_cluster.subprocess.run")
    def test_pem_not_found(self, mock_run, tmp_path):
        """Returns False when PEM file does not exist."""
        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_ip="1.2.3.4",
            keypair="nonexistent-key",
            region="us-west-2",
            profile="test",
        )
        assert ok is False
        mock_run.assert_not_called()

    @patch("daylily_ec.workflow.create_cluster.subprocess.run")
    @patch("daylily_ec.workflow.create_cluster.Path")
    def test_success_path(self, mock_path_cls, mock_run, tmp_path):
        """Happy path: all SSH steps succeed."""
        # Make PEM path exist
        pem = tmp_path / ".ssh" / "test-key.pem"
        pem.parent.mkdir(parents=True, exist_ok=True)
        pem.write_text("fake-pem")

        # Config file
        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = cfg_dir / "daylily_cli_global.yaml"
        cfg_file.write_text(
            "daylily:\n"
            "  git_ephemeral_cluster_repo_tag: '0.7.601'\n"
            "  git_ephemeral_cluster_repo: https://github.com/test/repo.git\n"
        )

        # Mock Path to resolve to our tmp paths
        def path_side_effect(arg):
            if isinstance(arg, str) and arg == "config/daylily_cli_global.yaml":
                return cfg_file
            # Return a real Path for other calls
            from pathlib import Path as RealPath

            return RealPath(arg)

        mock_path_cls.side_effect = path_side_effect
        mock_path_cls.home.return_value = tmp_path

        # All SSH commands succeed; verify returns day-clone output
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="Available repositories:\n- repo1\n", stderr="",
        )

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_ip="1.2.3.4",
            keypair="test-key",
            region="us-west-2",
            profile="test",
        )
        assert ok is True
        # 5 setup steps + 1 verify = 6 subprocess.run calls
        assert mock_run.call_count == 6

    @patch("daylily_ec.workflow.create_cluster.subprocess.run")
    @patch("daylily_ec.workflow.create_cluster.Path")
    def test_ssh_step_failure_continues(self, mock_path_cls, mock_run, tmp_path):
        """Individual SSH step failure does not abort — remaining steps still run."""
        pem = tmp_path / ".ssh" / "test-key.pem"
        pem.parent.mkdir(parents=True, exist_ok=True)
        pem.write_text("fake-pem")

        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = cfg_dir / "daylily_cli_global.yaml"
        cfg_file.write_text(
            "daylily:\n"
            "  git_ephemeral_cluster_repo_tag: main\n"
            "  git_ephemeral_cluster_repo: https://github.com/test/repo.git\n"
        )

        def path_side_effect(arg):
            if isinstance(arg, str) and arg == "config/daylily_cli_global.yaml":
                return cfg_file
            from pathlib import Path as RealPath

            return RealPath(arg)

        mock_path_cls.side_effect = path_side_effect
        mock_path_cls.home.return_value = tmp_path

        # First call fails, rest succeed
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="err"),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr=""),
            subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="Available repositories:\n", stderr="",
            ),
        ]

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_ip="1.2.3.4",
            keypair="test-key",
            region="us-west-2",
            profile="test",
        )
        # Still returns True — individual failures are non-fatal
        assert ok is True
        assert mock_run.call_count == 6

    @patch("daylily_ec.workflow.create_cluster.subprocess.run")
    @patch("daylily_ec.workflow.create_cluster.Path")
    def test_timeout_continues(self, mock_path_cls, mock_run, tmp_path):
        """SSH timeout on a step does not abort remaining steps."""
        pem = tmp_path / ".ssh" / "test-key.pem"
        pem.parent.mkdir(parents=True, exist_ok=True)
        pem.write_text("fake-pem")

        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = cfg_dir / "daylily_cli_global.yaml"
        cfg_file.write_text(
            "daylily:\n"
            "  git_ephemeral_cluster_repo_tag: main\n"
            "  git_ephemeral_cluster_repo: https://github.com/test/repo.git\n"
        )

        def path_side_effect(arg):
            if isinstance(arg, str) and arg == "config/daylily_cli_global.yaml":
                return cfg_file
            from pathlib import Path as RealPath

            return RealPath(arg)

        mock_path_cls.side_effect = path_side_effect
        mock_path_cls.home.return_value = tmp_path

        # Second call times out, rest succeed
        ok_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="ok", stderr="",
        )
        mock_run.side_effect = [
            ok_result,
            subprocess.TimeoutExpired(cmd="ssh", timeout=300),
            ok_result,
            ok_result,
            ok_result,
            subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="Available repositories:\n", stderr="",
            ),
        ]

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_ip="1.2.3.4",
            keypair="test-key",
            region="us-west-2",
            profile="test",
        )
        assert ok is True
        assert mock_run.call_count == 6

    @patch("daylily_ec.workflow.create_cluster.subprocess.run")
    def test_global_config_not_found(self, mock_run, tmp_path, monkeypatch):
        """Falls back to packaged config when local/global config is missing."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)

        pem = tmp_path / ".ssh" / "test-key.pem"
        pem.parent.mkdir(parents=True, exist_ok=True)
        pem.write_text("fake-pem")

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="repositories", stderr="",
        )

        ok = configure_headnode(
            cluster_name="test-cluster",
            head_node_ip="1.2.3.4",
            keypair="test-key",
            region="us-west-2",
            profile="test",
        )
        assert ok is True
        assert mock_run.call_count >= 1


# ── configure_headnode export ────────────────────────────────────────


class TestConfigureHeadnodeExport:
    def test_exported_from_workflow(self):
        import daylily_ec.workflow as wf

        assert hasattr(wf, "configure_headnode")
