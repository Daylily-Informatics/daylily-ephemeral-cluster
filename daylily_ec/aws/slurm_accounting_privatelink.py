"""PrivateLink bridge to an existing DayEC Slurm accounting database."""

from __future__ import annotations

import ipaddress
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # pragma: no cover
    BotoCoreError = Exception  # type: ignore[misc,assignment]
    ClientError = Exception  # type: ignore[misc,assignment]

from daylily_ec.aws.slurm_accounting import SlurmAccountingDb
from daylily_ec.resources import resource_path

DEFAULT_TEMPLATE_PATH = "config/day_cluster/slurm_accounting_privatelink.yml"
BRIDGE_COMPONENT = "slurm-accounting-privatelink"
MANAGED_BY = "daylily-ephemeral-cluster"
HEALTHY_STACK_STATUSES = frozenset(
    {"CREATE_COMPLETE", "UPDATE_COMPLETE", "UPDATE_ROLLBACK_COMPLETE"}
)
REQUIRED_PROVIDER_OUTPUTS = frozenset(
    {
        "AccountingDbPrivateIp",
        "AccountingDatabaseName",
        "AccountingUserName",
        "AccountingPasswordSecretArn",
        "AccountingInstanceId",
    }
)
REQUIRED_BRIDGE_OUTPUTS = frozenset(
    {
        "AccountingClientSecurityGroupId",
        "AccountingClientSecretReadPolicyArn",
        "AccountingDatabaseName",
        "AccountingEndpointId",
        "AccountingEndpointServiceId",
        "AccountingInstanceId",
        "AccountingPasswordSecretArn",
        "AccountingTargetGroupArn",
        "AccountingUserName",
        "ConsumerEndpointSubnetId",
        "ConsumerVpcId",
        "ProviderAccountingStackName",
        "ProviderVpcId",
    }
)


class SlurmAccountingPrivateLinkError(RuntimeError):
    """Raised when the accounting bridge cannot be created or resolved safely."""


@dataclass(frozen=True)
class SlurmAccountingPrivateLinkBridge:
    stack_name: str
    status: str
    provider_accounting_stack_name: str
    provider_vpc_id: str
    consumer_vpc_id: str
    endpoint_id: str
    endpoint_service_id: str
    endpoint_subnet_id: str
    client_security_group_id: str
    client_secret_read_policy_arn: str
    target_group_arn: str = field(repr=False)
    uri: str = field(repr=False)
    endpoint_private_ip: str = field(repr=False)
    database_name: str
    username: str
    password_secret_arn: str = field(repr=False)
    accounting_instance_id: str

    def as_accounting_db(self) -> SlurmAccountingDb:
        return SlurmAccountingDb(
            stack_name=self.stack_name,
            status=self.status,
            uri=self.uri,
            private_ip=self.endpoint_private_ip,
            database_name=self.database_name,
            username=self.username,
            password_secret_arn=self.password_secret_arn,
            client_security_group_id=self.client_security_group_id,
            client_secret_read_policy_arn=self.client_secret_read_policy_arn,
            instance_id=self.accounting_instance_id,
        )


@dataclass(frozen=True)
class _Provider:
    stack_name: str
    vpc_id: str
    subnet_id: str
    availability_zone: str
    database_private_ip: str = field(repr=False)
    database_security_group_id: str
    database_name: str
    username: str
    password_secret_arn: str = field(repr=False)
    instance_id: str


def derive_privatelink_stack_name(consumer_vpc_id: str) -> str:
    value = consumer_vpc_id.strip()
    if not re.fullmatch(r"vpc-[0-9a-f]{8,17}", value):
        raise SlurmAccountingPrivateLinkError("A valid consumer VPC ID is required.")
    return f"dayec-sacct-pl-{value}"


