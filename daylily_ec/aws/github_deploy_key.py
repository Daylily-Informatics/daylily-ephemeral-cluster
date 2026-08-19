"""Read-only validation for the scoped LSMC GitHub credential policy."""

from __future__ import annotations

import json
import re
from fnmatch import fnmatchcase
from typing import Any
from urllib.parse import unquote

from daylily_ec.state.models import CheckResult, CheckStatus, PreflightReport

ALLOWED_SECRET_ACTIONS = frozenset(
    {
        "secretsmanager:DescribeSecret",
        "secretsmanager:GetSecretValue",
    }
)
LSMC_BIO_SECRET_NAME_PREFIX = "dayec/github-deploy-keys/lsmc-bio"
MANAGED_GITHUB_TOKEN_SECRET_NAME = "dayec/github-token/lsmc-bio-dayoa-dyec"


def _secretsmanager_policy_arn_prefix(secret_arn: str, *, portable: bool = False) -> str:
    """Return the Secrets Manager policy ARN prefix for one configured secret."""

    marker = ":secret:"
    if marker not in secret_arn:
        raise ValueError("Configured deploy-key secret ARN is malformed.")
    arn_prefix, _secret_name = secret_arn.split(marker, 1)
    parts = arn_prefix.split(":")
    if (
        len(parts) != 5
        or parts[0] != "arn"
        or parts[1] not in {"aws", "aws-us-gov"}
        or parts[2] != "secretsmanager"
        or not re.fullmatch(r"[a-z0-9-]+", parts[3])
        or not re.fullmatch(r"\d{12}", parts[4])
    ):
        raise ValueError("Configured deploy-key secret ARN is malformed.")
    if portable:
        parts[3] = "*"
    return ":".join(parts)


def lsmc_bio_policy_resource(secret_arn: str) -> str:
    """Return the exact IAM resource pattern for LSMC Bio deploy-key secrets."""

    marker = ":secret:"
    if marker not in secret_arn:
        raise ValueError("Configured deploy-key secret ARN is malformed.")
    _arn_prefix, secret_name = secret_arn.split(marker, 1)
    if not secret_name.startswith(LSMC_BIO_SECRET_NAME_PREFIX):
        raise ValueError(
            "Configured deploy-key secret must use the "
            f"{LSMC_BIO_SECRET_NAME_PREFIX!r} Secrets Manager namespace."
        )
    return f"{_secretsmanager_policy_arn_prefix(secret_arn)}{marker}{LSMC_BIO_SECRET_NAME_PREFIX}*"


def portable_lsmc_bio_policy_resource(secret_arn: str) -> str:
    """Return the account-scoped, region-portable deploy-key resource pattern."""

    marker = ":secret:"
    if marker not in secret_arn:
        raise ValueError("Configured deploy-key secret ARN is malformed.")
    _arn_prefix, secret_name = secret_arn.split(marker, 1)
    if not secret_name.startswith(LSMC_BIO_SECRET_NAME_PREFIX):
        raise ValueError(
            "Configured deploy-key secret must use the "
            f"{LSMC_BIO_SECRET_NAME_PREFIX!r} Secrets Manager namespace."
        )
    return (
        f"{_secretsmanager_policy_arn_prefix(secret_arn, portable=True)}"
        f"{marker}{LSMC_BIO_SECRET_NAME_PREFIX}*"
    )


def managed_github_token_policy_resource(secret_arn: str, *, portable: bool = False) -> str:
    """Return the scoped managed-token policy resource compatible with one account."""

    prefix = _secretsmanager_policy_arn_prefix(secret_arn, portable=portable)
    return f"{prefix}:secret:{MANAGED_GITHUB_TOKEN_SECRET_NAME}-*"


