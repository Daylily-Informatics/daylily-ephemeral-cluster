"""Attach Slurm accounting to an already-created ParallelCluster."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from daylily_ec.aws.context import AWSContext
from daylily_ec.aws.slurm_accounting import (
    DEFAULT_ACCOUNTING_DATABASE_NAME,
    DEFAULT_ACCOUNTING_USERNAME,
    SlurmAccountingDb,
    ensure_slurm_accounting_db,
)
from daylily_ec.pcluster import runner as pcluster_runner
from daylily_ec.state.store import config_dir


class SlurmAccountingAttachError(RuntimeError):
    """Raised when a post-create accounting attachment cannot proceed safely."""


@dataclass(frozen=True)
class SlurmAccountingAttachResult:
    """Non-secret result of an accounting attach validation or submission."""

    cluster_name: str
    region: str
    accounting_stack_name: str
    update_config_path: str
    dry_run_only: bool
    update_submitted: bool


def _latest_cluster_config(
    cluster_name: str,
    region: str,
    *,
    profile: Optional[str],
) -> Path:
    """Return the newest persisted create config for an exact cluster identity."""
    matches: list[tuple[str, Path]] = []
    for state_path in config_dir().glob(f"state_{cluster_name}_*.json"):
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("cluster_name") != cluster_name or payload.get("region") != region:
            continue
        if profile and payload.get("aws_profile") != profile:
            continue
        config_value = payload.get("cluster_yaml_path")
        run_id = payload.get("run_id")
        if not isinstance(config_value, str) or not config_value:
            continue
        if not isinstance(run_id, str) or not run_id:
            continue
        config_path = Path(config_value).expanduser()
        if config_path.is_file():
            matches.append((run_id, config_path))
    if not matches:
        raise SlurmAccountingAttachError(
            "No persisted DYEC cluster configuration was found for "
            f"{cluster_name!r} in {region}. Pass --cluster-configuration explicitly."
        )
    return max(matches, key=lambda item: item[0])[1]


def _load_cluster_config(path: Path) -> dict:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SlurmAccountingAttachError(
            f"Could not read ParallelCluster configuration {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise SlurmAccountingAttachError(
            f"ParallelCluster configuration {path} must contain a YAML mapping."
        )
    return payload


def _headnode_subnet_id(payload: dict) -> str:
    try:
        subnet_id = payload["HeadNode"]["Networking"]["SubnetId"]
    except (KeyError, TypeError) as exc:
        raise SlurmAccountingAttachError(
            "ParallelCluster configuration is missing HeadNode.Networking.SubnetId."
        ) from exc
    if not isinstance(subnet_id, str) or not subnet_id.strip():
        raise SlurmAccountingAttachError(
            "ParallelCluster HeadNode.Networking.SubnetId must be a non-empty string."
        )
    return subnet_id.strip()


def render_slurm_accounting_update_config(
    source_config: Path,
    destination_config: Path,
    db: SlurmAccountingDb,
) -> Path:
    """Write a separate update config containing the accounting attachment."""
    payload = _load_cluster_config(source_config)

    scheduling = payload.setdefault("Scheduling", {})
    if not isinstance(scheduling, dict):
        raise SlurmAccountingAttachError("Scheduling must be a YAML mapping.")
    slurm_settings = scheduling.setdefault("SlurmSettings", {})
    if not isinstance(slurm_settings, dict):
        raise SlurmAccountingAttachError("Scheduling.SlurmSettings must be a YAML mapping.")
    if "Database" in slurm_settings:
        raise SlurmAccountingAttachError(
            "The cluster configuration already contains Scheduling.SlurmSettings.Database."
        )

    head_node = payload.get("HeadNode")
    if not isinstance(head_node, dict):
        raise SlurmAccountingAttachError("HeadNode must be a YAML mapping.")
    networking = head_node.get("Networking")
    if not isinstance(networking, dict):
        raise SlurmAccountingAttachError("HeadNode.Networking must be a YAML mapping.")
    additional_groups = networking.setdefault("AdditionalSecurityGroups", [])
    if not isinstance(additional_groups, list) or not all(
        isinstance(value, str) and value for value in additional_groups
    ):
        raise SlurmAccountingAttachError(
            "HeadNode.Networking.AdditionalSecurityGroups must be a list of security-group ids."
        )
    if db.client_security_group_id not in additional_groups:
        additional_groups.append(db.client_security_group_id)

    slurm_settings["Database"] = {
        "Uri": db.uri,
        "UserName": db.username,
        "PasswordSecretArn": db.password_secret_arn,
        "DatabaseName": db.database_name,
    }

    destination_config.parent.mkdir(parents=True, exist_ok=True)
    destination_config.write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )
    return destination_config


def attach_slurm_accounting(
    *,
    cluster_name: str,
    region: str,
    profile: Optional[str] = None,
    cluster_configuration: Optional[Path] = None,
    stack_name: str = "",
    database_name: str = DEFAULT_ACCOUNTING_DATABASE_NAME,
    db_username: str = DEFAULT_ACCOUNTING_USERNAME,
    dry_run_only: bool = False,
    output_dir: Optional[Path] = None,
) -> SlurmAccountingAttachResult:
    """Attach an existing, same-VPC accounting service to a stopped cluster.

    This function never stops compute capacity, creates an accounting stack,
    forces a ParallelCluster update, or edits the original cluster config.
    """
    cluster_name = cluster_name.strip()
    region = region.strip()
    if not cluster_name:
        raise SlurmAccountingAttachError("Cluster name is required.")
    if not region:
        raise SlurmAccountingAttachError("AWS region is required.")

    description = pcluster_runner.describe_cluster(
        cluster_name,
        region,
        profile=profile,
    )
    if not description.success:
        raise SlurmAccountingAttachError(
            f"Could not describe ParallelCluster {cluster_name!r} in {region}."
        )
    status = description.json_body.get("clusterStatus")
    if status != "CREATE_COMPLETE":
        raise SlurmAccountingAttachError(
            f"Cluster {cluster_name!r} must be CREATE_COMPLETE before accounting attach; "
            f"current status is {status!r}."
        )

    fleet = pcluster_runner.describe_compute_fleet(
        cluster_name,
        region,
        profile=profile,
    )
    if not fleet.success:
        raise SlurmAccountingAttachError(
            f"Could not describe the compute fleet for {cluster_name!r}."
        )
    fleet_status = fleet.json_body.get("status")
    if fleet_status != "STOPPED":
        raise SlurmAccountingAttachError(
            "AWS ParallelCluster requires the compute fleet to be STOPPED before "
            "Scheduling.SlurmSettings.Database can be changed. Confirm no jobs must "
            "remain running, then stop the fleet explicitly with: "
            f"pcluster update-compute-fleet --cluster-name {cluster_name} "
            f"--region {region} --status STOP_REQUESTED"
        )

    source_config = (
        cluster_configuration.expanduser()
        if cluster_configuration is not None
        else _latest_cluster_config(cluster_name, region, profile=profile)
    )
    if not source_config.is_file():
        raise SlurmAccountingAttachError(
            f"ParallelCluster configuration does not exist: {source_config}"
        )
    source_payload = _load_cluster_config(source_config)
    headnode_subnet_id = _headnode_subnet_id(source_payload)

    aws_ctx = AWSContext.build_region(region, profile=profile)
    ec2 = aws_ctx.client("ec2")
    subnet_response = ec2.describe_subnets(SubnetIds=[headnode_subnet_id])
    subnets = subnet_response.get("Subnets", [])
    if len(subnets) != 1:
        raise SlurmAccountingAttachError(
            f"Expected one EC2 subnet for {headnode_subnet_id}; found {len(subnets)}."
        )
    subnet = subnets[0]
    vpc_id = subnet.get("VpcId")
    region_az = subnet.get("AvailabilityZone")
    if not isinstance(vpc_id, str) or not vpc_id:
        raise SlurmAccountingAttachError(f"EC2 subnet {headnode_subnet_id} is missing VpcId.")
    if not isinstance(region_az, str) or not region_az:
        raise SlurmAccountingAttachError(
            f"EC2 subnet {headnode_subnet_id} is missing AvailabilityZone."
        )

    db = ensure_slurm_accounting_db(
        aws_ctx,
        region_az=region_az,
        vpc_id=vpc_id,
        private_subnet_id=headnode_subnet_id,
        create_if_missing=False,
        stack_name=stack_name.strip(),
        database_name=database_name,
        username=db_username,
    )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    destination_dir = output_dir.expanduser() if output_dir else config_dir()
    update_config = destination_dir / (f"{cluster_name}_slurm_accounting_update_{timestamp}.yaml")
    render_slurm_accounting_update_config(source_config, update_config, db)

    dry_run = pcluster_runner.update_cluster(
        cluster_name,
        str(update_config),
        region,
        profile=profile,
        dry_run=True,
    )
    if not dry_run.success:
        raise SlurmAccountingAttachError(
            "pcluster update-cluster dry-run rejected the accounting update. "
            f"The generated configuration remains at {update_config}."
        )

    if dry_run_only:
        return SlurmAccountingAttachResult(
            cluster_name=cluster_name,
            region=region,
            accounting_stack_name=db.stack_name,
            update_config_path=str(update_config),
            dry_run_only=True,
            update_submitted=False,
        )

    update = pcluster_runner.update_cluster(
        cluster_name,
        str(update_config),
        region,
        profile=profile,
        dry_run=False,
    )
    if not update.success:
        raise SlurmAccountingAttachError(
            "pcluster update-cluster failed to submit the accounting update. "
            f"The generated configuration remains at {update_config}."
        )

    return SlurmAccountingAttachResult(
        cluster_name=cluster_name,
        region=region,
        accounting_stack_name=db.stack_name,
        update_config_path=str(update_config),
        dry_run_only=False,
        update_submitted=True,
    )
