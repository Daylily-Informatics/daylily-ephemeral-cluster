"""Launch the legacy remote test workflow on the headnode via SSM."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

from daylily_ec.aws.ssm import (
    resolve_headnode_instance_id,
    run_shell,
    wait_for_ssm_online,
)
from daylily_ec.resources import resource_path
from daylily_ec.scripts.common import CommandError, need_cmd, resolve_cluster, resolve_region


def _load_default_repo() -> tuple[str, str]:
    cfg_path = resource_path("config/daylily_available_repositories.yaml")
    cfg = yaml.safe_load(Path(cfg_path).read_text(encoding="utf-8")) or {}
    repo_key = cfg.get("default_repository") or "daylily-omics-analysis"
    repo = (cfg.get("repositories") or {}).get(repo_key) or {}
    return str(repo.get("https_url") or ""), str(repo.get("default_ref") or "main")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Launch the legacy remote test workflow on the headnode via SSM.",
    )
    parser.add_argument("--region", help="AWS region")
    parser.add_argument(
        "--profile",
        default=os.environ.get("AWS_PROFILE"),
        help="AWS CLI profile (default: $AWS_PROFILE)",
    )
    parser.add_argument("--cluster", help="Cluster name (prompted if omitted)")
    parser.add_argument("--yes", action="store_true", help="Launch the workflow without prompting")
    parser.add_argument("--no-launch", action="store_true", help="Skip the workflow launch")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.profile:
        raise CommandError("AWS profile is required. Set AWS_PROFILE or use --profile.")
    if args.yes and args.no_launch:
        raise CommandError("Choose at most one of --yes or --no-launch.")

    need_cmd("aws")
    need_cmd("pcluster")

    region = resolve_region(args.profile, args.region)
    cluster_name = resolve_cluster(args.profile, region, args.cluster)
    target = resolve_headnode_instance_id(cluster_name, region, profile=args.profile)
    wait_for_ssm_online(target.instance_id, region, profile=args.profile, timeout=120)

    if args.no_launch:
        print(
            "Access the headnode with: daylily-ssh-into-headnode "
            f"--profile {args.profile} --region {region} --cluster {cluster_name}"
        )
        return 0

    repo_url, repo_tag = _load_default_repo()
    session_name = "cluster_test_$(date +%s)"
    launch_script = f"""
set -euo pipefail
mkdir -p /fsx/analysis_results/ubuntu/daylily_remote_test
cd /fsx/analysis_results/ubuntu/daylily_remote_test
if [[ ! -d daylily-omics-analysis/.git ]]; then
  git clone -b {repo_tag} {repo_url} daylily-omics-analysis
fi
session_name={session_name}
tmux new-session -d -s "$session_name" \
  "bash -lc 'source ~/.bashrc && source ~/projects/daylily-ephemeral-cluster/activate && eval \"$(daylily-ec headnode init --emit-shell --non-interactive)\" && cd /fsx/analysis_results/ubuntu/daylily_remote_test/daylily-omics-analysis && source bin/day_activate slurm hg38 remote && DAY_CONTAINERIZED=true ./bin/day_run produce_snv_concordances -p -k -j 2 --config aligners=[\\\"strobe\\\",\\\"bwa2a\\\"] dedupers=[\\\"dppl\\\"] genome_build=\\\"hg38\\\" snv_callers=[\\\"deep\\\"]; bash'"
echo "__DAYLILY_SESSION__=$session_name"
"""

    result = run_shell(
        target.instance_id,
        region,
        launch_script,
        profile=args.profile,
        timeout=180,
        comment="Launch legacy remote test workflow",
    )
    session_line = next(
        (line for line in (result.stdout or "").splitlines() if line.startswith("__DAYLILY_SESSION__=")),
        "",
    )
    if not session_line:
        raise CommandError("Remote workflow launch did not report a tmux session name.")
    session_name = session_line.split("=", 1)[1].strip()
    print(f"Tmux session '{session_name}' created on the head node.")
    print(
        "Reconnect with: daylily-ssh-into-headnode "
        f"--profile {args.profile} --region {region} --cluster {cluster_name}"
    )
    print(f"Then run: tmux attach -t {session_name}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except CommandError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
