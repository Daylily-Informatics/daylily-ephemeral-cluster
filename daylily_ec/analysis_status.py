"""Read-only, exact-root DayOA workflow status collection."""

from __future__ import annotations

import csv
import json
import re
import shlex
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence


class AnalysisStatusError(RuntimeError):
    """Raised when an analysis status request violates the inspection contract."""


Runner = Callable[..., subprocess.CompletedProcess[str]]
PROGRESS_RE = re.compile(r"(?P<done>\d+) of (?P<total>\d+) steps \((?P<pct>\d+)%\) done")
RULE_RE = re.compile(r"^(?:local)?rule (?P<rule>[A-Za-z0-9_.-]+):", re.MULTILINE)
SUBMITTED_JOB_RE = re.compile(r"\bSubmitted job (?P<job_id>\d+)\b")
FINISHED_JOB_RE = re.compile(r"\bFinished job (?P<job_id>\d+)\b")
CONTROLLER_RC_RE = re.compile(
    r"(?:__DAYOA_CONTROLLER_RC__|DAYOA_CONTROLLER_RC|controller[_ ]rc)\s*[=:]\s*(?P<rc>-?\d+)",
    re.IGNORECASE,
)
WORKFLOW_SUCCESS_RE = re.compile(r"\bWORKFLOW SUCCESS\b", re.IGNORECASE)
WORKFLOW_RETURN_CODE_RE = re.compile(r"\bRETURN CODE:\s*(?P<rc>-?\d+)\b", re.IGNORECASE)
FAILURE_PATTERNS = (
    "Error in rule",
    "Error in group",
    "WorkflowError",
    "Exiting because a job execution failed",
)
CANONICAL_ARTIFACT_NAMES = (
    "DAY_final_multiqc.html",
    "multiqc_data.json",
    "dayoa_evidence_manifest.json",
)
RUN_QC_TARGET_PLATFORMS = {
    "produce_illumina_run_qc": "illumina",
    "produce_ont_run_qc": "ont",
    "produce_ultima_run_qc": "ultima",
}
PROGRESS_MARKER_RE = re.compile(
    r"(?:\b\d+(?:\.\d+)?%|\b(?:records?|reads?|loci|contigs?|variants?|steps?)\b|"
    r"\b(?:error|failed|warning|complete|finished|writing|merging|sorting|indexing)\b)",
    re.IGNORECASE,
)
MAX_STREAM_EXCERPT_LINES = 5
MAX_MASTER_EXCERPT_LINES = 20
MAX_TMUX_EXCERPT_LINES = 20
MAX_PROGRESS_MARKERS = 20
MAX_BENCHMARK_EVIDENCE_ROWS = 20
MAX_SACCT_EVIDENCE_ROWS = 50
MAX_RECENT_RULE_LOGS = 20
FAILED_STATES = {
    "FAILED",
    "BOOT_FAIL",
    "CANCELLED",
    "DEADLINE",
    "NODE_FAIL",
    "OUT_OF_MEMORY",
    "TIMEOUT",
}
ACTIVE_STATES = {"RUNNING", "CONFIGURING", "COMPLETING"}
SAFE_WORKFLOW_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9_.-]+")


def _normalized_slurm_state(value: Any) -> str:
    text = str(value or "").split("+", 1)[0].strip()
    return text.split(maxsplit=1)[0].upper() if text else ""


