"""AWS Systems Manager helpers for PEM-free headnode access and orchestration."""

from __future__ import annotations

import base64
import json
import logging
import os
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

PENDING_STATUSES = {"Pending", "InProgress", "Delayed"}
SUCCESS_STATUS = "Success"
SUPPORTED_REMOTE_USER = "ubuntu"


class SsmError(RuntimeError):
    """Base class for SSM-related failures."""


class SessionManagerPluginMissingError(SsmError):
    """Raised when the local Session Manager plugin is not installed."""


class SsmInstanceUnavailableError(SsmError):
    """Raised when the target instance is not managed by SSM."""


class SsmCommandFailedError(SsmError):
    """Raised when an SSM Run Command invocation fails."""

    def __init__(self, message: str, result: "SsmCommandResult") -> None:
        super().__init__(message)
        self.result = result


@dataclass(frozen=True)
class HeadNodeTarget:
    """Resolved headnode target for Session Manager operations."""

    cluster_name: str
    region: str
    instance_id: str


@dataclass(frozen=True)
class SsmCommandResult:
    """Normalized result for an SSM Run Command invocation."""

    command_id: str
    instance_id: str
    status: str
    response_code: int
    stdout: str
    stderr: str


def _build_env(*, profile: Optional[str] = None, region: Optional[str] = None) -> Dict[str, str]:
    env = dict(os.environ)
    if profile:
        env["AWS_PROFILE"] = profile
    if region:
        env["AWS_REGION"] = region
        env.setdefault("AWS_DEFAULT_REGION", region)
    return env


def _build_boto_session(*, profile: Optional[str], region: str):
    if profile:
        return boto3.Session(profile_name=profile, region_name=region)
    return boto3.Session(region_name=region)


def require_session_manager_plugin() -> None:
    """Ensure the local Session Manager plugin is installed."""
    if shutil.which("session-manager-plugin"):
        return
    raise SessionManagerPluginMissingError(
        "session-manager-plugin is required for interactive SSM sessions."
    )


def resolve_headnode_instance_id(
    cluster_name: str,
    region: str,
    *,
    profile: Optional[str] = None,
) -> HeadNodeTarget:
    """Resolve the headnode EC2 instance id for a ParallelCluster cluster."""
    commands = [
        [
            "pcluster",
            "describe-cluster",
            "--cluster-name",
            cluster_name,
            "--region",
            region,
        ],
        [
            "pcluster",
            "describe-cluster-instances",
            "--cluster-name",
            cluster_name,
            "--region",
            region,
        ],
    ]
    env = _build_env(profile=profile, region=region)
    errors: list[str] = []

    for cmd in commands:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
            )
        except FileNotFoundError as exc:
            raise SsmError("pcluster CLI not found on PATH.") from exc

        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
            errors.append(detail)
            continue

        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            errors.append(f"Unable to parse {' '.join(cmd[1:3])} output.")
            continue

        head_node = payload.get("headNode") or {}
        instance_id = head_node.get("instanceId")
        if instance_id:
            return HeadNodeTarget(
                cluster_name=cluster_name,
                region=region,
                instance_id=str(instance_id),
            )

        for instance in payload.get("instances", []) or []:
            if instance.get("nodeType") == "HeadNode" and instance.get("instanceId"):
                return HeadNodeTarget(
                    cluster_name=cluster_name,
                    region=region,
                    instance_id=str(instance["instanceId"]),
                )

    if errors:
        raise SsmError(
            f"Unable to resolve head node instance for cluster '{cluster_name}': {errors[-1]}"
        )
    raise SsmError(f"Head node instance not found for cluster '{cluster_name}'.")


def wait_for_ssm_online(
    instance_id: str,
    region: str,
    *,
    profile: Optional[str] = None,
    timeout: int = 600,
    poll_interval: int = 10,
) -> None:
    """Wait until *instance_id* appears as an online SSM managed instance."""
    session = _build_boto_session(profile=profile, region=region)
    client = session.client("ssm")
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            response = client.describe_instance_information(
                Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
            )
        except (BotoCoreError, ClientError) as exc:
            raise SsmError(
                f"Unable to query SSM managed instance state for '{instance_id}': {exc}"
            ) from exc

        info_list = response.get("InstanceInformationList", []) or []
        if info_list:
            ping_status = str(info_list[0].get("PingStatus") or "")
            if ping_status == "Online":
                return

        time.sleep(poll_interval)

    raise SsmInstanceUnavailableError(
        f"Head node instance '{instance_id}' did not become available in SSM within {timeout}s."
    )


