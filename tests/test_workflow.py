"""Tests for CP-017: Wire Workflow + Swap Entrypoint.

Tests cover:
1. _extract_selected helper
2. _noop_heartbeat_result helper
3. run_preflight_only function
4. run_create_workflow function (early exits)
5. Module exports
6. Exit code constants
"""

from __future__ import annotations

from unittest.mock import patch

from daylily_ec.state.models import CheckResult, CheckStatus, PreflightReport
from daylily_ec.workflow.create_cluster import (
    EXIT_AWS_FAILURE,
    EXIT_DRIFT,
    EXIT_SUCCESS,
    EXIT_TOOLCHAIN,
    EXIT_VALIDATION_FAILURE,
    _extract_selected,
    _noop_heartbeat_result,
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

        rc = run_create_workflow("us-west-2b", profile="test")
        assert rc == EXIT_AWS_FAILURE

