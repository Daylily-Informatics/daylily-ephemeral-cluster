from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from daylily_ec.aws.sentieon_license import (
    DEFAULT_SECRET_NAME,
    SentieonLicenseSecretMetadata,
    ensure_sentieon_license_secret,
    materialize_sentieon_license,
    read_metadata,
)

SECRET_ARN = (
    "arn:aws:secretsmanager:us-west-2:123456789012:"
    "secret:dayec/sentieon/license-servers/usw2d-01-AbCdEf"
)
VERSION_ID = "00000000-1111-2222-3333-444444444444"
LICENSE_BYTES = b"opaque-vendor-license\n"
LICENSE_SHA256 = hashlib.sha256(LICENSE_BYTES).hexdigest()


def _private_license(tmp_path: Path, value: bytes = LICENSE_BYTES) -> Path:
    path = tmp_path / "cluster.lic"
    path.write_bytes(value)
    path.chmod(0o600)
    return path


def _not_found() -> ClientError:
    return ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "not found"}},
        "DescribeSecret",
    )


def _existing_client(*, value: object = LICENSE_BYTES) -> MagicMock:
    client = MagicMock()
    client.describe_secret.return_value = {
        "ARN": SECRET_ARN,
        "Name": DEFAULT_SECRET_NAME,
    }
    client.get_secret_value.return_value = {
        "ARN": SECRET_ARN,
        "VersionId": VERSION_ID,
        "SecretBinary": value,
    }
    return client


def _metadata() -> SentieonLicenseSecretMetadata:
    return SentieonLicenseSecretMetadata(
        secret_arn=SECRET_ARN,
        version_id=VERSION_ID,
        sha256=LICENSE_SHA256,
    )


def test_ensure_creates_binary_secret_without_string_or_secret_logging(tmp_path: Path) -> None:
    client = MagicMock()
    client.describe_secret.side_effect = _not_found()
    client.create_secret.return_value = {"ARN": SECRET_ARN, "VersionId": VERSION_ID}

    result = ensure_sentieon_license_secret(
        secretsmanager_client=client,
        license_path=_private_license(tmp_path),
    )

    assert result == _metadata()
    kwargs = client.create_secret.call_args.kwargs
    assert kwargs["Name"] == DEFAULT_SECRET_NAME
    assert kwargs["SecretBinary"] == LICENSE_BYTES
    assert "SecretString" not in kwargs
    client.get_secret_value.assert_not_called()


def test_ensure_verifies_exact_existing_binary_version(tmp_path: Path) -> None:
    client = _existing_client()

    result = ensure_sentieon_license_secret(
        secretsmanager_client=client,
        license_path=_private_license(tmp_path),
    )

    assert result == _metadata()
    client.get_secret_value.assert_called_once_with(
        SecretId=SECRET_ARN,
        VersionStage="AWSCURRENT",
    )
    client.create_secret.assert_not_called()


def test_ensure_refuses_to_replace_mismatched_existing_value(tmp_path: Path) -> None:
    client = _existing_client(value=b"different-license")

    with pytest.raises(ValueError, match="refusing to replace AWSCURRENT"):
        ensure_sentieon_license_secret(
            secretsmanager_client=client,
            license_path=_private_license(tmp_path),
        )

    client.create_secret.assert_not_called()
    assert not hasattr(client, "put_secret_value") or not client.put_secret_value.called


def test_ensure_rejects_secret_string(tmp_path: Path) -> None:
    client = _existing_client(value=None)
    client.get_secret_value.return_value = {
        "ARN": SECRET_ARN,
        "VersionId": VERSION_ID,
        "SecretString": "forbidden",
    }

    with pytest.raises(ValueError, match="SecretBinary"):
        ensure_sentieon_license_secret(
            secretsmanager_client=client,
            license_path=_private_license(tmp_path),
        )


def test_ensure_rejects_non_private_source_permissions(tmp_path: Path) -> None:
    path = _private_license(tmp_path)
    path.chmod(0o644)

    with pytest.raises(ValueError, match="group or other access"):
        ensure_sentieon_license_secret(
            secretsmanager_client=MagicMock(),
            license_path=path,
        )


def test_ensure_rejects_symlink_source(tmp_path: Path) -> None:
    target = _private_license(tmp_path)
    link = tmp_path / "linked.lic"
    link.symlink_to(target)

    with pytest.raises(ValueError, match="non-symlink"):
        ensure_sentieon_license_secret(
            secretsmanager_client=MagicMock(),
            license_path=link,
        )


def test_metadata_record_contains_only_arn_version_and_hash_and_is_private(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "sentieon-license-metadata.json"

    _metadata().write(destination)

    assert json.loads(destination.read_text(encoding="utf-8")) == {
        "secret_arn": SECRET_ARN,
        "sha256": LICENSE_SHA256,
        "version_id": VERSION_ID,
    }
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert read_metadata(destination) == _metadata()


def test_read_metadata_rejects_extra_fields(tmp_path: Path) -> None:
    destination = tmp_path / "sentieon-license-metadata.json"
    destination.write_text(
        json.dumps(
            {
                "secret_arn": SECRET_ARN,
                "version_id": VERSION_ID,
                "sha256": LICENSE_SHA256,
                "license": "forbidden",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="exactly ARN, version, and hash"):
        read_metadata(destination)


def test_materialize_fetches_on_instance_and_installs_atomically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_shell = MagicMock(
        return_value=SimpleNamespace(
            stdout=f"SENTIEON_LICENSE_MATERIALIZED\t{LICENSE_SHA256}\n",
            stderr="",
        )
    )
    monkeypatch.setattr("daylily_ec.aws.sentieon_license.run_shell", run_shell)

    result = materialize_sentieon_license(
        instance_id="i-0123456789abcdef0",
        region="us-west-2",
        profile="lsmc",
        metadata=_metadata(),
    )

    assert result == _metadata()
    args = run_shell.call_args.args
    kwargs = run_shell.call_args.kwargs
    assert args[:2] == ("i-0123456789abcdef0", "us-west-2")
    script = args[2]
    assert "secretsmanager get-secret-value" in script
    assert '--version-id "$version_id"' in script
    assert "install -o root -g sentieon -m 0640" in script
    assert 'mv -fT -- "$partial" "$destination"' in script
    assert 'test ! -L "$destination"' in script
    assert LICENSE_BYTES.decode().strip() not in script
    assert kwargs == {
        "profile": "lsmc",
        "as_user": "ubuntu",
        "timeout": 300,
        "comment": "Materialize Sentieon license secret",
    }


def test_materialize_fails_on_unexpected_remote_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_shell = MagicMock(return_value=SimpleNamespace(stdout="unexpected\n", stderr=""))
    monkeypatch.setattr("daylily_ec.aws.sentieon_license.run_shell", run_shell)

    with pytest.raises(RuntimeError, match="unexpected output"):
        materialize_sentieon_license(
            instance_id="i-0123456789abcdef0",
            region="us-west-2",
            metadata=_metadata(),
        )
