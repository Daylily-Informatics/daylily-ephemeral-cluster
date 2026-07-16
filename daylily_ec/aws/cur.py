"""Athena-backed hourly CUR adapter for EC2 instance costs."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Sequence


class CurAthenaError(RuntimeError):
    """Raised when CUR/Athena cost retrieval cannot continue safely."""


@dataclass(frozen=True)
class CurAthenaConfig:
    database: str
    table: str
    output_s3_uri: str
    workgroup: str = "primary"
    cluster_tag_column: str = "resource_tags_user_parallelcluster_cluster_name"
    cluster_tag_map_column: str = ""
    cluster_tag_key: str = ""
    region_column: str = "product_region"
    currency_column: str = "pricing_currency"


@dataclass(frozen=True)
class HourlyInstanceCost:
    instance_id: str
    cluster_name: str
    region: str
    hour_start: str
    hour_end: str
    amount_usd: Decimal
    currency: str
    usage_type: str
    operation: str
    purchase_option: str
    line_item_type: str

    def to_dict(self) -> dict[str, str]:
        return {
            "instance_id": self.instance_id,
            "cluster_name": self.cluster_name,
            "region": self.region,
            "hour_start": self.hour_start,
            "hour_end": self.hour_end,
            "amount_usd": str(self.amount_usd),
            "currency": self.currency,
            "usage_type": self.usage_type,
            "operation": self.operation,
            "purchase_option": self.purchase_option,
            "line_item_type": self.line_item_type,
        }


def query_hourly_ec2_instance_costs(
    athena_client: Any,
    *,
    config: CurAthenaConfig,
    cluster_name: str,
    start_hour: datetime,
    end_hour: datetime,
    instance_ids: Sequence[str] = (),
    poll_interval_seconds: float = 2.0,
    timeout_seconds: int = 300,
) -> list[HourlyInstanceCost]:
    """Run an Athena CUR query for hourly EC2 compute cost."""
    sql = build_hourly_ec2_instance_cost_sql(
        config=config,
        cluster_name=cluster_name,
        start_hour=start_hour,
        end_hour=end_hour,
        instance_ids=instance_ids,
    )
    response = athena_client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": config.database},
        ResultConfiguration={"OutputLocation": config.output_s3_uri},
        WorkGroup=config.workgroup,
    )
    query_execution_id = str(response.get("QueryExecutionId") or "")
    if not query_execution_id:
        raise CurAthenaError("Athena did not return QueryExecutionId.")
    _wait_for_query(
        athena_client,
        query_execution_id=query_execution_id,
        poll_interval_seconds=poll_interval_seconds,
        timeout_seconds=timeout_seconds,
    )
    return _read_query_results(athena_client, query_execution_id=query_execution_id)


def build_hourly_ec2_instance_cost_sql(
    *,
    config: CurAthenaConfig,
    cluster_name: str,
    start_hour: datetime,
    end_hour: datetime,
    instance_ids: Sequence[str] = (),
) -> str:
    if not config.database or not config.table or not config.output_s3_uri:
        raise CurAthenaError("CUR Athena database, table, and output_s3_uri are required.")
    if not cluster_name.strip():
        raise CurAthenaError("cluster_name is required.")
    if start_hour >= end_hour:
        raise CurAthenaError("start_hour must be before end_hour.")
    table_ref = f'"{_identifier(config.database)}"."{_identifier(config.table)}"'
    start_sql = _sql_timestamp(start_hour)
    end_sql = _sql_timestamp(end_hour)
    cluster_sql = _sql_string(cluster_name)
    cluster_expr = _cluster_tag_expression(config)
    region_expr = _column_expr(config.region_column)
    currency_expr = _column_expr(config.currency_column)
    instance_filter = ""
    if instance_ids:
        values = ", ".join(_sql_string(value) for value in instance_ids)
        instance_filter = f"\n  AND line_item_resource_id IN ({values})"
    return f"""
SELECT
  line_item_resource_id AS instance_id,
  {cluster_expr} AS cluster_name,
  {region_expr} AS region,
  date_trunc('hour', line_item_usage_start_date) AS hour_start,
  date_add('hour', 1, date_trunc('hour', line_item_usage_start_date)) AS hour_end,
  CAST(sum(CAST(line_item_unblended_cost AS double)) AS varchar) AS amount_usd,
  {currency_expr} AS currency,
  line_item_usage_type AS usage_type,
  line_item_operation AS operation,
  pricing_term AS purchase_option,
  line_item_line_item_type AS line_item_type
