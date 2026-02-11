"""CLI entry point for daylily-ec, built on cli-core-yo.

Provides the ``create`` command (and future subcommands) for managing
ephemeral AWS ParallelCluster environments.  All flags from the legacy
Bash script are preserved here, even those not yet implemented.

Usage::

    python -m daylily_ec --help
    python -m daylily_ec create --region-az us-west-2b --profile my-profile
"""

from __future__ import annotations

import os
import sys
from typing import List, Optional

import typer
from cli_core_yo import output
from cli_core_yo.app import create_app
from cli_core_yo.runtime import _reset, initialize
from cli_core_yo.spec import CliSpec, XdgSpec

# ── App specification ────────────────────────────────────────────────────────

spec = CliSpec(
    prog_name="daylily-ec",
    app_display_name="Daylily Ephemeral Cluster",
    dist_name="daylily-ephemeral-cluster",
    root_help=(
        "Create and manage ephemeral AWS ParallelCluster environments "
        "for bioinformatics workloads."
    ),
    xdg=XdgSpec(app_dir_name="daylily"),
)

app = create_app(spec)


# ── Root callback (global options) ───────────────────────────────────────────


@app.callback()
def _root_callback(
    json_flag: bool = typer.Option(
        False, "--json", "-j", help="Output as JSON."
    ),
) -> None:
    """Daylily Ephemeral Cluster control plane."""
    _reset()
    debug = os.environ.get("CLI_CORE_YO_DEBUG") == "1"
    xdg_paths = app._cli_core_yo_xdg_paths  # type: ignore[attr-defined]
    initialize(spec, xdg_paths, json_mode=json_flag, debug=debug)


# ── create command ───────────────────────────────────────────────────────────


@app.command()
def create(
    region_az: str = typer.Option(
        ...,
        "--region-az",
        help="AWS region + availability zone (e.g. us-west-2b).",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile. Defaults to AWS_PROFILE env var.",
    ),
    config: Optional[str] = typer.Option(
        None,
        "--config",
        help=(
            "Path to daylily config YAML. "
            "Default: config/daylily_ephemeral_cluster_template.yaml"
        ),
    ),
    pass_on_warn: bool = typer.Option(
        False,
        "--pass-on-warn",
        help="Continue on preflight warnings instead of failing.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug output (print commands as executed).",
    ),
    repo_override: Optional[List[str]] = typer.Option(
        None,
        "--repo-override",
        help=(
            "Override default_ref for a repository: <repo-key>:<git-ref>. "
            "Can be specified multiple times."
        ),
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Disable interactive prompts; use config defaults or fail.",
    ),
) -> None:
    """Create an ephemeral AWS ParallelCluster environment.

    This is the primary workflow command, replacing
    bin/daylily-create-ephemeral-cluster.

    Environment variables:
      DAY_CONTACT_EMAIL          Used for notification/budget email fields.
      DAY_DISABLE_AUTO_SELECT    Set to 1 to always prompt for config values.
      DAY_BREAK                  Set to 1 to exit after dry-run validation.
      AWS_PROFILE                Default AWS profile when --profile is omitted.
    """
    # CP-001 skeleton — prints inputs and exits cleanly.
    # Real implementation lands in CP-003 (workflow orchestrator).
    effective_profile = profile or os.environ.get("AWS_PROFILE", "(unset)")

    output.action("daylily-ec create: not yet implemented (CP-001 skeleton)")
    output.detail(f"region-az:       {region_az}")
    output.detail(f"profile:         {effective_profile}")
    output.detail(f"config:          {config or '(default)'}")
    output.detail(f"pass-on-warn:    {pass_on_warn}")
    output.detail(f"debug:           {debug}")
    output.detail(f"repo-override:   {repo_override or '(none)'}")
    output.detail(f"non-interactive: {non_interactive}")
    raise typer.Exit(0)


# ── Entry point ──────────────────────────────────────────────────────────────


def main() -> int:
    """Run the CLI and return an exit code."""
    try:
        app()
        return 0
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0


if __name__ == "__main__":
    sys.exit(main())

