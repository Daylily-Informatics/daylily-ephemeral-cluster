"""Strict DYEC read-side coverage for clone-resident execution status v2."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from daylily_ec.execution_status import (
    ExecutionStatusError,
    attempt_exit_codes,
    controller_attempt,
    latest_attempt,
    read_execution_status,
    validate_execution_status,
)


def _status_payload(root: Path, repo: Path) -> dict[str, object]:
    timestamp = "2026-08-18T04:00:00Z"
    return {
        "schema_version": "daylily.analysis_status.v2",
        "analysis": {
            "analysis_root": str(root),
            "repo_path": str(repo),
            "created_at": timestamp,
        },
        "updated_at": timestamp,
        "attempts": [
            {
                "attempt_id": "00000000-0000-4000-8000-000000000001",
                "sequence": 1,
                "origin": "dyec_controller",
                "mode": "dry_run",
                "requested_command": "dy-r target -n",
                "started_at": timestamp,
                "completed_at": timestamp,
                "state": "failed",
                "controller": {
                    "state": "failed",
                    "session_name": "session-1",
                    "pid": 1234,
                    "command": "dy-r target -n",
                    "started_at": timestamp,
                    "completed_at": timestamp,
                    "exit_code": 7,
                },
                "day_run": {
                    "state": "failed",
                    "argv": ["bin/day_run", "target", "-n"],
                    "started_at": timestamp,
                    "completed_at": timestamp,
                    "exit_code": 7,
                },
                "snakemake": {
                    "state": "succeeded",
                    "argv": ["snakemake", "--profile=/profile", "target", "-n"],
                    "started_at": timestamp,
                    "completed_at": timestamp,
                    "exit_code": 0,
                    "log_path": ".snakemake/log/one.snakemake.log",
                    "log_attribution": "exact invocation file-set difference",
                },
            }
        ],
    }


def _clone_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "owner" / "analysis"
    repo = root / "daylily-omics-analysis"
    repo.mkdir(parents=True)
    return root, repo, repo / "status.json"


def test_reader_preserves_all_three_independent_exit_codes(tmp_path: Path) -> None:
    root, repo, status_path = _clone_paths(tmp_path)
    status_path.write_text(json.dumps(_status_payload(root, repo)), encoding="utf-8")

    payload = read_execution_status(
        status_path,
        repo_path=str(repo),
        analysis_root=str(root),
    )
    attempt = controller_attempt(
        payload,
        attempt_id="00000000-0000-4000-8000-000000000001",
        session_name="session-1",
    )

    assert attempt_exit_codes(attempt) == {
        "controller_exit_code": 7,
        "day_run_exit_code": 7,
        "snakemake_exit_code": 0,
    }
    assert latest_attempt(payload) == attempt


def test_reader_rejects_home_receipts_and_missing_clone_v2(tmp_path: Path) -> None:
    root, repo, status_path = _clone_paths(tmp_path)
    retired_home_receipt = tmp_path / "home" / "ubuntu" / "daylily-runs" / "x" / "status.json"
    retired_home_receipt.parent.mkdir(parents=True)
    retired_home_receipt.write_text('{"workflow_exit_code": 0}', encoding="utf-8")

    with pytest.raises(ExecutionStatusError, match="clone-root v2 receipt"):
        read_execution_status(
            retired_home_receipt,
            repo_path=str(repo),
            analysis_root=str(root),
        )
    with pytest.raises(ExecutionStatusError, match="is missing"):
        read_execution_status(
            status_path,
            repo_path=str(repo),
            analysis_root=str(root),
        )


def test_reader_rejects_mismatched_identity_and_duplicate_attempt_ids(tmp_path: Path) -> None:
    root, repo, _status_path = _clone_paths(tmp_path)
    payload = _status_payload(root, repo)
    mismatched = copy.deepcopy(payload)
    mismatched["analysis"]["analysis_root"] = "/fsx/analysis_results/other/root"  # type: ignore[index]
    with pytest.raises(ExecutionStatusError, match="identity"):
        validate_execution_status(
            mismatched,
            repo_path=str(repo),
            analysis_root=str(root),
        )

    duplicate = copy.deepcopy(payload)
    duplicate_attempt = copy.deepcopy(duplicate["attempts"][0])  # type: ignore[index]
    duplicate_attempt["sequence"] = 2  # type: ignore[index]
    duplicate["attempts"].append(duplicate_attempt)  # type: ignore[index]
    with pytest.raises(ExecutionStatusError, match="duplicated"):
        validate_execution_status(
            duplicate,
            repo_path=str(repo),
            analysis_root=str(root),
        )
