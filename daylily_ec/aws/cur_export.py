"""CUR 2.0 Data Export and Athena setup for cost-center allocation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from daylily_ec.aws.cur import CurAthenaConfig


class CurExportError(RuntimeError):
    """Raised when CUR export setup cannot continue safely."""


DEFAULT_EXPORT_NAME = "dayec-cur2-hourly"
DEFAULT_EXPORT_PREFIX = "dayec-cur"
DEFAULT_DATABASE = "dayec_cur"
DEFAULT_TABLE = "cur2_hourly"
DEFAULT_BILLING_REGION = "us-east-1"
DEFAULT_CLUSTER_TAG_KEY = "user_parallelcluster_cluster_name"
DATA_EXPORTS_SERVICE = "bcm-data-exports.amazonaws.com"
DATA_EXPORTS_TABLE = "COST_AND_USAGE_REPORT"
TABLE_PROPERTIES = {
    "TIME_GRANULARITY": "HOURLY",
    "INCLUDE_RESOURCES": "TRUE",
    "INCLUDE_SPLIT_COST_ALLOCATION_DATA": "FALSE",
    "INCLUDE_MANUAL_DISCOUNT_COMPATIBILITY": "FALSE",
}
CUR_EXPORT_COLUMNS = (
    "line_item_resource_id",
    "line_item_usage_start_date",
    "line_item_usage_end_date",
    "line_item_product_code",
    "line_item_usage_type",
    "line_item_operation",
    "line_item_unblended_cost",
    "line_item_currency_code",
    "line_item_line_item_type",
    "pricing_term",
    "product_region_code",
    "resource_tags",
)

_EXPORT_NAME_RE = re.compile(r"^[0-9A-Za-z_-]{1,128}$")
_GLUE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,254}$")
_BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")


@dataclass(frozen=True)
class CurExportConfig:
    account_id: str
    bucket: str
    bucket_region: str = DEFAULT_BILLING_REGION
    billing_region: str = DEFAULT_BILLING_REGION
    athena_region: str = DEFAULT_BILLING_REGION
    export_name: str = DEFAULT_EXPORT_NAME
    s3_prefix: str = DEFAULT_EXPORT_PREFIX
    database: str = DEFAULT_DATABASE
    table: str = DEFAULT_TABLE
    athena_output_s3_uri: str = ""
    cluster_tag_key: str = DEFAULT_CLUSTER_TAG_KEY

    def normalized(self) -> "CurExportConfig":
        account_id = str(self.account_id or "").strip()
        if not re.fullmatch(r"\d{12}", account_id):
            raise CurExportError("A 12-digit AWS account id is required.")
        bucket = _validate_bucket(self.bucket)
        export_name = _validate_export_name(self.export_name)
        database = _validate_glue_name(self.database, "Glue database")
        table = _validate_glue_name(self.table, "Glue table")
        s3_prefix = _normalize_prefix(self.s3_prefix)
        bucket_region = _require_value(self.bucket_region, "bucket_region")
        billing_region = _require_value(self.billing_region, "billing_region")
        athena_region = _require_value(self.athena_region, "athena_region")
        cluster_tag_key = _require_value(self.cluster_tag_key, "cluster_tag_key")
        output_uri = str(self.athena_output_s3_uri or "").strip()
        if not output_uri:
            output_uri = f"s3://{bucket}/{s3_prefix}/athena-results/"
        if not output_uri.startswith("s3://") or not output_uri.endswith("/"):
            raise CurExportError("athena_output_s3_uri must be an s3:// URI ending in '/'.")
        return CurExportConfig(
            account_id=account_id,
            bucket=bucket,
            bucket_region=bucket_region,
            billing_region=billing_region,
            athena_region=athena_region,
            export_name=export_name,
            s3_prefix=s3_prefix,
            database=database,
            table=table,
            athena_output_s3_uri=output_uri,
            cluster_tag_key=cluster_tag_key,
        )


def default_cur_export_bucket(account_id: str) -> str:
    account = str(account_id or "").strip()
    if not re.fullmatch(r"\d{12}", account):
        raise CurExportError("A 12-digit AWS account id is required for the default CUR bucket.")
    return f"dayec-cur-{account}-us-east-1"


def ensure_cur2_athena_source(
    *,
    s3_client: Any,
    bcm_client: Any,
    glue_client: Any,
    config: CurExportConfig,
    update_existing_export: bool = False,
    adopt_glue_table: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Ensure the explicit CUR 2.0 export, S3 policy, Glue DB/table, and partition."""
    resolved = config.normalized()
    timestamp = now or datetime.now(timezone.utc)
    period = timestamp.strftime("%Y-%m")
    bucket_action = ensure_export_bucket(s3_client, config=resolved)
    policy_action = ensure_data_exports_bucket_policy(s3_client, config=resolved)
    export = ensure_bcm_cur2_export(
        bcm_client,
        config=resolved,
        update_existing=update_existing_export,
    )
    schema = get_cur2_schema(bcm_client)
    database_action = ensure_glue_database(glue_client, resolved.database)
    table_action = ensure_glue_table(
        glue_client,
        config=resolved,
        schema=schema,
        adopt_existing=adopt_glue_table,
    )
    partition_action = ensure_current_billing_partition(
        glue_client,
        config=resolved,
        schema=schema,
        billing_period=period,
    )
    latest_execution = latest_export_execution(bcm_client, export_arn=export["export_arn"])
    cur_config = CurAthenaConfig(
        database=resolved.database,
        table=resolved.table,
        output_s3_uri=resolved.athena_output_s3_uri,
        cluster_tag_column="",
        cluster_tag_map_column="resource_tags",
        cluster_tag_key=resolved.cluster_tag_key,
        region_column="product_region_code",
        currency_column="line_item_currency_code",
    )
    return {
        "account_id": resolved.account_id,
        "billing_region": resolved.billing_region,
        "athena_region": resolved.athena_region,
        "bucket": resolved.bucket,
        "bucket_region": resolved.bucket_region,
        "s3_prefix": resolved.s3_prefix,
        "export_name": resolved.export_name,
        "export_arn": export["export_arn"],
        "export_action": export["action"],
        "export_status": _json_safe(export.get("status", {})),
        "bucket_action": bucket_action,
        "bucket_policy_action": policy_action,
        "database": resolved.database,
        "database_action": database_action,
        "table": resolved.table,
        "table_action": table_action,
        "billing_period": period,
        "partition_action": partition_action,
        "data_location": billing_period_data_location(resolved, period),
        "athena_output_s3_uri": resolved.athena_output_s3_uri,
        "cluster_tag_key": resolved.cluster_tag_key,
        "cur_athena_config": {
            "database": cur_config.database,
            "table": cur_config.table,
            "output_s3_uri": cur_config.output_s3_uri,
            "workgroup": cur_config.workgroup,
            "cluster_tag_map_column": cur_config.cluster_tag_map_column,
            "cluster_tag_key": cur_config.cluster_tag_key,
            "region_column": cur_config.region_column,
            "currency_column": cur_config.currency_column,
        },
        "latest_execution": latest_execution,
        "delivery_note": (
            "AWS Data Exports refreshes CUR 2.0 when source billing data updates; "
            "new exports are not expected to have immediate data files."
        ),
    }


