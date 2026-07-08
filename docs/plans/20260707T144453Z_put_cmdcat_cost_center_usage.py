#!/usr/bin/env python3
"""Write the zero-spend validation usage snapshot for the DYEC 10.0.103 catalog cluster."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from decimal import Decimal

from daylily_ec.aws.context import AWSContext
from daylily_ec.aws.cost_centers import (
    DEFAULT_COST_CENTER_USAGE_TABLE,
    CostCenterUsage,
    put_cost_center_usage,
    validate_cost_center_name,
    validate_month,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="cmdcat-103-all-20260707")
    parser.add_argument("--month", default=_utc_now().strftime("%Y-%m"))
    parser.add_argument("--profile", default="lsmc")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--monthly-spend-usd", default="0")
    parser.add_argument("--usage-table-name", default=DEFAULT_COST_CENTER_USAGE_TABLE)
    args = parser.parse_args()

    now = _utc_now()
    latest_hour = now.replace(minute=0, second=0, microsecond=0)
    usage = CostCenterUsage(
        name=validate_cost_center_name(args.name),
        month=validate_month(args.month),
        monthly_spend_usd=Decimal(args.monthly_spend_usd),
        latest_processed_hour=_iso_z(latest_hour),
        updated_at=_iso_z(now),
    )
    aws_ctx = AWSContext.build_region(args.region, profile=args.profile)
    written = put_cost_center_usage(
        aws_ctx.client("dynamodb"),
        usage,
        usage_table_name=args.usage_table_name,
    )
    print(json.dumps(written.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
