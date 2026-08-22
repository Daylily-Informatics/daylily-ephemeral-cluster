"""Persistent storage for preflight reports and state records (CP-004/CP-016).

Writes JSON to ``~/.config/daylily/`` (XDG_CONFIG_HOME / daylily).

File naming::

    preflight_<cluster>_<run_id>.json
    state_<cluster>_<run_id>.json

All JSON is serialised with **sorted keys** for deterministic, diff-friendly output.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from daylily_ec.state.models import PreflightReport, SlurmAccountingReceipt, StateRecord

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


def write_state_record(record: StateRecord) -> Path:
    """Persist *record* as sorted-key JSON and return the written path.

    Path pattern: ``<config_dir>/state_<cluster>_<run_id>.json``
    """
    cluster = _safe_cluster_name(record.cluster_name)
    filename = f"state_{cluster}_{record.run_id}.json"
    dest = config_dir() / filename

    payload = json.dumps(
        record.model_dump(mode="json"),
        indent=2,
        sort_keys=True,
    )
    dest.write_text(payload + "\n", encoding="utf-8")
    logger.info("State record written to %s", dest)
    return dest


def write_resource_receipt(
    *,
    cluster_name: str,
    run_id: str,
    resource_type: str,
    payload: dict,
) -> Path:
    """Persist a pre-cluster AWS resource receipt before pcluster submission."""

    cluster = _safe_cluster_name(cluster_name)
    safe_resource_type = _safe_cluster_name(resource_type)
    filename = f"resource_{safe_resource_type}_{cluster}_{run_id}.json"
    dest = config_dir() / filename
    dest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    logger.info("Resource receipt written to %s", dest)
    return dest


def write_slurm_accounting_receipt(
    receipt: SlurmAccountingReceipt,
    *,
    cluster_name: str,
    run_id: str,
    destination: Path | None = None,
) -> Path:
    """Persist a non-secret post-create Slurm accounting receipt.

    The strict :class:`SlurmAccountingReceipt` schema is the redaction
    boundary: callers cannot add connection endpoints, private addresses,
    secrets, credentials, or arbitrary exception text to this artifact.
    """

    explicit_destination = destination is not None
    if destination is None:
        cluster = _safe_cluster_name(cluster_name)
        filename = f"slurm_accounting_{cluster}_{run_id}_receipt.json"
        dest = config_dir() / filename
    else:
        dest = destination.expanduser()
        if not dest.is_absolute():
            raise ValueError("Explicit Slurm accounting receipt destination must be absolute")
        dest = dest.resolve()
        if dest.exists():
            raise FileExistsError(
                f"Explicit Slurm accounting receipt destination already exists: {dest}"
            )
        if not dest.parent.is_dir():
            raise ValueError(
                "Explicit Slurm accounting receipt parent must already be a directory"
            )
    payload = json.dumps(receipt.model_dump(mode="json"), indent=2, sort_keys=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{dest.name}.",
        suffix=".tmp",
        dir=str(dest.parent),
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        if explicit_destination:
            os.link(temporary, dest)
        else:
            os.replace(temporary, dest)
    finally:
        temporary.unlink(missing_ok=True)
    logger.info("Slurm accounting receipt written to %s", dest)
    return dest


def load_state_record(path: Path) -> StateRecord:
    """Load a :class:`StateRecord` from a JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return StateRecord(**data)


def load_slurm_accounting_receipt(path: Path) -> SlurmAccountingReceipt:
    """Load and validate a non-secret Slurm accounting receipt."""

    return SlurmAccountingReceipt.model_validate_json(path.read_text(encoding="utf-8"))
