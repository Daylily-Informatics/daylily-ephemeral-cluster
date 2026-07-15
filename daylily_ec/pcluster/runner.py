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
DRY_RUN_SUCCESS_MESSAGE: str = "Request would have succeeded, but DryRun flag is set."

#: Defensive pagination bound for ``pcluster list-clusters``.
MAX_LIST_CLUSTER_PAGES: int = 1000

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
    executable: str = "pcluster",
) -> PclusterResult:
    """Run ``pcluster`` with *args* and return a :class:`PclusterResult`.

    *profile* is injected as ``AWS_PROFILE`` in the subprocess env.
    """
    cmd = [executable, *args]
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
        parsed_body = json.loads(result.stdout) if result.stdout else {}
    except json.JSONDecodeError:
        parsed_body = {}

    result.json_body = parsed_body if isinstance(parsed_body, dict) else {}

    result.message = result.json_body.get("message", "")
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_clusters(
    region: str,
    *,
    profile: Optional[str] = None,
    executable: str = "pcluster",
) -> PclusterResult:
    """Return a validated, paginated regional ParallelCluster inventory.

    The returned JSON body contains only ``clusterName`` and ``clusterStatus``
    for each record. Any command failure, malformed JSON, malformed record, or
    invalid pagination token fails closed with ``success=False``.
    """

    clusters: list[Dict[str, str]] = []
    next_token: Optional[str] = None
    seen_tokens: set[str] = set()
    base_command = f"{executable} list-clusters --region {region}"

    for _page_number in range(1, MAX_LIST_CLUSTER_PAGES + 1):
        args = ["list-clusters", "--region", region]
        if next_token is not None:
            args.extend(["--next-token", next_token])

        page = _run_pcluster(
            args,
            profile=profile,
            executable=executable,
        )
        if page.returncode != 0:
            page.success = False
            page.message = (
                "pcluster list-clusters failed with exit code "
                f"{page.returncode}"
            )
            page.json_body = {}
            return page

        try:
            payload = json.loads(page.stdout)
        except json.JSONDecodeError:
            page.success = False
            page.message = "pcluster list-clusters returned malformed JSON"
            page.json_body = {}
            return page

        if not isinstance(payload, dict):
            page.success = False
            page.message = "pcluster list-clusters response must be a JSON object"
            page.json_body = {}
            return page

        records = payload.get("clusters")
        if not isinstance(records, list):
            page.success = False
            page.message = "pcluster list-clusters response must contain a clusters list"
            page.json_body = {}
            return page

        for index, record in enumerate(records):
            if not isinstance(record, dict):
                page.success = False
                page.message = f"pcluster list-clusters clusters[{index}] must be an object"
                page.json_body = {}
                return page

            name = record.get("clusterName")
            status = record.get("clusterStatus")
            if not isinstance(name, str) or not name.strip():
                page.success = False
                page.message = (
                    f"pcluster list-clusters clusters[{index}].clusterName "
                    "must be a non-empty string"
                )
                page.json_body = {}
                return page
            if not isinstance(status, str) or not status.strip():
                page.success = False
                page.message = (
                    f"pcluster list-clusters clusters[{index}].clusterStatus "
                    "must be a non-empty string"
                )
                page.json_body = {}
                return page

            clusters.append(
                {
                    "clusterName": name,
                    "clusterStatus": status,
                }
            )

        raw_next_token = payload.get("nextToken")
        if raw_next_token is None:
            body = {"clusters": clusters}
            return PclusterResult(
                command=base_command,
                returncode=0,
                stdout=json.dumps(body),
                json_body=body,
                success=True,
            )
        if not isinstance(raw_next_token, str) or not raw_next_token:
            page.success = False
            page.message = "pcluster list-clusters nextToken must be a non-empty string"
            page.json_body = {}
            return page
        if raw_next_token in seen_tokens:
            page.success = False
            page.message = "pcluster list-clusters returned a repeated nextToken"
            page.json_body = {}
            return page

        seen_tokens.add(raw_next_token)
        next_token = raw_next_token

    return PclusterResult(
        command=base_command,
        returncode=4,
        message=(
            "pcluster list-clusters exceeded the pagination safety limit of "
            f"{MAX_LIST_CLUSTER_PAGES} pages"
        ),
    )


