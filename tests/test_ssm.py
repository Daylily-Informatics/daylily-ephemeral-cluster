from __future__ import annotations

import base64
import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from daylily_ec.aws.ssm import (
    HeadNodeTarget,
    SessionManagerPluginMissingError,
    SsmCommandFailedError,
    SsmInstanceUnavailableError,
    SsmError,
    resolve_headnode_instance_id,
    require_session_manager_plugin,
    run_shell,
    start_session,
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
            stdout='{"headNode":{"instanceId":"i-abc123"}}',
            stderr="/Users/jmajor/miniconda3/envs/DAY-EC/lib/python3.11/site-packages/pcluster/api/controllers/common.py:20: UserWarning: pkg_resources is deprecated as an API.\n",
        )

        result = resolve_headnode_instance_id("cluster-a", "us-west-2", profile="dev")

        assert result == HeadNodeTarget(
            cluster_name="cluster-a",
            region="us-west-2",
            instance_id="i-abc123",
        )

    @patch("daylily_ec.aws.ssm.subprocess.run")
    def test_falls_back_to_describe_cluster_instances(self, mock_run):
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='{"headNode":{}}',
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='{"instances":[{"nodeType":"HeadNode","instanceId":"i-abc123"}]}',
                stderr="",
            ),
        ]

        result = resolve_headnode_instance_id("cluster-a", "us-west-2", profile="dev")

        assert result.instance_id == "i-abc123"
        assert mock_run.call_count == 2

    @patch("daylily_ec.aws.ssm.subprocess.run")
    def test_missing_headnode_raises(self, mock_run):
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='{"headNode":{}}',
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='{"instances":[]}',
                stderr="",
            ),
        ]

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

        with pytest.raises(SsmInstanceUnavailableError, match="did not become available in SSM"):
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
        assert "chown ubuntu \"$tmp\"" in sent["Parameters"]["commands"][0]
        assert "sudo -iu ubuntu bash -l \"$tmp\"" in sent["Parameters"]["commands"][0]
        assert sent["Parameters"]["commands"][0].startswith("set -eu\n")
        encoded = sent["Parameters"]["commands"][0].split("DAYLILY_SSM_B64=")[1].split("\n", 1)[0]
        decoded = base64.b64decode(encoded).decode("utf-8")
        assert "Daylily SSM payload must run as ubuntu" in decoded
        assert 'if [ "$actual_user" != "ubuntu" ]; then' in decoded

    @patch("daylily_ec.aws.ssm.time.sleep", return_value=None)
    @patch("daylily_ec.aws.ssm.boto3.Session")
    def test_no_timeout_omits_send_command_timeout_and_waits_until_success(
        self,
        mock_session_cls,
        _mock_sleep,
    ):
        client = MagicMock()
        client.send_command.return_value = {"Command": {"CommandId": "cmd-1"}}
        client.get_command_invocation.side_effect = [
            {
                "Status": "InProgress",
                "ResponseCode": -1,
                "StandardOutputContent": "",
                "StandardErrorContent": "",
            },
            {
                "Status": "Success",
                "ResponseCode": 0,
                "StandardOutputContent": "done\n",
                "StandardErrorContent": "",
            },
        ]
        mock_session_cls.return_value.client.return_value = client

        result = run_shell(
            "i-abc123",
            "us-west-2",
            "sleep 900",
            profile="dev",
            timeout=None,
            poll_interval=0,
        )

        assert result.command_id == "cmd-1"
        assert result.stdout == "done\n"
        assert client.get_command_invocation.call_count == 2
        sent = client.send_command.call_args.kwargs
        assert "TimeoutSeconds" not in sent

    @pytest.mark.parametrize("as_user", [None, "root", "ssm-user"])
    @patch("daylily_ec.aws.ssm.boto3.Session")
    def test_rejects_non_ubuntu_users(self, mock_session_cls, as_user):
        with pytest.raises(SsmError, match="must run as ubuntu"):
            run_shell("i-abc123", "us-west-2", "echo hi", profile="dev", as_user=as_user)
        mock_session_cls.assert_not_called()

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
    @pytest.mark.parametrize("as_user", [None, "root", "ssm-user"])
    @patch("daylily_ec.aws.ssm.run_shell")
    def test_rejects_non_ubuntu_users(self, mock_run_shell, as_user):
        with pytest.raises(SsmError, match="must run as ubuntu"):
            write_remote_text(
                "i-abc123",
                "us-west-2",
                "~/test.txt",
                "hello\n",
                profile="dev",
                as_user=as_user,
            )
        mock_run_shell.assert_not_called()

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


class TestStartSession:
    @patch("daylily_ec.aws.ssm.require_session_manager_plugin")
    @patch("daylily_ec.aws.ssm.subprocess.run")
    def test_validates_session_manager_run_as_ubuntu_and_starts_session(
        self,
        mock_run,
        _mock_require_plugin,
    ):
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='{"inputs":{"runAsEnabled":true,"runAsDefaultUser":"ubuntu","shellProfile":{"linux":"exec bash -l"}}}',
                stderr="",
            ),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        ]

        rc = start_session("i-abc123", "us-west-2", profile="dev")

        assert rc == 0
        assert mock_run.call_count == 2
        assert mock_run.call_args_list[0].args[0][:5] == [
            "aws",
            "ssm",
            "get-document",
            "--name",
            "SSM-SessionManagerRunShell",
        ]
        assert mock_run.call_args_list[1].args[0] == [
            "aws",
            "ssm",
            "start-session",
            "--region",
            "us-west-2",
            "--target",
            "i-abc123",
            "--document-name",
            "SSM-SessionManagerRunShell",
        ]

    @patch("daylily_ec.aws.ssm.require_session_manager_plugin")
    @patch("daylily_ec.aws.ssm.subprocess.run")
    def test_rejects_session_manager_preferences_without_ubuntu_run_as(
        self,
        mock_run,
        _mock_require_plugin,
    ):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"inputs":{"runAsEnabled":false,"runAsDefaultUser":"ssm-user"}}',
            stderr="",
        )

        with pytest.raises(SsmError, match="run shell sessions as ubuntu"):
            start_session("i-abc123", "us-west-2", profile="dev")

    @patch("daylily_ec.aws.ssm.require_session_manager_plugin")
    @patch("daylily_ec.aws.ssm.subprocess.run")
    def test_rejects_session_manager_preferences_without_login_shell_profile(
        self,
        mock_run,
        _mock_require_plugin,
    ):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"inputs":{"runAsEnabled":true,"runAsDefaultUser":"ubuntu","shellProfile":{"linux":"pwd"}}}',
            stderr="",
        )

        with pytest.raises(SsmError, match="source the ubuntu login shell"):
            start_session("i-abc123", "us-west-2", profile="dev")
