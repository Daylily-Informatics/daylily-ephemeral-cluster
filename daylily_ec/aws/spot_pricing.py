"""Spot-price heuristics for ParallelCluster compute resources.

Replaces the core logic of ``bin/calcuate_spotprice_for_cluster_yaml.py``
as an importable library module (CP-012, Option A).

The standalone script continues to work by importing from here.
"""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

# ── constants ────────────────────────────────────────────────────────

#: Default bump price added to median spot price (matches Bash invocation).
DEFAULT_BUMP_PRICE: float = 4.14

#: Fallback spot price when the API returns an unparseable result.
FALLBACK_SPOT_PRICE: float = 5.55


# ── low-level price lookup ───────────────────────────────────────────


def get_spot_price(
    ec2_client: Any,
    instance_type: str,
    az: str,
) -> float:
    """Return the current spot price for *instance_type* in *az*.

    Uses ``describe_spot_price_history`` via boto3.  Falls back to
    :data:`FALLBACK_SPOT_PRICE` when the API returns no data or a
    non-numeric result (matching the Bash script behaviour).

    Raises
    ------
    RuntimeError
        If the API call itself fails (permissions, network, etc.).
    """
    try:
        resp = ec2_client.describe_spot_price_history(
            InstanceTypes=[instance_type],
            AvailabilityZone=az,
            ProductDescriptions=["Linux/UNIX"],
            MaxResults=1,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Spot price lookup failed for {instance_type} in {az}. "
            f"Confirm instance type is valid and you have ec2:DescribeSpotPriceHistory permission. "
            f"Detail: {exc}"
        ) from exc

    prices = resp.get("SpotPriceHistory", [])
    if not prices:
        return FALLBACK_SPOT_PRICE

    try:
        return float(prices[0]["SpotPrice"])
    except (KeyError, ValueError, TypeError):
        return FALLBACK_SPOT_PRICE


# ── queue-level calculation ──────────────────────────────────────────


def calculate_queue_spot_price(
    ec2_client: Any,
    queue_config: Dict[str, Any],
    az: str,
    bump_price: float = DEFAULT_BUMP_PRICE,
) -> Optional[float]:
    """Return the bumped median spot price for all instances in a queue.

    Iterates over every ``ComputeResources[].Instances[].InstanceType``,
    looks up the current spot price, then returns
    ``round(median + bump_price, 4)``.

    Returns ``None`` if no prices could be collected.
    """
    all_prices: List[float] = []
    for resource in queue_config.get("ComputeResources", []):
        for inst in resource.get("Instances", []):
            itype = inst.get("InstanceType")
            if itype:
                price = get_spot_price(ec2_client, itype, az)
                all_prices.append(price)

    if not all_prices:
        return None

    return round(statistics.median(all_prices) + bump_price, 4)


def apply_spot_to_queue(
    ec2_client: Any,
    queue_config: Dict[str, Any],
    az: str,
    bump_price: float = DEFAULT_BUMP_PRICE,
) -> None:
    """Set ``SpotPrice`` on every ComputeResource in *queue_config* (in-place).

    Adds a YAML end-of-line comment when the config is a
    :class:`~ruamel.yaml.comments.CommentedMap`.
    """
    spot = calculate_queue_spot_price(ec2_client, queue_config, az, bump_price)
    if spot is None:
        return

    for resource in queue_config.get("ComputeResources", []):
        resource["SpotPrice"] = spot
        if isinstance(resource, CommentedMap):
            resource.yaml_add_eol_comment(
                "Calculated using (median spot price).",
                key="SpotPrice",
                column=0,
            )


def process_slurm_queues(
    config: Dict[str, Any],
    az: str,
    ec2_client: Any,
    bump_price: float = DEFAULT_BUMP_PRICE,
) -> None:
    """Process **all** Slurm queues in *config* to add SpotPrice values (in-place)."""
    for queue in config.get("Scheduling", {}).get("SlurmQueues", []):
        if not isinstance(queue, CommentedMap):
            queue = CommentedMap(queue)
        apply_spot_to_queue(ec2_client, queue, az, bump_price)


# ── top-level convenience ────────────────────────────────────────────


def apply_spot_prices(
    input_path: str,
    output_path: str,
    az: str,
    *,
    ec2_client: Any = None,
    profile: Optional[str] = None,
    bump_price: float = DEFAULT_BUMP_PRICE,
) -> None:
    """Read init-template YAML, set SpotPrice, write final cluster YAML.

    Either *ec2_client* (boto3 EC2 client) **or** *profile* must be
    provided.  When *ec2_client* is ``None``, a new client is created
    from *profile*.
    """
    if ec2_client is None:
        import boto3

        session_kw: Dict[str, str] = {}
        if profile:
            session_kw["profile_name"] = profile
        region = az[:-1]
        session_kw["region_name"] = region
        ec2_client = boto3.Session(**session_kw).client("ec2")

    yaml = YAML()
    yaml.preserve_quotes = True
    config = yaml.load(Path(input_path))

    process_slurm_queues(config, az, ec2_client, bump_price)

    out_yaml = YAML()
    out_yaml.explicit_start = True
    out_yaml.explicit_end = True
    with open(output_path, "w", encoding="utf-8") as fh:
        out_yaml.dump(config, fh)

