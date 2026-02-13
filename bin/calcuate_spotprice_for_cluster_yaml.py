#!/usr/bin/env python
"""Thin CLI wrapper around ``daylily_ec.aws.spot_pricing``.

This script preserves full backward compatibility with the original
command-line interface::

    python bin/calcuate_spotprice_for_cluster_yaml.py \\
        -i init_template.yaml -o final.yaml \\
        --az us-west-2a --profile myprofile -b 4.14

All core logic now lives in ``daylily_ec.aws.spot_pricing`` (CP-012).
"""

from __future__ import annotations

import argparse
import os
import sys

# ---------------------------------------------------------------------------
# Bootstrap: ensure DAY-EC conda env is active (legacy helper)
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "helpers"))
from ensure_dayec import ensure_dayec  # noqa: E402

ensure_dayec(quiet=True)

# ---------------------------------------------------------------------------
# Imports from the new library module
# ---------------------------------------------------------------------------
from daylily_ec.aws.spot_pricing import (  # noqa: E402
    DEFAULT_BUMP_PRICE,
    apply_spot_prices,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Insert SpotPrice into pcluster_config.yaml using "
            "median(spot) + BUMP_PRICE strategy."
        ),
    )
    parser.add_argument("-i", "--input", required=True, help="Input YAML file.")
    parser.add_argument(
        "-b",
        "--bump-price",
        type=float,
        default=DEFAULT_BUMP_PRICE,
        help=f"Price bump added to median spot price (default {DEFAULT_BUMP_PRICE}).",
    )
    parser.add_argument("-o", "--output", required=True, help="Output YAML file.")
    parser.add_argument("--az", required=True, help="Availability zone.")
    parser.add_argument(
        "--profile",
        help="AWS CLI profile (defaults to AWS_PROFILE env var).",
    )
    # Legacy flag kept for backward compat; library always uses spot via boto3.
    parser.add_argument(
        "--avg-price-of",
        choices=["spot", "dedicated"],
        default="spot",
        help="(legacy) Type of price to calculate.",
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
            bump_price=float(args.bump_price),
        )
    except RuntimeError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Updated configuration saved to {args.output}.")


if __name__ == "__main__":
    main()