def _run(
    argv: Sequence[str],
    *,
    runner: Runner,
    timeout: int = 20,
) -> subprocess.CompletedProcess[str]:
    return runner(
        list(argv),
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def _tail(path: Path, lines: int) -> list[str]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return handle.readlines()[-lines:]


def _manifest_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise AnalysisStatusError(f"required analysis manifest does not exist: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = [
            {str(key).strip().upper(): str(value or "") for key, value in row.items()}
            for row in csv.DictReader(handle, delimiter="\t")
        ]
    if not rows:
        raise AnalysisStatusError(f"required analysis manifest has no data rows: {path}")
    return rows


def _unique_manifest_values(
    rows: Sequence[dict[str, str]],
    field: str,
    path: Path,
) -> list[str]:
    values = [row.get(field, "") for row in rows]
    if any(not value for value in values):
        raise AnalysisStatusError(f"every {path.name} row must have {field}: {path}")
    if any(value != value.strip() for value in values):
        raise AnalysisStatusError(
            f"{field} values must be byte-exact without surrounding whitespace: {path}"
        )
    if len(set(values)) != len(values):
        raise AnalysisStatusError(f"{field} values must be unique: {path}")
    return values


def _optional_unique_manifest_values(
    rows: Sequence[dict[str, str]],
    field: str,
    path: Path,
) -> list[str]:
    values = [row.get(field, "") for row in rows]
    populated = [value for value in values if value]
    if any(value != value.strip() for value in populated):
        raise AnalysisStatusError(
            f"{field} values must be byte-exact without surrounding whitespace: {path}"
        )
    if len(set(populated)) != len(populated):
        raise AnalysisStatusError(f"nonblank {field} values must be unique: {path}")
    return values


def _dayoa_analysis_unit_uid(row: dict[str, str], path: Path) -> str:
    supplied = row.get("ANALYSIS_UNIT_UID", "")
    if supplied:
        value = supplied
    else:
        parts = [
            row.get(field, "")
            for field in (
                "RUNID",
                "SAMPLEID",
                "EXPERIMENTID",
                "LANEID",
                "BARCODEID",
                "LIBPREP",
                "SEQ_VENDOR",
                "SEQ_PLATFORM",
            )
        ]
        parts = [part for part in parts if part and part.lower() not in {"na", "none"}]
        if not parts:
            raise AnalysisStatusError(
                f"cannot construct ANALYSIS_UNIT_UID from the exact libraries.tsv fields: {path}"
            )
        value = "-".join(parts)
    if SAFE_WORKFLOW_IDENTIFIER_RE.fullmatch(value) is None:
        raise AnalysisStatusError(
            f"unsafe ANALYSIS_UNIT_UID {value!r}; DayOA does not rewrite identifiers: {path}"
        )
    return value


def _analysis_manifests(dayoa_root: Path) -> dict[str, Any]:
    from daylily_ec.manifest_set import (
        MANIFEST_NAMES,
        ManifestSetError,
        load_manifest_set,
        selected_input_details,
    )

    config_root = dayoa_root / "config"
    recognized = (*MANIFEST_NAMES, "units.tsv")
    present = {name for name in recognized if (config_root / name).is_file()}
    if not present:
        return {
            "available": False,
            "input_contract": None,
            "files": [],
            "row_counts": {},
            "note": "this command has no sample-manifest inputs",
        }

    try:
        manifests = load_manifest_set(config_root)
    except ManifestSetError as exc:
        raise AnalysisStatusError(str(exc)) from exc
    details = selected_input_details(manifests)
    return {
        "available": True,
        "input_contract": "six_manifest",
        "files": list(MANIFEST_NAMES),
        "hashes": dict(manifests.hashes),
        "row_counts": {
            name.removesuffix(".tsv"): len(manifests.rows[name]) for name in MANIFEST_NAMES
        },
        "analysis_units": [
            {
                "analysis_unit_uid": row["ANALYSIS_UNIT_UID"],
                **details[row["ANALYSIS_UNIT_UID"]],
            }
            for row in manifests.rows["analysis_units.tsv"]
        ],
        "lineage_validated": True,
    }


def _tail_summary(path: Path | None, lines: int, *, excerpt_lines: int) -> dict[str, Any]:
    raw = _tail(path, lines) if path else []
    normalized = [item.rstrip("\n") for item in raw]
    markers = [item for item in normalized if PROGRESS_MARKER_RE.search(item)]
    return {
        "path": str(path) if path else None,
        "lines_requested": lines,
        "lines_scanned": len(normalized),
        "excerpt": normalized[-excerpt_lines:],
        "progress_markers": markers[-MAX_PROGRESS_MARKERS:],
        "bounded": len(normalized) > excerpt_lines,
    }


def _latest_master_log(dayoa_root: Path) -> Path | None:
    log_dir = dayoa_root / ".snakemake" / "log"
    candidates = [path for path in log_dir.glob("*.snakemake.log") if path.is_file()]
    if not candidates:
        candidates = [path for path in log_dir.glob("*.log") if path.is_file()]
    workflow_candidates = [
        path
        for path in candidates
        if path.read_text(encoding="utf-8", errors="replace").strip()
        != "Unlocking working directory."
    ]
    selected = workflow_candidates or candidates
    return max(selected, key=lambda path: path.stat().st_mtime) if selected else None


def _workflow_evidence(dayoa_root: Path, *, tail_lines: int, full: bool) -> dict[str, Any]:
    master_log = _latest_master_log(dayoa_root)
    evidence: dict[str, Any] = {
        "master_log": str(master_log) if master_log else None,
        "progress": {"completed": None, "total": None, "percent": None},
        "scheduled_rules": [],
        "job_events": {
            "submitted_count": None,
            "completed_count": None,
            "source": str(master_log) if master_log else None,
        },
        "terminal": {
            "return_code": None,
            "return_code_source": None,
            "success_marker": False,
            "success_marker_source": None,
        },
        "failure_count": 0,
        "first_failure_line": None,
        "failure_lines": [],
        "failure_lines_bounded": False,
    }
    if master_log is None:
        return evidence

    text = master_log.read_text(encoding="utf-8", errors="replace")
    progress = list(PROGRESS_RE.finditer(text))
    if progress:
        latest = progress[-1]
        evidence["progress"] = {
            "completed": int(latest.group("done")),
            "total": int(latest.group("total")),
            "percent": int(latest.group("pct")),
        }
    rc_matches = list(WORKFLOW_RETURN_CODE_RE.finditer(text))
    if rc_matches:
        evidence["terminal"]["return_code"] = int(rc_matches[-1].group("rc"))
        evidence["terminal"]["return_code_source"] = str(master_log)
    if WORKFLOW_SUCCESS_RE.search(text):
        evidence["terminal"]["success_marker"] = True
        evidence["terminal"]["success_marker_source"] = str(master_log)
    evidence["scheduled_rules"] = sorted(set(RULE_RE.findall(text)))
    evidence["job_events"] = {
        "submitted_count": len(set(SUBMITTED_JOB_RE.findall(text))),
        "completed_count": len(set(FINISHED_JOB_RE.findall(text))),
        "source": str(master_log),
    }
    failure_lines = [
        line.strip()
        for line in text.splitlines()
        if any(pattern in line for pattern in FAILURE_PATTERNS)
    ]
    evidence["failure_count"] = len(failure_lines)
    evidence["first_failure_line"] = failure_lines[0] if failure_lines else None
    failure_limit = 50 if full else 5
    evidence["failure_lines"] = failure_lines[-failure_limit:]
    evidence["failure_lines_bounded"] = len(failure_lines) > failure_limit
    if full:
        evidence["tail"] = _tail_summary(
            master_log,
            tail_lines,
            excerpt_lines=MAX_MASTER_EXCERPT_LINES,
        )
    return evidence


def _parse_key_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        tokens = shlex.split(text)
    except ValueError:
        tokens = text.split()
    for token in tokens:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        values[key] = value
    return values


def _slurm_jobs(dayoa_root: Path, *, runner: Runner, full: bool, tail_lines: int) -> dict[str, Any]:
    result: dict[str, Any] = {
        "available": False,
        "error": None,
        "state_counts": {},
        "jobs": [],
    }
    if shutil.which("squeue") is None or shutil.which("scontrol") is None:
        result["error"] = "squeue and scontrol are not both available"
        return result

    queue = _run(
        [
            "squeue",
            "-h",
            "-o",
            "%i|%P|%C|%t|%N|%c|%T|%m|%M|%D|%j",
        ],
        runner=runner,
    )
    if queue.returncode != 0:
        result["error"] = queue.stderr.strip() or f"squeue exited {queue.returncode}"
        return result
    result["available"] = True

    fields = (
        "job_id",
        "partition",
        "cpus",
        "short_state",
        "nodes",
        "min_cpus",
        "state",
        "min_memory",
        "elapsed",
        "node_count",
        "name",
    )
    jobs: list[dict[str, Any]] = []
    for line in queue.stdout.splitlines():
        parts = line.split("|", len(fields) - 1)
        if len(parts) != len(fields):
            continue
        job: dict[str, Any] = dict(zip(fields, parts))
        detail_result = _run(["scontrol", "show", "job", "-o", job["job_id"]], runner=runner)
        if detail_result.returncode != 0:
            continue
        details = _parse_key_values(detail_result.stdout.strip())
        workdir = details.get("WorkDir")
        if workdir is None or Path(workdir).resolve() != dayoa_root.resolve():
            continue
        job["workdir"] = workdir
        job["stdout"] = details.get("StdOut")
        job["stderr"] = details.get("StdErr")
        job["comment"] = details.get("Comment")
        job["reason"] = details.get("Reason")
        job["submit_time"] = details.get("SubmitTime")
        job["start_time"] = details.get("StartTime")
        restart_text = str(details.get("Restarts", "") or "")
        job["restart_count"] = int(restart_text) if restart_text.isdigit() else None
        if full:
            for stream in ("stdout", "stderr"):
                raw_path = job.get(stream)
                path = Path(raw_path) if raw_path and "%" not in raw_path else None
                job[f"{stream}_tail"] = _tail_summary(
                    path,
                    tail_lines,
                    excerpt_lines=MAX_STREAM_EXCERPT_LINES,
                )
        jobs.append(job)

    result["jobs"] = jobs
    result["state_counts"] = dict(sorted(Counter(job["state"] for job in jobs).items()))
    return result


def _sacct_jobs(dayoa_root: Path, *, runner: Runner) -> dict[str, Any]:
    result: dict[str, Any] = {
        "available": False,
        "error": None,
        "state_counts": {},
        "normalized_state_counts": {},
        "attempt_count": 0,
        "unique_job_count": 0,
        "jobs": [],
        "jobs_bounded": False,
    }
    if shutil.which("sacct") is None:
        result["error"] = "sacct is not available"
        return result
    start = datetime.fromtimestamp(dayoa_root.stat().st_mtime, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )
    fields = (
        "JobIDRaw",
        "JobName",
        "State",
        "Elapsed",
        "AllocCPUS",
        "NodeList",
        "Partition",
        "WorkDir",
        "ExitCode",
        "Comment",
        "Submit",
        "Start",
        "End",
        "Reason",
    )
    proc = _run(
        [
            "sacct",
            "-X",
            "--starttime",
            start,
            "--noheader",
            "--parsable2",
            "--allusers",
            "--format",
            ",".join(fields),
        ],
        runner=runner,
        timeout=60,
    )
    if proc.returncode != 0:
        result["error"] = proc.stderr.strip() or f"sacct exited {proc.returncode}"
        return result
    result["available"] = True
    jobs: list[dict[str, str]] = []
    for line in proc.stdout.splitlines():
        parts = line.split("|")
        if parts and parts[-1] == "":
            parts.pop()
        if len(parts) != len(fields):
            continue
        job = dict(zip(fields, parts))
        workdir = job["WorkDir"]
        if not workdir or Path(workdir).resolve() != dayoa_root.resolve():
            continue
        jobs.append(job)
    result["attempt_count"] = len(jobs)
    result["state_counts"] = dict(sorted(Counter(job["State"] for job in jobs).items()))
    result["normalized_state_counts"] = dict(
        sorted(Counter(_normalized_slurm_state(job["State"]) for job in jobs).items())
    )
    result["unique_job_count"] = len(
        {job["JobIDRaw"].split(".", 1)[0] for job in jobs if job["JobIDRaw"]}
    )
    result["jobs"] = jobs[-MAX_SACCT_EVIDENCE_ROWS:]
    result["jobs_bounded"] = len(jobs) > MAX_SACCT_EVIDENCE_ROWS
    return result


def _controller_processes(
    analysis_root: Path,
    *,
    runner: Runner,
    full: bool,
    tail_lines: int,
) -> dict[str, Any]:
    result = _run(["ps", "-eo", "pid=,ppid=,etimes=,args="], runner=runner)
    if result.returncode != 0:
        return {
            "available": False,
            "error": result.stderr.strip(),
            "active": False,
            "return_code": None,
            "processes": [],
            "tmux_panes": [],
        }
    root_text = str(analysis_root.resolve())
    processes: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        match = re.match(
            r"(?P<pid>\d+)\s+(?P<ppid>\d+)\s+(?P<elapsed>\d+)\s+(?P<command>.*)",
            stripped,
        )
        if not match:
            continue
        command = match.group("command")
        if "analysis status" in command or "daylily_ec.analysis_status" in command:
            continue
        if not any(token in command for token in ("dy-r", "day_run", "snakemake")):
            continue
        cwd = None
        if root_text not in command:
            cwd_result = _run(["readlink", "-f", f"/proc/{match.group('pid')}/cwd"], runner=runner)
            if cwd_result.returncode == 0:
                cwd = cwd_result.stdout.strip()
            if not cwd or not (cwd == root_text or cwd.startswith(root_text + "/")):
                continue
        processes.append(
            {
                "pid": int(match.group("pid")),
                "ppid": int(match.group("ppid")),
                "elapsed_seconds": int(match.group("elapsed")),
                "command": command,
                "cwd": cwd,
            }
        )

    panes: list[dict[str, Any]] = []
    controller_rc: int | None = None
    controller_rc_source: str | None = None
    if shutil.which("tmux"):
        pane_result = _run(
            [
                "tmux",
                "list-panes",
                "-a",
                "-F",
                "#{session_name}|#{window_index}|#{pane_index}|#{pane_pid}|#{pane_current_path}|#{pane_dead}|#{pane_dead_status}",
            ],
            runner=runner,
        )
        if pane_result.returncode == 0:
            capture_count = tail_lines if full else min(tail_lines, 100)
            for line in pane_result.stdout.splitlines():
                parts = line.split("|", 6)
                if len(parts) != 7:
                    continue
                session, window, pane, pane_pid, current_path, pane_dead, pane_dead_status = parts
                target = f"{session}:{window}.{pane}"
                capture = _run(
                    ["tmux", "capture-pane", "-p", "-t", target, "-S", f"-{capture_count}"],
                    runner=runner,
                )
                capture_text = capture.stdout if capture.returncode == 0 else ""
                if not (
                    current_path == root_text
                    or current_path.startswith(root_text + "/")
                    or root_text in capture_text
                ):
                    continue
                rc_matches = list(CONTROLLER_RC_RE.finditer(capture_text))
                pane_rc = int(rc_matches[-1].group("rc")) if rc_matches else None
                if pane_rc is not None:
                    controller_rc = pane_rc
                    controller_rc_source = f"tmux pane {target}"
                pane_payload: dict[str, Any] = {
                    "session": session,
                    "window": int(window),
                    "pane": int(pane),
                    "pane_pid": int(pane_pid),
                    "current_path": current_path,
                    "dead": pane_dead == "1",
                    "dead_status": (
                        int(pane_dead_status) if pane_dead_status.lstrip("-").isdigit() else None
                    ),
                    "controller_return_code": pane_rc,
                    "observed_commands": [
                        item[item.find(marker) :].strip()
                        for item in capture_text.splitlines()
                        for marker in ("dy-a ", "dy-r ")
                        if marker in item
                    ][-10:],
                }
                if full:
                    capture_lines = capture_text.splitlines()
                    pane_payload["tail"] = {
                        "lines_requested": capture_count,
                        "lines_scanned": len(capture_lines),
                        "excerpt": capture_lines[-MAX_TMUX_EXCERPT_LINES:],
                        "progress_markers": [
                            item for item in capture_lines if PROGRESS_MARKER_RE.search(item)
                        ][-MAX_PROGRESS_MARKERS:],
                        "bounded": len(capture_lines) > MAX_TMUX_EXCERPT_LINES,
                    }
                panes.append(pane_payload)
    receipt_path = (
        Path.home() / "daylily-runs" / analysis_root.name / "status.json"
    )
    receipt: dict[str, Any] = {
        "available": False,
        "path": str(receipt_path),
        "error": None,
    }
    if receipt_path.is_file():
        try:
            raw_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if not isinstance(raw_receipt, dict):
                raise ValueError("status receipt must be a JSON object")
            repo_path = Path(str(raw_receipt.get("repo_path") or "")).resolve()
            session_name = str(raw_receipt.get("session_name") or "").strip()
            exit_code = raw_receipt.get("exit_code")
            completed_at = str(raw_receipt.get("completed_at") or "").strip()
            command = str(raw_receipt.get("command") or "").strip()
            if repo_path != (analysis_root / "daylily-omics-analysis").resolve():
                raise ValueError("status receipt repo_path does not match analysis root")
            if session_name != analysis_root.name:
                raise ValueError("status receipt session_name does not match analysis root")
            if isinstance(exit_code, bool) or not isinstance(exit_code, int):
                raise ValueError("status receipt exit_code must be an integer")
            if not completed_at:
                raise ValueError("status receipt completed_at is required")
            if not command:
                raise ValueError("status receipt command is required")
            receipt = {
                "available": True,
                "path": str(receipt_path),
                "error": None,
                "repo_path": str(repo_path),
                "session_name": session_name,
                "exit_code": exit_code,
                "completed_at": completed_at,
                "started_at": str(raw_receipt.get("started_at") or "").strip() or None,
                "command": command,
            }
            controller_rc = exit_code
            controller_rc_source = str(receipt_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            receipt["error"] = str(exc)
    return {
        "available": True,
        "error": None,
        "active": bool(processes),
        "return_code": controller_rc,
        "return_code_source": controller_rc_source,
        "processes": processes,
        "tmux_panes": panes,
        "status_receipt": receipt,
    }


def _controller_run_receipt(
    analysis_root: Path,
    *,
    run_state_root: Path | None = None,
) -> dict[str, Any]:
    """Read the one run-control status receipt that owns this exact analysis root."""

    from daylily_ec.scripts.daylily_run_omics_analysis_headnode import (
        CommandError,
        parse_controller_target,
    )

    root = analysis_root.resolve()
    state_root = (
        run_state_root.expanduser().resolve()
        if run_state_root is not None
        else (Path.home() / "daylily-runs").resolve()
    )
    result: dict[str, Any] = {
        "available": False,
        "controller_target_path": None,
        "status_path": None,
        "controller_id": None,
        "started_at": None,
        "completed_at": None,
        "return_code": None,
        "error": None,
    }
    if not state_root.is_dir():
        result["error"] = f"run-control state directory does not exist: {state_root}"
        return result

    matches: list[tuple[Path, Any]] = []
    for target_path in sorted(state_root.glob("*/controller_target.json")):
        if (
            target_path.is_symlink()
            or target_path.parent.is_symlink()
            or not target_path.is_file()
        ):
            continue
        try:
            target = parse_controller_target(target_path.read_text(encoding="utf-8"))
        except (OSError, CommandError):
            continue
        if Path(target.analysis_root) == root:
            matches.append((target_path, target))

    if len(matches) > 1:
        paths = ", ".join(str(path) for path, _target in matches)
        raise AnalysisStatusError(
            f"multiple run-control receipts claim analysis root {root}: {paths}"
        )
    if not matches:
        result["error"] = f"no exact run-control receipt claims analysis root {root}"
        return result

    target_path, target = matches[0]
    status_path = target_path.with_name("status.json")
    result.update(
        {
            "controller_target_path": str(target_path),
            "status_path": str(status_path),
            "controller_id": target.controller_id,
        }
    )
    if status_path.is_symlink() or not status_path.is_file():
        result["error"] = f"matched run-control status receipt does not exist: {status_path}"
        return result
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AnalysisStatusError(
            f"matched run-control status receipt is invalid: {status_path}: {exc}"
        ) from exc
    required = {
        "session_name",
        "repo_path",
        "started_at",
        "completed_at",
        "exit_code",
        "command",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise AnalysisStatusError(
            f"matched run-control status receipt fields are invalid: {status_path}"
        )
    if payload["session_name"] != target.controller_id:
        raise AnalysisStatusError(
            f"matched run-control status session differs from controller target: {status_path}"
        )
    if payload["repo_path"] != target.cwd:
        raise AnalysisStatusError(
            f"matched run-control status repo path differs from controller target: {status_path}"
        )
    if not isinstance(payload["command"], str) or not payload["command"].strip():
        raise AnalysisStatusError(
            f"matched run-control status command is invalid: {status_path}"
        )
    for field in ("started_at", "completed_at"):
        value = payload[field]
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise AnalysisStatusError(
                f"matched run-control status {field} is invalid: {status_path}"
            )
    return_code = payload["exit_code"]
    if return_code is not None and (
        isinstance(return_code, bool) or not isinstance(return_code, int)
    ):
        raise AnalysisStatusError(
            f"matched run-control status exit_code is invalid: {status_path}"
        )
    if return_code is not None and payload["completed_at"] is None:
        raise AnalysisStatusError(
            f"matched terminal run-control status has no completed_at: {status_path}"
        )
    result.update(
        {
            "available": True,
            "started_at": payload["started_at"],
            "completed_at": payload["completed_at"],
            "return_code": return_code,
            "error": None,
        }
    )
    return result


def _filesystem(analysis_root: Path, *, runner: Runner) -> dict[str, Any]:
    fsx = Path("/fsx") if str(analysis_root).startswith("/fsx/") else analysis_root
    result = _run(["df", "-Pk", str(fsx)], runner=runner)
    payload: dict[str, Any] = {"path": str(fsx), "available": False, "error": None}
    if result.returncode != 0:
        payload["error"] = result.stderr.strip() or f"df exited {result.returncode}"
        return payload
    lines = result.stdout.strip().splitlines()
    if len(lines) < 2:
        payload["error"] = "df returned no filesystem row"
        return payload
    parts = lines[-1].split()
    if len(parts) < 6:
        payload["error"] = "df returned a malformed filesystem row"
        return payload
    payload.update(
        {
            "available": True,
            "filesystem": parts[0],
            "size_kib": int(parts[1]),
            "used_kib": int(parts[2]),
            "available_kib": int(parts[3]),
            "use_percent": int(parts[4].rstrip("%")),
            "mountpoint": parts[5],
        }
    )
    return payload


def _filesystem_io(*, runner: Runner) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "available": False,
        "health": None,
        "client_stats": [],
        "lfs_df": None,
        "point_sample_only": True,
        "error": None,
    }
    health_path = Path("/proc/fs/lustre/health_check")
    if health_path.is_file():
        payload["health"] = health_path.read_text(encoding="utf-8", errors="replace").strip()
    stats_paths = sorted(Path("/proc/fs/lustre/llite").glob("*/stats"))
    for path in stats_paths:
        selected = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            key = line.split(maxsplit=1)[0] if line.strip() else ""
            if key in {"read_bytes", "write_bytes", "read", "write", "open", "close"}:
                selected.append(line.strip())
        payload["client_stats"].append({"path": str(path), "metrics": selected})
    if shutil.which("lfs"):
        proc = _run(["lfs", "df", "-h", "/fsx"], runner=runner)
        if proc.returncode == 0:
            payload["lfs_df"] = proc.stdout.strip()
        elif proc.stderr.strip():
            payload["error"] = proc.stderr.strip()
    payload["available"] = bool(
        payload["health"] is not None or payload["client_stats"] or payload["lfs_df"]
    )
    if not payload["available"] and not payload["error"]:
        payload["error"] = "Lustre health/client-stat evidence is unavailable"
    return payload


def _canonical_artifacts(
    dayoa_root: Path,
    *,
    controller: dict[str, Any],
) -> dict[str, Any]:
    reports = dayoa_root / "results" / "day"
    matches: dict[str, list[str]] = {}
    for name in CANONICAL_ARTIFACT_NAMES:
        matches[name] = sorted(
            str(path) for path in reports.glob(f"*/reports/**/{name}") if path.is_file()
        )
    generic_complete = all(matches[name] for name in CANONICAL_ARTIFACT_NAMES)
    receipt = controller.get("status_receipt") or {}
    command = str(receipt.get("command") or "")
    platform = next(
        (
            candidate_platform
            for target, candidate_platform in RUN_QC_TARGET_PLATFORMS.items()
            if re.search(rf"(?:^|\s){re.escape(target)}(?:\s|$)", command)
        ),
        None,
    )
    run_qc_bundles: list[dict[str, Any]] = []
    if platform:
        for report in sorted(
            dayoa_root.glob(f"results/runs/**/run_qc/{platform}/multiqc_report.html")
        ):
            run_qc_root = report.parent
            required = (
                run_qc_root / "summary.html",
                run_qc_root / "summary.tsv",
                report,
                run_qc_root / "multiqc_report_data" / "multiqc_data.json",
            )
            run_qc_bundles.append(
                {
                    "root": str(run_qc_root),
                    "all_present": all(path.is_file() for path in required),
                    "files": [str(path) for path in required if path.is_file()],
                    "missing": [str(path) for path in required if not path.is_file()],
                }
            )
    run_qc_complete = bool(run_qc_bundles) and all(
        bundle["all_present"] for bundle in run_qc_bundles
    )
    return {
        "all_present": run_qc_complete if platform else generic_complete,
        "contract": f"run_qc_{platform}" if platform else "dayoa_canonical",
        "files": matches,
        "run_qc_bundles": run_qc_bundles,
    }


def _float(row: dict[str, str], names: Sequence[str]) -> float | None:
    for name in names:
        raw = row.get(name)
        if raw in (None, "", "NA", "nan"):
            continue
        try:
            return float(raw)
        except ValueError:
            continue
    return None


def _benchmarks(dayoa_root: Path) -> dict[str, Any]:
    files = sorted(
        path
        for path in dayoa_root.rglob("*.tsv")
        if path.is_file() and "bench" in path.name.lower()
    )
    rows: list[dict[str, Any]] = []
    total_cost = 0.0
    total_runtime_seconds = 0.0
    for path in files:
        try:
            with path.open(newline="", encoding="utf-8", errors="replace") as handle:
                parsed = list(csv.DictReader(handle, delimiter="\t"))
        except (OSError, csv.Error):
            continue
        if not parsed:
            continue
        latest = parsed[-1]
        runtime = _float(latest, ("s", "runtime_seconds", "elapsed_seconds"))
        cost = _float(
            latest,
            ("task_cost", "estimated_cost_usd", "cost_usd", "total_cost_usd"),
        )
        peak_rss = _float(latest, ("max_rss", "max_rss_mb", "peak_rss_mb"))
        mean_load = _float(latest, ("mean_load", "cpu_percent", "cpu_utilization"))
        total_runtime_seconds += runtime or 0.0
        total_cost += cost or 0.0
        rows.append(
            {
                "path": str(path),
                "sample": latest.get("sample"),
                "rule": latest.get("rule"),
                "runtime_seconds": runtime,
                "cost_usd": cost,
                "peak_rss": peak_rss,
                "mean_load": mean_load,
            }
        )
    return {
        "file_count": len(files),
        "parsed_row_count": len(rows),
        "completed_runtime_seconds_sum": total_runtime_seconds,
        "completed_cost_usd_sum": total_cost,
        "evidence_rows": rows[-MAX_BENCHMARK_EVIDENCE_ROWS:],
        "evidence_rows_bounded": len(rows) > MAX_BENCHMARK_EVIDENCE_ROWS,
    }


def _recent_rule_logs(dayoa_root: Path, *, tail_lines: int) -> dict[str, Any]:
    candidates = sorted(
        (
            path
            for path in dayoa_root.rglob("*.log")
            if path.is_file() and "logs" in path.parts and ".snakemake" not in path.parts
        ),
        key=lambda path: path.stat().st_mtime,
    )
    selected = candidates[-MAX_RECENT_RULE_LOGS:]
    return {
        "total_log_count": len(candidates),
        "logs_bounded": len(candidates) > MAX_RECENT_RULE_LOGS,
        "recent": [
            {
                "modified_at": datetime.fromtimestamp(
                    path.stat().st_mtime, tz=timezone.utc
                ).isoformat(),
                **_tail_summary(
                    path,
                    tail_lines,
                    excerpt_lines=MAX_STREAM_EXCERPT_LINES,
                ),
            }
            for path in selected
        ],
    }


def _node_telemetry(jobs: list[dict[str, Any]], *, runner: Runner) -> list[dict[str, Any]]:
    nodes = sorted(
        {
            job["nodes"]
            for job in jobs
            if job.get("state") == "RUNNING" and job.get("nodes") not in (None, "", "(null)", "n/a")
        }
    )
    snapshots: list[dict[str, Any]] = []
    fields = (
        "cpu.user,cpu.system,load.min1,mem.percent,swap.percent,"
        "fs.free,fs.percent,diskio.read_bytes,diskio.write_bytes,"
        "network.rx,network.tx,processcount.total"
    )
    for node in nodes:
        result = _run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=5",
                node,
                "timeout",
                "12",
                "glances",
                "--stdout",
                fields,
                "--time",
                "2",
                "--quiet",
            ],
            runner=runner,
            timeout=18,
        )
        snapshots.append(
            {
                "node": node,
                "available": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "point_sample_only": True,
            }
        )
    return snapshots


