"""Pure builders and parsers for bounded headnode observability commands."""

from __future__ import annotations

import json
import math
import re
import textwrap
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any, Dict


SCHEMA_VERSION = 1
ANALYSIS_RESULTS_ROOT = "/fsx/analysis_results"
FSX_ROOT = "/fsx"
SYSTEM_INFO_MARKER = "__DYEC_HEADNODE_SYSTEM_INFO_V1__="
FSX_USAGE_MARKER = "__DYEC_HEADNODE_FSX_USAGE_V1__="
ANALYSIS_DISCOVERY_MARKER = "__DYEC_ANALYSIS_DISCOVERY_V1__="
BENCHMARK_REPORT_MARKER = "__DYEC_BENCHMARK_REPORT_V1__="

MAX_SSM_STDOUT_BYTES = 20 * 1024
DEFAULT_MAX_OUTPUT_BYTES = MAX_SSM_STDOUT_BYTES
DEFAULT_DISCOVERY_LIMIT = 200
MAX_DISCOVERY_LIMIT = 1000
DEFAULT_DISCOVERY_MAX_DEPTH = 8
MAX_DISCOVERY_DEPTH = 16
DEFAULT_DISCOVERY_MAX_SCANNED_ENTRIES = 10_000
MAX_DISCOVERY_SCANNED_ENTRIES = 100_000
DEFAULT_BENCHMARK_MAX_BYTES = 4 * 1024 * 1024
MAX_BENCHMARK_BYTES = 32 * 1024 * 1024
DEFAULT_BENCHMARK_MAX_ROWS = 10_000
MAX_BENCHMARK_ROWS = 100_000
MAX_BENCHMARK_COLUMNS = 256
MAX_BENCHMARK_COLUMN_CHARS = 128
MAX_BENCHMARK_FIELD_CHARS = 65_536
DEFAULT_BENCHMARK_MAX_GROUPS = 32
MAX_BENCHMARK_GROUPS = 32
MAX_BENCHMARK_GROUP_CHARS = 256
MAX_PATH_CHARS = 4096

DISCOVERY_MODES = frozenset({"direct", "recursive-dayoa"})
BENCHMARK_GENOME_BUILDS = frozenset({"b37", "hg38", "hg38_broad"})
BENCHMARK_GROUP_COLUMN = "rule"
BENCHMARK_NUMERIC_COLUMNS = ("s", "task_cost")
SAFE_PATH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class HeadnodeObservabilityError(RuntimeError):
    """Raised when an observability request or response violates its contract."""


