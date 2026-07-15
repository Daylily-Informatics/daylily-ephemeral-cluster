"""DYEC-owned, cluster-bound FSx for Lustre PERSISTENT_2 resources.

ParallelCluster cannot express the enhanced metadata configuration required by
the Daylily P2 contract.  DYEC therefore creates the file system and reference
DRA explicitly, then renders the resulting ``FileSystemId`` as external shared
storage in the ParallelCluster configuration.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml
from botocore.exceptions import ClientError

FSX_OWNER = "DYEC"
FSX_LIFECYCLE = "CLUSTER_BOUND"
FSX_DEPLOYMENT_TYPE = "PERSISTENT_2"
FSX_STORAGE_TYPE = "SSD"
FSX_LUSTRE_VERSION = "2.15"
FSX_METADATA_MODE = "AUTOMATIC"
FSX_ENCRYPTION_MODE = "AWS_MANAGED_FSX"
SWEEP_PRESERVE_TAG_KEY = "ursa-preserve"
SWEEP_PRESERVE_TAG_VALUE = "true"
REFERENCE_FILE_SYSTEM_PATH = "/references/"
FSX_PORT_RANGES = ((988, 988), (1021, 1023))
TERMINAL_FAILURE_STATES = {"FAILED", "DELETING", "DELETED"}


@dataclass(frozen=True)
class Persistent2Spec:
    cluster_name: str
    region: str
    region_az: str
    subnet_id: str
    storage_capacity_gib: int
    throughput_mbps_per_tib: int
    reference_s3_uri: str
    username_tag: str
    account_profile_tag: str
    enforce_budget_tag: str
    cost_center_region: str
    cost_center_table: str
    cost_center_usage_table: str
    lustre_version: str = FSX_LUSTRE_VERSION
    metadata_mode: str = FSX_METADATA_MODE
    encryption_mode: str = FSX_ENCRYPTION_MODE
    owner: str = FSX_OWNER
    lifecycle: str = FSX_LIFECYCLE
    sweep_preserve: bool = True

    def validate(self) -> None:
        if not self.cluster_name:
            raise ValueError("P2 FSx cluster_name is required.")
        if not self.region or not self.region_az or not self.subnet_id:
            raise ValueError("P2 FSx region, region_az, and subnet_id are required.")
        if self.storage_capacity_gib != 4800:
            raise ValueError("P2 benchmark FSx must use exactly 4800 GiB.")
        if self.throughput_mbps_per_tib != 250:
            raise ValueError("P2 benchmark FSx must use exactly 250 MB/s/TiB.")
        if self.lustre_version != FSX_LUSTRE_VERSION:
            raise ValueError(f"P2 benchmark FSx must use Lustre {FSX_LUSTRE_VERSION}.")
        if self.metadata_mode != FSX_METADATA_MODE:
            raise ValueError(f"P2 benchmark FSx metadata mode must be {FSX_METADATA_MODE}.")
        if self.encryption_mode != FSX_ENCRYPTION_MODE:
            raise ValueError(f"P2 benchmark FSx encryption mode must be {FSX_ENCRYPTION_MODE}.")
        if self.owner != FSX_OWNER or self.lifecycle != FSX_LIFECYCLE:
            raise ValueError(f"P2 benchmark FSx ownership must be {FSX_OWNER}/{FSX_LIFECYCLE}.")
        if not self.sweep_preserve:
            raise ValueError("P2 benchmark cluster must set ursa-preserve=true.")
        if not self.reference_s3_uri.startswith("s3://"):
            raise ValueError("P2 FSx reference_s3_uri must be an explicit s3:// URI.")


@dataclass(frozen=True)
class Persistent2Resources:
    file_system_id: str
    security_group_id: str
    data_repository_association_id: str
    subnet_id: str
    vpc_id: str
    deployment_type: str = FSX_DEPLOYMENT_TYPE
    storage_type: str = FSX_STORAGE_TYPE
    lustre_version: str = FSX_LUSTRE_VERSION
    metadata_mode: str = FSX_METADATA_MODE
    encryption_mode: str = FSX_ENCRYPTION_MODE
    owner: str = FSX_OWNER
    lifecycle: str = FSX_LIFECYCLE


def _tags(spec: Persistent2Spec, *, resource_role: str) -> list[dict[str, str]]:
    return [
        {"Key": "Name", "Value": f"{resource_role}-{spec.cluster_name}"},
        {"Key": "parallelcluster:cluster-name", "Value": spec.cluster_name},
        {"Key": "aws-parallelcluster-clustername", "Value": spec.cluster_name},
        {"Key": "aws-parallelcluster-project", "Value": spec.cluster_name},
        {"Key": "aws-parallelcluster-username", "Value": spec.username_tag},
        {"Key": "aws-parallelcluster-jobid", "Value": spec.account_profile_tag},
        {"Key": "aws-parallelcluster-enforce-budget", "Value": spec.enforce_budget_tag},
        {"Key": "aws-parallelcluster-cost-center-region", "Value": spec.cost_center_region},
        {"Key": "aws-parallelcluster-cost-center-table", "Value": spec.cost_center_table},
        {
            "Key": "aws-parallelcluster-cost-center-usage-table",
            "Value": spec.cost_center_usage_table,
        },
        {"Key": "dyec:cluster-name", "Value": spec.cluster_name},
        {"Key": "dyec:resource-role", "Value": resource_role},
        {"Key": "dyec:fsx-owner", "Value": spec.owner},
        {"Key": "dyec:fsx-lifecycle", "Value": spec.lifecycle},
        {"Key": SWEEP_PRESERVE_TAG_KEY, "Value": SWEEP_PRESERVE_TAG_VALUE},
    ]


def _tag_map(tags: Iterable[dict[str, Any]]) -> dict[str, str]:
    return {
        str(item.get("Key")): str(item.get("Value")) for item in tags if item.get("Key") is not None
    }


def _client_token(spec: Persistent2Spec, resource_role: str) -> str:
    payload = {"resource_role": resource_role, **asdict(spec)}
    # FSx accepts at most 63 characters; a SHA-256 hex digest is 64.
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:63]


def _describe_target_subnet(ec2_client: Any, spec: Persistent2Spec) -> tuple[str, str]:
    response = ec2_client.describe_subnets(SubnetIds=[spec.subnet_id])
    subnets = response.get("Subnets") or []
    if len(subnets) != 1:
        raise RuntimeError(f"Expected exactly one subnet record for {spec.subnet_id}.")
    subnet = subnets[0]
    actual_az = str(subnet.get("AvailabilityZone") or "")
    if actual_az != spec.region_az:
        raise RuntimeError(
            f"FSx subnet {spec.subnet_id} is in {actual_az}, expected {spec.region_az}."
        )
    vpc_id = str(subnet.get("VpcId") or "")
    if not vpc_id:
        raise RuntimeError(f"FSx subnet {spec.subnet_id} has no VPC id.")
    return vpc_id, actual_az


def _find_security_groups(ec2_client: Any, spec: Persistent2Spec, vpc_id: str) -> list[dict]:
    response = ec2_client.describe_security_groups(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "tag:dyec:cluster-name", "Values": [spec.cluster_name]},
            {"Name": "tag:dyec:resource-role", "Values": ["fsx-client-sg"]},
        ]
    )
    return list(response.get("SecurityGroups") or [])


def _ensure_self_ingress(ec2_client: Any, security_group_id: str) -> None:
    for start, end in FSX_PORT_RANGES:
        permission = {
            "IpProtocol": "tcp",
            "FromPort": start,
            "ToPort": end,
            "UserIdGroupPairs": [{"GroupId": security_group_id}],
        }
        try:
            ec2_client.authorize_security_group_ingress(
                GroupId=security_group_id,
                IpPermissions=[permission],
            )
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code") or "")
            if code != "InvalidPermission.Duplicate":
                raise


def ensure_security_group(ec2_client: Any, spec: Persistent2Spec) -> tuple[str, str]:
    """Return the exact shared client/FSx security group and VPC id."""

    spec.validate()
    vpc_id, _actual_az = _describe_target_subnet(ec2_client, spec)
    matches = _find_security_groups(ec2_client, spec, vpc_id)
    if len(matches) > 1:
        ids = ", ".join(str(item.get("GroupId")) for item in matches)
        raise RuntimeError(f"Multiple DYEC P2 security groups exist for {spec.cluster_name}: {ids}")
    if matches:
        security_group_id = str(matches[0].get("GroupId") or "")
    else:
        response = ec2_client.create_security_group(
            GroupName=f"dyec-fsx-{spec.cluster_name}",
            Description=f"DYEC P2 FSx clients for {spec.cluster_name}",
            VpcId=vpc_id,
            TagSpecifications=[
                {
                    "ResourceType": "security-group",
                    "Tags": _tags(spec, resource_role="fsx-client-sg"),
                }
            ],
        )
        security_group_id = str(response.get("GroupId") or "")
    if not security_group_id:
        raise RuntimeError("EC2 did not return a security group id for P2 FSx.")
    _ensure_self_ingress(ec2_client, security_group_id)
    return security_group_id, vpc_id


def _matching_file_systems(fsx_client: Any, spec: Persistent2Spec) -> list[dict]:
    matches: list[dict] = []
    paginator = fsx_client.get_paginator("describe_file_systems")
    for page in paginator.paginate():
        for filesystem in page.get("FileSystems", []) or []:
            tags = _tag_map(filesystem.get("Tags") or [])
            if (
                tags.get("dyec:cluster-name") == spec.cluster_name
                and tags.get("dyec:resource-role") == "fsx"
            ):
                matches.append(filesystem)
    return matches


def _validate_file_system(
    filesystem: dict[str, Any],
    spec: Persistent2Spec,
    security_group_id: str,
) -> None:
    lustre = filesystem.get("LustreConfiguration") or {}
    expected = {
        "FileSystemType": "LUSTRE",
        "StorageType": FSX_STORAGE_TYPE,
        "StorageCapacity": spec.storage_capacity_gib,
        "FileSystemTypeVersion": spec.lustre_version,
        "DeploymentType": FSX_DEPLOYMENT_TYPE,
        "PerUnitStorageThroughput": spec.throughput_mbps_per_tib,
        "MetadataMode": spec.metadata_mode,
        "SubnetIds": [spec.subnet_id],
    }
    actual = {
        "FileSystemType": filesystem.get("FileSystemType"),
        "StorageType": filesystem.get("StorageType"),
        "StorageCapacity": filesystem.get("StorageCapacity"),
        "FileSystemTypeVersion": filesystem.get("FileSystemTypeVersion"),
        "DeploymentType": lustre.get("DeploymentType"),
        "PerUnitStorageThroughput": lustre.get("PerUnitStorageThroughput"),
        "MetadataMode": (lustre.get("MetadataConfiguration") or {}).get("Mode"),
        "SubnetIds": filesystem.get("SubnetIds"),
    }
    if actual != expected:
        raise RuntimeError(
            "Existing DYEC P2 filesystem does not match the requested contract: "
            f"expected={expected!r} actual={actual!r}"
        )
    tags = _tag_map(filesystem.get("Tags") or [])
    required_tags = {
        "dyec:fsx-owner": FSX_OWNER,
        "dyec:fsx-lifecycle": FSX_LIFECYCLE,
        SWEEP_PRESERVE_TAG_KEY: SWEEP_PRESERVE_TAG_VALUE,
    }
    for key, value in required_tags.items():
        if tags.get(key) != value:
            raise RuntimeError(f"Existing DYEC P2 filesystem is missing tag {key}={value}.")
    configured_sgs = set(filesystem.get("SecurityGroupIds") or [])
    if configured_sgs and security_group_id not in configured_sgs:
        raise RuntimeError(
            f"Existing DYEC P2 filesystem does not use security group {security_group_id}."
        )


def _wait_for_file_system(
    fsx_client: Any,
    file_system_id: str,
    *,
    timeout_seconds: int,
    poll_interval_seconds: int,
    sleep_fn: Callable[[float], None],
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        response = fsx_client.describe_file_systems(FileSystemIds=[file_system_id])
        filesystems = response.get("FileSystems") or []
        if len(filesystems) != 1:
            raise RuntimeError(f"FSx did not return exactly one record for {file_system_id}.")
        filesystem = filesystems[0]
        lifecycle = str(filesystem.get("Lifecycle") or "")
        if lifecycle == "AVAILABLE":
            return filesystem
        if lifecycle in TERMINAL_FAILURE_STATES:
            failure = filesystem.get("FailureDetails") or {}
            raise RuntimeError(
                f"FSx {file_system_id} entered {lifecycle}: {failure.get('Message') or failure}"
            )
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"FSx {file_system_id} did not become AVAILABLE within {timeout_seconds}s; "
                f"last lifecycle={lifecycle}."
            )
        sleep_fn(poll_interval_seconds)


def ensure_file_system(
    fsx_client: Any,
    spec: Persistent2Spec,
    security_group_id: str,
    *,
    timeout_seconds: int = 3600,
    poll_interval_seconds: int = 30,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Create or validate the one exact P2 filesystem for the cluster."""

    spec.validate()
    matches = _matching_file_systems(fsx_client, spec)
    if len(matches) > 1:
        ids = ", ".join(str(item.get("FileSystemId")) for item in matches)
        raise RuntimeError(f"Multiple DYEC P2 filesystems exist for {spec.cluster_name}: {ids}")
    if matches:
        file_system_id = str(matches[0].get("FileSystemId") or "")
    else:
        response = fsx_client.create_file_system(
            ClientRequestToken=_client_token(spec, "fsx"),
            FileSystemType="LUSTRE",
            FileSystemTypeVersion=spec.lustre_version,
            StorageCapacity=spec.storage_capacity_gib,
            StorageType=FSX_STORAGE_TYPE,
            SubnetIds=[spec.subnet_id],
            SecurityGroupIds=[security_group_id],
            Tags=_tags(spec, resource_role="fsx"),
            LustreConfiguration={
                "DeploymentType": FSX_DEPLOYMENT_TYPE,
                "PerUnitStorageThroughput": spec.throughput_mbps_per_tib,
                "MetadataConfiguration": {"Mode": spec.metadata_mode},
                "DataCompressionType": "NONE",
                "AutomaticBackupRetentionDays": 0,
                "CopyTagsToBackups": True,
            },
        )
        file_system_id = str((response.get("FileSystem") or {}).get("FileSystemId") or "")
    if not file_system_id:
        raise RuntimeError("FSx did not return a file system id for P2 creation.")
    filesystem = _wait_for_file_system(
        fsx_client,
        file_system_id,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        sleep_fn=sleep_fn,
    )
    _validate_file_system(filesystem, spec, security_group_id)
    return filesystem


