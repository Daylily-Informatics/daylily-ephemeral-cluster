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
from unittest.mock import MagicMock, patch

import daylily_ec.aws.cloudformation as cloudformation
import daylily_ec.aws.context as aws_context
import daylily_ec.aws.ec2 as aws_ec2
import daylily_ec.aws.heartbeat as aws_heartbeat
import daylily_ec.aws.iam as aws_iam
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

    def test_collects_budget_and_heartbeat_inputs_before_dry_run(
        self, tmp_path, monkeypatch
    ):
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
        assert (
            records["heartbeat_kwargs"]["schedule_expression"] == "rate(60 minutes)"
        )
        assert records["next_run_values"]["budget_email"] == "johnm@lsmc.com"
        assert records["next_run_values"]["heartbeat_email"] == "johnm@lsmc.com"
        assert records["next_run_values"]["heartbeat_schedule"] == "rate(60 minutes)"
        assert records["next_run_values"]["heartbeat_scheduler_role_arn"] == ""
        assert records["resolve_scheduler_role_kwargs"]["preconfigured"] == ""

    def test_prints_ssh_command_then_fin_and_runs_say_when_available(
        self, tmp_path, monkeypatch
    ):
        records = _run_stubbed_create_workflow(
            tmp_path,
            monkeypatch,
            interactive=False,
            head_node_ip="54.1.2.3",
            say_available=True,
        )

        assert records["rc"] == EXIT_SUCCESS
        assert records["echoes"][-2:] == [
            "ssh -i ~/.ssh/daykey.pem ubuntu@54.1.2.3",
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
            head_node_ip=None,
            say_available=False,
        )

        assert records["rc"] == EXIT_SUCCESS
        assert records["echoes"][-2:] == [
            "pcluster describe-cluster -n majors-cluster --region us-west-2",
            "...fin!",
        ]
        assert records["subprocess_calls"] == [
            ["/bin/sh", "-lc", "command -v say >/dev/null 2>&1"]
        ]



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
                    "headnode_instance_type": ["USESETVALUE", "", "m5.xlarge"],
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
    monkeypatch.setattr(
        cloudformation, "derive_stack_name", lambda _region_az: "daylily-stack"
    )
    monkeypatch.setattr(aws_ec2, "list_public_subnets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(aws_ec2, "list_private_subnets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        aws_ec2,
        "list_pcluster_tags_budget_policies",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        create_cluster_module,
        "_resolve_ssh_keypair",
        lambda *_args, **_kwargs: "daykey",
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
        ),
    )
    monkeypatch.setattr(create_cluster_module, "configure_headnode", lambda **_kwargs: True)
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
    monkeypatch.setattr(
        triplets, "write_next_run_template", fake_write_next_run_template
    )
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
