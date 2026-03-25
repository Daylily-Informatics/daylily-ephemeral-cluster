"""Tests for the delete workflow and CLI."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from daylily_ec.cli import app
from daylily_ec.state.models import StateRecord
from daylily_ec.workflow.delete_cluster import (
    DeleteOptions,
    ResolvedDeleteOptions,
    _resolve_delete_options,
    confirm_delete,
    find_fsx_associations,
    run_delete_workflow,
)

runner = CliRunner()


def _write_state(path: Path) -> None:
    path.write_text(
        StateRecord(
            cluster_name="state-cluster",
            region="us-west-2",
            aws_profile="state-profile",
            account_id="123456789012",
            heartbeat_topic_arn="arn:aws:sns:us-west-2:123456789012:topic",
            heartbeat_schedule_name="schedule-name",
        ).to_sorted_json(),
        encoding="utf-8",
    )


class TestDeleteHelpers:
    def test_resolve_delete_options_uses_state_defaults(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        _write_state(state_file)
        monkeypatch.setattr(
            "daylily_ec.workflow.delete_cluster.resolve_profile",
            lambda profile=None: profile or "env-profile",
        )

        resolved, state = _resolve_delete_options(DeleteOptions(None, None, None, state_file))

        assert resolved.cluster_name == "state-cluster"
        assert resolved.region == "us-west-2"
        assert resolved.profile == "state-profile"
        assert state is not None
        assert state.account_id == "123456789012"

    def test_confirm_delete_checks_phrase(self):
        assert confirm_delete(["fs-123"], yes=False, prompt_fn=lambda _: "please delete") is True
        assert confirm_delete(["fs-123"], yes=False, prompt_fn=lambda _: "no") is False

    def test_find_fsx_associations_filters_tags(self):
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "FileSystems": [
                    {
                        "FileSystemId": "fs-match",
                        "Tags": [{"Key": "parallelcluster:cluster-name", "Value": "alpha"}],
                    },
                    {
                        "FileSystemId": "fs-other",
                        "Tags": [{"Key": "parallelcluster:cluster-name", "Value": "beta"}],
                    },
                ]
            }
        ]
        fsx_client = MagicMock()
        fsx_client.get_paginator.return_value = paginator

        assert find_fsx_associations(fsx_client, "alpha") == ["fs-match"]


class TestDeleteWorkflow:
    @patch("daylily_ec.workflow.delete_cluster.wait_for_deletion")
    @patch("daylily_ec.workflow.delete_cluster.start_delete_cluster")
    @patch("daylily_ec.workflow.delete_cluster.find_fsx_associations")
    @patch("daylily_ec.workflow.delete_cluster.get_cluster_status")
    @patch("daylily_ec.workflow.delete_cluster.boto3.Session")
    def test_run_delete_workflow_success(
        self,
        mock_session,
        mock_status,
        mock_find_fsx,
        mock_start_delete,
        mock_wait,
    ):
        resolved = ResolvedDeleteOptions(
            cluster_name="alpha",
            region="us-west-2",
            profile="prof",
            state_file=None,
            yes=True,
            poll_interval=0.01,
        )
        session = MagicMock()
        session.client.return_value = MagicMock()
        mock_session.return_value = session
        mock_status.return_value = "CREATE_COMPLETE"
        mock_find_fsx.return_value = []
        mock_start_delete.return_value = MagicMock(success=True, stdout="", stderr="")
        mock_wait.return_value = MagicMock(success=True, error="", final_status=None)

        with patch(
            "daylily_ec.workflow.delete_cluster._resolve_delete_options",
            return_value=(resolved, None),
        ):
            rc = run_delete_workflow(DeleteOptions(None, None, None))

        assert rc == 0
        mock_start_delete.assert_called_once_with("alpha", "us-west-2", profile="prof")
        mock_wait.assert_called_once_with(
            "alpha",
            "us-west-2",
            profile="prof",
            poll_interval=0.01,
        )

    @patch("daylily_ec.workflow.delete_cluster.start_delete_cluster")
    @patch("daylily_ec.workflow.delete_cluster.find_fsx_associations")
    @patch("daylily_ec.workflow.delete_cluster.get_cluster_status")
    @patch("daylily_ec.workflow.delete_cluster.boto3.Session")
    def test_run_delete_workflow_aborts_on_confirmation(
        self,
        mock_session,
        mock_status,
        mock_find_fsx,
        mock_start_delete,
    ):
        resolved = ResolvedDeleteOptions(
            cluster_name="alpha",
            region="us-west-2",
            profile="prof",
            state_file=None,
            yes=False,
            poll_interval=0.01,
        )
        mock_session.return_value = MagicMock()
        mock_status.return_value = "CREATE_COMPLETE"
        mock_find_fsx.return_value = ["fs-123"]

        with (
            patch(
                "daylily_ec.workflow.delete_cluster._resolve_delete_options",
                return_value=(resolved, None),
            ),
            patch(
                "daylily_ec.workflow.delete_cluster.confirm_delete",
                return_value=False,
            ),
        ):
            rc = run_delete_workflow(DeleteOptions(None, None, None))

        assert rc == 1
        mock_start_delete.assert_not_called()


class TestDeleteCli:
    def test_cli_delete_passes_options(self, tmp_path):
        state_file = tmp_path / "state.json"
        state_file.write_text("{}", encoding="utf-8")

        with patch(
            "daylily_ec.workflow.delete_cluster.run_delete_workflow", return_value=0
        ) as mock_run:
            result = runner.invoke(
                app,
                [
                    "delete",
                    "--cluster-name",
                    "alpha",
                    "--region",
                    "us-west-2",
                    "--profile",
                    "prof",
                    "--state-file",
                    str(state_file),
                    "--yes",
                ],
            )

        assert result.exit_code == 0
        options = mock_run.call_args.args[0]
        assert options.cluster_name == "alpha"
        assert options.region == "us-west-2"
        assert options.profile == "prof"
        assert options.state_file == state_file
        assert options.yes is True

    def test_resolve_delete_options_raises_for_missing_state(self, tmp_path):
        with pytest.raises(RuntimeError, match="State file not found"):
            _resolve_delete_options(DeleteOptions(None, None, None, tmp_path / "missing.json"))