def ensure_slurm_accounting_privatelink_bridge(
    aws_ctx: Any,
    *,
    provider_accounting_stack_name: str,
    consumer_vpc_id: str,
    consumer_endpoint_subnet_cidr: str,
    stack_name: str = "",
    template_path: str = DEFAULT_TEMPLATE_PATH,
    sleep_fn: Callable[[float], None] = time.sleep,
    target_health_attempts: int = 60,
) -> SlurmAccountingPrivateLinkBridge:
    """Create or reuse an exact account-local, TCP/3306-only bridge."""
    cfn = aws_ctx.client("cloudformation")
    ec2 = aws_ctx.client("ec2")
    provider = _resolve_provider(cfn, ec2, provider_accounting_stack_name)
    consumer_vpc_id = consumer_vpc_id.strip()
    if provider.vpc_id == consumer_vpc_id:
        raise SlurmAccountingPrivateLinkError(
            "Provider and consumer VPCs are identical; use direct accounting attachment."
        )
    name = stack_name.strip() or derive_privatelink_stack_name(consumer_vpc_id)
    existing = _describe_stack(cfn, name)
    existing_subnet_id = ""
    if existing is not None:
        _validate_existing_bridge(
            existing,
            provider_stack_name=provider.stack_name,
            consumer_vpc_id=consumer_vpc_id,
        )
        existing_subnet_id = next(
            (
                str(item.get("OutputValue") or "")
                for item in existing.get("Outputs", [])
                if item.get("OutputKey") == "ConsumerEndpointSubnetId"
            ),
            "",
        )
        if not existing_subnet_id:
            raise SlurmAccountingPrivateLinkError(
                "Existing PrivateLink stack is missing its endpoint subnet output."
            )
    _validate_consumer_network(
        ec2,
        consumer_vpc_id=consumer_vpc_id,
        endpoint_subnet_cidr=consumer_endpoint_subnet_cidr,
        allowed_existing_subnet_id=existing_subnet_id,
    )

    template_body = _read_template(template_path)
    tags = [
        {"Key": "daylily-ec:component", "Value": BRIDGE_COMPONENT},
        {"Key": "daylily-ec:region", "Value": aws_ctx.region},
        {"Key": "daylily-ec:managed-by", "Value": MANAGED_BY},
        {"Key": "daylily-ec:provider-accounting-stack", "Value": provider.stack_name},
        {"Key": "daylily-ec:provider-vpc-id", "Value": provider.vpc_id},
        {"Key": "daylily-ec:consumer-vpc-id", "Value": consumer_vpc_id},
    ]
    parameters = {
        "EnvironmentName": name,
        "ProviderVpcId": provider.vpc_id,
        "ProviderSubnetId": provider.subnet_id,
        "ProviderDatabasePrivateIp": provider.database_private_ip,
        "ProviderDatabaseSecurityGroupId": provider.database_security_group_id,
        "ProviderAccountingStackName": provider.stack_name,
        "ProviderAccountingPasswordSecretArn": provider.password_secret_arn,
        "AccountingDatabaseName": provider.database_name,
        "AccountingUserName": provider.username,
        "AccountingInstanceId": provider.instance_id,
        "ConsumerVpcId": consumer_vpc_id,
        "ConsumerEndpointAvailabilityZone": provider.availability_zone,
        "ConsumerEndpointSubnetCidr": consumer_endpoint_subnet_cidr,
    }
    stack_parameters = [
        {"ParameterKey": key, "ParameterValue": value} for key, value in parameters.items()
    ]
    if existing is not None:
        try:
            cfn.update_stack(
                StackName=name,
                TemplateBody=template_body,
                Capabilities=["CAPABILITY_IAM"],
                Parameters=stack_parameters,
                Tags=tags,
            )
            cfn.get_waiter("stack_update_complete").wait(StackName=name)
        except ClientError as exc:
            if "No updates are to be performed" not in str(exc):
                raise SlurmAccountingPrivateLinkError(
                    f"PrivateLink stack '{name}' did not update successfully; inspect "
                    "its CloudFormation events before any recovery action."
                ) from None
        except BotoCoreError:
            raise SlurmAccountingPrivateLinkError(
                f"PrivateLink stack '{name}' did not update successfully; inspect its "
                "CloudFormation events before any recovery action."
            ) from None
        except Exception:
            raise SlurmAccountingPrivateLinkError(
                f"PrivateLink stack '{name}' did not reach UPDATE_COMPLETE safely."
            ) from None
        updated = _describe_stack(cfn, name)
        if updated is None:
            raise SlurmAccountingPrivateLinkError(
                f"PrivateLink stack '{name}' was updated but cannot be described."
            )
        return _wait_for_healthy_bridge(
            aws_ctx,
            updated,
            sleep_fn=sleep_fn,
            attempts=target_health_attempts,
        )

    try:
        cfn.create_stack(
            StackName=name,
            TemplateBody=template_body,
            Capabilities=["CAPABILITY_IAM"],
            EnableTerminationProtection=True,
            Parameters=stack_parameters,
            Tags=tags,
        )
        cfn.get_waiter("stack_create_complete").wait(StackName=name)
    except (BotoCoreError, ClientError):
        raise SlurmAccountingPrivateLinkError(
            f"PrivateLink stack '{name}' did not create successfully; inspect its "
            "CloudFormation events before any recovery action."
        ) from None
    except Exception:
        raise SlurmAccountingPrivateLinkError(
            f"PrivateLink stack '{name}' did not reach CREATE_COMPLETE safely."
        ) from None

    created = _describe_stack(cfn, name)
    if created is None:
        raise SlurmAccountingPrivateLinkError(
            f"PrivateLink stack '{name}' was created but cannot be described."
        )
    return _wait_for_healthy_bridge(
        aws_ctx,
        created,
        sleep_fn=sleep_fn,
        attempts=target_health_attempts,
    )


