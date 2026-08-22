"""Exact operator controls for one configured LSMC Bio deploy-key secret."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from daylily_ec.aws.context import AWSContext
from daylily_ec.aws.github_deploy_key import LSMC_BIO_SECRET_NAME_PREFIX


_SECRET_ARN_RE = re.compile(
    r"^arn:(?P<partition>aws(?:-us-gov)?):secretsmanager:"
    r"(?P<region>[a-z0-9-]+):(?P<account_id>\d{12}):secret:"
    r"(?P<secret_name>[A-Za-z0-9/_+=.@-]+)$"
)


@dataclass(frozen=True)
class DeployKeySecretStatus:
    """Metadata-only state for one exact configured deploy-key secret."""

    secret_arn: str
    region: str
    account_id: str
    deletion_scheduled: bool
    deleted_date: str | None


def inspect_deploy_key_secret(
    aws_ctx: AWSContext,
    *,
    secret_arn: str,
) -> DeployKeySecretStatus:
    """Describe one exact secret without requesting its value."""

    _validate_secret_arn(aws_ctx, secret_arn)
    description = aws_ctx.client("secretsmanager").describe_secret(SecretId=secret_arn)
    _require_exact_returned_arn(description, secret_arn)
    deleted_date = description.get("DeletedDate")
    return DeployKeySecretStatus(
        secret_arn=secret_arn,
        region=aws_ctx.region,
        account_id=aws_ctx.account_id,
        deletion_scheduled=deleted_date is not None,
        deleted_date=_isoformat(deleted_date),
    )


def _validate_secret_arn(aws_ctx: AWSContext, secret_arn: str) -> None:
    match = _SECRET_ARN_RE.fullmatch(secret_arn.strip())
    if match is None:
        raise ValueError("Configured deploy-key secret ARN is malformed.")
    secret_name = match.group("secret_name")
    if not secret_name.startswith(LSMC_BIO_SECRET_NAME_PREFIX):
        raise ValueError(
            "Configured deploy-key secret must use the "
            f"{LSMC_BIO_SECRET_NAME_PREFIX!r} Secrets Manager namespace."
        )
    if match.group("region") != aws_ctx.region:
        raise ValueError("Configured deploy-key secret ARN region does not match --region.")
    if match.group("account_id") != aws_ctx.account_id:
        raise ValueError("Configured deploy-key secret ARN account does not match the AWS caller.")


def _require_exact_returned_arn(response: dict[str, Any], expected_arn: str) -> None:
    if str(response.get("ARN") or "") != expected_arn:
        raise RuntimeError("Secrets Manager returned a different secret ARN.")


def _isoformat(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