def ensure_export_bucket(s3_client: Any, *, config: CurExportConfig) -> str:
    try:
        s3_client.head_bucket(Bucket=config.bucket)
    except Exception as exc:
        if not _is_not_found(exc):
            raise CurExportError(f"Cannot access S3 bucket '{config.bucket}': {exc}") from exc
        kwargs: dict[str, Any] = {"Bucket": config.bucket}
        if config.bucket_region != "us-east-1":
            kwargs["CreateBucketConfiguration"] = {"LocationConstraint": config.bucket_region}
        s3_client.create_bucket(**kwargs)
        _wait_for_bucket(s3_client, config.bucket)
        return "created"
    actual_region = get_bucket_region(s3_client, config.bucket)
    if actual_region != config.bucket_region:
        raise CurExportError(
            f"S3 bucket '{config.bucket}' is in {actual_region}, expected {config.bucket_region}."
        )
    return "existing"


def get_bucket_region(s3_client: Any, bucket: str) -> str:
    response = s3_client.get_bucket_location(Bucket=bucket)
    location = response.get("LocationConstraint") or "us-east-1"
    if location == "EU":
        return "eu-west-1"
    return str(location)


def ensure_data_exports_bucket_policy(s3_client: Any, *, config: CurExportConfig) -> str:
    expected = data_exports_bucket_policy_statement(config)
    try:
        response = s3_client.get_bucket_policy(Bucket=config.bucket)
        policy = json.loads(response.get("Policy") or "{}")
    except Exception as exc:
        if _is_not_found(exc) or _error_code(exc) == "NoSuchBucketPolicy":
            policy = {"Version": "2012-10-17", "Statement": []}
        else:
            raise CurExportError(f"Cannot read S3 bucket policy for '{config.bucket}': {exc}") from exc
    statements = policy.get("Statement")
    if not isinstance(statements, list):
        raise CurExportError(f"S3 bucket '{config.bucket}' has a policy with no Statement list.")
    for statement in statements:
        if _policy_statement_for_compare(statement) == _policy_statement_for_compare(expected):
            return "existing"
    sid = expected["Sid"]
    policy["Statement"] = [
        statement
        for statement in statements
        if not (isinstance(statement, dict) and statement.get("Sid") == sid)
    ]
    policy["Statement"].append(expected)
    s3_client.put_bucket_policy(Bucket=config.bucket, Policy=json.dumps(policy, sort_keys=True))
    return "updated"


