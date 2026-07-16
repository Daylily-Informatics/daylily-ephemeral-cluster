from __future__ import annotations

from dataclasses import dataclass
import re

from daylily_ec.aws.pricing_snapshots import (
    DEFAULT_PRODUCTION_PARTITIONS,
    collect_pricing_snapshot,
    format_pricing_snapshot_table,
    load_partition_instance_types,
)


@dataclass
class _FakeEC2Client:
    region_name: str

    def describe_availability_zones(self, Filters=None):  # noqa: N803
        return {
            "AvailabilityZones": [
                {"ZoneName": f"{self.region_name}a", "ZoneId": "test-az1"},
                {"ZoneName": f"{self.region_name}b", "ZoneId": "test-az2"},
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
        deterministic_prices = {
            "test-a.2xlarge": "1.0",
            "test-b.2xlarge": "2.0",
            "test-c.2xlarge": "4.0",
        }
        if instance_type == "test-c.2xlarge" and AvailabilityZone.endswith("b"):
            return {"SpotPriceHistory": []}
        if instance_type in deterministic_prices:
            return {"SpotPriceHistory": [{"SpotPrice": deterministic_prices[instance_type]}]}
        if instance_type == "r7i.metal-48xl" and AvailabilityZone.endswith("b"):
            return {"SpotPriceHistory": []}
        return {
            "SpotPriceHistory": [
                {
                    "SpotPrice": "9.6" if "48xlarge" in instance_type or "metal" in instance_type else "0.8"
                }
            ]
        }

    def get_spot_placement_scores(  # noqa: N803
        self,
        InstanceTypes,
        TargetCapacity,
        TargetCapacityUnitType,
        SingleAvailabilityZone,
        RegionNames,
        MaxResults,
        NextToken=None,
    ):
        assert InstanceTypes
        assert TargetCapacity == 384
        assert TargetCapacityUnitType == "vcpu"
        assert SingleAvailabilityZone is True
        assert RegionNames == [self.region_name]
        assert MaxResults == 1000
        if NextToken is None:
            return {
                "SpotPlacementScores": [
                    {
                        "Region": self.region_name,
                        "AvailabilityZoneId": "test-az1",
                        "Score": 8,
                    }
                ],
                "NextToken": "page-2",
            }
        assert NextToken == "page-2"
        return {
            "SpotPlacementScores": [
                {
                    "Region": self.region_name,
                    "AvailabilityZoneId": "test-az2",
                    "Score": 5,
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
    assert "i4i.32xlarge" in mapping["i128nvme"]
    assert "c8id.96xlarge" in mapping["i384nvme"]


def test_collect_pricing_snapshot_returns_raw_points():
    snapshot = collect_pricing_snapshot(
        regions=["us-west-2"],
        partitions=["i192nvme"],
        captured_at="2026-03-08T12:00:00Z",
        session_factory=_fake_session_factory,
    )

    assert snapshot.captured_at == "2026-03-08T12:00:00Z"
    assert snapshot.regions == ["us-west-2"]
    assert snapshot.partitions == ["i192nvme"]
    assert snapshot.points

    first_point = snapshot.points[0]
    assert first_point.partition == "i192nvme"
    assert first_point.region == "us-west-2"
    assert first_point.availability_zone == "us-west-2a"
    assert first_point.vcpu_cost_per_hour == round(first_point.hourly_spot_price / first_point.vcpu_count, 8)


def test_collect_pricing_snapshot_skips_missing_prices():
    snapshot = collect_pricing_snapshot(
        regions=["us-west-2"],
        partitions=["i192nvme"],
        session_factory=_fake_session_factory,
    )
    skipped = [
        point
        for point in snapshot.points
        if point.instance_type == "r7i.metal-48xl" and point.availability_zone == "us-west-2b"
    ]
    assert skipped == []


def test_collect_pricing_snapshot_builds_summaries_and_placement_scores(tmp_path):
    config_path = tmp_path / "cluster.yaml"
    config_path.write_text(
        """Scheduling:
  SlurmQueues:
    - Name: i8
      ComputeResources:
        - Instances:
            - InstanceType: test-a.2xlarge
            - InstanceType: test-b.2xlarge
            - InstanceType: test-c.2xlarge
""",
        encoding="utf-8",
    )

    snapshot = collect_pricing_snapshot(
        regions=["us-west-2"],
        partitions=["i8"],
        cluster_config_path=str(config_path),
        target_capacity_vcpus=384,
        captured_at="2026-07-16T11:36:05Z",
        session_factory=_fake_session_factory,
    )

    assert snapshot.target_capacity_vcpus == 384
    assert len(snapshot.points) == 5
    assert len(snapshot.summaries) == 2
    zone_a, zone_b = snapshot.summaries
    assert zone_a.availability_zone == "us-west-2a"
    assert zone_a.priced_instance_count == 3
    assert zone_a.configured_instance_count == 3
    assert zone_a.price_coverage_percent == 100.0
    assert zone_a.min_hourly_spot_price == 1.0
    assert zone_a.median_hourly_spot_price == 2.0
    assert zone_a.harmonic_mean_hourly_spot_price == 1.71428571
    assert zone_a.max_hourly_spot_price == 4.0
    assert zone_a.spread_hourly_spot_price == 3.0
    assert zone_a.spot_placement_score == 8
    assert zone_b.availability_zone == "us-west-2b"
    assert zone_b.priced_instance_count == 2
    assert zone_b.price_coverage_percent == 66.67
    assert zone_b.median_hourly_spot_price == 1.5
    assert zone_b.harmonic_mean_hourly_spot_price == 1.33333333
    assert zone_b.spot_placement_score == 5
    payload = snapshot.to_dict()
    assert len(payload["points"]) == 5
    assert len(payload["summaries"]) == 2


def test_format_pricing_snapshot_table_renders_partition_zone_summaries():
    payload = {
        "captured_at": "2026-07-16T11:36:05Z",
        "cluster_config_path": "/tmp/cluster.yaml",
        "regions": ["us-west-2"],
        "partitions": ["i8"],
        "target_capacity_vcpus": 384,
        "summaries": [
            {
                "region": "us-west-2",
                "availability_zone": "us-west-2a",
                "partition": "i8",
                "priced_instance_count": 3,
                "configured_instance_count": 4,
                "price_coverage_percent": 75.0,
                "min_hourly_spot_price": 0.1734,
                "median_hourly_spot_price": 0.2,
                "harmonic_mean_hourly_spot_price": 0.19,
                "max_hourly_spot_price": 0.3,
                "spread_hourly_spot_price": 0.1266,
                "spot_placement_target_capacity_vcpus": 384,
                "spot_placement_score": 8,
            },
        ],
        "points": [{"raw": "point remains in JSON"}],
    }

    rendered = format_pricing_snapshot_table(payload)

    assert "Captured at: 2026-07-16T11:36:05Z" in rendered
    assert "Cluster config: /tmp/cluster.yaml" in rendered
    assert "Spot Placement Score target: 384 vCPUs" in rendered
    assert "Priced/Configured" in rendered
    assert "| us-west-2a" in rendered
    assert "3/4" in rendered
    assert "75.00%" in rendered
    assert "0.17340" in rendered
    assert "0.12660" in rendered
    assert re.search(r"\|\s+8\s+\|$", rendered, re.MULTILINE)
