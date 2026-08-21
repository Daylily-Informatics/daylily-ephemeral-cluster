"""Tests for daylily_ec.aws.spot_pricing."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from ruamel.yaml import YAML

from daylily_ec.aws.spot_pricing import (
    DEFAULT_GLOBAL_SPOT_MAX_COST,
    DEFAULT_SPOT_COST_LIMIT_PCT,
    DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD,
    F2_LOW_DIVERSITY_SPOT_COST_LIMIT_PCT,
    MAX_GLOBAL_SPOT_MAX_COST,
    MAX_SPOT_COST_LIMIT_PCT,
    MIN_SPOT_COST_LIMIT_PCT,
    SPOT_PRICE_SUMMARY_SCHEMA_VERSION,
    apply_spot_prices,
    apply_spot_to_queue,
    calculate_compute_resource_spot_price,
    get_fresh_spot_price_observation,
    get_spot_price,
    process_slurm_queues,
    validate_spot_pricing_limits,
)


def _mock_ec2(price: float = 1.5) -> MagicMock:
    client = MagicMock()
    client.describe_spot_price_history.return_value = {
        "SpotPriceHistory": [_fresh_spot_row(price)],
    }
    _set_instance_vcpus(client, {})
    return client


def _fresh_spot_row(price: float | str) -> dict[str, object]:
    return {
        "SpotPrice": str(price),
        "Timestamp": datetime.now(timezone.utc),
    }


def _set_instance_vcpus(client: MagicMock, counts: dict[str, int], default: int = 128) -> None:
    def _instance_types_for(InstanceTypes, **_kwargs):
        return {
            "InstanceTypes": [
                {
                    "InstanceType": instance_type,
                    "VCpuInfo": {
                        "DefaultVCpus": counts.get(instance_type, default),
                    },
                }
                for instance_type in InstanceTypes
            ]
        }

    client.describe_instance_types.side_effect = _instance_types_for


def _resource(
    name: str,
    instance_types: list[str],
    *,
    min_count: int = 0,
    max_count: int = 1,
) -> dict:
    return {
        "Name": name,
        "MinCount": min_count,
        "MaxCount": max_count,
        "Instances": [{"InstanceType": instance_type} for instance_type in instance_types],
    }


def _queue(
    name: str,
    resources: list[dict],
    *,
    capacity_type: str = "SPOT",
) -> dict:
    return {
        "Name": name,
        "CapacityType": capacity_type,
        "ComputeResources": resources,
    }


def _config(queues: list[dict]) -> dict:
    return {"Scheduling": {"SlurmQueues": queues}}


class TestConstants:
    def test_double_auth_default_sentinels(self) -> None:
        assert DEFAULT_GLOBAL_SPOT_MAX_COST == 9.99
        assert MAX_GLOBAL_SPOT_MAX_COST == 9.99
        assert DEFAULT_SPOT_COST_LIMIT_PCT == 1.70
        assert MIN_SPOT_COST_LIMIT_PCT == 1.0
        assert MAX_SPOT_COST_LIMIT_PCT == 2.20
        assert DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD == 8.00
        assert F2_LOW_DIVERSITY_SPOT_COST_LIMIT_PCT == 1.20
        assert validate_spot_pricing_limits() == (9.99, 1.70, 8.00)


class TestGetSpotPrice:
    def test_returns_price(self) -> None:
        ec2 = _mock_ec2(2.0)
        assert get_spot_price(ec2, "m5.xlarge", "us-west-2a") == 2.0

    def test_returns_named_product_price(self) -> None:
        ec2 = _mock_ec2(2.0)
        assert (
            get_spot_price(
                ec2,
                "f2.6xlarge",
                "us-west-2a",
                product_description="Red Hat Enterprise Linux",
            )
            == 2.0
        )
        ec2.describe_spot_price_history.assert_called_once_with(
            InstanceTypes=["f2.6xlarge"],
            AvailabilityZone="us-west-2a",
            ProductDescriptions=["Red Hat Enterprise Linux"],
            MaxResults=1,
        )


class TestFreshSpotPriceObservation:
    def test_records_live_capture_and_provider_effective_time(self) -> None:
        captured_at = datetime(2026, 8, 20, 18, 5, tzinfo=timezone.utc)
        provider_effective_at = captured_at - timedelta(seconds=90)
        ec2 = MagicMock()
        ec2.describe_spot_price_history.return_value = {
            "SpotPriceHistory": [
                {"SpotPrice": "1.25", "Timestamp": provider_effective_at}
            ]
        }

        result = get_fresh_spot_price_observation(
            ec2,
            "r7i.2xlarge",
            "us-west-2d",
            captured_at=captured_at,
        )

        assert result["observed_at"] == "2026-08-20T18:05:00Z"
        assert result["age_seconds"] == 0.0
        assert result["provider_effective_at"] == "2026-08-20T18:03:30Z"

    def test_accepts_long_lived_current_price(self) -> None:
        captured_at = datetime(2026, 8, 20, 18, 5, tzinfo=timezone.utc)
        provider_effective_at = captured_at - timedelta(days=30)
        ec2 = MagicMock()
        ec2.describe_spot_price_history.return_value = {
            "SpotPriceHistory": [
                {"SpotPrice": "1.25", "Timestamp": provider_effective_at}
            ]
        }

        result = get_fresh_spot_price_observation(
            ec2,
            "r7i.2xlarge",
            "us-west-2d",
            captured_at=captured_at,
        )

        assert result["observed_at"] == "2026-08-20T18:05:00Z"
        assert result["age_seconds"] == 0.0
        assert result["provider_effective_at"] == "2026-07-21T18:05:00Z"

    def test_rejects_future_provider_effective_time(self) -> None:
        captured_at = datetime(2026, 8, 20, 18, 5, tzinfo=timezone.utc)
        ec2 = MagicMock()
        ec2.describe_spot_price_history.return_value = {
            "SpotPriceHistory": [
                {
                    "SpotPrice": "1.25",
                    "Timestamp": captured_at + timedelta(seconds=301),
                }
            ]
        }
        with pytest.raises(RuntimeError, match="future"):
            get_fresh_spot_price_observation(
                ec2,
                "r7i.2xlarge",
                "us-west-2d",
                captured_at=captured_at,
            )

    def test_provider_error_does_not_surface_sdk_text(self) -> None:
        ec2 = MagicMock()
        ec2.describe_spot_price_history.side_effect = RuntimeError("secret provider token")
        with pytest.raises(RuntimeError) as captured:
            get_fresh_spot_price_observation(
                ec2,
                "r7i.2xlarge",
                "us-west-2d",
            )
        assert "secret provider token" not in str(captured.value)

    def test_empty_history_fails_hard(self) -> None:
        ec2 = MagicMock()
        ec2.describe_spot_price_history.return_value = {"SpotPriceHistory": []}
        with pytest.raises(RuntimeError, match="returned no price history"):
            get_spot_price(ec2, "m5.xlarge", "us-west-2a")

    def test_api_error_raises_runtime(self) -> None:
        ec2 = MagicMock()
        ec2.describe_spot_price_history.side_effect = Exception("denied")
        with pytest.raises(RuntimeError, match="Spot price lookup failed"):
            get_spot_price(ec2, "m5.xlarge", "us-west-2a")

    def test_non_numeric_fails_hard(self) -> None:
        ec2 = MagicMock()
        ec2.describe_spot_price_history.return_value = {"SpotPriceHistory": [{"SpotPrice": "N/A"}]}
        with pytest.raises(RuntimeError, match="non-numeric SpotPrice"):
            get_spot_price(ec2, "m5.xlarge", "us-west-2a")

    def test_calls_correct_params(self) -> None:
        ec2 = _mock_ec2()
        get_spot_price(ec2, "r6i.8xlarge", "us-east-1b")
        ec2.describe_spot_price_history.assert_called_once_with(
            InstanceTypes=["r6i.8xlarge"],
            AvailabilityZone="us-east-1b",
            ProductDescriptions=["Linux/UNIX"],
            MaxResults=1,
        )


class TestValidation:
    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"global_spot_max_cost": 10.00}, "--global-spot-max-cost"),
            ({"global_spot_max_cost": 0}, "--global-spot-max-cost"),
            ({"spot_cost_limit_pct": 0.99}, "--spot-cost-limit-pct"),
            ({"spot_cost_limit_pct": 2.21}, "--spot-cost-limit-pct"),
            (
                {"write_spot_pricing_warn_threshold": 0},
                "--write-spot-pricing-warn-threshold",
            ),
        ],
    )
    def test_invalid_limits_fail(self, kwargs: dict, message: str) -> None:
        with pytest.raises(ValueError, match=message):
            validate_spot_pricing_limits(**kwargs)


class TestCalculateComputeResourceSpotPrice:
    def test_default_capped_percentage_bid(self) -> None:
        ec2 = _mock_ec2(9.0)
        resource = _resource("price128", ["m5.xlarge", "m5.2xlarge"])
        result = calculate_compute_resource_spot_price(ec2, resource, "us-west-2a")
        assert result == DEFAULT_GLOBAL_SPOT_MAX_COST

    def test_custom_global_cap(self) -> None:
        ec2 = _mock_ec2(9.0)
        resource = _resource("price128", ["m5.xlarge"])
        result = calculate_compute_resource_spot_price(
            ec2,
            resource,
            "us-west-2a",
            global_spot_max_cost=9.50,
        )
        assert result == 9.50

    def test_no_instances_returns_none(self) -> None:
        ec2 = _mock_ec2()
        assert calculate_compute_resource_spot_price(ec2, {"Instances": []}, "us-west-2a") is None


class TestProcessSlurmQueues:
    def test_skips_ondemand_queues_without_spot_lookups_or_spotprice(self) -> None:
        ec2 = _mock_ec2(0.8)
        spot_resource = _resource("f26xlarge", ["f2.6xlarge"])
        ondemand_resource = _resource("f26xlargeod", ["f2.6xlarge"])
        cfg = _config(
            [
                _queue("dragen", [spot_resource]),
                _queue(
                    "dragen-ondemand",
                    [ondemand_resource],
                    capacity_type="ONDEMAND",
                ),
            ]
        )

        summary = process_slurm_queues(cfg, "us-west-2c", ec2)

        assert spot_resource["SpotPrice"] == 0.96
        assert "SpotPrice" not in ondemand_resource
        assert [row["queue"] for row in summary["resources"]] == ["dragen"]
        assert [row["queue"] for row in summary["partitions"]] == ["dragen"]
        ec2.describe_spot_price_history.assert_called_once()

    def test_sets_each_resource_from_reference_median_and_summary(self) -> None:
        ec2 = MagicMock()
        prices = {
            "c6i.32xlarge": "1.0",
            "c6i.metal": "3.0",
            "r6i.32xlarge": "9.0",
        }

        def _price_for(InstanceTypes, **_kwargs):
            return {"SpotPriceHistory": [_fresh_spot_row(prices[InstanceTypes[0]])]}

        ec2.describe_spot_price_history.side_effect = _price_for
        _set_instance_vcpus(
            ec2,
            {
                "c6i.32xlarge": 128,
                "c6i.metal": 128,
                "r6i.32xlarge": 128,
            },
        )
        cfg = _config(
            [
                _queue(
                    "i128",
                    [
                        _resource("price128", ["c6i.32xlarge", "c6i.metal"], max_count=2),
                        _resource("mem128", ["r6i.32xlarge"], max_count=1),
                    ],
                )
            ]
        )

        summary = process_slurm_queues(cfg, "us-west-2a", ec2)

        resources = cfg["Scheduling"]["SlurmQueues"][0]["ComputeResources"]
        assert resources[0]["SpotPrice"] == 3.4
        assert resources[1]["SpotPrice"] == 9.99
        assert summary["schema_version"] == SPOT_PRICE_SUMMARY_SCHEMA_VERSION
        assert summary["partitions"][0]["queue"] == "i128"
        assert summary["partitions"][0]["max_final_bid_usd_per_vcpu_hour"] == 0.0780
        assert summary["partitions"][0]["global_limiter_applied"] is True
        assert summary["partitions"][0]["warn_threshold_exceeded"] is True

    def test_i384_uses_its_own_reference_median(self) -> None:
        ec2 = MagicMock()
        prices = {
            "c7i.48xlarge": "1.0",
            "c8i.96xlarge": "9.0",
        }

        def _price_for(InstanceTypes, **_kwargs):
            return {"SpotPriceHistory": [_fresh_spot_row(prices[InstanceTypes[0]])]}

        ec2.describe_spot_price_history.side_effect = _price_for
        _set_instance_vcpus(ec2, {"c7i.48xlarge": 192, "c8i.96xlarge": 384})
        cfg = _config(
            [
                _queue("i192nvme", [_resource("price192nvme", ["c7i.48xlarge"])]),
                _queue("i384nvme", [_resource("price384nvme", ["c8i.96xlarge"])]),
            ]
        )

        summary = process_slurm_queues(cfg, "us-west-2a", ec2)

        i384_resource = cfg["Scheduling"]["SlurmQueues"][1]["ComputeResources"][0]
        assert i384_resource["SpotPrice"] == 9.99
        i384_row = next(row for row in summary["resources"] if row["queue"] == "i384nvme")
        assert i384_row["reference_queue"] == "i384nvme"
        assert i384_row["reference_resource"] == "price384nvme"
        assert i384_row["reference_source"] == "self"
        assert i384_row["max_final_bid_usd_per_vcpu_hour"] == 0.0260

    def test_i384_without_an_i192_reference_uses_its_own_price(self) -> None:
        ec2 = _mock_ec2(9.0)
        cfg = _config([_queue("i384nvme", [_resource("price384nvme", ["c8i.96xlarge"])])])

        summary = process_slurm_queues(cfg, "us-west-2a", ec2)
        assert cfg["Scheduling"]["SlurmQueues"][0]["ComputeResources"][0]["SpotPrice"] == 9.99
        assert summary["resources"][0]["reference_source"] == "self"

    def test_f2_low_diversity_partition_uses_linux_price_plus_twenty_percent(self) -> None:
        ec2 = MagicMock()
        prices = {
            ("f2.6xlarge", "Linux/UNIX"): "0.8013",
        }

        def _price_for(InstanceTypes, ProductDescriptions, **_kwargs):
            return {
                "SpotPriceHistory": [
                    _fresh_spot_row(prices[(InstanceTypes[0], ProductDescriptions[0])])
                ]
            }

        ec2.describe_spot_price_history.side_effect = _price_for
        _set_instance_vcpus(ec2, {"f2.6xlarge": 24})
        cfg = _config(
            [
                _queue(
                    "dragen",
                    [_resource("f26xlarge", ["f2.6xlarge"], max_count=1)],
                )
            ]
        )

        summary = process_slurm_queues(cfg, "us-west-2c", ec2)

        resource = cfg["Scheduling"]["SlurmQueues"][0]["ComputeResources"][0]
        row = summary["resources"][0]
        assert resource["SpotPrice"] == 0.9616
        assert row["raw_max_spot_price"] == 0.8013
        assert row["reference_resource"] == "partition_max"
        assert row["reference_source"] == "f2_partition_max"
        assert row["reference_median_spot_price"] == 0.8013
        assert row["spot_cost_limit_pct"] == 1.20
        ec2.describe_spot_price_history.assert_called_once()
        assert ec2.describe_spot_price_history.call_args.kwargs["ProductDescriptions"] == [
            "Linux/UNIX"
        ]

    def test_f2_low_diversity_partition_uses_partition_max_price(self) -> None:
        ec2 = MagicMock()
        prices = {
            ("f2.6xlarge", "Linux/UNIX"): "0.80",
            ("c6i.8xlarge", "Linux/UNIX"): "2.00",
        }

        def _price_for(InstanceTypes, ProductDescriptions, **_kwargs):
            return {
                "SpotPriceHistory": [
                    _fresh_spot_row(prices[(InstanceTypes[0], ProductDescriptions[0])])
                ]
            }

        ec2.describe_spot_price_history.side_effect = _price_for
        _set_instance_vcpus(ec2, {"f2.6xlarge": 24, "c6i.8xlarge": 32})
        cfg = _config(
            [
                _queue(
                    "dragen",
                    [
                        _resource("f26xlarge", ["f2.6xlarge"], max_count=1),
                        _resource("i8xlarge", ["c6i.8xlarge"], max_count=1),
                    ],
                )
            ]
        )

        summary = process_slurm_queues(cfg, "us-west-2c", ec2)

        resources = cfg["Scheduling"]["SlurmQueues"][0]["ComputeResources"]
        f2_row = next(row for row in summary["resources"] if row["resource"] == "f26xlarge")
        non_f2_row = next(row for row in summary["resources"] if row["resource"] == "i8xlarge")
        assert resources[0]["SpotPrice"] == 2.4
        assert f2_row["reference_resource"] == "partition_max"
        assert f2_row["reference_median_spot_price"] == 2.0
        assert non_f2_row["reference_source"] == "self"
        assert non_f2_row["reference_median_spot_price"] == 2.0

    def test_f2_partition_max_rule_requires_less_than_three_max_instances(self) -> None:
        ec2 = MagicMock()
        prices = {
            ("f2.6xlarge", "Linux/UNIX"): "0.80",
            ("c6i.8xlarge", "Linux/UNIX"): "2.00",
        }

        def _price_for(InstanceTypes, ProductDescriptions, **_kwargs):
            return {
                "SpotPriceHistory": [
                    _fresh_spot_row(prices[(InstanceTypes[0], ProductDescriptions[0])])
                ]
            }

        ec2.describe_spot_price_history.side_effect = _price_for
        _set_instance_vcpus(ec2, {"f2.6xlarge": 24, "c6i.8xlarge": 32})
        cfg = _config(
            [
                _queue(
                    "dragen",
                    [
                        _resource("f26xlarge", ["f2.6xlarge"], max_count=3),
                        _resource("i8xlarge", ["c6i.8xlarge"], max_count=1),
                    ],
                )
            ]
        )

        summary = process_slurm_queues(cfg, "us-west-2c", ec2)

        f2_resource = cfg["Scheduling"]["SlurmQueues"][0]["ComputeResources"][0]
        f2_row = next(row for row in summary["resources"] if row["resource"] == "f26xlarge")
        assert f2_resource["SpotPrice"] == 1.36
        assert f2_row["reference_resource"] == "f26xlarge"
        assert f2_row["reference_source"] == "self"
        assert f2_row["reference_median_spot_price"] == 0.8

    def test_apply_spot_to_queue_uses_default_cap(self) -> None:
        ec2 = _mock_ec2(99.0)
        q = _queue("i128", [_resource("price128", ["m5.xlarge"])])
        summary = apply_spot_to_queue(ec2, q, "us-west-2a")
        assert q["ComputeResources"][0]["SpotPrice"] == 9.99
        assert summary["resources"][0]["global_limiter_applied"] is True

    def test_summary_tracks_partition_costs_and_warn_threshold_separately(self) -> None:
        ec2 = MagicMock()
        prices = {
            "c6i.16xlarge": "5.0",
            "c6i.32xlarge": "7.0",
        }

        def _price_for(InstanceTypes, **_kwargs):
            return {"SpotPriceHistory": [_fresh_spot_row(prices[InstanceTypes[0]])]}

        ec2.describe_spot_price_history.side_effect = _price_for
        _set_instance_vcpus(ec2, {"c6i.16xlarge": 64, "c6i.32xlarge": 128})
        cfg = _config(
            [
                _queue(
                    "i128",
                    [
                        _resource(
                            "price128",
                            ["c6i.16xlarge", "c6i.32xlarge"],
                            min_count=1,
                            max_count=3,
                        )
                    ],
                )
            ]
        )

        summary = process_slurm_queues(
            cfg,
            "us-west-2a",
            ec2,
            global_spot_max_cost=9.99,
            write_spot_pricing_warn_threshold=7.5,
        )

        row = summary["resources"][0]
        partition = summary["partitions"][0]
        assert row["raw_median_spot_price"] == 6.0
        assert row["uncapped_pct_bid"] == 10.2
        assert row["final_bid"] == 9.99
        assert row["warn_threshold_exceeded"] is True
        assert partition["raw_min_hourly_cost_without_limiter"] == 6.0
        assert partition["raw_max_hourly_cost_without_limiter"] == 18.0
        assert partition["max_reference_median_spot_price"] == 6.0
        assert partition["max_final_bid_usd_per_vcpu_hour"] == 0.1561
        assert partition["max_uncapped_pct_bid"] == 10.2
        assert partition["warn_threshold_exceeded"] is True


def test_apply_spot_prices_writes_cluster_yaml_and_summary(tmp_path: Path) -> None:
    ec2 = _mock_ec2(9.0)
    source = tmp_path / "init.yaml"
    output = tmp_path / "cluster.yaml"
    summary_path = tmp_path / "summary.json"
    source.write_text(
        """
