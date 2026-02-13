"""Tests for daylily_ec.aws.spot_pricing — CP-012."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from daylily_ec.aws.spot_pricing import (
    DEFAULT_BUMP_PRICE,
    FALLBACK_SPOT_PRICE,
    apply_spot_to_queue,
    calculate_queue_spot_price,
    get_spot_price,
    process_slurm_queues,
)


# ── helpers ──────────────────────────────────────────────────────────


def _mock_ec2(price: float = 1.5) -> MagicMock:
    """Return a mock EC2 client that returns *price* for any instance."""
    client = MagicMock()
    client.describe_spot_price_history.return_value = {
        "SpotPriceHistory": [{"SpotPrice": str(price)}],
    }
    return client


def _queue(instance_types: list[str]) -> dict:
    return {
        "Name": "test-queue",
        "ComputeResources": [
            {"Instances": [{"InstanceType": t} for t in instance_types]}
        ],
    }


def _config(queues: list[dict]) -> dict:
    return {"Scheduling": {"SlurmQueues": queues}}


# ── TestConstants ────────────────────────────────────────────────────


class TestConstants:
    def test_default_bump_price(self):
        assert DEFAULT_BUMP_PRICE == 4.14

    def test_fallback_spot_price(self):
        assert FALLBACK_SPOT_PRICE == 5.55


# ── TestGetSpotPrice ─────────────────────────────────────────────────


class TestGetSpotPrice:
    def test_returns_price(self):
        ec2 = _mock_ec2(2.0)
        assert get_spot_price(ec2, "m5.xlarge", "us-west-2a") == 2.0

    def test_empty_history_returns_fallback(self):
        ec2 = MagicMock()
        ec2.describe_spot_price_history.return_value = {"SpotPriceHistory": []}
        assert get_spot_price(ec2, "m5.xlarge", "us-west-2a") == FALLBACK_SPOT_PRICE

    def test_api_error_raises_runtime(self):
        ec2 = MagicMock()
        ec2.describe_spot_price_history.side_effect = Exception("denied")
        with pytest.raises(RuntimeError, match="Spot price lookup failed"):
            get_spot_price(ec2, "m5.xlarge", "us-west-2a")

    def test_non_numeric_returns_fallback(self):
        ec2 = MagicMock()
        ec2.describe_spot_price_history.return_value = {
            "SpotPriceHistory": [{"SpotPrice": "N/A"}]
        }
        assert get_spot_price(ec2, "m5.xlarge", "us-west-2a") == FALLBACK_SPOT_PRICE

    def test_calls_correct_params(self):
        ec2 = _mock_ec2()
        get_spot_price(ec2, "r6i.8xlarge", "us-east-1b")
        ec2.describe_spot_price_history.assert_called_once_with(
            InstanceTypes=["r6i.8xlarge"],
            AvailabilityZone="us-east-1b",
            ProductDescriptions=["Linux/UNIX"],
            MaxResults=1,
        )


# ── TestCalculateQueueSpotPrice ──────────────────────────────────────


class TestCalculateQueueSpotPrice:
    def test_median_plus_bump(self):
        # Two instance types both at 1.0 → median 1.0 + bump 4.14 = 5.14
        ec2 = _mock_ec2(1.0)
        q = _queue(["m5.xlarge", "m5.2xlarge"])
        result = calculate_queue_spot_price(ec2, q, "us-west-2a")
        assert result == round(1.0 + DEFAULT_BUMP_PRICE, 4)

    def test_custom_bump(self):
        ec2 = _mock_ec2(2.0)
        q = _queue(["m5.xlarge"])
        result = calculate_queue_spot_price(ec2, q, "us-west-2a", bump_price=1.0)
        assert result == 3.0

    def test_no_instances_returns_none(self):
        ec2 = _mock_ec2()
        q = {"Name": "empty", "ComputeResources": [{"Instances": []}]}
        assert calculate_queue_spot_price(ec2, q, "us-west-2a") is None

    def test_empty_resources_returns_none(self):
        ec2 = _mock_ec2()
        q = {"Name": "empty", "ComputeResources": []}
        assert calculate_queue_spot_price(ec2, q, "us-west-2a") is None


# ── TestApplySpotToQueue ─────────────────────────────────────────────


class TestApplySpotToQueue:
    def test_sets_spot_price_on_resources(self):
        ec2 = _mock_ec2(1.0)
        q = _queue(["m5.xlarge"])
        apply_spot_to_queue(ec2, q, "us-west-2a")
        for r in q["ComputeResources"]:
            assert "SpotPrice" in r
            assert r["SpotPrice"] == round(1.0 + DEFAULT_BUMP_PRICE, 4)

    def test_no_op_when_no_prices(self):
        ec2 = _mock_ec2()
        q = {"Name": "empty", "ComputeResources": []}
        apply_spot_to_queue(ec2, q, "us-west-2a")
        # No crash, nothing set


# ── TestProcessSlurmQueues ───────────────────────────────────────────


class TestProcessSlurmQueues:
    def test_processes_multiple_queues(self):
        ec2 = _mock_ec2(1.0)
        cfg = _config([_queue(["m5.xlarge"]), _queue(["r6i.8xlarge"])])
        process_slurm_queues(cfg, "us-west-2a", ec2)
        for q in cfg["Scheduling"]["SlurmQueues"]:
            for r in q["ComputeResources"]:
                assert "SpotPrice" in r

    def test_empty_config_no_crash(self):
        ec2 = _mock_ec2()
        process_slurm_queues({}, "us-west-2a", ec2)

    def test_missing_scheduling_key(self):
        ec2 = _mock_ec2()
        process_slurm_queues({"Scheduling": {}}, "us-west-2a", ec2)