def reconcile_existing_slurm_accounting_privatelink_bridge_for_consumer(
    aws_ctx: Any,
    *,
    consumer_vpc_id: str,
    provider_accounting_stack_name: str,
    sleep_fn: Callable[[float], None] = time.sleep,
    target_health_attempts: int = 60,
) -> SlurmAccountingPrivateLinkBridge:
    """Update the deterministic existing bridge to the packaged template contract.

    Reconciliation is intentionally existing-only. The endpoint subnet CIDR is
    read from the bridge stack's authoritative CloudFormation parameter; a
    missing stack or parameter fails instead of guessing network configuration.
    """
    consumer_vpc_id = consumer_vpc_id.strip()
    provider_accounting_stack_name = provider_accounting_stack_name.strip()
    if not provider_accounting_stack_name:
        raise SlurmAccountingPrivateLinkError(
            "An explicit provider accounting stack name is required for bridge reconciliation."
        )
    stack_name = derive_privatelink_stack_name(consumer_vpc_id)
    stack = _describe_stack(aws_ctx.client("cloudformation"), stack_name)
    if stack is None:
        raise SlurmAccountingPrivateLinkError(
            f"PrivateLink stack '{stack_name}' does not exist; create it explicitly with "
            "a reviewed consumer endpoint subnet CIDR."
        )
    endpoint_subnet_cidr = next(
        (
            str(item.get("ParameterValue") or "").strip()
            for item in stack.get("Parameters", [])
            if item.get("ParameterKey") == "ConsumerEndpointSubnetCidr"
        ),
        "",
    )
    if not endpoint_subnet_cidr:
        raise SlurmAccountingPrivateLinkError(
            f"PrivateLink stack '{stack_name}' is missing its authoritative "
            "ConsumerEndpointSubnetCidr parameter."
        )
    return ensure_slurm_accounting_privatelink_bridge(
        aws_ctx,
        provider_accounting_stack_name=provider_accounting_stack_name,
        consumer_vpc_id=consumer_vpc_id,
        consumer_endpoint_subnet_cidr=endpoint_subnet_cidr,
        stack_name=stack_name,
        sleep_fn=sleep_fn,
        target_health_attempts=target_health_attempts,
    )


def resolve_slurm_accounting_privatelink_bridge(
    aws_ctx: Any,
    *,
    stack_name: str,
    require_healthy_target: bool = True,
) -> SlurmAccountingPrivateLinkBridge:
    cfn = aws_ctx.client("cloudformation")
    stack = _describe_stack(cfn, stack_name.strip())
    if stack is None:
        raise SlurmAccountingPrivateLinkError(f"PrivateLink stack '{stack_name}' does not exist.")
    return _resolve_bridge(
        aws_ctx,
        stack,
        require_healthy_target=require_healthy_target,
    )


