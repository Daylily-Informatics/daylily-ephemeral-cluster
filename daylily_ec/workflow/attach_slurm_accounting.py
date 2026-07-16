"""Attach Slurm accounting to an already-created ParallelCluster."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import yaml

from daylily_ec.aws.context import AWSContext
from daylily_ec.aws.slurm_accounting import (
    DEFAULT_ACCOUNTING_DATABASE_NAME,
    DEFAULT_ACCOUNTING_USERNAME,
    SlurmAccountingDb,
    SlurmAccountingError,
    list_regional_slurm_accounting_stacks,
    resolve_slurm_accounting_db,
)
from daylily_ec.pcluster import runner as pcluster_runner
from daylily_ec.state.store import config_dir


class SlurmAccountingAttachError(RuntimeError):
    """Raised when a post-create accounting attachment cannot proceed safely."""


class SlurmAccountingPreparationError(SlurmAccountingAttachError):
    """Safe structured failure from the pre-fleet-mutation preparation stage."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        reason_code: str,
        regional_stack_count: int | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.reason_code = reason_code
        self.regional_stack_count = regional_stack_count


@dataclass(frozen=True)
class PreparedSlurmAccountingUpdate:
    """Non-secret, pre-rendered update ready for supported pcluster execution."""

    cluster_name: str
    region: str
    accounting_stack_name: str
    update_config_path: Path
    service_created: bool


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
    except (OSError, yaml.YAMLError):
        raise SlurmAccountingAttachError(
            f"Could not read ParallelCluster configuration {path} safely."
        ) from None
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