def dry_run_create(
    cluster_name: str,
    config_path: str,
    region: str,
    *,
    profile: Optional[str] = None,
    executable: str = "pcluster",
) -> PclusterResult:
    """Execute ``pcluster create-cluster --dryrun true`` and evaluate success.

    Returns a :class:`PclusterResult` with ``success=True`` only when
    the response message exactly matches :data:`DRY_RUN_SUCCESS_MESSAGE`.
    """
    result = _run_pcluster(
        [
            "create-cluster",
            "-n",
            cluster_name,
            "-c",
            config_path,
            "--dryrun",
            "true",
            "--region",
            region,
        ],
        profile=profile,
        executable=executable,
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
    executable: str = "pcluster",
) -> PclusterResult:
    """Execute the real ``pcluster create-cluster`` invocation.

    Returns a :class:`PclusterResult` with ``success=True`` when the
    process exits 0.
    """
    result = _run_pcluster(
        [
            "create-cluster",
            "-n",
            cluster_name,
            "-c",
            config_path,
            "--region",
            region,
        ],
        profile=profile,
        executable=executable,
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


def describe_cluster(
    cluster_name: str,
    region: str,
    *,
    profile: Optional[str] = None,
    executable: str = "pcluster",
) -> PclusterResult:
    """Return the current ParallelCluster description for *cluster_name*."""
    result = _run_pcluster(
        ["describe-cluster", "-n", cluster_name, "--region", region],
        profile=profile,
        executable=executable,
    )
    result.success = result.returncode == 0 and bool(result.json_body)
    return result


def describe_compute_fleet(
    cluster_name: str,
    region: str,
    *,
    profile: Optional[str] = None,
    executable: str = "pcluster",
) -> PclusterResult:
    """Return the current ParallelCluster compute-fleet description."""
    result = _run_pcluster(
        ["describe-compute-fleet", "-n", cluster_name, "--region", region],
        profile=profile,
        executable=executable,
    )
    result.success = result.returncode == 0 and bool(result.json_body)
    return result


def update_cluster(
    cluster_name: str,
    config_path: str,
    region: str,
    *,
    profile: Optional[str] = None,
    dry_run: bool = False,
    executable: str = "pcluster",
) -> PclusterResult:
    """Validate or submit a supported ``pcluster update-cluster`` operation."""
    result = _run_pcluster(
        [
            "update-cluster",
            "-n",
            cluster_name,
            "-c",
            config_path,
            "--dryrun",
            "true" if dry_run else "false",
            "--region",
            region,
        ],
        profile=profile,
        executable=executable,
    )
    if dry_run:
        result.success = result.message == DRY_RUN_SUCCESS_MESSAGE
    else:
        result.success = result.returncode == 0
    return result


def delete_cluster(
    cluster_name: str,
    region: str,
    *,
    profile: Optional[str] = None,
    executable: str = "pcluster",
) -> PclusterResult:
    """Execute ``pcluster delete-cluster`` for *cluster_name*."""
    result = _run_pcluster(
        [
            "delete-cluster",
            "-n",
            cluster_name,
            "--region",
            region,
        ],
        profile=profile,
        executable=executable,
    )
    result.success = result.returncode == 0

    if result.success:
        logger.info("Cluster deletion initiated: %s", cluster_name)
    else:
        logger.error(
            "Cluster deletion failed to start (rc=%d): %s | stdout: %s",
            result.returncode,
            result.stderr or "(no stderr)",
            result.stdout or result.message or "(no output)",
        )

    return result
