"""CLI entry point for daylily-ec, built on cli-core-yo.

Provides ``create``, ``preflight``, and ``drift`` commands for managing
ephemeral AWS ParallelCluster environments.

Usage::

    python -m daylily_ec --help
    python -m daylily_ec create --region-az us-west-2b --profile my-profile
    python -m daylily_ec preflight --region-az us-west-2b
    python -m daylily_ec drift --state-file ~/.config/daylily/state_prod_*.json
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
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
    from daylily_ec.workflow.create_cluster import run_create_workflow

    if debug:
        logging.basicConfig(level=logging.DEBUG)

    output.action(f"Creating cluster in {region_az} ...")
    rc = run_create_workflow(
        region_az,
        profile=profile,
        config_path=config,
        pass_on_warn=pass_on_warn,
        debug=debug,
        non_interactive=non_interactive,
    )
    raise typer.Exit(rc)


# ── preflight command ────────────────────────────────────────────────────────


@app.command()
def preflight(
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
        help="Path to daylily config YAML.",
    ),
    pass_on_warn: bool = typer.Option(
        False,
        "--pass-on-warn",
        help="Treat warnings as non-fatal.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug output.",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Disable interactive prompts.",
    ),
) -> None:
    """Run preflight validation only (no cluster creation).

    Exits 0 on success, 1 on validation failure.
    """
    from daylily_ec.workflow.create_cluster import run_preflight_only

    if debug:
        logging.basicConfig(level=logging.DEBUG)

    output.action(f"Running preflight for {region_az} ...")
    rc = run_preflight_only(
        region_az,
        profile=profile,
        config_path=config,
        pass_on_warn=pass_on_warn,
        debug=debug,
        non_interactive=non_interactive,
    )
    raise typer.Exit(rc)


# ── drift command ────────────────────────────────────────────────────────────


@app.command()
def drift(
    state_file: str = typer.Option(
        ...,
        "--state-file",
        help="Path to a state JSON file from a previous run.",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        help="AWS CLI profile.",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug output.",
    ),
) -> None:
    """Check for drift against a previous run's state.

    Exit codes: 0 = no drift, 3 = drift detected, 2 = error.
    """
    import json

    from daylily_ec.aws.context import AWSContext
    from daylily_ec.state.drift import run_drift_check
    from daylily_ec.state.models import StateRecord
    from daylily_ec.workflow.create_cluster import (
        EXIT_AWS_FAILURE,
        EXIT_DRIFT,
        EXIT_SUCCESS,
    )

    if debug:
        logging.basicConfig(level=logging.DEBUG)

    # Load state
    p = Path(state_file)
    if not p.is_file():
        output.error(f"State file not found: {state_file}")
        raise typer.Exit(EXIT_AWS_FAILURE)

    state = StateRecord.model_validate_json(p.read_text(encoding="utf-8"))
    output.action(f"Checking drift for cluster '{state.cluster_name}' ...")

    # Build AWS context
    region_az = state.region_az or f"{state.region}a"
    try:
        aws_ctx = AWSContext.build(region_az, profile=profile)
    except RuntimeError as exc:
        output.error(f"AWS context failed: {exc}")
        raise typer.Exit(EXIT_AWS_FAILURE) from exc

    report = run_drift_check(
        state,
        cfn_client=aws_ctx.client("cloudformation"),
        budgets_client=aws_ctx.client("budgets"),
        sns_client=aws_ctx.client("sns"),
        scheduler_client=aws_ctx.client("scheduler"),
        account_id=aws_ctx.account_id,
    )

    # Print report
    output.detail(json.dumps(report.__dict__, indent=2, default=str))

    if report.has_drift:
        output.warn("Drift detected.")
        raise typer.Exit(EXIT_DRIFT)

    output.success("No drift detected.")
    raise typer.Exit(EXIT_SUCCESS)


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

