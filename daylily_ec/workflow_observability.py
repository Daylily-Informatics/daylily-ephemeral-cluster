"""Exact, provider-neutral observability for one DayOA controller invocation."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import zlib
from collections import Counter, deque
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Optional

from daylily_ec.execution_status import (
    STATUS_SCHEMA_VERSION,
    ExecutionStatusError,
    attempt_exit_codes,
    controller_attempt,
    read_execution_status,
    status_path_for_repo,
)

CONTROLLER_TARGET_SCHEMA = "dyec.controller_target.v2"
WORKFLOW_OBSERVABILITY_SCHEMA = "dyec.workflow_observability.v1"
SNAKEMAKE_LOG_SUFFIX = ".snakemake.log"
SNAKEMAKE_TAIL_ENCODING = "zlib+base64"
MAX_SNAKEMAKE_TAIL_BYTES = 8 * 1024 * 1024
MAX_ENCODED_SNAKEMAKE_TAIL_BYTES = 12 * 1024
MAX_TRANSPORT_COLLECTION_RECORDS = 20
MAX_SNAKEMAKE_MATCH_TEXT_BYTES = 512
MAX_SNAKEMAKE_MATCH_CONTEXT_LINES = 200
MAX_SNAKEMAKE_MATCHES = 10

SUBMITTED_RE = re.compile(
    r"^Submitted job (?P<job_id>\d+) with external jobid ['\"](?P<external_id>[^'\"]+)['\"]\.\s*$"
)
FINISHED_RE = re.compile(r"^Finished job (?P<job_id>\d+)\.\s*$")
PROGRESS_RE = re.compile(r"^\d+ of \d+ steps \(\d+%\) done\s*$")
FAILURE_PATTERNS = (
    ("job_execution_failed", re.compile(r"^Exiting because a job execution failed\.")),
    ("workflow_error", re.compile(r"^WorkflowError:\s*(?:$|\S)")),
    ("rule_error", re.compile(r"^Error in rule [A-Za-z0-9_.-]+:\s*$")),
    ("rule_exception", re.compile(r"^RuleException(?: in rule [A-Za-z0-9_.-]+)?:\s*$")),
    (
        "jobs_incomplete",
        re.compile(r"^At least one job did not complete successfully\.\s*$"),
    ),
)


class WorkflowObservabilityError(RuntimeError):
    """Raised when exact workflow attribution cannot be established."""


def build_remote_probe_command(arguments: Sequence[str]) -> str:
    """Build a compressed self-contained probe; do not depend on headnode DYEC version."""

    source = Path(__file__).read_bytes()
    execution_status_source = Path(__file__).with_name("execution_status.py").read_bytes()
    encoded = base64.b64encode(zlib.compress(source, level=9)).decode("ascii")
    execution_status_encoded = base64.b64encode(
        zlib.compress(execution_status_source, level=9)
    ).decode("ascii")
    bootstrap = (
        "import base64,sys,types,zlib;"
        "package=sys.modules.setdefault('daylily_ec',types.ModuleType('daylily_ec'));"
        "package.__path__=getattr(package,'__path__',[]);"
        "dependency=types.ModuleType('daylily_ec.execution_status');"
        "exec(compile(zlib.decompress(base64.b64decode("
        + repr(execution_status_encoded)
        + ")), '<dyec-execution-status>', 'exec'), dependency.__dict__);"
        "sys.modules['daylily_ec.execution_status']=dependency;"
        "exec(compile(zlib.decompress(base64.b64decode(" + repr(encoded) + ")),"
        "'<dyec-workflow-observability>','exec'))"
    )
    return shlex.join(["python3", "-c", bootstrap, *arguments])


def normalize_repo_path(value: str) -> str:
    """Validate one explicit DayOA checkout path on a headnode."""

    raw = str(value or "").strip().rstrip("/")
    if not raw or any(character in raw for character in ("\x00", "\n", "\r")):
        raise WorkflowObservabilityError("--repo-path must be one absolute POSIX path")
    path = PurePosixPath(raw)
    if not path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise WorkflowObservabilityError("--repo-path must be one canonical absolute POSIX path")
    if path.parts[:3] != ("/", "fsx", "analysis_results"):
        raise WorkflowObservabilityError("--repo-path must be under /fsx/analysis_results")
    if path.name != "daylily-omics-analysis":
        raise WorkflowObservabilityError(
            "--repo-path must name the daylily-omics-analysis checkout"
        )
    if len(path.parts) != 6:
        raise WorkflowObservabilityError(
            "--repo-path must be /fsx/analysis_results/<owner>/<analysis_id>/daylily-omics-analysis"
        )
    return path.as_posix()


def normalize_snakemake_log(value: str, *, repo_path: str) -> str:
    """Validate an explicit Snakemake master log within one exact checkout."""

    raw = str(value or "").strip()
    if not raw or any(character in raw for character in ("\x00", "\n", "\r")):
        raise WorkflowObservabilityError("--snakemake-log must be one absolute POSIX path")
    path = PurePosixPath(raw)
    expected_parent = PurePosixPath(repo_path) / ".snakemake" / "log"
    if (
        not path.is_absolute()
        or any(part in {".", ".."} for part in path.parts)
        or path.parent != expected_parent
        or not path.name.endswith(SNAKEMAKE_LOG_SUFFIX)
    ):
        raise WorkflowObservabilityError(
            "--snakemake-log must be an exact <repo-path>/.snakemake/log/*.snakemake.log path"
        )
    return path.as_posix()


def derive_state(
    *,
    controller_live: bool,
    controller_attributed: bool,
    terminal_rc: Optional[int],
    terminal_rc_attributed: bool,
    high_signal_failure: bool,
) -> str:
    """Derive state without using inspection RC, queue emptiness, or stale shell text."""

    if terminal_rc_attributed and terminal_rc is not None:
        return "SUCCEEDED" if terminal_rc == 0 else "FAILED"
    if controller_live and controller_attributed:
        return "RUNNING"
    if high_signal_failure:
        return "FAILED"
    return "UNKNOWN"


def parse_snakemake_lines(lines: Iterable[str]) -> dict[str, Any]:
    """Extract bounded progress, job, and high-signal failure evidence."""

    submitted: list[dict[str, Any]] = []
    finished_ids: list[int] = []
    failure_markers: list[dict[str, str]] = []
    last_progress_line: Optional[str] = None
    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        submitted_match = SUBMITTED_RE.match(line)
        if submitted_match:
            submitted.append(
                {
                    "job_id": int(submitted_match.group("job_id")),
                    "external_job_id": submitted_match.group("external_id"),
                }
            )
            last_progress_line = line
        finished_match = FINISHED_RE.match(line)
        if finished_match:
            finished_ids.append(int(finished_match.group("job_id")))
            last_progress_line = line
        if PROGRESS_RE.match(line):
            last_progress_line = line
        for marker, pattern in FAILURE_PATTERNS:
            if pattern.match(line):
                failure_markers.append({"marker": marker, "line": line})
                break

    finished_set = set(finished_ids)
    for record in submitted:
        record["finished"] = record["job_id"] in finished_set
    return {
        "submitted_count": len(submitted),
        "finished_count": len(finished_ids),
        "submitted": submitted,
        "finished_job_ids": finished_ids,
        "last_progress_line": last_progress_line,
        "failure_markers": failure_markers[-10:],
    }


def bounded_transport_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Bound growing record collections while preserving authoritative totals."""

    jobs = dict(payload["jobs"])
    submitted = list(jobs["submitted"])
    finished_job_ids = list(jobs["finished_job_ids"])
    jobs["submitted"] = submitted[-MAX_TRANSPORT_COLLECTION_RECORDS:]
    jobs["submitted_returned_count"] = len(jobs["submitted"])
    jobs["submitted_truncated"] = len(submitted) > len(jobs["submitted"])
    jobs["finished_job_ids"] = finished_job_ids[-MAX_TRANSPORT_COLLECTION_RECORDS:]
    jobs["finished_job_ids_returned_count"] = len(jobs["finished_job_ids"])
    jobs["finished_job_ids_truncated"] = len(finished_job_ids) > len(jobs["finished_job_ids"])

    slurm = dict(payload["slurm"])
    states = list(slurm["states"])
    slurm["states"] = states[-MAX_TRANSPORT_COLLECTION_RECORDS:]
    slurm["states_count"] = len(states)
    slurm["states_returned_count"] = len(slurm["states"])
    slurm["states_truncated"] = len(states) > len(slurm["states"])

    return {
        **payload,
        "jobs": jobs,
        "slurm": slurm,
        "transport": {
            "bounded": True,
            "max_collection_records": MAX_TRANSPORT_COLLECTION_RECORDS,
        },
    }


