"""Tests for the export workflow and CLI."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from daylily_ec.cli import app
from daylily_ec.workflow.export_data import ExportOptions, _normalise_target, run_export_workflow

runner = CliRunner()


def _filesystem(export_path: str = "s3://bucket/exports") -> dict[str, object]:
    return {
        "FileSystemId": "fs-123",
        "LustreConfiguration": {"DataRepositoryConfiguration": {"ExportPath": export_path}},
    }


class TestExportHelpers:
    def test_normalise_relative_target(self):
        relative_path, s3_uri = _normalise_target(_filesystem(), "/analysis_results/run-1")
        assert relative_path == "analysis_results/run-1"
        assert s3_uri == "s3://bucket/exports/analysis_results/run-1"

    def test_normalise_s3_target_requires_export_prefix(self):
        with pytest.raises(RuntimeError, match="expected prefix"):
            _normalise_target(_filesystem(), "s3://other-bucket/path")


class TestExportWorkflow:
    @patch("daylily_ec.workflow.export_data._await_export")
    @patch("daylily_ec.workflow.export_data._start_export")
    @patch("daylily_ec.workflow.export_data._find_filesystem")
    @patch("daylily_ec.workflow.export_data._create_session")
    def test_run_export_workflow_success(
        self,
        mock_create_session,
        mock_find_filesystem,
        mock_start_export,
        mock_await_export,
        tmp_path,
    ):
        mock_create_session.return_value = MagicMock(client=MagicMock(return_value=MagicMock()))
        mock_find_filesystem.return_value = _filesystem()
        mock_start_export.return_value = "task-123"
        mock_await_export.return_value = {"Lifecycle": "SUCCEEDED"}

        rc = run_export_workflow(
            ExportOptions(
                cluster_name="alpha",
                target_uri="analysis_results",
                region="us-west-2",
                profile="prof",
                output_dir=tmp_path,
            )
        )

        assert rc == 0
        payload = yaml.safe_load((tmp_path / "fsx_export.yaml").read_text(encoding="utf-8"))
        assert payload["fsx_export"]["status"] == "success"
        assert payload["fsx_export"]["s3_uri"] == "s3://bucket/exports/analysis_results"

    @patch("daylily_ec.workflow.export_data._create_session")
    @patch("daylily_ec.workflow.export_data._find_filesystem")
    def test_run_export_workflow_failure_writes_error(
        self,
        mock_find_filesystem,
        mock_create_session,
        tmp_path,
    ):
        mock_create_session.return_value = MagicMock(client=MagicMock(return_value=MagicMock()))
        mock_find_filesystem.side_effect = RuntimeError("boom")

        rc = run_export_workflow(
            ExportOptions(
                cluster_name="alpha",
                target_uri="analysis_results",
                region="us-west-2",
                profile=None,
                output_dir=tmp_path,
            )
        )

        assert rc == 1
        payload = yaml.safe_load((tmp_path / "fsx_export.yaml").read_text(encoding="utf-8"))
        assert payload["fsx_export"]["status"] == "error"
        assert "boom" in payload["fsx_export"]["message"]


class TestExportCli:
    def test_cli_export_passes_options(self, tmp_path):
        with (
            patch("daylily_ec.workflow.export_data.configure_logging") as mock_logging,
            patch(
                "daylily_ec.workflow.export_data.run_export_workflow",
                return_value=0,
            ) as mock_run,
        ):
            result = runner.invoke(
                app,
                [
                    "export",
                    "--cluster-name",
                    "alpha",
                    "--target-uri",
                    "analysis_results",
                    "--region",
                    "us-west-2",
                    "--output-dir",
                    str(tmp_path),
                    "--profile",
                    "prof",
                    "--verbose",
                ],
            )

        assert result.exit_code == 0
        mock_logging.assert_called_once_with(True)
        options = mock_run.call_args.args[0]
        assert options.cluster_name == "alpha"
        assert options.target_uri == "analysis_results"
        assert options.region == "us-west-2"
        assert options.profile == "prof"
        assert options.output_dir == Path(tmp_path).resolve()