def data_exports_bucket_policy_statement(config: CurExportConfig) -> dict[str, Any]:
    return {
        "Sid": "EnableAWSDataExportsToWriteToS3",
        "Effect": "Allow",
        "Principal": {"Service": [DATA_EXPORTS_SERVICE]},
        "Action": ["s3:PutObject"],
        "Resource": f"arn:aws:s3:::{config.bucket}/*",
        "Condition": {
            "ArnLike": {
                "aws:SourceArn": (
                    f"arn:aws:bcm-data-exports:{config.billing_region}:"
                    f"{config.account_id}:export/*"
                )
            },
            "StringEquals": {"aws:SourceAccount": config.account_id},
        },
    }


def _policy_statement_for_compare(statement: Any) -> Any:
    if not isinstance(statement, dict):
        return statement
    copy = json.loads(json.dumps(statement))
    principal = copy.get("Principal")
    if isinstance(principal, dict):
        service = principal.get("Service")
        if isinstance(service, str):
            principal["Service"] = [service]
    action = copy.get("Action")
    if isinstance(action, str):
        copy["Action"] = [action]
    return copy


def ensure_bcm_cur2_export(
    bcm_client: Any,
    *,
    config: CurExportConfig,
    update_existing: bool = False,
) -> dict[str, Any]:
    expected = build_cur2_export_definition(config)
    existing = _find_export_by_name(bcm_client, config.export_name)
    if existing is None:
        response = bcm_client.create_export(
            Export=expected,
            ResourceTags=[
                {"Key": "dayec:managed", "Value": "true"},
                {"Key": "dayec:purpose", "Value": "cost-center-accounting"},
            ],
        )
        return {
            "action": "created",
            "export_arn": response.get("ExportArn", ""),
            "status": {},
        }
    export_arn = existing["ExportArn"]
    current = bcm_client.get_export(ExportArn=export_arn).get("Export", {})
    if _export_for_compare(current) != _export_for_compare(expected):
        if not update_existing:
            raise CurExportError(
                f"Data Export '{config.export_name}' already exists with a different definition. "
                "Pass --update-existing-export to update it explicitly."
            )
        bcm_client.update_export(ExportArn=export_arn, Export=expected)
        action = "updated"
    else:
        action = "existing"
    return {
        "action": action,
        "export_arn": export_arn,
        "status": existing.get("ExportStatus", {}),
    }


def build_cur2_export_definition(config: CurExportConfig) -> dict[str, Any]:
    return {
        "Name": config.export_name,
        "Description": "DayEC hourly CUR 2.0 export for Slurm cost-center allocation.",
        "DataQuery": {
            "QueryStatement": "SELECT "
            + ", ".join(CUR_EXPORT_COLUMNS)
            + f" FROM {DATA_EXPORTS_TABLE}",
            "TableConfigurations": {DATA_EXPORTS_TABLE: dict(TABLE_PROPERTIES)},
        },
        "DestinationConfigurations": {
            "S3Destination": {
                "S3Bucket": config.bucket,
                "S3BucketOwner": config.account_id,
                "S3Prefix": config.s3_prefix,
                "S3Region": config.bucket_region,
                "S3OutputConfigurations": {
                    "OutputType": "CUSTOM",
                    "Format": "PARQUET",
                    "Compression": "PARQUET",
                    "Overwrite": "OVERWRITE_REPORT",
                },
            }
        },
        "RefreshCadence": {"Frequency": "SYNCHRONOUS"},
    }