def _matching_associations(fsx_client: Any, file_system_id: str) -> list[dict]:
    response = fsx_client.describe_data_repository_associations(
        Filters=[{"Name": "file-system-id", "Values": [file_system_id]}]
    )
    return list(response.get("Associations") or [])


def _wait_for_association(
    fsx_client: Any,
    association_id: str,
    *,
    timeout_seconds: int,
    poll_interval_seconds: int,
    sleep_fn: Callable[[float], None],
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        response = fsx_client.describe_data_repository_associations(AssociationIds=[association_id])
        associations = response.get("Associations") or []
        if len(associations) != 1:
            raise RuntimeError(f"FSx did not return exactly one DRA for {association_id}.")
        association = associations[0]
        lifecycle = str(association.get("Lifecycle") or "")
        if lifecycle == "AVAILABLE":
            return association
        if lifecycle in TERMINAL_FAILURE_STATES or lifecycle == "MISCONFIGURED":
            failure = association.get("FailureDetails") or {}
            raise RuntimeError(
                f"DRA {association_id} entered {lifecycle}: {failure.get('Message') or failure}"
            )
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"DRA {association_id} did not become AVAILABLE within {timeout_seconds}s; "
                f"last lifecycle={lifecycle}."
            )
        sleep_fn(poll_interval_seconds)


