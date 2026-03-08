from __future__ import annotations

from dataclasses import dataclass

from daylily_ec.aws.pricing_snapshots import (
    DEFAULT_PRODUCTION_PARTITIONS,
    collect_pricing_snapshot,
    load_partition_instance_types,
)


@dataclass
class _FakeEC2Client:
    region_name: str

    def describe_availability_zones(self, Filters=None):  # noqa: N803
        return {
            "AvailabilityZones": [
                {"ZoneName": f"{self.region_name}a"},
                {"ZoneName": f"{self.region_name}b"},
            ]
        }

    def describe_instance_types(self, InstanceTypes):  # noqa: N803
        return {
            "InstanceTypes": [
                {
                    "InstanceType": instance_type,
                    "VCpuInfo": {"DefaultVCpus": 192 if "48xlarge" in instance_type or "metal" in instance_type else 8},
                }
                for instance_type in InstanceTypes
            ]
        }

    def describe_spot_price_history(  # noqa: N803
        self,
        InstanceTypes,
        AvailabilityZone,
        ProductDescriptions,
        MaxResults,
    ):
        instance_type = InstanceTypes[0]
        if instance_type == "r7i.metal-48xl" and AvailabilityZone.endswith("b"):
            return {"SpotPriceHistory": []}
        return {
            "SpotPriceHistory": [
                {
                    "SpotPrice": "9.6" if "48xlarge" in instance_type or "metal" in instance_type else "0.8"
                }
            ]
        }


@dataclass
class _FakeSession:
    def client(self, service_name: str, region_name: str):
        assert service_name == "ec2"
        return _FakeEC2Client(region_name=region_name)


def _fake_session_factory(profile: str | None):
    return _FakeSession()


def test_load_partition_instance_types_reads_packaged_prod_config():
    mapping = load_partition_instance_types()
    assert tuple(mapping.keys()) == DEFAULT_PRODUCTION_PARTITIONS
    assert "c7i.48xlarge" in mapping["i192"]
    assert "r7i.48xlarge" in mapping["i192bigmem"]


def test_collect_pricing_snapshot_returns_raw_points():
    snapshot = collect_pricing_snapshot(
        regions=["us-west-2"],
        partitions=["i192bigmem"],
        captured_at="2026-03-08T12:00:00Z",
        session_factory=_fake_session_factory,
    )

    assert snapshot.captured_at == "2026-03-08T12:00:00Z"
    assert snapshot.regions == ["us-west-2"]
    assert snapshot.partitions == ["i192bigmem"]
    assert snapshot.points

    first_point = snapshot.points[0]
    assert first_point.partition == "i192bigmem"
    assert first_point.region == "us-west-2"
    assert first_point.availability_zone == "us-west-2a"
    assert first_point.vcpu_cost_per_hour == round(first_point.hourly_spot_price / first_point.vcpu_count, 8)


def test_collect_pricing_snapshot_skips_missing_prices():
    snapshot = collect_pricing_snapshot(
        regions=["us-west-2"],
        partitions=["i192bigmem"],
        session_factory=_fake_session_factory,
    )
    skipped = [
        point
        for point in snapshot.points
        if point.instance_type == "r7i.metal-48xl" and point.availability_zone == "us-west-2b"
    ]
    assert skipped == []
