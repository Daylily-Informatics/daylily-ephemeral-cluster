from __future__ import annotations

from unittest.mock import MagicMock

from daylily_ec.aws.github_deploy_key import (
    ALLOWED_SECRET_ACTIONS,
    lsmc_bio_policy_resource,
    make_github_deploy_key_preflight_step,
    managed_github_token_policy_resource,
    portable_lsmc_bio_policy_resource,
)
from daylily_ec.state.models import CheckStatus, PreflightReport

SECRET_ARN = (
    "arn:aws:secretsmanager:us-west-2:123456789012:"
    "secret:dayec/github-deploy-keys/lsmc-bio/dayoa-AbCdEf"
)
POLICY_ARN = "arn:aws:iam::123456789012:policy/DayECHeadnodeGitHubClone"
MANAGED_TOKEN_ARN = (
    "arn:aws:secretsmanager:us-west-2:123456789012:secret:"
    "dayec/github-token/lsmc-bio-dayoa-dyec-AbCdEf"
)


def _statement(*, actions=None, resource=None):
    return {
        "Effect": "Allow",
        "Action": sorted(actions or ALLOWED_SECRET_ACTIONS),
        "Resource": resource or lsmc_bio_policy_resource(SECRET_ARN),
    }


def _policy_document(*, actions=None, resource=None, statements=None):
    return {
        "Version": "2012-10-17",
        "Statement": statements or [_statement(actions=actions, resource=resource)],
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
    assert report.checks[-1].details["policy_resource"].endswith(
        ":secret:dayec/github-deploy-keys/lsmc-bio*"
    )
    assert report.checks[-1].details["portable_policy_resource"].startswith(
        "arn:aws:secretsmanager:*:123456789012:secret:"
    )
    secrets.describe_secret.assert_called_once_with(SecretId=SECRET_ARN)
    assert not secrets.get_secret_value.called


def test_github_deploy_key_preflight_supports_distinct_repository_check_ids():
    secrets, iam = _clients()
    report = PreflightReport()

    make_github_deploy_key_preflight_step(
        secretsmanager_client=secrets,
        iam_client=iam,
        secret_arn=SECRET_ARN,
        policy_arn=POLICY_ARN,
        check_id="iam.dyec_deploy_key_secret_policy",
        display_name="DYEC",
    )(report)

    assert report.checks[-1].id == "iam.dyec_deploy_key_secret_policy"
    assert report.checks[-1].status is CheckStatus.PASS


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


def test_github_deploy_key_preflight_rejects_unscoped_secret_resource():
    secrets, iam = _clients(document=_policy_document(resource="*"))
    report = PreflightReport()

    make_github_deploy_key_preflight_step(
        secretsmanager_client=secrets,
        iam_client=iam,
        secret_arn=SECRET_ARN,
        policy_arn=POLICY_ARN,
    )(report)

    assert report.checks[-1].status is CheckStatus.FAIL
    assert "Resource must be the configured" in report.checks[-1].details["error"]


def test_github_deploy_key_preflight_rejects_exact_single_secret_resource():
    secrets, iam = _clients(document=_policy_document(resource=SECRET_ARN))
    report = PreflightReport()

    make_github_deploy_key_preflight_step(
        secretsmanager_client=secrets,
        iam_client=iam,
        secret_arn=SECRET_ARN,
        policy_arn=POLICY_ARN,
    )(report)

    assert report.checks[-1].status is CheckStatus.FAIL
    assert "deploy-key namespace" in report.checks[-1].details["error"]


def test_github_deploy_key_preflight_rejects_secret_outside_lsmc_bio_namespace():
    secrets, iam = _clients()
    outside_arn = SECRET_ARN.replace("lsmc-bio/dayoa", "another-org/dayoa")
    secrets.describe_secret.return_value = {"ARN": outside_arn, "Name": "dayoa"}
    report = PreflightReport()

    make_github_deploy_key_preflight_step(
        secretsmanager_client=secrets,
        iam_client=iam,
        secret_arn=outside_arn,
        policy_arn=POLICY_ARN,
    )(report)

    assert report.checks[-1].status is CheckStatus.FAIL
    assert "lsmc-bio" in report.checks[-1].details["error"]


def test_github_deploy_key_preflight_accepts_managed_token_statement():
    secrets, iam = _clients(
        document=_policy_document(
            statements=[
                _statement(),
                _statement(resource=MANAGED_TOKEN_ARN),
            ]
        )
    )
    report = PreflightReport()

    make_github_deploy_key_preflight_step(
        secretsmanager_client=secrets,
        iam_client=iam,
        secret_arn=SECRET_ARN,
        policy_arn=POLICY_ARN,
    )(report)

    assert report.checks[-1].status is CheckStatus.PASS
    assert report.checks[-1].details["secret_value_read"] is False


def test_github_deploy_key_preflight_accepts_portable_region_resources():
    secrets, iam = _clients(
        document=_policy_document(
            statements=[
                _statement(resource=portable_lsmc_bio_policy_resource(SECRET_ARN)),
                _statement(
                    resource=managed_github_token_policy_resource(SECRET_ARN, portable=True)
                ),
            ]
        )
    )
    report = PreflightReport()

    make_github_deploy_key_preflight_step(
        secretsmanager_client=secrets,
        iam_client=iam,
        secret_arn=SECRET_ARN,
        policy_arn=POLICY_ARN,
    )(report)

    assert report.checks[-1].status is CheckStatus.PASS


def test_github_deploy_key_preflight_portable_policy_supports_explicit_other_region():
    regional_secret_arn = SECRET_ARN.replace("us-west-2", "eu-central-1")
    secrets, iam = _clients(
        document=_policy_document(
            statements=[
                _statement(resource=portable_lsmc_bio_policy_resource(regional_secret_arn)),
                _statement(
                    resource=managed_github_token_policy_resource(
                        regional_secret_arn,
                        portable=True,
                    )
                ),
            ]
        )
    )
    secrets.describe_secret.return_value = {"ARN": regional_secret_arn, "Name": "dayoa"}
    report = PreflightReport()

    make_github_deploy_key_preflight_step(
        secretsmanager_client=secrets,
        iam_client=iam,
        secret_arn=regional_secret_arn,
        policy_arn=POLICY_ARN,
    )(report)

    assert report.checks[-1].status is CheckStatus.PASS


def test_github_deploy_key_preflight_rejects_unrecognized_second_statement():
    secrets, iam = _clients(
        document=_policy_document(
            statements=[
                _statement(),
                _statement(
                    resource=(
                        "arn:aws:secretsmanager:us-west-2:123456789012:secret:"
                        "dayec/github-token/lsmc-bio-unapproved-*"
                    )
                ),
            ]
        )
    )
    report = PreflightReport()

    make_github_deploy_key_preflight_step(
        secretsmanager_client=secrets,
        iam_client=iam,
        secret_arn=SECRET_ARN,
        policy_arn=POLICY_ARN,
    )(report)

    assert report.checks[-1].status is CheckStatus.FAIL
    assert "designated managed GitHub-token" in report.checks[-1].details["error"]


def test_github_deploy_key_preflight_rejects_account_wildcard():
    secrets, iam = _clients(
        document=_policy_document(
            resource=(
                "arn:aws:secretsmanager:*:*:secret:dayec/github-deploy-keys/lsmc-bio*"
            )
        )
    )
    report = PreflightReport()

    make_github_deploy_key_preflight_step(
        secretsmanager_client=secrets,
        iam_client=iam,
        secret_arn=SECRET_ARN,
        policy_arn=POLICY_ARN,
    )(report)

    assert report.checks[-1].status is CheckStatus.FAIL
    assert "configured LSMC Bio deploy-key namespace" in report.checks[-1].details["error"]


def test_github_deploy_key_preflight_rejects_non_exact_configured_secret_arn():
    wildcard_account_secret_arn = SECRET_ARN.replace(":123456789012:", ":*:")
    secrets, iam = _clients()
    secrets.describe_secret.return_value = {
        "ARN": wildcard_account_secret_arn,
        "Name": "dayoa",
    }
    report = PreflightReport()

    make_github_deploy_key_preflight_step(
        secretsmanager_client=secrets,
        iam_client=iam,
        secret_arn=wildcard_account_secret_arn,
        policy_arn=POLICY_ARN,
    )(report)

    assert report.checks[-1].status is CheckStatus.FAIL
    assert "malformed" in report.checks[-1].details["error"]


def test_github_deploy_key_preflight_rejects_extra_statement():
    secrets, iam = _clients(
        document=_policy_document(
            statements=[
                _statement(),
                _statement(resource=managed_github_token_policy_resource(SECRET_ARN)),
                _statement(resource=managed_github_token_policy_resource(SECRET_ARN)),
            ]
        )
    )
    report = PreflightReport()

    make_github_deploy_key_preflight_step(
        secretsmanager_client=secrets,
        iam_client=iam,
        secret_arn=SECRET_ARN,
        policy_arn=POLICY_ARN,
    )(report)

    assert report.checks[-1].status is CheckStatus.FAIL
    assert "one deploy-key statement" in report.checks[-1].details["error"]


def test_github_deploy_key_preflight_rejects_extra_token_action():
    secrets, iam = _clients(
        document=_policy_document(
            statements=[
                _statement(),
                _statement(
                    actions={*ALLOWED_SECRET_ACTIONS, "secretsmanager:ListSecrets"},
                    resource=MANAGED_TOKEN_ARN,
                ),
            ]
        )
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