def _validate_reference_association(association: dict[str, Any], spec: Persistent2Spec) -> None:
    expected_repository = spec.reference_s3_uri.rstrip("/")
    actual_repository = str(association.get("DataRepositoryPath") or "").rstrip("/")
    if str(association.get("FileSystemPath") or "") != REFERENCE_FILE_SYSTEM_PATH:
        raise RuntimeError("P2 FSx DRA must map exactly /references/.")
    if actual_repository != expected_repository:
        raise RuntimeError(
            f"P2 FSx DRA repository mismatch: expected {expected_repository}, "
            f"actual {actual_repository}."
        )
    events = set(((association.get("S3") or {}).get("AutoImportPolicy") or {}).get("Events") or [])
    if events != {"NEW", "CHANGED", "DELETED"}:
        raise RuntimeError(
            "P2 FSx reference DRA must auto-import NEW, CHANGED, and DELETED events."
        )


def ensure_reference_association(
    fsx_client: Any,
    spec: Persistent2Spec,
    file_system_id: str,
    *,
    timeout_seconds: int = 3600,
    poll_interval_seconds: int = 30,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Create or validate the sole `/references/` data repository association."""

    associations = _matching_associations(fsx_client, file_system_id)
    if len(associations) > 1:
        ids = ", ".join(str(item.get("AssociationId")) for item in associations)
        raise RuntimeError(f"P2 FSx has multiple data repository associations: {ids}")
    if associations:
        association_id = str(associations[0].get("AssociationId") or "")
    else:
        response = fsx_client.create_data_repository_association(
            FileSystemId=file_system_id,
            FileSystemPath=REFERENCE_FILE_SYSTEM_PATH,
            DataRepositoryPath=spec.reference_s3_uri.rstrip("/"),
            BatchImportMetaDataOnCreate=True,
            S3={"AutoImportPolicy": {"Events": ["NEW", "CHANGED", "DELETED"]}},
            ClientRequestToken=_client_token(spec, "reference-dra"),
            Tags=_tags(spec, resource_role="reference-dra"),
        )
        association_id = str((response.get("Association") or {}).get("AssociationId") or "")
    if not association_id:
        raise RuntimeError("FSx did not return an association id for the reference DRA.")
    association = _wait_for_association(
        fsx_client,
        association_id,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        sleep_fn=sleep_fn,
    )
    _validate_reference_association(association, spec)
    return association


def ensure_persistent2_resources(
    ec2_client: Any,
    fsx_client: Any,
    spec: Persistent2Spec,
) -> Persistent2Resources:
    """Ensure the exact SG, P2 filesystem, and reference DRA contract."""

    security_group_id, vpc_id = ensure_security_group(ec2_client, spec)
    filesystem = ensure_file_system(fsx_client, spec, security_group_id)
    file_system_id = str(filesystem["FileSystemId"])
    association = ensure_reference_association(fsx_client, spec, file_system_id)
    return Persistent2Resources(
        file_system_id=file_system_id,
        security_group_id=security_group_id,
        data_repository_association_id=str(association["AssociationId"]),
        subnet_id=spec.subnet_id,
        vpc_id=vpc_id,
    )


def render_external_mount(
    cluster_yaml_path: str | Path,
    resources: Persistent2Resources,
) -> None:
    """Replace managed FSx settings with the exact external mount contract."""

    path = Path(cluster_yaml_path)
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    fsx_entries = [
        item
        for item in payload.get("SharedStorage") or []
        if isinstance(item, dict) and item.get("StorageType") == "FsxLustre"
    ]
    if len(fsx_entries) != 1:
        raise ValueError("P2 cluster YAML must contain exactly one FsxLustre mount.")
    fsx_entry = fsx_entries[0]
    if fsx_entry.get("MountDir") != "/fsx":
        raise ValueError("P2 external FSx must mount exactly at /fsx.")
    fsx_entry["Name"] = "fsx-p2-external"
    fsx_entry["FsxLustreSettings"] = {"FileSystemId": resources.file_system_id}

    head_networking = payload.setdefault("HeadNode", {}).setdefault("Networking", {})
    head_groups = head_networking.setdefault("AdditionalSecurityGroups", [])
    if resources.security_group_id not in head_groups:
        head_groups.append(resources.security_group_id)

    queues = (payload.get("Scheduling") or {}).get("SlurmQueues") or []
    if not queues:
        raise ValueError("P2 cluster YAML must contain at least one Slurm queue.")
    for queue in queues:
        queue_networking = queue.setdefault("Networking", {})
        queue_groups = queue_networking.setdefault("AdditionalSecurityGroups", [])
        if resources.security_group_id not in queue_groups:
            queue_groups.append(resources.security_group_id)

    tags = payload.setdefault("Tags", [])
    preserve_matches = [item for item in tags if item.get("Key") == SWEEP_PRESERVE_TAG_KEY]
    if preserve_matches and any(
        str(item.get("Value")).lower() != SWEEP_PRESERVE_TAG_VALUE for item in preserve_matches
    ):
        raise ValueError("Cluster YAML contains a conflicting ursa-preserve tag.")
    if not preserve_matches:
        tags.append({"Key": SWEEP_PRESERVE_TAG_KEY, "Value": SWEEP_PRESERVE_TAG_VALUE})

    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def validate_external_mount(
    cluster_yaml_path: str | Path,
    resources: Persistent2Resources,
) -> None:
    """Fail unless rendered YAML matches the full external-P2 mount contract."""

    payload = yaml.safe_load(Path(cluster_yaml_path).read_text(encoding="utf-8")) or {}
    fsx_entries = [
        item
        for item in payload.get("SharedStorage") or []
        if isinstance(item, dict) and item.get("StorageType") == "FsxLustre"
    ]
    if len(fsx_entries) != 1:
        raise ValueError("Rendered P2 YAML must contain exactly one FsxLustre mount.")
    settings = fsx_entries[0].get("FsxLustreSettings") or {}
    if settings != {"FileSystemId": resources.file_system_id}:
        raise ValueError("Rendered P2 YAML must contain only the external FileSystemId.")
    head_groups = ((payload.get("HeadNode") or {}).get("Networking") or {}).get(
        "AdditionalSecurityGroups"
    ) or []
    if resources.security_group_id not in head_groups:
        raise ValueError("Rendered P2 headnode is missing the FSx client security group.")
    for queue in (payload.get("Scheduling") or {}).get("SlurmQueues") or []:
        groups = (queue.get("Networking") or {}).get("AdditionalSecurityGroups") or []
        if resources.security_group_id not in groups:
            raise ValueError(
                f"Rendered P2 queue {queue.get('Name')} is missing the FSx client security group."
            )
    tags = _tag_map(payload.get("Tags") or [])
    if tags.get(SWEEP_PRESERVE_TAG_KEY) != SWEEP_PRESERVE_TAG_VALUE:
        raise ValueError("Rendered P2 cluster must set ursa-preserve=true.")


def find_cluster_bound_file_systems(
    fsx_client: Any,
    *,
    cluster_name: str,
    file_system_ids: Iterable[str],
) -> list[str]:
    """Return only exact DYEC-owned, cluster-bound P2 filesystem ids."""

    ids = [str(item) for item in file_system_ids if str(item)]
    if not ids:
        return []
    response = fsx_client.describe_file_systems(FileSystemIds=ids)
    matched: list[str] = []
    for filesystem in response.get("FileSystems", []) or []:
        tags = _tag_map(filesystem.get("Tags") or [])
        lustre = filesystem.get("LustreConfiguration") or {}
        if (
            tags.get("dyec:cluster-name") == cluster_name
            and tags.get("dyec:resource-role") == "fsx"
            and tags.get("dyec:fsx-owner") == FSX_OWNER
            and tags.get("dyec:fsx-lifecycle") == FSX_LIFECYCLE
            and lustre.get("DeploymentType") == FSX_DEPLOYMENT_TYPE
        ):
            matched.append(str(filesystem.get("FileSystemId")))
    return sorted(matched)


def _wait_for_file_system_absent(
    fsx_client: Any,
    file_system_id: str,
    *,
    timeout_seconds: int,
    poll_interval_seconds: int,
    sleep_fn: Callable[[float], None],
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            response = fsx_client.describe_file_systems(FileSystemIds=[file_system_id])
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code") or "")
            if code in {"FileSystemNotFound", "FileSystemNotFoundException"}:
                return
            raise
        if not (response.get("FileSystems") or []):
            return
        if time.monotonic() >= deadline:
            lifecycle = str(response["FileSystems"][0].get("Lifecycle") or "")
            raise TimeoutError(
                f"FSx {file_system_id} was not deleted within {timeout_seconds}s; "
                f"last lifecycle={lifecycle}."
            )
        sleep_fn(poll_interval_seconds)


def _delete_security_groups(
    ec2_client: Any,
    *,
    cluster_name: str,
    timeout_seconds: int,
    poll_interval_seconds: int,
    sleep_fn: Callable[[float], None],
) -> list[str]:
    response = ec2_client.describe_security_groups(
        Filters=[
            {"Name": "tag:dyec:cluster-name", "Values": [cluster_name]},
            {"Name": "tag:dyec:resource-role", "Values": ["fsx-client-sg"]},
            {"Name": "tag:dyec:fsx-owner", "Values": [FSX_OWNER]},
            {"Name": "tag:dyec:fsx-lifecycle", "Values": [FSX_LIFECYCLE]},
        ]
    )
    deleted: list[str] = []
    for group in response.get("SecurityGroups", []) or []:
        group_id = str(group.get("GroupId") or "")
        if not group_id:
            continue
        deadline = time.monotonic() + timeout_seconds
        while True:
            try:
                ec2_client.delete_security_group(GroupId=group_id)
                deleted.append(group_id)
                break
            except ClientError as exc:
                code = str(exc.response.get("Error", {}).get("Code") or "")
                if code == "InvalidGroup.NotFound":
                    deleted.append(group_id)
                    break
                if code != "DependencyViolation" or time.monotonic() >= deadline:
                    raise
                sleep_fn(poll_interval_seconds)
    return deleted


def delete_cluster_bound_resources(
    ec2_client: Any,
    fsx_client: Any,
    *,
    cluster_name: str,
    file_system_ids: Iterable[str],
    timeout_seconds: int = 3600,
    poll_interval_seconds: int = 30,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, list[str]]:
    """Delete exact external P2 resources after ParallelCluster is absent."""

    matched = find_cluster_bound_file_systems(
        fsx_client,
        cluster_name=cluster_name,
        file_system_ids=file_system_ids,
    )
    for file_system_id in matched:
        fsx_client.delete_file_system(
            FileSystemId=file_system_id,
            LustreConfiguration={"SkipFinalBackup": True},
        )
        _wait_for_file_system_absent(
            fsx_client,
            file_system_id,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
            sleep_fn=sleep_fn,
        )
    deleted_groups = _delete_security_groups(
        ec2_client,
        cluster_name=cluster_name,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        sleep_fn=sleep_fn,
    )
    return {"file_system_ids": matched, "security_group_ids": deleted_groups}
