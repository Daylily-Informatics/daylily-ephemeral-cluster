from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

from daylily_ec.aws import sentieon_license as license_module
from daylily_ec.aws import sentieon_license_server as server_module


def _metadata() -> license_module.SentieonLicenseSecretMetadata:
    return license_module.SentieonLicenseSecretMetadata(
        secret_arn=(
            "arn:aws:secretsmanager:us-west-2:123456789012:"
            "secret:dayec/sentieon/license-servers/usw2d-01-abcdef"
        ),
        version_id="version-1",
        sha256="a" * 64,
    )


@pytest.mark.parametrize(
    ("operation", "target", "extra"),
    [
        ("install", "install_license_server", []),
        ("start", "start_license_server", []),
        ("restart", "restart_license_server", ["--approve-restart"]),
        ("validate", "validate_license_server", []),
        ("install-cloudwatch-agent", "install_cloudwatch_agent", []),
        ("configure-logging", "configure_cloudwatch_logging", []),
    ],
)
def test_license_server_main_dispatches_every_operation(
    monkeypatch, capsys, operation, target, extra
):
    calls: list[dict] = []
    monkeypatch.setattr(server_module, target, lambda **kwargs: calls.append(kwargs))

    assert (
        server_module.main(
            [
                operation,
                "--instance-id",
                "i-server",
                "--region",
                "us-west-2",
                "--profile",
                "test",
                *extra,
            ]
        )
        == 0
    )
    assert calls[0]["instance_id"] == "i-server"
    assert calls[0]["region"] == "us-west-2"
    if operation == "restart":
        assert calls[0]["approve_restart"] is True
    assert f"{operation} completed" in capsys.readouterr().out


def test_license_server_main_redacts_failure_to_error_exit(monkeypatch, capsys):
    monkeypatch.setattr(
        server_module,
        "install_license_server",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("install failed")),
    )
    assert (
        server_module.main(["install", "--instance-id", "i-server", "--region", "us-west-2"]) == 1
    )
    assert "ERROR: install failed" in capsys.readouterr().err


def test_license_server_runtime_markers_and_failures(monkeypatch):
    monkeypatch.setattr(
        server_module,
        "run_shell",
        lambda *_args, **_kwargs: SimpleNamespace(stdout="unexpected"),
    )
    with pytest.raises(RuntimeError, match="unexpected output"):
        server_module.install_license_server(
            instance_id="i-server", region="us-west-2", profile="test"
        )
    with pytest.raises(RuntimeError, match="unexpected output"):
        server_module._run_service_action(
            action="validate",
            instance_id="i-server",
            region="us-west-2",
            profile="test",
        )
    with pytest.raises(RuntimeError, match="unexpected output"):
        server_module.configure_cloudwatch_logging(
            instance_id="i-server", region="us-west-2", profile="test"
        )
    with pytest.raises(ValueError, match="Unsupported"):
        server_module._service_action_script("stop")


def test_license_main_ensure_writes_metadata(monkeypatch, tmp_path, capsys):
    metadata = _metadata()
    writes: list[Path] = []
    monkeypatch.setattr(
        license_module.boto3,
        "Session",
        lambda **_kwargs: SimpleNamespace(client=lambda _service: object()),
    )
    monkeypatch.setattr(
        license_module,
        "ensure_sentieon_license_secret",
        lambda **_kwargs: metadata,
    )
    monkeypatch.setattr(
        license_module.SentieonLicenseSecretMetadata,
        "write",
        lambda self, path: writes.append(path),
    )
    metadata_path = tmp_path / "metadata.json"
    assert (
        license_module.main(
            [
                "ensure",
                "--license-file",
                str(tmp_path / "license.lic"),
                "--metadata-file",
                str(metadata_path),
                "--secret-name",
                "dayec/test",
                "--region",
                "us-west-2",
                "--profile",
                "test",
            ]
        )
        == 0
    )
    assert writes == [metadata_path]
    output = capsys.readouterr().out
    assert metadata.secret_arn in output
    assert metadata.version_id in output
    assert metadata.sha256 in output


def test_license_main_materialize_reads_exact_metadata(monkeypatch, tmp_path, capsys):
    metadata = _metadata()
    calls: list[dict] = []
    monkeypatch.setattr(license_module, "read_metadata", lambda _path: metadata)
    monkeypatch.setattr(
        license_module,
        "materialize_sentieon_license",
        lambda **kwargs: calls.append(kwargs),
    )
    assert (
        license_module.main(
            [
                "materialize",
                "--instance-id",
                "i-server",
                "--metadata-file",
                str(tmp_path / "metadata.json"),
                "--region",
                "us-west-2",
                "--profile",
                "test",
            ]
        )
        == 0
    )
    assert calls == [
        {
            "instance_id": "i-server",
            "region": "us-west-2",
            "profile": "test",
            "metadata": metadata,
        }
    ]
    assert "Materialized Sentieon license secret" in capsys.readouterr().out


def test_license_main_returns_error_for_safe_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        license_module,
        "read_metadata",
        lambda _path: (_ for _ in ()).throw(ValueError("invalid metadata")),
    )
    assert (
        license_module.main(
            [
                "materialize",
                "--instance-id",
                "i-server",
                "--metadata-file",
                str(tmp_path / "metadata.json"),
                "--region",
                "us-west-2",
            ]
        )
        == 1
    )
    assert "ERROR: invalid metadata" in capsys.readouterr().err


def test_license_secret_and_metadata_failure_edges(tmp_path, monkeypatch):
    license_file = tmp_path / "license.lic"
    license_file.write_bytes(b"license")
    license_file.chmod(0o600)
    error = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
        "DescribeSecret",
    )
    client = SimpleNamespace(describe_secret=lambda **_kwargs: (_ for _ in ()).throw(error))
    with pytest.raises(RuntimeError, match="Unable to describe"):
        license_module.ensure_sentieon_license_secret(
            secretsmanager_client=client, license_path=license_file
        )
    with pytest.raises(ValueError, match="regular, non-symlink"):
        license_module.read_metadata(tmp_path / "missing.json")
    with pytest.raises(ValueError, match="unexpected fields"):
        license_module._write_metadata(tmp_path / "metadata.json", {"extra": "value"})
    with pytest.raises(ValueError, match="existing non-symlink"):
        license_module._write_metadata(
            tmp_path / "missing" / "metadata.json",
            {
                "secret_arn": _metadata().secret_arn,
                "version_id": "version-1",
                "sha256": "a" * 64,
            },
        )
