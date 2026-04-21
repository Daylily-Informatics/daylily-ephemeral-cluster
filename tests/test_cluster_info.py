"""Tests for the cluster-info CLI subcommand."""

from __future__ import annotations

import json
from subprocess import CompletedProcess
from unittest.mock import patch

from typer.testing import CliRunner

import daylily_ec.cli as cli_module
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
    if isinstance(cmd, (list, tuple)) and "-c" in cmd:
        return _make_cp()
    if "list-clusters" in cmd:
        return _make_cp(stdout=LIST_CLUSTERS_JSON)
    if "describe-cluster" in cmd:
        name = cmd[cmd.index("-n") + 1] if "-n" in cmd else cmd[cmd.index("--cluster-name") + 1]
        if name == "alpha":
            return _make_cp(stdout=DESCRIBE_ALPHA)
        return _make_cp(stdout=DESCRIBE_BETA)
    raise ValueError(f"unexpected cmd: {cmd}")


def _activate_dayec_runtime(monkeypatch):
    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestClusterInfoTable:
    def test_table_output(self, monkeypatch):
        _activate_dayec_runtime(monkeypatch)
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        with patch("subprocess.run", side_effect=_side_effect_for_happy):
            result = runner.invoke(app, ["cluster-info", "--region", "us-west-2"])
        assert result.exit_code == 0
        assert "alpha" in result.stdout
        assert "beta" in result.stdout
        assert "CREATE_COMPLETE" in result.stdout
        assert "1.2.3.4" in result.stdout

    def test_json_output(self, monkeypatch):
        _activate_dayec_runtime(monkeypatch)
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        with patch("subprocess.run", side_effect=_side_effect_for_happy):
            result = runner.invoke(app, ["--json", "cluster-info", "--region", "us-west-2"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["region"] == "us-west-2"
        assert len(data["clusters"]) == 2
        assert data["clusters"][0]["name"] == "alpha"
        assert data["clusters"][0]["ip"] == "1.2.3.4"

    def test_cluster_list_json_output(self, monkeypatch):
        _activate_dayec_runtime(monkeypatch)
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        with patch("subprocess.run", side_effect=_side_effect_for_happy):
            result = runner.invoke(app, ["--json", "cluster", "list", "--region", "us-west-2"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["region"] == "us-west-2"
        assert data["clusters"][0]["name"] == "alpha"
        assert data["clusters"][0]["status"] == "CREATE_COMPLETE"

    def test_cluster_list_details_includes_headnode(self, monkeypatch):
        _activate_dayec_runtime(monkeypatch)
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        with patch("subprocess.run", side_effect=_side_effect_for_happy):
            result = runner.invoke(
                app,
                ["--json", "cluster", "list", "--region", "us-west-2", "--details"],
            )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["clusters"][0]["ip"] == "1.2.3.4"
        assert data["clusters"][0]["details"]["clusterName"] == "alpha"

    def test_cluster_describe_returns_full_payload(self, monkeypatch):
        _activate_dayec_runtime(monkeypatch)
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        with patch("subprocess.run", side_effect=_side_effect_for_happy):
            result = runner.invoke(
                app,
                [
                    "--json",
                    "cluster",
                    "describe",
                    "--region",
                    "us-west-2",
                    "--cluster",
                    "alpha",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["clusterName"] == "alpha"
        assert data["headNode"]["publicIpAddress"] == "1.2.3.4"

    def test_cluster_wait_polls_until_target_status(self, monkeypatch):
        _activate_dayec_runtime(monkeypatch)
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        responses = [
            _make_cp(stdout=json.dumps({"clusterName": "alpha", "clusterStatus": "CREATE_IN_PROGRESS"})),
            _make_cp(stdout=DESCRIBE_ALPHA),
        ]

        def side_effect(*args, **kwargs):
            cmd = kwargs.get("args") or args[0]
            if isinstance(cmd, (list, tuple)) and "-c" in cmd:
                return _make_cp()
            return responses.pop(0)

        monkeypatch.setattr(cli_module.time, "sleep", lambda _seconds: None)
        with patch("subprocess.run", side_effect=side_effect):
            result = runner.invoke(
                app,
                [
                    "cluster",
                    "wait",
                    "--region",
                    "us-west-2",
                    "--cluster",
                    "alpha",
                    "--poll-interval",
                    "1",
                ],
            )
        assert result.exit_code == 0
        assert "CREATE_COMPLETE" in result.stdout


class TestClusterInfoEdgeCases:
    def test_no_profile(self, monkeypatch):
        _activate_dayec_runtime(monkeypatch)
        monkeypatch.delenv("AWS_PROFILE", raising=False)
        result = runner.invoke(app, ["cluster-info", "--region", "us-west-2"])
        assert result.exit_code == 1

    def test_profile_from_flag(self, monkeypatch):
        _activate_dayec_runtime(monkeypatch)
        with patch("subprocess.run", side_effect=_side_effect_for_happy):
            result = runner.invoke(
                app, ["cluster-info", "--region", "us-west-2", "--profile", "my-prof"]
            )
        assert result.exit_code == 0
        assert "alpha" in result.stdout

    def test_pcluster_not_found(self, monkeypatch):
        _activate_dayec_runtime(monkeypatch)
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        def side_effect(*args, **kwargs):
            cmd = kwargs.get("args") or args[0]
            if isinstance(cmd, (list, tuple)) and "-c" in cmd:
                return _make_cp()
            raise FileNotFoundError("pcluster")

        with patch("subprocess.run", side_effect=side_effect):
            result = runner.invoke(app, ["cluster-info", "--region", "us-west-2"])
        assert result.exit_code == 1

    def test_no_clusters(self, monkeypatch):
        _activate_dayec_runtime(monkeypatch)
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        empty = _make_cp(stdout=json.dumps({"clusters": []}))
        with patch("subprocess.run", return_value=empty):
            result = runner.invoke(app, ["cluster-info", "--region", "us-west-2"])
        assert result.exit_code == 0
        assert "No clusters" in result.stdout

    def test_list_clusters_failure(self, monkeypatch):
        _activate_dayec_runtime(monkeypatch)
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        fail = _make_cp(rc=1, stderr="access denied")

        def side_effect(*args, **kwargs):
            cmd = kwargs.get("args") or args[0]
            if isinstance(cmd, (list, tuple)) and "-c" in cmd:
                return _make_cp()
            return fail

        with patch("subprocess.run", side_effect=side_effect):
            result = runner.invoke(app, ["cluster-info", "--region", "us-west-2"])
        assert result.exit_code == 1

    def test_describe_failure_still_shows_rows(self, monkeypatch):
        _activate_dayec_runtime(monkeypatch)
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        list_ok = _make_cp(stdout=json.dumps({"clusters": [{"clusterName": "c1"}]}))
        desc_fail = _make_cp(rc=1, stderr="timeout")

        def side_effect(*args, **kwargs):
            cmd = kwargs.get("args") or args[0]
            if isinstance(cmd, (list, tuple)) and "-c" in cmd:
                return _make_cp()
            if "list-clusters" in cmd:
                return list_ok
            return desc_fail

        with patch("subprocess.run", side_effect=side_effect):
            result = runner.invoke(app, ["--json", "cluster-info", "--region", "us-west-2"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["clusters"][0]["status"] == "ERROR"

    def test_bad_json_from_list(self, monkeypatch):
        _activate_dayec_runtime(monkeypatch)
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        bad = _make_cp(stdout="not-json{{")
        with patch("subprocess.run", return_value=bad):
            result = runner.invoke(app, ["cluster-info", "--region", "us-west-2"])
        assert result.exit_code == 1