def make_github_deploy_key_preflight_step(
    *,
    secretsmanager_client: Any,
    iam_client: Any,
    secret_arn: str,
    policy_arn: str,
    check_id: str = "iam.dayoa_deploy_key_secret_policy",
    display_name: str = "DayOA",
):
    """Validate secret metadata and the shared LSMC headnode managed policy.

    The preflight deliberately does not read the deploy-key value.
    """

    def step(report: PreflightReport) -> PreflightReport:
        try:
            secret = secretsmanager_client.describe_secret(SecretId=secret_arn)
            if str(secret.get("ARN") or "") != secret_arn:
                raise ValueError("Secrets Manager returned a different secret ARN.")
            if secret.get("DeletedDate") is not None:
                raise ValueError("Configured deploy-key secret is scheduled for deletion.")
            if secret.get("KmsKeyId"):
                raise ValueError(
                    "Configured deploy-key secret uses a customer KMS key; this contract "
                    "supports the Secrets Manager managed key only."
                )

            policy = iam_client.get_policy(PolicyArn=policy_arn).get("Policy") or {}
            version_id = str(policy.get("DefaultVersionId") or "")
            if not version_id:
                raise ValueError("Managed policy has no default version.")
            version = (
                iam_client.get_policy_version(
                    PolicyArn=policy_arn,
                    VersionId=version_id,
                ).get("PolicyVersion")
                or {}
            )
            document = _policy_document(version.get("Document"))
            policy_resource = lsmc_bio_policy_resource(secret_arn)
            portable_policy_resource = portable_lsmc_bio_policy_resource(secret_arn)
            _validate_policy_document(
                document,
                policy_resource=policy_resource,
                portable_policy_resource=portable_policy_resource,
                managed_token_resource=managed_github_token_policy_resource(secret_arn),
                portable_managed_token_resource=managed_github_token_policy_resource(
                    secret_arn,
                    portable=True,
                ),
            )
        except Exception as exc:  # noqa: BLE001 - preflight records all remote/schema failures.
            report.checks.append(
                CheckResult(
                    id=check_id,
                    status=CheckStatus.FAIL,
                    details={
                        "secret_arn": secret_arn,
                        "policy_arn": policy_arn,
                        "secret_value_read": False,
                        "error": str(exc),
                    },
                    remediation=(
                        f"Create the configured {display_name} deploy-key secret in the "
                        f"{LSMC_BIO_SECRET_NAME_PREFIX!r} namespace and a headnode-only managed "
                        "policy with one deploy-key statement and, only when needed, one "
                        "managed GitHub-token statement. Each statement must grant only "
                        "secretsmanager:DescribeSecret and secretsmanager:GetSecretValue "
                        "on its explicitly allowed resource."
                    ),
                )
            )
            return report

        report.checks.append(
            CheckResult(
                id=check_id,
                status=CheckStatus.PASS,
                details={
                    "secret_arn": secret_arn,
                    "policy_arn": policy_arn,
                    "policy_actions": sorted(ALLOWED_SECRET_ACTIONS),
                    "policy_resource": policy_resource,
                    "portable_policy_resource": portable_policy_resource,
                    "secret_value_read": False,
                },
            )
        )
        return report

    return step


def _policy_document(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Managed policy version has no policy document.")
    decoded = json.loads(unquote(value))
    if not isinstance(decoded, dict):
        raise TypeError("Managed policy document must be a JSON mapping.")
    return decoded


def _validate_policy_document(
    document: dict[str, Any],
    *,
    policy_resource: str,
    portable_policy_resource: str,
    managed_token_resource: str,
    portable_managed_token_resource: str,
) -> None:
    statements = document.get("Statement") or []
    if isinstance(statements, dict):
        statements = [statements]
    if not isinstance(statements, list) or len(statements) not in {1, 2}:
        raise ValueError(
            "Managed policy must contain one deploy-key statement and may contain one "
            "managed GitHub-token statement."
        )

    deploy_resources = {policy_resource, portable_policy_resource}
    token_resources = (managed_token_resource, portable_managed_token_resource)
    observed_kinds: set[str] = set()
    for statement in statements:
        resource = _single_statement_resource(statement)
        if resource in deploy_resources:
            kind = "deploy-key"
        elif any(fnmatchcase(resource, pattern) for pattern in token_resources):
            kind = "managed GitHub-token"
        else:
            raise ValueError(
                "Managed policy Resource must be the configured LSMC Bio deploy-key "
                "namespace or the designated managed GitHub-token secret."
            )
        if kind in observed_kinds:
            raise ValueError(f"Managed policy contains more than one {kind} statement.")
        _validate_secret_read_statement(statement)
        observed_kinds.add(kind)

    if "deploy-key" not in observed_kinds:
        raise ValueError("Managed policy is missing the deploy-key statement.")
    if len(statements) == 2 and "managed GitHub-token" not in observed_kinds:
        raise ValueError("Managed policy has an unrecognized second statement.")


def _single_statement_resource(statement: Any) -> str:
    if not isinstance(statement, dict):
        raise TypeError("Managed policy statement must be a mapping.")
    resources = statement.get("Resource") or []
    if isinstance(resources, str):
        resources = [resources]
    if not isinstance(resources, list) or len(resources) != 1:
        raise ValueError("Managed policy statement must name exactly one Resource.")
    return str(resources[0])


def _validate_secret_read_statement(statement: Any) -> None:
    if not isinstance(statement, dict) or statement.get("Effect") != "Allow":
        raise ValueError("Managed policy statement must have Effect Allow.")

    actions = statement.get("Action") or []
    if isinstance(actions, str):
        actions = [actions]
    if frozenset(str(action) for action in actions) != ALLOWED_SECRET_ACTIONS:
        raise ValueError(
            "Managed policy actions must be exactly secretsmanager:DescribeSecret and "
            "secretsmanager:GetSecretValue."
        )
    if statement.get("NotAction") or statement.get("NotResource"):
        raise ValueError("Managed policy must not use NotAction or NotResource.")