HeadNode:
  CustomActions:
    OnNodeConfigured:
      Script: s3://references/runtime_assets/cluster_boot_config/post_install_ubuntu_combined.sh
      Args:
        - us-west-2
        - s3://references/runtime_assets/cluster_boot_config
        - "8.00"
Scheduling:
  SlurmQueues:
    - Name: i128
      CapacityType: SPOT
      CustomActions:
        OnNodeConfigured:
          Script: s3://references/runtime_assets/cluster_boot_config/post_install_ubuntu_combined.sh
          Args:
            - us-west-2
            - s3://references/runtime_assets/cluster_boot_config
            - "8.00"
      ComputeResources:
        - Name: price128
          MinCount: 0
          MaxCount: 1
          Instances:
            - InstanceType: c6i.32xlarge
""".lstrip(),
        encoding="utf-8",
    )

    summary = apply_spot_prices(
        str(source),
        str(output),
        "us-west-2a",
        ec2_client=ec2,
        summary_output_path=summary_path,
    )

    yaml = YAML(typ="safe")
    written = yaml.load(output.read_text(encoding="utf-8"))
    assert written["Scheduling"]["SlurmQueues"][0]["ComputeResources"][0]["SpotPrice"] == 9.99
    headnode_args = written["HeadNode"]["CustomActions"]["OnNodeConfigured"]["Args"]
    queue_args = written["Scheduling"]["SlurmQueues"][0]["CustomActions"]["OnNodeConfigured"][
        "Args"
    ]
    assert headnode_args[2] == "8.00"
    assert queue_args[2] == "8.00"
    assert all(isinstance(arg, str) for arg in headnode_args)
    assert all(isinstance(arg, str) for arg in queue_args)
    persisted = json.loads(summary_path.read_text(encoding="utf-8"))
    assert persisted == summary
    assert persisted["resources"][0]["final_bid"] == 9.99
