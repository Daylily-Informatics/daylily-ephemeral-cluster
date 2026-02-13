"""ParallelCluster CLI wrapper — dry-run + real create (CP-013).

Wraps ``pcluster create-cluster`` as a subprocess so the Python control
plane never reimplements pcluster internals.  Behaviour mirrors the
Bash monolith lines ~2466-2493.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Exact message pcluster returns on dry-run success.
DRY_RUN_SUCCESS_MESSAGE: str = (
    "Request would have succeeded, but DryRun flag is set."
)

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class PclusterResult:
    """Parsed outcome of a ``pcluster`` CLI invocation."""

    command: str
    returncode: int
    stdout: str = ""
    stderr: str = ""
    json_body: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    success: bool = False


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _run_pcluster(
    args: list[str],
    *,
    profile: Optional[str] = None,
    extra_env: Optional[Dict[str, str]] = None,
) -> PclusterResult:
    """Run ``pcluster`` with *args* and return a :class:`PclusterResult`.

    *profile* is injected as ``AWS_PROFILE`` in the subprocess env.
    """
    cmd = ["pcluster", *args]
    env = {**os.environ}
    if profile:
        env["AWS_PROFILE"] = profile
    if extra_env:
        env.update(extra_env)

    logger.info("Running: %s", " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
        )
    except FileNotFoundError:
        return PclusterResult(
            command=" ".join(cmd),
            returncode=4,
            stderr="pcluster CLI not found on PATH",
        )

    result = PclusterResult(
        command=" ".join(cmd),
        returncode=proc.returncode,
        stdout=proc.stdout.strip(),
        stderr=proc.stderr.strip(),
    )

    # Attempt to parse stdout as JSON
    try:
        result.json_body = json.loads(result.stdout) if result.stdout else {}
    except json.JSONDecodeError:
        result.json_body = {}

    result.message = result.json_body.get("message", "")
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def dry_run_create(
    cluster_name: str,
    config_path: str,
    region: str,
    *,
    profile: Optional[str] = None,
) -> PclusterResult:
    """Execute ``pcluster create-cluster --dryrun true`` and evaluate success.

    Returns a :class:`PclusterResult` with ``success=True`` only when
    the response message exactly matches :data:`DRY_RUN_SUCCESS_MESSAGE`.
    """
    result = _run_pcluster(
        [
            "create-cluster",
            "-n", cluster_name,
            "-c", config_path,
            "--dryrun", "true",
            "--region", region,
        ],
        profile=profile,
    )
    result.success = result.message == DRY_RUN_SUCCESS_MESSAGE

    if result.success:
        logger.info("Dry-run succeeded for cluster %s", cluster_name)
    else:
        logger.warning(
            "Dry-run failed for cluster %s: %s",
            cluster_name,
            result.message or result.stderr or "(no message)",
        )

    return result


def should_break_after_dry_run() -> bool:
    """Return *True* when ``DAY_BREAK=1`` is set in the environment."""
    return os.environ.get("DAY_BREAK", "") == "1"


def create_cluster(
    cluster_name: str,
    config_path: str,
    region: str,
    *,
    profile: Optional[str] = None,
) -> PclusterResult:
    """Execute the real ``pcluster create-cluster`` invocation.

    Returns a :class:`PclusterResult` with ``success=True`` when the
    process exits 0.
    """
    result = _run_pcluster(
        [
            "create-cluster",
            "-n", cluster_name,
            "-c", config_path,
            "--region", region,
        ],
        profile=profile,
    )
    result.success = result.returncode == 0

    if result.success:
        logger.info("Cluster creation initiated: %s", cluster_name)
    else:
        logger.error(
            "Cluster creation failed (rc=%d): %s | stdout: %s",
            result.returncode,
            result.stderr or "(no stderr)",
            result.stdout or result.message or "(no output)",
        )

    return result