def resolve_slurm_accounting_privatelink_bridge_for_consumer(
    aws_ctx: Any,
    *,
    consumer_vpc_id: str,
    provider_accounting_stack_name: str = "",
    require_healthy_target: bool = True,
) -> SlurmAccountingPrivateLinkBridge:
    """Resolve the one deterministic, already-existing bridge for a consumer VPC.

    This is reuse-only: it derives the managed bridge stack name from the exact
    consumer VPC and never creates, updates, or broadly selects infrastructure.
    An explicit provider name, when supplied, is an additional identity check.
    """
    consumer_vpc_id = consumer_vpc_id.strip()
    bridge = resolve_slurm_accounting_privatelink_bridge(
        aws_ctx,
        stack_name=derive_privatelink_stack_name(consumer_vpc_id),
        require_healthy_target=require_healthy_target,
    )
    if bridge.consumer_vpc_id != consumer_vpc_id:
        raise SlurmAccountingPrivateLinkError(
            "The deterministic PrivateLink bridge consumer VPC does not match the "
            "requested cluster VPC."
        )
    provider_accounting_stack_name = provider_accounting_stack_name.strip()
    if (
        provider_accounting_stack_name
        and bridge.provider_accounting_stack_name != provider_accounting_stack_name
    ):
        raise SlurmAccountingPrivateLinkError(
            "The deterministic PrivateLink bridge provider does not match the "
            "requested accounting stack."
        )
    return bridge


def _resolve_provider(cfn: Any, ec2: Any, stack_name: str) -> _Provider:
    name = stack_name.strip()
    if not name:
        raise SlurmAccountingPrivateLinkError(
            "An explicit provider accounting stack name is required."
        )
    stack = _describe_stack(cfn, name)
    if stack is None or str(stack.get("StackStatus") or "") not in HEALTHY_STACK_STATUSES:
        raise SlurmAccountingPrivateLinkError(
            f"Provider accounting stack '{name}' is missing or unhealthy."
        )
    tags = _tags(stack)
    if tags.get("daylily-ec:component") != "slurm-accounting-mysql":
        raise SlurmAccountingPrivateLinkError(
            f"Provider stack '{name}' is not a DayEC Slurm accounting database."
        )
    vpc_id = tags.get("daylily-ec:vpc-id", "")
    outputs = _outputs(stack, REQUIRED_PROVIDER_OUTPUTS)
    instance_id = outputs["AccountingInstanceId"]
    try:
        reservations = ec2.describe_instances(InstanceIds=[instance_id]).get("Reservations", [])
        instances = [
            instance
            for reservation in reservations
            for instance in reservation.get("Instances", [])
        ]
    except (BotoCoreError, ClientError):
        raise SlurmAccountingPrivateLinkError(
            "The provider accounting instance could not be inspected safely."
        ) from None
    if len(instances) != 1:
        raise SlurmAccountingPrivateLinkError(
            "The provider accounting stack must resolve to exactly one EC2 instance."
        )
    instance = instances[0]
    if instance.get("State", {}).get("Name") != "running":
        raise SlurmAccountingPrivateLinkError("The provider accounting instance is not running.")
    if instance.get("VpcId") != vpc_id:
        raise SlurmAccountingPrivateLinkError("Provider accounting VPC evidence is inconsistent.")
    try:
        resource = cfn.describe_stack_resource(
            StackName=name,
            LogicalResourceId="AccountingDbSecurityGroup",
        ).get("StackResourceDetail", {})
    except (BotoCoreError, ClientError):
        raise SlurmAccountingPrivateLinkError(
            "The provider database security group could not be resolved safely."
        ) from None
    database_sg = str(resource.get("PhysicalResourceId") or "")
    attached_groups = {
        str(group.get("GroupId") or "") for group in instance.get("SecurityGroups", [])
    }
    if not database_sg or database_sg not in attached_groups:
        raise SlurmAccountingPrivateLinkError(
            "The provider database security-group attachment is inconsistent."
        )
    return _Provider(
        stack_name=name,
        vpc_id=vpc_id,
        subnet_id=str(instance.get("SubnetId") or ""),
        availability_zone=str(instance.get("Placement", {}).get("AvailabilityZone") or ""),
        database_private_ip=outputs["AccountingDbPrivateIp"],
        database_security_group_id=database_sg,
        database_name=outputs["AccountingDatabaseName"],
        username=outputs["AccountingUserName"],
        password_secret_arn=outputs["AccountingPasswordSecretArn"],
        instance_id=instance_id,
    )


