"""Spot-price log collection and CSV rendering."""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any, Iterable


DEFAULT_SPOT_LOG_PATHS = ("/fsx/logs", "/fsx/scratch", "/fsx/tmp")
DEFAULT_SPOT_LOG_NAME_GLOBS = ("*.log",)
SPOT_PRICE_LOG_JSON_BEGIN = "__DYEC_SPOT_PRICE_LOGS_JSON_BEGIN__"
SPOT_PRICE_LOG_JSON_END = "__DYEC_SPOT_PRICE_LOGS_JSON_END__"

SPOT_PRICE_LOG_COLUMNS = (
    "cluster",
    "headnode_instance_id",
    "source_path",
    "line_number",
    "recorded_at",
    "region",
    "availability_zone",
    "instance_type",
    "spot_price_usd_per_hour",
    "node_type",
    "slurm_partition",
    "compute_resource",
    "hostname",
    "instance_id",
    "raw_line",
)

_OLD_SPOT_LINE_RE = re.compile(
    r"^(?P<recorded_at>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - "
    r"Region: (?P<region>[^,]+), "
    r"AZ: (?P<availability_zone>[^,]+), "
    r"Instance type: (?P<instance_type>[^,]+), "
    r"Spot price: (?P<spot_price_usd_per_hour>\S+) USD/hour$"
)

_CONTEXT_SPOT_LINE_RE = re.compile(
    r"^(?P<recorded_at>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - "
    r"Node type: (?P<node_type>[^,]*), "
    r"(?:Partition|Queue): (?P<slurm_partition>[^,]*), "
    r"Compute resource: (?P<compute_resource>[^,]*), "
    r"Hostname: (?P<hostname>[^,]*), "
    r"Instance id: (?P<instance_id>[^,]*), "
    r"Region: (?P<region>[^,]+), "
    r"AZ: (?P<availability_zone>[^,]+), "
    r"Instance type: (?P<instance_type>[^,]+), "
    r"Spot price: (?P<spot_price_usd_per_hour>\S+) USD/hour$"
)


def parse_spot_price_log_line(
    line: str,
    *,
    source_path: str = "",
    line_number: int | str = "",
    cluster: str = "",
    headnode_instance_id: str = "",
) -> dict[str, str] | None:
    """Parse a single spot-price log line.

    Returns ``None`` when the line is unrelated to spot pricing.
    Raises ``ValueError`` when the line mentions spot pricing but does not
    match one of the supported exact formats.
    """

    raw_line = line.rstrip("\n")
    if "Spot price:" not in raw_line:
        return None

    match = _CONTEXT_SPOT_LINE_RE.match(raw_line) or _OLD_SPOT_LINE_RE.match(raw_line)
    if not match:
        raise ValueError(f"Malformed spot price log line: {raw_line}")

    parsed = {key: (value or "").strip() for key, value in match.groupdict().items()}
    row = {column: "" for column in SPOT_PRICE_LOG_COLUMNS}
    row.update(parsed)
    row.update(
        {
            "cluster": cluster,
            "headnode_instance_id": headnode_instance_id,
            "source_path": str(source_path),
            "line_number": str(line_number),
            "raw_line": raw_line,
        }
    )
    return row


def normalize_spot_price_rows(
    rows: Iterable[dict[str, Any]],
    *,
    cluster: str,
    headnode_instance_id: str,
) -> list[dict[str, str]]:
    """Normalize remote scan rows to the public CSV schema."""

    normalized: list[dict[str, str]] = []
    for source in rows:
        row = {column: "" for column in SPOT_PRICE_LOG_COLUMNS}
        for column in SPOT_PRICE_LOG_COLUMNS:
            if column in source and source[column] is not None:
                row[column] = str(source[column])
        row["cluster"] = cluster
        row["headnode_instance_id"] = headnode_instance_id
        normalized.append(row)
    return normalized


def spot_price_rows_to_csv(rows: Iterable[dict[str, Any]]) -> str:
    """Render normalized rows as CSV text."""

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(SPOT_PRICE_LOG_COLUMNS),
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in SPOT_PRICE_LOG_COLUMNS})
    return buffer.getvalue()


