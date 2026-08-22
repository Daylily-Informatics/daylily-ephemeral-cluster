from __future__ import annotations

from datetime import datetime, timezone

import pytest

from daylily_ec.aws.context import AWSContext
from daylily_ec.aws.github_deploy_key_secret import (
    inspect_deploy_key_secret,
)


SECRET_ARN = (
    "arn:aws:secretsmanager:us-west-2:123456789012:secret:"
    "dayec/github-deploy-keys/lsmc-bio-daylily-omics-analysis-ABC123"
)


class _SecretsManager:
    def __init__(self, *, deleted_date: datetime | None) -> None:
        self.deleted_date = deleted_date
        self.calls: list[tuple[str, str]] = []

    def describe_secret(self, *, SecretId: str):
        self.calls.append(("describe", SecretId))
        payload = {"ARN": SECRET_ARN}
        if self.deleted_date is not None:
            payload["DeletedDate"] = self.deleted_date
        return payload

def _context(client: _SecretsManager) -> AWSContext:
    context = AWSContext(
        profile="lsmc",
        region="us-west-2",
        region_az="us-west-2",
        account_id="123456789012",
    )
    context.client = lambda service: client  # type: ignore[method-assign]
    return context


def test_status_reads_only_exact_secret_metadata() -> None:
    deleted_date = datetime(2026, 8, 22, tzinfo=timezone.utc)
    client = _SecretsManager(deleted_date=deleted_date)

    result = inspect_deploy_key_secret(_context(client), secret_arn=SECRET_ARN)

    assert result.deletion_scheduled is True
    assert result.deleted_date == deleted_date.isoformat()
    assert client.calls == [("describe", SECRET_ARN)]


def test_status_rejects_account_mismatch_before_aws_call() -> None:
    client = _SecretsManager(deleted_date=None)
    context = _context(client)
    context.account_id = "999999999999"

    with pytest.raises(ValueError, match="account does not match"):
        inspect_deploy_key_secret(context, secret_arn=SECRET_ARN)

    assert client.calls == []