def _encoded_snakemake_tail(path: str, *, tail_lines: int) -> dict[str, Any]:
    """Read and encode an exact bounded tail for safe transport in probe JSON."""

    if isinstance(tail_lines, bool) or tail_lines < 1:
        raise WorkflowObservabilityError("--tail-lines must be a positive integer")
    log_path = Path(path)
    if not log_path.is_file():
        raise WorkflowObservabilityError(f"attributed Snakemake log is missing: {path}")
    try:
        with log_path.open("rb") as handle:
            raw = b"".join(deque(handle, maxlen=tail_lines))
    except OSError as exc:
        raise WorkflowObservabilityError(
            f"unable to read attributed Snakemake log: {path}"
        ) from exc
    if len(raw) > MAX_SNAKEMAKE_TAIL_BYTES:
        raise WorkflowObservabilityError(
            "requested Snakemake tail exceeds the 8 MiB transport limit; use fewer --lines"
        )
    encoded = base64.b64encode(zlib.compress(raw, level=9)).decode("ascii")
    if len(encoded.encode("ascii")) > MAX_ENCODED_SNAKEMAKE_TAIL_BYTES:
        raise WorkflowObservabilityError(
            "compressed Snakemake tail exceeds the SSM output limit; use fewer --lines"
        )
    return {
        "encoding": SNAKEMAKE_TAIL_ENCODING,
        "data": encoded,
        "byte_count": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "line_count_requested": tail_lines,
    }


