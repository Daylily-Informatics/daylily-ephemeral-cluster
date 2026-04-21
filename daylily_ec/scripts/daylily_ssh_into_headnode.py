"""Connect to a Daylily headnode via AWS Systems Manager Session Manager."""

from __future__ import annotations

import argparse
import os
import sys

from daylily_ec.aws.ssm import (
    SsmError,
    resolve_headnode_instance_id,
    start_session,
    wait_for_ssm_online,
)
from daylily_ec.scripts.common import CommandError, need_cmd, resolve_cluster, resolve_region


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Open an ubuntu login shell on a Daylily headnode via Session Manager.",
    )
    parser.add_argument(
        "--profile",
        default=os.environ.get("AWS_PROFILE"),
        help="AWS CLI profile to use (default: $AWS_PROFILE)",
    )
    parser.add_argument("--region", help="AWS region (skip interactive selection)")
    parser.add_argument("--cluster", help="ParallelCluster name (skip interactive selection)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the Session Manager command that would be used and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.profile:
        raise CommandError("AWS profile is required. Set AWS_PROFILE or use --profile.")

    need_cmd("aws")
    need_cmd("pcluster")

    region = resolve_region(args.profile, args.region)
    cluster = resolve_cluster(args.profile, region, args.cluster)
    target = resolve_headnode_instance_id(cluster, region, profile=args.profile)
    wait_for_ssm_online(target.instance_id, region, profile=args.profile, timeout=120)

    connect_cmd = (
        "aws ssm start-session "
        f"--region {region} "
        f"--target {target.instance_id} "
        "--document-name SSM-SessionManagerRunShell"
    )
    print(
        f"Opening Session Manager session as ubuntu to {target.instance_id} "
        f"(cluster={cluster} region={region} profile={args.profile})"
    )
    print(f"Session Manager command: {connect_cmd}")
    if args.dry_run:
        return 0
    try:
        return start_session(target.instance_id, region, profile=args.profile)
    except SsmError as exc:
        raise CommandError(str(exc)) from exc


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except CommandError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
