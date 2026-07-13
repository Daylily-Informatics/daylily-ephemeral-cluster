from __future__ import annotations

from pathlib import Path


TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "docs/plans/20260712T102020Z_sentieon_license_server_usw2d_cloudformation.yaml"
)


def _template() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def test_template_scopes_secret_and_runtime_access_to_server_role() -> None:
    text = _template()
    role = text.split("  LicenseServerRole:", 1)[1].split(
        "  LicenseServerInstanceProfile:", 1
    )[0]
    assert role.count("secretsmanager:GetSecretValue") == 1
    assert role.count("secretsmanager:DescribeSecret") == 1
    assert "Resource: !Ref LicenseSecretArn" in role
    assert role.count("s3:GetObject") == 1
    assert role.count("sentieon-genomics-202503.03/") == 4
    assert text.count("secretsmanager:GetSecretValue") == 1


def test_template_never_opens_license_ingress_to_the_public() -> None:
    text = _template()
    ingress = text.split("SecurityGroupIngress:", 1)[1].split(
        "SecurityGroupEgress:", 1
    )[0]
    assert "FromPort: 8990" in ingress
    assert "ToPort: 8990" in ingress
    assert "CidrIp: !Ref AllowedClientCidr" in ingress
    assert "0.0.0.0/0" not in ingress
    assert "::/0" not in ingress


def test_log_group_is_retained_with_bounded_retention() -> None:
    text = _template()
    log_group = text.split("  LicsrvrLogGroup:", 1)[1].split(
        "  LicenseServerSecurityGroup:", 1
    )[0]
    assert "DeletionPolicy: Retain" in log_group
    assert "UpdateReplacePolicy: Retain" in log_group
    assert "LogGroupName: /sentieon/licsrvr/LicsrvrLog" in log_group
    assert "RetentionInDays: 90" in log_group


def test_instance_identity_and_network_contract_remain_fixed() -> None:
    text = _template()
    instance = text.split("  LicenseServerInstance:", 1)[1].split(
        "  LicenseServerElasticIp:", 1
    )[0]
    assert "InstanceType: !Ref InstanceType" in instance
    assert "DeletionPolicy: Retain" in instance
    assert "UpdateReplacePolicy: Retain" in instance
    assert "IamInstanceProfile: !Ref LicenseServerInstanceProfile" in instance
    assert "AssociatePublicIpAddress: false" in instance
    assert "HttpTokens: required" in instance
    assert "usw2d-01.sentieon.lsmc.bio" in text
    assert "license.sentieon.lsmc.bio" in text


def test_stable_address_and_private_zone_are_retained() -> None:
    text = _template()
    elastic_ip = text.split("  LicenseServerElasticIp:", 1)[1].split(
        "  LicenseServerEipAssociation:", 1
    )[0]
    private_zone = text.split("  PrivateHostedZone:", 1)[1].split(
        "  PrivateBackendRecord:", 1
    )[0]
    for resource in (elastic_ip, private_zone):
        assert "DeletionPolicy: Retain" in resource
        assert "UpdateReplacePolicy: Retain" in resource


def test_template_contains_no_vendor_license_material() -> None:
    text = _template()
    assert "Life_Sciences_Data_Manufacturing_cluster.lic" not in text
    assert "BLGWA-" not in text
    assert "SecretBinary" not in text
