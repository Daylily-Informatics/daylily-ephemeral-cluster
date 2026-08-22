"""Read and validate the clone-resident DayOA execution-status v2 record.

DYEC deliberately owns only the read side of this contract.  DayOA creates and
atomically appends the record in the analysis clone, while DYEC selects the one
controller attempt named by ``controller_target.json``.  There is no reader or
migration path for the retired home-directory receipt format.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any


STATUS_SCHEMA_VERSION = "daylily.analysis_status.v2"
STATUS_FILENAME = "status.json"
_ORIGINS = frozenset({"dyec_controller", "direct_day_run"})
_MODES = frozenset({"dry_run", "live", "unknown"})
_RUN_STATES = frozenset({"not_started", "running", "succeeded", "failed"})
_ATTEMPT_STATES = frozenset({"running", "succeeded", "failed"})


class ExecutionStatusError(ValueError):
    """Raised when the clone-resident v2 record is missing or malformed."""


def status_path_for_repo(repo_path: str | Path) -> Path:
    """Return the one supported clone-root status location."""

    repo = Path(repo_path)
    if repo.name != "daylily-omics-analysis":
        raise ExecutionStatusError("repo_path must name the daylily-omics-analysis clone")
    return repo / STATUS_FILENAME


def _require_exact_keys(payload: dict[str, Any], keys: set[str], label: str) -> None:
    actual = set(payload)
    if actual != keys:
        unexpected = ", ".join(sorted(actual.difference(keys))) or "none"
        missing = ", ".join(sorted(keys.difference(actual))) or "none"
        raise ExecutionStatusError(
            f"{label} has unexpected keys ({unexpected}) or missing keys ({missing})"
        )


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExecutionStatusError(f"{label} must be a non-empty string")
    return value


def _timestamp(value: Any, label: str) -> str:
    return _string(value, label)


def _exit_code(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ExecutionStatusError(f"{label} must be an integer")
    return value


def _argv(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ExecutionStatusError(f"{label} must be a non-empty argv array")
    if any(not isinstance(item, str) or not item for item in value):
        raise ExecutionStatusError(f"{label} must contain only non-empty strings")
    return value


def _validate_child(payload: Any, *, label: str, log_fields: bool = False) -> None:
    if not isinstance(payload, dict):
        raise ExecutionStatusError(f"{label} must be an object")
    keys = {"state", "argv", "started_at", "completed_at", "exit_code"}
    if log_fields:
        keys.update({"log_path", "log_attribution"})
    _require_exact_keys(payload, keys, label)
    state = payload["state"]
    if state not in _RUN_STATES:
        raise ExecutionStatusError(f"{label}.state is invalid")
    argv = payload["argv"]
    started_at = payload["started_at"]
    completed_at = payload["completed_at"]
    exit_code = payload["exit_code"]
    if state == "not_started":
        if any(value is not None for value in (argv, started_at, completed_at, exit_code)):
            raise ExecutionStatusError(f"{label} not_started state must not carry execution data")
    elif state == "running":
        _argv(argv, f"{label}.argv")
        _timestamp(started_at, f"{label}.started_at")
        if completed_at is not None or exit_code is not None:
            raise ExecutionStatusError(f"{label} running state must not carry terminal data")
    else:
        _argv(argv, f"{label}.argv")
        _timestamp(started_at, f"{label}.started_at")
        _timestamp(completed_at, f"{label}.completed_at")
        code = _exit_code(exit_code, f"{label}.exit_code")
        if (state == "succeeded") != (code == 0):
            raise ExecutionStatusError(f"{label}.state does not match its exit code")
    if log_fields:
        log_path = payload["log_path"]
        log_attribution = payload["log_attribution"]
        if log_path is not None:
            _string(log_path, f"{label}.log_path")
        if log_attribution is not None:
            _string(log_attribution, f"{label}.log_attribution")
        if log_path is not None and log_attribution is None:
            raise ExecutionStatusError(f"{label}.log_path requires log attribution")


def _validate_controller(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ExecutionStatusError("controller must be an object")
    _require_exact_keys(
        payload,
        {
            "state",
            "session_name",
            "pid",
            "command",
            "started_at",
            "completed_at",
            "exit_code",
        },
        "controller",
    )
    state = payload["state"]
    if state not in {"running", "succeeded", "failed"}:
        raise ExecutionStatusError("controller.state is invalid")
    _string(payload["session_name"], "controller.session_name")
    if isinstance(payload["pid"], bool) or not isinstance(payload["pid"], int) or payload["pid"] < 1:
        raise ExecutionStatusError("controller.pid must be a positive integer")
    _string(payload["command"], "controller.command")
    _timestamp(payload["started_at"], "controller.started_at")
    if state == "running":
        if payload["completed_at"] is not None or payload["exit_code"] is not None:
            raise ExecutionStatusError("running controller must not carry terminal data")
        return
    _timestamp(payload["completed_at"], "controller.completed_at")
    code = _exit_code(payload["exit_code"], "controller.exit_code")
    if (state == "succeeded") != (code == 0):
        raise ExecutionStatusError("controller.state does not match its exit code")


def _validate_attempt(payload: Any, *, expected_sequence: int, seen_ids: set[str]) -> None:
    if not isinstance(payload, dict):
        raise ExecutionStatusError("attempt must be an object")
    _require_exact_keys(
        payload,
        {
            "attempt_id",
            "sequence",
            "origin",
            "mode",
            "requested_command",
            "started_at",
            "completed_at",
            "state",
            "controller",
            "day_run",
            "snakemake",
        },
        "attempt",
    )
    attempt_id = _string(payload["attempt_id"], "attempt.attempt_id")
    try:
        uuid.UUID(attempt_id)
    except (ValueError, AttributeError) as exc:
        raise ExecutionStatusError("attempt.attempt_id must be a UUID") from exc
    if attempt_id in seen_ids:
        raise ExecutionStatusError("attempt.attempt_id is duplicated")
    seen_ids.add(attempt_id)
    if payload["sequence"] != expected_sequence:
        raise ExecutionStatusError("attempt.sequence must increase from one")
    if payload["origin"] not in _ORIGINS:
        raise ExecutionStatusError("attempt.origin is invalid")
    if payload["mode"] not in _MODES:
        raise ExecutionStatusError("attempt.mode is invalid")
    _string(payload["requested_command"], "attempt.requested_command")
    _timestamp(payload["started_at"], "attempt.started_at")
    state = payload["state"]
    if state not in _ATTEMPT_STATES:
        raise ExecutionStatusError("attempt.state is invalid")
    if state == "running":
        if payload["completed_at"] is not None:
            raise ExecutionStatusError("running attempt must not have completed_at")
    else:
        _timestamp(payload["completed_at"], "attempt.completed_at")
    controller = payload["controller"]
    if payload["origin"] == "dyec_controller":
        _validate_controller(controller)
        if state != "running" and controller["state"] != state:
            raise ExecutionStatusError("terminal DYEC attempt must match controller state")
    elif controller is not None:
        raise ExecutionStatusError("direct_day_run attempt must not have a controller object")
    _validate_child(payload["day_run"], label="day_run")
    _validate_child(payload["snakemake"], label="snakemake", log_fields=True)
    if payload["origin"] == "direct_day_run" and state != "running":
        if payload["day_run"]["state"] != state:
            raise ExecutionStatusError("terminal direct attempt must match day_run state")


def validate_execution_status(payload: Any, *, repo_path: str, analysis_root: str) -> dict[str, Any]:
    """Validate strict v2 shape and immutable clone identity."""

    if not isinstance(payload, dict):
        raise ExecutionStatusError("status payload must be an object")
    _require_exact_keys(payload, {"schema_version", "analysis", "updated_at", "attempts"}, "status")
    if payload["schema_version"] != STATUS_SCHEMA_VERSION:
        raise ExecutionStatusError(
            f"unsupported clone-resident status schema: {payload['schema_version']!r}"
        )
    analysis = payload["analysis"]
    if not isinstance(analysis, dict):
        raise ExecutionStatusError("analysis must be an object")
    _require_exact_keys(analysis, {"analysis_root", "repo_path", "created_at"}, "analysis")
    if analysis["analysis_root"] != analysis_root or analysis["repo_path"] != repo_path:
        raise ExecutionStatusError("status analysis identity does not match controller target")
    _timestamp(analysis["created_at"], "analysis.created_at")
    _timestamp(payload["updated_at"], "updated_at")
    attempts = payload["attempts"]
    if not isinstance(attempts, list):
        raise ExecutionStatusError("attempts must be an array")
    seen_ids: set[str] = set()
    for sequence, attempt in enumerate(attempts, start=1):
        _validate_attempt(attempt, expected_sequence=sequence, seen_ids=seen_ids)
    return payload


def read_execution_status(
    path: str | Path,
    *,
    repo_path: str,
    analysis_root: str,
) -> dict[str, Any]:
    """Read only the canonical v2 file; reject retired or malformed receipts."""

    expected = status_path_for_repo(repo_path)
    status_path = Path(path)
    if status_path != expected:
        raise ExecutionStatusError(
            f"status path must be the clone-root v2 receipt: {expected.as_posix()}"
        )
    if not status_path.is_file() or status_path.is_symlink():
        raise ExecutionStatusError(
            f"clone-resident status v2 is missing: {status_path.as_posix()}"
        )
    try:
        raw = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutionStatusError(
            f"clone-resident status v2 is not valid JSON: {status_path.as_posix()}"
        ) from exc
    return validate_execution_status(raw, repo_path=repo_path, analysis_root=analysis_root)


def controller_attempt(
    payload: dict[str, Any], *, attempt_id: str, session_name: str
) -> dict[str, Any]:
    """Return one exact DYEC controller attempt, never a guessed latest entry."""

    matches = [attempt for attempt in payload["attempts"] if attempt["attempt_id"] == attempt_id]
    if len(matches) != 1:
        raise ExecutionStatusError(
            f"clone-resident status v2 does not contain controller attempt {attempt_id}"
        )
    attempt = matches[0]
    controller = attempt["controller"]
    if attempt["origin"] != "dyec_controller" or not isinstance(controller, dict):
        raise ExecutionStatusError("controller target attempt is not a DYEC controller attempt")
    if controller["session_name"] != session_name:
        raise ExecutionStatusError("controller target session does not match status attempt")
    return attempt


def latest_attempt(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return the last validated append-only attempt, if one has been started."""

    attempts = payload["attempts"]
    return attempts[-1] if attempts else None


def attempt_exit_codes(attempt: dict[str, Any]) -> dict[str, int | None]:
    """Expose the three independently recorded terminal results without conflation."""

    controller = attempt["controller"]
    return {
        "controller_exit_code": controller["exit_code"] if isinstance(controller, dict) else None,
        "day_run_exit_code": attempt["day_run"]["exit_code"],
        "snakemake_exit_code": attempt["snakemake"]["exit_code"],
    }