def _normalize_match_text(value: str) -> str:
    resolved = str(value or "")
    if (
        not resolved
        or any(character in resolved for character in ("\x00", "\n", "\r"))
        or len(resolved.encode("utf-8")) > MAX_SNAKEMAKE_MATCH_TEXT_BYTES
    ):
        raise WorkflowObservabilityError(
            "--match must be one non-empty literal line fragment of at most 512 UTF-8 bytes"
        )
    return resolved


def _encoded_snakemake_match_context(
    path: str,
    *,
    match_text: str,
    before_lines: int,
    after_lines: int,
    max_matches: int,
) -> dict[str, Any]:
    """Find bounded literal-match context in one exact attributed log."""

    resolved_match = _normalize_match_text(match_text)
    for value, label in ((before_lines, "--before-lines"), (after_lines, "--after-lines")):
        if isinstance(value, bool) or value < 0 or value > MAX_SNAKEMAKE_MATCH_CONTEXT_LINES:
            raise WorkflowObservabilityError(f"{label} must be between 0 and 200")
    if isinstance(max_matches, bool) or max_matches < 1 or max_matches > MAX_SNAKEMAKE_MATCHES:
        raise WorkflowObservabilityError("--max-matches must be between 1 and 10")

    log_path = Path(path)
    if not log_path.is_file():
        raise WorkflowObservabilityError(f"attributed Snakemake log is missing: {path}")
    preceding: deque[tuple[int, str]] = deque(maxlen=before_lines)
    contexts: list[dict[str, Any]] = []
    current: Optional[dict[str, Any]] = None
    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, line in enumerate(handle, start=1):
                if current is not None:
                    current["lines"].append((line_number, line))
                    current["after_remaining"] -= 1
                    if current["after_remaining"] == 0:
                        contexts.append(current)
                        current = None
                elif resolved_match in line and len(contexts) < max_matches:
                    current = {
                        "match_line": line_number,
                        "lines": [*preceding, (line_number, line)],
                        "after_remaining": after_lines,
                    }
                    if after_lines == 0:
                        contexts.append(current)
                        current = None
                preceding.append((line_number, line))
                if current is None and len(contexts) >= max_matches:
                    break
    except OSError as exc:
        raise WorkflowObservabilityError(
            f"unable to search attributed Snakemake log: {path}"
        ) from exc
    if current is not None:
        contexts.append(current)

    rendered: list[str] = []
    matched_line_numbers: list[int] = []
    for index, context in enumerate(contexts, start=1):
        match_line = int(context["match_line"])
        matched_line_numbers.append(match_line)
        rendered.append(f"=== literal match {index} at line {match_line} ===\n")
        for line_number, line in context["lines"]:
            suffix = "" if line.endswith("\n") else "\n"
            rendered.append(f"{line_number}:{line}{suffix}")
    raw = "".join(rendered).encode("utf-8")
    encoded = base64.b64encode(zlib.compress(raw, level=9)).decode("ascii")
    if len(encoded.encode("ascii")) > MAX_ENCODED_SNAKEMAKE_TAIL_BYTES:
        raise WorkflowObservabilityError(
            "compressed Snakemake match context exceeds the SSM output limit; "
            "use fewer context lines or matches"
        )
    return {
        "encoding": SNAKEMAKE_TAIL_ENCODING,
        "data": encoded,
        "byte_count": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "literal_match": resolved_match,
        "before_lines": before_lines,
        "after_lines": after_lines,
        "max_matches": max_matches,
        "match_count": len(contexts),
        "matched_line_numbers": matched_line_numbers,
    }


