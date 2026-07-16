"""Strict, exact-root progress reporting for supported DayOA command families."""

from __future__ import annotations

import csv
import hashlib
import json
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
        {str(key).strip().upper(): str(value or "").strip() for key, value in row.items()}
        for row in rows
    ]


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


def _running_or_failed(
    unit: str,
    status: dict[str, Any],
    rule_tokens: Sequence[str],
) -> tuple[str | None, str | None]:
    for job in status["slurm"]["jobs"]:
        job_text = " ".join(str(job.get(key, "")) for key in ("name", "stdout", "stderr")).lower()
        if unit.lower() in job_text and any(token in job_text for token in rule_tokens):
            state = str(job.get("state", "")).upper()
            if state in ACTIVE_STATES:
                return "running", str(job.get("elapsed") or "unknown")
    for job in status["accounting"]["jobs"]:
        name = str(job.get("JobName", "")).lower()
        if (
            unit.lower() in name
            and any(token in name for token in rule_tokens)
            and str(job.get("State", "")).split("+", 1)[0] in FAILED_STATES
        ):
            return "failed", None
    failure_text = "\n".join(status["workflow"].get("failure_lines", []))
    if unit in failure_text and any(token in failure_text.lower() for token in rule_tokens):
        return "failed", None
    return None, None


def _milestone(
    path: Path | None,
    unit: str,
    status: dict[str, Any],
    *,
    rule_tokens: Sequence[str] = (),
    configured: bool = True,
) -> dict[str, Any]:
    if not configured:
        return {"state": "not_configured", "display": "not configured", "path": None}
    if path is not None and path.is_file():
        stamp = _utc_timestamp(path.stat().st_mtime)
        return {"state": "complete", "display": stamp, "path": str(path)}
    state, elapsed = _running_or_failed(unit, status, rule_tokens)
    if state == "running":
        return {
            "state": state,
            "display": f"running {elapsed}",
            "path": str(path) if path else None,
        }
    if state == "failed":
        return {"state": state, "display": "failed", "path": str(path) if path else None}
    return {"state": "pending", "display": "pending", "path": str(path) if path else None}


def _metadata_for_unit(build_root: Path, unit: str) -> tuple[dict[str, Any], Path]:
    path = build_root / unit / f"{unit}_metadata.json"
    return _load_json(path), path


def _unit_row(
    *,
    unit_row: dict[str, str],
    sample_row: dict[str, str],
    build_root: Path,
    status: dict[str, Any],
    segdup_genes: list[str],
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

    fields = {
        "required_gender": _first_explicit(
            sample_row, ("BIOLOGICAL_SEX", "REQUIRED_GENDER", "SEX"), source="config/samples.tsv"
        ),
        "observed_gender": _scalar(
            observed_gender, source=str(observed_path) if observed_gender is not None else None
        ),
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
            sample_row,
            ("SPECIMEN_TYPE", "SAMPLESOURCE", "SAMPLE_TYPE"),
            source="config/samples.tsv",
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
        "sample_id": unit_row.get("SAMPLEID"),
        "overall_percent_complete": (
            round(100 * complete / len(configured), 1) if configured else 0.0
        ),
        "milestones": milestones,
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
    if master and Path(master).is_file():
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
    slurm_restarts = 0
    for job in status["slurm"]["jobs"]:
        count = int(job.get("restart_count", 0))
        slurm_restarts += count
        if count:
            identifiers.add(f"slurm:{job.get('job_id') or job.get('name')}")
    return {
        "count": len(identifiers),
        "event_count": len(lines) + slurm_restarts,
        "identifiers": sorted(identifiers),
        "master_log_lines": lines[-50:],
        "active_slurm_restarts": slurm_restarts,
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
    units_path = dayoa_root / "config" / "units.tsv"
    samples_path = dayoa_root / "config" / "samples.tsv"
    units = _read_tsv(units_path)
    samples = _read_tsv(samples_path)
    if any(not row.get("ANALYSIS_UNIT_UID") for row in units):
        raise CommandSampleStatsError(
            f"every units.tsv row must have ANALYSIS_UNIT_UID: {units_path}"
        )
    unit_ids = [row["ANALYSIS_UNIT_UID"] for row in units]
    if len(set(unit_ids)) != len(unit_ids):
        raise CommandSampleStatsError(f"ANALYSIS_UNIT_UID values must be unique: {units_path}")
    sample_ids = [row.get("SAMPLEID", "") for row in samples]
    if any(not sample_id for sample_id in sample_ids):
        raise CommandSampleStatsError(f"every samples.tsv row must have SAMPLEID: {samples_path}")
    if len(set(sample_ids)) != len(sample_ids):
        raise CommandSampleStatsError(f"SAMPLEID values must be unique: {samples_path}")
    sample_by_id = {row.get("SAMPLEID", ""): row for row in samples}
    missing_samples = sorted(
        {row.get("SAMPLEID", "") for row in units if row.get("SAMPLEID", "") not in sample_by_id}
    )
    if missing_samples:
        raise CommandSampleStatsError(
            "units.tsv SAMPLEID values are absent from samples.tsv: " + ", ".join(missing_samples)
        )
    from daylily_ec.repositories import load_repository_catalog

    catalog = load_repository_catalog()
    command = catalog.get_command(PIPELINES[pipeline])
    build_root = dayoa_root / "results" / "day" / command.genome
    genes = _segdup_genes(dayoa_root)
    rows = [
        _unit_row(
            unit_row=unit,
            sample_row=sample_by_id[unit["SAMPLEID"]],
            build_root=build_root,
            status=status,
            segdup_genes=genes,
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
    generated = datetime.now(timezone.utc)
    start_epoch, start_source = _start_time(dayoa_root, status)
    progress = status["workflow"]["progress"]
    total = progress["total"]
    complete = progress["completed"]
    running = sum(
        str(job.get("state", "")).upper() in ACTIVE_STATES for job in status["slurm"]["jobs"]
    )
    failed_events = status["workflow"]["failure_count"]
    failed = sum(
        int(count)
        for state, count in status["accounting"].get("state_counts", {}).items()
        if str(state).split("+", 1)[0] in FAILED_STATES
    )
    observed_commands = [
        command_text
        for pane in status["controller"]["tmux_panes"]
        for command_text in pane.get("observed_commands", [])
    ]
    dayoa_identity = _git_identity(dayoa_root, runner=runner)
    retry = _retry_evidence(status)
    report = {
        "schema_version": "dyec.command_sample_stats.v1",
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
            "samples_rows": len(samples),
            "units_rows": len(units),
            "jobs_total": total,
            "jobs_complete": complete,
            "jobs_failed": failed,
            "jobs_failed_events": failed_events,
            "jobs_running": running,
            "jobs_to_run": (
                max(0, total - complete - running - failed)
                if total is not None and complete is not None
                else None
            ),
            "percent_complete": progress["percent"],
            "ont_aligned_read_length_median_summary": _summary(ont_lengths),
            "ilmn_insert_size_median_summary": _summary(ilmn_inserts),
            "final_multiqc": bool(
                status["canonical_artifacts"].get("files", {}).get("DAY_final_multiqc.html")
            ),
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
        f"Jobs: {pipeline['jobs_complete']}/{pipeline['jobs_total']} ({pipeline['percent_complete']}%); running={pipeline['jobs_running']}; failed={pipeline['jobs_failed']}; retries={report['command_details']['retried_jobs']['count']}; final MultiQC={'Y' if pipeline['final_multiqc'] else 'N'}",
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
