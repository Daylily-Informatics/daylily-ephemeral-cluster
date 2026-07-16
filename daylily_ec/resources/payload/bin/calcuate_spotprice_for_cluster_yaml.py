#!/usr/bin/env python
"""Thin CLI wrapper around ``daylily_ec.aws.spot_pricing``.

This script uses the DYEC capped spot bid policy::

    python bin/calcuate_spotprice_for_cluster_yaml.py \\
        -i init_template.yaml -o final.yaml \\
        --az us-west-2a --profile myprofile

All core logic now lives in ``daylily_ec.aws.spot_pricing`` (CP-012).
"""

from __future__ import annotations

import argparse
import os
import sys

# ---------------------------------------------------------------------------
# Imports from the new library module
# ---------------------------------------------------------------------------
from daylily_ec.aws.spot_pricing import (  # noqa: E402
    DEFAULT_GLOBAL_SPOT_MAX_COST,
    DEFAULT_SPOT_COST_LIMIT_PCT,
    DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD,
    MAX_SPOT_COST_LIMIT_PCT,
    MIN_SPOT_COST_LIMIT_PCT,
    apply_spot_prices,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Insert SpotPrice into pcluster_config.yaml using "
            "DYEC capped median spot bid strategy."
        ),
    )
    parser.add_argument("-i", "--input", required=True, help="Input YAML file.")
    parser.add_argument(
        "--global-spot-max-cost",
        type=float,
        default=DEFAULT_GLOBAL_SPOT_MAX_COST,
        help=(
            "Global maximum PCluster SpotPrice bid "
            f"(default {DEFAULT_GLOBAL_SPOT_MAX_COST:.2f})."
        ),
    )
    parser.add_argument(
        "--spot-cost-limit-pct",
        type=float,
        default=DEFAULT_SPOT_COST_LIMIT_PCT,
        help=(
            "Multiplier applied to the reference median spot price "
            f"(default {DEFAULT_SPOT_COST_LIMIT_PCT:.2f}; hard limit "
            f"{MIN_SPOT_COST_LIMIT_PCT:.1f} <= value <= {MAX_SPOT_COST_LIMIT_PCT:.1f})."
        ),
    )
    parser.add_argument(
        "--write-spot-pricing-warn-threshold",
        type=float,
        default=DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD,
        help=(
            "Observed runtime spot price threshold for warning rows "
            f"(default {DEFAULT_WRITE_SPOT_PRICING_WARN_THRESHOLD:.2f})."
        ),
    )
    parser.add_argument("-o", "--output", required=True, help="Output YAML file.")
    parser.add_argument("--az", required=True, help="Availability zone.")
    parser.add_argument(
        "--profile",
        help="AWS CLI profile (defaults to AWS_PROFILE env var).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    profile = args.profile or os.environ.get("AWS_PROFILE")
    if not profile:
        print(
            "Error: AWS_PROFILE is not set. "
            "Please export AWS_PROFILE or supply --profile.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        apply_spot_prices(
            input_path=args.input,
            output_path=args.output,
            az=args.az,
            profile=profile,
            global_spot_max_cost=float(args.global_spot_max_cost),
            spot_cost_limit_pct=float(args.spot_cost_limit_pct),
            write_spot_pricing_warn_threshold=float(
                args.write_spot_pricing_warn_threshold
            ),
        )
    except (RuntimeError, ValueError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Updated configuration saved to {args.output}.")


if __name__ == "__main__":
    main()
