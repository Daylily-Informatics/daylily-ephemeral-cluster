"""Persistent storage for preflight reports and state records.

Writes JSON to ``~/.config/daylily/`` (XDG_CONFIG_HOME / daylily).

File naming::

    preflight_<cluster>_<run_id>.json

All JSON is serialised with **sorted keys** for deterministic, diff-friendly output.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from daylily_ec.state.models import PreflightReport

logger = logging.getLogger(__name__)

_APP_DIR = "daylily"


# ---------------------------------------------------------------------------
# Directory resolution
# ---------------------------------------------------------------------------


def config_dir() -> Path:
    """Return the XDG config directory for daylily.

    Uses ``XDG_CONFIG_HOME`` if set, otherwise ``~/.config``.
    Creates the directory if it does not exist.
    """
    base = os.environ.get("XDG_CONFIG_HOME", "")
    if not base:
        base = str(Path.home() / ".config")
    path = Path(base) / _APP_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------


def _safe_cluster_name(name: Optional[str]) -> str:
    """Sanitise cluster name for use in a filename."""
    if not name:
        return "unknown"
    # Replace anything that isn't alphanumeric, dash, or underscore
    return "".join(c if (c.isalnum() or c in "-_") else "_" for c in name)


def write_preflight_report(report: PreflightReport) -> Path:
    """Persist *report* as sorted-key JSON and return the written path.

    Path pattern: ``<config_dir>/preflight_<cluster>_<run_id>.json``
    """
    cluster = _safe_cluster_name(report.cluster_name)
    filename = f"preflight_{cluster}_{report.run_id}.json"
    dest = config_dir() / filename

    payload = json.dumps(
        report.model_dump(mode="json"),
        indent=2,
        sort_keys=True,
    )
    dest.write_text(payload + "\n", encoding="utf-8")
    logger.info("Preflight report written to %s", dest)
    return dest

