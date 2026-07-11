from __future__ import annotations

from unittest.mock import MagicMock

from daylily_ec.aws.github_deploy_key import (
    ALLOWED_SECRET_ACTIONS,
    make_github_deploy_key_preflight_step,
)
from daylily_ec.state.models import CheckStatus, PreflightReport


SECRET_ARN = "arn:aws:secretsmanager:us-west-2:123456789012:secret:dayec/github-deploy-keys/dayoa"
POLICY_ARN = "arn:aws:iam::123456789012:policy/DayECHeadnodeDayOAClone"


def _policy_document(*, actions=None, resource=SECRET_ARN):
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": sorted(actions or ALLOWED_SECRET_ACTIONS),
                "Resource": resource,
            }
        ],
    }


def _clients(*, document=None):
    secrets = MagicMock()
    secrets.describe_secret.return_value = {"ARN": SECRET_ARN, "Name": "dayoa"}
    iam = MagicMock()
    iam.get_policy.return_value = {"Policy": {"Arn": POLICY_ARN, "DefaultVersionId": "v1"}}
    iam.get_policy_version.return_value = {
        "PolicyVersion": {"Document": document or _policy_document()}
    }
    return secrets, iam


def test_github_deploy_key_preflight_validates_metadata_without_reading_secret_value():
    secrets, iam = _clients()
    report = PreflightReport()

    make_github_deploy_key_preflight_step(
        secretsmanager_client=secrets,
        iam_client=iam,
        secret_arn=SECRET_ARN,
        policy_arn=POLICY_ARN,
    )(report)

    assert report.checks[-1].status is CheckStatus.PASS
    assert report.checks[-1].details["secret_value_read"] is False
    secrets.describe_secret.assert_called_once_with(SecretId=SECRET_ARN)
    assert not secrets.get_secret_value.called


def test_github_deploy_key_preflight_rejects_extra_policy_action():
    secrets, iam = _clients(
        document=_policy_document(actions={*ALLOWED_SECRET_ACTIONS, "secretsmanager:ListSecrets"})
    )
    report = PreflightReport()

    make_github_deploy_key_preflight_step(
        secretsmanager_client=secrets,
        iam_client=iam,
        secret_arn=SECRET_ARN,
        policy_arn=POLICY_ARN,
    )(report)

    assert report.checks[-1].status is CheckStatus.FAIL
    assert "exactly secretsmanager:DescribeSecret" in report.checks[-1].details["error"]


def test_github_deploy_key_preflight_rejects_wrong_secret_resource():
    secrets, iam = _clients(document=_policy_document(resource="*"))
    report = PreflightReport()

    make_github_deploy_key_preflight_step(
        secretsmanager_client=secrets,
        iam_client=iam,
        secret_arn=SECRET_ARN,
        policy_arn=POLICY_ARN,
    )(report)

    assert report.checks[-1].status is CheckStatus.FAIL
    assert "Resource must be exactly" in report.checks[-1].details["error"]
