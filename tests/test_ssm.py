from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from daylily_ec.aws.ssm import (
    HeadNodeTarget,
    SessionManagerPluginMissingError,
    SsmCommandFailedError,
    SsmInstanceUnavailableError,
    resolve_headnode_instance_id,
    require_session_manager_plugin,
    run_shell,
    wait_for_ssm_online,
    write_remote_text,
)


class TestRequireSessionManagerPlugin:
    @patch("daylily_ec.aws.ssm.shutil.which", return_value="/usr/local/bin/session-manager-plugin")
    def test_present(self, _mock_which):
        require_session_manager_plugin()

    @patch("daylily_ec.aws.ssm.shutil.which", return_value=None)
    def test_missing(self, _mock_which):
        with pytest.raises(SessionManagerPluginMissingError):
            require_session_manager_plugin()


class TestResolveHeadnodeInstanceId:
    @patch("daylily_ec.aws.ssm.subprocess.run")
    def test_resolves_headnode(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"instances":[{"nodeType":"HeadNode","instanceId":"i-abc123"}]}',
            stderr="",
        )

        result = resolve_headnode_instance_id("cluster-a", "us-west-2", profile="dev")

        assert result == HeadNodeTarget(
            cluster_name="cluster-a",
            region="us-west-2",
            instance_id="i-abc123",
        )

    @patch("daylily_ec.aws.ssm.subprocess.run")
    def test_missing_headnode_raises(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"instances":[]}',
            stderr="",
        )

        with pytest.raises(RuntimeError):
            resolve_headnode_instance_id("cluster-a", "us-west-2")


class TestWaitForSsmOnline:
    @patch("daylily_ec.aws.ssm.time.sleep", return_value=None)
    @patch("daylily_ec.aws.ssm.boto3.Session")
    def test_waits_until_online(self, mock_session_cls, _mock_sleep):
        client = MagicMock()
        client.describe_instance_information.side_effect = [
            {"InstanceInformationList": []},
            {"InstanceInformationList": [{"PingStatus": "Online"}]},
        ]
        mock_session_cls.return_value.client.return_value = client

        wait_for_ssm_online("i-abc123", "us-west-2", timeout=5, poll_interval=0)

        assert client.describe_instance_information.call_count == 2

    @patch("daylily_ec.aws.ssm.time.sleep", return_value=None)
    @patch("daylily_ec.aws.ssm.time.time", side_effect=[0, 0, 1, 4])
    @patch("daylily_ec.aws.ssm.boto3.Session")
    def test_times_out_when_instance_never_becomes_online(
        self,
        mock_session_cls,
        _mock_time,
        _mock_sleep,
    ):
        client = MagicMock()
        client.describe_instance_information.return_value = {"InstanceInformationList": []}
        mock_session_cls.return_value.client.return_value = client

        with pytest.raises(SsmInstanceUnavailableError):
            wait_for_ssm_online("i-abc123", "us-west-2", timeout=3, poll_interval=0)


class TestRunShell:
    @patch("daylily_ec.aws.ssm.boto3.Session")
    def test_success(self, mock_session_cls):
        client = MagicMock()
        client.send_command.return_value = {"Command": {"CommandId": "cmd-1"}}
        client.get_command_invocation.return_value = {
            "Status": "Success",
            "ResponseCode": 0,
            "StandardOutputContent": "ok\n",
            "StandardErrorContent": "",
        }
        mock_session_cls.return_value.client.return_value = client

        result = run_shell("i-abc123", "us-west-2", "echo hi", profile="dev")

        assert result.command_id == "cmd-1"
        assert result.stdout == "ok\n"
        sent = client.send_command.call_args.kwargs
        assert sent["DocumentName"] == "AWS-RunShellScript"
        assert "sudo -iu ubuntu bash" in sent["Parameters"]["commands"][0]

    @patch("daylily_ec.aws.ssm.boto3.Session")
    def test_failure_raises(self, mock_session_cls):
        client = MagicMock()
        client.send_command.return_value = {"Command": {"CommandId": "cmd-1"}}
        client.get_command_invocation.return_value = {
            "Status": "Failed",
            "ResponseCode": 1,
            "StandardOutputContent": "",
            "StandardErrorContent": "boom",
        }
        mock_session_cls.return_value.client.return_value = client

        with pytest.raises(SsmCommandFailedError):
            run_shell("i-abc123", "us-west-2", "false", profile="dev")

    @patch("daylily_ec.aws.ssm.time.sleep", return_value=None)
    @patch("daylily_ec.aws.ssm.time.time", side_effect=[0, 0, 5])
    @patch("daylily_ec.aws.ssm.boto3.Session")
    def test_pending_status_timeout_raises(
        self,
        mock_session_cls,
        _mock_time,
        _mock_sleep,
    ):
        client = MagicMock()
        client.send_command.return_value = {"Command": {"CommandId": "cmd-1"}}
        client.get_command_invocation.return_value = {
            "Status": "InProgress",
            "ResponseCode": -1,
            "StandardOutputContent": "",
            "StandardErrorContent": "",
        }
        mock_session_cls.return_value.client.return_value = client

        with pytest.raises(TimeoutError, match="did not complete"):
            run_shell("i-abc123", "us-west-2", "sleep 10", profile="dev", timeout=3, poll_interval=0)

    @patch("daylily_ec.aws.ssm.time.time", side_effect=[0, 5])
    @patch("daylily_ec.aws.ssm.boto3.Session")
    def test_invocation_missing_timeout_raises(self, mock_session_cls, _mock_time):
        class InvocationDoesNotExist(Exception):
            pass

        client = MagicMock()
        client.send_command.return_value = {"Command": {"CommandId": "cmd-1"}}
        client.exceptions = SimpleNamespace(InvocationDoesNotExist=InvocationDoesNotExist)
        client.get_command_invocation.side_effect = InvocationDoesNotExist()
        mock_session_cls.return_value.client.return_value = client

        with pytest.raises(TimeoutError, match="did not start"):
            run_shell("i-abc123", "us-west-2", "echo hi", profile="dev", timeout=3, poll_interval=0)


class TestWriteRemoteText:
    @patch("daylily_ec.aws.ssm.run_shell")
    def test_expands_home_path(self, mock_run_shell):
        mock_run_shell.return_value = MagicMock()

        write_remote_text(
            "i-abc123",
            "us-west-2",
            "~/.config/daylily/test.yaml",
            "hello: world\n",
            profile="dev",
        )

        script = mock_run_shell.call_args.args[2]
        assert "/home/ubuntu/.config/daylily/test.yaml" in script