def _positive_int(value: int, *, name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise HeadnodeObservabilityError(f"{name} must be an integer")
    if value < 1 or value > maximum:
        raise HeadnodeObservabilityError(f"{name} must be between 1 and {maximum}")
    return value


def _script(body: str) -> str:
    python_body = textwrap.dedent(body).strip()
    return (
        "set -euo pipefail\n"
        'if [ "$(id -un)" != "ubuntu" ]; then\n'
        '  echo "DYEC headnode observability must run as ubuntu." >&2\n'
        "  exit 64\n"
        "fi\n"
        "python3 - <<'PY'\n"
        f"{python_body}\n"
        "PY\n"
    )


def build_system_info_script() -> str:
    """Return a fixed script that emits bounded, non-secret host facts."""

    return _script(
        f"""
        import datetime
        import importlib.metadata
        import json
        import math
        import os
        import platform
        import shlex
        import shutil
        import socket

        os_release = {{}}
        with open("/etc/os-release", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text or text.startswith("#"):
                    continue
                key, separator, raw = text.partition("=")
                if not separator or key not in {{"ID", "VERSION_ID", "PRETTY_NAME"}}:
                    continue
                values = shlex.split(raw, posix=True)
                if len(values) != 1 or not values[0] or len(values[0]) > 256:
                    raise SystemExit(f"Malformed {{key}} in /etc/os-release")
                if any(ord(character) < 32 for character in values[0]):
                    raise SystemExit(f"Unsafe {{key}} in /etc/os-release")
                os_release[key] = values[0]
        if set(os_release) != {{"ID", "VERSION_ID", "PRETTY_NAME"}}:
            raise SystemExit("Required /etc/os-release fields are unavailable")
        if os_release["ID"] != "ubuntu":
            raise SystemExit("Headnode operating system must be Ubuntu")
        memory_total_kib = None
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                key, separator, raw = line.partition(":")
                if separator and key == "MemTotal":
                    fields = raw.split()
                    if len(fields) != 2 or fields[1] != "kB":
                        raise SystemExit("Malformed MemTotal in /proc/meminfo")
                    memory_total_kib = int(fields[0])
                    break
        if memory_total_kib is None or memory_total_kib < 1:
            raise SystemExit("MemTotal is unavailable in /proc/meminfo")
        cpu_count = os.cpu_count()
        if cpu_count is None or cpu_count < 1:
            raise SystemExit("CPU count is unavailable")
        with open("/proc/uptime", encoding="utf-8") as handle:
            uptime_fields = handle.read(256).split()
        if len(uptime_fields) < 1:
            raise SystemExit("Uptime is unavailable in /proc/uptime")
        uptime = float(uptime_fields[0])
        if not math.isfinite(uptime) or uptime < 0:
            raise SystemExit("Uptime is malformed in /proc/uptime")
        try:
            dyec_version = importlib.metadata.version("daylily-ephemeral-cluster")
        except importlib.metadata.PackageNotFoundError as exc:
            raise SystemExit("Installed DAY-EC package version is unavailable") from exc
        if not dyec_version or len(dyec_version) > 128 or any(
            ord(character) < 32 for character in dyec_version
        ):
            raise SystemExit("Installed DAY-EC package version is malformed")
        day_clone_available = shutil.which("day-clone") is not None
        payload = {{
            "schema_version": {SCHEMA_VERSION},
            "operation": "headnode_system_info",
            "observed_at": datetime.datetime.now(datetime.timezone.utc)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z"),
            "host": {{
                "hostname": socket.gethostname(),
                "os_release": {{
                    "id": os_release["ID"],
                    "version_id": os_release["VERSION_ID"],
                    "pretty_name": os_release["PRETTY_NAME"],
                }},
                "kernel_release": platform.release(),
                "architecture": platform.machine(),
                "uptime_seconds": int(uptime),
                "cpu_count": cpu_count,
                "memory_total_kib": memory_total_kib,
                "dyec_version": dyec_version,
                "day_clone_available": day_clone_available,
                "day_clone_version": None,
                "day_clone_default_ref": None,
            }},
        }}
        output = (
            {SYSTEM_INFO_MARKER!r}
            + json.dumps(payload, sort_keys=True, separators=(",", ":"))
            + "\\n"
        )
        if len(output.encode("utf-8")) > {MAX_SSM_STDOUT_BYTES}:
            raise SystemExit("System-info JSON violates the SSM stdout byte limit")
        print(output, end="")
        """
    )


def build_fsx_usage_script() -> str:
    """Return a fixed script that reports ``df -Pk /fsx`` semantics as JSON."""

    return _script(
        f"""
        import datetime
        import json
        import subprocess

        result = subprocess.run(
            ["df", "-Pk", {FSX_ROOT!r}],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if result.returncode != 0:
            raise SystemExit(result.stderr.strip() or f"df exited {{result.returncode}}")
        lines = result.stdout.strip().splitlines()
        if len(lines) != 2:
            raise SystemExit("df -Pk /fsx returned an unexpected row count")
        fields = lines[1].split()
        if len(fields) != 6:
            raise SystemExit("df -Pk /fsx returned a malformed filesystem row")
        filesystem, size, used, available, use_percent, mountpoint = fields
        if mountpoint != {FSX_ROOT!r}:
            raise SystemExit(f"df resolved unexpected mountpoint: {{mountpoint}}")
        if not use_percent.endswith("%"):
            raise SystemExit("df returned malformed use percent")
        payload = {{
            "schema_version": {SCHEMA_VERSION},
            "operation": "headnode_fsx_usage",
            "observed_at": datetime.datetime.now(datetime.timezone.utc)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z"),
            "filesystem": {{
                "path": {FSX_ROOT!r},
                "filesystem": filesystem,
                "size_kib": int(size),
                "used_kib": int(used),
                "available_kib": int(available),
                "use_percent": int(use_percent[:-1]),
                "mountpoint": mountpoint,
            }},
        }}
        output = (
            {FSX_USAGE_MARKER!r}
            + json.dumps(payload, sort_keys=True, separators=(",", ":"))
            + "\\n"
        )
        if len(output.encode("utf-8")) > {MAX_SSM_STDOUT_BYTES}:
            raise SystemExit("FSx-usage JSON violates the SSM stdout byte limit")
        print(output, end="")
        """
    )


def build_analysis_discovery_script(
    mode: str,
    *,
    max_results: int = DEFAULT_DISCOVERY_LIMIT,
    max_depth: int = DEFAULT_DISCOVERY_MAX_DEPTH,
    max_scanned_entries: int = DEFAULT_DISCOVERY_MAX_SCANNED_ENTRIES,
) -> str:
    """Build a fixed-root, deterministic and bounded analysis discovery script."""

    if mode not in DISCOVERY_MODES:
        allowed = ", ".join(sorted(DISCOVERY_MODES))
        raise HeadnodeObservabilityError(f"mode must be one of: {allowed}")
    resolved_limit = _positive_int(
        max_results,
        name="max_results",
        maximum=MAX_DISCOVERY_LIMIT,
    )
    resolved_depth = _positive_int(
        max_depth,
        name="max_depth",
        maximum=MAX_DISCOVERY_DEPTH,
    )
    resolved_scanned = _positive_int(
        max_scanned_entries,
        name="max_scanned_entries",
        maximum=MAX_DISCOVERY_SCANNED_ENTRIES,
    )
    return _script(
        f"""
        import datetime
        import json
        import os
        import re
        from pathlib import Path

        root = Path({ANALYSIS_RESULTS_ROOT!r})
        mode = {mode!r}
        max_results = {resolved_limit}
        max_depth = {resolved_depth}
        max_scanned_entries = {resolved_scanned}
        if not root.is_dir() or root.is_symlink():
            raise SystemExit("Analysis-results root does not exist: /fsx/analysis_results")

        found = []
        scanned_entries = 0

        def bounded_children(parent):
            global scanned_entries
            children = []
            with os.scandir(parent) as entries:
                for entry in entries:
                    scanned_entries += 1
                    if scanned_entries > max_scanned_entries:
                        raise SystemExit("Analysis discovery violates the scanned-entry limit")
                    if entry.is_dir(follow_symlinks=False):
                        children.append(Path(entry.path))
            return sorted(children, key=lambda path: path.name)

        def add_dayoa_root(dayoa_root):
            analysis_root = dayoa_root.parent
            relative_parts = analysis_root.relative_to(root).parts
            if not relative_parts or any(
                re.fullmatch(r"[A-Za-z0-9_.-]+", part) is None for part in relative_parts
            ):
                raise SystemExit("Discovered analysis path contains an unsafe segment")
            for path in (analysis_root, dayoa_root):
                text = str(path)
                if len(text) > {MAX_PATH_CHARS}:
                    raise SystemExit("Discovered analysis path exceeds the path limit")
            found.append({{
                "analysis_root": str(analysis_root),
                "dayoa_root": str(dayoa_root),
                "relative_path": str(analysis_root.relative_to(root)),
            }})

        if mode == "direct":
            stop = False
            for owner in bounded_children(root):
                for analysis_root in bounded_children(owner):
                    dayoa_root = analysis_root / "daylily-omics-analysis"
                    if dayoa_root.is_dir() and not dayoa_root.is_symlink():
                        add_dayoa_root(dayoa_root)
                        if len(found) > max_results:
                            stop = True
                            break
                if stop:
                    break
        else:
            pending = [(root, 0)]
            while pending:
                current_path, depth = pending.pop()
                children = bounded_children(current_path)
                dayoa_roots = [path for path in children if path.name == "daylily-omics-analysis"]
                if dayoa_roots:
                    add_dayoa_root(dayoa_roots[0])
                    if len(found) > max_results:
                        break
                if depth < max_depth:
                    descendants = [
                        path for path in children if path.name != "daylily-omics-analysis"
                    ]
                    pending.extend((path, depth + 1) for path in reversed(descendants))

        truncated = len(found) > max_results
        payload = {{
            "schema_version": {SCHEMA_VERSION},
            "operation": "analysis_discovery",
            "observed_at": datetime.datetime.now(datetime.timezone.utc)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z"),
            "root": str(root),
            "mode": mode,
            "max_results": max_results,
            "max_depth": max_depth,
            "max_scanned_entries": max_scanned_entries,
            "scanned_entries": scanned_entries,
            "truncated": truncated,
            "analyses": found[:max_results],
        }}
        output = (
            {ANALYSIS_DISCOVERY_MARKER!r}
            + json.dumps(payload, sort_keys=True, separators=(",", ":"))
            + "\\n"
        )
        if len(output.encode("utf-8")) > {MAX_SSM_STDOUT_BYTES}:
            raise SystemExit("Analysis-discovery JSON violates the SSM stdout byte limit")
        print(output, end="")
        """
    )


def validate_analysis_root(analysis_root: str) -> str:
    """Validate an exact ``/fsx/analysis_results/<owner>/<analysis>`` path."""

    raw = str(analysis_root or "").strip().rstrip("/")
    if not raw or len(raw) > MAX_PATH_CHARS:
        raise HeadnodeObservabilityError("analysis_root is required and must fit the path limit")
    if any(character in raw for character in ("\x00", "\n", "\r")):
        raise HeadnodeObservabilityError("analysis_root must be one POSIX path")
    path = PurePosixPath(raw)
    if path.parts[:3] != ("/", "fsx", "analysis_results") or len(path.parts) != 5:
        raise HeadnodeObservabilityError(
            "analysis_root must be /fsx/analysis_results/<owner>/<analysis_id>"
        )
    for segment in path.parts[3:]:
        if segment in {".", ".."} or SAFE_PATH_SEGMENT_RE.fullmatch(segment) is None:
            raise HeadnodeObservabilityError("analysis_root owner and analysis_id are unsafe")
    return path.as_posix()


def validate_genome_build(genome_build: str) -> str:
    """Validate one supported DayOA benchmark genome build."""

    resolved = str(genome_build or "").strip()
    if resolved not in BENCHMARK_GENOME_BUILDS:
        allowed = ", ".join(sorted(BENCHMARK_GENOME_BUILDS))
        raise HeadnodeObservabilityError(f"genome_build must be one of: {allowed}")
    return resolved


def _validate_discovered_analysis_root(raw: str, *, mode: str, max_depth: int) -> str:
    path = PurePosixPath(str(raw or ""))
    if path.parts[:3] != ("/", "fsx", "analysis_results"):
        raise HeadnodeObservabilityError("analysis-discovery path is outside its fixed root")
    relative = path.parts[3:]
    if not relative or len(relative) > max_depth:
        raise HeadnodeObservabilityError("analysis-discovery path violates its depth limit")
    if mode == "direct" and len(relative) != 2:
        raise HeadnodeObservabilityError("direct analysis-discovery path is not owner/analysis")
    if any(SAFE_PATH_SEGMENT_RE.fullmatch(segment) is None for segment in relative):
        raise HeadnodeObservabilityError("analysis_root owner and analysis_id are unsafe")
    return path.as_posix()


def build_benchmark_report_script(
    analysis_root: str,
    genome_build: str,
    *,
    max_bytes: int = DEFAULT_BENCHMARK_MAX_BYTES,
    max_rows: int = DEFAULT_BENCHMARK_MAX_ROWS,
    max_groups: int = DEFAULT_BENCHMARK_MAX_GROUPS,
) -> str:
    """Build a bounded aggregate report for one canonical benchmark summary TSV.

    The exact grouping column is ``rule``. The required numeric fields are
    ``s`` and ``task_cost``; aliases and fallback names are unsupported.
    """

    resolved_root = validate_analysis_root(analysis_root)
    resolved_build = validate_genome_build(genome_build)
    resolved_max_bytes = _positive_int(
        max_bytes,
        name="max_bytes",
        maximum=MAX_BENCHMARK_BYTES,
    )
    resolved_max_rows = _positive_int(
        max_rows,
        name="max_rows",
        maximum=MAX_BENCHMARK_ROWS,
    )
    resolved_max_groups = _positive_int(
        max_groups,
        name="max_groups",
        maximum=MAX_BENCHMARK_GROUPS,
    )
    summary_path = (
        PurePosixPath(resolved_root)
        / "daylily-omics-analysis"
        / "results"
        / "day"
        / resolved_build
        / "reports"
        / "benchmarks_summary.tsv"
    ).as_posix()
    return _script(
        f"""
        import csv
        import datetime
        import json
        import math
        import statistics
        from pathlib import Path

        analysis_root = Path({resolved_root!r})
        genome_build = {resolved_build!r}
        summary_path = Path({summary_path!r})
        max_bytes = {resolved_max_bytes}
        max_rows = {resolved_max_rows}
        max_groups = {resolved_max_groups}
        directory_chain = [
            Path("/fsx"),
            Path("/fsx/analysis_results"),
            analysis_root.parent,
            analysis_root,
            analysis_root / "daylily-omics-analysis",
            analysis_root / "daylily-omics-analysis" / "results",
            analysis_root / "daylily-omics-analysis" / "results" / "day",
            analysis_root / "daylily-omics-analysis" / "results" / "day" / genome_build,
            analysis_root
            / "daylily-omics-analysis"
            / "results"
            / "day"
            / genome_build
            / "reports",
        ]
        for path in directory_chain:
            if not path.is_dir() or path.is_symlink():
                raise SystemExit("Benchmark canonical path contains a missing or symlink directory")
        if not summary_path.is_file() or summary_path.is_symlink():
            raise SystemExit("Benchmark summary TSV is missing or not a regular file")
        size_bytes = summary_path.stat().st_size
        if size_bytes < 1 or size_bytes > max_bytes:
            raise SystemExit("Benchmark summary TSV violates the byte limit")
        with summary_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle, delimiter="\\t")
            columns = reader.fieldnames
            if not columns or len(columns) > {MAX_BENCHMARK_COLUMNS}:
                raise SystemExit("Benchmark summary TSV has an invalid column count")
            if any(
                not column
                or column != column.strip()
                or len(column) > {MAX_BENCHMARK_COLUMN_CHARS}
                for column in columns
            ):
                raise SystemExit("Benchmark summary TSV has a blank or non-canonical column")
            if len(set(columns)) != len(columns):
                raise SystemExit("Benchmark summary TSV has duplicate columns")
            required_columns = {{{BENCHMARK_GROUP_COLUMN!r}, *{BENCHMARK_NUMERIC_COLUMNS!r}}}
            missing_columns = sorted(required_columns - set(columns))
            if missing_columns:
                raise SystemExit(
                    "Benchmark summary TSV is missing required columns: "
                    + ",".join(missing_columns)
                )
            numeric_columns = list({BENCHMARK_NUMERIC_COLUMNS!r})
            grouped = {{}}
            grouped_row_counts = {{}}
            row_count = 0
            for row_number, row in enumerate(reader, start=1):
                if row_number > max_rows:
                    raise SystemExit("Benchmark summary TSV violates the row limit")
                if None in row or any(row.get(column) is None for column in columns):
                    raise SystemExit("Benchmark summary TSV contains a malformed-width row")
                normalized = {{column: str(row.get(column) or "") for column in columns}}
                if any(len(value) > {MAX_BENCHMARK_FIELD_CHARS} for value in normalized.values()):
                    raise SystemExit("Benchmark summary TSV contains an oversized field")
                group = normalized[{BENCHMARK_GROUP_COLUMN!r}]
                if not group or group != group.strip() or len(group) > {MAX_BENCHMARK_GROUP_CHARS}:
                    raise SystemExit("Benchmark summary TSV contains an invalid rule value")
                if group not in grouped:
                    if len(grouped) >= max_groups:
                        raise SystemExit("Benchmark summary TSV exceeds the unique-rule group limit")
                    grouped[group] = {{column: [] for column in numeric_columns}}
                    grouped_row_counts[group] = 0
                for column in numeric_columns:
                    raw = normalized[column]
                    if not raw:
                        raise SystemExit(
                            f"Benchmark summary TSV has an empty {{column}} value"
                        )
                    try:
                        value = float(raw)
                    except ValueError as exc:
                        raise SystemExit(
                            f"Benchmark summary TSV has a nonnumeric {{column}} value"
                        ) from exc
                    if not math.isfinite(value):
                        raise SystemExit(
                            f"Benchmark summary TSV has a nonfinite {{column}} value"
                        )
                    grouped[group][column].append(value)
                grouped_row_counts[group] += 1
                row_count += 1
        if row_count < 1:
            raise SystemExit("Benchmark summary TSV contains no data rows")
        groups = []
        for group in sorted(grouped):
            metrics = {{}}
            for column in numeric_columns:
                values = grouped[group][column]
                metrics[column] = {{
                    "value_count": len(values),
                    "total": math.fsum(values),
                    "mean": statistics.fmean(values) if values else None,
                    "median": statistics.median(values) if values else None,
                }}
            groups.append({{
                "rule": group,
                "row_count": grouped_row_counts[group],
                "metrics": metrics,
            }})
        payload = {{
            "schema_version": {SCHEMA_VERSION},
            "operation": "benchmark_report",
            "observed_at": datetime.datetime.now(datetime.timezone.utc)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z"),
            "analysis_root": str(analysis_root),
            "genome_build": genome_build,
            "summary_tsv": str(summary_path),
            "source": {{
                "bytes": size_bytes,
                "columns": columns,
                "row_count": row_count,
            }},
            "group_by": {BENCHMARK_GROUP_COLUMN!r},
            "numeric_columns": numeric_columns,
            "group_count": len(groups),
            "max_rows": max_rows,
            "max_bytes": max_bytes,
            "max_groups": max_groups,
            "truncated": False,
            "groups": groups,
        }}
        output = (
            {BENCHMARK_REPORT_MARKER!r}
            + json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
            + "\\n"
        )
        if len(output.encode("utf-8")) > {MAX_SSM_STDOUT_BYTES}:
            raise SystemExit("Benchmark JSON violates the SSM stdout byte limit")
        print(output, end="")
        """
    )


def _parse_marker_payload(
    stdout: str,
    *,
    marker: str,
    operation: str,
    max_output_bytes: int,
) -> Dict[str, Any]:
    resolved_max = _positive_int(
        max_output_bytes,
        name="max_output_bytes",
        maximum=DEFAULT_MAX_OUTPUT_BYTES,
    )
    if len(stdout.encode("utf-8")) > resolved_max:
        raise HeadnodeObservabilityError("observability output exceeds the byte limit")
    marked = [line[len(marker) :] for line in stdout.splitlines() if line.startswith(marker)]
    if len(marked) != 1:
        raise HeadnodeObservabilityError("observability output must contain exactly one marker")
    try:
        payload = json.loads(marked[0])
    except json.JSONDecodeError as exc:
        raise HeadnodeObservabilityError("observability marker contains malformed JSON") from exc
    if not isinstance(payload, dict):
        raise HeadnodeObservabilityError("observability payload must be a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise HeadnodeObservabilityError("observability payload has an unsupported schema_version")
    if payload.get("operation") != operation:
        raise HeadnodeObservabilityError(
            "observability payload operation does not match its marker"
        )
    observed_at = payload.get("observed_at")
    if not isinstance(observed_at, str) or not observed_at.endswith("Z"):
        raise HeadnodeObservabilityError("observability payload has an invalid observed_at")
    try:
        datetime.fromisoformat(observed_at.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise HeadnodeObservabilityError(
            "observability payload has an invalid observed_at"
        ) from exc
    return payload


def parse_system_info_output(
    stdout: str,
    *,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> Dict[str, Any]:
    payload = _parse_marker_payload(
        stdout,
        marker=SYSTEM_INFO_MARKER,
        operation="headnode_system_info",
        max_output_bytes=max_output_bytes,
    )
    if set(payload) != {"schema_version", "operation", "observed_at", "host"}:
        raise HeadnodeObservabilityError("system-info payload fields are invalid")
    host = payload.get("host")
    if not isinstance(host, dict):
        raise HeadnodeObservabilityError("system-info payload is missing host")
    expected_host_keys = {
        "hostname",
        "os_release",
        "kernel_release",
        "architecture",
        "uptime_seconds",
        "cpu_count",
        "memory_total_kib",
        "dyec_version",
        "day_clone_available",
        "day_clone_version",
        "day_clone_default_ref",
    }
    if set(host) != expected_host_keys:
        raise HeadnodeObservabilityError("system-info host fields are invalid")
    for key in ("hostname", "kernel_release", "architecture", "dyec_version"):
        value = host.get(key)
        if (
            not isinstance(value, str)
            or not value
            or len(value) > 256
            or any(ord(character) < 32 for character in value)
        ):
            raise HeadnodeObservabilityError(f"system-info host.{key} is invalid")
    os_release = host.get("os_release")
    if not isinstance(os_release, dict) or set(os_release) != {
        "id",
        "version_id",
        "pretty_name",
    }:
        raise HeadnodeObservabilityError("system-info host.os_release is invalid")
    for key in ("id", "version_id", "pretty_name"):
        value = os_release.get(key)
        if (
            not isinstance(value, str)
            or not value
            or len(value) > 256
            or any(ord(character) < 32 for character in value)
        ):
            raise HeadnodeObservabilityError(f"system-info host.os_release.{key} is invalid")
    if os_release["id"] != "ubuntu":
        raise HeadnodeObservabilityError("system-info host operating system is not Ubuntu")
    for key in ("cpu_count", "memory_total_kib"):
        if isinstance(host.get(key), bool) or not isinstance(host.get(key), int) or host[key] < 1:
            raise HeadnodeObservabilityError(f"system-info host.{key} is invalid")
    uptime = host.get("uptime_seconds")
    if isinstance(uptime, bool) or not isinstance(uptime, int) or uptime < 0:
        raise HeadnodeObservabilityError("system-info host.uptime_seconds is invalid")
    if not isinstance(host.get("day_clone_available"), bool):
        raise HeadnodeObservabilityError("system-info host.day_clone_available is invalid")
    for key in ("day_clone_version", "day_clone_default_ref"):
        value = host.get(key)
        if value is not None and (
            not isinstance(value, str)
            or not value
            or len(value) > 128
            or value.startswith("/")
            or any(ord(character) < 32 for character in value)
        ):
            raise HeadnodeObservabilityError(f"system-info host.{key} is invalid")
    if not host["day_clone_available"] and (
        host["day_clone_version"] is not None or host["day_clone_default_ref"] is not None
    ):
        raise HeadnodeObservabilityError("system-info unavailable day-clone cannot expose metadata")
    return payload


def parse_fsx_usage_output(
    stdout: str,
    *,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> Dict[str, Any]:
    payload = _parse_marker_payload(
        stdout,
        marker=FSX_USAGE_MARKER,
        operation="headnode_fsx_usage",
        max_output_bytes=max_output_bytes,
    )
    filesystem = payload.get("filesystem")
    if not isinstance(filesystem, dict):
        raise HeadnodeObservabilityError("FSx payload is missing filesystem")
    if filesystem.get("path") != FSX_ROOT or filesystem.get("mountpoint") != FSX_ROOT:
        raise HeadnodeObservabilityError("FSx payload does not describe /fsx")
    if not isinstance(filesystem.get("filesystem"), str) or not filesystem["filesystem"]:
        raise HeadnodeObservabilityError("FSx payload has an invalid filesystem source")
    for key in ("size_kib", "used_kib", "available_kib", "use_percent"):
        value = filesystem.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise HeadnodeObservabilityError(f"FSx payload filesystem.{key} is invalid")
    if filesystem["use_percent"] > 100:
        raise HeadnodeObservabilityError("FSx payload use_percent exceeds 100")
    return payload


def parse_analysis_discovery_output(
    stdout: str,
    *,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> Dict[str, Any]:
    payload = _parse_marker_payload(
        stdout,
        marker=ANALYSIS_DISCOVERY_MARKER,
        operation="analysis_discovery",
        max_output_bytes=max_output_bytes,
    )
    if payload.get("root") != ANALYSIS_RESULTS_ROOT or payload.get("mode") not in DISCOVERY_MODES:
        raise HeadnodeObservabilityError("analysis-discovery scope is invalid")
    limit = payload.get("max_results")
    depth = payload.get("max_depth")
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= MAX_DISCOVERY_LIMIT
    ):
        raise HeadnodeObservabilityError("analysis-discovery max_results is invalid")
    if (
        isinstance(depth, bool)
        or not isinstance(depth, int)
        or not 1 <= depth <= MAX_DISCOVERY_DEPTH
    ):
        raise HeadnodeObservabilityError("analysis-discovery max_depth is invalid")
    scanned_limit = payload.get("max_scanned_entries")
    scanned = payload.get("scanned_entries")
    if (
        isinstance(scanned_limit, bool)
        or not isinstance(scanned_limit, int)
        or not 1 <= scanned_limit <= MAX_DISCOVERY_SCANNED_ENTRIES
        or isinstance(scanned, bool)
        or not isinstance(scanned, int)
        or not 0 <= scanned <= scanned_limit
    ):
        raise HeadnodeObservabilityError("analysis-discovery scan accounting is invalid")
    analyses = payload.get("analyses")
    if not isinstance(analyses, list) or len(analyses) > limit:
        raise HeadnodeObservabilityError("analysis-discovery list violates its limit")
    if not isinstance(payload.get("truncated"), bool):
        raise HeadnodeObservabilityError("analysis-discovery truncated flag is invalid")
    for item in analyses:
        if not isinstance(item, dict):
            raise HeadnodeObservabilityError("analysis-discovery item must be an object")
        root = _validate_discovered_analysis_root(
            str(item.get("analysis_root") or ""),
            mode=str(payload["mode"]),
            max_depth=depth,
        )
        if item.get("dayoa_root") != f"{root}/daylily-omics-analysis":
            raise HeadnodeObservabilityError("analysis-discovery DayOA path is invalid")
        expected_relative = str(PurePosixPath(root).relative_to(ANALYSIS_RESULTS_ROOT))
        if item.get("relative_path") != expected_relative:
            raise HeadnodeObservabilityError("analysis-discovery relative path is invalid")
    return payload


def parse_benchmark_report_output(
    stdout: str,
    *,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> Dict[str, Any]:
    payload = _parse_marker_payload(
        stdout,
        marker=BENCHMARK_REPORT_MARKER,
        operation="benchmark_report",
        max_output_bytes=max_output_bytes,
    )
    expected_payload_keys = {
        "schema_version",
        "operation",
        "observed_at",
        "analysis_root",
        "genome_build",
        "summary_tsv",
        "source",
        "group_by",
        "numeric_columns",
        "group_count",
        "max_rows",
        "max_bytes",
        "max_groups",
        "truncated",
        "groups",
    }
    if set(payload) != expected_payload_keys:
        raise HeadnodeObservabilityError("benchmark-report fields are invalid")
    root = validate_analysis_root(str(payload.get("analysis_root") or ""))
    build = validate_genome_build(str(payload.get("genome_build") or ""))
    expected = f"{root}/daylily-omics-analysis/results/day/{build}/reports/benchmarks_summary.tsv"
    if payload.get("summary_tsv") != expected:
        raise HeadnodeObservabilityError("benchmark-report summary path is invalid")
    source = payload.get("source")
    if not isinstance(source, dict) or set(source) != {"bytes", "columns", "row_count"}:
        raise HeadnodeObservabilityError("benchmark-report source metadata is invalid")
    columns = source.get("columns")
    row_count = source.get("row_count")
    max_rows = payload.get("max_rows")
    if not isinstance(columns, list) or not columns or len(columns) > MAX_BENCHMARK_COLUMNS:
        raise HeadnodeObservabilityError("benchmark-report columns are invalid")
    if any(
        not isinstance(column, str)
        or not column
        or column != column.strip()
        or len(column) > MAX_BENCHMARK_COLUMN_CHARS
        for column in columns
    ):
        raise HeadnodeObservabilityError("benchmark-report column name is invalid")
    if len(set(columns)) != len(columns):
        raise HeadnodeObservabilityError("benchmark-report columns are duplicated")
    required_columns = {BENCHMARK_GROUP_COLUMN, *BENCHMARK_NUMERIC_COLUMNS}
    if not required_columns.issubset(columns):
        raise HeadnodeObservabilityError("benchmark-report required columns are missing")
    if (
        isinstance(max_rows, bool)
        or not isinstance(max_rows, int)
        or not 1 <= max_rows <= MAX_BENCHMARK_ROWS
    ):
        raise HeadnodeObservabilityError("benchmark-report max_rows is invalid")
    if (
        isinstance(row_count, bool)
        or not isinstance(row_count, int)
        or not 1 <= row_count <= max_rows
    ):
        raise HeadnodeObservabilityError("benchmark-report row count is invalid")
    size_bytes = source.get("bytes")
    if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 1:
        raise HeadnodeObservabilityError("benchmark-report byte count is invalid")
    max_bytes = payload.get("max_bytes")
    if (
        isinstance(max_bytes, bool)
        or not isinstance(max_bytes, int)
        or not 1 <= max_bytes <= MAX_BENCHMARK_BYTES
        or size_bytes > max_bytes
    ):
        raise HeadnodeObservabilityError("benchmark-report bytes violate their limit")
    if payload.get("group_by") != BENCHMARK_GROUP_COLUMN:
        raise HeadnodeObservabilityError("benchmark-report grouping column is invalid")
    if payload.get("numeric_columns") != list(BENCHMARK_NUMERIC_COLUMNS):
        raise HeadnodeObservabilityError("benchmark-report numeric columns are invalid")
    max_groups = payload.get("max_groups")
    if (
        isinstance(max_groups, bool)
        or not isinstance(max_groups, int)
        or not 1 <= max_groups <= MAX_BENCHMARK_GROUPS
    ):
        raise HeadnodeObservabilityError("benchmark-report max_groups is invalid")
    if payload.get("truncated") is not False:
        raise HeadnodeObservabilityError("benchmark-report truncated state is invalid")
    groups = payload.get("groups")
    group_count = payload.get("group_count")
    if (
        not isinstance(groups, list)
        or isinstance(group_count, bool)
        or not isinstance(group_count, int)
        or not 1 <= group_count <= max_groups
        or group_count != len(groups)
    ):
        raise HeadnodeObservabilityError("benchmark-report group count is invalid")
    group_names = []
    counted_rows = 0
    for group in groups:
        if not isinstance(group, dict) or set(group) != {"rule", "row_count", "metrics"}:
            raise HeadnodeObservabilityError("benchmark-report group fields are invalid")
        rule = group.get("rule")
        if (
            not isinstance(rule, str)
            or not rule
            or rule != rule.strip()
            or len(rule) > MAX_BENCHMARK_GROUP_CHARS
        ):
            raise HeadnodeObservabilityError("benchmark-report rule is invalid")
        rows_in_group = group.get("row_count")
        if (
            isinstance(rows_in_group, bool)
            or not isinstance(rows_in_group, int)
            or rows_in_group < 1
        ):
            raise HeadnodeObservabilityError("benchmark-report group row_count is invalid")
        metrics = group.get("metrics")
        if not isinstance(metrics, dict) or set(metrics) != set(BENCHMARK_NUMERIC_COLUMNS):
            raise HeadnodeObservabilityError("benchmark-report group metrics are invalid")
        for column in BENCHMARK_NUMERIC_COLUMNS:
            metric = metrics[column]
            if not isinstance(metric, dict) or set(metric) != {
                "value_count",
                "total",
                "mean",
                "median",
            }:
                raise HeadnodeObservabilityError("benchmark-report metric fields are invalid")
            if metric.get("value_count") != rows_in_group:
                raise HeadnodeObservabilityError("benchmark-report metric count is invalid")
            for statistic in ("total", "mean", "median"):
                value = metric.get(statistic)
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                ):
                    raise HeadnodeObservabilityError(
                        f"benchmark-report {column}.{statistic} is invalid"
                    )
        group_names.append(rule)
        counted_rows += rows_in_group
    if group_names != sorted(set(group_names)):
        raise HeadnodeObservabilityError("benchmark-report groups are not unique and sorted")
    if counted_rows != row_count:
        raise HeadnodeObservabilityError("benchmark-report grouped rows do not match source")
    return payload
