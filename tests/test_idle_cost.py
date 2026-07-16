from __future__ import annotations

import json
from decimal import Decimal

import pytest

from daylily_ec.aws.idle_cost import (
    HOURS_PER_MONTH,
    IdleCostPricingError,
    estimate_idle_cluster_cost,
)


def _price_product(unit: str, rate: str) -> str:
    return json.dumps(
        {
            "terms": {
                "OnDemand": {
                    "term": {
                        "priceDimensions": {
                            "dimension": {
                                "unit": unit,
                                "pricePerUnit": {"USD": rate},
                            }
                        }
                    }
                }
            }
        }
    )


class FakePricingClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_products(self, **kwargs):
        self.calls.append(kwargs)
        filters = {
            item["Field"]: item["Value"]
            for item in kwargs["Filters"]
        }
        service = kwargs["ServiceCode"]
        if service == "AmazonEC2" and "instanceType" in filters:
            price = _price_product("Hrs", "0.5292")
        elif service == "AmazonEC2" and filters.get("volumeApiName") == "gp3":
            price = _price_product("GB-Mo", "0.08")
        elif service == "AmazonFSx":
            price = _price_product(
                "GB-Mo",
                "0.21" if filters.get("throughputCapacity") == "250" else "0.14",
            )
        elif service == "AmazonVPC":
            price = _price_product("Hrs", "0.005")
        else:
            return {"PriceList": []}
        return {"PriceList": [price]}


def test_estimate_idle_cluster_cost_prices_all_configured_idle_resources() -> None:
    client = FakePricingClient()

    estimate = estimate_idle_cluster_cost(
        client,
        region="us-west-2",
        headnode_instance_type="r7i.2xlarge",
        root_volume_type="gp3",
        root_volume_gib=421,
        fsx_deployment_type="PERSISTENT_2",
        fsx_capacity_gib=4800,
        fsx_throughput_mbps_per_tib="250",
    )

    assert estimate.headnode_hourly_usd == Decimal("0.5292")
    assert estimate.root_volume_hourly_usd == Decimal("0.08") * 421 / HOURS_PER_MONTH
    assert estimate.fsx_hourly_usd == Decimal("0.21") * 4800 / HOURS_PER_MONTH
    assert estimate.public_ipv4_hourly_usd == Decimal("0.005")
    assert estimate.total_hourly_usd == (
        Decimal("0.5292")
        + Decimal("0.08") * 421 / HOURS_PER_MONTH
        + Decimal("0.21") * 4800 / HOURS_PER_MONTH
        + Decimal("0.005")
    )

    calls_by_service = {
        call["ServiceCode"]: call
        for call in client.calls
        if call["ServiceCode"] != "AmazonEC2"
        or any(item["Field"] == "instanceType" for item in call["Filters"])
    }
    ec2_filters = {
        item["Field"]: item["Value"]
        for item in calls_by_service["AmazonEC2"]["Filters"]
    }
    fsx_filters = {
        item["Field"]: item["Value"]
        for item in calls_by_service["AmazonFSx"]["Filters"]
    }
    ipv4_filters = {
        item["Field"]: item["Value"]
        for item in calls_by_service["AmazonVPC"]["Filters"]
    }
    assert ec2_filters == {
        "regionCode": "us-west-2",
        "instanceType": "r7i.2xlarge",
        "operatingSystem": "Linux",
        "tenancy": "Shared",
        "preInstalledSw": "NA",
        "capacitystatus": "Used",
    }
    assert fsx_filters["throughputCapacity"] == "250"
    assert ipv4_filters["groupDescription"] == (
        "Hourly charge for In-use Public IPv4 Addresses"
    )


def test_scratch2_uses_the_lustre_storage_product_without_a_throughput_tier() -> None:
    client = FakePricingClient()

    estimate = estimate_idle_cluster_cost(
        client,
        region="us-west-2",
        headnode_instance_type="r7i.2xlarge",
        root_volume_type="gp3",
        root_volume_gib=421,
        fsx_deployment_type="SCRATCH_2",
        fsx_capacity_gib=2400,
    )

    fsx_call = next(call for call in client.calls if call["ServiceCode"] == "AmazonFSx")
    fsx_filters = {
        item["Field"]: item["Value"]
        for item in fsx_call["Filters"]
    }
    assert fsx_filters["throughputCapacity"] == "N/A"
    assert estimate.fsx_hourly_usd == Decimal("0.14") * 2400 / HOURS_PER_MONTH


def test_missing_authoritative_price_fails_closed() -> None:
    class MissingPricingClient:
        def get_products(self, **_kwargs):
            return {"PriceList": []}

    with pytest.raises(
        IdleCostPricingError,
        match="exactly one Hrs rate for Linux on-demand r7i.2xlarge",
    ):
        estimate_idle_cluster_cost(
            MissingPricingClient(),
            region="us-west-2",
            headnode_instance_type="r7i.2xlarge",
            root_volume_type="gp3",
            root_volume_gib=421,
            fsx_deployment_type="SCRATCH_2",
            fsx_capacity_gib=2400,
        )


def test_explicit_root_volume_performance_requires_a_supported_price_model() -> None:
    with pytest.raises(IdleCostPricingError, match="supports the rendered gp3"):
        estimate_idle_cluster_cost(
            FakePricingClient(),
            region="us-west-2",
            headnode_instance_type="r7i.2xlarge",
            root_volume_type="io2",
            root_volume_gib=421,
            fsx_deployment_type="SCRATCH_2",
            fsx_capacity_gib=2400,
        )
