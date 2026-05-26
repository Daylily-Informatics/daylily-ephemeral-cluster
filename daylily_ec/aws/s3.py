"""S3 role validation for Daylily cluster storage contracts.

The cluster create path requires explicit S3 role inputs. It does not discover
or auto-select S3 storage because the DayOA storage split has separate contracts
for references, control read data, and mutable staging. Runtime assets are part
of the reference contract under ``runtime_assets/`` and are mounted through the
single reference DRA.

Public API
----------
- :func:`normalize_role_s3_uri` — normalize storage role S3 URI values
- :func:`verify_s3_roles` — verify role S3 URIs directly with boto3
- :func:`make_s3_bucket_preflight_step` — factory returning a :data:`PreflightStep`
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import boto3
from botocore.config import Config

from daylily_ec.state.models import CheckResult, CheckStatus, PreflightReport

logger = logging.getLogger(__name__)

BUCKET_NAME_FILTER = "omics-analysis"

ROLE_REFERENCE = "reference"
ROLE_CONTROL_DATA = "control_data"
ROLE_STAGING = "staging"
REQUIRED_S3_ROLES = (
    ROLE_REFERENCE,
    ROLE_CONTROL_DATA,
    ROLE_STAGING,
)


@dataclasses.dataclass(frozen=True)
class S3RoleSpec:
    """Normalized S3 role binding."""

    role: str
    uri: str
    bucket: str
    prefix: str


def _standard_s3_config() -> Config:
    """Return an S3 client config suitable for bucket metadata reads."""
    return Config(s3={"use_accelerate_endpoint": False})


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
    except Exception as exc:
        logger.debug("Could not resolve region for bucket %s: %s", bucket_name, exc)
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
    s3 = aws_ctx.client("s3", config=_standard_s3_config())

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
# Reference bundle verification
# ---------------------------------------------------------------------------

REFERENCE_VERSION_KEY = "s3_reference_data_version.info"
DEFAULT_REFERENCE_VERSION = "0.7.131c"
ROLE_REQUIRED_PREFIXES: Dict[str, Tuple[str, ...]] = {
    ROLE_REFERENCE: (
        "genomic_data/organism_references/H_sapiens/hg38/",
        "genomic_data/organism_annotations/H_sapiens/hg38/",
        "runtime_assets/cluster_boot_config/",
        "runtime_assets/cached_envs/",
        "runtime_assets/tool_specific_resources/",
        "runtime_assets/budget_tags/",
    ),
    ROLE_CONTROL_DATA: (
        "genomic_data/organism_reads/",
    ),
    ROLE_STAGING: (),
}


def _reference_role_s3_client(*, profile: str = "", region: str = "") -> Any:
    session = boto3.session.Session(
        profile_name=profile or None,
        region_name=region or None,
    )
    return session.client("s3", config=_standard_s3_config())


def normalize_role_s3_uri(value: str, *, role: str) -> S3RoleSpec:
    """Normalize a required S3 role input.

    Accepts either ``s3://bucket[/prefix]`` or explicit ``bucket[/prefix]``.
    Empty values, non-S3 schemes, query strings, fragments, and bucketless
    values fail hard.
    """
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{role} S3 URI is required.")
    if "://" not in raw:
        raw = f"s3://{raw}"
    parsed = urlparse(raw)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"{role} must be an S3 bucket or s3:// URI, got {value!r}.")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError(f"{role} S3 URI must not include params, query, or fragment.")
    prefix = parsed.path.lstrip("/").rstrip("/")
    uri = f"s3://{parsed.netloc}/{prefix}/" if prefix else f"s3://{parsed.netloc}/"
    return S3RoleSpec(role=role, uri=uri, bucket=parsed.netloc, prefix=prefix)


def bucket_name_from_role_value(value: str, *, role: str) -> str:
    """Return only the bucket name from an explicit role value."""
    return normalize_role_s3_uri(value, role=role).bucket


def role_prefix_key(spec: S3RoleSpec, relative_key: str) -> str:
    """Return a key relative to the role prefix."""
    cleaned = relative_key.lstrip("/")
    if spec.prefix:
        return f"{spec.prefix.rstrip('/')}/{cleaned}"
    return cleaned


def _normalize_role_map(role_values: Dict[str, str]) -> Dict[str, S3RoleSpec]:
    missing = [role for role in REQUIRED_S3_ROLES if not str(role_values.get(role, "")).strip()]
    if missing:
        raise ValueError(f"Missing required S3 role value(s): {', '.join(sorted(missing))}")
    specs = {
        role: normalize_role_s3_uri(role_values[role], role=role)
        for role in REQUIRED_S3_ROLES
    }
    _validate_role_s3_prefixes_do_not_overlap(specs)
    return specs


def _s3_prefixes_overlap(left: S3RoleSpec, right: S3RoleSpec) -> bool:
    if left.bucket != right.bucket:
        return False
    first = (left.prefix.rstrip("/") + "/") if left.prefix else ""
    second = (right.prefix.rstrip("/") + "/") if right.prefix else ""
    return first == second or first.startswith(second) or second.startswith(first)


def _validate_role_s3_prefixes_do_not_overlap(specs: Dict[str, S3RoleSpec]) -> None:
    roles = sorted(specs)
    for idx, left_role in enumerate(roles):
        for right_role in roles[idx + 1 :]:
            left = specs[left_role]
            right = specs[right_role]
            if _s3_prefixes_overlap(left, right):
                raise ValueError(
                    "S3 role prefixes must not overlap: "
                    f"{left.role}={left.uri} and {right.role}={right.uri}"
                )


def _reference_role_bucket_exists(s3_client: Any, bucket_name: str) -> bool:
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except Exception:
        return False
    return True


def _read_reference_role_version(s3_client: Any, bucket_name: str) -> Optional[str]:
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


def verify_s3_roles(
    role_values: Dict[str, str],
    *,
    profile: str = "",
    region: str = "",
) -> Tuple[bool, Dict[str, Any]]:
    """Verify explicit DayOA role S3 URIs and required prefixes.

    Returns ``(ok, details)``. Details always include normalized role URIs and
    an ``issues`` list suitable for a preflight remediation message.
    """
    try:
        specs = _normalize_role_map(role_values)
    except ValueError as exc:
        return False, {"roles": {}, "issues": [str(exc)]}

    s3_client = _reference_role_s3_client(profile=profile, region=region)
    issues: List[str] = []
    details: Dict[str, Any] = {
        "roles": {
            role: {"uri": spec.uri, "bucket": spec.bucket, "prefix": spec.prefix}
            for role, spec in specs.items()
        },
        "buckets": sorted({spec.bucket for spec in specs.values()}),
        "issues": issues,
    }

    for role, spec in specs.items():
        if not _reference_role_bucket_exists(s3_client, spec.bucket):
            issues.append(f"{role}: bucket does not exist or is not accessible: {spec.bucket}")
            continue

        if role == ROLE_REFERENCE:
            version_key = role_prefix_key(spec, REFERENCE_VERSION_KEY)
            bucket_version = _read_reference_role_version_for_key(
                s3_client,
                spec.bucket,
                version_key,
            )
            if bucket_version is None:
                issues.append(f"{role}: missing version marker {version_key}")
            elif bucket_version != DEFAULT_REFERENCE_VERSION:
                issues.append(
                    f"{role}: version mismatch at {version_key} "
                    f"(expected {DEFAULT_REFERENCE_VERSION}, found {bucket_version})"
                )

        for prefix in ROLE_REQUIRED_PREFIXES.get(role, ()):
            key_prefix = role_prefix_key(spec, prefix)
            if not _reference_prefix_exists(s3_client, spec.bucket, key_prefix):
                issues.append(f"{role}: missing objects under {key_prefix}")

    return not issues, details


def _read_reference_role_version_for_key(
    s3_client: Any,
    bucket_name: str,
    key: str,
) -> Optional[str]:
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
    except Exception:
        return None

    body = response.get("Body")
    if body is None:
        return None

    return body.read().decode("utf-8").strip()


def verify_reference_bundle(
    bucket_name: str,
    *,
    profile: str = "",
    region: str = "",
) -> bool:
    """Verify the selected reference storage bucket and return success.

    Matches the previously delegated `daylily-omics-references verify
    --exclude-b37` contract by checking:

    - the bucket exists
    - the version marker matches :data:`DEFAULT_REFERENCE_VERSION`
    - all required non-b37 prefixes have at least one object
    """
    try:
        s3_client = _reference_role_s3_client(profile=profile, region=region)
        if not _reference_role_bucket_exists(s3_client, bucket_name):
            logger.error("Reference verification failed: bucket %s does not exist.", bucket_name)
            return False

        issues: List[str] = []

        bucket_version = _read_reference_role_version(s3_client, bucket_name)
        if bucket_version is None:
            issues.append("missing version marker")
        elif bucket_version != DEFAULT_REFERENCE_VERSION:
            issues.append(
                "version mismatch "
                f"(expected {DEFAULT_REFERENCE_VERSION}, found {bucket_version})"
            )

        legacy_prefixes = (
            "genomic_data/organism_references/H_sapiens/hg38/",
            "genomic_data/organism_annotations/H_sapiens/hg38/",
            "runtime_assets/cluster_boot_config/",
            "runtime_assets/cached_envs/",
            "runtime_assets/tool_specific_resources/",
            "runtime_assets/budget_tags/",
        )
        for prefix in legacy_prefixes:
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


def bucket_url(bucket_name: str) -> str:
    """Return ``s3://<bucket_name>``."""
    return f"s3://{bucket_name}"


