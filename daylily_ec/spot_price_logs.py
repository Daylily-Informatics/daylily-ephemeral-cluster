"""Spot-price log collection and CSV rendering."""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
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
    "event",
    "recorded_at_epoch",
    "interruption_action",
    "interruption_time",
    "shutdown_reason",
)

SPOT_COST_INTERVAL_COLUMNS = (
    "cluster",
    "instance_id",
    "hostname",
    "node_type",
    "slurm_partition",
    "compute_resource",
    "region",
    "availability_zone",
    "instance_type",
    "start_recorded_at",
    "start_recorded_at_epoch",
    "end_recorded_at",
    "end_recorded_at_epoch",
    "end_event",
    "interruption_action",
    "interruption_time",
    "shutdown_reason",
    "duration_seconds",
    "duration_hours",
    "spot_price_usd_per_hour",
    "cost_price_source",
    "spot_cost_usd",
    "open_interval",
    "source_start_path",
    "source_start_line",
    "source_end_path",
    "source_end_line",
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

_LIFECYCLE_SPOT_LINE_RE = re.compile(
    r"^(?P<recorded_at>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - "
    r"Event: (?P<event>start|shutdown|interruption_notice), "
    r"Node type: (?P<node_type>[^,]*), "
    r"(?:Partition|Queue): (?P<slurm_partition>[^,]*), "
    r"Compute resource: (?P<compute_resource>[^,]*), "
    r"Hostname: (?P<hostname>[^,]*), "
    r"Instance id: (?P<instance_id>[^,]*), "
    r"Region: (?P<region>[^,]+), "
    r"AZ: (?P<availability_zone>[^,]+), "
    r"Instance type: (?P<instance_type>[^,]+), "
    r"Spot price: (?P<spot_price_usd_per_hour>\S+) USD/hour, "
    r"Recorded epoch: (?P<recorded_at_epoch>\d+)"
    r"(?:, Interruption action: (?P<interruption_action>[^,]+), "
    r"Interruption time: (?P<interruption_time>[^,]+))?"
    r"(?:, Shutdown reason: (?P<shutdown_reason>[^,]+))?$"
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

    match = (
        _LIFECYCLE_SPOT_LINE_RE.match(raw_line)
        or _CONTEXT_SPOT_LINE_RE.match(raw_line)
        or _OLD_SPOT_LINE_RE.match(raw_line)
    )
    if not match:
        raise ValueError(f"Malformed spot price log line: {raw_line}")

    parsed = {key: (value or "").strip() for key, value in match.groupdict().items()}
    parsed["event"] = parsed.get("event") or "start"
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
        if not row["event"] and row["spot_price_usd_per_hour"]:
            row["event"] = "start"
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


def spot_cost_intervals_to_csv(intervals: Iterable[dict[str, Any]]) -> str:
    """Render spot cost intervals as CSV text."""

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(SPOT_COST_INTERVAL_COLUMNS),
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for interval in intervals:
        writer.writerow(
            {column: interval.get(column, "") for column in SPOT_COST_INTERVAL_COLUMNS}
        )
    return buffer.getvalue()


def build_spot_cost_intervals(
    rows: Iterable[dict[str, Any]],
    *,
    price_source: str = "history",
    ec2_client: Any | None = None,
    compute_only: bool = True,
) -> list[dict[str, str]]:
    """Build per-instance lifecycle cost intervals from normalized spot log rows."""

    if price_source not in {"history", "logged"}:
        raise ValueError("--cost-price-source must be either 'history' or 'logged'")
    normalized_rows = [dict(row) for row in rows]
    if compute_only:
        normalized_rows = [
            row for row in normalized_rows if row.get("node_type") == "ComputeFleet"
        ]

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in normalized_rows:
        event = (row.get("event") or "start").strip()
        if event not in {"start", "shutdown", "interruption_notice"}:
            raise ValueError(f"Unsupported spot lifecycle event: {event}")
        if not row.get("instance_id"):
            raise ValueError(f"Lifecycle cost row is missing instance_id: {row}")
        grouped.setdefault(str(row["instance_id"]), []).append(row)

    intervals: list[dict[str, str]] = []
    for instance_rows in grouped.values():
        instance_rows.sort(key=_spot_row_sort_key)
        start_indexes = [
            index
            for index, row in enumerate(instance_rows)
            if (row.get("event") or "start") == "start"
        ]
        for position, start_index in enumerate(start_indexes):
            next_start_index = (
                start_indexes[position + 1]
                if position + 1 < len(start_indexes)
                else len(instance_rows)
            )
            start_row = instance_rows[start_index]
            lifecycle_rows = instance_rows[start_index + 1 : next_start_index]
            shutdown_row = next(
                (
                    row
                    for row in lifecycle_rows
                    if (row.get("event") or "start") == "shutdown"
                ),
                None,
            )
            notice_row = next(
                (
                    row
                    for row in lifecycle_rows
                    if (row.get("event") or "start") == "interruption_notice"
                ),
                None,
            )

            start_dt = _row_recorded_datetime(start_row)
            end_row = shutdown_row or notice_row
            end_dt = None
            end_event = ""
            if shutdown_row is not None:
                end_dt = _row_recorded_datetime(shutdown_row)
                end_event = "shutdown"
            elif notice_row is not None and notice_row.get("interruption_time"):
                end_dt = _parse_interruption_time(str(notice_row["interruption_time"]))
                end_event = "interruption_notice"

            interval = _base_cost_interval(start_row, start_dt, end_row, end_dt, end_event)
            if end_dt is None:
                interval.update(
                    {
                        "duration_seconds": "",
                        "duration_hours": "",
                        "cost_price_source": price_source,
                        "spot_cost_usd": "",
                        "open_interval": "true",
                    }
                )
                intervals.append(interval)
                continue
            if end_dt < start_dt:
                raise ValueError(
                    "Spot lifecycle interval end precedes start for "
                    f"{start_row.get('instance_id')}: {start_dt.isoformat()} > "
                    f"{end_dt.isoformat()}"
                )

            duration_seconds = int((end_dt - start_dt).total_seconds())
            interval["duration_seconds"] = str(duration_seconds)
            interval["duration_hours"] = _format_decimal(
                Decimal(duration_seconds) / Decimal("3600")
            )
            interval["cost_price_source"] = price_source
            interval["open_interval"] = "false"
            if price_source == "logged":
                cost = _logged_interval_cost(start_row, duration_seconds)
            else:
                if ec2_client is None:
                    raise ValueError(
                        "An EC2 client is required when --cost-price-source=history"
                    )
                cost = _history_interval_cost(
                    ec2_client=ec2_client,
                    start_dt=start_dt,
                    end_dt=end_dt,
                    instance_type=str(start_row.get("instance_type") or ""),
                    availability_zone=str(start_row.get("availability_zone") or ""),
                )
            interval["spot_cost_usd"] = _format_decimal(cost)
            intervals.append(interval)

    intervals.sort(
        key=lambda interval: (
            interval.get("start_recorded_at_epoch") or "",
            interval.get("instance_id") or "",
        )
    )
    return intervals


def _base_cost_interval(
    start_row: dict[str, Any],
    start_dt: datetime,
    end_row: dict[str, Any] | None,
    end_dt: datetime | None,
    end_event: str,
) -> dict[str, str]:
    interval = {column: "" for column in SPOT_COST_INTERVAL_COLUMNS}
    for column in (
        "cluster",
        "instance_id",
        "hostname",
        "node_type",
        "slurm_partition",
        "compute_resource",
        "region",
        "availability_zone",
        "instance_type",
        "spot_price_usd_per_hour",
    ):
        interval[column] = str(start_row.get(column) or "")
    interval.update(
        {
            "start_recorded_at": str(start_row.get("recorded_at") or ""),
            "start_recorded_at_epoch": str(
                start_row.get("recorded_at_epoch") or int(start_dt.timestamp())
            ),
            "source_start_path": str(start_row.get("source_path") or ""),
            "source_start_line": str(start_row.get("line_number") or ""),
            "end_event": end_event,
        }
    )
    if end_row is not None:
        interval.update(
            {
                "interruption_action": str(end_row.get("interruption_action") or ""),
                "interruption_time": str(end_row.get("interruption_time") or ""),
                "shutdown_reason": str(end_row.get("shutdown_reason") or ""),
                "source_end_path": str(end_row.get("source_path") or ""),
                "source_end_line": str(end_row.get("line_number") or ""),
            }
        )
    if end_dt is not None:
        interval["end_recorded_at"] = end_dt.strftime("%Y-%m-%d %H:%M:%S")
        interval["end_recorded_at_epoch"] = str(int(end_dt.timestamp()))
    return interval


def _spot_row_sort_key(row: dict[str, Any]) -> tuple[int, str, int]:
    timestamp = int(_row_recorded_datetime(row).timestamp())
    line_number = _safe_int(row.get("line_number"))
    return timestamp, str(row.get("source_path") or ""), line_number


def _row_recorded_datetime(row: dict[str, Any]) -> datetime:
    recorded_at_epoch = str(row.get("recorded_at_epoch") or "").strip()
    if recorded_at_epoch:
        return datetime.fromtimestamp(int(recorded_at_epoch), tz=timezone.utc)
    recorded_at = str(row.get("recorded_at") or "").strip()
    if not recorded_at:
        raise ValueError(f"Spot lifecycle row is missing recorded_at: {row}")
    return datetime.strptime(recorded_at, "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=timezone.utc
    )


def _parse_interruption_time(value: str) -> datetime:
    normalized = value.strip()
    if not normalized:
        raise ValueError("interruption_time is required to close an interruption interval")
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _logged_interval_cost(start_row: dict[str, Any], duration_seconds: int) -> Decimal:
    price = Decimal(str(start_row.get("spot_price_usd_per_hour") or "0"))
    return price * Decimal(duration_seconds) / Decimal("3600")


def _history_interval_cost(
    *,
    ec2_client: Any,
    start_dt: datetime,
    end_dt: datetime,
    instance_type: str,
    availability_zone: str,
) -> Decimal:
    if not instance_type:
        raise ValueError("instance_type is required for history-based spot pricing")
    if not availability_zone:
        raise ValueError("availability_zone is required for history-based spot pricing")

    history = _describe_spot_price_history(
        ec2_client=ec2_client,
        start_dt=start_dt - timedelta(days=1),
        end_dt=end_dt,
        instance_type=instance_type,
        availability_zone=availability_zone,
    )
    points = sorted(
        (
            (_coerce_aws_datetime(point["Timestamp"]), Decimal(str(point["SpotPrice"])))
            for point in history
        ),
        key=lambda item: item[0],
    )
    current_price: Decimal | None = None
    for timestamp, price in points:
        if timestamp <= start_dt:
            current_price = price
        else:
            break
    if current_price is None:
        raise ValueError(
            "Spot price history did not include a price effective at interval start "
            f"for {instance_type} in {availability_zone} at {start_dt.isoformat()}"
        )

    cost = Decimal("0")
    cursor = start_dt
    for timestamp, price in points:
        if timestamp <= start_dt:
            continue
        if timestamp >= end_dt:
            break
        cost += current_price * Decimal(int((timestamp - cursor).total_seconds())) / Decimal(
            "3600"
        )
        cursor = timestamp
        current_price = price
    cost += current_price * Decimal(int((end_dt - cursor).total_seconds())) / Decimal(
        "3600"
    )
    return cost


def _describe_spot_price_history(
    *,
    ec2_client: Any,
    start_dt: datetime,
    end_dt: datetime,
    instance_type: str,
    availability_zone: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    next_token = ""
    while True:
        request: dict[str, Any] = {
            "StartTime": start_dt,
            "EndTime": end_dt,
            "InstanceTypes": [instance_type],
            "ProductDescriptions": ["Linux/UNIX"],
            "AvailabilityZone": availability_zone,
        }
        if next_token:
            request["NextToken"] = next_token
        response = ec2_client.describe_spot_price_history(**request)
        records.extend(response.get("SpotPriceHistory", []))
        next_token = response.get("NextToken") or ""
        if not next_token:
            break
    return records


def _coerce_aws_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    text = str(value)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_decimal(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.00000001")), "f")


def _safe_int(value: Any) -> int:
    try:
        return int(str(value or "0"))
    except ValueError:
        return 0


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
        "lifecycle_re = re.compile(r'^(?P<recorded_at>\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}) - Event: (?P<event>start|shutdown|interruption_notice), Node type: (?P<node_type>[^,]*), (?:Partition|Queue): (?P<slurm_partition>[^,]*), Compute resource: (?P<compute_resource>[^,]*), Hostname: (?P<hostname>[^,]*), Instance id: (?P<instance_id>[^,]*), Region: (?P<region>[^,]+), AZ: (?P<availability_zone>[^,]+), Instance type: (?P<instance_type>[^,]+), Spot price: (?P<spot_price_usd_per_hour>\\S+) USD/hour, Recorded epoch: (?P<recorded_at_epoch>\\d+)(?:, Interruption action: (?P<interruption_action>[^,]+), Interruption time: (?P<interruption_time>[^,]+))?(?:, Shutdown reason: (?P<shutdown_reason>[^,]+))?$')\n"
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
        "    match = lifecycle_re.match(raw_line) or context_re.match(raw_line) or old_re.match(raw_line)\n"
        "    if not match:\n"
        "        raise ValueError('%s:%s malformed spot price log line: %s' % (path, line_number, raw_line))\n"
        "    row = dict((column, '') for column in columns)\n"
        "    row.update(dict((key, (value or '').strip()) for key, value in match.groupdict().items()))\n"
        "    if not row.get('event'):\n"
        "        row['event'] = 'start'\n"
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
