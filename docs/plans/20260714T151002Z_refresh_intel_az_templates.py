#!/usr/bin/env python3
"""Audit and refresh active Intel AZ templates from authoritative EC2 offerings.

Default mode is a read-only plan. ``--write`` applies the deterministic source
changes and refreshes packaged mirrors. ``--check`` fails if either source or
payload would change. The script never creates, updates, or deletes AWS
resources.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

import boto3
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_INTEL_ROOT = REPO_ROOT / "config/day_cluster/intel"
PAYLOAD_ROOT = REPO_ROOT / "daylily_ec/resources/payload"
SENTIEON_RELPATH = Path(
    "config/day_cluster/sentieon-single/us-west-2/us-west-2c/"
    "prod_cluster_sentieon-single_us-west-2c.yaml"
)
TARGET_REGION_AZS = (
    "ap-south-1a",
    "ap-south-1b",
    "ap-south-1c",
    "eu-central-1a",
    "eu-central-1b",
    "eu-central-1c",
    "us-east-2a",
    "us-east-2b",
    "us-east-2c",
    "us-west-1a",
    "us-west-1b",
    "us-west-2a",
    "us-west-2b",
    "us-west-2c",
    "us-west-2d",
)
QUEUE_START = re.compile(r"^  - Name: ([A-Za-z0-9_-]+)\s*$")
MODERN_CPU_FAMILY = re.compile(r"^(?:c[5-9]|m[5-9]|r[5-9]|i(?:3en|4i|7i|7ie)|x(?:2|8))")
ACCELERATOR_KEYS = (
    "FpgaInfo",
    "GpuInfo",
    "InferenceAcceleratorInfo",
    "MediaAcceleratorInfo",
    "NeuronInfo",
)


def region_for_az(region_az: str) -> str:
    region = region_az[:-1]
    if not region or not region_az.startswith(region):
        raise ValueError(f"Invalid availability zone name: {region_az}")
    return region


def intel_relpath(region_az: str) -> Path:
    region = region_for_az(region_az)
    return Path(
        f"config/day_cluster/intel/{region}/{region_az}/"
        f"prod_cluster_intel_{region_az}.yaml"
    )


def queue_ranges(text: str) -> dict[str, tuple[int, int]]:
    lines = text.splitlines(keepends=True)
    starts: list[tuple[str, int]] = []
    for index, line in enumerate(lines):
        match = QUEUE_START.match(line.rstrip("\n"))
        if match:
            starts.append((match.group(1), index))
    ranges: dict[str, tuple[int, int]] = {}
    for offset, (name, start) in enumerate(starts):
        end = starts[offset + 1][1] if offset + 1 < len(starts) else len(lines)
        if name in ranges:
            raise ValueError(f"Duplicate Slurm queue in template: {name}")
        ranges[name] = (start, end)
    return ranges


def replace_or_insert_queue(text: str, *, name: str, block: str, before: str) -> str:
    lines = text.splitlines(keepends=True)
    ranges = queue_ranges(text)
    if name in ranges:
        start, end = ranges[name]
        lines[start:end] = block.splitlines(keepends=True)
        return "".join(lines)
    if before not in ranges:
        raise ValueError(f"Cannot insert {name}: required following queue {before} is absent")
    start, _end = ranges[before]
    lines[start:start] = block.splitlines(keepends=True)
    return "".join(lines)


def remove_queue(text: str, name: str) -> str:
    lines = text.splitlines(keepends=True)
    ranges = queue_ranges(text)
    if name not in ranges:
        return text
    start, end = ranges[name]
    del lines[start:end]
    return "".join(lines)


def instance_types(resource: dict[str, Any]) -> list[str]:
    return [
        str(item.get("InstanceType") or "")
        for item in (resource.get("Instances") or [])
        if str(item.get("InstanceType") or "")
    ]


def all_listed_types(payload: dict[str, Any]) -> set[str]:
    return {
        instance_type
        for queue in payload["Scheduling"]["SlurmQueues"]
        for resource in queue["ComputeResources"]
        for instance_type in instance_types(resource)
    }


def total_instance_storage_gb(spec: dict[str, Any]) -> int:
    return sum(
        int(disk.get("Count") or 0) * int(disk.get("SizeInGB") or 0)
        for disk in (spec.get("InstanceStorageInfo") or {}).get("Disks", [])
    )


def eligible_cpu_type(spec: dict[str, Any]) -> bool:
    instance_type = str(spec.get("InstanceType") or "")
    family = instance_type.split(".", 1)[0]
    manufacturer = str((spec.get("ProcessorInfo") or {}).get("Manufacturer") or "")
    return (
        bool(MODERN_CPU_FAMILY.match(family))
        and "intel" in manufacturer.lower()
        and bool(spec.get("InstanceStorageSupported"))
        and not any(spec.get(key) for key in ACCELERATOR_KEYS)
    )


def candidate_specs(ec2: Any) -> dict[int, dict[str, dict[str, Any]]]:
    filters = [
        {"Name": "vcpu-info.default-vcpus", "Values": ["8", "96", "384"]},
        {"Name": "instance-storage-supported", "Values": ["true"]},
        {"Name": "processor-info.supported-architecture", "Values": ["x86_64"]},
    ]
    by_vcpu: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
    paginator = ec2.get_paginator("describe_instance_types")
    for page in paginator.paginate(Filters=filters):
        for spec in page.get("InstanceTypes", []):
            if not eligible_cpu_type(spec):
                continue
            vcpus = int((spec.get("VCpuInfo") or {}).get("DefaultVCpus") or 0)
            by_vcpu[vcpus][str(spec["InstanceType"])] = spec
    return dict(by_vcpu)


def offered_types(ec2: Any, *, region_az: str, candidates: set[str]) -> set[str]:
    offered: set[str] = set()
    values = sorted(candidates)
    for offset in range(0, len(values), 100):
        response = ec2.describe_instance_type_offerings(
            LocationType="availability-zone",
            Filters=[
                {"Name": "location", "Values": [region_az]},
                {"Name": "instance-type", "Values": values[offset : offset + 100]},
            ],
        )
        offered.update(
            str(item["InstanceType"])
            for item in response.get("InstanceTypeOfferings", [])
        )
    return offered


def linux_spot_types(ec2: Any, *, region_az: str, candidates: set[str]) -> set[str]:
    seen: set[str] = set()
    values = sorted(candidates)
    end_time = datetime.now(timezone.utc)
    # EC2 returns the current/latest Linux Spot price for each requested type
    # when StartTime equals EndTime, avoiding an unbounded history download.
    start_time = end_time
    for offset in range(0, len(values), 100):
        next_token: str | None = None
        while True:
            request: dict[str, Any] = {
                "AvailabilityZone": region_az,
                "InstanceTypes": values[offset : offset + 100],
                "ProductDescriptions": ["Linux/UNIX"],
                "StartTime": start_time,
                "EndTime": end_time,
                "MaxResults": 1000,
            }
            if next_token:
                request["NextToken"] = next_token
            response = ec2.describe_spot_price_history(**request)
            seen.update(
                str(item["InstanceType"])
                for item in response.get("SpotPriceHistory", [])
            )
            next_token = response.get("NextToken")
            if not next_token:
                break
    return seen


def queue_block(
    *,
    queue_name: str,
    resource_name: str,
    types: list[str],
    max_count: str,
    allocation_strategy: str,
) -> str:
    if not types:
        raise ValueError(f"Refusing to render empty queue {queue_name}")
    instance_lines = "".join(f"      - InstanceType: {item}\n" for item in types)
    return (
        f"  - Name: {queue_name}\n"
        "    JobExclusiveAllocation: false\n"
        "    CapacityType: SPOT\n"
        f"    AllocationStrategy: {allocation_strategy}\n"
        "    ComputeSettings:\n"
        "      LocalStorage:\n"
        "        EphemeralVolume:\n"
        "          MountDir: /scratch\n"
        "    ComputeResources:\n"
        f"    - Name: {resource_name}\n"
        "      Instances:\n"
        f"{instance_lines}"
        "      MinCount: 0\n"
        f"      MaxCount: {max_count}\n"
        "      SpotPrice: CALCULATE_MAX_SPOT_PRICE\n"
        "      DynamicNodePriority: 100\n"
        "      Networking:\n"
        "        PlacementGroup:\n"
        "          Enabled: false\n"
        "      Efa:\n"
        "        Enabled: false\n"
        "    Networking:\n"
        "      SubnetIds:\n"
        "      - ${REGSUB_PRIVATE_SUBNET}\n"
        "    CustomActions:\n"
        "      OnNodeConfigured:\n"
        "        Script: ${REGSUB_S3_BUCKET_INIT}/post_install_ubuntu_combined.sh\n"
        "        Args:\n"
        "        - ${REGSUB_REGION}\n"
        "        - ${REGSUB_S3_BUCKET_INIT}\n"
        "        - ${REGSUB_SPOT_PRICE_WARN_THRESHOLD}\n"
        "    Iam:\n"
        "      S3Access:\n"
        "      - BucketName: ${REGSUB_S3_REFERENCE_BUCKET}\n"
        "        EnableWriteAccess: false\n"
        "      - BucketName: ${REGSUB_S3_CONTROL_DATA_BUCKET}\n"
        "        EnableWriteAccess: false\n"
        "      - BucketName: ${REGSUB_S3_STAGE_BUCKET}\n"
        "        EnableWriteAccess: false\n"
        "      - BucketName: ${REGSUB_S3_EXPORT_BUCKET}\n"
        "        EnableWriteAccess: true\n"
        "      AdditionalIamPolicies:\n"
        "      - Policy: ${REGSUB_S3_IAM_POLICY}\n"
        "      - Policy: arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore\n"
    )


def validate_rendered_template(
    *,
    path: Path,
    text: str,
    region_az: str,
    offered: set[str],
    expected_i96: list[str] | None,
) -> None:
    payload = yaml.safe_load(text)
    queues = payload["Scheduling"]["SlurmQueues"]
    queue_names = [str(queue["Name"]) for queue in queues]
    if len(queue_names) != len(set(queue_names)):
        raise ValueError(f"{path}: duplicate queue name")
    for queue in queues:
        for resource in queue["ComputeResources"]:
            listed = instance_types(resource)
            if not listed:
                raise ValueError(
                    f"{path}: {queue['Name']}/{resource['Name']} has no instance types"
                )
            unavailable = sorted(set(listed) - offered)
            if unavailable:
                raise ValueError(
                    f"{path}: {queue['Name']}/{resource['Name']} contains unavailable "
                    f"types in {region_az}: {', '.join(unavailable)}"
                )
    if expected_i96 is not None:
        i96 = next((queue for queue in queues if queue["Name"] == "i96nvme"), None)
        if i96 is None:
            raise ValueError(f"{path}: i96nvme is absent")
        resources = i96["ComputeResources"]
        if len(resources) != 1 or instance_types(resources[0]) != expected_i96:
            raise ValueError(f"{path}: i96nvme does not match the audited AZ pool")
        if resources[0].get("MaxCount") != "${REGSUB_MAX_COUNT_96I_NVME}":
            raise ValueError(f"{path}: i96nvme has the wrong MaxCount token")


def refresh_intel_template(
    *,
    path: Path,
    region_az: str,
    offered: set[str],
    candidates_96: list[str],
    candidates_384: list[str],
) -> str:
    original = path.read_text(encoding="utf-8")
    payload = yaml.safe_load(original)
    unmanaged_types = {
        instance_type
        for queue in payload["Scheduling"]["SlurmQueues"]
        if queue["Name"] not in {"i96nvme", "i384nvme"}
        for resource in queue["ComputeResources"]
        for instance_type in instance_types(resource)
    }
    unavailable = sorted(unmanaged_types - offered)
    if unavailable:
        raise ValueError(
            f"{path}: existing instance types are no longer offered in {region_az}: "
            + ", ".join(unavailable)
        )
    updated = original
    i384 = next(
        (
            queue
            for queue in payload["Scheduling"]["SlurmQueues"]
            if queue["Name"] == "i384nvme"
        ),
        None,
    )
    if i384 is not None:
        if not candidates_384:
            updated = remove_queue(updated, "i384nvme")
        elif any(not instance_types(resource) for resource in i384["ComputeResources"]):
            updated = replace_or_insert_queue(
                updated,
                name="i384nvme",
                before="i192hugenvme",
                block=queue_block(
                    queue_name="i384nvme",
                    resource_name="price384nvme",
                    types=candidates_384,
                    max_count="${REGSUB_MAX_COUNT_384I_NVME_C}",
                    allocation_strategy="${REGSUB_ALLOCATION_STRATEGY}",
                ),
            )
    if not candidates_96:
        raise ValueError(f"{path}: no eligible 96-vCPU local-NVMe types in {region_az}")
    updated = replace_or_insert_queue(
        updated,
        name="i96nvme",
        before="i128",
        block=queue_block(
            queue_name="i96nvme",
            resource_name="price96nvme",
            types=candidates_96,
            max_count="${REGSUB_MAX_COUNT_96I_NVME}",
            allocation_strategy="${REGSUB_ALLOCATION_STRATEGY}",
        ),
    )
    validate_rendered_template(
        path=path,
        text=updated,
        region_az=region_az,
        offered=offered,
        expected_i96=candidates_96,
    )
    return updated


def refresh_sentieon_template(
    *, path: Path, offered: set[str], candidates_8: list[str]
) -> str:
    if not candidates_8:
        raise ValueError(f"{path}: no eligible 8-vCPU local-NVMe types in us-west-2c")
    original = path.read_text(encoding="utf-8")
    updated = replace_or_insert_queue(
        original,
        name="i8",
        before="i96nvme",
        block=queue_block(
            queue_name="i8",
            resource_name="price8",
            types=candidates_8,
            max_count="12",
            allocation_strategy="price-capacity-optimized",
        ),
    )
    validate_rendered_template(
        path=path,
        text=updated,
        region_az="us-west-2c",
        offered=offered,
        expected_i96=None,
    )
    return updated


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="apply source and payload edits")
    mode.add_argument("--check", action="store_true", help="fail if refresh would change files")
    parser.add_argument("--profile", default="lsmc")
    args = parser.parse_args()

    source_paths = [REPO_ROOT / intel_relpath(az) for az in TARGET_REGION_AZS]
    missing = [str(path) for path in source_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing active Intel template(s): " + ", ".join(missing))
    discovered = sorted(SOURCE_INTEL_ROOT.glob("*/*/*.yaml"))
    if discovered != sorted(source_paths):
        raise ValueError(
            "Active Intel template inventory changed; update TARGET_REGION_AZS explicitly"
        )

    session = boto3.Session(profile_name=args.profile)
    by_region: dict[str, list[str]] = defaultdict(list)
    for region_az in TARGET_REGION_AZS:
        by_region[region_for_az(region_az)].append(region_az)

    refreshed: dict[Path, str] = {}
    for region, region_azs in sorted(by_region.items()):
        ec2 = session.client("ec2", region_name=region)
        specs_by_vcpu = candidate_specs(ec2)
        candidate_names = {
            instance_type
            for specs in specs_by_vcpu.values()
            for instance_type in specs
        }
        for region_az in region_azs:
            path = REPO_ROOT / intel_relpath(region_az)
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            offered = offered_types(
                ec2,
                region_az=region_az,
                candidates=candidate_names | all_listed_types(payload),
            )
            spot = linux_spot_types(
                ec2,
                region_az=region_az,
                candidates=candidate_names,
            )
            valid_candidates = offered & spot
            candidates_96 = sorted(
                set(specs_by_vcpu.get(96, {})) & valid_candidates
            )
            candidates_384 = sorted(
                set(specs_by_vcpu.get(384, {})) & valid_candidates
            )
            refreshed[path] = refresh_intel_template(
                path=path,
                region_az=region_az,
                offered=offered,
                candidates_96=candidates_96,
                candidates_384=candidates_384,
            )
            print(
                f"{region_az}: i96nvme={len(candidates_96)} "
                f"i384nvme={'supported' if candidates_384 else 'unsupported'}"
            )

        if region == "us-west-2":
            sentieon_path = REPO_ROOT / SENTIEON_RELPATH
            sentieon_payload = yaml.safe_load(sentieon_path.read_text(encoding="utf-8"))
            offered = offered_types(
                ec2,
                region_az="us-west-2c",
                candidates=candidate_names | all_listed_types(sentieon_payload),
            )
            spot = linux_spot_types(
                ec2,
                region_az="us-west-2c",
                candidates=candidate_names,
            )
            valid_candidates = offered & spot
            candidates_8 = sorted(
                instance_type
                for instance_type, spec in specs_by_vcpu.get(8, {}).items()
                if instance_type in valid_candidates
                and instance_type.split(".", 1)[0]
                in {"i3en", "i4i", "i7i", "i7ie"}
                and total_instance_storage_gb(spec) >= 1200
            )
            refreshed[sentieon_path] = refresh_sentieon_template(
                path=sentieon_path,
                offered=offered,
                candidates_8=candidates_8,
            )
            print(f"sentieon-single/us-west-2c: i8={len(candidates_8)}")

    changed: list[Path] = []
    for source_path, updated in refreshed.items():
        relative_path = source_path.relative_to(REPO_ROOT)
        payload_path = PAYLOAD_ROOT / relative_path
        source_changed = source_path.read_text(encoding="utf-8") != updated
        payload_changed = not payload_path.is_file() or payload_path.read_text(
            encoding="utf-8"
        ) != updated
        if source_changed or payload_changed:
            changed.append(relative_path)
            print(
                f"CHANGE {relative_path}: source={source_changed} payload={payload_changed}"
            )
            if args.write:
                source_path.write_text(updated, encoding="utf-8")
                payload_path.parent.mkdir(parents=True, exist_ok=True)
                payload_path.write_text(updated, encoding="utf-8")

    if args.check and changed:
        raise SystemExit(
            "Template refresh required for: " + ", ".join(str(path) for path in changed)
        )
    print(f"mode={'write' if args.write else 'check' if args.check else 'plan'} changed={len(changed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