def _decode_compressed_log_text(payload: Any, *, label: str) -> str:
    """Decode and integrity-check bounded text returned by the remote probe."""

    if not isinstance(payload, dict):
        raise WorkflowObservabilityError(f"Snakemake {label} payload is missing")
    if payload.get("encoding") != SNAKEMAKE_TAIL_ENCODING:
        raise WorkflowObservabilityError(f"Snakemake {label} payload has an unsupported encoding")
    encoded = payload.get("data")
    byte_count = payload.get("byte_count")
    expected_sha256 = payload.get("sha256")
    if (
        not isinstance(encoded, str)
        or isinstance(byte_count, bool)
        or not isinstance(byte_count, int)
        or byte_count < 0
        or byte_count > MAX_SNAKEMAKE_TAIL_BYTES
        or not isinstance(expected_sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
    ):
        raise WorkflowObservabilityError(f"Snakemake {label} payload fields are invalid")
    try:
        raw = zlib.decompress(base64.b64decode(encoded, validate=True))
    except (binascii.Error, zlib.error) as exc:
        raise WorkflowObservabilityError(f"Snakemake {label} payload is corrupt") from exc
    if len(raw) != byte_count or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise WorkflowObservabilityError(f"Snakemake {label} payload failed integrity validation")
    return raw.decode("utf-8", errors="replace")


def decode_snakemake_tail(payload: Any) -> str:
    """Decode and integrity-check a Snakemake tail returned by the remote probe."""

    return _decode_compressed_log_text(payload, label="tail")


def decode_snakemake_match_context(payload: Any) -> str:
    """Decode bounded literal-match context returned by the remote probe."""

    return _decode_compressed_log_text(payload, label="match context")


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise WorkflowObservabilityError(f"{label} is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowObservabilityError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise WorkflowObservabilityError(f"{label} must contain one JSON object: {path}")
    return payload


def _process_snapshot() -> dict[int, int]:
    parents: dict[int, int] = {}
    proc_root = Path("/proc")
    if not proc_root.is_dir():
        return parents
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text(encoding="utf-8")
            remainder = stat[stat.rfind(")") + 2 :].split()
            parents[int(entry.name)] = int(remainder[1])
        except (OSError, ValueError, IndexError):
            continue
    return parents


def _descendants(controller_pid: int, parents: dict[int, int]) -> set[int]:
    selected = {controller_pid}
    changed = True
    while changed:
        changed = False
        for pid, parent in parents.items():
            if parent in selected and pid not in selected:
                selected.add(pid)
                changed = True
    return selected


def _observed_process(pid: int) -> dict[str, Any]:
    proc_path = Path("/proc") / str(pid)
    if not proc_path.is_dir():
        return {"pid_exists": False, "cwd": None, "command": None}
    try:
        cwd = os.readlink(proc_path / "cwd")
    except OSError:
        cwd = None
    try:
        command = (
            (proc_path / "cmdline")
            .read_bytes()
            .replace(b"\0", b" ")
            .decode("utf-8", errors="replace")
            .strip()
        )
    except OSError:
        command = None
    return {"pid_exists": True, "cwd": cwd, "command": command}


def _tmux_correlates(session: str, controller_pid: int, parents: dict[int, int]) -> bool:
    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-t", f"={session}", "-F", "#{pane_pid}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False
    pane_pids = {int(line) for line in result.stdout.splitlines() if line.strip().isdigit()}
    current = controller_pid
    seen: set[int] = set()
    while current > 0 and current not in seen:
        if current in pane_pids:
            return True
        seen.add(current)
        current = parents.get(current, 0)
    return False


def _open_snakemake_logs(
    controller_pid: int,
    *,
    repo_path: str,
    parents: dict[int, int],
) -> list[str]:
    expected_parent = Path(repo_path) / ".snakemake" / "log"
    candidates: set[str] = set()
    for pid in _descendants(controller_pid, parents):
        fd_dir = Path("/proc") / str(pid) / "fd"
        try:
            descriptors = list(fd_dir.iterdir())
        except OSError:
            continue
        for descriptor in descriptors:
            try:
                target = Path(os.readlink(descriptor))
            except OSError:
                continue
            if target.parent == expected_parent and target.name.endswith(SNAKEMAKE_LOG_SUFFIX):
                candidates.add(target.as_posix())
    return sorted(candidates)


def _log_evidence(path: str) -> dict[str, Any]:
    log_path = Path(path)
    if not log_path.is_file():
        raise WorkflowObservabilityError(f"attributed Snakemake log is missing: {path}")
    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        evidence = parse_snakemake_lines(handle)
    modified_at = datetime.fromtimestamp(log_path.stat().st_mtime, timezone.utc)
    if evidence["last_progress_line"] is not None:
        evidence["last_progress_at"] = modified_at.isoformat().replace("+00:00", "Z")
    else:
        evidence["last_progress_at"] = None
    return evidence


def _slurm_states(external_job_ids: Sequence[str]) -> dict[str, Any]:
    ids = sorted(
        {job_id for job_id in external_job_ids if re.fullmatch(r"\d+(?:_[0-9]+)?", job_id)}
    )
    if not ids:
        return {"available": True, "states": [], "state_counts": {}}
    try:
        result = subprocess.run(
            ["squeue", "--noheader", "--jobs", ",".join(ids), "--format", "%i|%T|%j|%R"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {
            "available": False,
            "states": [],
            "state_counts": {},
            "error": type(exc).__name__,
        }
    if result.returncode != 0:
        return {
            "available": False,
            "states": [],
            "state_counts": {},
            "error": result.stderr.strip() or f"squeue rc={result.returncode}",
        }
    states: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        fields = line.split("|", 3)
        if len(fields) == 4:
            states.append(
                {"job_id": fields[0], "state": fields[1], "name": fields[2], "reason": fields[3]}
            )
    return {
        "available": True,
        "states": states,
        "state_counts": dict(sorted(Counter(item["state"] for item in states).items())),
    }


def _read_controller_target(path: Path) -> dict[str, Any]:
    """Read the v2 target that names one immutable clone-resident attempt."""

    target = _read_json_object(path, label="controller target receipt")
    required = {
        "schema_version",
        "controller_id",
        "pid",
        "cwd",
        "log_path",
        "dag_path",
        "analysis_root",
        "status_attempt_id",
    }
    if set(target) != required:
        raise WorkflowObservabilityError(f"controller target fields are invalid: {path}")
    if target["schema_version"] != CONTROLLER_TARGET_SCHEMA:
        raise WorkflowObservabilityError(
            f"controller target has an unsupported schema version: {path}"
        )
    session = target["controller_id"]
    pid = target["pid"]
    target_repo = target["cwd"]
    analysis_root = target["analysis_root"]
    attempt_id = target["status_attempt_id"]
    if (
        not isinstance(session, str)
        or not session
        or isinstance(pid, bool)
        or not isinstance(pid, int)
        or pid < 1
        or not isinstance(target_repo, str)
        or not isinstance(analysis_root, str)
        or not isinstance(attempt_id, str)
        or not attempt_id
    ):
        raise WorkflowObservabilityError(f"controller target fields are invalid: {path}")
    repo_path = normalize_repo_path(target_repo)
    if analysis_root != str(PurePosixPath(repo_path).parent):
        raise WorkflowObservabilityError(
            f"controller target analysis_root does not match its clone path: {path}"
        )
    for named_path in ("log_path", "dag_path"):
        value = target[named_path]
        if not isinstance(value, str) or not value.startswith(repo_path + "/"):
            raise WorkflowObservabilityError(
                f"controller target {named_path} is not within its clone path: {path}"
            )
    return target


def collect_workflow_observability(
    *,
    mode: str,
    session: Optional[str] = None,
    run_dir: Optional[str] = None,
    repo_path: Optional[str] = None,
    controller_pid: Optional[int] = None,
    snakemake_log: Optional[str] = None,
    tail_lines: Optional[int] = None,
    match_text: Optional[str] = None,
    before_lines: int = 40,
    after_lines: int = 80,
    max_matches: int = 1,
) -> dict[str, Any]:
    """Collect exact local headnode evidence for one controller invocation."""

    if mode not in {"launched", "manual"}:
        raise WorkflowObservabilityError("mode must be launched or manual")
    if tail_lines is not None and match_text is not None:
        raise WorkflowObservabilityError("--tail-lines and --match are mutually exclusive")
    status_payload: Optional[dict[str, Any]] = None
    status_attempt: Optional[dict[str, Any]] = None
    status_path: Optional[Path] = None
    controller_source: str
    tmux_session = session
    if mode == "launched":
        if not run_dir or repo_path is not None or controller_pid is not None or snakemake_log:
            raise WorkflowObservabilityError(
                "launched inspection requires run_dir and no manual attribution options"
            )
        run_path = Path(run_dir)
        target_path = run_path / "controller_target.json"
        target = _read_controller_target(target_path)
        target_session = target["controller_id"]
        target_pid = target["pid"]
        target_repo = target["cwd"]
        if session and target_session != session:
            raise WorkflowObservabilityError(
                f"controller target does not match requested session: {target_path}"
            )
        session = target_session
        tmux_session = target_session
        controller_pid = target_pid
        repo_path = normalize_repo_path(target_repo)
        status_path = status_path_for_repo(repo_path)
        try:
            status_payload = read_execution_status(
                status_path,
                repo_path=repo_path,
                analysis_root=target["analysis_root"],
            )
            status_attempt = controller_attempt(
                status_payload,
                attempt_id=target["status_attempt_id"],
                session_name=target_session,
            )
        except ExecutionStatusError as exc:
            raise WorkflowObservabilityError(str(exc)) from exc
        controller_source = target_path.as_posix()
    else:
        if not repo_path or controller_pid is None or run_dir is not None:
            raise WorkflowObservabilityError(
                "manual inspection requires repo_path and controller_pid and forbids run_dir"
            )
        if isinstance(controller_pid, bool) or controller_pid < 1:
            raise WorkflowObservabilityError("--controller-pid must be a positive integer")
        repo_path = normalize_repo_path(repo_path)
        if snakemake_log:
            snakemake_log = normalize_snakemake_log(snakemake_log, repo_path=repo_path)
        controller_source = "explicit --controller-pid"

    assert controller_pid is not None
    assert repo_path is not None
    parents = _process_snapshot()
    observed = _observed_process(controller_pid)
    pid_exists = bool(observed["pid_exists"])
    cwd_matches = observed["cwd"] == repo_path
    observed_command = str(observed["command"] or "")
    if mode == "launched":
        command_matches = "dyec-controller-launch.sh" in observed_command
    else:
        command_matches = bool(
            re.search(r"(?:^|[/\s])(snakemake|day_run)(?:$|\s)", observed_command)
        )
    tmux_correlated: Optional[bool] = None
    if tmux_session and pid_exists:
        tmux_correlated = _tmux_correlates(tmux_session, controller_pid, parents)
    attributed = pid_exists and cwd_matches and command_matches and (tmux_correlated is not False)

    open_logs = (
        _open_snakemake_logs(controller_pid, repo_path=repo_path, parents=parents)
        if attributed
        else []
    )
    log_path: Optional[str] = None
    log_source: Optional[str] = None
    log_problem: Optional[str] = None
    if snakemake_log:
        if pid_exists and not attributed:
            log_problem = "live controller PID is not attributable to the requested invocation"
        elif open_logs and snakemake_log not in open_logs:
            log_problem = "explicit log is not open by the attributed controller process tree"
        else:
            log_path = snakemake_log
            log_source = "explicit --snakemake-log"
    elif len(open_logs) == 1:
        log_path = open_logs[0]
        log_source = "controller process-tree open file descriptor"
    elif len(open_logs) > 1:
        log_problem = "multiple Snakemake logs are open by the attributed controller process tree"
    else:
        snakemake_receipt = status_attempt["snakemake"] if status_attempt else None
        receipt_log = (
            snakemake_receipt.get("log_path")
            if isinstance(snakemake_receipt, dict)
            else None
        )
        if isinstance(receipt_log, str) and receipt_log and snakemake_receipt is not None:
            receipt_attribution = snakemake_receipt.get("log_attribution")
            if receipt_attribution != "exact invocation file-set difference":
                log_problem = "status receipt log lacks exact invocation attribution"
            else:
                try:
                    log_path = normalize_snakemake_log(receipt_log, repo_path=repo_path)
                    log_source = str(status_path)
                except WorkflowObservabilityError as exc:
                    log_problem = str(exc)
        else:
            log_problem = "no exact Snakemake log is attributable to this invocation"

    if log_path:
        log = _log_evidence(log_path)
    else:
        log = {
            "submitted_count": 0,
            "finished_count": 0,
            "submitted": [],
            "finished_job_ids": [],
            "last_progress_line": None,
            "last_progress_at": None,
            "failure_markers": [],
        }
    slurm = _slurm_states([item["external_job_id"] for item in log["submitted"]])

    terminal_codes = {
        "controller_exit_code": None,
        "day_run_exit_code": None,
        "snakemake_exit_code": None,
    }
    terminal_rc: Optional[int] = None
    terminal_rc_attributed = False
    terminal_rc_source: Optional[str] = None
    if status_attempt is not None and status_path is not None:
        terminal_codes = attempt_exit_codes(status_attempt)
        terminal_rc = terminal_codes["controller_exit_code"]
        terminal_rc_attributed = terminal_rc is not None
        if terminal_rc_attributed:
            terminal_rc_source = (
                f"{status_path.as_posix()}#attempts/{status_attempt['attempt_id']}/controller/exit_code"
            )
    state = derive_state(
        controller_live=pid_exists,
        controller_attributed=attributed,
        terminal_rc=terminal_rc,
        terminal_rc_attributed=terminal_rc_attributed,
        high_signal_failure=bool(log["failure_markers"]),
    )
    snakemake_log_payload: dict[str, Any] = {
        "path": log_path,
        "source": log_source,
        "problem": log_problem,
        "open_candidates": open_logs,
    }
    if tail_lines is not None and log_path is not None:
        snakemake_log_payload["tail"] = _encoded_snakemake_tail(
            log_path,
            tail_lines=tail_lines,
        )
    if match_text is not None and log_path is not None:
        snakemake_log_payload["match_context"] = _encoded_snakemake_match_context(
            log_path,
            match_text=match_text,
            before_lines=before_lines,
            after_lines=after_lines,
            max_matches=max_matches,
        )
    return {
        "schema_version": WORKFLOW_OBSERVABILITY_SCHEMA,
        "state": state,
        "mode": mode,
        "session": session,
        "run_dir": run_dir,
        "repo_path": repo_path,
        "status": (
            {
                "path": status_path.as_posix(),
                "schema_version": STATUS_SCHEMA_VERSION,
                "attempt_id": status_attempt["attempt_id"],
            }
            if status_path is not None and status_attempt is not None
            else None
        ),
        "controller": {
            "pid": controller_pid,
            "pid_source": controller_source,
            "tmux_session": tmux_session,
            "pid_exists": pid_exists,
            "live": attributed,
            "attributed": attributed,
            "observed_cwd": observed["cwd"],
            "expected_cwd": repo_path,
            "command": observed["command"],
            "command_matches": command_matches,
            "tmux_correlated": tmux_correlated,
        },
        "snakemake_log": snakemake_log_payload,
        "last_progress_at": log["last_progress_at"],
        "last_progress_line": log["last_progress_line"],
        "jobs": {
            "submitted_count": log["submitted_count"],
            "finished_count": log["finished_count"],
            "submitted": log["submitted"],
            "finished_job_ids": log["finished_job_ids"],
        },
        "slurm": slurm,
        "terminal": {
            **terminal_codes,
            "controller_exit_code_attributed": terminal_rc_attributed,
            "controller_exit_code_source": terminal_rc_source,
            "failure_markers": log["failure_markers"],
        },
        "semantics": {
            "queue_emptiness_is_success": False,
            "inspection_exit_code_is_workflow_exit_code": False,
            "generic_error_text_is_terminal_failure": False,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--mode", choices=("launched", "manual"), required=True)
    parser.add_argument("--session")
    parser.add_argument("--run-dir")
    parser.add_argument("--repo-path")
    parser.add_argument("--controller-pid", type=int)
    parser.add_argument("--snakemake-log")
    parser.add_argument("--tail-lines", type=int)
    parser.add_argument("--match")
    parser.add_argument("--before-lines", type=int, default=40)
    parser.add_argument("--after-lines", type=int, default=80)
    parser.add_argument("--max-matches", type=int, default=1)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = collect_workflow_observability(
            mode=args.mode,
            session=args.session,
            run_dir=args.run_dir,
            repo_path=args.repo_path,
            controller_pid=args.controller_pid,
            snakemake_log=args.snakemake_log,
            tail_lines=args.tail_lines,
            match_text=args.match,
            before_lines=args.before_lines,
            after_lines=args.after_lines,
            max_matches=args.max_matches,
        )
    except WorkflowObservabilityError as exc:
        print(f"DYEC workflow observability error: {exc}", file=sys.stderr)
        return 2
    if args.tail_lines is not None or args.match is not None:
        payload = {
            "schema_version": payload["schema_version"],
            "repo_path": payload["repo_path"],
            "controller": {
                "pid": payload["controller"]["pid"],
                "live": payload["controller"]["live"],
                "attributed": payload["controller"]["attributed"],
            },
            "snakemake_log": payload["snakemake_log"],
        }
    else:
        payload = bounded_transport_payload(payload)
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