def _evidence_value(
    value: Any,
    *,
    source: str | None,
    note: str | None = None,
) -> dict[str, Any]:
    payload = {
        "value": value,
        "available": value is not None,
        "source": source,
    }
    if note:
        payload["note"] = note
    return payload


def _job_counts(
    workflow: dict[str, Any],
    slurm: dict[str, Any],
    accounting: dict[str, Any],
) -> dict[str, Any]:
    progress = workflow["progress"]
    total = progress["total"]
    completed = progress["completed"]
    events = workflow.get("job_events", {})
    master_log = workflow.get("master_log")
    slurm_source = "exact-workdir squeue/scontrol" if slurm["available"] else None
    accounting_source = "exact-workdir sacct -X" if accounting["available"] else None
    normalized = accounting.get("normalized_state_counts", {})
    running = None
    pending = None
    dependency_blocked = None
    if slurm["available"]:
        running = sum(
            1 for job in slurm["jobs"] if str(job.get("state", "")).upper() in ACTIVE_STATES
        )
        pending = sum(1 for job in slurm["jobs"] if str(job.get("state", "")).upper() == "PENDING")
        dependency_blocked = sum(
            1
            for job in slurm["jobs"]
            if str(job.get("state", "")).upper() == "PENDING"
            and str(job.get("reason", "")).lower().startswith("dependency")
        )
    failed = None
    if accounting["available"]:
        failed = sum(normalized.get(state, 0) for state in FAILED_STATES)
    still_to_run = (
        max(0, total - completed) if total is not None and completed is not None else None
    )
    return {
        "submitted": _evidence_value(
            events.get("submitted_count"),
            source=events.get("source"),
            note="unique Snakemake job IDs observed in the current master log",
        ),
        "completed": _evidence_value(
            completed,
            source=master_log,
            note="latest Snakemake progress denominator",
        ),
        "failed": _evidence_value(
            failed,
            source=accounting_source,
            note="terminal failed Slurm allocations; not inferred from an empty queue",
        ),
        "running": _evidence_value(running, source=slurm_source),
        "pending": _evidence_value(pending, source=slurm_source),
        "still_to_run": _evidence_value(
            still_to_run,
            source=master_log,
            note="DAG total minus completed; includes currently running or pending work",
        ),
        "dependency_blocked": _evidence_value(
            dependency_blocked,
            source=slurm_source,
            note="pending exact-root jobs whose scheduler reason begins with Dependency",
        ),
    }