def get_cur2_schema(bcm_client: Any) -> list[dict[str, str]]:
    response = bcm_client.get_table(
        TableName=DATA_EXPORTS_TABLE,
        TableProperties=dict(TABLE_PROPERTIES),
    )
    schema = response.get("Schema") or []
    if not schema:
        raise CurExportError("BCM Data Exports table dictionary returned no CUR schema.")
    names = {str(column.get("Name") or "") for column in schema}
    required = {
        "line_item_resource_id",
        "line_item_usage_start_date",
        "line_item_unblended_cost",
        "line_item_currency_code",
        "line_item_product_code",
        "product_region_code",
        "resource_tags",
    }
    missing = sorted(required - names)
    if missing:
        raise CurExportError("CUR 2.0 schema is missing required columns: " + ", ".join(missing))
    columns_by_name = {str(column["Name"]): column for column in schema}
    return [
        {"Name": str(columns_by_name[name]["Name"]), "Type": str(columns_by_name[name]["Type"])}
        for name in CUR_EXPORT_COLUMNS
    ]


def ensure_glue_database(glue_client: Any, database: str) -> str:
    try:
        glue_client.get_database(Name=database)
        return "existing"
    except Exception as exc:
        if not _is_not_found(exc):
            raise CurExportError(f"Cannot read Glue database '{database}': {exc}") from exc
    glue_client.create_database(
        DatabaseInput={
            "Name": database,
            "Description": "DayEC CUR 2.0 database for cost-center allocation.",
        }
    )
    return "created"


def ensure_glue_table(
    glue_client: Any,
    *,
    config: CurExportConfig,
    schema: list[dict[str, str]],
    adopt_existing: bool = False,
) -> str:
    expected = glue_table_input(config, schema=schema)
    try:
        current = glue_client.get_table(DatabaseName=config.database, Name=config.table).get("Table", {})
    except Exception as exc:
        if not _is_not_found(exc):
            raise CurExportError(f"Cannot read Glue table '{config.database}.{config.table}': {exc}") from exc
        glue_client.create_table(DatabaseName=config.database, TableInput=expected)
        return "created"
    params = current.get("Parameters") or {}
    if params.get("dayec:managed") != "true" and not adopt_existing:
        raise CurExportError(
            f"Glue table '{config.database}.{config.table}' exists but is not marked dayec-managed. "
            "Pass --adopt-glue-table to manage it explicitly."
        )
    glue_client.update_table(DatabaseName=config.database, TableInput=expected)
    return "updated" if params.get("dayec:managed") != "true" else "existing"


def glue_table_input(config: CurExportConfig, *, schema: list[dict[str, str]]) -> dict[str, Any]:
    columns = [_glue_column(column) for column in schema]
    return {
        "Name": config.table,
        "Description": "DayEC CUR 2.0 hourly table for Slurm cost-center allocation.",
        "TableType": "EXTERNAL_TABLE",
        "Parameters": {
            "classification": "parquet",
            "EXTERNAL": "TRUE",
            "dayec:managed": "true",
            "dayec:source": "bcm-data-exports",
            "dayec:export-name": config.export_name,
        },
        "PartitionKeys": [{"Name": "billing_period", "Type": "string"}],
        "StorageDescriptor": _storage_descriptor(
            columns=columns,
            location=f"s3://{config.bucket}/{config.s3_prefix}/{config.export_name}/data/",
        ),
    }


def ensure_current_billing_partition(
    glue_client: Any,
    *,
    config: CurExportConfig,
    schema: list[dict[str, str]],
    billing_period: str,
) -> str:
    try:
        glue_client.get_partition(
            DatabaseName=config.database,
            TableName=config.table,
            PartitionValues=[billing_period],
        )
        return "existing"
    except Exception as exc:
        if not _is_not_found(exc):
            raise CurExportError(
                f"Cannot read Glue partition '{config.database}.{config.table}/{billing_period}': {exc}"
            ) from exc
    columns = [_glue_column(column) for column in schema]
    glue_client.create_partition(
        DatabaseName=config.database,
        TableName=config.table,
        PartitionInput={
            "Values": [billing_period],
            "StorageDescriptor": _storage_descriptor(
                columns=columns,
                location=billing_period_data_location(config, billing_period),
            ),
            "Parameters": {"dayec:managed": "true"},
        },
    )
    return "created"


def billing_period_data_location(config: CurExportConfig, billing_period: str) -> str:
    return (
        f"s3://{config.bucket}/{config.s3_prefix}/{config.export_name}/data/"
        f"BILLING_PERIOD={billing_period}/"
    )


