from __future__ import annotations

from datetime import datetime, timezone

import pytest

from daylily_ec.aws.cur import (
    CurAthenaConfig,
    CurAthenaError,
    build_hourly_ec2_instance_cost_sql,
    parse_hourly_instance_cost_rows,
    query_hourly_ec2_instance_costs,
)


def test_build_hourly_sql_filters_cluster_and_instances():
    sql = build_hourly_ec2_instance_cost_sql(
        config=CurAthenaConfig(database="curdb", table="curtable", output_s3_uri="s3://out/"),
        cluster_name="cluster-a",
        start_hour=datetime(2026, 7, 5, tzinfo=timezone.utc),
        end_hour=datetime(2026, 7, 5, 1, tzinfo=timezone.utc),
        instance_ids=["i-1", "i-2"],
    )

    assert '"curdb"."curtable"' in sql
    assert "line_item_product_code = 'AmazonEC2'" in sql
    assert "resource_tags_user_parallelcluster_cluster_name = 'cluster-a'" in sql
    assert "line_item_resource_id IN ('i-1', 'i-2')" in sql


def test_build_hourly_sql_supports_cur2_resource_tags_map():
    sql = build_hourly_ec2_instance_cost_sql(
        config=CurAthenaConfig(
            database="curdb",
            table="curtable",
            output_s3_uri="s3://out/",
            cluster_tag_column="",
            cluster_tag_map_column="resource_tags",
            cluster_tag_key="user_parallelcluster_cluster_name",
            region_column="product_region_code",
            currency_column="line_item_currency_code",
        ),
        cluster_name="cluster-a",
        start_hour=datetime(2026, 7, 5, tzinfo=timezone.utc),
        end_hour=datetime(2026, 7, 5, 1, tzinfo=timezone.utc),
    )

    assert "element_at(resource_tags, 'user_parallelcluster_cluster_name') AS cluster_name" in sql
    assert "element_at(resource_tags, 'user_parallelcluster_cluster_name') = 'cluster-a'" in sql
    assert "product_region_code AS region" in sql
    assert "line_item_currency_code AS currency" in sql


def test_build_hourly_sql_rejects_partial_map_config():
    with pytest.raises(CurAthenaError, match="provided together"):
        build_hourly_ec2_instance_cost_sql(
            config=CurAthenaConfig(
                database="curdb",
                table="curtable",
                output_s3_uri="s3://out/",
                cluster_tag_map_column="resource_tags",
            ),
            cluster_name="cluster-a",
            start_hour=datetime(2026, 7, 5, tzinfo=timezone.utc),
            end_hour=datetime(2026, 7, 5, 1, tzinfo=timezone.utc),
        )


def test_parse_hourly_instance_cost_rows():
    rows = [
        [
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
        ],
        [
            "i-1",
            "cluster-a",
            "us-west-2",
            "2026-07-05 00:00:00.000",
            "2026-07-05 01:00:00.000",
            "1.25",
            "USD",
            "BoxUsage",
            "RunInstances",
            "OnDemand",
            "Usage",
        ],
    ]

    parsed = parse_hourly_instance_cost_rows(rows)

    assert len(parsed) == 1
    assert parsed[0].instance_id == "i-1"
    assert str(parsed[0].amount_usd) == "1.25"


def test_parse_rejects_missing_columns():
    with pytest.raises(CurAthenaError, match="columns mismatch"):
        parse_hourly_instance_cost_rows([["instance_id"]])


class FakeAthena:
    def __init__(self, state="SUCCEEDED"):
        self.state = state

    def start_query_execution(self, **_kwargs):
        return {"QueryExecutionId": "qid"}

    def get_query_execution(self, **_kwargs):
        return {"QueryExecution": {"Status": {"State": self.state, "StateChangeReason": "bad"}}}

    def get_query_results(self, **_kwargs):
        return {
            "ResultSet": {
                "Rows": [
                    {
                        "Data": [
                            {"VarCharValue": "instance_id"},
                            {"VarCharValue": "cluster_name"},
                            {"VarCharValue": "region"},
                            {"VarCharValue": "hour_start"},
                            {"VarCharValue": "hour_end"},
                            {"VarCharValue": "amount_usd"},
                            {"VarCharValue": "currency"},
                            {"VarCharValue": "usage_type"},
                            {"VarCharValue": "operation"},
                            {"VarCharValue": "purchase_option"},
                            {"VarCharValue": "line_item_type"},
                        ]
                    }
                ]
            }
        }


def test_query_fails_on_athena_failed():
    with pytest.raises(CurAthenaError, match="FAILED"):
        query_hourly_ec2_instance_costs(
            FakeAthena(state="FAILED"),
            config=CurAthenaConfig(database="curdb", table="curtable", output_s3_uri="s3://out/"),
            cluster_name="cluster-a",
            start_hour=datetime(2026, 7, 5, tzinfo=timezone.utc),
            end_hour=datetime(2026, 7, 5, 1, tzinfo=timezone.utc),
            poll_interval_seconds=0,
            timeout_seconds=1,
        )
