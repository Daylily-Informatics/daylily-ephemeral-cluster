"""Read-only, non-secret Slurm-accounting provider and bridge inspection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from daylily_ec.aws.context import AWSContext, parse_region_az
from daylily_ec.aws.slurm_accounting import (
    ACCOUNTING_COMPONENT_TAG_KEY,
    ACCOUNTING_COMPONENT_TAG_VALUE,
    ACCOUNTING_MANAGED_BY_TAG_KEY,
    ACCOUNTING_MANAGED_BY_TAG_VALUE,
    ACCOUNTING_REGION_AZ_TAG_KEY,
    ACCOUNTING_REGION_TAG_KEY,
    ACCOUNTING_VPC_TAG_KEY,
    HEALTHY_STACK_STATUSES,
    REQUIRED_OUTPUTS,
    list_regional_slurm_accounting_stacks,
)
from daylily_ec.aws.slurm_accounting_privatelink import (
    SlurmAccountingPrivateLinkError,
    resolve_slurm_accounting_privatelink_bridge,
)

SLURM_ACCOUNTING_INSPECTION_SCHEMA = "dyec.slurm_accounting_inspection.v1"
MAX_INSPECTION_TEXT_LENGTH = 256
MAX_REGIONAL_PROVIDERS = 100


class SlurmAccountingInspectionError(RuntimeError):
    """Raised when read-only accounting inspection cannot complete safely."""


def _required_text(value: object, *, field: str) -> str:
    text = str(value or "")
    if not text or text != text.strip():
        raise SlurmAccountingInspectionError(f"{field} must be a non-empty trimmed string.")
    return _bounded_text(text, field=field)


def _optional_text(value: object, *, field: str) -> str | None:
    text = str(value or "")
    if not text:
        return None
    if text != text.strip():
        raise SlurmAccountingInspectionError(f"{field} must be a trimmed string when supplied.")
    return _bounded_text(text, field=field)


def _bounded_text(value: object, *, field: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise SlurmAccountingInspectionError(f"{field} returned a non-string identity.")
    if not value and allow_empty:
        return ""
    if (
        not value
        or value != value.strip()
        or len(value) > MAX_INSPECTION_TEXT_LENGTH
        or any(not character.isascii() or ord(character) < 32 for character in value)
    ):
        raise SlurmAccountingInspectionError(f"{field} returned an invalid bounded identity.")
    return value


def _tags(stack: dict[str, Any]) -> dict[str, str]:
    tags = stack.get("Tags", [])
    if not isinstance(tags, list):
        raise SlurmAccountingInspectionError("A regional provider returned invalid tags.")
    return {
        _bounded_text(str(item.get("Key") or ""), field="provider tag key"): _bounded_text(
            str(item.get("Value") or ""),
            field="provider tag value",
            allow_empty=True,
        )
        for item in tags
        if isinstance(item, dict) and item.get("Key")
    }


def _outputs(stack: dict[str, Any]) -> dict[str, str]:
    outputs = stack.get("Outputs", [])
    if not isinstance(outputs, list):
        raise SlurmAccountingInspectionError("A regional provider returned invalid outputs.")
    result: dict[str, str] = {}
    for item in outputs:
        if not isinstance(item, dict) or not item.get("OutputKey"):
            continue
        key = _bounded_text(str(item["OutputKey"]), field="provider output key")
        value = str(item.get("OutputValue") or "")
        if key in {
            "AccountingDatabaseName",
            "AccountingUserName",
            "AccountingInstanceId",
        }:
            result[key] = _bounded_text(
                value,
                field=f"provider output {key}",
                allow_empty=True,
            )
        else:
            # Secret-bearing and endpoint outputs are used only as presence checks.
            result[key] = "present" if value else ""
    return result


def _provider_payload(
    stack: dict[str, Any],
    *,
    instance_types: dict[str, str],
) -> dict[str, Any]:
    tags = _tags(stack)
    outputs = _outputs(stack)
    stack_name = _bounded_text(stack.get("StackName"), field="provider stack name")
    status = _bounded_text(stack.get("StackStatus"), field="provider stack status")
    required_outputs_present = all(outputs.get(key) for key in REQUIRED_OUTPUTS)
    instance_id = _bounded_text(
        outputs.get("AccountingInstanceId", ""),
        field="provider instance id",
        allow_empty=True,
    )
    instance_type = instance_types.get(instance_id, "")
    contract_healthy = (
        status in HEALTHY_STACK_STATUSES
        and tags.get(ACCOUNTING_COMPONENT_TAG_KEY) == ACCOUNTING_COMPONENT_TAG_VALUE
        and tags.get(ACCOUNTING_MANAGED_BY_TAG_KEY) == ACCOUNTING_MANAGED_BY_TAG_VALUE
        and bool(tags.get(ACCOUNTING_VPC_TAG_KEY))
        and required_outputs_present
        and bool(instance_type)
    )
    return {
        "stack_name": stack_name,
        "status": status,
        "region": _bounded_text(
            tags.get(ACCOUNTING_REGION_TAG_KEY, ""),
            field="provider region tag",
            allow_empty=True,
        ),
        "region_az": _bounded_text(
            tags.get(ACCOUNTING_REGION_AZ_TAG_KEY, ""),
            field="provider region-AZ tag",
            allow_empty=True,
        ),
        "vpc_id": _bounded_text(
            tags.get(ACCOUNTING_VPC_TAG_KEY, ""),
            field="provider VPC tag",
            allow_empty=True,
        ),
        "database_name": _bounded_text(
            outputs.get("AccountingDatabaseName", ""),
            field="provider database name",
            allow_empty=True,
        ),
        "db_username": _bounded_text(
            outputs.get("AccountingUserName", ""),
            field="provider database user",
            allow_empty=True,
        ),
        "instance_id": instance_id,
        "instance_type": instance_type,
        "required_outputs_present": required_outputs_present,
        "contract_healthy": contract_healthy,
    }


def _exact_instance_types(aws_ctx: Any, instance_ids: set[str]) -> dict[str, str]:
    if not instance_ids:
        return {}
    try:
        response = aws_ctx.client("ec2").describe_instances(InstanceIds=sorted(instance_ids))
    except Exception:  # noqa: BLE001 - provider text is never public
        raise SlurmAccountingInspectionError(
            "The accounting provider instance inventory could not be inspected safely."
        ) from None
    resolved: dict[str, str] = {}
    reservations = response.get("Reservations")
    if not isinstance(reservations, list):
        raise SlurmAccountingInspectionError(
            "The accounting provider instance inventory is invalid."
        )
    for reservation in reservations:
        if not isinstance(reservation, dict):
            raise SlurmAccountingInspectionError(
                "The accounting provider instance inventory is invalid."
            )
        instances = reservation.get("Instances")
        if not isinstance(instances, list):
            raise SlurmAccountingInspectionError(
                "The accounting provider instance inventory is invalid."
            )
        for instance in instances:
            if not isinstance(instance, dict):
                raise SlurmAccountingInspectionError(
                    "The accounting provider instance inventory is invalid."
                )
            instance_id = _bounded_text(
                instance.get("InstanceId"),
                field="accounting provider instance id",
            )
            instance_type = _bounded_text(
                instance.get("InstanceType"),
                field="accounting provider instance type",
            )
            if instance_id not in instance_ids or instance_id in resolved:
                raise SlurmAccountingInspectionError(
                    "The accounting provider instance inventory is ambiguous."
                )
            resolved[instance_id] = instance_type
    if set(resolved) != instance_ids:
        raise SlurmAccountingInspectionError(
            "The accounting provider instance inventory is incomplete."
        )
    return resolved


@dataclass(frozen=True)
class SlurmAccountingInspectionResult:
    """Bounded, non-secret read-only accounting identity evidence."""

    aws_profile: str
    aws_account_id: str
    region: str
    region_az: str
    expected_accounting_stack_name: str | None
    expected_privatelink_stack_name: str | None
    regional_providers: tuple[dict[str, Any], ...]
    exact_bridge: dict[str, Any] | None
    exact_bridge_resolved: bool | None
    exact_bridge_error_code: str | None

    def to_payload(self) -> dict[str, Any]:
        expected_provider = self.expected_accounting_stack_name
        regional_provider_matches_expected = (
            None
            if expected_provider is None
            else len(self.regional_providers) == 1
            and self.regional_providers[0]["stack_name"] == expected_provider
            and self.regional_providers[0]["contract_healthy"] is True
        )
        bridge_provider_matches_expected = (
            None
            if self.exact_bridge is None or expected_provider is None
            else self.exact_bridge["provider_accounting_stack_name"] == expected_provider
        )
        matching_providers = (
            []
            if self.exact_bridge is None
            else [
                provider
                for provider in self.regional_providers
                if provider["stack_name"] == self.exact_bridge["provider_accounting_stack_name"]
            ]
        )
        bridge_provider_binding_matches = (
            None
            if self.exact_bridge is None
            else len(matching_providers) == 1
            and matching_providers[0]["contract_healthy"] is True
            and matching_providers[0]["vpc_id"] == self.exact_bridge["provider_vpc_id"]
            and matching_providers[0]["database_name"] == self.exact_bridge["database_name"]
            and matching_providers[0]["db_username"] == self.exact_bridge["db_username"]
            and matching_providers[0]["instance_id"] == self.exact_bridge["accounting_instance_id"]
            and matching_providers[0]["instance_type"]
            == self.exact_bridge["accounting_instance_type"]
        )
        return {
            "schema_version": SLURM_ACCOUNTING_INSPECTION_SCHEMA,
            "ok": True,
            "read_only": True,
            "aws_profile": self.aws_profile,
            "aws_account_id": self.aws_account_id,
            "region": self.region,
            "region_az": self.region_az,
            "expected_accounting_stack_name": expected_provider,
            "expected_privatelink_stack_name": self.expected_privatelink_stack_name,
            "regional_provider_count": len(self.regional_providers),
            "regional_singleton": len(self.regional_providers) == 1,
            "regional_provider_matches_expected": regional_provider_matches_expected,
            "regional_providers": list(self.regional_providers),
            "exact_bridge": self.exact_bridge,
            "exact_bridge_resolved": self.exact_bridge_resolved,
            "exact_bridge_error_code": self.exact_bridge_error_code,
            "bridge_provider_matches_expected": bridge_provider_matches_expected,
            "bridge_provider_binding_matches_regional_provider": (bridge_provider_binding_matches),
        }


def inspect_slurm_accounting(
    *,
    profile: str,
    region_az: str,
    expected_accounting_stack_name: str = "",
    expected_privatelink_stack_name: str = "",
) -> SlurmAccountingInspectionResult:
    """Inspect exact provider/bridge identities without mutation or discovery fallback."""

    profile = _required_text(profile, field="profile")
    region_az = _required_text(region_az, field="region_az")
    expected_provider = _optional_text(
        expected_accounting_stack_name,
        field="stack_name",
    )
    expected_bridge_name = _optional_text(
        expected_privatelink_stack_name,
        field="privatelink_stack_name",
    )
    try:
        region, _az = parse_region_az(region_az)
    except ValueError:
        raise SlurmAccountingInspectionError("region_az is invalid.") from None
    try:
        aws_ctx = AWSContext.build_region(region, profile=profile)
        aws_account_id = _required_text(aws_ctx.account_id, field="aws_account_id")
        stacks = list_regional_slurm_accounting_stacks(aws_ctx, region_az=region_az)
    except SlurmAccountingInspectionError:
        raise
    except Exception:  # noqa: BLE001 - provider text is excluded from this public contract
        raise SlurmAccountingInspectionError(
            "The regional accounting provider inventory could not be inspected safely."
        ) from None
    if len(stacks) > MAX_REGIONAL_PROVIDERS:
        raise SlurmAccountingInspectionError(
            "The regional accounting provider inventory exceeds the bounded result limit."
        )
    provider_instance_ids: set[str] = set()
    for stack in stacks:
        instance_id = _outputs(stack).get("AccountingInstanceId", "")
        if instance_id:
            provider_instance_ids.add(instance_id)
    provider_instance_types = _exact_instance_types(aws_ctx, provider_instance_ids)
    providers = tuple(
        _provider_payload(stack, instance_types=provider_instance_types) for stack in stacks
    )

    exact_bridge: dict[str, Any] | None = None
    bridge_resolved: bool | None = None
    bridge_error_code: str | None = None
    if expected_bridge_name is not None:
        try:
            bridge = resolve_slurm_accounting_privatelink_bridge(
                aws_ctx,
                stack_name=expected_bridge_name,
                require_healthy_target=False,
            )
            if bridge.stack_name != expected_bridge_name:
                raise SlurmAccountingInspectionError(
                    "The exact bridge resolver returned a different stack identity."
                )
            bridge_instance_type = provider_instance_types.get(bridge.accounting_instance_id)
            if bridge_instance_type is None:
                bridge_instance_type = _exact_instance_types(
                    aws_ctx,
                    {bridge.accounting_instance_id},
                )[bridge.accounting_instance_id]
            exact_bridge = {
                "stack_name": _bounded_text(bridge.stack_name, field="bridge stack name"),
                "status": _bounded_text(bridge.status, field="bridge stack status"),
                "provider_accounting_stack_name": _bounded_text(
                    bridge.provider_accounting_stack_name,
                    field="bridge provider stack name",
                ),
                "provider_vpc_id": _bounded_text(
                    bridge.provider_vpc_id,
                    field="bridge provider VPC",
                ),
                "consumer_vpc_id": _bounded_text(
                    bridge.consumer_vpc_id,
                    field="bridge consumer VPC",
                ),
                "database_name": _bounded_text(
                    bridge.database_name,
                    field="bridge database name",
                ),
                "db_username": _bounded_text(
                    bridge.username,
                    field="bridge database user",
                ),
                "accounting_instance_id": _bounded_text(
                    bridge.accounting_instance_id,
                    field="bridge accounting instance id",
                ),
                "accounting_instance_type": _bounded_text(
                    bridge_instance_type,
                    field="bridge accounting instance type",
                ),
                "contract_healthy": False,
            }
            bridge_resolved = True
        except (SlurmAccountingPrivateLinkError, SlurmAccountingInspectionError):
            bridge_resolved = False
            bridge_error_code = "exact_bridge_unavailable_or_incompatible"
        if exact_bridge is not None:
            try:
                healthy_bridge = resolve_slurm_accounting_privatelink_bridge(
                    aws_ctx,
                    stack_name=expected_bridge_name,
                    require_healthy_target=True,
                )
                if healthy_bridge.stack_name != expected_bridge_name:
                    raise SlurmAccountingInspectionError(
                        "The healthy bridge resolver returned a different stack identity."
                    )
                exact_bridge["contract_healthy"] = True
            except (SlurmAccountingPrivateLinkError, SlurmAccountingInspectionError):
                bridge_error_code = "exact_bridge_target_unhealthy_or_unverified"

    return SlurmAccountingInspectionResult(
        aws_profile=profile,
        aws_account_id=aws_account_id,
        region=region,
        region_az=region_az,
        expected_accounting_stack_name=expected_provider,
        expected_privatelink_stack_name=expected_bridge_name,
        regional_providers=providers,
        exact_bridge=exact_bridge,
        exact_bridge_resolved=bridge_resolved,
        exact_bridge_error_code=bridge_error_code,
    )