FROM {table_ref}
WHERE line_item_product_code = 'AmazonEC2'
  AND line_item_resource_id LIKE 'i-%'
  AND {cluster_expr} = {cluster_sql}
  AND line_item_usage_start_date >= TIMESTAMP {start_sql}
  AND line_item_usage_start_date < TIMESTAMP {end_sql}{instance_filter}
GROUP BY
  line_item_resource_id,
  {cluster_expr},
  {region_expr},
  date_trunc('hour', line_item_usage_start_date),
  date_add('hour', 1, date_trunc('hour', line_item_usage_start_date)),
  {currency_expr},
  line_item_usage_type,
  line_item_operation,
  pricing_term,
  line_item_line_item_type
ORDER BY hour_start, instance_id
""".strip()


def _wait_for_query(
    athena_client: Any,
    *,
    query_execution_id: str,
    poll_interval_seconds: float,
    timeout_seconds: int,
) -> None:
    deadline = time.time() + timeout_seconds
    while True:
        response = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
        status = (
            response.get("QueryExecution", {})
            .get("Status", {})
            .get("State", "")
        )
        if status == "SUCCEEDED":
            return
        if status in {"FAILED", "CANCELLED"}:
            reason = (
                response.get("QueryExecution", {})
                .get("Status", {})
                .get("StateChangeReason", "")
            )
            raise CurAthenaError(f"Athena query {query_execution_id} {status}: {reason}")
        if time.time() >= deadline:
            raise CurAthenaError(f"Athena query {query_execution_id} timed out.")
        time.sleep(poll_interval_seconds)


def _read_query_results(athena_client: Any, *, query_execution_id: str) -> list[HourlyInstanceCost]:
    rows: list[list[str]] = []
    next_token: str | None = None
    while True:
        kwargs = {"QueryExecutionId": query_execution_id}
        if next_token:
            kwargs["NextToken"] = next_token
        response = athena_client.get_query_results(**kwargs)
        for row in response.get("ResultSet", {}).get("Rows", []):
            rows.append([cell.get("VarCharValue", "") for cell in row.get("Data", [])])
        next_token = response.get("NextToken")
        if not next_token:
            break
    return parse_hourly_instance_cost_rows(rows)


def parse_hourly_instance_cost_rows(rows: list[list[str]]) -> list[HourlyInstanceCost]:
    if not rows:
        return []
    header = rows[0]
    expected = [
        "instance_id",
        "cluster_name",
        "region",
        "hour_start",
        "hour_end",
        "amount_usd",
        "currency",
        "usage_type",
        "operation",
        "purchase_option",
        "line_item_type",
    ]
    if header != expected:
        raise CurAthenaError(f"Athena result columns mismatch: {header}")
    parsed: list[HourlyInstanceCost] = []
    for row in rows[1:]:
        if len(row) != len(expected):
            raise CurAthenaError(f"Athena result row has {len(row)} columns, expected {len(expected)}.")
        values = dict(zip(expected, row))
        parsed.append(
            HourlyInstanceCost(
                instance_id=values["instance_id"],
                cluster_name=values["cluster_name"],
                region=values["region"],
                hour_start=_normalize_athena_timestamp(values["hour_start"]),
                hour_end=_normalize_athena_timestamp(values["hour_end"]),
                amount_usd=Decimal(values["amount_usd"] or "0"),
                currency=values["currency"],
                usage_type=values["usage_type"],
                operation=values["operation"],
                purchase_option=values["purchase_option"],
                line_item_type=values["line_item_type"],
            )
        )
    return parsed


def _identifier(value: str) -> str:
    clean = str(value or "").strip()
    if not clean or '"' in clean:
        raise CurAthenaError("Athena identifiers must be non-empty and must not contain quotes.")
    return clean


def _column_expr(value: str) -> str:
    return _identifier(value)


def _cluster_tag_expression(config: CurAthenaConfig) -> str:
    map_column = str(config.cluster_tag_map_column or "").strip()
    map_key = str(config.cluster_tag_key or "").strip()
    scalar_column = str(config.cluster_tag_column or "").strip()
    if map_column or map_key:
        if not map_column or not map_key:
            raise CurAthenaError(
                "cluster_tag_map_column and cluster_tag_key must be provided together."
            )
        return f"element_at({_column_expr(map_column)}, {_sql_string(map_key)})"
    if not scalar_column:
        raise CurAthenaError("cluster_tag_column is required when no map tag column is configured.")
    return _column_expr(scalar_column)


def _sql_string(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _sql_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc).replace(tzinfo=None, microsecond=0)
    return _sql_string(value.isoformat(sep=" "))


def _normalize_athena_timestamp(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text.replace(" ", "T") + ("Z" if not text.endswith("Z") else "")