def _normalize_remote_path(path: str, *, user: str) -> str:
    if path == "~":
        return f"/home/{user}"
    if path.startswith("~/"):
        return str(PurePosixPath("/home") / user / path[2:])
    return path


def _require_ubuntu_user(as_user: Optional[str]) -> str:
    if as_user != SUPPORTED_REMOTE_USER:
        raise SsmError(
            "Supported SSM commands must run as ubuntu; "
            f"got {as_user!r}."
        )
    return SUPPORTED_REMOTE_USER


def _ubuntu_payload_guard() -> str:
    return "\n".join(
        [
            'actual_user="$(id -un)"',
            f'if [ "$actual_user" != "{SUPPORTED_REMOTE_USER}" ]; then',
            '  echo "Daylily SSM payload must run as ubuntu; got $actual_user." >&2',
            "  exit 64",
            "fi",
        ]
    )


def _encode_script_payload(script: str, *, as_user: Optional[str]) -> str:
    user = _require_ubuntu_user(as_user)
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    writer = (
        "import base64, os, pathlib; "
        "path = pathlib.Path(os.environ['DAYLILY_SSM_TMP']); "
        "path.write_text(base64.b64decode(os.environ['DAYLILY_SSM_B64']).decode('utf-8'), encoding='utf-8')"
    )
    runner = f"sudo -iu {shlex.quote(user)} bash \"$tmp\""
    return "\n".join(
        [
            # AWS-RunShellScript uses /bin/sh for the transport wrapper on Ubuntu.
            # Keep the wrapper POSIX-safe and run the real payload under bash as ubuntu.
            "set -eu",
            "tmp=$(mktemp /tmp/daylily-ssm-XXXXXX.sh)",
            f"export DAYLILY_SSM_B64={shlex.quote(encoded)}",
            'export DAYLILY_SSM_TMP="$tmp"',
            f"python3 -c {shlex.quote(writer)}",
            f"chown {shlex.quote(user)} \"$tmp\"",
            "chmod 700 \"$tmp\"",
            "set +e",
            runner,
            "rc=$?",
            "set -e",
            "rm -f \"$tmp\"",
            "exit $rc",
        ]
    )


def run_shell(
    instance_id: str,
    region: str,
    script: str,
    *,
    profile: Optional[str] = None,
    as_user: Optional[str] = "ubuntu",
    timeout: int = 300,
    poll_interval: int = 3,
    comment: str = "Daylily remote command",
) -> SsmCommandResult:
    """Run *script* on an instance via SSM Run Command and return its result."""
    _require_ubuntu_user(as_user)
    session = _build_boto_session(profile=profile, region=region)
    client = session.client("ssm")
    payload = _encode_script_payload(
        "\n".join([_ubuntu_payload_guard(), script]),
        as_user=as_user,
    )

    try:
        response = client.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Comment=comment,
            Parameters={"commands": [payload]},
            TimeoutSeconds=max(timeout, 30),
        )
    except (BotoCoreError, ClientError) as exc:
        raise SsmError(f"Unable to start SSM Run Command on '{instance_id}': {exc}") from exc

    command_id = str(response["Command"]["CommandId"])
    deadline = time.time() + timeout

    while True:
        try:
            invocation = client.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id,
            )
        except client.exceptions.InvocationDoesNotExist:
            if time.time() >= deadline:
                raise TimeoutError(
                    f"SSM command '{command_id}' did not start within {timeout}s."
                )
            time.sleep(poll_interval)
            continue
        except (BotoCoreError, ClientError) as exc:
            raise SsmError(
                f"Unable to fetch SSM command invocation '{command_id}': {exc}"
            ) from exc

        status = str(invocation.get("Status") or "")
        if status in PENDING_STATUSES:
            if time.time() >= deadline:
                raise TimeoutError(
                    f"SSM command '{command_id}' did not complete within {timeout}s."
                )
            time.sleep(poll_interval)
            continue

        result = SsmCommandResult(
            command_id=command_id,
            instance_id=instance_id,
            status=status,
            response_code=int(invocation.get("ResponseCode") or 0),
            stdout=str(invocation.get("StandardOutputContent") or ""),
            stderr=str(invocation.get("StandardErrorContent") or ""),
        )
        if status != SUCCESS_STATUS or result.response_code != 0:
            raise SsmCommandFailedError(
                f"SSM command '{command_id}' failed with status={status} rc={result.response_code}",
                result,
            )
        return result


