"""DayEC-owned Slurm accounting database discovery and provisioning."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # pragma: no cover - exercised only on trimmed botocore installs
    BotoCoreError = Exception  # type: ignore[misc,assignment]
    ClientError = Exception  # type: ignore[misc,assignment]

from daylily_ec.resources import resource_path

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE_PATH = "config/day_cluster/slurm_accounting_mysql_ec2.yml"
DEFAULT_ACCOUNTING_DATABASE_NAME = "dayec_slurm_acct"
DEFAULT_ACCOUNTING_USERNAME = "slurm_acct"
DEFAULT_ACCOUNTING_INSTANCE_TYPE = "t4g.micro"

ACCOUNTING_COMPONENT_TAG_KEY = "daylily-ec:component"
ACCOUNTING_COMPONENT_TAG_VALUE = "slurm-accounting-mysql"
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


def derive_slurm_accounting_stack_name(region_az: str) -> str:
    """Return the deterministic accounting stack name for a Region/AZ."""
    region_az = region_az.strip()
    if not region_az:
        raise ValueError("region_az must not be empty")
    return f"dayec-slurm-accounting-{region_az}"


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
    return [
        {"Key": ACCOUNTING_COMPONENT_TAG_KEY, "Value": ACCOUNTING_COMPONENT_TAG_VALUE},
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
    """Discover DayEC-tagged Slurm accounting stacks in one VPC/AZ."""
    cfn = aws_ctx.client("cloudformation")
    if stack_name.strip():
        stack = _describe_stack_or_none(cfn, stack_name.strip())
        if stack is None:
            return []
        if not _stack_has_accounting_tags(stack, region_az=region_az, vpc_id=vpc_id):
            raise SlurmAccountingError(
                f"Stack '{stack_name}' exists but is not tagged as the DayEC "
                f"Slurm accounting stack for {region_az} in VPC {vpc_id}."
            )
        return [_db_from_stack(stack)]

    matches: list[SlurmAccountingDb] = []
    for summary in _list_stack_summaries(cfn):
        name = str(summary.get("StackName") or "")
        if not name:
            continue
        stack = _describe_stack_or_none(cfn, name)
        if stack is None:
            continue
        if not _stack_has_accounting_tags(stack, region_az=region_az, vpc_id=vpc_id):
            continue
        matches.append(_db_from_stack(stack))
    return matches


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
    template_path: str = DEFAULT_TEMPLATE_PATH,
) -> SlurmAccountingDb:
    """Resolve one accounting DB stack, creating it only when explicitly allowed."""
    database_name = validate_database_name(database_name or DEFAULT_ACCOUNTING_DATABASE_NAME)
    username = validate_username(username or DEFAULT_ACCOUNTING_USERNAME)
    stack_name = stack_name.strip()

    matches = discover_slurm_accounting_dbs(
        aws_ctx,
        region_az=region_az,
        vpc_id=vpc_id,
        stack_name=stack_name,
    )
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(sorted(db.stack_name for db in matches))
        raise SlurmAccountingError(
            f"Multiple DayEC Slurm accounting stacks match {region_az} in VPC {vpc_id}: {names}"
        )
    if not create_if_missing:
        raise SlurmAccountingError(
            f"No DayEC Slurm accounting stack exists for {region_az} in VPC {vpc_id}; "
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
        template_path=template_path,
    )


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


def _stack_has_accounting_tags(stack: dict[str, Any], *, region_az: str, vpc_id: str) -> bool:
    tags = {str(t.get("Key")): str(t.get("Value")) for t in stack.get("Tags", [])}
    return (
        tags.get(ACCOUNTING_COMPONENT_TAG_KEY) == ACCOUNTING_COMPONENT_TAG_VALUE
        and tags.get(ACCOUNTING_REGION_AZ_TAG_KEY) == region_az
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