def _validate_consumer_network(
    ec2: Any,
    *,
    consumer_vpc_id: str,
    endpoint_subnet_cidr: str,
    allowed_existing_subnet_id: str = "",
) -> None:
    try:
        network = ipaddress.ip_network(endpoint_subnet_cidr.strip(), strict=True)
    except ValueError:
        raise SlurmAccountingPrivateLinkError(
            "Consumer endpoint subnet CIDR must be a canonical IPv4 /28."
        ) from None
    if network.version != 4 or network.prefixlen != 28:
        raise SlurmAccountingPrivateLinkError(
            "Consumer endpoint subnet CIDR must be a canonical IPv4 /28."
        )
    try:
        vpcs = ec2.describe_vpcs(VpcIds=[consumer_vpc_id]).get("Vpcs", [])
        subnets = ec2.describe_subnets(
            Filters=[{"Name": "vpc-id", "Values": [consumer_vpc_id]}]
        ).get("Subnets", [])
    except (BotoCoreError, ClientError):
        raise SlurmAccountingPrivateLinkError(
            "The consumer VPC could not be inspected safely."
        ) from None
    if len(vpcs) != 1:
        raise SlurmAccountingPrivateLinkError("Consumer VPC does not exist uniquely.")
    associations = vpcs[0].get("CidrBlockAssociationSet", []) or []
    vpc_networks = [
        ipaddress.ip_network(item["CidrBlock"], strict=True)
        for item in associations
        if item.get("CidrBlock")
    ] or [ipaddress.ip_network(vpcs[0]["CidrBlock"], strict=True)]
    if not any(network.subnet_of(vpc_network) for vpc_network in vpc_networks):
        raise SlurmAccountingPrivateLinkError(
            "Consumer endpoint subnet CIDR is outside the consumer VPC CIDR blocks."
        )
    for subnet in subnets:
        existing = ipaddress.ip_network(subnet["CidrBlock"], strict=True)
        if network.overlaps(existing) and subnet.get("SubnetId") != allowed_existing_subnet_id:
            raise SlurmAccountingPrivateLinkError(
                f"Consumer endpoint subnet CIDR overlaps existing subnet {subnet.get('SubnetId')}."
            )


def _validate_existing_bridge(
    stack: dict[str, Any],
    *,
    provider_stack_name: str,
    consumer_vpc_id: str,
) -> None:
    status = str(stack.get("StackStatus") or "")
    tags = _tags(stack)
    if status not in HEALTHY_STACK_STATUSES:
        raise SlurmAccountingPrivateLinkError(
            f"Existing PrivateLink stack is not healthy: {status}."
        )
    expected = {
        "daylily-ec:component": BRIDGE_COMPONENT,
        "daylily-ec:managed-by": MANAGED_BY,
        "daylily-ec:provider-accounting-stack": provider_stack_name,
        "daylily-ec:consumer-vpc-id": consumer_vpc_id,
    }
    if any(tags.get(key) != value for key, value in expected.items()):
        raise SlurmAccountingPrivateLinkError(
            "Existing PrivateLink stack identity does not match the requested bridge."
        )


def _wait_for_healthy_bridge(
    aws_ctx: Any,
    stack: dict[str, Any],
    *,
    sleep_fn: Callable[[float], None],
    attempts: int,
) -> SlurmAccountingPrivateLinkBridge:
    for attempt in range(max(attempts, 1)):
        try:
            return _resolve_bridge(aws_ctx, stack, require_healthy_target=True)
        except SlurmAccountingPrivateLinkError as exc:
            if "target is not healthy" not in str(exc) or attempt + 1 >= max(attempts, 1):
                raise
            sleep_fn(10)
    raise AssertionError("unreachable")