def latest_export_execution(bcm_client: Any, *, export_arn: str) -> dict[str, Any] | None:
    if not export_arn:
        return None
    executions: list[dict[str, Any]] = []
    kwargs: dict[str, Any] = {"ExportArn": export_arn}
    while True:
        response = bcm_client.list_executions(**kwargs)
        executions.extend(response.get("Executions", []))
        token = response.get("NextToken")
        if not token:
            break
        kwargs["NextToken"] = token
    if not executions:
        return None
    executions.sort(
        key=lambda item: str((item.get("ExecutionStatus") or {}).get("CreatedAt") or ""),
        reverse=True,
    )
    return _json_safe(executions[0])


def _storage_descriptor(*, columns: list[dict[str, str]], location: str) -> dict[str, Any]:
    return {
        "Columns": columns,
        "Location": location,
        "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
        "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
        "SerdeInfo": {
            "SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe",
            "Parameters": {"serialization.format": "1"},
        },
        "StoredAsSubDirectories": False,
    }


def _glue_column(column: dict[str, str]) -> dict[str, str]:
    name = str(column.get("Name") or "").strip()
    type_name = str(column.get("Type") or "").strip()
    if not name:
        raise CurExportError("CUR schema contains a column with no name.")
    return {"Name": name, "Type": _glue_type(type_name)}


def _glue_type(type_name: str) -> str:
    normalized = type_name.strip().lower()
    if normalized == "string":
        return "string"
    if normalized == "timestamp":
        return "timestamp"
    if normalized == "number":
        return "double"
    if normalized == "map":
        return "map<string,string>"
    raise CurExportError(f"Unsupported CUR schema type '{type_name}'.")


def _find_export_by_name(bcm_client: Any, export_name: str) -> dict[str, Any] | None:
    kwargs: dict[str, Any] = {}
    while True:
        response = bcm_client.list_exports(**kwargs)
        for export in response.get("Exports", []):
            if export.get("ExportName") == export_name:
                return export
        token = response.get("NextToken")
        if not token:
            return None
        kwargs["NextToken"] = token


def _export_for_compare(export: dict[str, Any]) -> dict[str, Any]:
    copy = json.loads(json.dumps(export))
    copy.pop("ExportArn", None)
    table_configurations = (
        copy.get("DataQuery", {})
        .get("TableConfigurations", {})
    )
    if isinstance(table_configurations, dict):
        cur_config = table_configurations.get(DATA_EXPORTS_TABLE)
        if isinstance(cur_config, dict):
            cur_config.pop("BILLING_VIEW_ARN", None)
    return copy


def _wait_for_bucket(s3_client: Any, bucket: str) -> None:
    try:
        waiter = s3_client.get_waiter("bucket_exists")
    except Exception:
        waiter = None
    if waiter is not None:
        waiter.wait(Bucket=bucket)


def _validate_bucket(value: str) -> str:
    bucket = str(value or "").strip()
    if not _BUCKET_RE.fullmatch(bucket) or ".." in bucket or ".-" in bucket or "-." in bucket:
        raise CurExportError("S3 bucket name is invalid for a DYEC CUR export.")
    return bucket


def _validate_export_name(value: str) -> str:
    name = str(value or "").strip()
    if not _EXPORT_NAME_RE.fullmatch(name):
        raise CurExportError("Data Export name must contain only letters, numbers, '-' and '_'.")
    return name


def _validate_glue_name(value: str, label: str) -> str:
    name = str(value or "").strip()
    if not _GLUE_NAME_RE.fullmatch(name):
        raise CurExportError(f"{label} name must start with a letter or '_' and use letters, numbers, or '_'.")
    return name


def _normalize_prefix(value: str) -> str:
    prefix = str(value or "").strip().strip("/")
    if not prefix:
        raise CurExportError("S3 prefix is required.")
    if any(part in {"", ".", ".."} for part in prefix.split("/")):
        raise CurExportError("S3 prefix contains an invalid path segment.")
    return prefix


def _require_value(value: str, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CurExportError(f"{field} is required.")
    return text


def _is_not_found(exc: Exception) -> bool:
    code = _error_code(exc)
    if code in {
        "404",
        "NoSuchBucket",
        "NoSuchBucketPolicy",
        "EntityNotFoundException",
        "ResourceNotFoundException",
        "NotFoundException",
    }:
        return True
    text = str(exc).lower()
    return "not found" in text or "notfound" in text


def _error_code(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        return str((response.get("Error") or {}).get("Code") or "")
    return ""


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return value
