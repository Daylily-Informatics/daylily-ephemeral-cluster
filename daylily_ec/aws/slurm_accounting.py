"""DayEC-owned Slurm accounting database discovery and provisioning."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # pragma: no cover - exercised only on trimmed botocore installs
    BotoCoreError = Exception  # type: ignore[misc,assignment]
    ClientError = Exception  # type: ignore[misc,assignment]

from daylily_ec.aws.context import parse_region_az
from daylily_ec.resources import resource_path

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE_PATH = "config/day_cluster/slurm_accounting_mysql_ec2.yml"
DEFAULT_ACCOUNTING_DATABASE_NAME = "dayec_slurm_acct"
DEFAULT_ACCOUNTING_USERNAME = "slurm_acct"
DEFAULT_ACCOUNTING_INSTANCE_TYPE = "t4g.micro"
MULTIPLE_ACCOUNTING_SELECTION_DELAY_SECONDS = 90
VALIDATION_ACCOUNTING_STACK_PREFIX = "dayec-costacct-"
VALIDATION_IGNORE_BEFORE_UTC = datetime(2026, 7, 4, tzinfo=timezone.utc)

ACCOUNTING_COMPONENT_TAG_KEY = "daylily-ec:component"
ACCOUNTING_COMPONENT_TAG_VALUE = "slurm-accounting-mysql"
ACCOUNTING_REGION_TAG_KEY = "daylily-ec:region"
ACCOUNTING_REGION_AZ_TAG_KEY = "daylily-ec:region-az"
ACCOUNTING_VPC_TAG_KEY = "daylily-ec:vpc-id"
ACCOUNTING_MANAGED_BY_TAG_KEY = "daylily-ec:managed-by"
ACCOUNTING_MANAGED_BY_TAG_VALUE = "daylily-ephemeral-cluster"

HEALTHY_STACK_STATUSES = frozenset(
    {
        "CREATE_COMPLETE",
        "UPDATE_COMPLETE",
        "UPDATE_ROLLBACK_COMPLETE",
        "IMPORT_COMPLETE",
    }
)

DISCOVERABLE_STACK_STATUSES = (
    "CREATE_IN_PROGRESS",
    "CREATE_FAILED",
    "CREATE_COMPLETE",
    "ROLLBACK_IN_PROGRESS",
    "ROLLBACK_FAILED",
    "ROLLBACK_COMPLETE",
    "DELETE_FAILED",
    "UPDATE_IN_PROGRESS",
    "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
    "UPDATE_COMPLETE",
    "UPDATE_ROLLBACK_IN_PROGRESS",
    "UPDATE_ROLLBACK_FAILED",
    "UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS",
    "UPDATE_ROLLBACK_COMPLETE",
    "IMPORT_IN_PROGRESS",
    "IMPORT_COMPLETE",
    "IMPORT_ROLLBACK_IN_PROGRESS",
    "IMPORT_ROLLBACK_FAILED",
    "IMPORT_ROLLBACK_COMPLETE",
)

REQUIRED_OUTPUTS = {
    "AccountingDbUri",
    "AccountingDbPrivateIp",
    "AccountingDatabaseName",
    "AccountingUserName",
    "AccountingPasswordSecretArn",
    "AccountingClientSecurityGroupId",
}

DATABASE_NAME_RE = re.compile(r"^[a-z0-9_]{1,64}$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{1,32}$")


class SlurmAccountingError(RuntimeError):
    """Raised when Slurm accounting DB resolution cannot continue safely."""


@dataclass(frozen=True)
class SlurmAccountingDb:
    """Resolved DayEC Slurm accounting database values."""

    stack_name: str
    status: str
    uri: str
    private_ip: str
    database_name: str
    username: str
    password_secret_arn: str
    client_security_group_id: str
    instance_id: str = ""


@dataclass(frozen=True)
class SlurmAccountingScanCandidate:
    """One EC2 scan hit for a possible Slurm accounting database host."""

    instance_id: str
    name: str
    private_ip: str
    availability_zone: str
    vpc_id: str
    source: str
    selectable: bool
    reason: str
    db: SlurmAccountingDb | None = None


@dataclass(frozen=True)
class SlurmAccountingSelectionCandidate:
    """One regional stack considered during duplicate-service selection."""

    stack_name: str
    status: str
    vpc_id: str
    compatible: bool
    reason: str
    attached_instance_ids: tuple[str, ...] | None
    db: SlurmAccountingDb | None = None

    @property
    def attached_host_count(self) -> int | None:
        if self.attached_instance_ids is None:
            return None
        return len(self.attached_instance_ids)


def derive_slurm_accounting_stack_name(region_az: str) -> str:
    """Return the deterministic regional accounting stack name."""
    region_az = region_az.strip()
    if not region_az:
        raise ValueError("region_az must not be empty")
    region, _az = parse_region_az(region_az)
    return f"dayec-slurm-accounting-{region}"


def derive_validation_slurm_accounting_stack_name(utcstamp: str) -> str:
    value = utcstamp.strip()
    if not re.fullmatch(r"\d{8}T\d{6}Z", value):
        raise SlurmAccountingError("Validation accounting UTC stamp must be YYYYMMDDTHHMMSSZ.")
    return f"{VALIDATION_ACCOUNTING_STACK_PREFIX}{value}"


def list_active_validation_slurm_accounting_stacks(
    aws_ctx: Any,
    *,
    created_after: datetime = VALIDATION_IGNORE_BEFORE_UTC,
) -> list[dict[str, Any]]:
    """List active post-cutoff `dayec-costacct-*` stacks for live-validation guardrails."""
    cfn = aws_ctx.client("cloudformation")
    cutoff = _as_utc(created_after)
    matches: list[dict[str, Any]] = []
    for summary in _list_stack_summaries(cfn):
        name = str(summary.get("StackName") or "")
        if not name.startswith(VALIDATION_ACCOUNTING_STACK_PREFIX):
            continue
        status = str(summary.get("StackStatus") or "")
        if status == "DELETE_COMPLETE":
            continue
        created = _as_utc(summary.get("CreationTime"))
        if created < cutoff:
            continue
        stack = _describe_stack_or_none(cfn, name)
        if stack is not None:
            matches.append(stack)
    return sorted(matches, key=lambda stack: str(stack.get("StackName") or ""))


def require_no_active_validation_slurm_accounting_stacks(
    aws_ctx: Any,
    *,
    created_after: datetime = VALIDATION_IGNORE_BEFORE_UTC,
) -> None:
    matches = list_active_validation_slurm_accounting_stacks(
        aws_ctx,
        created_after=created_after,
    )
    if matches:
        names = ", ".join(str(stack.get("StackName") or "") for stack in matches)
        raise SlurmAccountingError(
            "Active post-2026-07-04 validation Slurm accounting stack exists: "
            f"{names}. Delete or finish that validation resource before creating another."
        )


def validate_database_name(database_name: str) -> str:
    """Validate the pcluster Slurm accounting database name contract."""
    value = database_name.strip()
    if not DATABASE_NAME_RE.fullmatch(value):
        raise SlurmAccountingError(
            "Slurm accounting database name must contain only lowercase letters, "
            "numbers, and underscores, and must be 1-64 characters."
        )
    return value


def validate_username(username: str) -> str:
    """Validate the MariaDB user name emitted into pcluster config."""
    value = username.strip()
    if not USERNAME_RE.fullmatch(value):
        raise SlurmAccountingError(
            "Slurm accounting DB username must contain only letters, numbers, "
            "and underscores, and must be 1-32 characters."
        )
    return value


def build_slurm_accounting_tags(region_az: str, vpc_id: str) -> list[dict[str, str]]:
    """Return the exact DayEC tags used for accounting stack discovery."""
    region, _az = parse_region_az(region_az)
    return [
        {"Key": ACCOUNTING_COMPONENT_TAG_KEY, "Value": ACCOUNTING_COMPONENT_TAG_VALUE},
        {"Key": ACCOUNTING_REGION_TAG_KEY, "Value": region},
        {"Key": ACCOUNTING_REGION_AZ_TAG_KEY, "Value": region_az},
        {"Key": ACCOUNTING_VPC_TAG_KEY, "Value": vpc_id},
        {"Key": ACCOUNTING_MANAGED_BY_TAG_KEY, "Value": ACCOUNTING_MANAGED_BY_TAG_VALUE},
    ]


def empty_slurm_accounting_render_blocks() -> dict[str, str]:
    """Return disabled renderer blocks for optional Slurm accounting config."""
    return {
        "REGSUB_SLURM_ACCOUNTING_HEADNODE_NETWORKING": "",
        "REGSUB_SLURM_ACCOUNTING_DATABASE": "",
    }


def slurm_accounting_render_blocks(db: SlurmAccountingDb) -> dict[str, str]:
    """Return renderer substitutions for enabled Slurm accounting."""
    return {
        "REGSUB_SLURM_ACCOUNTING_HEADNODE_NETWORKING": format_headnode_networking_block(
            db.client_security_group_id
        ),
        "REGSUB_SLURM_ACCOUNTING_DATABASE": format_database_block(db),
    }


def format_headnode_networking_block(client_security_group_id: str) -> str:
    """Render the optional head node client security group block."""
    if not client_security_group_id.strip():
        raise SlurmAccountingError("Accounting client security group ID is empty.")
    return (
        "\n"
        "    AdditionalSecurityGroups:\n"
        f"      - {client_security_group_id.strip()}\n"
    )


def format_database_block(db: SlurmAccountingDb) -> str:
    """Render the optional ParallelCluster SlurmSettings.Database block."""
    _validate_uri(db.uri)
    validate_database_name(db.database_name)
    validate_username(db.username)
    if not db.password_secret_arn.strip():
        raise SlurmAccountingError("Accounting password secret ARN is empty.")
    return (
        "\n"
        "    Database:\n"
        f"      Uri: {db.uri.strip()}\n"
        f"      UserName: {db.username.strip()}\n"
        f"      PasswordSecretArn: {db.password_secret_arn.strip()}\n"
        f"      DatabaseName: {db.database_name.strip()}\n"
    )


def discover_slurm_accounting_dbs(
    aws_ctx: Any,
    *,
    region_az: str,
    vpc_id: str,
    stack_name: str = "",
) -> list[SlurmAccountingDb]:
    """Discover the one reusable DayEC Slurm accounting stack in a region.

    Every DayEC accounting stack, including validation-named stacks, counts
    toward the singleton. The singleton must be in the selected cluster VPC
    because its private address and client security group are not reachable
    across unrelated VPCs.
    """
    cfn = aws_ctx.client("cloudformation")
    region, _az = parse_region_az(region_az)
    matching_stacks = _list_regional_accounting_stacks(cfn, region=region)
    if stack_name.strip():
        stack = _describe_stack_or_none(cfn, stack_name.strip())
        if stack is None:
            if matching_stacks:
                names = ", ".join(
                    sorted(str(item.get("StackName") or "") for item in matching_stacks)
                )
                raise SlurmAccountingError(
                    f"Explicit Slurm accounting stack '{stack_name}' does not exist, but "
                    f"region {region} already has accounting singleton: {names}. A second "
                    "regional accounting stack is forbidden."
                )
            return []
        if not _stack_is_accounting_stack_in_region(stack, region=region):
            raise SlurmAccountingError(
                f"Stack '{stack_name}' exists but is not tagged as the DayEC "
                f"Slurm accounting singleton for region {region}."
            )
        _require_stack_vpc(stack, requested_vpc_id=vpc_id, region=region)
        return [_db_from_stack(stack)]

    matches = [_db_from_stack(stack) for stack in matching_stacks]
    if len(matching_stacks) == 1:
        _require_stack_vpc(
            matching_stacks[0],
            requested_vpc_id=vpc_id,
            region=region,
        )
    return matches


def list_regional_slurm_accounting_stacks(
    aws_ctx: Any,
    *,
    region_az: str,
) -> list[dict[str, Any]]:
    """Return every DayEC accounting stack that counts toward the region singleton."""
    region, _az = parse_region_az(region_az)
    return _list_regional_accounting_stacks(
        aws_ctx.client("cloudformation"),
        region=region,
    )


def scan_slurm_accounting_ec2_candidates(
    aws_ctx: Any,
    *,
    region_az: str,
    vpc_id: str,
) -> list[SlurmAccountingScanCandidate]:
    """Scan same-VPC EC2 instances for reusable Slurm accounting DB candidates.

    The scan is read-only. Candidates are selectable only when they can be
    matched to the complete DayEC CloudFormation output contract required by
    ParallelCluster.
    """
    del region_az  # Region is already fixed by aws_ctx; scan is VPC scoped.
    if not vpc_id.strip():
        raise SlurmAccountingError("VPC ID is required to scan Slurm accounting EC2 hosts.")

    cfn = aws_ctx.client("cloudformation")
    ec2 = aws_ctx.client("ec2")
    valid_dbs, invalid_stack_reasons = _discover_accounting_dbs_by_instance_for_vpc(
        cfn,
        vpc_id=vpc_id,
    )
    instances = _list_running_instances_in_vpc(ec2, vpc_id=vpc_id)
    security_groups = _describe_security_groups(
        ec2,
        _security_group_ids_for_instances(instances),
    )

    candidates: list[SlurmAccountingScanCandidate] = []
    for instance in instances:
        instance_id = str(instance.get("InstanceId") or "")
        if not instance_id:
            continue
        tags = _tags_by_key(instance.get("Tags", []))
        is_dayec_accounting_host = (
            tags.get(ACCOUNTING_COMPONENT_TAG_KEY) == ACCOUNTING_COMPONENT_TAG_VALUE
        )
        db = valid_dbs.get(instance_id)
        if db is not None:
            candidates.append(
                _candidate_from_instance(
                    instance,
                    source="dayec-stack",
                    selectable=True,
                    reason=f"Matched healthy DayEC accounting stack {db.stack_name}.",
                    db=db,
                )
            )
            continue

        if is_dayec_accounting_host:
            candidates.append(
                _candidate_from_instance(
                    instance,
                    source="dayec-tagged",
                    selectable=False,
                    reason=invalid_stack_reasons.get(
                        instance_id,
                        "DayEC-tagged accounting instance has no matching healthy stack outputs.",
                    ),
                )
            )
            continue

        if _instance_has_mysql_accounting_signal(instance, security_groups):
            candidates.append(
                _candidate_from_instance(
                    instance,
                    source="ec2-advisory",
                    selectable=False,
                    reason=(
                        "Running same-VPC instance has MySQL/accounting EC2 metadata "
                        "but no complete DayEC accounting stack outputs."
                    ),
                )
            )

    return sorted(
        candidates,
        key=lambda candidate: (
            not candidate.selectable,
            candidate.source != "dayec-stack",
            candidate.name or candidate.instance_id,
        ),
    )


def ensure_slurm_accounting_db(
    aws_ctx: Any,
    *,
    region_az: str,
    vpc_id: str,
    private_subnet_id: str,
    create_if_missing: bool,
    stack_name: str = "",
    database_name: str = DEFAULT_ACCOUNTING_DATABASE_NAME,
    username: str = DEFAULT_ACCOUNTING_USERNAME,
    instance_type: str = DEFAULT_ACCOUNTING_INSTANCE_TYPE,
    assign_public_ip: bool = False,
    template_path: str = DEFAULT_TEMPLATE_PATH,
    warning_callback: Callable[[str], None] | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> SlurmAccountingDb:
    """Resolve one accounting DB stack, creating it only when explicitly allowed."""
    database_name = validate_database_name(database_name or DEFAULT_ACCOUNTING_DATABASE_NAME)
    username = validate_username(username or DEFAULT_ACCOUNTING_USERNAME)
    stack_name = stack_name.strip()

    region, _az = parse_region_az(region_az)
    regional_stacks = _list_regional_accounting_stacks(
        aws_ctx.client("cloudformation"),
        region=region,
    )
    if len(regional_stacks) > 1:
        candidates = _inspect_selection_candidates(
            aws_ctx,
            stacks=regional_stacks,
            requested_vpc_id=vpc_id,
        )
        selected, selection_reason = _select_duplicate_accounting_candidate(
            candidates,
            preferred_stack_name=stack_name,
            region=region,
        )
        _warn_and_delay_duplicate_accounting_selection(
            candidates,
            selected=selected,
            selection_reason=selection_reason,
            preferred_stack_name=stack_name,
            region=region,
            warning_callback=warning_callback or logger.warning,
            sleep_fn=sleep_fn or time.sleep,
        )
        if selected.db is None:  # Defensive: selection only returns compatible DBs.
            raise SlurmAccountingError(
                f"Selected Slurm accounting stack '{selected.stack_name}' has no database."
            )
        return selected.db

    matches = discover_slurm_accounting_dbs(
        aws_ctx,
        region_az=region_az,
        vpc_id=vpc_id,
        stack_name=stack_name,
    )
    if len(matches) == 1:
        return matches[0]
    if not create_if_missing:
        raise SlurmAccountingError(
            f"No DayEC Slurm accounting stack exists for region {region}; "
            "rerun with --create-slurm-accounting-db or create it with "
            "dyec slurm-accounting ensure."
        )

    create_name = stack_name or derive_slurm_accounting_stack_name(region_az)
    return create_slurm_accounting_stack(
        aws_ctx,
        region_az=region_az,
        vpc_id=vpc_id,
        private_subnet_id=private_subnet_id,
        stack_name=create_name,
        database_name=database_name,
        username=username,
        instance_type=instance_type or DEFAULT_ACCOUNTING_INSTANCE_TYPE,
        assign_public_ip=assign_public_ip,
        template_path=template_path,
    )


def _inspect_selection_candidates(
    aws_ctx: Any,
    *,
    stacks: list[dict[str, Any]],
    requested_vpc_id: str,
) -> list[SlurmAccountingSelectionCandidate]:
    inspected: list[SlurmAccountingSelectionCandidate] = []
    for stack in stacks:
        stack_name = str(stack.get("StackName") or "")
        status = str(stack.get("StackStatus") or "")
        vpc_id = _tags_by_key(stack.get("Tags", [])).get(ACCOUNTING_VPC_TAG_KEY, "").strip()
        try:
            db = _db_from_stack(stack)
        except SlurmAccountingError as exc:
            inspected.append(
                SlurmAccountingSelectionCandidate(
                    stack_name=stack_name,
                    status=status,
                    vpc_id=vpc_id,
                    compatible=False,
                    reason=str(exc),
                    attached_instance_ids=(),
                )
            )
            continue

        compatible = bool(vpc_id) and vpc_id == requested_vpc_id
        if compatible:
            reason = f"healthy and in requested VPC {requested_vpc_id}"
        elif not vpc_id:
            reason = f"missing required tag {ACCOUNTING_VPC_TAG_KEY}"
        else:
            reason = f"VPC {vpc_id} does not match requested VPC {requested_vpc_id}"
        inspected.append(
            SlurmAccountingSelectionCandidate(
                stack_name=stack_name,
                status=status,
                vpc_id=vpc_id,
                compatible=compatible,
                reason=reason,
                attached_instance_ids=(),
                db=db,
            )
        )

    client_security_group_ids = sorted(
        {
            candidate.db.client_security_group_id
            for candidate in inspected
            if candidate.db is not None
        }
    )
    try:
        attached_by_group = _attached_instance_ids_by_security_group(
            aws_ctx.client("ec2"),
            client_security_group_ids,
        )
    except SlurmAccountingError as exc:
        logger.warning("Unable to count Slurm accounting attached hosts: %s", exc)
        attached_by_group = None

    with_counts: list[SlurmAccountingSelectionCandidate] = []
    for candidate in inspected:
        if candidate.db is None:
            attached_ids: tuple[str, ...] | None = ()
        elif attached_by_group is None:
            attached_ids = None
        else:
            attached_ids = tuple(
                instance_id
                for instance_id in attached_by_group.get(
                    candidate.db.client_security_group_id,
                    (),
                )
                if instance_id != candidate.db.instance_id
            )
        with_counts.append(
            SlurmAccountingSelectionCandidate(
                stack_name=candidate.stack_name,
                status=candidate.status,
                vpc_id=candidate.vpc_id,
                compatible=candidate.compatible,
                reason=candidate.reason,
                attached_instance_ids=attached_ids,
                db=candidate.db,
            )
        )
    return with_counts


def _select_duplicate_accounting_candidate(
    candidates: list[SlurmAccountingSelectionCandidate],
    *,
    preferred_stack_name: str,
    region: str,
) -> tuple[SlurmAccountingSelectionCandidate, str]:
    compatible = [candidate for candidate in candidates if candidate.compatible and candidate.db]
    if not compatible:
        details = "; ".join(
            f"{candidate.stack_name}: {candidate.reason}" for candidate in candidates
        )
        raise SlurmAccountingError(
            f"Multiple DayEC Slurm accounting stacks exist in region {region}, but none "
            f"is compatible with the requested cluster: {details}"
        )

    preferred_stack_name = preferred_stack_name.strip()
    if preferred_stack_name:
        preferred = next(
            (
                candidate
                for candidate in compatible
                if candidate.stack_name == preferred_stack_name
            ),
            None,
        )
        if preferred is not None:
            return (
                preferred,
                "explicit slurm_accounting_stack_name preference "
                "(the Ursa configuration selection hook)",
            )

    selected = sorted(
        compatible,
        key=lambda candidate: (
            -(candidate.attached_host_count or 0),
            candidate.stack_name,
        ),
    )[0]
    return selected, "largest attached-host count, then stack-name tie-breaker"


def _warn_and_delay_duplicate_accounting_selection(
    candidates: list[SlurmAccountingSelectionCandidate],
    *,
    selected: SlurmAccountingSelectionCandidate,
    selection_reason: str,
    preferred_stack_name: str,
    region: str,
    warning_callback: Callable[[str], None],
    sleep_fn: Callable[[float], None],
) -> None:
    warning_callback(
        "MULTIPLE DAYEC SLURM ACCOUNTING SERVICES DETECTED. "
        f"Region {region} has {len(candidates)} services; there should be exactly one."
    )
    warning_callback(
        "DYEC will continue instead of failing. attached_hosts counts unique EC2 instances "
        "whose network interfaces carry the accounting client security group; it does not "
        "claim a count of active SQL sessions."
    )
    for candidate in candidates:
        attached = (
            "unknown"
            if candidate.attached_host_count is None
            else str(candidate.attached_host_count)
        )
        preference = (
            "yes"
            if preferred_stack_name.strip() == candidate.stack_name
            else "no"
        )
        warning_callback(
            f"Candidate {candidate.stack_name}: status={candidate.status}; "
            f"vpc={candidate.vpc_id or 'missing'}; "
            f"compatible={'yes' if candidate.compatible else 'no'}; "
            f"attached_hosts={attached}; ursa_or_config_preferred={preference}; "
            f"reason={candidate.reason}"
        )
    preferred_stack_name = preferred_stack_name.strip()
    if preferred_stack_name and selected.stack_name != preferred_stack_name:
        warning_callback(
            f"Configured Ursa/accounting preference {preferred_stack_name} was not selected "
            "because it was not found among the compatible services."
        )
    warning_callback(
        f"AUTO-SELECTED {selected.stack_name}: {selection_reason}. "
        "Set Ursa's slurm_accounting.stack_name to the service used by "
        "ursa.day.lsmc.bio when that preference is known."
    )
    warning_callback(
        f"Automatic selection continues in {MULTIPLE_ACCOUNTING_SELECTION_DELAY_SECONDS} "
        "seconds. Press Ctrl-C now to abort."
    )
    sleep_fn(60)
    warning_callback("Automatic Slurm accounting selection continues in 30 seconds.")
    sleep_fn(20)
    warning_callback("Automatic Slurm accounting selection continues in 10 seconds.")
    sleep_fn(10)


def create_slurm_accounting_stack(
    aws_ctx: Any,
    *,
    region_az: str,
    vpc_id: str,
    private_subnet_id: str,
    stack_name: str,
    database_name: str,
    username: str,
    instance_type: str,
    assign_public_ip: bool = False,
    template_path: str = DEFAULT_TEMPLATE_PATH,
) -> SlurmAccountingDb:
    """Create the standalone DayEC Slurm accounting DB CloudFormation stack."""
    if not private_subnet_id.strip():
        raise SlurmAccountingError("Private subnet ID is required to create accounting DB.")
    database_name = validate_database_name(database_name)
    username = validate_username(username)
    stack_name = stack_name.strip()
    if not stack_name:
        raise SlurmAccountingError("Accounting stack name is required.")

    cfn = aws_ctx.client("cloudformation")
    template_body = _read_template_body(template_path)
    tags = build_slurm_accounting_tags(region_az, vpc_id)

    try:
        logger.info("Creating Slurm accounting stack %s in %s", stack_name, region_az)
        cfn.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Capabilities=["CAPABILITY_IAM"],
            EnableTerminationProtection=True,
            Parameters=[
                {"ParameterKey": "EnvironmentName", "ParameterValue": stack_name},
                {"ParameterKey": "RegionAz", "ParameterValue": region_az},
                {"ParameterKey": "VpcId", "ParameterValue": vpc_id},
                {"ParameterKey": "PrivateSubnetId", "ParameterValue": private_subnet_id},
                {"ParameterKey": "InstanceType", "ParameterValue": instance_type},
                {"ParameterKey": "DatabaseName", "ParameterValue": database_name},
                {"ParameterKey": "DatabaseUserName", "ParameterValue": username},
                {
                    "ParameterKey": "AssignPublicIpAddress",
                    "ParameterValue": "true" if assign_public_ip else "false",
                },
            ],
            Tags=tags,
        )
        waiter = cfn.get_waiter("stack_create_complete")
        waiter.wait(StackName=stack_name)
    except (BotoCoreError, ClientError) as exc:
        raise SlurmAccountingError(
            f"Failed to create Slurm accounting stack '{stack_name}': {exc}"
        ) from exc
    except Exception as exc:
        raise SlurmAccountingError(
            f"Failed to create Slurm accounting stack '{stack_name}': {exc}"
        ) from exc

    stack = _describe_stack_or_none(cfn, stack_name)
    if stack is None:
        raise SlurmAccountingError(
            f"Slurm accounting stack '{stack_name}' was created but cannot be described."
        )
    return _db_from_stack(stack)


def _read_template_body(template_path: str) -> str:
    candidate = Path(template_path)
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8")
    return resource_path(template_path).read_text(encoding="utf-8")


def _list_stack_summaries(cfn: Any) -> Iterable[dict[str, Any]]:
    try:
        paginator = cfn.get_paginator("list_stacks")
        for page in paginator.paginate(StackStatusFilter=list(DISCOVERABLE_STACK_STATUSES)):
            for summary in page.get("StackSummaries", []):
                yield summary
    except (BotoCoreError, ClientError) as exc:
        raise SlurmAccountingError(f"Unable to list CloudFormation stacks: {exc}") from exc
    except Exception as exc:
        raise SlurmAccountingError(f"Unable to list CloudFormation stacks: {exc}") from exc


def _describe_stack_or_none(cfn: Any, stack_name: str) -> dict[str, Any] | None:
    try:
        resp = cfn.describe_stacks(StackName=stack_name)
    except ClientError as exc:
        if _is_stack_not_found(exc):
            return None
        raise SlurmAccountingError(
            f"Unable to describe CloudFormation stack '{stack_name}': {exc}"
        ) from exc
    except BotoCoreError as exc:
        raise SlurmAccountingError(
            f"Unable to describe CloudFormation stack '{stack_name}': {exc}"
        ) from exc
    except Exception as exc:
        raise SlurmAccountingError(
            f"Unable to describe CloudFormation stack '{stack_name}': {exc}"
        ) from exc

    stacks = resp.get("Stacks", [])
    if not stacks:
        return None
    return stacks[0]


def _is_stack_not_found(exc: BaseException) -> bool:
    response = getattr(exc, "response", {})
    code = str(response.get("Error", {}).get("Code", ""))
    message = str(response.get("Error", {}).get("Message", ""))
    return code == "ValidationError" and "does not exist" in message


def _as_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise SlurmAccountingError(f"Expected datetime, got {value!r}.")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _stack_is_accounting_stack_in_region(
    stack: dict[str, Any],
    *,
    region: str,
) -> bool:
    tags = {str(t.get("Key")): str(t.get("Value")) for t in stack.get("Tags", [])}
    tagged_region = tags.get(ACCOUNTING_REGION_TAG_KEY, "").strip()
    return (
        tags.get(ACCOUNTING_COMPONENT_TAG_KEY) == ACCOUNTING_COMPONENT_TAG_VALUE
        and (not tagged_region or tagged_region == region)
    )


def _list_regional_accounting_stacks(
    cfn: Any,
    *,
    region: str,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for summary in _list_stack_summaries(cfn):
        name = str(summary.get("StackName") or "")
        if not name:
            continue
        stack = _describe_stack_or_none(cfn, name)
        # CloudFormation clients are region-scoped, so the component tag is the
        # authoritative membership test. This deliberately counts legacy stacks
        # created before ACCOUNTING_REGION_TAG_KEY was introduced.
        if stack is None or not _stack_is_accounting_stack_in_region(
            stack,
            region=region,
        ):
            continue
        matches.append(stack)
    return sorted(matches, key=lambda item: str(item.get("StackName") or ""))


def _require_stack_vpc(
    stack: dict[str, Any],
    *,
    requested_vpc_id: str,
    region: str,
) -> None:
    tags = _tags_by_key(stack.get("Tags", []))
    stack_name = str(stack.get("StackName") or "")
    stack_vpc_id = tags.get(ACCOUNTING_VPC_TAG_KEY, "").strip()
    if not stack_vpc_id:
        raise SlurmAccountingError(
            f"Regional Slurm accounting stack '{stack_name}' is missing required tag "
            f"{ACCOUNTING_VPC_TAG_KEY}."
        )
    if stack_vpc_id != requested_vpc_id:
        raise SlurmAccountingError(
            f"Regional Slurm accounting stack '{stack_name}' for {region} is in VPC "
            f"{stack_vpc_id}, but the selected cluster VPC is {requested_vpc_id}. "
            "A second regional accounting stack is forbidden; select subnets in the "
            "accounting VPC or establish an explicit non-overlapping network contract."
        )


def _stack_has_accounting_vpc_tags(stack: dict[str, Any], *, vpc_id: str) -> bool:
    tags = _tags_by_key(stack.get("Tags", []))
    return (
        tags.get(ACCOUNTING_COMPONENT_TAG_KEY) == ACCOUNTING_COMPONENT_TAG_VALUE
        and tags.get(ACCOUNTING_VPC_TAG_KEY) == vpc_id
    )


def _db_from_stack(stack: dict[str, Any]) -> SlurmAccountingDb:
    stack_name = str(stack.get("StackName") or "")
    status = str(stack.get("StackStatus") or "")
    if status not in HEALTHY_STACK_STATUSES:
        raise SlurmAccountingError(
            f"Slurm accounting stack '{stack_name}' is not healthy: {status}"
        )

    outputs = {str(o.get("OutputKey")): str(o.get("OutputValue") or "") for o in stack.get("Outputs", [])}
    missing = sorted(key for key in REQUIRED_OUTPUTS if not outputs.get(key))
    if missing:
        raise SlurmAccountingError(
            f"Slurm accounting stack '{stack_name}' is missing output(s): "
            + ", ".join(missing)
        )

    uri = outputs["AccountingDbUri"].strip()
    _validate_uri(uri)
    private_ip = outputs["AccountingDbPrivateIp"].strip()
    database_name = validate_database_name(outputs["AccountingDatabaseName"])
    username = validate_username(outputs["AccountingUserName"])
    secret_arn = outputs["AccountingPasswordSecretArn"].strip()
    client_sg = outputs["AccountingClientSecurityGroupId"].strip()

    if not private_ip:
        raise SlurmAccountingError(f"Slurm accounting stack '{stack_name}' has empty private IP.")
    if not secret_arn:
        raise SlurmAccountingError(f"Slurm accounting stack '{stack_name}' has empty secret ARN.")
    if not client_sg:
        raise SlurmAccountingError(
            f"Slurm accounting stack '{stack_name}' has empty client security group."
        )

    return SlurmAccountingDb(
        stack_name=stack_name,
        status=status,
        uri=uri,
        private_ip=private_ip,
        database_name=database_name,
        username=username,
        password_secret_arn=secret_arn,
        client_security_group_id=client_sg,
        instance_id=outputs.get("AccountingInstanceId", "").strip(),
    )


def _discover_accounting_dbs_by_instance_for_vpc(
    cfn: Any,
    *,
    vpc_id: str,
) -> tuple[dict[str, SlurmAccountingDb], dict[str, str]]:
    dbs: dict[str, SlurmAccountingDb] = {}
    rejected: dict[str, str] = {}
    for summary in _list_stack_summaries(cfn):
        name = str(summary.get("StackName") or "")
        if not name:
            continue
        stack = _describe_stack_or_none(cfn, name)
        if stack is None or not _stack_has_accounting_vpc_tags(stack, vpc_id=vpc_id):
            continue
        outputs = _stack_outputs(stack)
        instance_id = outputs.get("AccountingInstanceId", "").strip()
        try:
            db = _db_from_stack(stack)
        except SlurmAccountingError as exc:
            if instance_id:
                rejected[instance_id] = str(exc)
            continue
        if db.instance_id:
            dbs[db.instance_id] = db
    return dbs, rejected


def _stack_outputs(stack: dict[str, Any]) -> dict[str, str]:
    return {
        str(output.get("OutputKey")): str(output.get("OutputValue") or "")
        for output in stack.get("Outputs", [])
    }


def _validate_uri(uri: str) -> None:
    value = uri.strip()
    if not value:
        raise SlurmAccountingError("Accounting DB URI is empty.")
    if "://" in value:
        raise SlurmAccountingError(
            "Accounting DB URI must be host:port without a scheme such as mysql://."
        )
    if ":" not in value:
        raise SlurmAccountingError("Accounting DB URI must include a port, e.g. host:3306.")


def _tags_by_key(tags: Iterable[dict[str, Any]]) -> dict[str, str]:
    return {str(tag.get("Key")): str(tag.get("Value") or "") for tag in tags}


def _list_running_instances_in_vpc(ec2: Any, *, vpc_id: str) -> list[dict[str, Any]]:
    try:
        paginator = ec2.get_paginator("describe_instances")
        instances: list[dict[str, Any]] = []
        for page in paginator.paginate(
            Filters=[
                {"Name": "vpc-id", "Values": [vpc_id]},
                {"Name": "instance-state-name", "Values": ["running"]},
            ]
        ):
            for reservation in page.get("Reservations", []):
                instances.extend(reservation.get("Instances", []) or [])
        return instances
    except (BotoCoreError, ClientError) as exc:
        raise SlurmAccountingError(f"Unable to list EC2 instances for VPC {vpc_id}: {exc}") from exc
    except Exception as exc:
        raise SlurmAccountingError(f"Unable to list EC2 instances for VPC {vpc_id}: {exc}") from exc


def _attached_instance_ids_by_security_group(
    ec2: Any,
    security_group_ids: list[str],
) -> dict[str, tuple[str, ...]]:
    """Return unique attached EC2 instance ids for each requested security group."""
    if not security_group_ids:
        return {}
    requested = set(security_group_ids)
    attached: dict[str, set[str]] = {group_id: set() for group_id in security_group_ids}
    request: dict[str, Any] = {
        "Filters": [{"Name": "group-id", "Values": security_group_ids}],
    }
    try:
        while True:
            response = ec2.describe_network_interfaces(**request)
            for interface in response.get("NetworkInterfaces", []) or []:
                instance_id = str(
                    (interface.get("Attachment") or {}).get("InstanceId") or ""
                ).strip()
                if not instance_id:
                    continue
                for group in interface.get("Groups", []) or []:
                    group_id = str(group.get("GroupId") or "").strip()
                    if group_id in requested:
                        attached[group_id].add(instance_id)
            next_token = str(response.get("NextToken") or "").strip()
            if not next_token:
                break
            request["NextToken"] = next_token
    except (BotoCoreError, ClientError) as exc:
        raise SlurmAccountingError(
            f"Unable to count EC2 hosts attached to accounting client security groups: {exc}"
        ) from exc
    except Exception as exc:
        raise SlurmAccountingError(
            f"Unable to count EC2 hosts attached to accounting client security groups: {exc}"
        ) from exc
    return {
        group_id: tuple(sorted(instance_ids))
        for group_id, instance_ids in attached.items()
    }


def _security_group_ids_for_instances(instances: Iterable[dict[str, Any]]) -> list[str]:
    group_ids: set[str] = set()
    for instance in instances:
        for group in instance.get("SecurityGroups", []) or []:
            group_id = str(group.get("GroupId") or "").strip()
            if group_id:
                group_ids.add(group_id)
    return sorted(group_ids)


def _describe_security_groups(ec2: Any, group_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not group_ids:
        return {}
    try:
        groups: dict[str, dict[str, Any]] = {}
        for offset in range(0, len(group_ids), 100):
            response = ec2.describe_security_groups(GroupIds=group_ids[offset : offset + 100])
            for group in response.get("SecurityGroups", []) or []:
                group_id = str(group.get("GroupId") or "")
                if group_id:
                    groups[group_id] = group
        return groups
    except (BotoCoreError, ClientError) as exc:
        raise SlurmAccountingError(f"Unable to inspect EC2 security groups: {exc}") from exc
    except Exception as exc:
        raise SlurmAccountingError(f"Unable to inspect EC2 security groups: {exc}") from exc


def _candidate_from_instance(
    instance: dict[str, Any],
    *,
    source: str,
    selectable: bool,
    reason: str,
    db: SlurmAccountingDb | None = None,
) -> SlurmAccountingScanCandidate:
    tags = _tags_by_key(instance.get("Tags", []))
    return SlurmAccountingScanCandidate(
        instance_id=str(instance.get("InstanceId") or ""),
        name=tags.get("Name", ""),
        private_ip=str(instance.get("PrivateIpAddress") or ""),
        availability_zone=str(instance.get("Placement", {}).get("AvailabilityZone") or ""),
        vpc_id=str(instance.get("VpcId") or ""),
        source=source,
        selectable=selectable,
        reason=reason,
        db=db,
    )


def _instance_has_mysql_accounting_signal(
    instance: dict[str, Any],
    security_groups: dict[str, dict[str, Any]],
) -> bool:
    tags = _tags_by_key(instance.get("Tags", []))
    text_parts = [
        str(tags.get("Name", "")),
        *[str(value) for value in tags.values()],
    ]
    for group in instance.get("SecurityGroups", []) or []:
        group_id = str(group.get("GroupId") or "")
        group_payload = security_groups.get(group_id, {})
        text_parts.extend(
            [
                str(group.get("GroupName") or ""),
                str(group_payload.get("GroupName") or ""),
                str(group_payload.get("Description") or ""),
            ]
        )
        if _security_group_allows_tcp_port(group_payload, 3306):
            return True

    text = " ".join(text_parts).lower()
    return any(
        token in text
        for token in ("mysql", "mariadb", "slurm", "sacct", "accounting")
    )


def _security_group_allows_tcp_port(group: dict[str, Any], port: int) -> bool:
    for permission in group.get("IpPermissions", []) or []:
        protocol = str(permission.get("IpProtocol") or "")
        if protocol == "-1":
            return True
        if protocol != "tcp":
            continue
        from_port = permission.get("FromPort")
        to_port = permission.get("ToPort")
        if from_port is None or to_port is None:
            continue
        if int(from_port) <= port <= int(to_port):
            return True
    return False
