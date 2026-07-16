from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import pytest

from daylily_ec.aws import sentieon_license_server as server


def test_minimal_runtime_objects_are_exact_and_pinned() -> None:
    assert [item.relative_path for item in server.RUNTIME_OBJECTS] == [
        "bin/sentieon",
        "share/funcs",
        "libexec/licsrvr",
        "libexec/licclnt",
    ]
    assert {item.mode for item in server.RUNTIME_OBJECTS} == {0o644, 0o755}
    assert all(len(item.sha256) == 64 for item in server.RUNTIME_OBJECTS)
    assert all(
        item.s3_uri.startswith(
            "s3://lsmc-dayoa-references-usw2/runtime_assets/cached_envs/"
            "sentieon-genomics-202503.03/"
        )
        for item in server.RUNTIME_OBJECTS
    )


def test_systemd_unit_uses_vendor_contract_and_hardening() -> None:
    unit = server.SYSTEMD_UNIT
    assert "Type=forking" in unit
    assert "User=sentieon" in unit
    assert "Group=sentieon" in unit
    assert "licsrvr --start --thread_count 4 --log" in unit
    assert "licsrvr --stop /etc/sentieon/license.lic" in unit
    assert "NoNewPrivileges=true" in unit
    assert "ProtectSystem=strict" in unit
    assert "PrivateTmp=true" in unit
    assert "ReadOnlyPaths=/opt/sentieon/202503.03 /etc/sentieon" in unit


def test_install_script_is_secret_safe_and_fail_closed() -> None:
    script = server._install_script()
    assert "secretsmanager get-secret-value" not in script
    assert "SENTIEON_LICENSE_SERVER_INSTALLED" in script
    assert "root:sentieon 640" in script
    assert "systemctl restart sentieon-license-server.service" not in script
    assert "systemctl start sentieon-license-server.service" not in script
    assert "licclnt ping" not in script
    assert "0.0.0.0/0" not in script
    for item in server.RUNTIME_OBJECTS:
        assert item.sha256 in script
        assert item.s3_uri in script


def test_cloudwatch_script_has_exact_group_and_pinned_agent() -> None:
    script = server._cloudwatch_script()
    assert server.CLOUDWATCH_AGENT_VERSION in script
    assert server.CLOUDWATCH_LOG_GROUP in base64.b64decode(
        next(
            token.strip("'")
            for token in script.split()
            if token.strip("'").startswith("ewogICJhZ2VudCI")
        )
    ).decode()
    assert "retention_in_days" not in script


def test_install_requires_exact_remote_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run_shell(*args: object, **kwargs: object) -> SimpleNamespace:
        calls.append({"args": args, "kwargs": kwargs})
        return SimpleNamespace(
            stdout=f"SENTIEON_LICENSE_SERVER_INSTALLED\t{server.RUNTIME_VERSION}\n",
            stderr="",
        )

    monkeypatch.setattr(server, "run_shell", fake_run_shell)
    server.install_license_server(
        instance_id="i-0123456789abcdef0",
        region="us-west-2",
        profile="lsmc",
    )

    assert calls[0]["kwargs"]["as_user"] == "ubuntu"
    assert calls[0]["kwargs"]["timeout"] == 600


def test_install_rejects_unexpected_remote_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        server,
        "run_shell",
        lambda *args, **kwargs: SimpleNamespace(stdout="unexpected\n", stderr=""),
    )
    with pytest.raises(RuntimeError, match="unexpected output"):
        server.install_license_server(
            instance_id="i-0123456789abcdef0",
            region="us-west-2",
        )


def test_cloudwatch_config_is_valid_json() -> None:
    script = server._cloudwatch_script()
    encoded = next(
        token.strip("'")
        for token in script.split()
        if token.strip("'").startswith("ewogICJhZ2VudCI")
    )
    payload = json.loads(base64.b64decode(encoded))
    item = payload["logs"]["logs_collected"]["files"]["collect_list"][0]
    assert item == {
        "file_path": "/var/log/sentieon/licsrvr.log",
        "log_group_name": "/sentieon/licsrvr/LicsrvrLog",
        "log_stream_name": "{instance_id}",
        "timezone": "UTC",
    }


@pytest.mark.parametrize("action", ["start", "restart", "validate"])
def test_service_action_script_is_explicit_and_validates_endpoints(action: str) -> None:
    script = server._service_action_script(action)
    if action == "validate":
        assert "systemctl start" not in script
        assert "systemctl restart" not in script
    else:
        assert f"systemctl {action} sentieon-license-server.service" in script
    assert "license.sentieon.lsmc.bio:8990" in script
    assert "usw2d-01.sentieon.lsmc.bio:8990" in script
    assert "systemctl show --property MainPID" in script
    assert "listener_owned" in script
    assert f"SENTIEON_LICENSE_SERVER_{action.upper()}_OK" in script


def test_restart_requires_explicit_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server,
        "run_shell",
        lambda *args, **kwargs: pytest.fail("restart must fail before remote execution"),
    )
    with pytest.raises(ValueError, match="--approve-restart"):
        server.restart_license_server(
            instance_id="i-0123456789abcdef0",
            region="us-west-2",
        )


