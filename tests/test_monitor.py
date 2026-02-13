"""Tests for daylily_ec.pcluster.monitor — CP-014."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from daylily_ec.pcluster.monitor import (
    DEFAULT_POLL_INTERVAL,
    MAX_CONSECUTIVE_FAILURES,
    STATUS_COMPLETE,
    STATUS_IN_PROGRESS,
    MonitorResult,
    get_cluster_details,
    get_cluster_status,
    wait_for_creation,
)


# ── helpers ──────────────────────────────────────────────────────────────


def _completed(stdout: str = "", stderr: str = "", rc: int = 0):
    cp = MagicMock()
    cp.returncode = rc
    cp.stdout = stdout
    cp.stderr = stderr
    return cp


def _noop_sleep(_: float) -> None:
    """Replacement for time.sleep in tests."""


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

import json as _json


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
        r = wait_for_creation(
            "cl", "us-west-2", poll_interval=0.01, _sleep_fn=_noop_sleep
        )
        assert r.success is True
        assert mock_status.call_count == 3

    @patch("daylily_ec.pcluster.monitor.get_cluster_status")
    def test_consecutive_failures_abort(self, mock_status):
        mock_status.return_value = None
        r = wait_for_creation(
            "cl", "us-west-2", max_failures=3, _sleep_fn=_noop_sleep
        )
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
        r = wait_for_creation(
            "cl", "us-west-2", max_failures=5, _sleep_fn=_noop_sleep
        )
        assert r.success is True

    @patch("daylily_ec.pcluster.monitor.get_cluster_status")
    def test_unexpected_status_fails(self, mock_status):
        mock_status.return_value = "CREATE_FAILED"
        r = wait_for_creation("cl", "us-west-2", _sleep_fn=_noop_sleep)
        assert r.success is False
        assert r.final_status == "CREATE_FAILED"
        assert "unexpected" in r.error.lower()

    @patch("daylily_ec.pcluster.monitor.get_cluster_details")
    @patch("daylily_ec.pcluster.monitor.get_cluster_status")
    def test_profile_passed(self, mock_status, mock_details):
        mock_status.return_value = STATUS_COMPLETE
        mock_details.return_value = {"headNode": {}}
        wait_for_creation(
            "cl", "us-west-2", profile="p", _sleep_fn=_noop_sleep
        )
        mock_status.assert_called_with("cl", "us-west-2", profile="p")

