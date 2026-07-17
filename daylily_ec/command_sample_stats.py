"""Strict, exact-root progress reporting for supported DayOA command families."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

import yaml

from daylily_ec import __version__
from daylily_ec.analysis_status import collect_analysis_status


class CommandSampleStatsError(RuntimeError):
    """Raised when a sample-stats request cannot satisfy its strict contract."""


Runner = Callable[..., subprocess.CompletedProcess[str]]
PIPELINES = {"hiomrs-kitchensink": "hybrid_ilmn_ont_hiomrs_kitchensink"}
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
SECRET_ENV_PARTS = ("TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "ACCESS_KEY", "PRIVATE_KEY")
ERROR_MARKER_RE = re.compile(
    r"(?:^|[\s\[])ERROR(?:[\s:\]]|$)|\bError in (?:rule|group)\b|"
    r"\b(?:Traceback|Exception|FAILED|Failed)\b|execution failed"
)
ETA_MARKER_RE = re.compile(r"\beta\b|estimated completion", re.IGNORECASE)
SAFE_WORKFLOW_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9_.-]+")


def _utc_timestamp(value: float) -> str:
    return (
        datetime.fromtimestamp(value, tz=timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _duration(seconds: float | int | None) -> str | None:
    if seconds is None:
        return None
    value = max(0, int(seconds))
    hours, remainder = divmod(value, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise CommandSampleStatsError(f"required TSV does not exist: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows:
        raise CommandSampleStatsError(f"required TSV has no data rows: {path}")
    return [
        {str(key).strip().upper(): str(value or "") for key, value in row.items()} for row in rows
    ]


def _require_unique_manifest_field(
    rows: Sequence[dict[str, str]],
    field: str,
    path: Path,
) -> list[str]:
    values = [row.get(field, "") for row in rows]
    if any(not value for value in values):
        raise CommandSampleStatsError(f"every {path.name} row must have {field}: {path}")
    if any(value != value.strip() for value in values):
        raise CommandSampleStatsError(
            f"{field} values must be byte-exact without surrounding whitespace: {path}"
        )
    if len(set(values)) != len(values):
        raise CommandSampleStatsError(f"{field} values must be unique: {path}")
    return values


def _optional_unique_manifest_field(
    rows: Sequence[dict[str, str]],
    field: str,
    path: Path,
) -> list[str]:
    values = [row.get(field, "") for row in rows]
    populated = [value for value in values if value]
    if any(value != value.strip() for value in populated):
        raise CommandSampleStatsError(
            f"{field} values must be byte-exact without surrounding whitespace: {path}"
        )
    if len(set(populated)) != len(populated):
        raise CommandSampleStatsError(f"nonblank {field} values must be unique: {path}")
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
            raise CommandSampleStatsError(
                f"cannot construct ANALYSIS_UNIT_UID from the exact libraries.tsv fields: {path}"
            )
        value = "-".join(parts)
    if SAFE_WORKFLOW_IDENTIFIER_RE.fullmatch(value) is None:
        raise CommandSampleStatsError(
            f"unsafe ANALYSIS_UNIT_UID {value!r}; DayOA does not rewrite identifiers: {path}"
        )
    return value


def _load_analysis_manifests(
    dayoa_root: Path,
    *,
    input_contract: str,
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    dict[str, dict[str, str]],
    str,
]:
    config_root = dayoa_root / "config"
    specimens_path = config_root / "specimens.tsv"
    samples_path = config_root / "samples.tsv"
    libraries_path = config_root / "libraries.tsv"
    units_path = config_root / "units.tsv"

    if input_contract == "sample_manifest_v12":
        if units_path.exists():
            raise CommandSampleStatsError(
                "DayOA 12 command sample-stats rejects config/units.tsv; migrate the analysis "
                "with `dayoa migrate-manifests` and retain only specimens.tsv, samples.tsv, "
                "and libraries.tsv"
            )
        specimens = _read_tsv(specimens_path)
        samples = _read_tsv(samples_path)
        libraries = _read_tsv(libraries_path)
        specimen_ids = _require_unique_manifest_field(specimens, "SPECIMEN_ID", specimens_path)
        _optional_unique_manifest_field(specimens, "SPECIMEN_EUID", specimens_path)
        sample_ids = _require_unique_manifest_field(samples, "SAMPLEID", samples_path)
        _optional_unique_manifest_field(samples, "SAMPLE_EUID", samples_path)
        for row in libraries:
            row["ANALYSIS_UNIT_UID"] = _dayoa_analysis_unit_uid(row, libraries_path)
        _require_unique_manifest_field(libraries, "ANALYSIS_UNIT_UID", libraries_path)
        _optional_unique_manifest_field(libraries, "LIBRARY_EUID", libraries_path)

        specimen_by_id = dict(zip(specimen_ids, specimens, strict=True))
        sample_by_id = dict(zip(sample_ids, samples, strict=True))
        missing_specimens = sorted(
            {
                row.get("SPECIMEN_ID", "")
                for row in samples
                if row.get("SPECIMEN_ID", "") not in specimen_by_id
            }
        )
        if missing_specimens:
            raise CommandSampleStatsError(
                "samples.tsv SPECIMEN_ID values are absent from specimens.tsv: "
                + ", ".join(missing_specimens)
            )
        missing_samples = sorted(
            {
                row.get("SAMPLEID", "")
                for row in libraries
                if row.get("SAMPLEID", "") not in sample_by_id
            }
        )
        if missing_samples:
            raise CommandSampleStatsError(
                "libraries.tsv SAMPLEID values are absent from samples.tsv: "
                + ", ".join(missing_samples)
            )
        return libraries, samples, specimen_by_id, "libraries.tsv"

    if input_contract != "sample_manifest":
        raise CommandSampleStatsError(
            f"sample-stats does not support input contract {input_contract!r}"
        )
    if specimens_path.exists() or libraries_path.exists():
        raise CommandSampleStatsError(
            "legacy sample_manifest analysis must not mix specimens.tsv or libraries.tsv with "
            "samples.tsv and units.tsv"
        )
    samples = _read_tsv(samples_path)
    units = _read_tsv(units_path)
    sample_ids = _require_unique_manifest_field(samples, "SAMPLEID", samples_path)
    _require_unique_manifest_field(units, "ANALYSIS_UNIT_UID", units_path)
    sample_by_id = dict(zip(sample_ids, samples, strict=True))
    missing_samples = sorted(
        {row.get("SAMPLEID", "") for row in units if row.get("SAMPLEID", "") not in sample_by_id}
    )
    if missing_samples:
        raise CommandSampleStatsError(
            "units.tsv SAMPLEID values are absent from samples.tsv: " + ", ".join(missing_samples)
        )
    return units, samples, {}, "units.tsv"


def _scalar(value: Any, *, source: str | None, state: str | None = None) -> dict[str, Any]:
    return {
        "value": value,
        "state": state or ("available" if value not in (None, "") else "not_available"),
        "source": source,
    }


def _first_explicit(row: dict[str, Any], names: Sequence[str], *, source: str) -> dict[str, Any]:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return _scalar(value, source=f"{source}:{name}")
    return _scalar(None, source=None)


def _float_value(row: dict[str, str], names: Sequence[str]) -> float | None:
    for name in names:
        raw = row.get(name)
        if raw in (None, "", "NA", "nan", "."):
            continue
        try:
            return float(raw)
        except ValueError:
            continue
    return None


def _single_row_tsv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if len(rows) != 1:
        return {}
    return {str(key).strip(): str(value or "").strip() for key, value in rows[0].items()}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _nested_value(payload: Any, names: set[str]) -> Any:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).lower() in names and value not in (None, ""):
                return value
        for value in payload.values():
            found = _nested_value(value, names)
            if found not in (None, ""):
                return found
    if isinstance(payload, list):
        for value in payload:
            found = _nested_value(value, names)
            if found not in (None, ""):
                return found
    return None


def _git_identity(path: Path, *, runner: Runner) -> dict[str, Any]:
    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return runner(
            ["git", "-C", str(path), *args], text=True, capture_output=True, check=False, timeout=20
        )

    commit = run("rev-parse", "HEAD")
    exact = run("describe", "--tags", "--exact-match")
    dirty = run("status", "--short")
    if commit.returncode != 0:
        raise CommandSampleStatsError(f"cannot resolve DayOA git identity at {path}")
    return {
        "commit": commit.stdout.strip(),
        "exact_tag": exact.stdout.strip() if exact.returncode == 0 else None,
        "dirty": bool(dirty.stdout.strip()),
        "dirty_paths": dirty.stdout.splitlines(),
    }


def _segdup_genes(dayoa_root: Path) -> list[str]:
    path = dayoa_root / "config" / "day_profiles" / "slurm" / "templates" / "rule_config.yaml"
    if not path.is_file():
        raise CommandSampleStatsError(f"active HIOMRS rule configuration is missing: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw = payload.get("hiomrs", {}).get("segdup_genes") if isinstance(payload, dict) else None
    genes = [item.strip() for item in str(raw or "").split(",") if item.strip()]
    if not genes or len(set(genes)) != len(genes):
        raise CommandSampleStatsError(f"hiomrs.segdup_genes is missing or invalid in {path}")
    return genes


def _job_matches(unit: str, rule_tokens: Sequence[str], text: str) -> bool:
    lowered = text.lower()
    return unit.lower() in lowered and any(token.lower() in lowered for token in rule_tokens)


def _normalized_slurm_state(value: Any) -> str:
    text = str(value or "").split("+", 1)[0].strip()
    return text.split(maxsplit=1)[0].upper() if text else ""


def _slurm_duration_seconds(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text or text.upper() in {"UNKNOWN", "UNLIMITED", "N/A"}:
        return None
    match = re.fullmatch(
        r"(?:(?P<days>\d+)-)?(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+)", text
    )
    if not match:
        return None
    return (
        int(match.group("days") or 0) * 86400
        + int(match.group("hours")) * 3600
        + int(match.group("minutes")) * 60
        + int(match.group("seconds"))
    )


def _first_log_marker(paths: Sequence[str], pattern: re.Pattern[str]) -> dict[str, Any]:
    for raw_path in paths:
        if not raw_path or "%" in raw_path:
            continue
        path = Path(raw_path)
        if not path.is_file():
            continue
        try:
            with path.open(encoding="utf-8", errors="replace") as handle:
                for line_number, line in enumerate(handle, start=1):
                    text = line.strip()
                    if pattern.search(text):
                        return {
                            "value": text,
                            "source": f"{path}:{line_number}",
                            "state": "observed",
                        }
        except OSError:
            continue
    return _scalar(None, source=None)


def _last_tail_marker(
    active_jobs: Sequence[dict[str, Any]], pattern: re.Pattern[str]
) -> dict[str, Any]:
    matches: list[dict[str, str]] = []
    for job in active_jobs:
        for stream in ("stdout", "stderr"):
            tail = job.get(f"{stream}_tail", {})
            for line in tail.get("progress_markers", []):
                if pattern.search(str(line)):
                    matches.append(
                        {
                            "value": str(line),
                            "source": str(tail.get("path") or job.get(stream) or ""),
                            "state": "observed",
                        }
                    )
    return matches[-1] if matches else _scalar(None, source=None)


def _milestone_execution_evidence(
    unit: str,
    status: dict[str, Any],
    rule_tokens: Sequence[str],
) -> dict[str, Any]:
    active_jobs = [
        job
        for job in status.get("slurm", {}).get("jobs", [])
        if _job_matches(
            unit,
            rule_tokens,
            " ".join(str(job.get(key, "")) for key in ("name", "stdout", "stderr")),
        )
    ]
    accounting_jobs = [
        job
        for job in status.get("accounting", {}).get("jobs", [])
        if _job_matches(unit, rule_tokens, str(job.get("JobName", "")))
    ]
    current = active_jobs[0] if active_jobs else None
    latest = accounting_jobs[-1] if accounting_jobs else None
    job_name = (
        str(current.get("name")) if current else str(latest.get("JobName")) if latest else None
    )
    scheduled_rules = status.get("workflow", {}).get("scheduled_rules", [])
    matched_rules = [
        rule for rule in scheduled_rules if job_name and rule.lower() in job_name.lower()
    ]
    rule = max(matched_rules, key=len) if matched_rules else None
    log_paths = sorted(
        {
            str(job.get(stream))
            for job in active_jobs
            for stream in ("stdout", "stderr")
            if job.get(stream)
        }
        | {
            str(item.get("path"))
            for item in status.get("recent_rule_logs", {}).get("recent", [])
            if item.get("path") and _job_matches(unit, rule_tokens, str(item.get("path")))
        }
    )
    elapsed = current.get("elapsed") if current else latest.get("Elapsed") if latest else None
    retry_values = [
        int(job["restart_count"]) for job in active_jobs if job.get("restart_count") is not None
    ]
    retry_count = sum(retry_values) if retry_values else None
    retry_source = "matching scontrol Restarts" if retry_values else None
    terminal_failure = None
    if latest and _normalized_slurm_state(latest.get("State")) in FAILED_STATES:
        terminal_failure = {
            "state": latest.get("State"),
            "exit_code": latest.get("ExitCode"),
            "reason": latest.get("Reason"),
            "source": "exact-workdir sacct -X",
        }
    first_causal_error = _first_log_marker(log_paths, ERROR_MARKER_RE)
    if first_causal_error["value"] is None:
        for line in status.get("workflow", {}).get("failure_lines", []):
            if _job_matches(unit, rule_tokens, str(line)):
                first_causal_error = {
                    "value": str(line),
                    "source": status.get("workflow", {}).get("master_log"),
                    "state": "observed",
                }
                break
    matched_job_evidence = [
        {
            "job_id": job.get("job_id"),
            "job_name": job.get("name"),
            "state": job.get("state"),
            "reason": job.get("reason"),
            "elapsed": job.get("elapsed"),
            "restart_count": job.get("restart_count"),
            "stdout": job.get("stdout"),
            "stderr": job.get("stderr"),
            "source": "exact-workdir squeue/scontrol",
        }
        for job in active_jobs
    ] + [
        {
            "job_id": job.get("JobIDRaw"),
            "job_name": job.get("JobName"),
            "state": job.get("State"),
            "reason": job.get("Reason"),
            "elapsed": job.get("Elapsed"),
            "exit_code": job.get("ExitCode"),
            "submit_time": job.get("Submit"),
            "start_time": job.get("Start"),
            "end_time": job.get("End"),
            "source": "exact-workdir sacct -X",
        }
        for job in accounting_jobs
    ]
    selected_job_id = (
        current.get("job_id") if current else latest.get("JobIDRaw") if latest else None
    )
    return {
        "job_id": _scalar(
            selected_job_id,
            source=(
                "exact-workdir squeue/scontrol"
                if current
                else "exact-workdir sacct -X"
                if latest
                else None
            ),
        ),
        "job_name": _scalar(
            job_name,
            source=(
                "exact-workdir squeue/scontrol"
                if current
                else "exact-workdir sacct -X"
                if latest
                else None
            ),
        ),
        "rule": _scalar(rule, source=status.get("workflow", {}).get("master_log")),
        "scheduler_state": _scalar(
            current.get("state") if current else latest.get("State") if latest else None,
            source=(
                "exact-workdir squeue/scontrol"
                if current
                else "exact-workdir sacct -X"
                if latest
                else None
            ),
        ),
        "scheduler_reason": _scalar(
            current.get("reason") if current else latest.get("Reason") if latest else None,
            source=(
                "exact-workdir squeue/scontrol"
                if current
                else "exact-workdir sacct -X"
                if latest
                else None
            ),
        ),
        "elapsed": _scalar(
            elapsed,
            source=(
                "exact-workdir squeue/scontrol"
                if current
                else "exact-workdir sacct -X"
                if latest
                else None
            ),
        ),
        "elapsed_seconds": _scalar(
            _slurm_duration_seconds(elapsed),
            source=(
                "exact-workdir squeue/scontrol"
                if current
                else "exact-workdir sacct -X"
                if latest
                else None
            ),
        ),
        "eta": _last_tail_marker(active_jobs, ETA_MARKER_RE),
        "first_causal_error": first_causal_error,
        "retry_count": _scalar(retry_count, source=retry_source),
        "log_paths": log_paths,
        "terminal_failure": terminal_failure,
        "jobs": matched_job_evidence,
        "accounting_evidence_bounded": status.get("accounting", {}).get("jobs_bounded", False),
    }


def _milestone(
    path: Path | None,
    unit: str,
    status: dict[str, Any],
    *,
    rule_tokens: Sequence[str] = (),
    configured: bool = True,
) -> dict[str, Any]:
    execution = _milestone_execution_evidence(unit, status, rule_tokens)
    if not configured:
        return {
            "state": "not_configured",
            "display": "not configured",
            "path": None,
            "execution": execution,
        }
    if path is not None and path.is_file():
        stamp = _utc_timestamp(path.stat().st_mtime)
        return {
            "state": "complete",
            "display": stamp,
            "path": str(path),
            "execution": execution,
        }
    scheduler_state = str(execution["scheduler_state"]["value"] or "").upper()
    state = None
    if scheduler_state in ACTIVE_STATES:
        state = "running"
    elif scheduler_state == "PENDING":
        state = "pending"
    elif execution["terminal_failure"] is not None:
        state = "failed"
    failure_text = "\n".join(status.get("workflow", {}).get("failure_lines", []))
    if state is None and _job_matches(unit, rule_tokens, failure_text):
        state = "failed"
    if state == "running":
        elapsed = execution["elapsed"]["value"] or "unknown"
        return {
            "state": state,
            "display": f"running {elapsed}",
            "path": str(path) if path else None,
            "execution": execution,
        }
    if state == "failed":
        return {
            "state": state,
            "display": "failed",
            "path": str(path) if path else None,
            "execution": execution,
        }
    return {
        "state": "pending",
        "display": "pending",
        "path": str(path) if path else None,
        "execution": execution,
    }


def _metadata_for_unit(build_root: Path, unit: str) -> tuple[dict[str, Any], Path]:
    path = build_root / unit / f"{unit}_metadata.json"
    return _load_json(path), path


def _observed_sex_evidence(unit_root: Path) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for path in sorted(unit_root.rglob("*.sex_complement.json")):
        payload = _load_json(path)
        value = _nested_value(
            payload,
            {
                "inferred_sex_chromosome_complement",
                "observed_gender",
                "observed_sex",
                "inferred_sex",
                "sex",
            },
        )
        if value in (None, ""):
            continue
        evidence.append(
            {
                "value": value,
                "source": str(path),
                "method": _nested_value(payload, {"method", "tool", "caller"}),
                "schema_version": payload.get("schema_version"),
            }
        )
    return evidence


def _hybrid_sv_provenance(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    if not payload:
        return {
            "available": False,
            "path": str(path),
            "selected_callset": None,
            "longreadsv": None,
            "short_read_fallback": None,
        }
    return {
        "available": True,
        "path": str(path),
        "schema_version": payload.get("schema_version"),
        "created_utc": payload.get("created_utc"),
        "workflow_rule": payload.get("workflow_rule"),
        "selected_callset": payload.get("selected_callset"),
        "vcf": payload.get("vcf"),
        "longreadsv": payload.get("longreadsv"),
        "short_read_fallback": payload.get("short_read_fallback"),
    }


def _unit_benchmark_costs(build_root: Path) -> dict[str, dict[str, Any]]:
    summary = build_root / "reports" / "benchmarks_summary.tsv"
    if not summary.is_file():
        return {}
    grouped: dict[str, list[dict[str, str]]] = {}
    with summary.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        for raw_row in csv.DictReader(handle, delimiter="\t"):
            row = {
                str(key or "").strip().lower(): str(value or "").strip()
                for key, value in raw_row.items()
            }
            unit = row.get("sample", "")
            if unit:
                grouped.setdefault(unit, []).append(row)
    result: dict[str, dict[str, Any]] = {}
    for unit, rows in grouped.items():
        values: list[float] = []
        missing = 0
        for row in rows:
            raw = row.get("task_cost", "")
            try:
                value = float(raw)
            except ValueError:
                missing += 1
                continue
            if not math.isfinite(value):
                missing += 1
                continue
            values.append(value)
        exact = bool(rows) and missing == 0
        result[unit] = {
            "value_usd": round(sum(values), 12) if exact else None,
            "state": "available" if exact else "incomplete",
            "source": str(summary),
            "matched_rows": len(rows),
            "priced_rows": len(values),
            "unpriced_rows": missing,
            "note": (
                None
                if exact
                else "unit task cost is withheld unless every matched benchmark row has task_cost"
            ),
        }
    return result


def _unit_runtime(
    milestones: dict[str, dict[str, Any]],
    *,
    start_epoch: float,
    start_source: str,
) -> dict[str, Any]:
    configured = [value for value in milestones.values() if value["state"] != "not_configured"]
    completed_paths = [
        Path(value["path"])
        for value in configured
        if value["state"] == "complete" and value.get("path")
    ]
    authoritative_start = (
        start_source == "controller process elapsed time"
        or start_source.startswith("timestamp encoded in ")
    )
    full_wall: dict[str, Any]
    if not authoritative_start:
        full_wall = {
            "seconds": None,
            "duration": None,
            "completed_at": None,
            "state": "not_available",
            "source": {"started_at": start_source},
            "note": "full wall runtime requires an observed controller or encoded launch timestamp",
        }
    elif configured and len(completed_paths) == len(configured):
        completed_epoch = max(path.stat().st_mtime for path in completed_paths)
        if completed_epoch >= start_epoch:
            seconds = int(completed_epoch - start_epoch)
            full_wall = {
                "seconds": seconds,
                "duration": _duration(seconds),
                "completed_at": _utc_timestamp(completed_epoch),
                "state": "available",
                "source": {
                    "started_at": start_source,
                    "required_artifacts": [str(path) for path in completed_paths],
                },
                "note": "controller start through the latest configured required milestone artifact",
            }
        else:
            full_wall = {
                "seconds": None,
                "duration": None,
                "completed_at": _utc_timestamp(completed_epoch),
                "state": "inconsistent",
                "source": {
                    "started_at": start_source,
                    "required_artifacts": [str(path) for path in completed_paths],
                },
                "note": "required artifact timestamp predates the observed controller start",
            }
    else:
        full_wall = {
            "seconds": None,
            "duration": None,
            "completed_at": None,
            "state": "not_available",
            "source": None,
            "note": "full wall runtime requires every configured milestone artifact",
        }
    return {
        "full_wall": full_wall,
        "dag_critical_path_no_wait": {
            "seconds": None,
            "duration": None,
            "state": "not_available",
            "source": None,
            "note": (
                "DayOA 11.0.15 evidence does not emit task dependency timing; "
                "benchmark duration sums are not a DAG critical path"
            ),
        },
    }


def _unit_row(
    *,
    unit_row: dict[str, str],
    sample_row: dict[str, str],
    specimen_row: dict[str, str],
    build_root: Path,
    status: dict[str, Any],
    segdup_genes: list[str],
    start_epoch: float,
    start_source: str,
    benchmark_cost: dict[str, Any] | None,
) -> dict[str, Any]:
    unit = unit_row["ANALYSIS_UNIT_UID"]
    prefix = build_root / unit
    sr_root = prefix / "align" / "hiomrs_sr" / "na"
    lr_root = prefix / "align" / "hiomrs_lr" / "na"
    snv_root = sr_root / "snv" / "hiomrs"
    sv_root = sr_root / "sv" / "hiomrs"
    cnv_root = sr_root / "cnv" / "hiomrs"
    specialty = sr_root / "hiomrs"
    stem = f"{unit}.hiomrs_sr.na.hiomrs"
    paths = {
        "sr_alignment": sr_root / f"{unit}.hiomrs_sr.na.cram",
        "lr_alignment": lr_root / f"{unit}.hiomrs_lr.na.cram",
        "hybrid_snv": snv_root / f"{stem}.g.vcf.gz",
        "hybrid_sv": sv_root / f"{stem}.sv.vcf.gz",
        "hybrid_cnv": cnv_root / f"{stem}.cnv.vcf.gz",
        "mitochondrial": specialty / "mito" / f"{unit}.mito.vcf.gz",
        "expansionhunter": specialty / "expansionhunter" / f"{unit}.eh.vcf",
    }
    hybrid_sv_provenance_path = sv_root / f"{stem}.sv.provenance.json"
    rule_tokens = {
        "sr_alignment": ("hiomrs_sr",),
        "lr_alignment": ("hiomrs_lr",),
        "hybrid_snv": ("hiomrs_core", "hiomrs_collect"),
        "hybrid_sv": ("hiomrs_longreadsv",),
        "hybrid_cnv": ("hiomrs_core", "hiomrs_collect"),
        "mitochondrial": ("hiomrs_mito",),
        "expansionhunter": ("hiomrs_expansionhunter",),
    }
    milestones = {
        name: _milestone(path, unit, status, rule_tokens=rule_tokens[name])
        for name, path in paths.items()
    }
    segdup_root = specialty / "segdup"
    segdup_done = segdup_root / f"{unit}.segdup.done"
    if segdup_done.is_file():
        segdup_complete = list(segdup_genes)
    else:
        segdup_complete = [
            gene
            for gene in segdup_genes
            if (segdup_root / f"{unit}.{gene}.result.vcf.gz").is_file()
            or (segdup_root / "shards" / f"{unit}.{gene}.segdup.tar.gz").is_file()
        ]
    segdup_state = _milestone(segdup_done, unit, status, rule_tokens=("hiomrs_segdup",))
    segdup_state.update(
        {
            "completed_targets": len(segdup_complete),
            "total_targets": len(segdup_genes),
            "targets": segdup_genes,
        }
    )
    milestones["segdup"] = segdup_state

    configured = [value for value in milestones.values() if value["state"] != "not_configured"]
    complete = sum(value["state"] == "complete" for value in configured)
    metadata, metadata_path = _metadata_for_unit(build_root, unit)
    sr_stats_path = sr_root / "alignqc" / "alignstats" / f"{unit}.hiomrs_sr.na.alignstats.tsv"
    lr_stats_path = lr_root / "alignqc" / "alignstats" / f"{unit}.hiomrs_lr.na.alignstats.tsv"
    sr_stats = _single_row_tsv(sr_stats_path)
    lr_stats = _single_row_tsv(lr_stats_path)
    observed_path = (
        prefix
        / "align"
        / "hiomrs_input_lr"
        / "na"
        / "alignqc"
        / "sex_complement"
        / f"{unit}.hiomrs_input_lr.na.sex_complement.json"
    )
    observed_payload = _load_json(observed_path)
    observed_gender = _nested_value(
        observed_payload, {"observed_gender", "observed_sex", "inferred_sex", "sex"}
    )
    contamination_path = (
        sr_root / "alignqc" / "contam" / "site_mix" / f"{unit}.hiomrs_sr.na.site_mix.tsv"
    )
    contamination = _float_value(
        _single_row_tsv(contamination_path),
        (
            "contamination_pct",
            "contamination",
            "Contamination",
            "FREEMIX",
            "mix",
            "Mix",
        ),
    )
    metadata_source = str(metadata_path) if metadata else None
    observed_sex_evidence = _observed_sex_evidence(prefix)

    fields = {
        "required_gender": _first_explicit(
            specimen_row or sample_row,
            ("BIOLOGICAL_SEX", "REQUIRED_GENDER", "SEX"),
            source="config/specimens.tsv" if specimen_row else "config/samples.tsv",
        ),
        "observed_gender": _scalar(
            observed_gender, source=str(observed_path) if observed_gender is not None else None
        ),
        "observed_gender_evidence": observed_sex_evidence,
        "contamination_percent": _scalar(
            contamination, source=str(contamination_path) if contamination is not None else None
        ),
        "ilmn_mean_coverage": _scalar(
            _float_value(sr_stats, ("WgsCoverageMean", "MeanCoverage", "mean_coverage")),
            source=str(sr_stats_path) if sr_stats else None,
        ),
        "ilmn_median_coverage": _scalar(
            _float_value(sr_stats, ("WgsCoverageMedian", "MedianCoverage", "median_coverage")),
            source=str(sr_stats_path) if sr_stats else None,
        ),
        "ont_mean_coverage": _scalar(
            _float_value(lr_stats, ("WgsCoverageMean", "MeanCoverage", "mean_coverage")),
            source=str(lr_stats_path) if lr_stats else None,
        ),
        "ont_median_coverage": _scalar(
            _float_value(lr_stats, ("WgsCoverageMedian", "MedianCoverage", "median_coverage")),
            source=str(lr_stats_path) if lr_stats else None,
        ),
        "specimen_type": _first_explicit(
            specimen_row or sample_row,
            ("SPECIMEN_TYPE", "SAMPLESOURCE", "SAMPLE_TYPE"),
            source="config/specimens.tsv" if specimen_row else "config/samples.tsv",
        ),
        "sample_use": _first_explicit(
            sample_row, ("SAMPLEUSE", "SAMPLE_USE"), source="config/samples.tsv"
        ),
        "order_type": _first_explicit(sample_row, ("ORDER_TYPE",), source="config/samples.tsv"),
        "final_qc_disposition": _scalar(
            _nested_value(metadata, {"final_qc_disposition"}), source=metadata_source
        ),
        "final_data_package_ready": _scalar(
            _nested_value(metadata, {"final_data_package_ready"}), source=metadata_source
        ),
        "final_data_package_delivered": _scalar(
            _nested_value(metadata, {"final_data_package_delivered"}), source=metadata_source
        ),
        "relatives": _scalar(
            _nested_value(metadata, {"relatives", "family_relatives"}), source=metadata_source
        ),
    }
    return {
        "analysis_unit_uid": unit,
        "library_euid": unit_row.get("LIBRARY_EUID") or None,
        "sample_id": unit_row.get("SAMPLEID"),
        "sample_euid": sample_row.get("SAMPLE_EUID") or None,
        "specimen_id": sample_row.get("SPECIMEN_ID") or None,
        "specimen_euid": specimen_row.get("SPECIMEN_EUID") or None,
        "overall_percent_complete": (
            round(100 * complete / len(configured), 1) if configured else 0.0
        ),
        "milestones": milestones,
        "runtime": _unit_runtime(
            milestones,
            start_epoch=start_epoch,
            start_source=start_source,
        ),
        "benchmark_task_cost": benchmark_cost
        or {
            "value_usd": None,
            "state": "not_available",
            "source": None,
            "matched_rows": 0,
            "priced_rows": 0,
            "unpriced_rows": 0,
            "note": "no exact unit rows were present in benchmarks_summary.tsv",
        },
        "hybrid_sv_provenance": _hybrid_sv_provenance(hybrid_sv_provenance_path),
        "metrics": fields,
        "giab_hc_snv_fscore": _scalar(None, source=None),
        "_ont_read_length": _float_value(
            lr_stats, ("AlignedReadLengthMedian", "aligned_read_length_median")
        ),
        "_ilmn_insert_size": _float_value(sr_stats, ("InsertSizeMedian", "insert_size_median")),
    }


def _apply_giab_fscores(build_root: Path, rows: list[dict[str, Any]]) -> None:
    path = build_root / "other_reports" / "giab_concordance_mqc.tsv"
    if not path.is_file():
        return
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        data = list(csv.DictReader(handle, delimiter="\t"))
    for row in rows:
        unit = row["analysis_unit_uid"]
        matches = [
            item
            for item in data
            if str(item.get("Sample", "")) == unit
            and str(item.get("VariantClass", "")).upper() in {"SNV", "SNP"}
            and str(item.get("SNVCaller", "")).lower() == "hiomrs"
            and "giabhc" in str(item.get("ROI", "")).lower().replace("_", "")
        ]
        if len(matches) == 1:
            value = _float_value(matches[0], ("Fscore", "F-score", "fscore"))
            row["giab_hc_snv_fscore"] = _scalar(value, source=str(path))
        elif len(matches) > 1:
            row["giab_hc_snv_fscore"] = _scalar(None, source=str(path), state="ambiguous")


def _summary(values: list[float]) -> dict[str, float | None]:
    return {
        "minimum": min(values) if values else None,
        "median": statistics.median(values) if values else None,
        "maximum": max(values) if values else None,
    }


def _retry_evidence(status: dict[str, Any]) -> dict[str, Any]:
    master = status["workflow"].get("master_log")
    lines: list[str] = []
    master_available = bool(master and Path(master).is_file())
    if master_available:
        retry_re = re.compile(
            r"(?:will be retried|trying to restart job|attempt\s+\d+\s+of)", re.IGNORECASE
        )
        lines = [
            line.strip()
            for line in Path(master).read_text(encoding="utf-8", errors="replace").splitlines()
            if retry_re.search(line)
        ]
    identifiers: set[str] = set()
    for line in lines:
        match = re.search(r"\bjob\s+(\d+)\b", line, re.IGNORECASE)
        identifiers.add(f"job:{match.group(1)}" if match else f"event:{line}")
    restart_values: list[int] = []
    for job in status["slurm"]["jobs"]:
        if job.get("restart_count") is None:
            continue
        count = int(job["restart_count"])
        restart_values.append(count)
        if count:
            identifiers.add(f"slurm:{job.get('job_id') or job.get('name')}")
    slurm_restarts = sum(restart_values)
    available = master_available or bool(restart_values)
    return {
        "available": available,
        "count": len(identifiers) if available else None,
        "event_count": len(lines) + slurm_restarts if available else None,
        "identifiers": sorted(identifiers),
        "master_log_lines": lines[-50:],
        "active_slurm_restarts": slurm_restarts if restart_values else None,
    }


def _dag(dayoa_root: Path) -> dict[str, Any]:
    candidates = sorted(
        {*dayoa_root.glob("dags/rulegraph*.png"), *dayoa_root.glob("dags/dag*.png")}
    )
    files = [path for path in candidates if path.is_file()]
    if not files:
        return {"available": False, "path": None, "size_bytes": None, "sha256": None}
    latest_mtime = max(path.stat().st_mtime for path in files)
    latest = [path for path in files if path.stat().st_mtime == latest_mtime]
    if len(latest) != 1:
        raise CommandSampleStatsError(
            "DAG selection is ambiguous: multiple latest PNGs have the same timestamp"
        )
    path = latest[0]
    return {
        "available": True,
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _start_time(dayoa_root: Path, status: dict[str, Any]) -> tuple[float, str]:
    processes = status["controller"].get("processes", [])
    elapsed = max((int(item["elapsed_seconds"]) for item in processes), default=None)
    if elapsed is not None:
        return datetime.now(timezone.utc).timestamp() - elapsed, "controller process elapsed time"
    master = status["workflow"].get("master_log")
    if master and Path(master).is_file():
        name = Path(master).name
        match = re.search(r"(?P<stamp>\d{4}-\d{2}-\d{2}T\d{2}[-:]\d{2}[-:]\d{2})", name)
        if match:
            parsed = datetime.strptime(
                match.group("stamp").replace(":", "-"),
                "%Y-%m-%dT%H-%M-%S",
            ).replace(tzinfo=timezone.utc)
            return parsed.timestamp(), f"timestamp encoded in {master}"
        compact = re.search(r"(?P<stamp>\d{8}T\d{6}Z)", name)
        if compact:
            parsed = datetime.strptime(compact.group("stamp"), "%Y%m%dT%H%M%SZ").replace(
                tzinfo=timezone.utc
            )
            return parsed.timestamp(), f"timestamp encoded in {master}"
    return dayoa_root.stat().st_mtime, str(dayoa_root)


def _relevant_environment() -> dict[str, str]:
    allowed = ("DAYOA_", "DYOA_", "DAY_")
    return {
        key: value
        for key, value in sorted(os.environ.items())
        if key.startswith(allowed) and not any(part in key.upper() for part in SECRET_ENV_PARTS)
    }


def collect_command_sample_stats(
    analysis_root: str | Path,
    *,
    name: str,
    pipeline: str,
    tail_lines: int = 1000,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    """Collect the source-backed HIOMRS sample-stats JSON contract."""

    report_name = str(name).strip()
    if not report_name:
        raise CommandSampleStatsError("--name must be non-empty")
    if pipeline not in PIPELINES:
        raise CommandSampleStatsError(
            f"unsupported pipeline {pipeline!r}; supported: {', '.join(sorted(PIPELINES))}"
        )
    root = Path(analysis_root).expanduser().resolve()
    dayoa_root = root / "daylily-omics-analysis"
    status = collect_analysis_status(root, mode="full", tail_lines=tail_lines, runner=runner)
    from daylily_ec.repositories import load_repository_catalog

    catalog = load_repository_catalog()
    command = catalog.get_command(PIPELINES[pipeline])
    units, samples, specimen_by_id, unit_label = _load_analysis_manifests(
        dayoa_root,
        input_contract=command.input_contract,
    )
    sample_by_id = {row["SAMPLEID"]: row for row in samples}
    build_root = dayoa_root / "results" / "day" / command.genome
    genes = _segdup_genes(dayoa_root)
    generated = datetime.now(timezone.utc)
    start_epoch, start_source = _start_time(dayoa_root, status)
    benchmark_costs = _unit_benchmark_costs(build_root)
    rows = [
        _unit_row(
            unit_row=unit,
            sample_row=sample_by_id[unit["SAMPLEID"]],
            specimen_row=specimen_by_id.get(
                sample_by_id[unit["SAMPLEID"]].get("SPECIMEN_ID", ""), {}
            ),
            build_root=build_root,
            status=status,
            segdup_genes=genes,
            start_epoch=start_epoch,
            start_source=start_source,
            benchmark_cost=benchmark_costs.get(unit["ANALYSIS_UNIT_UID"]),
        )
        for unit in units
    ]
    _apply_giab_fscores(build_root, rows)
    ont_lengths = [
        float(row["_ont_read_length"]) for row in rows if row["_ont_read_length"] is not None
    ]
    ilmn_inserts = [
        float(row["_ilmn_insert_size"]) for row in rows if row["_ilmn_insert_size"] is not None
    ]
    for row in rows:
        row.pop("_ont_read_length")
        row.pop("_ilmn_insert_size")
    progress = status["workflow"]["progress"]
    total = progress["total"]
    complete = progress["completed"]
    running = (
        sum(str(job.get("state", "")).upper() in ACTIVE_STATES for job in status["slurm"]["jobs"])
        if status["slurm"].get("available")
        else None
    )
    failed_events = status["workflow"]["failure_count"]
    failed = (
        sum(
            int(count)
            for state, count in status["accounting"].get("state_counts", {}).items()
            if _normalized_slurm_state(state) in FAILED_STATES
        )
        if status["accounting"].get("available")
        else None
    )
    observed_commands = [
        command_text
        for pane in status["controller"]["tmux_panes"]
        for command_text in pane.get("observed_commands", [])
    ]
    dayoa_identity = _git_identity(dayoa_root, runner=runner)
    retry = _retry_evidence(status)
    job_counts = {key: dict(value) for key, value in status.get("job_counts", {}).items()}
    job_counts["retried"] = {
        "value": retry["count"],
        "available": retry["available"],
        "source": status["workflow"].get("master_log"),
        "note": "unique explicit retry markers plus active Slurm restart evidence",
    }
    canonical_files = status.get("canonical_artifacts", {}).get("files", {})
    strict_requirements = status.get("terminal_evidence", {}).get("requirements", {})
    strict_artifact_names = (
        "DAY_final_multiqc.html",
        "multiqc_data.json",
        "dayoa_evidence_manifest.json",
    )
    strict_artifacts_present = all(canonical_files.get(name) for name in strict_artifact_names)
    report = {
        "schema_version": "dyec.command_sample_stats.v2",
        "compatible_schema_versions": ["dyec.command_sample_stats.v1"],
        "name": report_name,
        "cluster": {
            "name": None,
            "region": None,
            "availability_zone": None,
            "headnode_instance_id": None,
        },
        "analysis": {
            "analysis_root": str(root),
            "dayoa_root": str(dayoa_root),
            "started_at": _utc_timestamp(start_epoch),
            "started_at_source": start_source,
            "runtime_seconds": max(0, int(generated.timestamp() - start_epoch)),
            "runtime": _duration(generated.timestamp() - start_epoch),
            "generated_at": generated.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "terminal_state": status.get("state"),
            "controller_return_code": status.get("controller", {}).get("return_code"),
            "terminal_evidence": status.get("terminal_evidence"),
            "tmux_sessions": sorted(
                {pane["session"] for pane in status["controller"]["tmux_panes"]}
            ),
        },
        "command_details": {
            "dyec_version": __version__,
            "dayoa_version": dayoa_identity,
            "command_catalog_key": command.command_id,
            "command_catalog_version": catalog.command_catalog_version,
            "validated_version": command.validated_version,
            "git_tag": command.git_tag,
            "dayoa_environment": _relevant_environment(),
            "expected_command": f"dy-a {command.day_profile} {command.genome}\n{command.dy_command}",
            "observed_commands": observed_commands,
            "retried_jobs": retry,
        },
        "costs": {
            "completed_benchmark_cost_usd": status.get("benchmarks", {}).get(
                "completed_cost_usd_sum"
            ),
            "cluster_budget": {
                "available": False,
                "reason": "AWS enrichment not requested in headnode-local collection",
            },
            "project_budget": {
                "available": False,
                "reason": "no exact project cost-center was present in collected job evidence",
            },
        },
        "pipeline": {
            "name": pipeline,
            "input_contract": command.input_contract,
            "manifest_files": (
                ["specimens.tsv", "samples.tsv", "libraries.tsv"]
                if command.input_contract == "sample_manifest_v12"
                else ["samples.tsv", "units.tsv"]
            ),
            "specimens_rows": len(specimen_by_id) if specimen_by_id else None,
            "samples_rows": len(samples),
            "units_rows": len(units),
            "libraries_rows": len(units) if unit_label == "libraries.tsv" else None,
            "jobs_total": total,
            "jobs_complete": complete,
            "jobs_failed": failed,
            "jobs_failed_events": failed_events,
            "jobs_running": running,
            "jobs_to_run": (
                max(0, total - complete - running - failed)
                if None not in (total, complete, running, failed)
                else None
            ),
            "jobs_submitted": job_counts.get("submitted", {}).get("value"),
            "jobs_pending": job_counts.get("pending", {}).get("value"),
            "jobs_still_to_run": job_counts.get("still_to_run", {}).get("value"),
            "jobs_retried": job_counts["retried"]["value"],
            "jobs_dependency_blocked": job_counts.get("dependency_blocked", {}).get("value"),
            "job_counts": job_counts,
            "percent_complete": progress["percent"],
            "ont_aligned_read_length_median_summary": _summary(ont_lengths),
            "ilmn_insert_size_median_summary": _summary(ilmn_inserts),
            "final_multiqc": bool(canonical_files.get("DAY_final_multiqc.html")),
            "evidence_manifest": bool(canonical_files.get("dayoa_evidence_manifest.json")),
            "strict_success": {
                "verified": status.get("state") == "SUCCESS"
                and bool(strict_requirements)
                and all(strict_requirements.values())
                and strict_artifacts_present,
                "controller_state": status.get("state"),
                "controller_return_code": status.get("controller", {}).get("return_code"),
                "requirements": strict_requirements,
                "artifacts": {
                    name: {
                        "present": bool(canonical_files.get(name)),
                        "paths": canonical_files.get(name, []),
                    }
                    for name in strict_artifact_names
                },
            },
        },
        "library_units": rows,
        "dag": _dag(dayoa_root),
        "status_evidence": status,
    }
    return {report_name: report}


def copy_dag(payload: dict[str, Any], destination: str | Path) -> dict[str, Any]:
    """Copy the selected DAG to one exact, non-existing destination and verify it."""

    if len(payload) != 1:
        raise CommandSampleStatsError("sample-stats payload must have exactly one top-level name")
    report = next(iter(payload.values()))
    dag = report["dag"]
    if not dag["available"] or not dag["path"]:
        raise CommandSampleStatsError("this analysis has no generated DAG PNG")
    target = Path(destination).expanduser().resolve()
    if target.exists():
        raise CommandSampleStatsError(f"refusing to overwrite DAG destination: {target}")
    if not target.parent.is_dir():
        raise CommandSampleStatsError(f"DAG destination parent does not exist: {target.parent}")
    shutil.copyfile(dag["path"], target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    if target.stat().st_size != dag["size_bytes"] or digest != dag["sha256"]:
        target.unlink(missing_ok=True)
        raise CommandSampleStatsError("DAG copy failed SHA-256 or size verification")
    result = {"path": str(target), "size_bytes": target.stat().st_size, "sha256": digest}
    report["dag_download"] = result
    return result


def enrich_aws_context(
    payload: dict[str, Any],
    *,
    profile: str,
    region: str,
    cluster: str,
    headnode_instance_id: str,
) -> None:
    """Add live AWS placement and budget evidence without changing AWS state."""

    import boto3

    from daylily_ec.aws.cost_centers import get_cost_center, get_cost_center_usage

    if len(payload) != 1:
        raise CommandSampleStatsError("sample-stats payload must have exactly one top-level name")
    report = next(iter(payload.values()))
    report["cluster"].update(
        {
            "name": cluster,
            "region": region,
            "headnode_instance_id": headnode_instance_id,
        }
    )
    session = boto3.Session(profile_name=profile, region_name=region)
    try:
        response = session.client("ec2").describe_instances(InstanceIds=[headnode_instance_id])
        instance = response["Reservations"][0]["Instances"][0]
        report["cluster"]["availability_zone"] = instance["Placement"]["AvailabilityZone"]
    except Exception as exc:  # noqa: BLE001
        report["cluster"]["availability_zone_error"] = str(exc)

    try:
        account_id = session.client("sts").get_caller_identity()["Account"]
        budget = session.client("budgets", region_name="us-east-1").describe_budget(
            AccountId=account_id,
            BudgetName=cluster,
        )["Budget"]
        limit = budget.get("BudgetLimit", {})
        calculated = budget.get("CalculatedSpend", {})
        current_spend = calculated.get("ActualSpend", {})
        forecast_spend = calculated.get("ForecastedSpend", {})
        report["costs"]["cluster_budget"] = {
            "available": True,
            "name": budget.get("BudgetName"),
            "limit": str(limit.get("Amount")) if limit.get("Amount") is not None else None,
            "unit": limit.get("Unit"),
            "time_unit": budget.get("TimeUnit"),
            "budget_type": budget.get("BudgetType"),
            "actual_spend": (
                str(current_spend.get("Amount"))
                if current_spend.get("Amount") is not None
                else None
            ),
            "forecasted_spend": (
                str(forecast_spend.get("Amount"))
                if forecast_spend.get("Amount") is not None
                else None
            ),
        }
    except Exception as exc:  # noqa: BLE001
        report["costs"]["cluster_budget"] = {"available": False, "reason": str(exc)}

    comments = sorted(
        {
            str(job.get("comment", "")).strip()
            for job in report["status_evidence"]["slurm"]["jobs"]
            if str(job.get("comment", "")).strip() not in {"", "(null)", "None"}
        }
        | {
            str(job.get("Comment", "")).strip()
            for job in report["status_evidence"]["accounting"]["jobs"]
            if str(job.get("Comment", "")).strip() not in {"", "(null)", "None"}
        }
    )
    if len(comments) != 1:
        report["costs"]["project_budget"] = {
            "available": False,
            "reason": "expected exactly one exact-root Slurm cost-center comment",
            "observed_cost_centers": comments,
        }
        return
    try:
        home = boto3.Session(profile_name=profile, region_name="us-west-2")
        client = home.client("dynamodb")
        center = get_cost_center(client, comments[0])
        usage = get_cost_center_usage(
            client,
            comments[0],
            month=datetime.now(timezone.utc).strftime("%Y-%m"),
        )
        report["costs"]["project_budget"] = {
            "available": True,
            "cost_center": comments[0],
            "registry": center.to_dict() if center else None,
            "usage": usage.to_dict() if usage else None,
        }
    except Exception as exc:  # noqa: BLE001
        report["costs"]["project_budget"] = {
            "available": False,
            "cost_center": comments[0],
            "reason": str(exc),
        }


def render_command_sample_stats(payload: dict[str, Any]) -> str:
    """Render the compact human table; JSON mode retains all provenance."""

    if len(payload) != 1:
        raise CommandSampleStatsError("sample-stats payload must have exactly one top-level name")
    name, report = next(iter(payload.items()))
    pipeline = report["pipeline"]
    job_counts = pipeline.get("job_counts", {})

    def count(name: str) -> Any:
        return job_counts.get(name, {}).get("value")

    headers = [
        "Sample",
        "%",
        "SR Aln",
        "LR Aln",
        "Hybrid SNV",
        "Hybrid SV",
        "Mito",
        "CNV",
        "SegDup",
        "EH",
        "Req Gender",
        "Obs Gender",
        "Contam %",
        "ILMN Cov mean/med",
        "ONT Cov mean/med",
        "QC Disposition",
        "Package Ready",
        "Delivered",
        "GIAB HC Fscore",
        "Specimen",
        "Sample Use",
        "Order Type",
        "Relatives",
    ]
    lines = [
        f"{name}: {pipeline['name']}",
        f"Generated: {report['analysis']['generated_at']}  Runtime: {report['analysis']['runtime']}  Tmux: {','.join(report['analysis']['tmux_sessions']) or 'not observed'}",
        f"Jobs: {pipeline['jobs_complete']}/{pipeline['jobs_total']} ({pipeline['percent_complete']}%); "
        f"submitted={count('submitted')}; running={pipeline['jobs_running']}; "
        f"pending={count('pending')}; failed={pipeline['jobs_failed']}; "
        f"still-to-run={count('still_to_run')}; dependency-blocked={count('dependency_blocked')}; "
        f"retries={report['command_details']['retried_jobs']['count']}; "
        f"final MultiQC={'Y' if pipeline['final_multiqc'] else 'N'}; "
        f"strict success={'Y' if pipeline.get('strict_success', {}).get('verified') else 'N'}",
        "\t".join(headers),
    ]
    for row in report["library_units"]:
        milestone = row["milestones"]
        metric = row["metrics"]
        segdup = milestone["segdup"]

        def value(key: str) -> Any:
            return metric[key]["value"] if metric[key]["value"] is not None else ""

        lines.append(
            "\t".join(
                str(item)
                for item in (
                    row["analysis_unit_uid"],
                    row["overall_percent_complete"],
                    milestone["sr_alignment"]["display"],
                    milestone["lr_alignment"]["display"],
                    milestone["hybrid_snv"]["display"],
                    milestone["hybrid_sv"]["display"],
                    milestone["mitochondrial"]["display"],
                    milestone["hybrid_cnv"]["display"],
                    f"{segdup['completed_targets']}/{segdup['total_targets']} ({segdup['display']})",
                    milestone["expansionhunter"]["display"],
                    value("required_gender"),
                    value("observed_gender"),
                    value("contamination_percent"),
                    f"{value('ilmn_mean_coverage')}/{value('ilmn_median_coverage')}",
                    f"{value('ont_mean_coverage')}/{value('ont_median_coverage')}",
                    value("final_qc_disposition"),
                    value("final_data_package_ready"),
                    value("final_data_package_delivered"),
                    row["giab_hc_snv_fscore"]["value"] or "",
                    value("specimen_type"),
                    value("sample_use"),
                    value("order_type"),
                    value("relatives"),
                )
            )
        )
    return "\n".join(lines)
