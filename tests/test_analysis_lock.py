from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from daylily_ec.analysis_lock import (
    AnalysisLockError,
    acquire_lock,
    assert_operation_allowed,
    lock_status,
    release_lock,
    takeover_lock,
    takeover_request,
    visit_log_paths,
    write_visit,
)
from daylily_ec.cli import app


runner = CliRunner()


def _analysis_root(tmp_path: Path) -> Path:
    root = tmp_path / "fsx" / "analysis_results" / "ubuntu" / "analysis-1"
    root.mkdir(parents=True)
    return root


def _activate_dayec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")
    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")


def _set_agent(monkeypatch: pytest.MonkeyPatch, agent_id: str) -> None:
    monkeypatch.setenv("DAYOA_AGENT_ID", agent_id)
    monkeypatch.setenv("DAYOA_AGENT_KIND", "test-agent")
    monkeypatch.setenv("DAYOA_HUMAN_REQUESTOR", "jmajor")


def test_visit_writes_root_and_central_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _analysis_root(tmp_path)
    _set_agent(monkeypatch, "agent-read")

    payload = write_visit(
        root,
        mode="export",
        intent="verify export snapshot",
        note="no fsx delete",
    )

    root_log, central_log = visit_log_paths(root)
    assert root_log.is_file()
    assert central_log.is_file()
    root_event = json.loads(root_log.read_text(encoding="utf-8").splitlines()[-1])
    central_event = json.loads(central_log.read_text(encoding="utf-8").splitlines()[-1])
    assert root_event["schema_version"] == "dayoa.analysis_agent_visit.v1"
    assert root_event["mode"] == "export"
    assert root_event["intent"] == "verify export snapshot"
    assert root_event["human_requestor"] == "jmajor"
    assert central_event["analysis_root"] == payload["analysis_root"]


def test_foreign_writer_blocks_write_but_not_export_visit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _analysis_root(tmp_path)
    _set_agent(monkeypatch, "agent-a")
    owner = acquire_lock(root, operation="write", intent="live workflow")
    assert owner["agent_id"] == "agent-a"

    _set_agent(monkeypatch, "agent-b")
    with pytest.raises(AnalysisLockError, match="already locked"):
        acquire_lock(root, operation="write", intent="competing live workflow")
    with pytest.raises(AnalysisLockError, match="blocked by a foreign write lock"):
        assert_operation_allowed(root, operation="write", intent="competing live workflow")

    export_visit = assert_operation_allowed(
        root,
        operation="export",
        intent="snapshot export while active",
    )
    assert export_visit["mode"] == "export"
    assert export_visit["lock_state_seen"]["locked"] is True

    _set_agent(monkeypatch, "agent-a")
    release_lock(root)
    assert lock_status(root)["locked"] is False


def test_takeover_requires_request_token_and_records_previous_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _analysis_root(tmp_path)
    _set_agent(monkeypatch, "agent-a")
    acquire_lock(root, operation="write", intent="old controller")

    _set_agent(monkeypatch, "agent-b")
    request = takeover_request(root, operation="kill", reason="user double-approved takeover")
    assert request["token"]
    assert request["current_owner"]["agent_id"] == "agent-a"

    with pytest.raises(AnalysisLockError, match="approved-by"):
        takeover_lock(
            root,
            operation="kill",
            confirm_token=request["token"],
            approved_by="",
            reason="user double-approved takeover",
            intent="cancel stale jobs",
        )

    new_owner = takeover_lock(
        root,
        operation="kill",
        confirm_token=request["token"],
        approved_by="jmajor",
        reason="user double-approved takeover",
        intent="cancel stale jobs",
    )
    assert new_owner["agent_id"] == "agent-b"
    assert new_owner["takeover"]["previous_owner"]["agent_id"] == "agent-a"
    assert (root / ".dayoa_agent" / "takeovers.jsonl").is_file()


def test_analysis_cli_visit_and_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _analysis_root(tmp_path)
    _activate_dayec(monkeypatch)
    _set_agent(monkeypatch, "agent-cli")

    visit_result = runner.invoke(
        app,
        [
            "--json",
            "analysis",
            "visit",
            "--analysis-root",
            str(root),
            "--mode",
            "read",
            "--intent",
            "inspect logs",
        ],
    )
    assert visit_result.exit_code == 0, visit_result.stdout + visit_result.stderr
    assert json.loads(visit_result.stdout)["mode"] == "read"

    blocked_result = runner.invoke(
        app,
        [
            "analysis",
            "guard",
            "--analysis-root",
            str(root),
            "--operation",
            "write",
            "--intent",
            "live run without lock",
        ],
    )
    assert blocked_result.exit_code == 1
    assert "requires a write lock" in (blocked_result.stdout + blocked_result.stderr)

    acquire_result = runner.invoke(
        app,
        [
            "analysis",
            "lock",
            "acquire",
            "--analysis-root",
            str(root),
            "--operation",
            "write",
            "--intent",
            "live run",
        ],
    )
    assert acquire_result.exit_code == 0, acquire_result.stdout + acquire_result.stderr

    allowed_result = runner.invoke(
        app,
        [
            "analysis",
            "guard",
            "--analysis-root",
            str(root),
            "--operation",
            "write",
            "--intent",
            "live run",
        ],
    )
    assert allowed_result.exit_code == 0, allowed_result.stdout + allowed_result.stderr
