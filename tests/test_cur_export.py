from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from daylily_ec.aws.cur_export import (
    CurExportConfig,
    CurExportError,
    billing_period_data_location,
    build_cur2_export_definition,
    data_exports_bucket_policy_statement,
    default_cur_export_bucket,
    ensure_cur2_athena_source,
    glue_table_input,
)


class FakeClientError(Exception):
    def __init__(self, code: str):
        self.response = {"Error": {"Code": code}}
        super().__init__(code)


class FakeWaiter:
    def wait(self, **_kwargs):
        return None


class FakeS3:
    def __init__(self, *, bucket_exists: bool = False, policy: dict | None = None):
        self.bucket_exists = bucket_exists
        self.created_bucket = None
        self.policy = policy
        self.put_policy = None

    def head_bucket(self, **_kwargs):
        if not self.bucket_exists:
            raise FakeClientError("404")
        return {}

    def create_bucket(self, **kwargs):
        self.created_bucket = kwargs
        self.bucket_exists = True

    def get_waiter(self, _name):
        return FakeWaiter()

    def get_bucket_location(self, **_kwargs):
        return {"LocationConstraint": None}

    def get_bucket_policy(self, **_kwargs):
        if self.policy is None:
            raise FakeClientError("NoSuchBucketPolicy")
        return {"Policy": json.dumps(self.policy)}

    def put_bucket_policy(self, **kwargs):
        self.put_policy = json.loads(kwargs["Policy"])
        self.policy = self.put_policy


class FakeBcm:
    def __init__(self, *, existing_export: dict | None = None):
        self.existing_export = existing_export
        self.created_export = None
        self.updated_export = None

    def list_exports(self, **_kwargs):
        if self.existing_export:
            return {
                "Exports": [
                    {
                        "ExportArn": self.existing_export["ExportArn"],
                        "ExportName": self.existing_export["Name"],
                        "ExportStatus": {"StatusCode": "HEALTHY"},
                    }
                ]
            }
        return {"Exports": []}

    def get_export(self, **_kwargs):
        return {"Export": dict(self.existing_export)}

    def create_export(self, **kwargs):
        self.created_export = kwargs
        return {"ExportArn": "arn:aws:bcm-data-exports:us-east-1:123456789012:export/new"}

    def update_export(self, **kwargs):
        self.updated_export = kwargs
        return {"ExportArn": kwargs["ExportArn"]}

    def get_table(self, **_kwargs):
        return {
            "Schema": [
                {"Name": "line_item_resource_id", "Type": "String"},
                {"Name": "line_item_usage_start_date", "Type": "Timestamp"},
                {"Name": "line_item_usage_end_date", "Type": "Timestamp"},
                {"Name": "line_item_unblended_cost", "Type": "Number"},
                {"Name": "line_item_currency_code", "Type": "String"},
                {"Name": "line_item_product_code", "Type": "String"},
                {"Name": "line_item_usage_type", "Type": "String"},
                {"Name": "line_item_operation", "Type": "String"},
                {"Name": "line_item_line_item_type", "Type": "String"},
                {"Name": "product_region_code", "Type": "String"},
                {"Name": "resource_tags", "Type": "Map"},
                {"Name": "pricing_term", "Type": "String"},
            ]
        }

    def list_executions(self, **_kwargs):
        return {"Executions": []}


class FakeGlue:
    def __init__(self):
        self.database_created = None
        self.table_created = None
        self.table_updated = None
        self.partition_created = None

    def get_database(self, **_kwargs):
        raise FakeClientError("EntityNotFoundException")

    def create_database(self, **kwargs):
        self.database_created = kwargs

    def get_table(self, **_kwargs):
        raise FakeClientError("EntityNotFoundException")

    def create_table(self, **kwargs):
        self.table_created = kwargs

    def update_table(self, **kwargs):
        self.table_updated = kwargs

    def get_partition(self, **_kwargs):
        raise FakeClientError("EntityNotFoundException")

    def create_partition(self, **kwargs):
        self.partition_created = kwargs


def test_default_cur_export_bucket_is_account_scoped():
    assert default_cur_export_bucket("123456789012") == "dayec-cur-123456789012-us-east-1"


def test_data_exports_bucket_policy_statement_matches_bcm_contract():
    config = CurExportConfig(account_id="123456789012", bucket="dayec-cur-123456789012-us-east-1").normalized()

    statement = data_exports_bucket_policy_statement(config)

    assert statement["Principal"]["Service"] == ["bcm-data-exports.amazonaws.com"]
    assert statement["Action"] == ["s3:PutObject"]
    assert statement["Condition"]["ArnLike"]["aws:SourceArn"] == (
        "arn:aws:bcm-data-exports:us-east-1:123456789012:export/*"
    )
    assert statement["Condition"]["StringEquals"]["aws:SourceAccount"] == "123456789012"


def test_policy_compare_treats_aws_normalized_singletons_as_existing():
    config = CurExportConfig(account_id="123456789012", bucket="dayec-cur-123456789012-us-east-1").normalized()
    stored = data_exports_bucket_policy_statement(config)
    stored["Principal"]["Service"] = "bcm-data-exports.amazonaws.com"
    stored["Action"] = "s3:PutObject"
    s3 = FakeS3(bucket_exists=True, policy={"Version": "2012-10-17", "Statement": [stored]})

    payload = ensure_cur2_athena_source(
        s3_client=s3,
        bcm_client=FakeBcm(),
        glue_client=FakeGlue(),
        config=config,
        now=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )

    assert payload["bucket_policy_action"] == "existing"


