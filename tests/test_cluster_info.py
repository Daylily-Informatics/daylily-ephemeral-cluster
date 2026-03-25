"""Tests for the cluster-info CLI subcommand."""

from __future__ import annotations

import json
from subprocess import CompletedProcess
from unittest.mock import patch

from typer.testing import CliRunner

from daylily_ec.cli import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

LIST_CLUSTERS_JSON = json.dumps({
    "clusters": [
        {"clusterName": "alpha", "clusterStatus": "CREATE_COMPLETE"},
        {"clusterName": "beta", "clusterStatus": "CREATE_IN_PROGRESS"},
    ]
})

DESCRIBE_ALPHA = json.dumps({
    "clusterName": "alpha",
    "clusterStatus": "CREATE_COMPLETE",
    "headNode": {"publicIpAddress": "1.2.3.4"},
})

DESCRIBE_BETA = json.dumps({
    "clusterName": "beta",
    "clusterStatus": "CREATE_IN_PROGRESS",
    "headNode": {},
})


def _make_cp(stdout: str = "", stderr: str = "", rc: int = 0) -> CompletedProcess:
    return CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)


def _side_effect_for_happy(*_args, **kwargs):
    """Route subprocess.run calls to list or describe based on argv."""
    cmd = kwargs.get("args") or _args[0]
    if "list-clusters" in cmd:
        return _make_cp(stdout=LIST_CLUSTERS_JSON)
    if "describe-cluster" in cmd:
        name = cmd[cmd.index("-n") + 1]
        if name == "alpha":
            return _make_cp(stdout=DESCRIBE_ALPHA)
        return _make_cp(stdout=DESCRIBE_BETA)
    raise ValueError(f"unexpected cmd: {cmd}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestClusterInfoTable:
    def test_table_output(self, monkeypatch):
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        with patch("subprocess.run", side_effect=_side_effect_for_happy):
            result = runner.invoke(app, ["cluster-info", "--region", "us-west-2"])
        assert result.exit_code == 0
        assert "alpha" in result.stdout
        assert "beta" in result.stdout
        assert "CREATE_COMPLETE" in result.stdout
        assert "1.2.3.4" in result.stdout

    def test_json_output(self, monkeypatch):
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        with patch("subprocess.run", side_effect=_side_effect_for_happy):
            result = runner.invoke(app, ["cluster-info", "--region", "us-west-2", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["region"] == "us-west-2"
        assert len(data["clusters"]) == 2
        assert data["clusters"][0]["name"] == "alpha"
        assert data["clusters"][0]["ip"] == "1.2.3.4"


class TestClusterInfoEdgeCases:
    def test_no_profile(self, monkeypatch):
        monkeypatch.delenv("AWS_PROFILE", raising=False)
        result = runner.invoke(app, ["cluster-info", "--region", "us-west-2"])
        assert result.exit_code == 1

    def test_profile_from_flag(self):
        with patch("subprocess.run", side_effect=_side_effect_for_happy):
            result = runner.invoke(
                app, ["cluster-info", "--region", "us-west-2", "--profile", "my-prof"]
            )
        assert result.exit_code == 0
        assert "alpha" in result.stdout

    def test_pcluster_not_found(self, monkeypatch):
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        with patch("subprocess.run", side_effect=FileNotFoundError("pcluster")):
            result = runner.invoke(app, ["cluster-info", "--region", "us-west-2"])
        assert result.exit_code == 1

    def test_no_clusters(self, monkeypatch):
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        empty = _make_cp(stdout=json.dumps({"clusters": []}))
        with patch("subprocess.run", return_value=empty):
            result = runner.invoke(app, ["cluster-info", "--region", "us-west-2"])
        assert result.exit_code == 0
        assert "No clusters" in result.stdout

    def test_list_clusters_failure(self, monkeypatch):
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        fail = _make_cp(rc=1, stderr="access denied")
        with patch("subprocess.run", return_value=fail):
            result = runner.invoke(app, ["cluster-info", "--region", "us-west-2"])
        assert result.exit_code == 1

    def test_describe_failure_still_shows_rows(self, monkeypatch):
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        list_ok = _make_cp(stdout=json.dumps({"clusters": [{"clusterName": "c1"}]}))
        desc_fail = _make_cp(rc=1, stderr="timeout")

        def side_effect(*args, **kwargs):
            cmd = kwargs.get("args") or args[0]
            if "list-clusters" in cmd:
                return list_ok
            return desc_fail

        with patch("subprocess.run", side_effect=side_effect):
            result = runner.invoke(app, ["cluster-info", "--region", "us-west-2", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["clusters"][0]["status"] == "ERROR"

    def test_bad_json_from_list(self, monkeypatch):
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        bad = _make_cp(stdout="not-json{{")
        with patch("subprocess.run", return_value=bad):
            result = runner.invoke(app, ["cluster-info", "--region", "us-west-2"])
        assert result.exit_code == 1

