"""Command-catalog benchmark performance profiles for DYEC evidence bundles."""

from __future__ import annotations

import csv
import json
import math
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from daylily_ec.repositories import AnalysisCommand, RepositoryCatalog, load_repository_catalog


PERFORMANCE_HISTORY_SCHEMA = "dyec.command_catalog.performance_history.v1"
PERFORMANCE_PROFILE_SCHEMA = "dyec.command_catalog.performance_profile.v1"
PERFORMANCE_SUMMARY_FIELDS = (
    "command_id",
    "evidence_cohort",
    "catalog_type",
    "status",
    "benchmark_rows",
    "submitted_jobs",
    "slurm_jobs",
    "rule_count",
    "total_wall_s",
    "max_wall_s",
    "median_wall_s",
    "p95_wall_s",
    "total_cpu_time_s",
    "observed_cpu_hours",
    "allocated_vcpu_hours",
    "median_cpu_eff",
    "p95_cpu_eff",
    "max_threads_req",
    "median_threads_req",
    "max_mem_req_mb",
    "max_rss_mb",
    "p95_rss_mb",
    "max_mem_eff",
    "total_io_mb",
    "max_io_mb_s",
    "total_task_cost",
    "median_spot_cost_per_vcpu_hour",
    "over_threaded_rule_count",
    "over_memory_rule_count",
    "io_bound_rule_count",
    "tight_packing_rule_count",
    "partitions",
    "instance_types",
)
DEFAULT_COMPARATOR_METRICS = (
    "total_wall_s",
    "allocated_vcpu_hours",
    "observed_cpu_hours",
    "total_task_cost",
    "max_rss_mb",
    "total_io_mb",
)


class CommandCatalogPerformanceError(RuntimeError):
    """Raised when command-catalog performance profiling cannot complete."""


@dataclass(frozen=True)
class CommandCatalogPerformanceOptions:
    benchmark_rows_tsv: Path
    dyec_version: str
    output_dir: Path
    rule_summary_tsv: Optional[Path] = None
    slurm_jobs_tsv: Optional[Path] = None
    catalog_config: Optional[Path] = None
    dayoa_version: str = ""
    cluster: str = ""
    run_id: str = ""
    captured_at: Optional[str] = None
    command_ids: tuple[str, ...] = ()
    include_all_catalog_commands: bool = False
    dev_command_ids: frozenset[str] = field(default_factory=frozenset)
    prod_command_ids: frozenset[str] = field(default_factory=frozenset)
    history_json: Optional[Path] = None
    replace_existing_version: bool = False


