"""Tests for daylily_ec.pcluster.runner — CP-013."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from daylily_ec.pcluster.runner import (
    DRY_RUN_SUCCESS_MESSAGE,
    PclusterResult,
    _run_pcluster,
    create_cluster,
    delete_cluster,
    describe_cluster,
    describe_compute_fleet,
    dry_run_create,
    list_clusters,
    should_break_after_dry_run,
    update_cluster,
    update_compute_fleet,
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
    return json.dumps({"message": "Some validation error", "validationMessages": []})


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
    def test_explicit_backport_executable(self, mock_run):
        mock_run.return_value = _completed()
        _run_pcluster(["list-clusters"], executable="/opt/daylily/pcluster/bin/pcluster")
        assert mock_run.call_args.args[0][0] == "/opt/daylily/pcluster/bin/pcluster"

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

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_non_object_json_stdout(self, mock_run):
        mock_run.return_value = _completed(stdout="[]")
        r = _run_pcluster(["list-clusters"])
        assert r.json_body == {}


# ── TestListClusters ─────────────────────────────────────────────────────


class TestListClusters:
    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_uses_active_executable_profile_and_region(self, mock_run):
        mock_run.return_value = _completed(
            stdout=json.dumps(
                {
                    "clusters": [
                        {
                            "clusterName": "alpha",
                            "clusterStatus": "CREATE_COMPLETE",
                            "cloudformationStackArn": "not-retained",
                        }
                    ]
                }
            )
        )

        result = list_clusters(
            "us-west-2",
            profile="lsmc",
            executable="/opt/daylily/pcluster/bin/pcluster",
        )

        assert result.success is True
        assert result.json_body == {
            "clusters": [
                {
                    "clusterName": "alpha",
                    "clusterStatus": "CREATE_COMPLETE",
                }
            ]
        }
        assert mock_run.call_args.args[0] == [
            "/opt/daylily/pcluster/bin/pcluster",
            "list-clusters",
            "--region",
            "us-west-2",
        ]
        assert mock_run.call_args.kwargs["env"]["AWS_PROFILE"] == "lsmc"

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_paginates_until_next_token_is_absent(self, mock_run):
        mock_run.side_effect = [
            _completed(
                stdout=json.dumps(
                    {
                        "clusters": [
                            {
                                "clusterName": "alpha",
                                "clusterStatus": "CREATE_COMPLETE",
                            }
                        ],
                        "nextToken": "page-2",
                    }
                )
            ),
            _completed(
                stdout=json.dumps(
                    {
                        "clusters": [
                            {
                                "clusterName": "beta",
                                "clusterStatus": "CREATE_IN_PROGRESS",
                            }
                        ]
                    }
                )
            ),
        ]

        result = list_clusters("us-west-2")

        assert result.success is True
        assert [record["clusterName"] for record in result.json_body["clusters"]] == [
            "alpha",
            "beta",
        ]
        assert mock_run.call_args_list[1].args[0] == [
            "pcluster",
            "list-clusters",
            "--region",
            "us-west-2",
            "--next-token",
            "page-2",
        ]

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_fails_closed_when_list_command_fails(self, mock_run):
        mock_run.return_value = _completed(stderr="access denied", rc=2)

        result = list_clusters("us-west-2")

        assert result.success is False
        assert result.returncode == 2
        assert result.message == "pcluster list-clusters failed with exit code 2"
        assert result.json_body == {}

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_fails_closed_on_malformed_json(self, mock_run):
        mock_run.return_value = _completed(stdout="not-json")

        result = list_clusters("us-west-2")

        assert result.success is False
        assert result.message == "pcluster list-clusters returned malformed JSON"

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_fails_closed_on_malformed_record(self, mock_run):
        mock_run.return_value = _completed(
            stdout=json.dumps({"clusters": [{"clusterName": "alpha"}]})
        )

        result = list_clusters("us-west-2")

        assert result.success is False
        assert "clusterStatus" in result.message


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
            "pcluster",
            "create-cluster",
            "-n",
            "my-cl",
            "-c",
            "/tmp/c.yaml",
            "--dryrun",
            "true",
            "--region",
            "us-east-1",
        ]

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_explicit_backport_executable(self, mock_run):
        mock_run.return_value = _completed(stdout=_dry_run_ok_json())
        dry_run_create(
            "my-cl",
            "/tmp/c.yaml",
            "us-east-1",
            executable="/opt/daylily/pcluster/bin/pcluster",
        )
        assert mock_run.call_args.args[0][0] == "/opt/daylily/pcluster/bin/pcluster"


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
        mock_run.return_value = _completed(stdout=json.dumps({"clusterName": "my-cl"}))
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
            "pcluster",
            "create-cluster",
            "-n",
            "cl1",
            "-c",
            "/tmp/c.yaml",
            "--region",
            "eu-west-1",
        ]
        assert mock_run.call_args.kwargs["env"]["AWS_PROFILE"] == "p"


class TestDescribeAndUpdateCluster:
    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_describe_cluster(self, mock_run):
        mock_run.return_value = _completed(stdout=json.dumps({"clusterStatus": "CREATE_COMPLETE"}))

        result = describe_cluster("cl1", "us-west-2", profile="p")

        assert result.success is True
        assert mock_run.call_args.args[0] == [
            "pcluster",
            "describe-cluster",
            "-n",
            "cl1",
            "--region",
            "us-west-2",
        ]

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_describe_compute_fleet(self, mock_run):
        mock_run.return_value = _completed(stdout=json.dumps({"status": "STOPPED"}))

        result = describe_compute_fleet("cl1", "us-west-2")

        assert result.success is True
        assert "describe-compute-fleet" in mock_run.call_args.args[0]

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_update_cluster_dry_run_requires_exact_success_message(self, mock_run):
        # The LSMC ParallelCluster fork returns rc=1 for a successful update
        # dry run, so the exact AWS success message is authoritative here just
        # as it is for create-cluster dry runs.
        mock_run.return_value = _completed(stdout=_dry_run_ok_json(), rc=1)

        result = update_cluster(
            "cl1",
            "/tmp/update.yaml",
            "us-west-2",
            profile="p",
            dry_run=True,
        )

        assert result.success is True
        assert result.returncode == 1
        assert mock_run.call_args.args[0] == [
            "pcluster",
            "update-cluster",
            "-n",
            "cl1",
            "-c",
            "/tmp/update.yaml",
            "--dryrun",
            "true",
            "--region",
            "us-west-2",
        ]

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_update_cluster_submit_uses_false_dry_run(self, mock_run):
        mock_run.return_value = _completed(stdout=json.dumps({"clusterName": "cl1"}))

        result = update_cluster("cl1", "/tmp/update.yaml", "us-west-2")

        assert result.success is True
        assert mock_run.call_args.args[0][-2:] == ["--region", "us-west-2"]
        assert mock_run.call_args.args[0][6:8] == ["--dryrun", "false"]

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_update_cluster_dry_run_rejects_noncanonical_message_at_rc_zero(self, mock_run):
        mock_run.return_value = _completed(stdout=_dry_run_fail_json(), rc=0)

        result = update_cluster(
            "cl1",
            "/tmp/update.yaml",
            "us-west-2",
            dry_run=True,
        )

        assert result.success is False
        assert result.returncode == 0


class TestUpdateComputeFleet:
    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_stop_request_forwards_cluster_region_profile_and_executable(self, mock_run):
        mock_run.return_value = _completed(stdout=json.dumps({"status": "STOP_REQUESTED"}))

        result = update_compute_fleet(
            "cl1",
            "STOP_REQUESTED",
            "us-west-2",
            profile="lsmc",
            executable="/opt/daylily/pcluster/bin/pcluster",
        )

        assert result.success is True
        assert mock_run.call_args.args[0] == [
            "/opt/daylily/pcluster/bin/pcluster",
            "update-compute-fleet",
            "-n",
            "cl1",
            "--status",
            "STOP_REQUESTED",
            "--region",
            "us-west-2",
        ]
        assert mock_run.call_args.kwargs["env"]["AWS_PROFILE"] == "lsmc"

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_start_request_is_supported(self, mock_run):
        mock_run.return_value = _completed(stdout=json.dumps({"status": "START_REQUESTED"}))

        result = update_compute_fleet("cl1", "START_REQUESTED", "us-east-1")

        assert result.success is True

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_command_failure_is_explicit(self, mock_run):
        mock_run.return_value = _completed(stderr="transition rejected", rc=2)

        result = update_compute_fleet("cl1", "STOP_REQUESTED", "us-west-2")

        assert result.success is False
        assert result.returncode == 2
        assert result.stderr == "transition rejected"

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_rejects_non_request_status_before_invocation(self, mock_run):
        for status in ("RUNNING", "STOPPED", "stopped", ""):
            try:
                update_compute_fleet("cl1", status, "us-west-2")
            except ValueError as exc:
                assert "expected exactly" in str(exc)
            else:
                raise AssertionError(f"Expected {status!r} to be rejected")

        mock_run.assert_not_called()


class TestDeleteCluster:
    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = _completed(stdout=json.dumps({"clusterName": "my-cl"}))
        r = delete_cluster("my-cl", "us-west-2")
        assert r.success is True
        assert r.returncode == 0

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_failure(self, mock_run):
        mock_run.return_value = _completed(stderr="error", rc=1)
        r = delete_cluster("my-cl", "us-west-2")
        assert r.success is False
        assert r.returncode == 1

    @patch("daylily_ec.pcluster.runner.subprocess.run")
    def test_command_args(self, mock_run):
        mock_run.return_value = _completed()
        delete_cluster("cl1", "eu-west-1", profile="p")
        cmd = mock_run.call_args.args[0]
        assert cmd == [
            "pcluster",
            "delete-cluster",
            "-n",
            "cl1",
            "--region",
            "eu-west-1",
        ]
        assert mock_run.call_args.kwargs["env"]["AWS_PROFILE"] == "p"