def _resolve_bridge(
    aws_ctx: Any,
    stack: dict[str, Any],
    *,
    require_healthy_target: bool,
) -> SlurmAccountingPrivateLinkBridge:
    name = str(stack.get("StackName") or "")
    status = str(stack.get("StackStatus") or "")
    if status not in HEALTHY_STACK_STATUSES:
        raise SlurmAccountingPrivateLinkError(
            f"PrivateLink stack '{name}' is not healthy: {status}."
        )
    outputs = _outputs(stack, REQUIRED_BRIDGE_OUTPUTS)
    ec2 = aws_ctx.client("ec2")
    elbv2 = aws_ctx.client("elbv2")
    try:
        endpoints = ec2.describe_vpc_endpoints(
            VpcEndpointIds=[outputs["AccountingEndpointId"]]
        ).get("VpcEndpoints", [])
    except (BotoCoreError, ClientError):
        raise SlurmAccountingPrivateLinkError(
            "The PrivateLink interface endpoint could not be inspected safely."
        ) from None
    if len(endpoints) != 1 or endpoints[0].get("State") != "available":
        raise SlurmAccountingPrivateLinkError(
            "The PrivateLink interface endpoint is not available."
        )
    endpoint = endpoints[0]
    dns_names = sorted(
        str(entry.get("DnsName") or "")
        for entry in endpoint.get("DnsEntries", [])
        if entry.get("DnsName") and not str(entry.get("DnsName")).startswith("*.")
    )
    if not dns_names:
        raise SlurmAccountingPrivateLinkError(
            "The PrivateLink interface endpoint has no usable DNS name."
        )
    eni_ids = endpoint.get("NetworkInterfaceIds", [])
    try:
        enis = ec2.describe_network_interfaces(NetworkInterfaceIds=eni_ids).get(
            "NetworkInterfaces", []
        )
    except (BotoCoreError, ClientError):
        raise SlurmAccountingPrivateLinkError(
            "The PrivateLink endpoint network interface could not be inspected safely."
        ) from None
    if len(enis) != 1 or not enis[0].get("PrivateIpAddress"):
        raise SlurmAccountingPrivateLinkError(
            "The PrivateLink bridge must have exactly one endpoint network interface."
        )
    try:
        target_descriptions = elbv2.describe_target_health(
            TargetGroupArn=outputs["AccountingTargetGroupArn"]
        ).get("TargetHealthDescriptions", [])
    except (BotoCoreError, ClientError):
        raise SlurmAccountingPrivateLinkError(
            "The PrivateLink database target could not be inspected safely."
        ) from None
    if require_healthy_target and not any(
        item.get("TargetHealth", {}).get("State") == "healthy" for item in target_descriptions
    ):
        raise SlurmAccountingPrivateLinkError("The PrivateLink database target is not healthy.")
    return SlurmAccountingPrivateLinkBridge(
        stack_name=name,
        status=status,
        provider_accounting_stack_name=outputs["ProviderAccountingStackName"],
        provider_vpc_id=outputs["ProviderVpcId"],
        consumer_vpc_id=outputs["ConsumerVpcId"],
        endpoint_id=outputs["AccountingEndpointId"],
        endpoint_service_id=outputs["AccountingEndpointServiceId"],
        endpoint_subnet_id=outputs["ConsumerEndpointSubnetId"],
        client_security_group_id=outputs["AccountingClientSecurityGroupId"],
        client_secret_read_policy_arn=outputs["AccountingClientSecretReadPolicyArn"],
        target_group_arn=outputs["AccountingTargetGroupArn"],
        uri=f"{dns_names[0]}:3306",
        endpoint_private_ip=str(enis[0]["PrivateIpAddress"]),
        database_name=outputs["AccountingDatabaseName"],
        username=outputs["AccountingUserName"],
        password_secret_arn=outputs["AccountingPasswordSecretArn"],
        accounting_instance_id=outputs["AccountingInstanceId"],
    )


def _outputs(stack: dict[str, Any], required: frozenset[str]) -> dict[str, str]:
    values = {
        str(item.get("OutputKey") or ""): str(item.get("OutputValue") or "")
        for item in stack.get("Outputs", [])
    }
    missing = sorted(key for key in required if not values.get(key))
    if missing:
        raise SlurmAccountingPrivateLinkError(
            "CloudFormation stack is missing required outputs: " + ", ".join(missing)
        )
    return values


def _tags(stack: dict[str, Any]) -> dict[str, str]:
    return {
        str(item.get("Key") or ""): str(item.get("Value") or "") for item in stack.get("Tags", [])
    }


def _describe_stack(cfn: Any, stack_name: str) -> dict[str, Any] | None:
    try:
        stacks = cfn.describe_stacks(StackName=stack_name).get("Stacks", [])
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ValidationError":
            return None
        raise SlurmAccountingPrivateLinkError(
            f"CloudFormation stack '{stack_name}' could not be described safely."
        ) from None
    except BotoCoreError:
        raise SlurmAccountingPrivateLinkError(
            f"CloudFormation stack '{stack_name}' could not be described safely."
        ) from None
    if len(stacks) != 1:
        raise SlurmAccountingPrivateLinkError(
            f"CloudFormation stack '{stack_name}' did not resolve uniquely."
        )
    return stacks[0]


def _read_template(template_path: str) -> str:
    candidate = Path(template_path)
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8")
    return resource_path(template_path).read_text(encoding="utf-8")
