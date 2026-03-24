"""S3 bucket discovery, selection, and reference-bundle verification.

Preserves exact Bash behaviour:

1. List all buckets via ``s3api list-buckets``.
2. Filter candidates whose name contains ``omics-analysis``.
3. Resolve each bucket's region via ``GetBucketLocation``
   (``LocationConstraint=None`` → ``us-east-1``).
4. Keep only buckets matching the target region.
5. Auto-select based on config triplet / single-match / config fallback.
6. Verify via ``daylily-omics-references.sh verify --bucket <b> --exclude-b37``.
7. Hard-gate: FAIL if verification fails — never allow pcluster create.

Public API
----------
- :func:`list_candidate_buckets` — steps 1-4
- :func:`select_bucket` — step 5
- :func:`verify_reference_bundle` — step 6
- :func:`make_s3_bucket_preflight_step` — factory returning a :data:`PreflightStep`
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Any, List, Optional

import typer

from daylily_ec.config.triplets import is_auto_select_disabled, should_auto_apply
from daylily_ec.state.models import CheckResult, CheckStatus, PreflightReport

logger = logging.getLogger(__name__)

BUCKET_NAME_FILTER = "omics-analysis"


# ---------------------------------------------------------------------------
# Bucket discovery helpers
# ---------------------------------------------------------------------------


def _resolve_bucket_region(s3_client: Any, bucket_name: str) -> Optional[str]:
    """Return the region for *bucket_name*, or ``None`` on error.

    ``LocationConstraint`` of ``None`` means ``us-east-1`` (AWS convention).
    """
    try:
        resp = s3_client.get_bucket_location(Bucket=bucket_name)
        loc = resp.get("LocationConstraint")
        return "us-east-1" if loc is None else str(loc)
    except Exception:
        logger.debug("Could not resolve region for bucket %s", bucket_name)
        return None


def list_candidate_buckets(
    aws_ctx: Any,
    *,
    target_region: Optional[str] = None,
) -> List[str]:
    """Return bucket names matching ``omics-analysis`` in *target_region*.

    If *target_region* is ``None``, falls back to ``aws_ctx.region``.
    """
    region = target_region or aws_ctx.region
    s3 = aws_ctx.client("s3")

    try:
        resp = s3.list_buckets()
        all_buckets = [b["Name"] for b in resp.get("Buckets", [])]
    except Exception as exc:
        logger.error("Failed to list S3 buckets: %s", exc)
        return []

    candidates: List[str] = []
    for name in all_buckets:
        if BUCKET_NAME_FILTER not in name:
            continue
        bucket_region = _resolve_bucket_region(s3, name)
        if bucket_region == region:
            candidates.append(name)

    return sorted(candidates)


# ---------------------------------------------------------------------------
# Bucket selection (config triplet + auto-select logic)
# ---------------------------------------------------------------------------


def select_bucket(
    candidates: List[str],
    *,
    cfg_action: str = "",
    cfg_set_value: str = "",
    cfg_bucket_name: str = "",
) -> Optional[str]:
    """Choose a bucket from *candidates* using Bash-parity selection logic.

    Precedence (exact Bash parity):

    1. Config set_value if :func:`should_auto_apply` is True **and** value
       is in *candidates*.
    2. Single candidate auto-select (unless ``DAY_DISABLE_AUTO_SELECT=1``).
    3. ``cfg_bucket_name`` fallback if it is in *candidates*.
    4. ``None`` — caller should prompt interactively.
    """
    # 1. Triplet set_value auto-apply
    if should_auto_apply(cfg_action, cfg_set_value):
        if cfg_set_value in candidates:
            return cfg_set_value

    # 2. Single candidate auto-select
    if len(candidates) == 1:
        if not is_auto_select_disabled():
            return candidates[0]

    # 3. CONFIG_S3_BUCKET_NAME fallback
    if cfg_bucket_name and cfg_bucket_name in candidates:
        return cfg_bucket_name

    # 4. Needs interactive prompt (not handled here)
    return None


# ---------------------------------------------------------------------------
# Reference bundle verification
# ---------------------------------------------------------------------------

VERIFY_CMD = "daylily-omics-references"

VERIFY_CMDS = (
    "daylily-omics-references",
    "daylily-omics-references.sh",
)


def verify_reference_bundle(
    bucket_name: str,
    *,
    profile: str = "",
    region: str = "",
) -> bool:
    """Run ``daylily-omics-references verify`` and return success.

    Matches Bash::

        daylily-omics-references.sh --profile "$AWS_PROFILE" --region "$region" \\
            verify --bucket "$selected_bucket" --exclude-b37
    """
    verify_cmd = next((c for c in VERIFY_CMDS if shutil.which(c)), "")
    if not verify_cmd:
        logger.error(
            "daylily-omics-references CLI not found on PATH. Install with: "
            'pip install "daylily-omics-references==0.3.3"',
        )
        return False

    cmd: List[str] = [verify_cmd]
    if profile:
        cmd.extend(["--profile", profile])
    if region:
        cmd.extend(["--region", region])
    cmd.extend(["verify", "--bucket", bucket_name, "--exclude-b37"])

    logger.info("Verifying reference bundle: %s", " ".join(cmd))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            return True
        logger.error(
            "Reference verification failed (exit %d): %s",
            result.returncode,
            result.stderr.strip() or result.stdout.strip(),
        )
        return False
    except subprocess.TimeoutExpired:
        logger.error("Reference verification timed out after 300s")
        return False
    except Exception as exc:
        logger.error("Reference verification error: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def bucket_url(bucket_name: str) -> str:
    """Return ``s3://<bucket_name>`` (parity with Bash ``bucket_url``)."""
    return f"s3://{bucket_name}"


