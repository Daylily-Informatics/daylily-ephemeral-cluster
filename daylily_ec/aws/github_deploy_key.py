"""Read-only validation for the DayOA GitHub deploy-key secret policy."""

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


def make_github_deploy_key_preflight_step(
    *,
    secretsmanager_client: Any,
    iam_client: Any,
    secret_arn: str,
    policy_arn: str,
    check_id: str = "iam.dayoa_deploy_key_secret_policy",
    display_name: str = "DayOA",
):
    """Validate secret metadata and an exact least-privilege managed policy.

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
            _validate_policy_document(document, secret_arn)
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
                        f"Create the configured {display_name} deploy-key secret and a managed "
                        "policy granting "
                        "only secretsmanager:DescribeSecret and "
                        "secretsmanager:GetSecretValue on that exact secret ARN."
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


def _validate_policy_document(document: dict[str, Any], secret_arn: str) -> None:
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
    if [str(resource) for resource in resources] != [secret_arn]:
        raise ValueError("Managed policy Resource must be exactly the configured secret ARN.")
    if statement.get("NotAction") or statement.get("NotResource"):
        raise ValueError("Managed policy must not use NotAction or NotResource.")