def build_remote_spot_price_log_script(
    *,
    paths: Iterable[str] = DEFAULT_SPOT_LOG_PATHS,
    name_globs: Iterable[str] = DEFAULT_SPOT_LOG_NAME_GLOBS,
) -> str:
    """Build a Python scanner to run on the head node through SSM."""

    path_list = [str(path) for path in paths]
    glob_list = [str(pattern) for pattern in name_globs]
    if not path_list:
        raise ValueError("At least one remote path is required")
    if not glob_list:
        raise ValueError("At least one file-name glob is required")

    return (
        "set -euo pipefail\n"
        f"printf '%s\\n' {SPOT_PRICE_LOG_JSON_BEGIN!r}\n"
        "python3 - <<'PY'\n"
        "import fnmatch\n"
        "import json\n"
        "import os\n"
        "import re\n"
        "import sys\n"
        f"roots = {json.dumps(path_list)}\n"
        f"name_globs = {json.dumps(glob_list)}\n"
        "old_re = re.compile(r'^(?P<recorded_at>\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}) - Region: (?P<region>[^,]+), AZ: (?P<availability_zone>[^,]+), Instance type: (?P<instance_type>[^,]+), Spot price: (?P<spot_price_usd_per_hour>\\S+) USD/hour$')\n"
        "context_re = re.compile(r'^(?P<recorded_at>\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}) - Node type: (?P<node_type>[^,]*), (?:Partition|Queue): (?P<slurm_partition>[^,]*), Compute resource: (?P<compute_resource>[^,]*), Hostname: (?P<hostname>[^,]*), Instance id: (?P<instance_id>[^,]*), Region: (?P<region>[^,]+), AZ: (?P<availability_zone>[^,]+), Instance type: (?P<instance_type>[^,]+), Spot price: (?P<spot_price_usd_per_hour>\\S+) USD/hour$')\n"
        "columns = "
        + json.dumps(
            [
                column
                for column in SPOT_PRICE_LOG_COLUMNS
                if column not in {"cluster", "headnode_instance_id"}
            ]
        )
        + "\n"
        "def name_allowed(name):\n"
        "    return any(fnmatch.fnmatch(name, pattern) for pattern in name_globs)\n"
        "def parse_line(path, line_number, line):\n"
        "    raw_line = line.rstrip('\\n')\n"
        "    if 'Spot price:' not in raw_line:\n"
        "        return None\n"
        "    match = context_re.match(raw_line) or old_re.match(raw_line)\n"
        "    if not match:\n"
        "        raise ValueError('%s:%s malformed spot price log line: %s' % (path, line_number, raw_line))\n"
        "    row = dict((column, '') for column in columns)\n"
        "    row.update(dict((key, (value or '').strip()) for key, value in match.groupdict().items()))\n"
        "    row['source_path'] = path\n"
        "    row['line_number'] = str(line_number)\n"
        "    row['raw_line'] = raw_line\n"
        "    return row\n"
        "rows = []\n"
        "visited_files = 0\n"
        "for root in roots:\n"
        "    if not os.path.isdir(root):\n"
        "        continue\n"
        "    for dirpath, dirnames, filenames in os.walk(root):\n"
        "        dirnames[:] = sorted(name for name in dirnames if name not in {'.snapshot', '.snapshots'})\n"
        "        for filename in sorted(filenames):\n"
        "            if not name_allowed(filename):\n"
        "                continue\n"
        "            path = os.path.join(dirpath, filename)\n"
        "            visited_files += 1\n"
        "            try:\n"
        "                with open(path, 'r', encoding='utf-8', errors='replace') as handle:\n"
        "                    for line_number, line in enumerate(handle, 1):\n"
        "                        row = parse_line(path, line_number, line)\n"
        "                        if row is not None:\n"
        "                            rows.append(row)\n"
        "            except OSError as exc:\n"
        "                raise SystemExit('ERROR: failed reading %s: %s' % (path, exc))\n"
        "rows.sort(key=lambda row: (row.get('recorded_at', ''), row.get('source_path', ''), int(row.get('line_number') or 0)))\n"
        "print(json.dumps({'rows': rows, 'paths': roots, 'name_globs': name_globs, 'visited_files': visited_files}, sort_keys=True))\n"
        "PY\n"
        f"printf '%s\\n' {SPOT_PRICE_LOG_JSON_END!r}\n"
    )


def extract_remote_spot_price_payload(stdout: str) -> dict[str, Any]:
    """Extract the scanner JSON payload from SSM stdout."""

    lines = stdout.splitlines()
    try:
        start = lines.index(SPOT_PRICE_LOG_JSON_BEGIN)
        end = lines.index(SPOT_PRICE_LOG_JSON_END, start + 1)
    except ValueError as exc:
        raise ValueError("Spot price log scanner did not emit a complete JSON payload") from exc
    payload_text = "\n".join(lines[start + 1 : end]).strip()
    if not payload_text:
        raise ValueError("Spot price log scanner emitted an empty JSON payload")
    payload = json.loads(payload_text)
    if not isinstance(payload, dict):
        raise ValueError("Spot price log scanner payload must be a JSON object")
    if not isinstance(payload.get("rows"), list):
        raise ValueError("Spot price log scanner payload is missing rows")
    return payload