def test_start_does_not_restart_active_service(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_run_shell(instance_id: str, region: str, script: str, **kwargs: object):
        calls.append(script)
        return SimpleNamespace(stdout="SENTIEON_LICENSE_SERVER_START_OK\n", stderr="")

    monkeypatch.setattr(server, "run_shell", fake_run_shell)
    server.start_license_server(
        instance_id="i-0123456789abcdef0",
        region="us-west-2",
    )
    assert "systemctl start sentieon-license-server.service" in calls[0]
    assert "systemctl restart" not in calls[0]


def test_install_cloudwatch_agent_uses_pinned_ssm_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    class FakeClient:
        def send_command(self, **kwargs: object) -> dict[str, object]:
            calls.append(kwargs)
            return {"Command": {"CommandId": "cmd-1"}}

        def get_command_invocation(self, **kwargs: object) -> dict[str, str]:
            return {"Status": "Success"}

    class FakeSession:
        def client(self, name: str) -> FakeClient:
            assert name == "ssm"
            return FakeClient()

    monkeypatch.setattr(server.boto3, "Session", lambda **kwargs: FakeSession())
    monkeypatch.setattr(
        server,
        "run_shell",
        lambda *args, **kwargs: SimpleNamespace(
            stdout=(
                "SENTIEON_CLOUDWATCH_AGENT_READY\t"
                f"{server.CLOUDWATCH_AGENT_VERSION}\n"
            ),
            stderr="",
        ),
    )

    server.install_cloudwatch_agent(
        instance_id="i-0123456789abcdef0",
        region="us-west-2",
        profile="lsmc",
    )

    assert calls == [
        {
            "InstanceIds": ["i-0123456789abcdef0"],
            "DocumentName": "AWS-ConfigureAWSPackage",
            "Parameters": {
                "action": ["Install"],
                "installationType": ["Uninstall and reinstall"],
                "name": ["AmazonCloudWatchAgent"],
                "version": [server.CLOUDWATCH_AGENT_VERSION],
            },
            "TimeoutSeconds": 600,
            "Comment": "Install pinned CloudWatch Agent for Sentieon license server",
        }
    ]


def test_install_cloudwatch_agent_retries_invocation_visibility_race(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    polls = 0

    class FakeClient:
        def send_command(self, **kwargs: object) -> dict[str, object]:
            return {"Command": {"CommandId": "cmd-race"}}

        def get_command_invocation(self, **kwargs: object) -> dict[str, str]:
            nonlocal polls
            polls += 1
            if polls == 1:
                raise server.ClientError(
                    {
                        "Error": {
                            "Code": "InvocationDoesNotExist",
                            "Message": "not visible yet",
                        }
                    },
                    "GetCommandInvocation",
                )
            return {"Status": "Success"}

    class FakeSession:
        def client(self, name: str) -> FakeClient:
            assert name == "ssm"
            return FakeClient()

    monkeypatch.setattr(server.boto3, "Session", lambda **kwargs: FakeSession())
    monkeypatch.setattr(server.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        server,
        "run_shell",
        lambda *args, **kwargs: SimpleNamespace(
            stdout=(
                "SENTIEON_CLOUDWATCH_AGENT_READY\t"
                f"{server.CLOUDWATCH_AGENT_VERSION}\n"
            ),
            stderr="",
        ),
    )

    server.install_cloudwatch_agent(
        instance_id="i-0123456789abcdef0",
        region="us-west-2",
    )

    assert polls == 2


def test_install_cloudwatch_agent_times_out_when_invocation_never_appears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeClient:
        def send_command(self, **kwargs: object) -> dict[str, object]:
            return {"Command": {"CommandId": "cmd-missing"}}

        def get_command_invocation(self, **kwargs: object) -> dict[str, str]:
            raise server.ClientError(
                {
                    "Error": {
                        "Code": "InvocationDoesNotExist",
                        "Message": "not visible",
                    }
                },
                "GetCommandInvocation",
            )

    class FakeSession:
        def client(self, name: str) -> FakeClient:
            assert name == "ssm"
            return FakeClient()

    clock = iter((0.0, 2.0))
    monkeypatch.setattr(server.boto3, "Session", lambda **kwargs: FakeSession())
    monkeypatch.setattr(server.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(
        server.time,
        "sleep",
        lambda seconds: pytest.fail("deadline should fail before sleeping"),
    )

    with pytest.raises(TimeoutError, match="timed out"):
        server.install_cloudwatch_agent(
            instance_id="i-0123456789abcdef0",
            region="us-west-2",
            timeout=1,
        )


def test_install_cloudwatch_agent_does_not_retry_other_client_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeClient:
        def send_command(self, **kwargs: object) -> dict[str, object]:
            return {"Command": {"CommandId": "cmd-denied"}}

        def get_command_invocation(self, **kwargs: object) -> dict[str, str]:
            raise server.ClientError(
                {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
                "GetCommandInvocation",
            )

    class FakeSession:
        def client(self, name: str) -> FakeClient:
            assert name == "ssm"
            return FakeClient()

    monkeypatch.setattr(server.boto3, "Session", lambda **kwargs: FakeSession())
    monkeypatch.setattr(
        server.time,
        "sleep",
        lambda seconds: pytest.fail("non-transient errors must not be retried"),
    )

    with pytest.raises(server.ClientError) as error:
        server.install_cloudwatch_agent(
            instance_id="i-0123456789abcdef0",
            region="us-west-2",
        )

    assert error.value.response["Error"]["Code"] == "AccessDeniedException"