def build_command_catalog_performance_profile(
    options: CommandCatalogPerformanceOptions,
) -> dict[str, Any]:
    """Build, write, and optionally append a command-catalog performance profile."""

    if not str(options.dyec_version).strip():
        raise CommandCatalogPerformanceError("dyec_version is required.")
    benchmark_rows = read_tsv(options.benchmark_rows_tsv)
    rule_rows = read_optional_tsv(options.rule_summary_tsv)
    slurm_rows = read_optional_tsv(options.slurm_jobs_tsv)
    catalog = load_repository_catalog(options.catalog_config)
    command_order = resolve_command_order(
        catalog,
        benchmark_rows=benchmark_rows,
        rule_rows=rule_rows,
        slurm_rows=slurm_rows,
        explicit_command_ids=options.command_ids,
        include_all_catalog_commands=options.include_all_catalog_commands,
    )
    if not command_order:
        raise CommandCatalogPerformanceError("No command ids resolved for performance profile.")

    previous_history = load_history(options.history_json) if options.history_json else None
    previous_profile = latest_prior_profile(previous_history, options.dyec_version)
    commands = {
        command_id: summarize_command(
            command_id,
            catalog=catalog,
            evidence_cohort=evidence_cohort_for_command(command_id, options),
            benchmark_rows=[row for row in benchmark_rows if row.get("command_id") == command_id],
            rule_rows=[row for row in rule_rows if row.get("command_id") == command_id],
            slurm_rows=[row for row in slurm_rows if row.get("command_id") == command_id],
            prior_command=prior_command_profile(previous_profile, command_id),
        )
        for command_id in command_order
    }
    profile = {
        "schema_version": PERFORMANCE_PROFILE_SCHEMA,
        "captured_at": options.captured_at or utc_now(),
        "dyec_version": options.dyec_version,
        "dayoa_version": options.dayoa_version,
        "cluster": options.cluster,
        "run_id": options.run_id,
        "source_files": source_files_payload(options),
        "command_order": list(command_order),
        "command_count": len(command_order),
        "cohort_counts": cohort_counts(commands.values()),
        "status_counts": status_counts(commands.values()),
        "totals": totals_payload(commands.values()),
        "comparator": comparator_payload(previous_profile),
        "commands": commands,
    }
    write_outputs(
        profile,
        output_dir=options.output_dir,
        history_json=options.history_json,
        replace_existing_version=options.replace_existing_version,
    )
    return profile


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise CommandCatalogPerformanceError(f"TSV does not exist: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_optional_tsv(path: Optional[Path]) -> list[dict[str, str]]:
    if path is None:
        return []
    return read_tsv(path)


def resolve_command_order(
    catalog: RepositoryCatalog,
    *,
    benchmark_rows: Sequence[Mapping[str, Any]],
    rule_rows: Sequence[Mapping[str, Any]],
    slurm_rows: Sequence[Mapping[str, Any]],
    explicit_command_ids: Sequence[str],
    include_all_catalog_commands: bool,
) -> tuple[str, ...]:
    seen: set[str] = set()
    command_order: list[str] = []

    def add(command_id: str) -> None:
        cleaned = str(command_id or "").strip()
        if not cleaned or cleaned in seen:
            return
        seen.add(cleaned)
        command_order.append(cleaned)

    if include_all_catalog_commands:
        for command in catalog.commands():
            add(command.command_id)
    for command_id in explicit_command_ids:
        add(command_id)
    if not include_all_catalog_commands and not explicit_command_ids:
        for rows in (benchmark_rows, rule_rows, slurm_rows):
            for row in rows:
                add(str(row.get("command_id") or ""))
    return tuple(command_order)


def evidence_cohort_for_command(
    command_id: str,
    options: CommandCatalogPerformanceOptions,
) -> str:
    if command_id in options.dev_command_ids:
        return "dev"
    if command_id in options.prod_command_ids:
        return "prod"
    return "prod"


def summarize_command(
    command_id: str,
    *,
    catalog: RepositoryCatalog,
    evidence_cohort: str,
    benchmark_rows: Sequence[Mapping[str, Any]],
    rule_rows: Sequence[Mapping[str, Any]],
    slurm_rows: Sequence[Mapping[str, Any]],
    prior_command: Optional[Mapping[str, Any]],
) -> dict[str, Any]:
    command = catalog_command(catalog, command_id)
    benchmark_count = len(benchmark_rows)
    submitted_jobs = sum_int(row.get("submitted_jobs") for row in rule_rows)
    if not submitted_jobs:
        submitted_jobs = len(slurm_rows)
    status = command_status(benchmark_count, submitted_jobs)
    rules = sorted({str(row.get("rule") or "") for row in rule_rows if str(row.get("rule") or "")})
    if not rules:
        rules = sorted({str(row.get("rule") or "") for row in benchmark_rows if str(row.get("rule") or "")})

    total_wall_s = sum_float(row.get("wall_s") for row in benchmark_rows)
    total_cpu_time_s = sum_float(row.get("cpu_time_s") for row in benchmark_rows)
    allocated_vcpu_hours = sum(
        (to_float(row.get("wall_s")) or 0.0) * (to_float(row.get("threads_req")) or 0.0) / 3600.0
        for row in benchmark_rows
    )
    total_task_cost = sum_float(row.get("task_cost") for row in benchmark_rows)
    total_io_mb = sum_float(row.get("total_io_mb") for row in benchmark_rows)
    summary = {
        "command_id": command_id,
        "display_name": command.display_name if command else "",
        "catalog_type": command.type if command else "unknown",
        "evidence_cohort": evidence_cohort,
        "git_tag": command.git_tag if command else "",
        "genome": command.genome if command else "",
        "status": status,
        "benchmark_rows": benchmark_count,
        "submitted_jobs": submitted_jobs,
        "slurm_jobs": len(slurm_rows),
        "rule_count": len(rules),
        "rules": rules,
        "total_wall_s": round_float(total_wall_s),
        "max_wall_s": round_float(max_value(row.get("wall_s") for row in benchmark_rows)),
        "median_wall_s": round_float(median_value(row.get("wall_s") for row in benchmark_rows)),
        "p95_wall_s": round_float(percentile_value(row.get("wall_s") for row in benchmark_rows)),
        "total_cpu_time_s": round_float(total_cpu_time_s),
        "observed_cpu_hours": round_float(total_cpu_time_s / 3600.0),
        "allocated_vcpu_hours": round_float(allocated_vcpu_hours),
        "median_cpu_eff": round_float(median_value(row.get("cpu_eff") for row in benchmark_rows)),
        "p95_cpu_eff": round_float(percentile_value(row.get("cpu_eff") for row in benchmark_rows)),
        "max_threads_req": round_float(max_value(row.get("threads_req") for row in benchmark_rows)),
        "median_threads_req": round_float(median_value(row.get("threads_req") for row in benchmark_rows)),
        "max_mem_req_mb": round_float(max_value(row.get("mem_req_mb") for row in benchmark_rows)),
        "max_rss_mb": round_float(max_value(row.get("max_rss_mb") for row in benchmark_rows)),
        "p95_rss_mb": round_float(percentile_value(row.get("max_rss_mb") for row in benchmark_rows)),
        "max_mem_eff": round_float(max_value(row.get("max_mem_eff") for row in rule_rows)),
        "total_io_mb": round_float(total_io_mb),
        "max_io_mb_s": round_float(max_value(row.get("io_mb_s") for row in benchmark_rows)),
        "total_task_cost": round_float(total_task_cost),
        "median_spot_cost_per_vcpu_hour": round_float(
            median_value(row.get("spot_cost_per_vcpu_hour") for row in benchmark_rows)
        ),
        "unique_partitions": sorted_unique(
            row.get("partition") or row.get("partition_req") for row in list(benchmark_rows) + list(slurm_rows)
        ),
        "unique_instance_types": sorted_unique(row.get("instance_type") for row in benchmark_rows),
        "unique_nodes": sorted_unique(row.get("node") or row.get("hostname") for row in slurm_rows),
        "resource_signal_counts": resource_signal_counts(rule_rows),
        "per_rule": [rule_payload(row) for row in rule_rows],
        "comparison_to_prior": compare_command_to_prior(prior_command, command_metrics=None),
    }
    summary["comparison_to_prior"] = compare_command_to_prior(prior_command, summary)
    return summary


def catalog_command(catalog: RepositoryCatalog, command_id: str) -> Optional[AnalysisCommand]:
    try:
        return catalog.get_command(command_id)
    except KeyError:
        return None


def command_status(benchmark_rows: int, submitted_jobs: int) -> str:
    if benchmark_rows > 0:
        return "benchmarked"
    if submitted_jobs > 0:
        return "submitted_no_benchmark"
    return "no_benchmark_evidence"


def rule_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    resource_counts = resource_signal_counts([row])
    return {
        "rule": str(row.get("rule") or ""),
        "benchmark_rows": to_int(row.get("benchmark_rows")) or 0,
        "submitted_jobs": to_int(row.get("submitted_jobs")) or 0,
        "partition": str(row.get("partition") or ""),
        "threads_req": to_number(row.get("threads_req")),
        "mem_req_mb": to_number(row.get("mem_req_mb")),
        "max_rss_mb": to_number(row.get("max_rss_mb")),
        "p95_rss_mb": to_number(row.get("p95_rss_mb")),
        "max_mem_eff": to_number(row.get("max_mem_eff")),
        "median_wall_s": to_number(row.get("median_wall_s")),
        "p95_wall_s": to_number(row.get("p95_wall_s")),
        "median_cpu_eff": to_number(row.get("median_cpu_eff")),
        "p95_cpu_eff": to_number(row.get("p95_cpu_eff")),
        "total_io_mb": to_number(row.get("total_io_mb")),
        "max_io_mb_s": to_number(row.get("max_io_mb_s")),
        "median_pack_count": to_number(row.get("median_pack_count")),
        "max_pack_count": to_number(row.get("max_pack_count")),
        "median_pack_cpu_frac": to_number(row.get("median_pack_cpu_frac")),
        "median_pack_mem_frac": to_number(row.get("median_pack_mem_frac")),
        "nodes": split_list(row.get("nodes")),
        "instances": split_list(row.get("instances")),
        "total_task_cost": to_number(row.get("total_task_cost")),
        "recommendation": str(row.get("recommendation") or ""),
        "signals": resource_counts,
    }


def resource_signal_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {
        "over_threaded_rule_count": 0,
        "over_memory_rule_count": 0,
        "io_bound_rule_count": 0,
        "tight_packing_rule_count": 0,
    }
    for row in rows:
        recommendation = str(row.get("recommendation") or "").lower()
        if "cpu over-requested" in recommendation or "over-thread" in recommendation:
            counts["over_threaded_rule_count"] += 1
        if "reduce memory" in recommendation or "memory request is conservative" in recommendation:
            counts["over_memory_rule_count"] += 1
        if "i/o heavy" in recommendation or "i/o-bound" in recommendation:
            counts["io_bound_rule_count"] += 1
        if "node packing is tight" in recommendation:
            counts["tight_packing_rule_count"] += 1
    return counts


def compare_command_to_prior(
    prior_command: Optional[Mapping[str, Any]],
    command_metrics: Optional[Mapping[str, Any]],
) -> dict[str, Any]:
    if prior_command is None or command_metrics is None:
        return {"status": "no_prior_profile"}
    comparisons: dict[str, Any] = {}
    for metric in DEFAULT_COMPARATOR_METRICS:
        current = to_float(command_metrics.get(metric))
        prior = to_float(prior_command.get(metric))
        if current is None or prior is None:
            comparisons[metric] = {"status": "missing"}
            continue
        delta = current - prior
        ratio = None if prior == 0 else current / prior
        comparisons[metric] = {
            "current": round_float(current),
            "prior": round_float(prior),
            "delta": round_float(delta),
            "ratio": round_float(ratio),
        }
    return {"status": "compared", "metrics": comparisons}


def prior_command_profile(
    previous_profile: Optional[Mapping[str, Any]],
    command_id: str,
) -> Optional[Mapping[str, Any]]:
    if not previous_profile:
        return None
    commands = previous_profile.get("commands")
    if not isinstance(commands, Mapping):
        return None
    command = commands.get(command_id)
    return command if isinstance(command, Mapping) else None


def latest_prior_profile(
    history: Optional[Mapping[str, Any]],
    dyec_version: str,
) -> Optional[Mapping[str, Any]]:
    if not history:
        return None
    profiles = history.get("dyec_versions")
    if not isinstance(profiles, Mapping):
        return None
    candidates = [
        (version, profile)
        for version, profile in profiles.items()
        if version != dyec_version and isinstance(profile, Mapping)
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda item: version_sort_key(str(item[0])))
    return candidates[-1][1]


def version_sort_key(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for token in str(version).replace("-", ".").split("."):
        try:
            parts.append(int(token))
        except ValueError:
            parts.append(-1)
    return tuple(parts)


def comparator_payload(previous_profile: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    if not previous_profile:
        return {"status": "no_prior_profile"}
    return {
        "status": "prior_profile_found",
        "prior_dyec_version": str(previous_profile.get("dyec_version") or ""),
        "prior_captured_at": str(previous_profile.get("captured_at") or ""),
    }


def load_history(path: Optional[Path]) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"schema_version": PERFORMANCE_HISTORY_SCHEMA, "dyec_versions": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CommandCatalogPerformanceError(f"History JSON is malformed: {path}") from exc
    if not isinstance(payload, dict):
        raise CommandCatalogPerformanceError(f"History JSON must be an object: {path}")
    payload.setdefault("schema_version", PERFORMANCE_HISTORY_SCHEMA)
    payload.setdefault("dyec_versions", {})
    if not isinstance(payload["dyec_versions"], dict):
        raise CommandCatalogPerformanceError("History JSON dyec_versions must be an object.")
    return payload


def write_outputs(
    profile: Mapping[str, Any],
    *,
    output_dir: Path,
    history_json: Optional[Path],
    replace_existing_version: bool,
) -> None:
    history: Optional[dict[str, Any]] = None
    if history_json is not None:
        history = load_history(history_json)
        versions = history["dyec_versions"]
        dyec_version = str(profile["dyec_version"])
        if dyec_version in versions and not replace_existing_version:
            raise CommandCatalogPerformanceError(
                f"History already contains DYEC version {dyec_version}; "
                "pass replace_existing_version to overwrite it."
            )
        versions[dyec_version] = profile
    output_dir.mkdir(parents=True, exist_ok=True)
    profile_path = output_dir / "command_catalog_performance_profile.json"
    summary_path = output_dir / "command_catalog_performance_summary.tsv"
    profile_path.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_summary_tsv(summary_path, profile)
    if history_json is not None and history is not None:
        history_json.parent.mkdir(parents=True, exist_ok=True)
        history_json.write_text(
            json.dumps(history, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def write_summary_tsv(path: Path, profile: Mapping[str, Any]) -> None:
    commands = profile.get("commands")
    if not isinstance(commands, Mapping):
        raise CommandCatalogPerformanceError("Profile commands must be an object.")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=PERFORMANCE_SUMMARY_FIELDS)
        writer.writeheader()
        for command_id in profile.get("command_order", []):
            command = commands.get(command_id)
            if not isinstance(command, Mapping):
                continue
            signals = command.get("resource_signal_counts")
            signal_map = signals if isinstance(signals, Mapping) else {}
            row = {field: command.get(field, "") for field in PERFORMANCE_SUMMARY_FIELDS}
            for field in (
                "over_threaded_rule_count",
                "over_memory_rule_count",
                "io_bound_rule_count",
                "tight_packing_rule_count",
            ):
                row[field] = signal_map.get(field, "")
            row["partitions"] = ",".join(command.get("unique_partitions", []) or [])
            row["instance_types"] = ",".join(command.get("unique_instance_types", []) or [])
            writer.writerow(row)


def source_files_payload(options: CommandCatalogPerformanceOptions) -> dict[str, str]:
    payload = {"benchmark_rows_tsv": str(options.benchmark_rows_tsv)}
    if options.rule_summary_tsv is not None:
        payload["rule_summary_tsv"] = str(options.rule_summary_tsv)
    if options.slurm_jobs_tsv is not None:
        payload["slurm_jobs_tsv"] = str(options.slurm_jobs_tsv)
    if options.catalog_config is not None:
        payload["catalog_config"] = str(options.catalog_config)
    return payload


def cohort_counts(commands: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for command in commands:
        cohort = str(command.get("evidence_cohort") or "unknown")
        counts[cohort] = counts.get(cohort, 0) + 1
    return dict(sorted(counts.items()))


def status_counts(commands: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for command in commands:
        status = str(command.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def totals_payload(commands: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "benchmark_rows": sum_int(command.get("benchmark_rows") for command in commands),
        "submitted_jobs": sum_int(command.get("submitted_jobs") for command in commands),
        "slurm_jobs": sum_int(command.get("slurm_jobs") for command in commands),
        "total_wall_s": round_float(sum_float(command.get("total_wall_s") for command in commands)),
        "allocated_vcpu_hours": round_float(
            sum_float(command.get("allocated_vcpu_hours") for command in commands)
        ),
        "observed_cpu_hours": round_float(
            sum_float(command.get("observed_cpu_hours") for command in commands)
        ),
        "total_task_cost": round_float(
            sum_float(command.get("total_task_cost") for command in commands)
        ),
        "total_io_mb": round_float(sum_float(command.get("total_io_mb") for command in commands)),
    }


def to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"NA", "N/A", "nan", "None"}:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def to_int(value: Any) -> Optional[int]:
    parsed = to_float(value)
    return None if parsed is None else int(parsed)


def to_number(value: Any) -> Optional[int | float]:
    parsed = to_float(value)
    if parsed is None:
        return None
    if parsed.is_integer():
        return int(parsed)
    return round_float(parsed)


def sum_float(values: Any) -> float:
    total = 0.0
    for value in values:
        parsed = to_float(value)
        if parsed is not None:
            total += parsed
    return total


def sum_int(values: Any) -> int:
    total = 0
    for value in values:
        parsed = to_int(value)
        if parsed is not None:
            total += parsed
    return total


def numeric_values(values: Any) -> list[float]:
    result: list[float] = []
    for value in values:
        parsed = to_float(value)
        if parsed is not None:
            result.append(parsed)
    return result


def median_value(values: Any) -> Optional[float]:
    nums = numeric_values(values)
    return statistics.median(nums) if nums else None


def max_value(values: Any) -> Optional[float]:
    nums = numeric_values(values)
    return max(nums) if nums else None


def percentile_value(values: Any, percentile: float = 0.95) -> Optional[float]:
    nums = sorted(numeric_values(values))
    if not nums:
        return None
    if len(nums) == 1:
        return nums[0]
    index = math.ceil(percentile * len(nums)) - 1
    return nums[max(0, min(index, len(nums) - 1))]


def round_float(value: Optional[float], digits: int = 4) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)


def sorted_unique(values: Any) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value or "").strip()})


def split_list(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [item.strip() for item in text.split(",") if item.strip()]


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