# ---------------------------------------------------------------------------
# Preflight step factory
# ---------------------------------------------------------------------------


def make_s3_bucket_preflight_step(
    aws_ctx: Any,
    *,
    reference_s3_uri: str = "",
    control_data_s3_uri: str = "",
    stage_s3_uri: str = "",
    profile: str = "",
    interactive: bool = False,
) -> Any:
    """Return a :data:`PreflightStep` that verifies explicit S3 role bindings.

    The step appends two :class:`CheckResult` entries to the report:

    - ``s3.role_config`` — explicit role parsing and overlap validation
    - ``s3.role_verify`` — live bucket/prefix verification result

    Hard gate: if any role is absent, malformed, overlapping, inaccessible, or
    missing required prefixes, status is FAIL and workflow must abort.
    """
    del interactive  # explicit role config is required; there is no bucket prompt.

    def step(report: PreflightReport) -> PreflightReport:
        region = report.region or aws_ctx.region
        role_values = {
            ROLE_REFERENCE: reference_s3_uri,
            ROLE_CONTROL_DATA: control_data_s3_uri,
            ROLE_STAGING: stage_s3_uri,
        }
        ok, details = verify_s3_roles(role_values, profile=profile, region=region)
        if not details.get("roles"):
            report.checks.append(
                CheckResult(
                    id="s3.role_config",
                    status=CheckStatus.FAIL,
                    details={"region": region, **details},
                    remediation=(
                        "Set explicit reference_s3_uri, control_data_s3_uri, "
                        "and stage_s3_uri values."
                    ),
                )
            )
            return report

        report.checks.append(
            CheckResult(
                id="s3.role_config",
                status=CheckStatus.PASS,
                details={"region": region, "roles": details["roles"], "buckets": details["buckets"]},
            )
        )

        if ok:
            report.checks.append(
                CheckResult(
                    id="s3.role_verify",
                    status=CheckStatus.PASS,
                    details={"region": region, "verified": True, **details},
                )
            )
        else:
            report.checks.append(
                CheckResult(
                    id="s3.role_verify",
                    status=CheckStatus.FAIL,
                    details={"region": region, "verified": False, **details},
                    remediation=(
                        "S3 role verification failed. Confirm every role bucket exists, "
                        "reference contains "
                        f"{REFERENCE_VERSION_KEY}={DEFAULT_REFERENCE_VERSION}, and role "
                        "prefixes contain the required contract data."
                    ),
                )
            )

        return report

    return step
