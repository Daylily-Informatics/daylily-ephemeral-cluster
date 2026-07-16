"""Analysis-root visit logging and write-lock helpers.

The locking primitive is intentionally filesystem-native: acquiring a writer
lock is an atomic mkdir of ``<analysis_root>/.dayoa_agent/write.lock``.  That
keeps the contract usable from shell, Python, Codex, and non-Codex agents.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
from typing import Mapping, Optional, Sequence, Union
from urllib.parse import urlparse


READ_MODES = {"read", "monitor", "log", "search", "query", "export"}
PROTECTED_OPERATIONS = {"write", "unlock", "delete", "kill"}
VISIT_MODES = READ_MODES | PROTECTED_OPERATIONS
LOCK_SCHEMA_VERSION = "dayoa.analysis_agent_lock.v1"
VISIT_SCHEMA_VERSION = "dayoa.analysis_agent_visit.v1"


class AnalysisLockError(RuntimeError):
    """Raised when an analysis-root lock or visit operation cannot proceed."""


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def utc_stamp() -> str:
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def utc_iso() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def _safe_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._") or "agent"


def _json_default(value: object) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: Mapping[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, default=_json_default) + "\n")


AnalysisRootArg = Union[str, Path]


def normalize_analysis_root(analysis_root: AnalysisRootArg) -> Path:
    root = Path(analysis_root).expanduser()
    if not root.exists():
        raise AnalysisLockError(f"Analysis root does not exist: {root}")
    resolved = root.resolve()
    parts = resolved.parts
    if "analysis_results" not in parts:
        raise AnalysisLockError(
            "Analysis root must be under an analysis_results directory: " + str(resolved)
        )
    idx = parts.index("analysis_results")
    if len(parts) <= idx + 2:
        raise AnalysisLockError(
            "Analysis root must be /.../analysis_results/<owner>/<analysis_id>: "
            + str(resolved)
        )
    return resolved


def analysis_results_root(analysis_root: AnalysisRootArg) -> Path:
    root = normalize_analysis_root(analysis_root)
    parts = root.parts
    idx = parts.index("analysis_results")
    return Path(*parts[: idx + 1])


def agent_dir(analysis_root: AnalysisRootArg) -> Path:
    return normalize_analysis_root(analysis_root) / ".dayoa_agent"


def lock_dir(analysis_root: AnalysisRootArg) -> Path:
    return agent_dir(analysis_root) / "write.lock"


def owner_metadata_path(analysis_root: AnalysisRootArg) -> Path:
    return agent_dir(analysis_root) / "owner.json"


def lock_owner_path(analysis_root: AnalysisRootArg) -> Path:
    return lock_dir(analysis_root) / "owner.json"


def _analysis_identity(analysis_root: Path) -> dict[str, object]:
    parts = analysis_root.parts
    idx = parts.index("analysis_results")
    return {
        "realpath": str(analysis_root),
        "analysis_results_root": str(Path(*parts[: idx + 1])),
        "owner": parts[idx + 1],
        "analysis_id": parts[idx + 2],
        "cluster": os.environ.get("DAYOA_CLUSTER") or os.environ.get("DYEC_CLUSTER"),
        "fsx_id": os.environ.get("DAYOA_FSX_ID") or os.environ.get("DYEC_FSX_ID"),
    }


def current_agent_metadata(
    *,
    human_requestor: Optional[str] = None,
    intent: Optional[str] = None,
    operation: Optional[str] = None,
    tmux_session: Optional[str] = None,
    command_summary: Optional[str] = None,
) -> dict[str, object]:
    host = socket.gethostname()
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or "unknown"
    codex_session_id = (
        os.environ.get("CODEX_SESSION_ID")
        or os.environ.get("CODEX_THREAD_ID")
        or os.environ.get("CODEX_SESSION")
    )
    tmux_pane = os.environ.get("TMUX_PANE")
    tmux_env = os.environ.get("TMUX")
    agent_id = (
        os.environ.get("DAYOA_AGENT_ID")
        or codex_session_id
        or tmux_pane
        or tmux_env
        or f"{user}@{host}"
    )
    agent_kind = os.environ.get("DAYOA_AGENT_KIND")
    if not agent_kind:
        agent_kind = "codex" if codex_session_id else "shell"
    return {
        "agent_id": agent_id,
        "agent_kind": agent_kind,
        "codex_session_id": codex_session_id,
        "human_requestor": human_requestor
        or os.environ.get("DAYOA_HUMAN_REQUESTOR")
        or user,
        "host": host,
        "pid": os.getpid(),
        "user": user,
        "cwd": os.getcwd(),
        "tmux_session": tmux_session
        or os.environ.get("DAYOA_TMUX_SESSION")
        or os.environ.get("TMUX_SESSION"),
        "tmux_pane": tmux_pane,
        "intent": intent,
        "operation": operation,
        "command_summary": command_summary,
    }


def ensure_owner_metadata(analysis_root: AnalysisRootArg) -> dict[str, object]:
    root = normalize_analysis_root(analysis_root)
    meta_dir = agent_dir(root)
    meta_dir.mkdir(parents=True, exist_ok=True)
    path = owner_metadata_path(root)
    identity = _analysis_identity(root)
    existing: dict[str, object] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AnalysisLockError(f"Invalid owner metadata JSON: {path}") from exc
    payload = {
        "schema_version": LOCK_SCHEMA_VERSION,
        "created_at": existing.get("created_at") or utc_iso(),
        "updated_at": utc_iso(),
        **identity,
        "owning_ledger": os.environ.get("DAYOA_LEDGER_PATH"),
    }
    _write_json(path, payload)
    return payload


def read_active_lock(analysis_root: AnalysisRootArg) -> Optional[dict[str, object]]:
    root = normalize_analysis_root(analysis_root)
    path = lock_owner_path(root)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AnalysisLockError(f"Invalid active lock owner JSON: {path}") from exc
    return payload


def lock_status(analysis_root: AnalysisRootArg) -> dict[str, object]:
    root = normalize_analysis_root(analysis_root)
    active = read_active_lock(root)
    payload: dict[str, object] = {
        "analysis_root": str(root),
        "locked": active is not None,
        "lock_dir": str(lock_dir(root)),
        "owner": active,
    }
    return payload


def _same_agent(current: Mapping[str, object], owner: Mapping[str, object]) -> bool:
    current_id = str(current.get("agent_id") or "")
    owner_id = str(owner.get("agent_id") or "")
    return bool(current_id and owner_id and current_id == owner_id)


def lock_state_seen(analysis_root: AnalysisRootArg) -> dict[str, object]:
    active = read_active_lock(analysis_root)
    if not active:
        return {"locked": False, "owner": None}
    return {
        "locked": True,
        "owner": {
            "agent_id": active.get("agent_id"),
            "agent_kind": active.get("agent_kind"),
            "codex_session_id": active.get("codex_session_id"),
            "human_requestor": active.get("human_requestor"),
            "created_at": active.get("created_at"),
            "heartbeat_at": active.get("heartbeat_at"),
            "operation_scope": active.get("operation_scope"),
            "command_summary": active.get("command_summary"),
        },
    }


def visit_log_paths(
    analysis_root: AnalysisRootArg, timestamp: Optional[dt.datetime] = None
) -> tuple[Path, Path]:
    root = normalize_analysis_root(analysis_root)
    ts = timestamp or utc_now()
    day = ts.strftime("%Y%m%d")
    root_log = agent_dir(root) / "visits" / f"{day}.jsonl"
    central_log = analysis_results_root(root) / ".dayoa_agent_visits" / f"{day}.jsonl"
    return root_log, central_log


def write_visit(
    analysis_root: AnalysisRootArg,
    *,
    mode: str,
    intent: str,
    note: Optional[str] = None,
    event: str = "visit",
    human_requestor: Optional[str] = None,
    operation: Optional[str] = None,
    command_summary: Optional[str] = None,
    s3_visit_uri: Optional[str] = None,
) -> dict[str, object]:
    if mode not in VISIT_MODES:
        raise AnalysisLockError(f"Unsupported visit mode: {mode}")
    root = normalize_analysis_root(analysis_root)
    ensure_owner_metadata(root)
    timestamp = utc_now()
    agent = current_agent_metadata(
        human_requestor=human_requestor,
        intent=intent,
        operation=operation or mode,
        command_summary=command_summary,
    )
    payload: dict[str, object] = {
        "schema_version": VISIT_SCHEMA_VERSION,
        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        "event": event,
        "analysis_root": str(root),
        "mode": mode,
        "intent": intent,
        "note": note,
        "lock_state_seen": lock_state_seen(root),
        **agent,
    }
    root_log, central_log = visit_log_paths(root, timestamp)
    for path in (root_log, central_log):
        path.parent.mkdir(parents=True, exist_ok=True)
        _append_jsonl(path, payload)
    if s3_visit_uri:
        payload["s3_visit_object"] = write_s3_visit(s3_visit_uri, payload)
    return payload


def _heartbeat_path(root: Path) -> Path:
    return lock_dir(root) / "heartbeat.jsonl"


def acquire_lock(
    analysis_root: AnalysisRootArg,
    *,
    operation: str,
    intent: str,
    human_requestor: Optional[str] = None,
    command_summary: Optional[str] = None,
    operation_scope: Optional[str] = None,
) -> dict[str, object]:
    if operation not in PROTECTED_OPERATIONS:
        raise AnalysisLockError(f"Lock acquisition is only for protected operations: {operation}")
    root = normalize_analysis_root(analysis_root)
    ensure_owner_metadata(root)
    current = current_agent_metadata(
        human_requestor=human_requestor,
        intent=intent,
        operation=operation,
        command_summary=command_summary,
    )
    lock = lock_dir(root)
    try:
        lock.mkdir()
    except FileExistsError as exc:
        active = read_active_lock(root)
        if active and _same_agent(current, active):
            heartbeat_lock(root, note="reentrant acquire by current owner")
            active["already_owned"] = True
            return active
        raise AnalysisLockError(
            "Analysis root is already locked by another owner: "
            + json.dumps(lock_state_seen(root), sort_keys=True)
        ) from exc

    payload: dict[str, object] = {
        "schema_version": LOCK_SCHEMA_VERSION,
        "analysis_root": str(root),
        "created_at": utc_iso(),
        "heartbeat_at": utc_iso(),
        "operation": operation,
        "operation_scope": operation_scope or operation,
        **current,
    }
    _write_json(lock / "owner.json", payload)
    _append_jsonl(_heartbeat_path(root), {"timestamp": utc_iso(), "event": "acquire", **payload})
    write_visit(
        root,
        mode=operation,
        intent=intent,
        note="write lock acquired",
        event="lock_acquire",
        human_requestor=human_requestor,
        operation=operation,
        command_summary=command_summary,
    )
    return payload


def heartbeat_lock(
    analysis_root: AnalysisRootArg,
    *,
    note: Optional[str] = None,
    human_requestor: Optional[str] = None,
) -> dict[str, object]:
    root = normalize_analysis_root(analysis_root)
    current = current_agent_metadata(human_requestor=human_requestor)
    active = read_active_lock(root)
    if not active:
        raise AnalysisLockError("No active write lock to heartbeat: " + str(root))
    if not _same_agent(current, active):
        raise AnalysisLockError(
            "Cannot heartbeat a lock owned by another agent: "
            + json.dumps(lock_state_seen(root), sort_keys=True)
        )
    active["heartbeat_at"] = utc_iso()
    _write_json(lock_owner_path(root), active)
    event = {"timestamp": utc_iso(), "event": "heartbeat", "note": note, **active}
    _append_jsonl(_heartbeat_path(root), event)
    return active


def release_lock(
    analysis_root: AnalysisRootArg,
    *,
    human_requestor: Optional[str] = None,
    note: Optional[str] = None,
) -> dict[str, object]:
    root = normalize_analysis_root(analysis_root)
    current = current_agent_metadata(human_requestor=human_requestor)
    active = read_active_lock(root)
    if not active:
        raise AnalysisLockError("No active write lock to release: " + str(root))
    if not _same_agent(current, active):
        raise AnalysisLockError(
            "Cannot release a lock owned by another agent: "
            + json.dumps(lock_state_seen(root), sort_keys=True)
        )
    payload = {"timestamp": utc_iso(), "event": "release", "note": note, "released_lock": active}
    _append_jsonl(lock_dir(root) / "release.jsonl", payload)
    shutil.rmtree(lock_dir(root))
    write_visit(
        root,
        mode=str(active.get("operation") or "write"),
        intent=str(active.get("intent") or "release write lock"),
        note=note or "write lock released",
        event="lock_release",
        human_requestor=human_requestor,
        operation=str(active.get("operation") or "write"),
    )
    return payload


def takeover_token(
    analysis_root: AnalysisRootArg,
    *,
    operation: str,
) -> str:
    if operation not in PROTECTED_OPERATIONS:
        raise AnalysisLockError(f"Takeover operation must be protected: {operation}")
    root = normalize_analysis_root(analysis_root)
    active = read_active_lock(root)
    if not active:
        raise AnalysisLockError("No active write lock to take over: " + str(root))
    token_basis = {
        "analysis_root": str(root),
        "operation": operation,
        "owner_agent_id": active.get("agent_id"),
        "owner_created_at": active.get("created_at"),
        "owner_heartbeat_at": active.get("heartbeat_at"),
    }
    return hashlib.sha256(json.dumps(token_basis, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def takeover_request(
    analysis_root: AnalysisRootArg, *, operation: str, reason: str
) -> dict[str, object]:
    root = normalize_analysis_root(analysis_root)
    active = read_active_lock(root)
    if not active:
        raise AnalysisLockError("No active write lock to take over: " + str(root))
    token = takeover_token(root, operation=operation)
    write_visit(
        root,
        mode=operation,
        intent="request takeover",
        note=reason,
        event="takeover_request",
        operation=operation,
    )
    return {
        "analysis_root": str(root),
        "operation": operation,
        "token": token,
        "current_owner": active,
        "reason": reason,
    }


def takeover_lock(
    analysis_root: AnalysisRootArg,
    *,
    operation: str,
    confirm_token: str,
    approved_by: str,
    reason: str,
    intent: str,
    human_requestor: Optional[str] = None,
    command_summary: Optional[str] = None,
) -> dict[str, object]:
    if not approved_by.strip():
        raise AnalysisLockError("--approved-by is required for lock takeover")
    if not reason.strip():
        raise AnalysisLockError("--reason is required for lock takeover")
    root = normalize_analysis_root(analysis_root)
    expected = takeover_token(root, operation=operation)
    if confirm_token != expected:
        raise AnalysisLockError("Takeover confirmation token does not match current lock")
    previous_owner = read_active_lock(root)
    if not previous_owner:
        raise AnalysisLockError("No active write lock to take over: " + str(root))
    takeover_event = {
        "timestamp": utc_iso(),
        "event": "takeover",
        "analysis_root": str(root),
        "operation": operation,
        "approved_by": approved_by,
        "reason": reason,
        "previous_owner": previous_owner,
        "new_agent": current_agent_metadata(
            human_requestor=human_requestor,
            intent=intent,
            operation=operation,
            command_summary=command_summary,
        ),
    }
    _append_jsonl(agent_dir(root) / "takeovers.jsonl", takeover_event)
    shutil.rmtree(lock_dir(root))
    acquired = acquire_lock(
        root,
        operation=operation,
        intent=intent,
        human_requestor=human_requestor,
        command_summary=command_summary,
        operation_scope=f"takeover:{operation}",
    )
    acquired["takeover"] = takeover_event
    return acquired


def assert_operation_allowed(
    analysis_root: AnalysisRootArg,
    *,
    operation: str,
    intent: str,
    human_requestor: Optional[str] = None,
    command_summary: Optional[str] = None,
) -> dict[str, object]:
    root = normalize_analysis_root(analysis_root)
    if operation in READ_MODES:
        return write_visit(
            root,
            mode=operation,
            intent=intent,
            note="read/export operation allowed without write lock",
            event="guard_allowed",
            human_requestor=human_requestor,
            operation=operation,
            command_summary=command_summary,
        )
    if operation not in PROTECTED_OPERATIONS:
        raise AnalysisLockError(f"Unsupported guarded operation: {operation}")
    active = read_active_lock(root)
    if not active:
        raise AnalysisLockError(
            f"Operation {operation!r} requires a write lock owned by the current agent"
        )
    current = current_agent_metadata(human_requestor=human_requestor)
    if not _same_agent(current, active):
        raise AnalysisLockError(
            f"Operation {operation!r} is blocked by a foreign write lock: "
            + json.dumps(lock_state_seen(root), sort_keys=True)
        )
    heartbeat_lock(root, note=f"guard allowed {operation}", human_requestor=human_requestor)
    return write_visit(
        root,
        mode=operation,
        intent=intent,
        note="protected operation allowed for current lock owner",
        event="guard_allowed",
        human_requestor=human_requestor,
        operation=operation,
        command_summary=command_summary,
    )


def guarded_run(
    analysis_root: AnalysisRootArg,
    *,
    operation: str,
    intent: str,
    command: Sequence[str],
    human_requestor: Optional[str] = None,
) -> int:
    command_summary = " ".join(command)
    assert_operation_allowed(
        analysis_root,
        operation=operation,
        intent=intent,
        human_requestor=human_requestor,
        command_summary=command_summary,
    )
    result = subprocess.run(list(command), check=False)
    write_visit(
        analysis_root,
        mode=operation,
        intent=intent,
        note=f"guarded command completed rc={result.returncode}",
        event="guard_complete",
        human_requestor=human_requestor,
        operation=operation,
        command_summary=command_summary,
    )
    return result.returncode


def write_s3_visit(s3_uri: str, payload: Mapping[str, object]) -> str:
    parsed = urlparse(s3_uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise AnalysisLockError("S3 visit URI must be s3://bucket/prefix: " + s3_uri)
    prefix = parsed.path.strip("/")
    day = utc_now()
    agent = _safe_segment(str(payload.get("agent_id") or "agent"))
    key_parts = []
    if prefix:
        key_parts.append(prefix)
    key_parts.extend(
        [
            "_dayoa_agent_visits",
            day.strftime("%Y"),
            day.strftime("%m"),
            day.strftime("%d"),
            f"{utc_stamp()}_{agent}.json",
        ]
    )
    key = "/".join(key_parts)
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - dependency exists in DAY-EC
        raise AnalysisLockError("boto3 is required to write S3 visit markers") from exc
    boto3.client("s3").put_object(
        Bucket=parsed.netloc,
        Key=key,
        Body=json.dumps(payload, indent=2, sort_keys=True, default=_json_default).encode("utf-8"),
        ContentType="application/json",
    )
    return f"s3://{parsed.netloc}/{key}"


def cli_payload(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=_json_default)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Small module CLI for direct Python smoke tests."""

    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) < 2:
        print("usage: python -m daylily_ec.analysis_lock status ANALYSIS_ROOT", file=sys.stderr)
        return 2
    command = args[0]
    root = args[1]
    try:
        if command == "status":
            print(cli_payload(lock_status(root)))
            return 0
        raise AnalysisLockError("Unsupported module command: " + command)
    except AnalysisLockError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
