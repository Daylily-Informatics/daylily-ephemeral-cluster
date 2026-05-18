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
    find_active_fsx_repository_activity,
    find_fsx_associations,
    run_delete_dry_run,
    run_delete_workflow,
)

runner = CliRunner()


def _activate_dayec_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")


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

    def test_find_active_fsx_repository_activity_reports_dras_and_tasks(self):
        fsx_client = MagicMock()
        fsx_client.describe_data_repository_associations.return_value = {
            "Associations": [
                {
                    "AssociationId": "dra-run",
                    "FileSystemPath": "/run_dir_mounts/RUN123/",
                    "DataRepositoryPath": "s3://bucket/RUN123/",
                    "Lifecycle": "AVAILABLE",
                    "S3": {},
                },
                {
                    "AssociationId": "dra-old",
                    "FileSystemPath": "/analysis_results/ubuntu/old/",
                    "DataRepositoryPath": "s3://bucket/analysis_results/ubuntu/old/",
                    "Lifecycle": "DELETED",
                },
            ]
        }
        fsx_client.describe_data_repository_tasks.return_value = {
            "DataRepositoryTasks": [
                {
                    "TaskId": "task-1",
                    "Type": "EXPORT_TO_REPOSITORY",
                    "Lifecycle": "EXECUTING",
                    "Paths": ["/analysis_results/ubuntu/export_1/"],
                },
                {
                    "TaskId": "task-2",
                    "Type": "EXPORT_TO_REPOSITORY",
                    "Lifecycle": "SUCCEEDED",
                },
            ]
        }

        activity = find_active_fsx_repository_activity(fsx_client, ["fs-123"])

        assert [item["association_id"] for item in activity["associations"]] == ["dra-run"]
        assert [item["task_id"] for item in activity["export_tasks"]] == ["task-1"]


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
    @patch("daylily_ec.workflow.delete_cluster.find_active_fsx_repository_activity")
    @patch("daylily_ec.workflow.delete_cluster.find_fsx_associations")
    @patch("daylily_ec.workflow.delete_cluster.get_cluster_status")
    @patch("daylily_ec.workflow.delete_cluster.boto3.Session")
    def test_run_delete_workflow_aborts_on_confirmation(
        self,
        mock_session,
        mock_status,
        mock_find_fsx,
        mock_activity,
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
        mock_activity.return_value = {"associations": [], "export_tasks": []}

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

    @patch("daylily_ec.workflow.delete_cluster.find_active_fsx_repository_activity")
    @patch("daylily_ec.workflow.delete_cluster.find_fsx_associations")
    @patch("daylily_ec.workflow.delete_cluster.get_cluster_status")
    @patch("daylily_ec.workflow.delete_cluster.boto3.Session")
    def test_run_delete_dry_run_reports_active_dras(
        self,
        mock_session,
        mock_status,
        mock_find_fsx,
        mock_activity,
        capsys,
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
        mock_activity.return_value = {
            "associations": [
                {
                    "association_id": "dra-run",
                    "file_system_path": "/run_dir_mounts/RUN123/",
                    "data_repository_path": "s3://bucket/RUN123/",
                    "lifecycle": "AVAILABLE",
                    "auto_export_events": [],
                }
            ],
            "export_tasks": [
                {
                    "task_id": "task-1",
                    "paths": ["/analysis_results/ubuntu/export_1/"],
                    "lifecycle": "EXECUTING",
                }
            ],
        }

        with patch(
            "daylily_ec.workflow.delete_cluster._resolve_delete_options",
            return_value=(resolved, None),
        ):
            rc = run_delete_dry_run(DeleteOptions(None, None, None))

        assert rc == 0
        captured = capsys.readouterr().out
        assert "dra-run" in captured
        assert "task-1" in captured


class TestDeleteCli:
    def test_cli_delete_passes_options(self, tmp_path, monkeypatch):
        _activate_dayec_runtime(monkeypatch)
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
