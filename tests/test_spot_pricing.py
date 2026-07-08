"""Tests for daylily_ec.aws.spot_pricing."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from ruamel.yaml import YAML

from daylily_ec.aws.spot_pricing import (
    DEFAULT_GLOBAL_SPOT_MAX_COST,
    DEFAULT_SPOT_COST_LIMIT_PCT,
    DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD,
    MAX_GLOBAL_SPOT_MAX_COST,
    MAX_SPOT_COST_LIMIT_PCT,
    MIN_SPOT_COST_LIMIT_PCT,
    SPOT_PRICE_SUMMARY_SCHEMA_VERSION,
    apply_spot_prices,
    apply_spot_to_queue,
    calculate_compute_resource_spot_price,
    get_spot_price,
    process_slurm_queues,
    validate_spot_pricing_limits,
)


def _mock_ec2(price: float = 1.5) -> MagicMock:
    client = MagicMock()
    client.describe_spot_price_history.return_value = {
        "SpotPriceHistory": [{"SpotPrice": str(price)}],
    }
    _set_instance_vcpus(client, {})
    return client


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


def _queue(name: str, resources: list[dict]) -> dict:
    return {"Name": name, "ComputeResources": resources}


def _config(queues: list[dict]) -> dict:
    return {"Scheduling": {"SlurmQueues": queues}}


class TestConstants:
    def test_double_auth_default_sentinels(self) -> None:
        assert DEFAULT_GLOBAL_SPOT_MAX_COST == 7.50
        assert MAX_GLOBAL_SPOT_MAX_COST == 10.00
        assert DEFAULT_SPOT_COST_LIMIT_PCT == 1.2
        assert MIN_SPOT_COST_LIMIT_PCT == 1.0
        assert MAX_SPOT_COST_LIMIT_PCT == 1.4
        assert DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD == 6.00
        assert validate_spot_pricing_limits() == (7.50, 1.2, 6.00)


class TestGetSpotPrice:
    def test_returns_price(self) -> None:
        ec2 = _mock_ec2(2.0)
        assert get_spot_price(ec2, "m5.xlarge", "us-west-2a") == 2.0

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
        ec2.describe_spot_price_history.return_value = {
            "SpotPriceHistory": [{"SpotPrice": "N/A"}]
        }
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
            ({"global_spot_max_cost": 10.01}, "--global-spot-max-cost"),
            ({"global_spot_max_cost": 0}, "--global-spot-max-cost"),
            ({"spot_cost_limit_pct": 0.99}, "--spot-cost-limit-pct"),
            ({"spot_cost_limit_pct": 1.41}, "--spot-cost-limit-pct"),
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
            global_spot_max_cost=10.00,
        )
        assert result == 10.00

    def test_no_instances_returns_none(self) -> None:
        ec2 = _mock_ec2()
        assert calculate_compute_resource_spot_price(ec2, {"Instances": []}, "us-west-2a") is None


class TestProcessSlurmQueues:
    def test_sets_each_resource_from_reference_median_and_summary(self) -> None:
        ec2 = MagicMock()
        prices = {
            "c6i.32xlarge": "1.0",
            "c6i.metal": "3.0",
            "r6i.32xlarge": "9.0",
        }

        def _price_for(InstanceTypes, **_kwargs):
            return {"SpotPriceHistory": [{"SpotPrice": prices[InstanceTypes[0]]}]}

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
        assert resources[0]["SpotPrice"] == 2.4
        assert resources[1]["SpotPrice"] == 7.5
        assert summary["schema_version"] == SPOT_PRICE_SUMMARY_SCHEMA_VERSION
        assert summary["partitions"][0]["queue"] == "i128"
        assert summary["partitions"][0]["max_final_bid_usd_per_vcpu_hour"] == 0.0586
        assert summary["partitions"][0]["global_limiter_applied"] is True
        assert summary["partitions"][0]["warn_threshold_exceeded"] is True

    def test_i384_uses_i192_reference_median(self) -> None:
        ec2 = MagicMock()
        prices = {
            "c7i.48xlarge": "1.0",
            "c8i.96xlarge": "9.0",
        }

        def _price_for(InstanceTypes, **_kwargs):
            return {"SpotPriceHistory": [{"SpotPrice": prices[InstanceTypes[0]]}]}

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
        assert i384_resource["SpotPrice"] == 1.2
        i384_row = next(row for row in summary["resources"] if row["queue"] == "i384nvme")
        assert i384_row["reference_queue"] == "i192nvme"
        assert i384_row["reference_resource"] == "price192nvme"
        assert i384_row["reference_source"] == "i192_reference"
        assert i384_row["max_final_bid_usd_per_vcpu_hour"] == 0.0031

    def test_i384_missing_reference_fails_hard(self) -> None:
        ec2 = _mock_ec2(9.0)
        cfg = _config([_queue("i384nvme", [_resource("price384nvme", ["c8i.96xlarge"])])])

        with pytest.raises(RuntimeError, match="i384 reference spot data missing"):
            process_slurm_queues(cfg, "us-west-2a", ec2)

    def test_apply_spot_to_queue_uses_default_cap(self) -> None:
        ec2 = _mock_ec2(99.0)
        q = _queue("i128", [_resource("price128", ["m5.xlarge"])])
        summary = apply_spot_to_queue(ec2, q, "us-west-2a")
        assert q["ComputeResources"][0]["SpotPrice"] == 7.5
        assert summary["resources"][0]["global_limiter_applied"] is True

    def test_summary_tracks_partition_costs_and_warn_threshold_separately(self) -> None:
        ec2 = MagicMock()
        prices = {
            "c6i.16xlarge": "5.0",
            "c6i.32xlarge": "7.0",
        }

        def _price_for(InstanceTypes, **_kwargs):
            return {"SpotPriceHistory": [{"SpotPrice": prices[InstanceTypes[0]]}]}

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
            global_spot_max_cost=10.0,
            write_spot_pricing_warn_threshold=7.5,
        )

        row = summary["resources"][0]
        partition = summary["partitions"][0]
        assert row["raw_median_spot_price"] == 6.0
        assert row["uncapped_pct_bid"] == 7.2
        assert row["final_bid"] == 7.2
        assert row["warn_threshold_exceeded"] is False
        assert partition["raw_min_hourly_cost_without_limiter"] == 6.0
        assert partition["raw_max_hourly_cost_without_limiter"] == 18.0
        assert partition["max_reference_median_spot_price"] == 6.0
        assert partition["max_final_bid_usd_per_vcpu_hour"] == 0.1125
        assert partition["max_uncapped_pct_bid"] == 7.2
        assert partition["warn_threshold_exceeded"] is False


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
        - "6.00"
Scheduling:
  SlurmQueues:
    - Name: i128
      CustomActions:
        OnNodeConfigured:
          Script: s3://references/runtime_assets/cluster_boot_config/post_install_ubuntu_combined.sh
          Args:
            - us-west-2
            - s3://references/runtime_assets/cluster_boot_config
            - "6.00"
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
    assert written["Scheduling"]["SlurmQueues"][0]["ComputeResources"][0]["SpotPrice"] == 7.5
    headnode_args = written["HeadNode"]["CustomActions"]["OnNodeConfigured"]["Args"]
    queue_args = written["Scheduling"]["SlurmQueues"][0]["CustomActions"][
        "OnNodeConfigured"
    ]["Args"]
    assert headnode_args[2] == "6.00"
    assert queue_args[2] == "6.00"
    assert all(isinstance(arg, str) for arg in headnode_args)
    assert all(isinstance(arg, str) for arg in queue_args)
    persisted = json.loads(summary_path.read_text(encoding="utf-8"))
    assert persisted == summary
    assert persisted["resources"][0]["final_bid"] == 7.5
