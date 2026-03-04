#!/usr/bin/env python3
"""Estimate AWS spot costs for a Daylily workflow across zones.

This is a lightweight CLI wrapper around `daylib.day_cost_ec2`.
It intentionally keeps AWS interactions external (AWS CLI via subprocess).
"""

from __future__ import annotations

import argparse
import os
import re
import sys

from daylily_ec.resources import resource_path
from daylib.day_cost_ec2 import (  # type: ignore
    ConfigLoader,
    SpotPriceFetcher,
    ZoneStat,
    calculate_vcpu_mins,
    display_statistics,
    extract_instances,
)


def _parse_n_vcpus(partition: str) -> int:
    m = re.search(r"(\\d+)$", partition)
    if m:
        return int(m.group(1))
    return 192


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--config",
        default=str(resource_path("config/day_cluster/prod_cluster.yaml")),
        help="Path to cluster YAML (default: packaged prod_cluster.yaml).",
    )
    p.add_argument(
        "--profile",
        default=os.environ.get("AWS_PROFILE", ""),
        help="AWS CLI profile to use (default: AWS_PROFILE).",
    )
    p.add_argument(
        "--partition",
        default="i192",
        help="Slurm queue/partition name (default: %(default)s).",
    )
    p.add_argument(
        "--zones",
        default="us-west-2a,us-west-2b,us-west-2c",
        help="Comma-separated availability zones to evaluate.",
    )
    p.add_argument(
        "--cost-model",
        choices=["min", "max", "median", "harmonic"],
        default="harmonic",
        help="Spot price aggregation model (default: %(default)s).",
    )

    # Workflow vCPU-minute model (defaults match legacy assumptions).
    p.add_argument("--x-coverage", type=float, default=30.0)
    p.add_argument("--align", type=float, default=307.2)
    p.add_argument("--snvcall", type=float, default=684.0)
    p.add_argument("--svcall", type=float, default=19.0)
    p.add_argument("--other", type=float, default=0.021)

    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))

    cfg = ConfigLoader.load_config(args.config)
    instance_types = extract_instances(cfg, args.partition)
    zones = [z.strip() for z in args.zones.split(",") if z.strip()]

    if not zones:
        print("Error: --zones must contain at least one zone.", file=sys.stderr)
        return 2

    n_vcpus = _parse_n_vcpus(args.partition)
    vcpu_mins = calculate_vcpu_mins(
        args.x_coverage, args.align, args.snvcall, args.svcall, args.other
    )

    spot_data = SpotPriceFetcher.collect_spot_prices(instance_types, zones, args.profile)

    zone_stats: list[ZoneStat] = []
    for zone in zones:
        z = ZoneStat(zone)
        z.calculate_statistics(spot_data, n_vcpus, vcpu_mins, args.cost_model)
        zone_stats.append(z)

    display_statistics(zone_stats, n_vcpus, args.cost_model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

