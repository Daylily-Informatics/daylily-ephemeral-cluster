"""Current AWS Price List estimate for a zero-compute DYEC cluster."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


HOURS_PER_MONTH = Decimal("730")


class IdleCostPricingError(RuntimeError):
    """Raised when an authoritative idle-cost price cannot be resolved."""


@dataclass(frozen=True)
class IdleClusterCostEstimate:
    """Hourly prices for resources that remain active with no compute nodes."""

    headnode_instance_type: str
    headnode_hourly_usd: Decimal
    root_volume_type: str
    root_volume_gib: int
    root_volume_hourly_usd: Decimal
    fsx_deployment_type: str
    fsx_capacity_gib: int
    fsx_throughput_mbps_per_tib: str
    fsx_hourly_usd: Decimal
    public_ipv4_hourly_usd: Decimal

    @property
    def total_hourly_usd(self) -> Decimal:
        return (
            self.headnode_hourly_usd
            + self.root_volume_hourly_usd
            + self.fsx_hourly_usd
            + self.public_ipv4_hourly_usd
        )


def estimate_idle_cluster_cost(
    pricing_client: Any,
    *,
    region: str,
    headnode_instance_type: str,
    root_volume_type: str,
    root_volume_gib: int,
    fsx_deployment_type: str,
    fsx_capacity_gib: int,
    fsx_throughput_mbps_per_tib: str = "",
) -> IdleClusterCostEstimate:
    """Resolve the current configured idle cost from AWS Price List products.

    The idle boundary includes the on-demand headnode, its root EBS volume,
    the dedicated FSx for Lustre filesystem, and one in-use public IPv4 address.
    Slurm compute nodes are excluded because their configured minimum is zero.
    """
    normalized_region = region.strip()
    normalized_instance = headnode_instance_type.strip()
    normalized_volume_type = root_volume_type.strip().lower()
    normalized_deployment = fsx_deployment_type.strip().upper()
    normalized_throughput = fsx_throughput_mbps_per_tib.strip()

    if not normalized_region:
        raise IdleCostPricingError("AWS region is required for idle-cost pricing.")
    if not normalized_instance:
        raise IdleCostPricingError("Headnode instance type is required for idle-cost pricing.")
    if normalized_volume_type != "gp3":
        raise IdleCostPricingError(
            "Idle-cost pricing supports the rendered gp3 headnode root volume; "
            f"received {root_volume_type!r}."
        )
    if root_volume_gib <= 0:
        raise IdleCostPricingError("Headnode root volume size must be positive.")
    if fsx_capacity_gib <= 0:
        raise IdleCostPricingError("FSx capacity must be positive.")
    if normalized_deployment not in {"SCRATCH_2", "PERSISTENT_2"}:
        raise IdleCostPricingError(
            "Idle-cost pricing requires SCRATCH_2 or PERSISTENT_2; "
            f"received {fsx_deployment_type!r}."
        )
    if normalized_deployment == "PERSISTENT_2" and not normalized_throughput:
        raise IdleCostPricingError(
            "PERSISTENT_2 idle-cost pricing requires the throughput tier."
        )

    headnode_hourly = _get_single_price(
        pricing_client,
        service_code="AmazonEC2",
        filters={
            "regionCode": normalized_region,
            "instanceType": normalized_instance,
            "operatingSystem": "Linux",
            "tenancy": "Shared",
            "preInstalledSw": "NA",
            "capacitystatus": "Used",
        },
        unit="Hrs",
        label=f"Linux on-demand {normalized_instance}",
    )
    root_storage_monthly = _get_single_price(
        pricing_client,
        service_code="AmazonEC2",
        filters={
            "regionCode": normalized_region,
            "volumeApiName": normalized_volume_type,
            "productFamily": "Storage",
        },
        unit="GB-Mo",
        label=f"EBS {normalized_volume_type} storage",
    )

    fsx_filters = {
        "regionCode": normalized_region,
        "fileSystemType": "Lustre",
        "storageType": "SSD",
        "throughputCapacity": (
            normalized_throughput if normalized_deployment == "PERSISTENT_2" else "N/A"
        ),
    }
    fsx_storage_monthly = _get_single_price(
        pricing_client,
        service_code="AmazonFSx",
        filters=fsx_filters,
        unit="GB-Mo",
        label=(
            f"FSx for Lustre {normalized_deployment} "
            + (
                f"{normalized_throughput} MB/s/TiB storage"
                if normalized_deployment == "PERSISTENT_2"
                else "storage"
            )
        ),
    )
    public_ipv4_hourly = _get_single_price(
        pricing_client,
        service_code="AmazonVPC",
        filters={
            "regionCode": normalized_region,
            "group": "VPCPublicIPv4Address",
            "groupDescription": "Hourly charge for In-use Public IPv4 Addresses",
        },
        unit="Hrs",
        label="in-use public IPv4 address",
    )

    return IdleClusterCostEstimate(
        headnode_instance_type=normalized_instance,
        headnode_hourly_usd=headnode_hourly,
        root_volume_type=normalized_volume_type,
        root_volume_gib=root_volume_gib,
        root_volume_hourly_usd=(
            root_storage_monthly * Decimal(root_volume_gib) / HOURS_PER_MONTH
        ),
        fsx_deployment_type=normalized_deployment,
        fsx_capacity_gib=fsx_capacity_gib,
        fsx_throughput_mbps_per_tib=normalized_throughput,
        fsx_hourly_usd=(
            fsx_storage_monthly * Decimal(fsx_capacity_gib) / HOURS_PER_MONTH
        ),
        public_ipv4_hourly_usd=public_ipv4_hourly,
    )


def _get_single_price(
    pricing_client: Any,
    *,
    service_code: str,
    filters: dict[str, str],
    unit: str,
    label: str,
) -> Decimal:
    api_filters = [
        {"Type": "TERM_MATCH", "Field": field, "Value": value}
        for field, value in filters.items()
    ]
    price_list: list[str] = []
    next_token = ""
    try:
        while True:
            kwargs: dict[str, Any] = {
                "ServiceCode": service_code,
                "Filters": api_filters,
                "FormatVersion": "aws_v1",
                "MaxResults": 100,
            }
            if next_token:
                kwargs["NextToken"] = next_token
            response = pricing_client.get_products(**kwargs)
            price_list.extend(response.get("PriceList") or [])
            next_token = str(response.get("NextToken") or "")
            if not next_token:
                break
    except Exception as exc:
        raise IdleCostPricingError(
            f"AWS Price List lookup failed for {label}: {exc}"
        ) from exc

    rates: set[Decimal] = set()
    try:
        for raw_product in price_list:
            product = json.loads(raw_product)
            for term in (product.get("terms") or {}).get("OnDemand", {}).values():
                for dimension in (term.get("priceDimensions") or {}).values():
                    if dimension.get("unit") != unit:
                        continue
                    raw_rate = (dimension.get("pricePerUnit") or {}).get("USD")
                    if raw_rate is None:
                        continue
                    rates.add(Decimal(str(raw_rate)))
    except (InvalidOperation, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise IdleCostPricingError(
            f"AWS Price List returned malformed pricing for {label}: {exc}"
        ) from exc

    if len(rates) != 1:
        rendered_rates = ", ".join(str(rate) for rate in sorted(rates)) or "none"
        raise IdleCostPricingError(
            f"AWS Price List must return exactly one {unit} rate for {label}; "
            f"received {len(rates)} rates ({rendered_rates})."
        )
    return next(iter(rates))