def _prompt_for_bucket(candidates: List[str]) -> Optional[str]:
    """Prompt the user to choose one S3 bucket from *candidates*."""
    if not candidates:
        return None

    typer.echo("Select an S3 reference bucket:")
    for idx, candidate in enumerate(candidates, start=1):
        typer.echo(f"  [{idx}] {candidate}")

    while True:
        choice = typer.prompt("Enter selection number", default="1").strip()
        if not choice.isdigit():
            typer.echo("Invalid selection. Enter a number.")
            continue
        index = int(choice)
        if 1 <= index <= len(candidates):
            return candidates[index - 1]
        typer.echo("Invalid selection. Enter one of the listed numbers.")


# ---------------------------------------------------------------------------
# Preflight step factory
# ---------------------------------------------------------------------------


def make_s3_bucket_preflight_step(
    aws_ctx: Any,
    *,
    cfg_action: str = "",
    cfg_set_value: str = "",
    cfg_bucket_name: str = "",
    profile: str = "",
    interactive: bool = False,
) -> Any:
    """Return a :data:`PreflightStep` that discovers, selects, and verifies.

    The step appends two :class:`CheckResult` entries to the report:

    - ``s3.bucket_select`` — candidate discovery + selection result
    - ``s3.bucket_verify`` — reference bundle verification result

    Hard gate: if verification fails, status is FAIL and workflow must abort.
    """
    def step(report: PreflightReport) -> PreflightReport:
        region = report.region or aws_ctx.region

        # -- Discovery -------------------------------------------------------
        candidates = list_candidate_buckets(aws_ctx, target_region=region)

        if not candidates:
            report.checks.append(
                CheckResult(
                    id="s3.bucket_select",
                    status=CheckStatus.FAIL,
                    details={"region": region, "candidates": []},
                    remediation=(
                        f"No S3 buckets matching '{BUCKET_NAME_FILTER}' "
                        f"found in region {region}."
                    ),
                )
            )
            return report

        # -- Selection -------------------------------------------------------
        selected = select_bucket(
            candidates,
            cfg_action=cfg_action,
            cfg_set_value=cfg_set_value,
            cfg_bucket_name=cfg_bucket_name,
        )

        if selected is None:
            if interactive:
                selected = _prompt_for_bucket(candidates)

        if selected is None:
            # Cannot auto-select — needs interactive prompt
            # In non-interactive preflight, this is a FAIL
            report.checks.append(
                CheckResult(
                    id="s3.bucket_select",
                    status=CheckStatus.FAIL,
                    details={
                        "region": region,
                        "candidates": candidates,
                    },
                    remediation=(
                        "Multiple S3 buckets found and none could be "
                        "auto-selected. Set s3_bucket_name in config."
                    ),
                )
            )
            return report

        report.checks.append(
            CheckResult(
                id="s3.bucket_select",
                status=CheckStatus.PASS,
                details={
                    "region": region,
                    "candidates": candidates,
                    "selected": selected,
                    "bucket_url": bucket_url(selected),
                },
            )
        )

        # -- Verification (hard gate) ---------------------------------------
        ok = verify_reference_bundle(
            selected, profile=profile, region=region,
        )

        if ok:
            report.checks.append(
                CheckResult(
                    id="s3.bucket_verify",
                    status=CheckStatus.PASS,
                    details={"bucket": selected, "verified": True},
                )
            )
        else:
            report.checks.append(
                CheckResult(
                    id="s3.bucket_verify",
                    status=CheckStatus.FAIL,
                    details={"bucket": selected, "verified": False},
                    remediation=(
                        f"Reference bundle verification failed for "
                        f"bucket '{selected}'. Run: {VERIFY_CMD} "
                        f"verify --bucket {selected} --exclude-b37"
                    ),
                )
            )

        return report

    return step
