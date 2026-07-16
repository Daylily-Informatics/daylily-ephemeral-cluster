from __future__ import annotations

from unittest.mock import MagicMock

from daylily_ec.aws.dragen_license import make_dragen_license_preflight_step
from daylily_ec.state.models import CheckStatus, PreflightReport


SECRET_ARN = "arn:aws:secretsmanager:us-west-2:123456789012:secret:dayec/dragen"
POLICY_ARN = "arn:aws:iam::123456789012:policy/dayec-dragen-license-read"


def _report() -> PreflightReport:
    return PreflightReport(
        run_id="test",
        cluster_name="dragen-test",
        region="us-west-2",
        region_az="us-west-2b",
        aws_profile="test",
        account_id="123456789012",
        caller_arn="arn:aws:iam::123456789012:user/test",
    )


def _clients(*, resource: str = SECRET_ARN, actions: list[str] | None = None):
    secrets = MagicMock()
    secrets.describe_secret.return_value = {"ARN": SECRET_ARN}
    iam = MagicMock()
    iam.get_policy.return_value = {"Policy": {"DefaultVersionId": "v1"}}
    iam.get_policy_version.return_value = {
        "PolicyVersion": {
            "Document": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": actions
                        or [
                            "secretsmanager:DescribeSecret",
                            "secretsmanager:GetSecretValue",
                        ],
                        "Resource": resource,
                    }
                ],
            }
        }
    }
    return secrets, iam


def test_license_preflight_validates_metadata_without_reading_secret_value() -> None:
    secrets, iam = _clients()
    step = make_dragen_license_preflight_step(
        secretsmanager_client=secrets,
        iam_client=iam,
        secret_arn=SECRET_ARN,
        policy_arn=POLICY_ARN,
    )

    result = step(_report()).checks[-1]

    assert result.status == CheckStatus.PASS
    assert result.details["secret_value_read"] is False
    secrets.describe_secret.assert_called_once_with(SecretId=SECRET_ARN)
    assert not hasattr(secrets, "get_secret_value") or not secrets.get_secret_value.called


def test_license_preflight_rejects_broad_resource() -> None:
    secrets, iam = _clients(resource="*")
    step = make_dragen_license_preflight_step(
        secretsmanager_client=secrets,
        iam_client=iam,
        secret_arn=SECRET_ARN,
        policy_arn=POLICY_ARN,
    )

    result = step(_report()).checks[-1]

    assert result.status == CheckStatus.FAIL
    assert "Resource must be exactly" in result.details["error"]


def test_license_preflight_rejects_extra_actions() -> None:
    secrets, iam = _clients(
        actions=[
            "secretsmanager:DescribeSecret",
            "secretsmanager:GetSecretValue",
            "secretsmanager:ListSecrets",
        ]
    )
    step = make_dragen_license_preflight_step(
        secretsmanager_client=secrets,
        iam_client=iam,
        secret_arn=SECRET_ARN,
        policy_arn=POLICY_ARN,
    )

    result = step(_report()).checks[-1]

    assert result.status == CheckStatus.FAIL
    assert "actions must be exactly" in result.details["error"]
