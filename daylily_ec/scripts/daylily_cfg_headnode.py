"""Configure a Daylily headnode from the operator machine without a PEM."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, wait_for_ssm_online
from daylily_ec.scripts.common import CommandError, need_cmd, resolve_cluster, resolve_region
from daylily_ec.workflow.create_cluster import configure_headnode


def _load_repo_overrides(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    override_path = Path(path)
    if not override_path.is_file():
        raise CommandError(f"Repository overrides file not found: {override_path}")
    overrides: dict[str, str] = {}
    for raw_line in override_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        repo_key, git_ref = line.split(":", 1)
        overrides[repo_key.strip()] = git_ref.strip()
    return overrides


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Configure a ParallelCluster head node via SSM.",
    )
    parser.add_argument("--region", required=False, help="AWS region")
    parser.add_argument(
        "--profile",
        default=os.environ.get("AWS_PROFILE"),
        help="AWS CLI profile (default: $AWS_PROFILE)",
    )
    parser.add_argument("--cluster", help="Cluster name (prompted if omitted)")
    parser.add_argument(
        "--repo-overrides",
        help="File containing repo overrides (format: repo-key:git-ref per line)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.profile:
        raise CommandError("AWS profile is required. Set AWS_PROFILE or use --profile.")

    need_cmd("aws")
    need_cmd("pcluster")

    region = resolve_region(args.profile, args.region)
    cluster_name = resolve_cluster(args.profile, region, args.cluster)
    overrides = _load_repo_overrides(args.repo_overrides)
    target = resolve_headnode_instance_id(cluster_name, region, profile=args.profile)
    wait_for_ssm_online(target.instance_id, region, profile=args.profile, timeout=120)

    ok = configure_headnode(
        cluster_name=cluster_name,
        head_node_instance_id=target.instance_id,
        region=region,
        profile=args.profile,
        repo_overrides=overrides or None,
    )
    if not ok:
        raise CommandError(f"Headnode configuration failed for cluster '{cluster_name}'.")
    print(f"Headnode configured via SSM for cluster '{cluster_name}'.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except CommandError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
