"""Tests for daylily_ec.pcluster.monitor — CP-014."""

from __future__ import annotations

import json as _json
from unittest.mock import MagicMock, patch

from daylily_ec.pcluster.monitor import (
    DEFAULT_FLEET_TIMEOUT,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_UPDATE_TIMEOUT,
    DELETE_STATUS_FAILED,
    LifecycleMonitorResult,
    MAX_CONSECUTIVE_FAILURES,
    STATUS_COMPLETE,
    STATUS_IN_PROGRESS,
    MonitorResult,
    get_compute_fleet_status,
    get_cluster_details,
    get_cluster_status,
    wait_for_cluster_update,
    wait_for_compute_fleet,
    wait_for_deletion,
    wait_for_creation,
)
from daylily_ec.pcluster.runner import PclusterResult

# ── helpers ──────────────────────────────────────────────────────────────


def _completed(stdout: str = "", stderr: str = "", rc: int = 0):
    cp = MagicMock()
    cp.returncode = rc
    cp.stdout = stdout
    cp.stderr = stderr
    return cp


def _noop_sleep(_: float) -> None:
    """Replacement for time.sleep in tests."""


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def time(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


# ── TestConstants ────────────────────────────────────────────────────────


class TestConstants:
    def test_status_in_progress(self):
        assert STATUS_IN_PROGRESS == "CREATE_IN_PROGRESS"

    def test_status_complete(self):
        assert STATUS_COMPLETE == "CREATE_COMPLETE"

    def test_max_failures(self):
        assert MAX_CONSECUTIVE_FAILURES == 5

    def test_poll_interval(self):
        assert DEFAULT_POLL_INTERVAL == 30.0

    def test_lifecycle_timeouts(self):
        assert DEFAULT_FLEET_TIMEOUT == 20 * 60
        assert DEFAULT_UPDATE_TIMEOUT == 90 * 60


# ── TestMonitorResult ────────────────────────────────────────────────────


class TestMonitorResult:
    def test_defaults(self):
        r = MonitorResult(final_status="X", elapsed_seconds=1.0, success=False)
        assert r.consecutive_failures == 0
        assert r.error == ""
        assert r.head_node_ip is None
        assert r.head_node_instance_id is None

    def test_head_node_fields(self):
        r = MonitorResult(
            final_status="CREATE_COMPLETE",
            elapsed_seconds=60.0,
            success=True,
            head_node_ip="1.2.3.4",
            head_node_instance_id="i-abc123",
        )
        assert r.head_node_ip == "1.2.3.4"
        assert r.head_node_instance_id == "i-abc123"

    def test_lifecycle_result_defaults_to_unsafe(self):
        result = LifecycleMonitorResult(
            final_status="UPDATE_FAILED",
            elapsed_seconds=10,
            success=False,
            outcome="indeterminate_failure",
        )

        assert result.safe_to_restore_fleet is False


# ── TestGetClusterStatus ─────────────────────────────────────────────────


class TestGetClusterStatus:
    @patch("daylily_ec.pcluster.monitor.subprocess.run")
    def test_returns_status(self, mock_run):
        mock_run.return_value = _completed(stdout='"CREATE_COMPLETE"')
        assert get_cluster_status("cl", "us-west-2") == STATUS_COMPLETE

    @patch("daylily_ec.pcluster.monitor.subprocess.run")
    def test_nonzero_returns_none(self, mock_run):
        mock_run.return_value = _completed(rc=1, stderr="error")
        assert get_cluster_status("cl", "us-west-2") is None

    @patch("daylily_ec.pcluster.monitor.subprocess.run")
    def test_profile_injected(self, mock_run):
        mock_run.return_value = _completed(stdout='"CREATE_IN_PROGRESS"')
        get_cluster_status("cl", "us-west-2", profile="myprof")
        env = mock_run.call_args.kwargs["env"]
        assert env["AWS_PROFILE"] == "myprof"

    @patch("daylily_ec.pcluster.monitor.subprocess.run")
    def test_not_found_returns_none(self, mock_run):
        mock_run.side_effect = FileNotFoundError("pcluster")
        assert get_cluster_status("cl", "us-west-2") is None

    @patch("daylily_ec.pcluster.monitor.subprocess.run")
    def test_non_json_stdout(self, mock_run):
        mock_run.return_value = _completed(stdout="CREATE_COMPLETE")
        result = get_cluster_status("cl", "us-west-2")
        assert result == "CREATE_COMPLETE"


# ── TestGetClusterDetails ────────────────────────────────────────────────


class TestGetClusterDetails:
    @patch("daylily_ec.pcluster.monitor.subprocess.run")
    def test_returns_parsed_json(self, mock_run):
        payload = {
            "clusterStatus": "CREATE_COMPLETE",
            "headNode": {
                "publicIpAddress": "1.2.3.4",
                "instanceId": "i-abc",
            },
        }
        mock_run.return_value = _completed(stdout=_json.dumps(payload))
        result = get_cluster_details("cl", "us-west-2")
        assert result["headNode"]["publicIpAddress"] == "1.2.3.4"

    @patch("daylily_ec.pcluster.monitor.subprocess.run")
    def test_nonzero_returns_empty_dict(self, mock_run):
        mock_run.return_value = _completed(rc=1, stderr="err")
        assert get_cluster_details("cl", "us-west-2") == {}

    @patch("daylily_ec.pcluster.monitor.subprocess.run")
    def test_not_found_returns_empty_dict(self, mock_run):
        mock_run.side_effect = FileNotFoundError("pcluster")
        assert get_cluster_details("cl", "us-west-2") == {}

    @patch("daylily_ec.pcluster.monitor.subprocess.run")
    def test_profile_injected(self, mock_run):
        mock_run.return_value = _completed(stdout="{}")
        get_cluster_details("cl", "us-west-2", profile="myprof")
        env = mock_run.call_args.kwargs["env"]
        assert env["AWS_PROFILE"] == "myprof"


class TestGetComputeFleetStatus:
    @patch("daylily_ec.pcluster.runner.describe_compute_fleet")
    def test_returns_exact_status_and_forwards_identity(self, mock_describe):
        mock_describe.return_value = PclusterResult(
            command="pcluster describe-compute-fleet",
            returncode=0,
            json_body={"status": "STOPPED"},
            success=True,
        )

        status = get_compute_fleet_status(
            "cl",
            "us-west-2",
            profile="lsmc",
            executable="/opt/daylily/pcluster/bin/pcluster",
        )

        assert status == "STOPPED"
        mock_describe.assert_called_once_with(
            "cl",
            "us-west-2",
            profile="lsmc",
            executable="/opt/daylily/pcluster/bin/pcluster",
        )

    @patch("daylily_ec.pcluster.runner.describe_compute_fleet")
    def test_returns_none_for_failure_or_malformed_status(self, mock_describe):
        mock_describe.return_value = PclusterResult(
            command="pcluster describe-compute-fleet",
            returncode=1,
        )
        assert get_compute_fleet_status("cl", "us-west-2") is None

        mock_describe.return_value = PclusterResult(
            command="pcluster describe-compute-fleet",
            returncode=0,
            json_body={"status": 12},
            success=True,
        )
        assert get_compute_fleet_status("cl", "us-west-2") is None


# ── TestWaitForCreation ──────────────────────────────────────────────────


class TestWaitForCreation:
    @patch("daylily_ec.pcluster.monitor.get_cluster_details")
    @patch("daylily_ec.pcluster.monitor.get_cluster_status")
    def test_immediate_complete(self, mock_status, mock_details):
        mock_status.return_value = STATUS_COMPLETE
        mock_details.return_value = {
            "headNode": {
                "publicIpAddress": "5.6.7.8",
                "instanceId": "i-xyz",
            },
        }
        r = wait_for_creation("cl", "us-west-2", _sleep_fn=_noop_sleep)
        assert r.success is True
        assert r.final_status == STATUS_COMPLETE
        assert r.head_node_ip == "5.6.7.8"
        assert r.head_node_instance_id == "i-xyz"

    @patch("daylily_ec.pcluster.monitor.get_cluster_details")
    @patch("daylily_ec.pcluster.monitor.get_cluster_status")
    def test_in_progress_then_complete(self, mock_status, mock_details):
        mock_status.side_effect = [
            STATUS_IN_PROGRESS,
            STATUS_IN_PROGRESS,
            STATUS_COMPLETE,
        ]
        mock_details.return_value = {"headNode": {}}
        r = wait_for_creation("cl", "us-west-2", poll_interval=0.01, _sleep_fn=_noop_sleep)
        assert r.success is True
        assert mock_status.call_count == 3

    @patch("daylily_ec.pcluster.monitor.get_cluster_status")
    def test_consecutive_failures_abort(self, mock_status):
        mock_status.return_value = None
        r = wait_for_creation("cl", "us-west-2", max_failures=3, _sleep_fn=_noop_sleep)
        assert r.success is False
        assert r.consecutive_failures == 3
        assert "3" in r.error

    @patch("daylily_ec.pcluster.monitor.get_cluster_details")
    @patch("daylily_ec.pcluster.monitor.get_cluster_status")
    def test_failure_resets_on_progress(self, mock_status, mock_details):
        mock_status.side_effect = [
            None,
            None,
            STATUS_IN_PROGRESS,
            STATUS_COMPLETE,
        ]
        mock_details.return_value = {"headNode": {}}
        r = wait_for_creation("cl", "us-west-2", max_failures=5, _sleep_fn=_noop_sleep)
        assert r.success is True

    @patch("daylily_ec.pcluster.monitor.get_cluster_details")
    @patch("daylily_ec.pcluster.monitor.get_cluster_status")
    def test_unexpected_status_fails(self, mock_status, mock_details):
        mock_status.return_value = "CREATE_FAILED"
        mock_details.return_value = {
            "failures": [
                {
                    "failureCode": "HeadNodeBootstrapFailure",
                    "failureReason": "Failed to set up the head node.",
                }
            ]
        }
        r = wait_for_creation("cl", "us-west-2", _sleep_fn=_noop_sleep)
        assert r.success is False
        assert r.final_status == "CREATE_FAILED"
        assert "unexpected" in r.error.lower()
        assert "HeadNodeBootstrapFailure" in r.error
        assert "Failed to set up the head node" in r.error

    @patch("daylily_ec.pcluster.monitor.get_cluster_details")
    @patch("daylily_ec.pcluster.monitor.get_cluster_status")
    def test_profile_passed(self, mock_status, mock_details):
        mock_status.return_value = STATUS_COMPLETE
        mock_details.return_value = {"headNode": {}}
        wait_for_creation("cl", "us-west-2", profile="p", _sleep_fn=_noop_sleep)
        mock_status.assert_called_with("cl", "us-west-2", profile="p")

    @patch("daylily_ec.pcluster.monitor.get_cluster_details")
    @patch("daylily_ec.pcluster.monitor.get_cluster_status")
    def test_backport_executable_passed(self, mock_status, mock_details):
        mock_status.return_value = STATUS_COMPLETE
        mock_details.return_value = {"headNode": {}}
        executable = "/opt/daylily/pcluster/bin/pcluster"
        wait_for_creation(
            "cl",
            "us-west-2",
            executable=executable,
            _sleep_fn=_noop_sleep,
        )
        mock_status.assert_called_with(
            "cl",
            "us-west-2",
            profile=None,
            executable=executable,
        )
        mock_details.assert_called_with(
            "cl",
            "us-west-2",
            profile=None,
            executable=executable,
        )


class TestWaitForComputeFleet:
    def test_stop_progress_reaches_exact_target(self):
        status = MagicMock(side_effect=["RUNNING", "STOP_REQUESTED", "STOPPING", "STOPPED"])

        result = wait_for_compute_fleet(
            "cl",
            "us-west-2",
            "STOPPED",
            poll_interval=1,
            _status_fn=status,
            _time_fn=lambda: 0.0,
            _sleep_fn=_noop_sleep,
        )

        assert result.success is True
        assert result.final_status == "STOPPED"
        assert result.outcome == "success"

    def test_start_forwards_profile_and_executable(self):
        status = MagicMock(return_value="RUNNING")

        result = wait_for_compute_fleet(
            "cl",
            "us-west-2",
            "RUNNING",
            profile="lsmc",
            executable="/opt/daylily/pcluster/bin/pcluster",
            _status_fn=status,
        )

        assert result.success is True
        status.assert_called_once_with(
            "cl",
            "us-west-2",
            profile="lsmc",
            executable="/opt/daylily/pcluster/bin/pcluster",
        )

    def test_repeated_describe_failure_is_distinct(self):
        status = MagicMock(return_value=None)

        result = wait_for_compute_fleet(
            "cl",
            "us-west-2",
            "STOPPED",
            max_failures=3,
            poll_interval=1,
            _status_fn=status,
            _time_fn=lambda: 0.0,
            _sleep_fn=_noop_sleep,
        )

        assert result.outcome == "describe_failure"
        assert result.consecutive_failures == 3

    def test_unexpected_status_is_terminal_failure(self):
        result = wait_for_compute_fleet(
            "cl",
            "us-west-2",
            "STOPPED",
            _status_fn=MagicMock(return_value="PROTECTED"),
        )

        assert result.outcome == "terminal_failure"
        assert result.final_status == "PROTECTED"

    def test_timeout_is_bounded(self):
        clock = _Clock()

        result = wait_for_compute_fleet(
            "cl",
            "us-west-2",
            "STOPPED",
            timeout=3,
            poll_interval=1,
            _status_fn=MagicMock(return_value="STOPPING"),
            _time_fn=clock.time,
            _sleep_fn=clock.sleep,
        )

        assert result.outcome == "timeout"
        assert result.elapsed_seconds == 3

    def test_rejects_non_terminal_target_before_poll(self):
        status = MagicMock()

        try:
            wait_for_compute_fleet(
                "cl",
                "us-west-2",
                "STOPPING",
                _status_fn=status,
            )
        except ValueError as exc:
            assert "expected exactly" in str(exc)
        else:
            raise AssertionError("Expected STOPPING to be rejected")

        status.assert_not_called()


class TestWaitForClusterUpdate:
    def test_stale_create_then_update_success(self):
        status = MagicMock(side_effect=["CREATE_COMPLETE", "UPDATE_IN_PROGRESS", "UPDATE_COMPLETE"])

        result = wait_for_cluster_update(
            "cl",
            "us-west-2",
            poll_interval=1,
            _status_fn=status,
            _time_fn=lambda: 0.0,
            _sleep_fn=_noop_sleep,
        )

        assert result.success is True
        assert result.outcome == "success"
        assert result.safe_to_restore_fleet is True

    def test_completed_rollback_is_recoverable_and_safe_to_restore(self):
        status = MagicMock(
            side_effect=[
                "UPDATE_IN_PROGRESS",
                "UPDATE_ROLLBACK_IN_PROGRESS",
                "UPDATE_ROLLBACK_COMPLETE",
            ]
        )

        result = wait_for_cluster_update(
            "cl",
            "us-west-2",
            poll_interval=1,
            _status_fn=status,
            _time_fn=lambda: 0.0,
            _sleep_fn=_noop_sleep,
        )

        assert result.success is False
        assert result.outcome == "recoverable_rollback"
        assert result.safe_to_restore_fleet is True

    def test_rollback_failure_is_indeterminate_and_unsafe(self):
        result = wait_for_cluster_update(
            "cl",
            "us-west-2",
            _status_fn=MagicMock(return_value="UPDATE_ROLLBACK_FAILED"),
        )

        assert result.outcome == "indeterminate_failure"
        assert result.safe_to_restore_fleet is False

    def test_repeated_describe_failure_is_indeterminate(self):
        result = wait_for_cluster_update(
            "cl",
            "us-west-2",
            max_failures=2,
            poll_interval=1,
            _status_fn=MagicMock(return_value=None),
            _time_fn=lambda: 0.0,
            _sleep_fn=_noop_sleep,
        )

        assert result.outcome == "describe_failure"
        assert result.safe_to_restore_fleet is False

    def test_timeout_during_update_is_indeterminate(self):
        clock = _Clock()

        result = wait_for_cluster_update(
            "cl",
            "us-west-2",
            timeout=3,
            poll_interval=1,
            _status_fn=MagicMock(return_value="UPDATE_IN_PROGRESS"),
            _time_fn=clock.time,
            _sleep_fn=clock.sleep,
        )

        assert result.outcome == "timeout"
        assert result.safe_to_restore_fleet is False

    def test_stale_create_status_has_short_start_bound(self):
        clock = _Clock()

        result = wait_for_cluster_update(
            "cl",
            "us-west-2",
            timeout=100,
            update_start_timeout=3,
            poll_interval=1,
            _status_fn=MagicMock(return_value="CREATE_COMPLETE"),
            _time_fn=clock.time,
            _sleep_fn=clock.sleep,
        )

        assert result.outcome == "update_not_started"
        assert result.elapsed_seconds == 3
        assert result.safe_to_restore_fleet is False

    def test_unexpected_terminal_status_is_unsafe(self):
        result = wait_for_cluster_update(
            "cl",
            "us-west-2",
            _status_fn=MagicMock(return_value="DELETE_IN_PROGRESS"),
        )

        assert result.outcome == "terminal_failure"
        assert result.safe_to_restore_fleet is False

    def test_profile_and_alternate_executable_forwarded(self):
        status = MagicMock(return_value="UPDATE_COMPLETE")

        result = wait_for_cluster_update(
            "cl",
            "us-west-2",
            profile="lsmc",
            executable="/opt/daylily/pcluster/bin/pcluster",
            _status_fn=status,
        )

        assert result.success is True
        status.assert_called_once_with(
            "cl",
            "us-west-2",
            profile="lsmc",
            executable="/opt/daylily/pcluster/bin/pcluster",
        )


class TestWaitForDeletion:
    @patch("daylily_ec.pcluster.monitor.get_cluster_status")
    def test_none_means_deleted(self, mock_status):
        mock_status.return_value = None
        r = wait_for_deletion("cl", "us-west-2", _sleep_fn=_noop_sleep)
        assert r.success is True
        assert r.final_status is None

    @patch("daylily_ec.pcluster.monitor.get_cluster_status")
    def test_failed_status(self, mock_status):
        mock_status.return_value = DELETE_STATUS_FAILED
        r = wait_for_deletion("cl", "us-west-2", _sleep_fn=_noop_sleep)
        assert r.success is False
        assert r.final_status == DELETE_STATUS_FAILED

    @patch("daylily_ec.pcluster.monitor.get_cluster_status")
    def test_profile_passed(self, mock_status):
        mock_status.side_effect = ["DELETE_IN_PROGRESS", None]
        wait_for_deletion("cl", "us-west-2", profile="p", _sleep_fn=_noop_sleep)
        mock_status.assert_any_call("cl", "us-west-2", profile="p")
