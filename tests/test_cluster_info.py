"""Tests for the cluster-info CLI subcommand."""

from __future__ import annotations

import json
from subprocess import CompletedProcess
from unittest.mock import patch

from typer.testing import CliRunner

import daylily_ec.cli as cli_module
from daylily_ec.aws.ssm import SsmCommandFailedError, SsmCommandResult
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
    "creationTime": "2026-04-21T06:51:02.985Z",
    "lastUpdatedTime": "2026-04-21T07:10:03.000Z",
    "headNode": {
        "publicIpAddress": "1.2.3.4",
        "instanceId": "i-alpha",
        "launchTime": "2026-04-21T07:23:41.000Z",
    },
})

DESCRIBE_BETA = json.dumps({
    "clusterName": "beta",
    "clusterStatus": "CREATE_IN_PROGRESS",
    "creationTime": "2026-04-21T08:00:00.000Z",
    "lastUpdatedTime": "2026-04-21T08:05:00.000Z",
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


def _patch_headnode_config_check(monkeypatch, *, configured: bool = True):
    import daylily_ec.aws.ssm as ssm_module

    scripts: list[str] = []

    def fake_run_shell(_instance_id, _region, script, **_kwargs):
        scripts.append(script)
        if configured:
            return object()
        raise SsmCommandFailedError(
            "not configured",
            SsmCommandResult(
                command_id="cmd-1",
                instance_id="i-alpha",
                status="Failed",
                response_code=1,
                stdout="",
                stderr="day-clone: command not found",
            ),
        )

    monkeypatch.setattr(ssm_module, "run_shell", fake_run_shell)
    return scripts


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
        scripts = _patch_headnode_config_check(monkeypatch)
        with patch("subprocess.run", side_effect=_side_effect_for_happy) as mock_run:
            result = runner.invoke(app, ["--json", "cluster", "list", "--region", "us-west-2"])
        assert result.exit_code == 0
        describe_calls = [
            call
            for call in mock_run.call_args_list
            if "describe-cluster" in (call.kwargs.get("args") or call.args[0])
        ]
        assert len(describe_calls) == 2
        data = json.loads(result.stdout)
        assert data["region"] == "us-west-2"
        assert data["clusters"][0]["name"] == "alpha"
        assert data["clusters"][0]["status"] == "CREATE_COMPLETE"
        assert data["clusters"][0]["created_at"] == "2026-04-21T06:51:02.985Z"
        assert data["clusters"][0]["updated_at"] == "2026-04-21T07:10:03.000Z"
        assert data["clusters"][0]["headnode_launched_at"] == "2026-04-21T07:23:41.000Z"
        assert data["clusters"][0]["ip"] == "1.2.3.4"
        assert data["clusters"][0]["instance_id"] == "i-alpha"
        assert data["clusters"][0]["headnode_configured"] is True
        assert data["clusters"][0]["headnode_configured_text"] == "YES"
        assert "details" not in data["clusters"][0]
        assert data["clusters"][1]["headnode_configured"] is None
        assert data["clusters"][1]["headnode_configured_text"] == "N/A"
        assert len(scripts) == 1
        assert "day-clone --list" in scripts[0]

    def test_cluster_list_reports_unconfigured_headnode(self, monkeypatch):
        _activate_dayec_runtime(monkeypatch)
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        _patch_headnode_config_check(monkeypatch, configured=False)
        with patch("subprocess.run", side_effect=_side_effect_for_happy):
            result = runner.invoke(app, ["--json", "cluster", "list", "--region", "us-west-2"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["clusters"][0]["headnode_configured"] is False
        assert data["clusters"][0]["headnode_configured_text"] == "NO"
        assert "day-clone: command not found" in data["clusters"][0]["headnode_config_error"]

    def test_cluster_list_table_includes_describe_datetimes_and_ip(self, monkeypatch):
        _activate_dayec_runtime(monkeypatch)
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        _patch_headnode_config_check(monkeypatch)
        with patch("subprocess.run", side_effect=_side_effect_for_happy):
            result = runner.invoke(app, ["cluster", "list", "--region", "us-west-2"])
        assert result.exit_code == 0
        assert "HEADNODE_CONFIGURED" in result.stdout
        assert "YES" in result.stdout
        assert "CREATED_AT" in result.stdout
        assert "UPDATED_AT" in result.stdout
        assert "HEADNODE_LAUNCHED_AT" in result.stdout
        assert "2026-04-21T06:51:02.985Z" in result.stdout
        assert "2026-04-21T07:10:03.000Z" in result.stdout
        assert "2026-04-21T07:23:41.000Z" in result.stdout
        assert "1.2.3.4" in result.stdout

    def test_cluster_list_details_includes_headnode(self, monkeypatch):
        _activate_dayec_runtime(monkeypatch)
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        _patch_headnode_config_check(monkeypatch)
        with patch("subprocess.run", side_effect=_side_effect_for_happy):
            result = runner.invoke(
                app,
                ["--json", "cluster", "list", "--region", "us-west-2", "--details"],
            )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["clusters"][0]["ip"] == "1.2.3.4"
        assert data["clusters"][0]["instance_id"] == "i-alpha"
        assert data["clusters"][0]["created_at"] == "2026-04-21T06:51:02.985Z"
        assert data["clusters"][0]["headnode_configured_text"] == "YES"
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

    def test_cluster_list_failure_reports_pcluster_stdout_message(self, monkeypatch):
        _activate_dayec_runtime(monkeypatch)
        monkeypatch.setenv("AWS_PROFILE", "typo-profile")
        fail = _make_cp(
            stdout=json.dumps({"message": "Unexpected fatal exception."}),
            stderr="/path/to/pcluster/common.py:20: UserWarning: pkg_resources is deprecated",
            rc=1,
        )

        def side_effect(*args, **kwargs):
            cmd = kwargs.get("args") or args[0]
            if isinstance(cmd, (list, tuple)) and "-c" in cmd:
                return _make_cp()
            return fail

        with patch("subprocess.run", side_effect=side_effect):
            result = runner.invoke(app, ["cluster", "list", "--region", "us-west-2"])
        assert result.exit_code == 1
        assert "Unexpected fatal exception." in result.output
