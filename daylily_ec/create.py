"""Stable cluster-create helper for external callers."""

from __future__ import annotations

from typing import Optional

from daylily_ec.workflow.create_cluster import run_create_workflow


def create_cluster(
    *,
    region_az: str,
    profile: Optional[str] = None,
    config_path: Optional[str] = None,
    pass_on_warn: bool = False,
    debug: bool = False,
    non_interactive: bool = True,
) -> int:
    """Create a cluster using the supported daylily-ec workflow."""
    return run_create_workflow(
        region_az,
        profile=profile,
        config_path=config_path,
        pass_on_warn=pass_on_warn,
        debug=debug,
        non_interactive=non_interactive,
    )