def write_remote_text(
    instance_id: str,
    region: str,
    remote_path: str,
    content: str,
    *,
    profile: Optional[str] = None,
    as_user: str = "ubuntu",
) -> SsmCommandResult:
    """Write small text content to *remote_path* via SSM Run Command."""
    as_user = _require_ubuntu_user(as_user)
    target_path = _normalize_remote_path(remote_path, user=as_user)
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    script = "\n".join(
        [
            "set -euo pipefail",
            f"export DAYLILY_REMOTE_B64={shlex.quote(encoded)}",
            f"export DAYLILY_REMOTE_PATH={shlex.quote(target_path)}",
            "python3 -c "
            + shlex.quote(
                "import base64, os, pathlib; "
                "path = pathlib.Path(os.environ['DAYLILY_REMOTE_PATH']); "
                "path.parent.mkdir(parents=True, exist_ok=True); "
                "path.write_text(base64.b64decode(os.environ['DAYLILY_REMOTE_B64']).decode('utf-8'), encoding='utf-8')"
            ),
        ]
    )
    return run_shell(
        instance_id,
        region,
        script,
        profile=profile,
        as_user=as_user,
        comment=f"Write {target_path}",
    )


def _require_ubuntu_session_preferences(
    region: str,
    *,
    profile: Optional[str] = None,
) -> None:
    cmd = [
        "aws",
        "ssm",
        "get-document",
        "--name",
        "SSM-SessionManagerRunShell",
        "--document-format",
        "JSON",
        "--query",
        "Content",
        "--output",
        "text",
        "--region",
        region,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=_build_env(profile=profile, region=region),
        )
    except FileNotFoundError as exc:
        raise SsmError("aws CLI not found on PATH.") from exc

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise SsmError(
            "Unable to read Session Manager preferences for 'SSM-SessionManagerRunShell': "
            f"{detail}"
        )

    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise SsmError(
            "Unable to parse Session Manager preferences for 'SSM-SessionManagerRunShell'."
        ) from exc

    inputs = payload.get("inputs", {}) if isinstance(payload, dict) else {}
    shell_profile = inputs.get("shellProfile", {}) if isinstance(inputs, dict) else {}
    linux_shell_profile = ""
    if isinstance(shell_profile, dict):
        linux_shell_profile = str(shell_profile.get("linux") or "")
    if inputs.get("runAsEnabled") is not True or inputs.get("runAsDefaultUser") != SUPPORTED_REMOTE_USER:
        raise SsmError(
            "Session Manager must be configured to run shell sessions as ubuntu "
            "via SSM-SessionManagerRunShell."
        )
    if not linux_shell_profile or (
        "bash -l" not in linux_shell_profile
        and ".bash_profile" not in linux_shell_profile
        and "daylily-headnode-bootstrap.sh" not in linux_shell_profile
    ):
        raise SsmError(
            "Session Manager must source the ubuntu login shell via "
            "SSM-SessionManagerRunShell shellProfile.linux."
        )


def ensure_ubuntu_session_preferences(
    region: str,
    *,
    profile: Optional[str] = None,
) -> None:
    """Validate that Session Manager shell sessions land in the ubuntu login shell."""
    _require_ubuntu_session_preferences(region, profile=profile)


def start_session(
    instance_id: str,
    region: str,
    *,
    profile: Optional[str] = None,
) -> int:
    """Start an interactive Session Manager shell."""
    require_session_manager_plugin()
    ensure_ubuntu_session_preferences(region, profile=profile)
    cmd = [
        "aws",
        "ssm",
        "start-session",
        "--region",
        region,
        "--target",
        instance_id,
        "--document-name",
        "SSM-SessionManagerRunShell",
    ]
    result = subprocess.run(cmd, env=_build_env(profile=profile, region=region))
    return int(result.returncode)
