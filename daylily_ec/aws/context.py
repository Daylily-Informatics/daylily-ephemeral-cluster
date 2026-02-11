"""AWS context: session, identity, and region resolution.

Wraps boto3 session creation and STS ``get-caller-identity`` into a single
:class:`AWSContext` that every downstream module can depend on.

Region resolution precedence (matches Bash ``resolve_aws_profile``):
1. Explicit ``--region-az`` CLI flag
2. ``AWS_DEFAULT_REGION`` / ``AWS_REGION`` env vars
3. Hardcoded fallback (``us-east-1``)

Profile resolution precedence:
1. Explicit ``--profile`` CLI flag
2. ``AWS_PROFILE`` env var
3. Error — no implicit default
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

_DEFAULT_REGION = "us-east-1"


# ---------------------------------------------------------------------------
# Region / AZ helpers
# ---------------------------------------------------------------------------

def parse_region_az(region_az: str) -> tuple[str, str]:
    """Split ``us-west-2b`` into ``("us-west-2", "b")``.

    Raises :class:`ValueError` if the last character is not a letter.
    """
    if not region_az:
        raise ValueError("region_az must not be empty")
    az_char = region_az[-1]
    if not az_char.isalpha():
        raise ValueError(
            f"Last character of region_az '{region_az}' is '{az_char}', "
            "expected a letter (a-z)"
        )
    region = region_az[:-1]
    if not region:
        raise ValueError(f"region_az '{region_az}' has no region component")
    return region, az_char


def resolve_region(region_az: Optional[str] = None) -> str:
    """Return the AWS region string.

    Precedence: *region_az* flag → ``AWS_DEFAULT_REGION`` → ``AWS_REGION`` → fallback.
    """
    if region_az:
        region, _ = parse_region_az(region_az)
        return region
    return (
        os.environ.get("AWS_DEFAULT_REGION")
        or os.environ.get("AWS_REGION")
        or _DEFAULT_REGION
    )


def resolve_profile(profile: Optional[str] = None) -> str:
    """Return the AWS profile name.

    Precedence: explicit *profile* → ``AWS_PROFILE`` env → raise.
    """
    resolved = profile or os.environ.get("AWS_PROFILE", "")
    if not resolved:
        raise RuntimeError(
            "AWS_PROFILE is not set. Please export AWS_PROFILE or use --profile."
        )
    return resolved


# ---------------------------------------------------------------------------
# AWSContext
# ---------------------------------------------------------------------------

@dataclass
class AWSContext:
    """Immutable bag of AWS identity + session factory.

    Attributes:
        profile: Resolved AWS profile name.
        region: AWS region (e.g. ``us-west-2``).
        region_az: Full AZ string (e.g. ``us-west-2b``).
        account_id: 12-digit AWS account ID.
        caller_arn: Full ARN from ``sts:GetCallerIdentity``.
        iam_username: IAM user or role-session name extracted from *caller_arn*.
    """

    profile: str
    region: str
    region_az: str
    account_id: str = ""
    caller_arn: str = ""
    iam_username: str = ""
    _session: Any = field(default=None, repr=False, compare=False)

    # -- factory ----------------------------------------------------------

    @classmethod
    def build(
        cls,
        region_az: str,
        profile: Optional[str] = None,
    ) -> "AWSContext":
        """Construct an :class:`AWSContext` by calling STS.

        Raises :class:`RuntimeError` on credential / network failures.
        """
        resolved_profile = resolve_profile(profile)
        region, _ = parse_region_az(region_az)

        if resolved_profile == "default":
            logger.warning("AWS_PROFILE is set to 'default'.")

        session = boto3.Session(profile_name=resolved_profile, region_name=region)

        try:
            sts = session.client("sts")
            identity = sts.get_caller_identity()
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(
                f"AWS credentials invalid or inaccessible in region {region}: {exc}"
            ) from exc

        account_id = identity["Account"]
        caller_arn = identity["Arn"]
        iam_username = _extract_username(caller_arn)

        return cls(
            profile=resolved_profile,
            region=region,
            region_az=region_az,
            account_id=account_id,
            caller_arn=caller_arn,
            iam_username=iam_username,
            _session=session,
        )

    # -- session accessor -------------------------------------------------

    @property
    def session(self) -> boto3.Session:
        """Return the cached :class:`boto3.Session`."""
        if self._session is None:
            self._session = boto3.Session(
                profile_name=self.profile, region_name=self.region
            )
        return self._session

    def client(self, service: str, **kwargs: Any) -> Any:
        """Create a boto3 client for *service*."""
        return self.session.client(service, **kwargs)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_username(arn: str) -> str:
    """Extract the IAM user or role-session name from an ARN.

    Examples::

        arn:aws:iam::123456789012:user/alice        → alice
        arn:aws:sts::123456789012:assumed-role/r/s   → s
        arn:aws:iam::123456789012:root               → root
    """
    # Split on '/' and take the last segment
    parts = arn.split("/")
    if len(parts) >= 2:
        return parts[-1]
    # Fallback: last segment after ':'
    return arn.rsplit(":", maxsplit=1)[-1]

