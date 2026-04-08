"""S3 bucket discovery, selection, and reference-bundle verification.

Preserves exact Bash behaviour:

1. List all buckets via ``s3api list-buckets``.
2. Filter candidates whose name contains ``omics-analysis``.
3. Resolve each bucket's region via ``GetBucketLocation``
   (``LocationConstraint=None`` → ``us-east-1``).
4. Keep only buckets matching the target region.
5. Auto-select based on config triplet / single-match / config fallback.
6. Verify via direct boto3 checks against the expected reference-bucket layout.
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
from typing import Any, List, Optional

import boto3
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

REFERENCE_VERSION_KEY = "s3_reference_data_version.info"
DEFAULT_REFERENCE_VERSION = "0.7.131c"
CORE_REFERENCE_PREFIXES = (
    "cluster_boot_config/",
    "data/cached_envs/",
    "data/tool_specific_resources/",
    "data/budget_tags/",
)
HG38_REFERENCE_PREFIXES = (
    "data/genomic_data/organism_references/H_sapiens/hg38/",
    "data/genomic_data/organism_annotations/H_sapiens/hg38/",
)
GIAB_REFERENCE_PREFIXES = (
    "data/genomic_data/organism_reads/",
)
REQUIRED_REFERENCE_PREFIXES = (
    *CORE_REFERENCE_PREFIXES,
    *HG38_REFERENCE_PREFIXES,
    *GIAB_REFERENCE_PREFIXES,
)


def _reference_bucket_s3_client(*, profile: str = "", region: str = "") -> Any:
    session = boto3.session.Session(
        profile_name=profile or None,
        region_name=region or None,
    )
    return session.client("s3")


def _reference_bucket_exists(s3_client: Any, bucket_name: str) -> bool:
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except Exception:
        return False
    return True


def _read_reference_bucket_version(s3_client: Any, bucket_name: str) -> Optional[str]:
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=REFERENCE_VERSION_KEY)
    except Exception:
        return None

    body = response.get("Body")
    if body is None:
        return None

    return body.read().decode("utf-8").strip()


def _reference_prefix_exists(s3_client: Any, bucket_name: str, prefix: str) -> bool:
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix, MaxKeys=1)
    return "Contents" in response and bool(response["Contents"])


def verify_reference_bundle(
    bucket_name: str,
    *,
    profile: str = "",
    region: str = "",
) -> bool:
    """Verify the selected reference bucket and return success.

    Matches the previously delegated `daylily-omics-references verify
    --exclude-b37` contract by checking:

    - the bucket exists
    - the version marker matches :data:`DEFAULT_REFERENCE_VERSION`
    - all required non-b37 prefixes have at least one object
    """
    try:
        s3_client = _reference_bucket_s3_client(profile=profile, region=region)
        if not _reference_bucket_exists(s3_client, bucket_name):
            logger.error("Reference verification failed: bucket %s does not exist.", bucket_name)
            return False

        issues: List[str] = []

        bucket_version = _read_reference_bucket_version(s3_client, bucket_name)
        if bucket_version is None:
            issues.append("missing version marker")
        elif bucket_version != DEFAULT_REFERENCE_VERSION:
            issues.append(
                "version mismatch "
                f"(expected {DEFAULT_REFERENCE_VERSION}, found {bucket_version})"
            )

        for prefix in REQUIRED_REFERENCE_PREFIXES:
            if not _reference_prefix_exists(s3_client, bucket_name, prefix):
                issues.append(f"missing objects under {prefix}")

        if issues:
            logger.error(
                "Reference verification failed for %s: %s",
                bucket_name,
                "; ".join(issues),
            )
            return False

        return True
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
                        f"Reference bundle verification failed for bucket '{selected}'. "
                        "Confirm the bucket contains "
                        f"{REFERENCE_VERSION_KEY}={DEFAULT_REFERENCE_VERSION} and the "
                        "expected Daylily reference prefixes."
                    ),
                )
            )

        return report

    return step