def test_build_cur2_export_definition_uses_hourly_resource_parquet_overwrite():
    config = CurExportConfig(account_id="123456789012", bucket="dayec-cur-123456789012-us-east-1").normalized()

    export = build_cur2_export_definition(config)

    assert export["DataQuery"]["QueryStatement"] == (
        "SELECT line_item_resource_id, line_item_usage_start_date, line_item_usage_end_date, "
        "line_item_product_code, line_item_usage_type, line_item_operation, "
        "line_item_unblended_cost, line_item_currency_code, line_item_line_item_type, "
        "pricing_term, product_region_code, resource_tags FROM COST_AND_USAGE_REPORT"
    )
    assert export["DataQuery"]["TableConfigurations"]["COST_AND_USAGE_REPORT"] == {
        "TIME_GRANULARITY": "HOURLY",
        "INCLUDE_RESOURCES": "TRUE",
        "INCLUDE_SPLIT_COST_ALLOCATION_DATA": "FALSE",
        "INCLUDE_MANUAL_DISCOUNT_COMPATIBILITY": "FALSE",
    }
    output = export["DestinationConfigurations"]["S3Destination"]["S3OutputConfigurations"]
    assert output == {
        "OutputType": "CUSTOM",
        "Format": "PARQUET",
        "Compression": "PARQUET",
        "Overwrite": "OVERWRITE_REPORT",
    }


def test_glue_table_input_maps_cur2_schema_types():
    config = CurExportConfig(account_id="123456789012", bucket="dayec-cur-123456789012-us-east-1").normalized()

    table = glue_table_input(
        config,
        schema=[
            {"Name": "line_item_resource_id", "Type": "String"},
            {"Name": "line_item_usage_start_date", "Type": "Timestamp"},
            {"Name": "line_item_unblended_cost", "Type": "Number"},
            {"Name": "resource_tags", "Type": "Map"},
        ],
    )

    assert table["PartitionKeys"] == [{"Name": "billing_period", "Type": "string"}]
    columns = table["StorageDescriptor"]["Columns"]
    assert columns == [
        {"Name": "line_item_resource_id", "Type": "string"},
        {"Name": "line_item_usage_start_date", "Type": "timestamp"},
        {"Name": "line_item_unblended_cost", "Type": "double"},
        {"Name": "resource_tags", "Type": "map<string,string>"},
    ]


def test_ensure_cur2_athena_source_creates_export_table_and_partition():
    s3 = FakeS3(bucket_exists=False)
    bcm = FakeBcm()
    glue = FakeGlue()
    config = CurExportConfig(account_id="123456789012", bucket="dayec-cur-123456789012-us-east-1")

    payload = ensure_cur2_athena_source(
        s3_client=s3,
        bcm_client=bcm,
        glue_client=glue,
        config=config,
        now=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )

    assert payload["bucket_action"] == "created"
    assert payload["bucket_policy_action"] == "updated"
    assert payload["export_action"] == "created"
    assert payload["database_action"] == "created"
    assert payload["table_action"] == "created"
    assert payload["partition_action"] == "created"
    assert payload["billing_period"] == "2026-07"
    assert payload["cur_athena_config"]["cluster_tag_map_column"] == "resource_tags"
    assert payload["cur_athena_config"]["cluster_tag_key"] == "user_parallelcluster_cluster_name"
    assert bcm.created_export["Export"]["DataQuery"]["TableConfigurations"]["COST_AND_USAGE_REPORT"]["INCLUDE_RESOURCES"] == "TRUE"
    assert glue.partition_created["PartitionInput"]["StorageDescriptor"]["Location"] == billing_period_data_location(
        config.normalized(),
        "2026-07",
    )


def test_ensure_cur2_athena_source_rejects_drifted_existing_export_without_explicit_update():
    config = CurExportConfig(account_id="123456789012", bucket="dayec-cur-123456789012-us-east-1").normalized()
    drifted = build_cur2_export_definition(config)
    drifted["ExportArn"] = "arn:aws:bcm-data-exports:us-east-1:123456789012:export/existing"
    drifted["DestinationConfigurations"]["S3Destination"]["S3Prefix"] = "wrong"

    with pytest.raises(CurExportError, match="--update-existing-export"):
        ensure_cur2_athena_source(
            s3_client=FakeS3(bucket_exists=True),
            bcm_client=FakeBcm(existing_export=drifted),
            glue_client=FakeGlue(),
            config=config,
            now=datetime(2026, 7, 5, tzinfo=timezone.utc),
        )


def test_ensure_cur2_athena_source_tolerates_aws_injected_billing_view_arn():
    config = CurExportConfig(account_id="123456789012", bucket="dayec-cur-123456789012-us-east-1").normalized()
    existing = build_cur2_export_definition(config)
    existing["ExportArn"] = "arn:aws:bcm-data-exports:us-east-1:123456789012:export/existing"
    existing["DataQuery"]["TableConfigurations"]["COST_AND_USAGE_REPORT"]["BILLING_VIEW_ARN"] = (
        "arn:aws:billing::123456789012:billingview/primary"
    )

    payload = ensure_cur2_athena_source(
        s3_client=FakeS3(bucket_exists=True),
        bcm_client=FakeBcm(existing_export=existing),
        glue_client=FakeGlue(),
        config=config,
        now=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )

    assert payload["export_action"] == "existing"
