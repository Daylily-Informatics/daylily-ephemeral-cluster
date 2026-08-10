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

CONTROLLER_TARGET_SCHEMA = "dyec.controller_target.v1"
WORKFLOW_OBSERVABILITY_SCHEMA = "dyec.workflow_observability.v1"
SNAKEMAKE_LOG_SUFFIX = ".snakemake.log"
SNAKEMAKE_TAIL_ENCODING = "zlib+base64"
MAX_SNAKEMAKE_TAIL_BYTES = 8 * 1024 * 1024
MAX_ENCODED_SNAKEMAKE_TAIL_BYTES = 12 * 1024

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
    encoded = base64.b64encode(zlib.compress(source, level=9)).decode("ascii")
    bootstrap = (
        "import base64,zlib;"
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


def decode_snakemake_tail(payload: Any) -> str:
    """Decode and integrity-check a Snakemake tail returned by the remote probe."""

    if not isinstance(payload, dict):
        raise WorkflowObservabilityError("Snakemake tail payload is missing")
    if payload.get("encoding") != SNAKEMAKE_TAIL_ENCODING:
        raise WorkflowObservabilityError("Snakemake tail payload has an unsupported encoding")
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
        raise WorkflowObservabilityError("Snakemake tail payload fields are invalid")
    try:
        raw = zlib.decompress(base64.b64decode(encoded, validate=True))
    except (binascii.Error, zlib.error) as exc:
        raise WorkflowObservabilityError("Snakemake tail payload is corrupt") from exc
    if len(raw) != byte_count or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise WorkflowObservabilityError("Snakemake tail payload failed integrity validation")
    return raw.decode("utf-8", errors="replace")


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


def _validate_status_receipt(
    payload: dict[str, Any], *, session: str, repo_path: str, path: Path
) -> tuple[Optional[int], bool]:
    if payload.get("session_name") != session or payload.get("repo_path") != repo_path:
        raise WorkflowObservabilityError(
            f"workflow status receipt does not match controller target: {path}"
        )
    completed_at = payload.get("completed_at")
    exit_code = payload.get("exit_code")
    if completed_at is None and exit_code is None:
        return None, False
    if not isinstance(completed_at, str) or not completed_at.strip():
        raise WorkflowObservabilityError(
            f"workflow status receipt has an unattributable terminal result: {path}"
        )
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise WorkflowObservabilityError(
            f"workflow status receipt has a non-integer terminal exit_code: {path}"
        )
    return exit_code, True


def collect_workflow_observability(
    *,
    mode: str,
    session: Optional[str] = None,
    run_dir: Optional[str] = None,
    repo_path: Optional[str] = None,
    controller_pid: Optional[int] = None,
    snakemake_log: Optional[str] = None,
    tail_lines: Optional[int] = None,
) -> dict[str, Any]:
    """Collect exact local headnode evidence for one controller invocation."""

    if mode not in {"launched", "manual"}:
        raise WorkflowObservabilityError("mode must be launched or manual")
    status_payload: Optional[dict[str, Any]] = None
    status_path: Optional[Path] = None
    controller_source: str
    tmux_session = session
    if mode == "launched":
        if not run_dir or repo_path is not None or controller_pid is not None or snakemake_log:
            raise WorkflowObservabilityError(
                "launched inspection requires run_dir and no manual attribution options"
            )
        run_path = Path(run_dir)
        status_path = run_path / "status.json"
        target_path = run_path / "controller_target.json"
        status_payload = _read_json_object(status_path, label="workflow status receipt")
        target = _read_json_object(target_path, label="controller target receipt")
        if target.get("schema_version") != CONTROLLER_TARGET_SCHEMA:
            raise WorkflowObservabilityError(
                f"controller target has an unsupported schema version: {target_path}"
            )
        target_session = target.get("controller_id")
        target_pid = target.get("pid")
        target_repo = target.get("cwd")
        if (
            not isinstance(target_session, str)
            or not target_session
            or isinstance(target_pid, bool)
            or not isinstance(target_pid, int)
            or target_pid < 1
            or not isinstance(target_repo, str)
        ):
            raise WorkflowObservabilityError(f"controller target fields are invalid: {target_path}")
        status_session = status_payload.get("session_name")
        if not isinstance(status_session, str) or not status_session:
            raise WorkflowObservabilityError(
                f"workflow status receipt has an invalid session name: {status_path}"
            )
        if session and status_session != session:
            raise WorkflowObservabilityError(
                f"workflow status receipt does not match requested session: {status_path}"
            )
        session = status_session
        tmux_session = target_session
        controller_pid = target_pid
        repo_path = normalize_repo_path(target_repo)
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
        receipt_log = status_payload.get("snakemake_log_path") if status_payload else None
        if isinstance(receipt_log, str) and receipt_log and status_payload is not None:
            receipt_attribution = status_payload.get("snakemake_log_attribution")
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

    terminal_rc: Optional[int] = None
    terminal_rc_attributed = False
    terminal_rc_source: Optional[str] = None
    if status_payload is not None and status_path is not None and session is not None:
        terminal_rc, terminal_rc_attributed = _validate_status_receipt(
            status_payload,
            session=session,
            repo_path=repo_path,
            path=status_path,
        )
        if terminal_rc_attributed:
            terminal_rc_source = status_path.as_posix()
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
    return {
        "schema_version": WORKFLOW_OBSERVABILITY_SCHEMA,
        "state": state,
        "mode": mode,
        "session": session,
        "run_dir": run_dir,
        "repo_path": repo_path,
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
            "exit_code": terminal_rc,
            "exit_code_attributed": terminal_rc_attributed,
            "exit_code_source": terminal_rc_source,
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
        )
    except WorkflowObservabilityError as exc:
        print(f"DYEC workflow observability error: {exc}", file=sys.stderr)
        return 2
    if args.tail_lines is not None:
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
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
