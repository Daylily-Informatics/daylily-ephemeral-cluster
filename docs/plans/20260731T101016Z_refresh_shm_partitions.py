#!/usr/bin/env python3
"""Audit and refresh partition-aware SHM queues in active CPU templates.

Default mode is read-only. ``--write`` updates source and packaged mirrors;
``--check`` fails when either copy differs from the live offering-derived result.
No AWS resources are mutated.
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
import yaml

from daylily_ec.resources import (
    INTEL_ONDEMAND_TEMPLATE_RELPATHS,
    INTEL_SPOT_TEMPLATE_RELPATHS,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
PAYLOAD_ROOT = REPO_ROOT / "daylily_ec/resources/payload"
THRESHOLDS_GIB = {128: 468, 192: 468, 384: 968}
QUEUE_NAMES = {vcpus: f"i{vcpus}shm" for vcpus in THRESHOLDS_GIB}
MAX_COUNT_TOKENS = {
    128: "${REGSUB_MAX_COUNT_128I_M}",
    192: "${REGSUB_MAX_COUNT_192I_M}",
    384: "${REGSUB_MAX_COUNT_384I}",
}
QUEUE_START = re.compile(r"^  - Name: ([A-Za-z0-9_-]+)\s*$")
ACCELERATOR_KEYS = (
    "FpgaInfo",
    "GpuInfo",
    "InferenceAcceleratorInfo",
    "MediaAcceleratorInfo",
    "NeuronInfo",
)
DRAGEN_TEMPLATE_RELPATH = (
    "config/day_cluster/dragen/us-west-2/us-west-2b/"
    "prod_cluster_dragen_us-west-2b.yaml"
)
SENTIEON_SINGLE_TEMPLATE_RELPATH = (
    "config/day_cluster/sentieon-single/us-west-2/us-west-2c/"
    "prod_cluster_sentieon-single_us-west-2c.yaml"
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
            raise ValueError(f"duplicate queue name: {name}")
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
        raise ValueError(f"cannot insert {name}: following queue {before} is absent")
    start, _end = ranges[before]
    lines[start:start] = block.splitlines(keepends=True)
    return "".join(lines)


def remove_queue(text: str, *, name: str) -> str:
    lines = text.splitlines(keepends=True)
    ranges = queue_ranges(text)
    if name in ranges:
        start, end = ranges[name]
        del lines[start:end]
    return "".join(lines)


def eligible_specs(ec2: Any) -> dict[int, dict[str, dict[str, Any]]]:
    by_vcpu: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
    paginator = ec2.get_paginator("describe_instance_types")
    filters = [
        {
            "Name": "vcpu-info.default-vcpus",
            "Values": [str(value) for value in THRESHOLDS_GIB],
        },
        {"Name": "processor-info.supported-architecture", "Values": ["x86_64"]},
    ]
    for page in paginator.paginate(Filters=filters):
        for spec in page.get("InstanceTypes", []):
            vcpus = int((spec.get("VCpuInfo") or {}).get("DefaultVCpus") or 0)
            memory_gib = int((spec.get("MemoryInfo") or {}).get("SizeInMiB") or 0) / 1024
            architectures = (spec.get("ProcessorInfo") or {}).get(
                "SupportedArchitectures", []
            )
            if (
                vcpus not in THRESHOLDS_GIB
                or memory_gib < THRESHOLDS_GIB[vcpus]
                or "x86_64" not in architectures
                or any(spec.get(key) for key in ACCELERATOR_KEYS)
            ):
                continue
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
    now = datetime.now(timezone.utc)
    for offset in range(0, len(values), 100):
        next_token: str | None = None
        while True:
            request: dict[str, Any] = {
                "AvailabilityZone": region_az,
                "InstanceTypes": values[offset : offset + 100],
                "ProductDescriptions": ["Linux/UNIX"],
                "StartTime": now,
                "EndTime": now,
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
    vcpus: int,
    types: list[str],
    capacity_type: str,
    template_kind: str,
) -> str:
    if not types:
        raise ValueError(f"refusing to render empty {QUEUE_NAMES[vcpus]} queue")
    if capacity_type not in {"SPOT", "ONDEMAND"}:
        raise ValueError(f"unsupported capacity type: {capacity_type}")
    if template_kind not in {"intel", "dragen"}:
        raise ValueError(f"unsupported template kind: {template_kind}")
    strategy = (
        "${REGSUB_ALLOCATION_STRATEGY}"
        if capacity_type == "SPOT"
        else "lowest-price"
    )
    max_count = MAX_COUNT_TOKENS[vcpus]
    instance_lines = "".join(f"      - InstanceType: {item}\n" for item in types)
    spot_price = "      SpotPrice: CALCULATE_MAX_SPOT_PRICE\n" if capacity_type == "SPOT" else ""
    image = (
        "    Image:\n"
        "      CustomAmi: ${REGSUB_DRAGEN_PCLUSTER_AMI}\n"
        if template_kind == "dragen"
        else ""
    )
    script = (
        "${REGSUB_S3_BUCKET_INIT}/post_install_rhel8_dragen.sh"
        if template_kind == "dragen"
        else "${REGSUB_S3_BUCKET_INIT}/post_install_ubuntu_combined.sh"
    )
    script_args = "        - fsx\n        - cpu\n" if template_kind == "dragen" else ""
    return (
        f"  - Name: {QUEUE_NAMES[vcpus]}\n"
        "    JobExclusiveAllocation: false\n"
        f"    CapacityType: {capacity_type}\n"
        f"    AllocationStrategy: {strategy}\n"
        f"{image}"
        "    ComputeResources:\n"
        f"    - Name: shm{vcpus}\n"
        "      Instances:\n"
        f"{instance_lines}"
        "      MinCount: 0\n"
        f"      MaxCount: {max_count}\n"
        f"{spot_price}"
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
        f"        Script: {script}\n"
        "        Args:\n"
        "        - ${REGSUB_REGION}\n"
        "        - ${REGSUB_S3_BUCKET_INIT}\n"
        "        - ${REGSUB_SPOT_PRICE_WARN_THRESHOLD}\n"
        f"{script_args}"
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


def refresh_template(
    *,
    path: Path,
    candidates: dict[int, list[str]],
    capacity_type: str,
    template_kind: str = "intel",
) -> str:
    updated = path.read_text(encoding="utf-8")
    before_by_vcpu = (
        {128: "i192nvme", 192: "i192nvme", 384: "i192nvme"}
        if template_kind == "dragen"
        else {128: "i128nvme", 192: "i192nvme", 384: "i384nvme"}
    )
    for vcpus in THRESHOLDS_GIB:
        ranges = queue_ranges(updated)
        before = before_by_vcpu[vcpus]
        if before not in ranges and vcpus == 384:
            before = "i192hugenvme"
        updated = replace_or_insert_queue(
            updated,
            name=QUEUE_NAMES[vcpus],
            before=before,
            block=queue_block(
                vcpus=vcpus,
                types=candidates[vcpus],
                capacity_type=capacity_type,
                template_kind=template_kind,
            ),
        )
    payload = yaml.safe_load(updated)
    queues = payload["Scheduling"]["SlurmQueues"]
    names = [str(queue["Name"]) for queue in queues]
    for vcpus, queue_name in QUEUE_NAMES.items():
        if names.count(queue_name) != 1:
            raise ValueError(f"{path}: expected exactly one {queue_name}")
        queue = next(item for item in queues if item["Name"] == queue_name)
        if queue.get("ComputeSettings"):
            raise ValueError(f"{path}: {queue_name} must not mount local NVMe")
        resources = queue.get("ComputeResources") or []
        if len(resources) != 1:
            raise ValueError(f"{path}: {queue_name} must have one compute resource")
        rendered = [str(item["InstanceType"]) for item in resources[0]["Instances"]]
        if rendered != candidates[vcpus]:
            raise ValueError(f"{path}: {queue_name} candidate list drift")
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--profile", default="lsmc")
    args = parser.parse_args()

    session = boto3.Session(profile_name=args.profile)
    paths_by_az: dict[str, list[tuple[Path, str]]] = defaultdict(list)
    for relative in INTEL_SPOT_TEMPLATE_RELPATHS:
        az = Path(relative).stem.removeprefix("prod_cluster_intel_spot_")
        paths_by_az[az].append((REPO_ROOT / relative, "SPOT"))
    for relative in INTEL_ONDEMAND_TEMPLATE_RELPATHS:
        az = Path(relative).stem.removeprefix("prod_cluster_intel_ondemand_")
        paths_by_az[az].append((REPO_ROOT / relative, "ONDEMAND"))

    refreshed: dict[Path, str] = {}
    by_region: dict[str, list[str]] = defaultdict(list)
    for az in paths_by_az:
        by_region[az[:-1]].append(az)
    for region, region_azs in sorted(by_region.items()):
        ec2 = session.client("ec2", region_name=region)
        specs = eligible_specs(ec2)
        candidate_names = set().union(*(set(items) for items in specs.values()))
        for az in sorted(region_azs):
            offered = offered_types(ec2, region_az=az, candidates=candidate_names)
            spot = linux_spot_types(ec2, region_az=az, candidates=candidate_names)
            candidate_sets = {
                "SPOT": offered & spot,
                "ONDEMAND": offered,
            }
            for path, capacity_type in paths_by_az[az]:
                if not path.is_file():
                    raise FileNotFoundError(path)
                candidates = {
                    vcpus: sorted(set(specs.get(vcpus, {})) & candidate_sets[capacity_type])
                    for vcpus in THRESHOLDS_GIB
                }
                refreshed[path] = refresh_template(
                    path=path,
                    candidates=candidates,
                    capacity_type=capacity_type,
                )
                print(
                    f"{path.relative_to(REPO_ROOT)}: "
                    + " ".join(
                        f"{QUEUE_NAMES[vcpus]}={len(candidates[vcpus])}"
                        for vcpus in THRESHOLDS_GIB
                    )
                )

            if az == "us-west-2b":
                dragen_path = REPO_ROOT / DRAGEN_TEMPLATE_RELPATH
                candidates = {
                    vcpus: sorted(set(specs.get(vcpus, {})) & offered & spot)
                    for vcpus in THRESHOLDS_GIB
                }
                refreshed[dragen_path] = refresh_template(
                    path=dragen_path,
                    candidates=candidates,
                    capacity_type="SPOT",
                    template_kind="dragen",
                )
                print(
                    f"{dragen_path.relative_to(REPO_ROOT)}: "
                    + " ".join(
                        f"{QUEUE_NAMES[vcpus]}={len(candidates[vcpus])}"
                        for vcpus in THRESHOLDS_GIB
                    )
                )

    sentieon_path = REPO_ROOT / SENTIEON_SINGLE_TEMPLATE_RELPATH
    sentieon_cleaned = sentieon_path.read_text(encoding="utf-8")
    for queue_name in QUEUE_NAMES.values():
        sentieon_cleaned = remove_queue(sentieon_cleaned, name=queue_name)
    refreshed[sentieon_path] = sentieon_cleaned

    changed: list[Path] = []
    for source_path, updated in refreshed.items():
        relative = source_path.relative_to(REPO_ROOT)
        payload_path = PAYLOAD_ROOT / relative
        source_changed = source_path.read_text(encoding="utf-8") != updated
        payload_changed = not payload_path.is_file() or payload_path.read_text(
            encoding="utf-8"
        ) != updated
        if source_changed or payload_changed:
            changed.append(relative)
            print(f"CHANGE {relative}: source={source_changed} payload={payload_changed}")
            if args.write:
                source_path.write_text(updated, encoding="utf-8")
                payload_path.parent.mkdir(parents=True, exist_ok=True)
                payload_path.write_text(updated, encoding="utf-8")
    if args.check and changed:
        raise SystemExit("SHM template refresh required: " + ", ".join(map(str, changed)))
    print(
        f"mode={'write' if args.write else 'check' if args.check else 'plan'} "
        f"templates={len(refreshed)} changed={len(changed)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
