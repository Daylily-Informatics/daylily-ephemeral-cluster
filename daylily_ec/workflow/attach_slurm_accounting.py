"""Attach Slurm accounting to an already-created ParallelCluster."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

from daylily_ec.aws.context import AWSContext
from daylily_ec.aws.slurm_accounting import (
    ACCOUNTING_VPC_TAG_KEY,
    DEFAULT_ACCOUNTING_DATABASE_NAME,
    DEFAULT_ACCOUNTING_INSTANCE_TYPE,
    DEFAULT_ACCOUNTING_USERNAME,
    SlurmAccountingDb,
    SlurmAccountingError,
    create_slurm_accounting_stack,
    discover_slurm_accounting_dbs,
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


ATTACHABLE_CLUSTER_STATES = frozenset({"CREATE_COMPLETE", "UPDATE_COMPLETE"})
RECOVERABLE_FAILED_CLUSTER_STATE = "UPDATE_FAILED"
RECOVERABLE_CLOUDFORMATION_STATE = "UPDATE_ROLLBACK_COMPLETE"


@dataclass(frozen=True)
class PreparedSlurmAccountingUpdate:
    """Non-secret, pre-rendered update ready for supported pcluster execution."""

    cluster_name: str
    region: str
    accounting_stack_name: str
    provider_accounting_stack_name: str
    privatelink_stack_name: str | None
    consumer_vpc_id: str
    update_config_path: Path
    service_created: bool
    database_name: str = ""
    db_username: str = ""


@dataclass(frozen=True)
class ClusterAccountingNetworkIdentity:
    """Exact cluster subnet/VPC/AZ identity used before accounting preparation."""

    subnet_id: str
    vpc_id: str
    region_az: str


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
    profile: str | None,
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


def inspect_cluster_accounting_network(
    *,
    source_config: Path,
    region: str,
    profile: str | None,
    expected_region_az: str = "",
    aws_ctx: Any | None = None,
) -> ClusterAccountingNetworkIdentity:
    """Resolve the exact source-config headnode subnet without mutating AWS."""

    try:
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
        aws_ctx = aws_ctx or AWSContext.build_region(region, profile=profile)
        subnet_response = aws_ctx.client("ec2").describe_subnets(SubnetIds=[headnode_subnet_id])
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
        if expected_region_az and region_az != expected_region_az:
            raise SlurmAccountingPreparationError(
                "The cluster head-node subnet availability zone does not match "
                "the explicitly requested recovery availability zone.",
                stage="network",
                reason_code="subnet_az_mismatch",
            )
    except SlurmAccountingPreparationError:
        raise
    except Exception:  # noqa: BLE001 - SDK exceptions are normalized at this boundary
        raise SlurmAccountingPreparationError(
            "The cluster head-node subnet could not be inspected safely.",
            stage="network",
            reason_code="subnet_inspection_failed",
        ) from None
    return ClusterAccountingNetworkIdentity(
        subnet_id=headnode_subnet_id,
        vpc_id=vpc_id,
        region_az=region_az,
    )


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

    iam = head_node.setdefault("Iam", {})
    if not isinstance(iam, dict):
        raise SlurmAccountingAttachError("HeadNode.Iam must be a YAML mapping.")
    additional_policies = iam.setdefault("AdditionalIamPolicies", [])
    if not isinstance(additional_policies, list) or not all(
        isinstance(value, dict)
        and set(value) == {"Policy"}
        and isinstance(value["Policy"], str)
        and value["Policy"]
        for value in additional_policies
    ):
        raise SlurmAccountingAttachError(
            "HeadNode.Iam.AdditionalIamPolicies must be a list of Policy mappings."
        )
    client_policy = {"Policy": db.client_secret_read_policy_arn}
    if client_policy not in additional_policies:
        additional_policies.append(client_policy)

    slurm_settings["Database"] = {
        "Uri": db.uri,
        "UserName": db.username,
        "PasswordSecretArn": db.password_secret_arn,
        "DatabaseName": db.database_name,
    }

    rendered = yaml.safe_dump(payload, sort_keys=False)
    destination_config.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        dir=str(destination_config.parent),
        prefix=f".{destination_config.name}.tmp-",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination_config)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return destination_config


def prepare_slurm_accounting_update(
    *,
    cluster_name: str,
    region: str,
    profile: str | None = None,
    cluster_configuration: Path | None = None,
    stack_name: str = "",
    privatelink_stack_name: str = "",
    database_name: str = DEFAULT_ACCOUNTING_DATABASE_NAME,
    db_username: str = DEFAULT_ACCOUNTING_USERNAME,
    instance_type: str = DEFAULT_ACCOUNTING_INSTANCE_TYPE,
    create_if_missing: bool,
    output_dir: Path | None = None,
    destination_config: Path | None = None,
    expected_region_az: str = "",
    exact_target_only: bool = False,
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

    source_config = (
        cluster_configuration.expanduser()
        if cluster_configuration is not None
        else _latest_cluster_config(cluster_name, region, profile=profile)
    )
    if not source_config.is_file():
        raise SlurmAccountingPreparationError(
            "The ParallelCluster source configuration is missing or invalid for "
            "accounting preparation.",
            stage="source_config",
            reason_code="invalid_source_config",
        ) from None
    try:
        aws_ctx = AWSContext.build_region(region, profile=profile)
    except Exception:  # noqa: BLE001 - SDK/session text is normalized here
        raise SlurmAccountingPreparationError(
            "The cluster head-node subnet could not be inspected safely.",
            stage="network",
            reason_code="subnet_inspection_failed",
        ) from None
    network = inspect_cluster_accounting_network(
        source_config=source_config,
        region=region,
        profile=profile,
        expected_region_az=expected_region_az,
        aws_ctx=aws_ctx,
    )
    headnode_subnet_id = network.subnet_id
    vpc_id = network.vpc_id
    region_az = network.region_az

    regional_stack_count: int | None = None
    regional_stacks: list[dict] = []
    exact_stack_name = stack_name.strip()
    provider_accounting_stack_name = ""
    resolved_privatelink_stack_name: str | None = None
    if exact_target_only:
        if not exact_stack_name:
            raise SlurmAccountingPreparationError(
                "Exact accounting preparation requires an explicit stack name.",
                stage="service_resolution",
                reason_code="exact_stack_required",
            )
        exact_privatelink_stack_name = privatelink_stack_name.strip()
        if exact_privatelink_stack_name and create_if_missing:
            raise SlurmAccountingPreparationError(
                "Exact PrivateLink recovery cannot create an accounting provider or bridge.",
                stage="service_resolution",
                reason_code="exact_privatelink_creation_forbidden",
            )
        try:
            exact_regional_stacks = list_regional_slurm_accounting_stacks(
                aws_ctx,
                region_az=region_az,
            )
            exact_regional_names = [
                str(item.get("StackName") or "").strip() for item in exact_regional_stacks
            ]
        except Exception:  # noqa: BLE001 - provider text is normalized here
            raise SlurmAccountingPreparationError(
                "The regional accounting singleton inventory could not be read safely.",
                stage="service_resolution",
                reason_code="exact_regional_stack_inventory_failed",
            ) from None
        if len(exact_regional_names) > 1 or (
            exact_regional_names and exact_regional_names != [exact_stack_name]
        ):
            raise SlurmAccountingPreparationError(
                "The regional accounting singleton inventory conflicts with the exact "
                "requested stack.",
                stage="service_resolution",
                reason_code="exact_regional_stack_conflict",
            )
        provider_stack = exact_regional_stacks[0] if exact_regional_stacks else None
        provider_vpc_id = ""
        if provider_stack is not None:
            provider_tags = {
                str(item.get("Key") or ""): str(item.get("Value") or "")
                for item in provider_stack.get("Tags", [])
                if isinstance(item, dict)
            }
            provider_vpc_id = provider_tags.get(ACCOUNTING_VPC_TAG_KEY, "").strip()
            if not provider_vpc_id:
                raise SlurmAccountingPreparationError(
                    "The exact regional accounting provider is missing its VPC identity.",
                    stage="service_resolution",
                    reason_code="exact_service_identity_mismatch",
                )

        if exact_privatelink_stack_name:
            if provider_stack is None:
                raise SlurmAccountingPreparationError(
                    "The exact Slurm accounting provider stack is missing.",
                    stage="service_resolution",
                    reason_code="exact_stack_missing",
                )
            from daylily_ec.aws.slurm_accounting_privatelink import (
                resolve_slurm_accounting_privatelink_bridge,
            )

            try:
                bridge = resolve_slurm_accounting_privatelink_bridge(
                    aws_ctx,
                    stack_name=exact_privatelink_stack_name,
                    require_healthy_target=True,
                )
            except Exception:  # noqa: BLE001 - bridge/provider text is normalized here
                raise SlurmAccountingPreparationError(
                    "The exact accounting PrivateLink bridge is unavailable or unhealthy.",
                    stage="service_resolution",
                    reason_code="exact_privatelink_unavailable",
                ) from None
            try:
                bridge_identity_matches = (
                    bridge.stack_name == exact_privatelink_stack_name
                    and bridge.provider_accounting_stack_name == exact_stack_name
                    and bridge.provider_vpc_id == provider_vpc_id
                    and bridge.consumer_vpc_id == vpc_id
                    and bridge.database_name == database_name
                    and bridge.username == db_username
                )
            except Exception:  # noqa: BLE001 - malformed bridge result is normalized here
                bridge_identity_matches = False
            if not bridge_identity_matches:
                raise SlurmAccountingPreparationError(
                    "The exact accounting PrivateLink provider/consumer identity does not match.",
                    stage="service_resolution",
                    reason_code="exact_privatelink_identity_mismatch",
                )
            try:
                exact_matches = discover_slurm_accounting_dbs(
                    aws_ctx,
                    region_az=region_az,
                    vpc_id=provider_vpc_id,
                    stack_name=exact_stack_name,
                )
            except Exception:  # noqa: BLE001 - provider text is normalized here
                raise SlurmAccountingPreparationError(
                    "The exact accounting provider database could not be verified safely.",
                    stage="service_resolution",
                    reason_code="exact_database_discovery_failed",
                ) from None
            if len(exact_matches) != 1:
                raise SlurmAccountingPreparationError(
                    "Exact accounting provider discovery did not return one target.",
                    stage="service_resolution",
                    reason_code=(
                        "exact_database_multiple"
                        if len(exact_matches) > 1
                        else "exact_stack_missing"
                    ),
                )
            provider_db = exact_matches[0]
            try:
                provider_binding_matches = (
                    provider_db.stack_name == exact_stack_name
                    and provider_db.database_name == database_name
                    and provider_db.username == db_username
                    and provider_db.instance_id == bridge.accounting_instance_id
                    and provider_db.password_secret_arn == bridge.password_secret_arn
                )
            except Exception:  # noqa: BLE001 - malformed provider result is normalized here
                provider_binding_matches = False
            if not provider_binding_matches:
                raise SlurmAccountingPreparationError(
                    "The exact accounting provider and PrivateLink database bindings differ.",
                    stage="service_resolution",
                    reason_code="exact_privatelink_provider_binding_mismatch",
                )
            db = bridge.as_accounting_db()
            provider_accounting_stack_name = exact_stack_name
            resolved_privatelink_stack_name = exact_privatelink_stack_name
            service_created = False
        else:
            if provider_stack is not None and provider_vpc_id != vpc_id:
                raise SlurmAccountingPreparationError(
                    "The exact accounting provider is in another VPC; an explicit exact "
                    "PrivateLink bridge is required.",
                    stage="service_resolution",
                    reason_code="exact_direct_vpc_mismatch",
                )
            try:
                exact_matches = discover_slurm_accounting_dbs(
                    aws_ctx,
                    region_az=region_az,
                    vpc_id=vpc_id,
                    stack_name=exact_stack_name,
                )
                exact_match_count = len(exact_matches)
            except Exception:  # noqa: BLE001 - provider text is normalized here
                raise SlurmAccountingPreparationError(
                    "The exact accounting database target could not be discovered safely.",
                    stage="service_resolution",
                    reason_code="exact_database_discovery_failed",
                ) from None
            if exact_match_count > 1:
                raise SlurmAccountingPreparationError(
                    "Exact accounting database discovery returned more than one target.",
                    stage="service_resolution",
                    reason_code="exact_database_multiple",
                )
            if exact_match_count == 1:
                db = exact_matches[0]
                service_created = False
            elif create_if_missing:
                try:
                    db = create_slurm_accounting_stack(
                        aws_ctx,
                        region_az=region_az,
                        vpc_id=vpc_id,
                        private_subnet_id=headnode_subnet_id,
                        stack_name=exact_stack_name,
                        database_name=database_name,
                        username=db_username,
                        instance_type=instance_type,
                    )
                except Exception:  # noqa: BLE001 - provider text is normalized here
                    raise SlurmAccountingPreparationError(
                        "The exact Slurm accounting stack could not be created safely.",
                        stage="service_resolution",
                        reason_code="exact_stack_create_failed",
                    ) from None
                service_created = True
            else:
                raise SlurmAccountingPreparationError(
                    "The exact Slurm accounting stack is missing and creation was not approved.",
                    stage="service_resolution",
                    reason_code="exact_stack_missing",
                )
            try:
                exact_identity_matches = (
                    db.stack_name == exact_stack_name
                    and db.database_name == database_name
                    and db.username == db_username
                )
            except Exception:  # noqa: BLE001 - malformed provider result is normalized here
                exact_identity_matches = False
            if not exact_identity_matches:
                raise SlurmAccountingPreparationError(
                    "The resolved Slurm accounting stack/database/user identity does not "
                    "match the explicitly requested target.",
                    stage="service_resolution",
                    reason_code="exact_service_identity_mismatch",
                )
            provider_accounting_stack_name = exact_stack_name
    elif privatelink_stack_name.strip():
        from daylily_ec.aws.slurm_accounting_privatelink import (
            SlurmAccountingPrivateLinkError,
            resolve_slurm_accounting_privatelink_bridge,
        )

        try:
            bridge = resolve_slurm_accounting_privatelink_bridge(
                aws_ctx,
                stack_name=privatelink_stack_name.strip(),
            )
            if bridge.consumer_vpc_id != vpc_id:
                raise SlurmAccountingPrivateLinkError(
                    "PrivateLink consumer VPC does not match the cluster VPC."
                )
            if stack_name.strip() and bridge.provider_accounting_stack_name != stack_name.strip():
                raise SlurmAccountingPrivateLinkError(
                    "PrivateLink provider stack does not match --stack-name."
                )
            db = bridge.as_accounting_db()
            provider_accounting_stack_name = bridge.provider_accounting_stack_name
            resolved_privatelink_stack_name = bridge.stack_name
            service_created = False
        except SlurmAccountingPrivateLinkError:
            raise SlurmAccountingPreparationError(
                "The requested Slurm accounting PrivateLink bridge is unavailable or "
                "incompatible; no compute-fleet request was issued.",
                stage="service_resolution",
                reason_code="privatelink_incompatible",
            ) from None
    else:
        try:
            regional_stacks = list_regional_slurm_accounting_stacks(
                aws_ctx,
                region_az=region_az,
            )
            regional_stack_count = len(regional_stacks)
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
                instance_type=instance_type,
                warning_callback=warning_callback,
                sleep_fn=sleep_fn,
            )
            db = resolution.db
            provider_accounting_stack_name = db.stack_name
            service_created = resolution.service_created
        except SlurmAccountingError:
            bridge = None
            if regional_stack_count == 1:
                from daylily_ec.aws.slurm_accounting_privatelink import (
                    SlurmAccountingPrivateLinkError,
                    reconcile_existing_slurm_accounting_privatelink_bridge_for_consumer,
                    resolve_slurm_accounting_privatelink_bridge_for_consumer,
                )

                try:
                    provider_stack_name = (
                        stack_name.strip() or str(regional_stacks[0].get("StackName") or "").strip()
                    )
                    if not provider_stack_name:
                        raise SlurmAccountingPrivateLinkError(
                            "The regional accounting stack is missing its identity."
                        )
                    if create_if_missing:
                        bridge = (
                            reconcile_existing_slurm_accounting_privatelink_bridge_for_consumer(
                                aws_ctx,
                                consumer_vpc_id=vpc_id,
                                provider_accounting_stack_name=provider_stack_name,
                            )
                        )
                    else:
                        bridge = resolve_slurm_accounting_privatelink_bridge_for_consumer(
                            aws_ctx,
                            consumer_vpc_id=vpc_id,
                            provider_accounting_stack_name=provider_stack_name,
                        )
                except SlurmAccountingPrivateLinkError:
                    bridge = None
            if bridge is None:
                raise SlurmAccountingPreparationError(
                    "No compatible regional Slurm accounting service was prepared; "
                    "no compute-fleet request was issued.",
                    stage="service_resolution",
                    reason_code=(
                        "service_missing" if regional_stack_count == 0 else "service_incompatible"
                    ),
                    regional_stack_count=regional_stack_count,
                ) from None
            db = bridge.as_accounting_db()
            provider_accounting_stack_name = bridge.provider_accounting_stack_name
            resolved_privatelink_stack_name = bridge.stack_name
            service_created = False

    if destination_config is not None:
        update_config = destination_config.expanduser()
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        destination_dir = output_dir.expanduser() if output_dir else config_dir()
        update_config = destination_dir / (
            f"{cluster_name}_slurm_accounting_update_{timestamp}.yaml"
        )
    try:
        render_slurm_accounting_update_config(source_config, update_config, db)
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
        accounting_stack_name=db.stack_name,
        provider_accounting_stack_name=provider_accounting_stack_name,
        privatelink_stack_name=resolved_privatelink_stack_name,
        consumer_vpc_id=vpc_id,
        update_config_path=update_config,
        service_created=service_created,
        database_name=db.database_name,
        db_username=db.username,
    )


def attach_slurm_accounting(
    *,
    cluster_name: str,
    region: str,
    profile: str | None = None,
    cluster_configuration: Path | None = None,
    stack_name: str = "",
    privatelink_stack_name: str = "",
    database_name: str = DEFAULT_ACCOUNTING_DATABASE_NAME,
    db_username: str = DEFAULT_ACCOUNTING_USERNAME,
    dry_run_only: bool = False,
    output_dir: Path | None = None,
    pcluster_executable: str = "pcluster",
) -> SlurmAccountingAttachResult:
    """Attach a direct or PrivateLink accounting service to a stopped cluster.

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
    cloudformation_status = description.json_body.get("cloudFormationStackStatus")
    recoverable_failed_update = (
        status == RECOVERABLE_FAILED_CLUSTER_STATE
        and cloudformation_status == RECOVERABLE_CLOUDFORMATION_STATE
    )
    if status not in ATTACHABLE_CLUSTER_STATES and not recoverable_failed_update:
        raise SlurmAccountingAttachError(
            f"Cluster {cluster_name!r} must be CREATE_COMPLETE, UPDATE_COMPLETE, or an "
            "UPDATE_FAILED cluster whose CloudFormation stack is "
            "UPDATE_ROLLBACK_COMPLETE before accounting attach; current states are "
            f"cluster={status!r}, cloudformation={cloudformation_status!r}."
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
        privatelink_stack_name=privatelink_stack_name.strip(),
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
