"""Read-only validation for the shared LSMC GitHub deploy-key secret policy."""

from __future__ import annotations

import json
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


def lsmc_bio_policy_resource(secret_arn: str) -> str:
    """Return the exact IAM resource pattern for LSMC Bio deploy-key secrets."""

    marker = ":secret:"
    if marker not in secret_arn:
        raise ValueError("Configured deploy-key secret ARN is malformed.")
    arn_prefix, secret_name = secret_arn.split(marker, 1)
    if not secret_name.startswith(LSMC_BIO_SECRET_NAME_PREFIX):
        raise ValueError(
            "Configured deploy-key secret must use the "
            f"{LSMC_BIO_SECRET_NAME_PREFIX!r} Secrets Manager namespace."
        )
    return f"{arn_prefix}{marker}{LSMC_BIO_SECRET_NAME_PREFIX}*"


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
            _validate_policy_document(document, policy_resource)
        except Exception as exc:
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
                        "policy granting "
                        "only secretsmanager:DescribeSecret and "
                        "secretsmanager:GetSecretValue on that namespace."
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
        raise ValueError("Managed policy document must be a JSON mapping.")
    return decoded


def _validate_policy_document(document: dict[str, Any], policy_resource: str) -> None:
    statements = document.get("Statement") or []
    if isinstance(statements, dict):
        statements = [statements]
    if not isinstance(statements, list) or len(statements) != 1:
        raise ValueError("Managed policy must contain exactly one statement.")
    statement = statements[0]
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

    resources = statement.get("Resource") or []
    if isinstance(resources, str):
        resources = [resources]
    if [str(resource) for resource in resources] != [policy_resource]:
        raise ValueError(
            "Managed policy Resource must be exactly the configured LSMC Bio "
            "deploy-key namespace."
        )
    if statement.get("NotAction") or statement.get("NotResource"):
        raise ValueError("Managed policy must not use NotAction or NotResource.")
