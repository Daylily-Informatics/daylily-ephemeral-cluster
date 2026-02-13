"""Cluster creation monitor — poll until CREATE_COMPLETE (CP-014).

Replaces the Bash loop (lines ~2495-2510) and the helper
``bin/helpers/watch_cluster_status.py`` with an importable function.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Cluster status indicating creation is still running.
STATUS_IN_PROGRESS: str = "CREATE_IN_PROGRESS"

#: Cluster status indicating creation completed successfully.
STATUS_COMPLETE: str = "CREATE_COMPLETE"

#: Maximum consecutive poll failures before aborting.
MAX_CONSECUTIVE_FAILURES: int = 5

#: Default seconds between status polls.
DEFAULT_POLL_INTERVAL: float = 30.0

# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class MonitorResult:
    """Outcome of :func:`wait_for_creation`."""

    final_status: Optional[str]
    elapsed_seconds: float
    success: bool
    consecutive_failures: int = 0
    error: str = ""
    head_node_ip: Optional[str] = None
    head_node_instance_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Status lookup
# ---------------------------------------------------------------------------


def get_cluster_status(
    cluster_name: str,
    region: str,
    *,
    profile: Optional[str] = None,
) -> Optional[str]:
    """Return the current ``clusterStatus`` for *cluster_name*.

    Returns ``None`` when the cluster cannot be described (deleted,
    permissions error, etc.).
    """
    cmd = [
        "pcluster",
        "describe-cluster",
        "-n", cluster_name,
        "--region", region,
        "--query", "clusterStatus",
    ]
    env: Dict[str, Any] = {**os.environ}
    if profile:
        env["AWS_PROFILE"] = profile

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    except FileNotFoundError:
        logger.error("pcluster CLI not found on PATH")
        return None

    if proc.returncode != 0:
        logger.warning(
            "describe-cluster failed (rc=%d): %s",
            proc.returncode,
            proc.stderr.strip() or proc.stdout.strip(),
        )
        return None

    try:
        return json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError):
        return proc.stdout.strip() or None


def get_cluster_details(
    cluster_name: str,
    region: str,
    *,
    profile: Optional[str] = None,
) -> Dict[str, Any]:
    """Return the full ``pcluster describe-cluster`` JSON for *cluster_name*.

    Returns an empty dict on any error.
    """
    cmd = [
        "pcluster",
        "describe-cluster",
        "-n", cluster_name,
        "--region", region,
    ]
    env: Dict[str, Any] = {**os.environ}
    if profile:
        env["AWS_PROFILE"] = profile

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    except FileNotFoundError:
        logger.error("pcluster CLI not found on PATH")
        return {}

    if proc.returncode != 0:
        logger.warning(
            "describe-cluster failed (rc=%d): %s",
            proc.returncode,
            proc.stderr.strip() or proc.stdout.strip(),
        )
        return {}

    try:
        return json.loads(proc.stdout)  # type: ignore[no-any-return]
    except (json.JSONDecodeError, TypeError):
        return {}


# ---------------------------------------------------------------------------
# Wait loop
# ---------------------------------------------------------------------------


def wait_for_creation(
    cluster_name: str,
    region: str,
    *,
    profile: Optional[str] = None,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    max_failures: int = MAX_CONSECUTIVE_FAILURES,
    _sleep_fn: Any = None,
) -> MonitorResult:
    """Block until cluster reaches ``CREATE_COMPLETE`` or a terminal state.

    Mirrors the Bash loop behaviour:

    * While status is ``CREATE_IN_PROGRESS`` keep polling.
    * On ``CREATE_COMPLETE`` → success.
    * On ``None`` (transient failure) increment consecutive-failure counter;
      abort after *max_failures* consecutive failures.
    * Any other status is treated as a terminal error.

    The *_sleep_fn* parameter is for test injection (avoids real sleeps).
    """
    sleep = _sleep_fn or time.sleep
    start = time.time()
    consecutive_failures = 0

    while True:
        status = get_cluster_status(cluster_name, region, profile=profile)

        if status == STATUS_COMPLETE:
            # Fetch head node details for the success banner.
            details = get_cluster_details(
                cluster_name, region, profile=profile,
            )
            head_node = details.get("headNode", {})
            return MonitorResult(
                final_status=STATUS_COMPLETE,
                elapsed_seconds=time.time() - start,
                success=True,
                head_node_ip=head_node.get("publicIpAddress"),
                head_node_instance_id=head_node.get("instanceId"),
            )

        if status == STATUS_IN_PROGRESS:
            consecutive_failures = 0
            logger.info(
                "Cluster %s still creating (%.0fs elapsed)",
                cluster_name,
                time.time() - start,
            )
            sleep(poll_interval)
            continue

        if status is None:
            consecutive_failures += 1
            if consecutive_failures >= max_failures:
                return MonitorResult(
                    final_status=None,
                    elapsed_seconds=time.time() - start,
                    success=False,
                    consecutive_failures=consecutive_failures,
                    error=(
                        f"Monitor failed {consecutive_failures} "
                        "consecutive times. Aborting."
                    ),
                )
            logger.warning(
                "Status poll returned None (%d/%d)",
                consecutive_failures,
                max_failures,
            )
            sleep(poll_interval)
            continue

        # Any other status is a terminal failure
        return MonitorResult(
            final_status=status,
            elapsed_seconds=time.time() - start,
            success=False,
            error=f"Cluster entered unexpected status: {status}",
        )