def prepare_slurm_accounting_update(
    *,
    cluster_name: str,
    region: str,
    profile: Optional[str] = None,
    cluster_configuration: Optional[Path] = None,
    stack_name: str = "",
    database_name: str = DEFAULT_ACCOUNTING_DATABASE_NAME,
    db_username: str = DEFAULT_ACCOUNTING_USERNAME,
    create_if_missing: bool,
    output_dir: Optional[Path] = None,
    warning_callback: Callable[[str], None] | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> PreparedSlurmAccountingUpdate:
    """Resolve accounting and render its candidate update before fleet mutation.

    This function deliberately performs no ParallelCluster command and never
    prompts. The caller must decide whether singleton creation is approved and
    pass that decision explicitly through ``create_if_missing``.
    """
    cluster_name = cluster_name.strip()
    region = region.strip()
    if not cluster_name:
        raise SlurmAccountingPreparationError(
            "Cluster name is required for accounting preparation.",
            stage="source_config",
            reason_code="invalid_cluster_name",
        )
    if not region:
        raise SlurmAccountingPreparationError(
            "AWS region is required for accounting preparation.",
            stage="source_config",
            reason_code="invalid_region",
        )

    try:
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
    except SlurmAccountingAttachError:
        raise SlurmAccountingPreparationError(
            "The ParallelCluster source configuration is missing or invalid for "
            "accounting preparation.",
            stage="source_config",
            reason_code="invalid_source_config",
        ) from None

    try:
        aws_ctx = AWSContext.build_region(region, profile=profile)
        ec2 = aws_ctx.client("ec2")
        subnet_response = ec2.describe_subnets(SubnetIds=[headnode_subnet_id])
        subnets = subnet_response.get("Subnets", [])
        if len(subnets) != 1:
            raise SlurmAccountingPreparationError(
                "Expected exactly one EC2 subnet for the cluster head node.",
                stage="network",
                reason_code="subnet_not_unique",
            )
        subnet = subnets[0]
        vpc_id = subnet.get("VpcId")
        region_az = subnet.get("AvailabilityZone")
        if not isinstance(vpc_id, str) or not vpc_id:
            raise SlurmAccountingPreparationError(
                "The cluster head-node subnet is missing its VPC identity.",
                stage="network",
                reason_code="subnet_missing_vpc",
            )
        if not isinstance(region_az, str) or not region_az:
            raise SlurmAccountingPreparationError(
                "The cluster head-node subnet is missing its availability zone.",
                stage="network",
                reason_code="subnet_missing_az",
            )
    except SlurmAccountingPreparationError:
        raise
    except Exception:
        raise SlurmAccountingPreparationError(
            "The cluster head-node subnet could not be inspected safely.",
            stage="network",
            reason_code="subnet_inspection_failed",
        ) from None

    try:
        regional_stack_count = len(
            list_regional_slurm_accounting_stacks(
                aws_ctx,
                region_az=region_az,
            )
        )
    except SlurmAccountingError:
        raise SlurmAccountingPreparationError(
            "Regional Slurm accounting service discovery did not complete safely.",
            stage="service_resolution",
            reason_code="service_discovery_failed",
        ) from None

    try:
        resolution = resolve_slurm_accounting_db(
            aws_ctx,
            region_az=region_az,
            vpc_id=vpc_id,
            private_subnet_id=headnode_subnet_id,
            create_if_missing=create_if_missing,
            stack_name=stack_name.strip(),
            database_name=database_name,
            username=db_username,
            warning_callback=warning_callback,
            sleep_fn=sleep_fn,
        )
    except SlurmAccountingError:
        raise SlurmAccountingPreparationError(
            "No compatible regional Slurm accounting service was prepared; "
            "no compute-fleet request was issued.",
            stage="service_resolution",
            reason_code=(
                "service_missing" if regional_stack_count == 0 else "service_incompatible"
            ),
            regional_stack_count=regional_stack_count,
        ) from None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    destination_dir = output_dir.expanduser() if output_dir else config_dir()
    update_config = destination_dir / (f"{cluster_name}_slurm_accounting_update_{timestamp}.yaml")
    try:
        render_slurm_accounting_update_config(source_config, update_config, resolution.db)
    except (OSError, SlurmAccountingAttachError, SlurmAccountingError, yaml.YAMLError):
        raise SlurmAccountingPreparationError(
            "The Slurm accounting update configuration could not be rendered safely; "
            "no compute-fleet request was issued.",
            stage="render",
            reason_code="update_config_render_failed",
            regional_stack_count=regional_stack_count,
        ) from None

    return PreparedSlurmAccountingUpdate(
        cluster_name=cluster_name,
        region=region,
        accounting_stack_name=resolution.db.stack_name,
        update_config_path=update_config,
        service_created=resolution.service_created,
    )


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
    pcluster_executable: str = "pcluster",
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
        executable=pcluster_executable,
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
        executable=pcluster_executable,
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

    prepared = prepare_slurm_accounting_update(
        cluster_name=cluster_name,
        region=region,
        profile=profile,
        cluster_configuration=cluster_configuration,
        create_if_missing=False,
        stack_name=stack_name.strip(),
        database_name=database_name,
        db_username=db_username,
        output_dir=output_dir,
    )

    dry_run = pcluster_runner.update_cluster(
        cluster_name,
        str(prepared.update_config_path),
        region,
        profile=profile,
        dry_run=True,
        executable=pcluster_executable,
    )
    if not dry_run.success:
        raise SlurmAccountingAttachError(
            "pcluster update-cluster dry-run rejected the accounting update. "
            f"The generated configuration remains at {prepared.update_config_path}."
        )

    if dry_run_only:
        return SlurmAccountingAttachResult(
            cluster_name=cluster_name,
            region=region,
            accounting_stack_name=prepared.accounting_stack_name,
            update_config_path=str(prepared.update_config_path),
            dry_run_only=True,
            update_submitted=False,
        )

    update = pcluster_runner.update_cluster(
        cluster_name,
        str(prepared.update_config_path),
        region,
        profile=profile,
        dry_run=False,
        executable=pcluster_executable,
    )
    if not update.success:
        raise SlurmAccountingAttachError(
            "pcluster update-cluster failed to submit the accounting update. "
            f"The generated configuration remains at {prepared.update_config_path}."
        )

    return SlurmAccountingAttachResult(
        cluster_name=cluster_name,
        region=region,
        accounting_stack_name=prepared.accounting_stack_name,
        update_config_path=str(prepared.update_config_path),
        dry_run_only=False,
        update_submitted=True,
    )
