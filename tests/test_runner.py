"""Tests for daylily_ec.pcluster.runner — CP-013."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from daylily_ec.pcluster.runner import (
    DRY_RUN_SUCCESS_MESSAGE,
    PclusterResult,
    _run_pcluster,
    create_cluster,
    dry_run_create,
    should_break_after_dry_run,
)


# ── helpers ──────────────────────────────────────────────────────────────


def _completed(stdout: str = "", stderr: str = "", rc: int = 0):
    """Return a mock subprocess.CompletedProcess."""
    cp = MagicMock()
    cp.returncode = rc
    cp.stdout = stdout
    cp.stderr = stderr
    return cp


def _dry_run_ok_json() -> str:
    return json.dumps({"message": DRY_RUN_SUCCESS_MESSAGE})


def _dry_run_fail_json() -> str:
    return json.dumps(
        {"message": "Some validation error", "validationMessages": []}
    )


# ── TestConstants ────────────────────────────────────────────────────────


class TestConstants:
    def test_dry_run_message(self):
        assert "DryRun flag" in DRY_RUN_SUCCESS_MESSAGE


# ── TestPclusterResult ───────────────────────────────────────────────────


class TestPclusterResult:
    def test_defaults(self):
        r = PclusterResult(command="pcluster foo", returncode=0)
        assert r.success is False
        assert r.json_body == {}
        assert r.message == ""


# ── TestRunPcluster ──────────────────────────────────────────────────────


class TestRunPcluster:
    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_returns_parsed_json(self, mock_run):
        body = {"message": "ok", "extra": 1}
        mock_run.return_value = _completed(stdout=json.dumps(body))
        r = _run_pcluster(["list-clusters"])
        assert r.json_body == body
        assert r.message == "ok"
        assert r.returncode == 0

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_profile_injected(self, mock_run):
        mock_run.return_value = _completed()
        _run_pcluster(["list-clusters"], profile="myprof")
        env_used = mock_run.call_args.kwargs["env"]
        assert env_used["AWS_PROFILE"] == "myprof"

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("pcluster")
        r = _run_pcluster(["create-cluster"])
        assert r.returncode == 4
        assert "not found" in r.stderr

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_non_json_stdout(self, mock_run):
        mock_run.return_value = _completed(stdout="not json")
        r = _run_pcluster(["list-clusters"])
        assert r.json_body == {}


# ── TestDryRunCreate ─────────────────────────────────────────────────────


class TestDryRunCreate:
    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _completed(stdout=_dry_run_ok_json())
        r = dry_run_create("my-cluster", "/tmp/c.yaml", "us-west-2")
        assert r.success is True
        assert r.message == DRY_RUN_SUCCESS_MESSAGE

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_failure(self, mock_run):
        mock_run.return_value = _completed(stdout=_dry_run_fail_json(), rc=1)
        r = dry_run_create("my-cluster", "/tmp/c.yaml", "us-west-2")
        assert r.success is False

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_profile_passed(self, mock_run):
        mock_run.return_value = _completed(stdout=_dry_run_ok_json())
        dry_run_create("c", "/tmp/c.yaml", "us-west-2", profile="prof1")
        env_used = mock_run.call_args.kwargs["env"]
        assert env_used["AWS_PROFILE"] == "prof1"

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_command_args(self, mock_run):
        mock_run.return_value = _completed(stdout=_dry_run_ok_json())
        dry_run_create("my-cl", "/tmp/c.yaml", "us-east-1")
        cmd = mock_run.call_args.args[0]
        assert cmd == [
            "pcluster", "create-cluster",
            "-n", "my-cl",
            "-c", "/tmp/c.yaml",
            "--dryrun", "true",
            "--region", "us-east-1",
        ]


# ── TestShouldBreakAfterDryRun ───────────────────────────────────────────


class TestShouldBreakAfterDryRun:
    def test_break_when_set(self, monkeypatch):
        monkeypatch.setenv("DAY_BREAK", "1")
        assert should_break_after_dry_run() is True

    def test_no_break_when_unset(self, monkeypatch):
        monkeypatch.delenv("DAY_BREAK", raising=False)
        assert should_break_after_dry_run() is False

    def test_no_break_when_other_value(self, monkeypatch):
        monkeypatch.setenv("DAY_BREAK", "0")
        assert should_break_after_dry_run() is False


# ── TestCreateCluster ────────────────────────────────────────────────────


class TestCreateCluster:
    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _completed(
            stdout=json.dumps({"clusterName": "my-cl"})
        )
        r = create_cluster("my-cl", "/tmp/c.yaml", "us-west-2")
        assert r.success is True
        assert r.returncode == 0

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_failure(self, mock_run):
        mock_run.return_value = _completed(stderr="error", rc=1)
        r = create_cluster("my-cl", "/tmp/c.yaml", "us-west-2")
        assert r.success is False
        assert r.returncode == 1

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_command_args(self, mock_run):
        mock_run.return_value = _completed()
        create_cluster("cl1", "/tmp/c.yaml", "eu-west-1", profile="p")
        cmd = mock_run.call_args.args[0]
        assert cmd == [
            "pcluster", "create-cluster",
            "-n", "cl1",
            "-c", "/tmp/c.yaml",
            "--region", "eu-west-1",
        ]
        assert mock_run.call_args.kwargs["env"]["AWS_PROFILE"] == "p"

