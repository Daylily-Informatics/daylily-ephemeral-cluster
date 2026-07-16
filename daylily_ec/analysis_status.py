"""Read-only, exact-root DayOA workflow status collection."""

from __future__ import annotations

import csv
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
CONTROLLER_RC_RE = re.compile(
    r"(?:__DAYOA_CONTROLLER_RC__|DAYOA_CONTROLLER_RC|controller[_ ]rc)\s*[=:]\s*(?P<rc>-?\d+)",
    re.IGNORECASE,
)
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
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def _workflow_evidence(dayoa_root: Path, *, tail_lines: int, full: bool) -> dict[str, Any]:
    master_log = _latest_master_log(dayoa_root)
    evidence: dict[str, Any] = {
        "master_log": str(master_log) if master_log else None,
        "progress": {"completed": None, "total": None, "percent": None},
        "scheduled_rules": [],
        "failure_count": 0,
        "failure_lines": [],
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
    evidence["scheduled_rules"] = sorted(set(RULE_RE.findall(text)))
    failure_lines = [
        line.strip()
        for line in text.splitlines()
        if any(pattern in line for pattern in FAILURE_PATTERNS)
    ]
    evidence["failure_count"] = len(failure_lines)
    evidence["failure_lines"] = failure_lines[-50:] if full else failure_lines[-5:]
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
        job = dict(zip(fields, parts))
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
        "attempt_count": 0,
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
                pane_payload: dict[str, Any] = {
                    "session": session,
                    "window": int(window),
                    "pane": int(pane),
                    "pane_pid": int(pane_pid),
                    "current_path": current_path,
                    "dead": pane_dead == "1",
                    "dead_status": int(pane_dead_status) if pane_dead_status.lstrip("-").isdigit() else None,
                    "controller_return_code": pane_rc,
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
    return {
        "available": True,
        "error": None,
        "active": bool(processes),
        "return_code": controller_rc,
        "processes": processes,
        "tmux_panes": panes,
    }


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


def _canonical_artifacts(dayoa_root: Path) -> dict[str, Any]:
    reports = dayoa_root / "results" / "day"
    matches: dict[str, list[str]] = {}
    for name in CANONICAL_ARTIFACT_NAMES:
        matches[name] = sorted(str(path) for path in reports.glob(f"*/reports/**/{name}") if path.is_file())
    return {
        "all_present": all(matches[name] for name in CANONICAL_ARTIFACT_NAMES),
        "files": matches,
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
        cost = _float(latest, ("estimated_cost_usd", "cost_usd", "total_cost_usd"))
        peak_rss = _float(latest, ("max_rss", "max_rss_mb", "peak_rss_mb"))
        mean_load = _float(latest, ("mean_load", "cpu_percent", "cpu_utilization"))
        total_runtime_seconds += runtime or 0.0
        total_cost += cost or 0.0
        rows.append(
            {
                "path": str(path),
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
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", node, "timeout", "12", "glances", "--stdout", fields, "--time", "2", "--quiet"],
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


def collect_analysis_status(
    analysis_root: str | Path,
    *,
    mode: str,
    tail_lines: int = 1000,
    runner: Runner = subprocess.run,
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
    artifacts = _canonical_artifacts(dayoa_root)
    progress = workflow["progress"]
    complete = (
        progress["completed"] is not None
        and progress["completed"] == progress["total"]
        and artifacts["all_present"]
    )
    active = controller["active"] or bool(slurm["jobs"])
    if controller["return_code"] not in (None, 0) and not active:
        state = "FAILED"
    elif complete and controller["return_code"] == 0 and not active:
        state = "SUCCESS"
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
        "visit": visit,
        "workflow": workflow,
        "controller": controller,
        "slurm": slurm,
        "accounting": accounting,
        "filesystem": _filesystem(root, runner=runner),
        "canonical_artifacts": artifacts,
        "warnings": [],
    }
    if not slurm["available"]:
        payload["warnings"].append(f"Slurm evidence unavailable: {slurm['error']}")
    if not accounting["available"]:
        payload["warnings"].append(f"Slurm accounting evidence unavailable: {accounting['error']}")
    if workflow["progress"]["total"] is None:
        payload["warnings"].append("No Snakemake progress line was found in the current master log.")
    if complete and controller["return_code"] is None:
        payload["warnings"].append(
            "Canonical outputs and progress are complete, but controller rc 0 was not found; success is unverified."
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
    job_text = ", ".join(f"{state}={count}" for state, count in jobs["state_counts"].items()) or "none"
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