def _terminal_evidence(
    *,
    workflow: dict[str, Any],
    controller: dict[str, Any],
    slurm: dict[str, Any],
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    progress = workflow["progress"]
    progress_complete = (
        progress["completed"] is not None and progress["completed"] == progress["total"]
    )
    workflow_terminal = workflow.get("terminal", {})
    workflow_return_code = workflow_terminal.get("return_code")
    effective_return_code = (
        controller["return_code"] if controller["return_code"] is not None else workflow_return_code
    )
    terminal_success = (
        bool(workflow_terminal.get("success_marker")) and effective_return_code == 0
    )
    requirements = {
        "controller_exit_zero": effective_return_code == 0,
        "controller_inactive": controller["available"] and not controller["active"],
        "scheduler_idle": slurm["available"] and not slurm["jobs"],
        "workflow_progress_complete": progress_complete,
        "workflow_terminal_success": terminal_success,
        "strict_artifacts_present": artifacts["all_present"],
    }
    workflow_complete = progress_complete or terminal_success
    success_requirements = {
        "controller_exit_zero": requirements["controller_exit_zero"],
        "controller_inactive": requirements["controller_inactive"],
        "scheduler_idle": requirements["scheduler_idle"],
        "workflow_complete": workflow_complete,
        "strict_artifacts_present": requirements["strict_artifacts_present"],
    }
    return {
        "return_code": effective_return_code,
        "return_code_source": controller.get("return_code_source")
        or workflow_terminal.get("return_code_source"),
        "requirements": requirements,
        "success_verified": all(success_requirements.values()),
        "artifact_files": artifacts["files"],
    }


def collect_analysis_status(
    analysis_root: str | Path,
    *,
    mode: str,
    tail_lines: int = 1000,
    runner: Runner = subprocess.run,
    run_state_root: str | Path | None = None,
) -> dict[str, Any]:
    """Collect slim or full read-only status for one exact analysis root."""

    if mode not in {"slim", "full"}:
        raise AnalysisStatusError("mode must be exactly 'slim' or 'full'")
    if tail_lines < 1:
        raise AnalysisStatusError("tail_lines must be at least 1")
    root = Path(analysis_root).expanduser().resolve()
    if not root.is_dir():
        raise AnalysisStatusError(f"analysis root does not exist: {root}")
    dayoa_root = root / "daylily-omics-analysis"
    if not dayoa_root.is_dir():
        raise AnalysisStatusError(f"DayOA checkout does not exist: {dayoa_root}")

    from daylily_ec.analysis_lock import write_visit

    visit = write_visit(
        root,
        mode="monitor",
        intent=f"dyec analysis status {mode}",
        note="read-only exact-root status collection",
    )
    full = mode == "full"
    workflow = _workflow_evidence(dayoa_root, tail_lines=tail_lines, full=full)
    slurm = _slurm_jobs(dayoa_root, runner=runner, full=full, tail_lines=tail_lines)
    accounting = _sacct_jobs(dayoa_root, runner=runner)
    controller = _controller_processes(
        root,
        runner=runner,
        full=full,
        tail_lines=tail_lines,
    )
    run_receipt = _controller_run_receipt(
        root,
        run_state_root=Path(run_state_root) if run_state_root is not None else None,
    )
    receipt_return_code = run_receipt["return_code"]
    if (
        receipt_return_code is not None
        and controller["return_code"] is not None
        and receipt_return_code != controller["return_code"]
    ):
        raise AnalysisStatusError(
            "matching tmux controller marker disagrees with the exact run-control receipt"
        )
    if receipt_return_code is not None:
        controller["return_code"] = receipt_return_code
        controller["return_code_source"] = run_receipt["status_path"]
    controller["run_receipt"] = run_receipt
    manifests = _analysis_manifests(dayoa_root)
    artifacts = _canonical_artifacts(dayoa_root, controller=controller)
    progress = workflow["progress"]
    terminal_evidence = _terminal_evidence(
        workflow=workflow,
        controller=controller,
        slurm=slurm,
        artifacts=artifacts,
    )
    effective_return_code = terminal_evidence["return_code"]
    workflow_terminal_complete = (
        terminal_evidence["requirements"]["workflow_progress_complete"]
        or terminal_evidence["requirements"]["workflow_terminal_success"]
    )
    complete = (
        workflow_terminal_complete and artifacts["all_present"]
    )
    active = controller["active"] or bool(slurm["jobs"])
    if effective_return_code not in (None, 0) and not active:
        state = "FAILED"
    elif terminal_evidence["success_verified"]:
        state = "SUCCESS"
    elif complete and effective_return_code == 0 and not active and not slurm["available"]:
        state = "COMPLETE_ARTIFACTS_RC_ZERO_SCHEDULER_UNKNOWN"
    elif complete and not active:
        state = "COMPLETE_ARTIFACTS_RC_UNKNOWN"
    elif active:
        state = "RUNNING"
    elif workflow["failure_count"]:
        state = "FAILED_OR_INCOMPLETE"
    else:
        state = "INCOMPLETE_OR_UNKNOWN"

    payload: dict[str, Any] = {
        "schema_version": "dyec.analysis_status.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "analysis_root": str(root),
        "dayoa_root": str(dayoa_root),
        "state": state,
        "terminal_evidence": terminal_evidence,
        "job_counts": _job_counts(workflow, slurm, accounting),
        "visit": visit,
        "workflow": workflow,
        "controller": controller,
        "slurm": slurm,
        "accounting": accounting,
        "manifests": manifests,
        "filesystem": _filesystem(root, runner=runner),
        "canonical_artifacts": artifacts,
        "warnings": [],
    }
    if not slurm["available"]:
        payload["warnings"].append(f"Slurm evidence unavailable: {slurm['error']}")
    if not accounting["available"]:
        payload["warnings"].append(f"Slurm accounting evidence unavailable: {accounting['error']}")
    if workflow["progress"]["total"] is None and not workflow["terminal"]["success_marker"]:
        payload["warnings"].append(
            "No Snakemake progress line was found in the current master log."
        )
    if workflow["progress"]["total"] is None and workflow["terminal"]["success_marker"]:
        payload["warnings"].append(
            "No Snakemake progress line was found in the current master log; terminal workflow success evidence was used."
        )
    if complete and effective_return_code is None:
        payload["warnings"].append(
            "Canonical outputs and terminal workflow evidence are complete, but rc 0 was not found; success is unverified."
        )
    if complete and effective_return_code == 0 and not slurm["available"]:
        payload["warnings"].append(
            "Canonical outputs and controller rc 0 are present, but scheduler-idle state is unavailable; success is unverified."
        )
    if full:
        payload["benchmarks"] = _benchmarks(dayoa_root)
        payload["recent_rule_logs"] = _recent_rule_logs(dayoa_root, tail_lines=tail_lines)
        payload["filesystem_io"] = _filesystem_io(runner=runner)
        payload["node_telemetry"] = _node_telemetry(slurm["jobs"], runner=runner)
        completed = progress["completed"]
        total = progress["total"]
        controller_elapsed = max(
            (item["elapsed_seconds"] for item in controller["processes"]),
            default=None,
        )
        remaining_seconds = None
        eta = None
        if (
            controller_elapsed is not None
            and completed is not None
            and total is not None
            and 0 < completed < total
        ):
            remaining_seconds = controller_elapsed * (total - completed) / completed
            eta = datetime.fromtimestamp(
                datetime.now(timezone.utc).timestamp() + remaining_seconds,
                tz=timezone.utc,
            ).isoformat()
        payload["remaining_work"] = {
            "active_job_names": sorted({job["name"] for job in slurm["jobs"]}),
            "queued_rule_count": (
                progress["total"] - progress["completed"]
                if progress["total"] is not None and progress["completed"] is not None
                else None
            ),
            "estimated_remaining_seconds": remaining_seconds,
            "estimated_completion": eta,
            "estimate_confidence": "low" if eta else None,
            "estimate_method": (
                "linear controller-elapsed/workflow-step extrapolation" if eta else None
            ),
            "estimate_note": (
                "This is not a critical-path model and may be distorted by heterogeneous rule runtimes."
                if eta
                else "No completion time is asserted without controller elapsed time and measurable progress."
            ),
        }
    return payload


def render_analysis_status(payload: dict[str, Any]) -> str:
    """Render a concise human report; JSON retains all full-mode evidence."""

    progress = payload["workflow"]["progress"]
    if progress["total"] is None:
        progress_text = "unavailable"
    else:
        progress_text = f"{progress['completed']}/{progress['total']} ({progress['percent']}%)"
    fs = payload["filesystem"]
    fs_text = (
        f"{fs['use_percent']}% used; {fs['available_kib'] / 1024 / 1024:.1f} GiB available"
        if fs["available"]
        else f"unavailable ({fs['error']})"
    )
    jobs = payload["slurm"]
    job_text = (
        ", ".join(f"{state}={count}" for state, count in jobs["state_counts"].items()) or "none"
    )
    lines = [
        f"Analysis: {payload['analysis_root']}",
        f"State: {payload['state']}",
        f"Progress: {progress_text}",
        f"Controller: {'active' if payload['controller']['active'] else 'inactive'}",
        f"Scoped Slurm jobs: {job_text}",
        "Scoped sacct attempts: "
        + (
            str(payload["accounting"]["attempt_count"])
            if payload["accounting"]["available"]
            else "unavailable"
        ),
        f"FSx/filesystem: {fs_text}",
        f"Final artifacts complete: {'yes' if payload['canonical_artifacts']['all_present'] else 'no'}",
        f"Failure markers in current master log: {payload['workflow']['failure_count']}",
    ]
    if payload["mode"] == "full":
        benchmark = payload["benchmarks"]
        lines.extend(
            [
                f"Parsed benchmark rows: {benchmark['parsed_row_count']}/{benchmark['file_count']}",
                f"Completed benchmark cost sum: ${benchmark['completed_cost_usd_sum']:.6f}",
                f"Completed benchmark runtime sum: {benchmark['completed_runtime_seconds_sum']:.1f}s",
                f"Allocated-node telemetry samples: {len(payload['node_telemetry'])}",
                "Active jobs:",
            ]
        )
        for job in jobs["jobs"]:
            lines.append(
                f"  {job['job_id']} {job['state']} {job['partition']} cpus={job['cpus']} "
                f"elapsed={job['elapsed']} name={job['name']}"
            )
            for stream in ("stdout", "stderr"):
                tail = job.get(f"{stream}_tail", {})
                if tail.get("lines_scanned"):
                    lines.append(
                        f"  {stream}: scanned {tail['lines_scanned']}/{tail['lines_requested']} "
                        f"requested tail lines; {len(tail['progress_markers'])} markers"
                    )
                    lines.extend(f"    {item}" for item in tail["excerpt"])
        lines.append(payload["remaining_work"]["estimate_note"])
        if payload["remaining_work"]["estimated_completion"]:
            lines.append(
                "Low-confidence estimated completion: "
                + payload["remaining_work"]["estimated_completion"]
            )
    lines.extend(f"WARNING: {warning}" for warning in payload["warnings"])
    return "\n".join(lines)
