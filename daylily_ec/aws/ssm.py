"""AWS Systems Manager helpers for PEM-free headnode access and orchestration."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

PENDING_STATUSES = {"Pending", "InProgress", "Delayed"}
SUCCESS_STATUS = "Success"
DEFAULT_REMOTE_USER = "ubuntu"
EC2_REMOTE_USER = "ec2-user"
AUTO_REMOTE_USER = "auto"
SUPPORTED_REMOTE_USERS = (DEFAULT_REMOTE_USER, EC2_REMOTE_USER)
SUPPORTED_REMOTE_USER = DEFAULT_REMOTE_USER
SUPPORTED_SESSION_HOME = f"/home/{DEFAULT_REMOTE_USER}"
# AWS limits a Run Command document plus parameters to 97 KB.  The encoded
# transport wrapper adds substantial overhead, so retain room for its shell and
# document framing rather than attempting a request that AWS must reject.
MAX_RUN_COMMAND_PAYLOAD_BYTES = 80 * 1024
LARGE_PAYLOAD_CHUNK_BYTES = 24 * 1024
SOURCE_HEADNODE_STARTUP_FILES = (
    "set +e +u; "
    "for f in ~/.bash_profile ~/.bash_login ~/.profile; do "
    'if [[ -f "$f" ]]; then source "$f" || exit $?; break; fi; done; '
    "if [[ -f ~/.bashrc ]]; then source ~/.bashrc || exit $?; fi; "
    "set +e +u"
)
SUPPORTED_SESSION_SHELL_PROFILE = (
    f"cd {SUPPORTED_SESSION_HOME} && "
    "{ stty -ixon -ixoff 2>/dev/null || true; "
    f"exec bash --login --interactive -c {shlex.quote(SOURCE_HEADNODE_STARTUP_FILES + '; exec bash --interactive')}; }}"
)


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
        except json.JSONDecodeError:
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


def _remote_user_home(as_user: str) -> str:
    return f"/home/{as_user}"


def _session_shell_profile(as_user: str) -> str:
    return (
        f"cd {_remote_user_home(as_user)} && "
        "{ stty -ixon -ixoff 2>/dev/null || true; "
        f"exec bash --login --interactive -c {shlex.quote(SOURCE_HEADNODE_STARTUP_FILES + '; exec bash --interactive')}; }}"
    )


def _bash_login_interactive_source_bashrc_invocation(
    script_value: str,
    *,
    require_startup_success: bool = True,
) -> str:
    """Return a bash command that runs *script_value* in the required headnode context.

    ``script_value`` is a shell expression, normally ``"$tmp"`` from the
    transport wrapper.  Keep it out of environment variables and bash ``-c``
    positional arguments because ``sudo -i`` starts a login context that may
    reset environment or argument state before the final interactive bash sees
    it.  Instead, let the outer transport shell expand the already-created temp
    path directly into the inner command string.
    """

    startup = SOURCE_HEADNODE_STARTUP_FILES if require_startup_success else "set +e +u"
    bootstrap = f"{startup}; source "
    return " ".join(
        [
            "bash",
            "-ilc",
            f"{shlex.quote(bootstrap)}{script_value}",
        ]
    )


def _require_supported_remote_user(as_user: Optional[str]) -> str:
    if as_user not in SUPPORTED_REMOTE_USERS:
        supported = ", ".join(SUPPORTED_REMOTE_USERS)
        raise SsmError(f"Supported SSM commands must run as one of {supported}; got {as_user!r}.")
    return str(as_user)


def _remote_user_from_platform(platform_name: str, platform_version: str = "") -> str:
    haystack = f"{platform_name} {platform_version}".strip().lower()
    if "ubuntu" in haystack:
        return DEFAULT_REMOTE_USER
    if any(
        marker in haystack
        for marker in (
            "red hat",
            "rhel",
            "amazon linux",
            "almalinux",
            "alma linux",
            "rocky",
            "centos",
        )
    ):
        return EC2_REMOTE_USER
    raise SsmError(
        "Unable to determine supported SSM remote user from managed instance platform "
        f"metadata: PlatformName={platform_name!r}, PlatformVersion={platform_version!r}. "
        f"Pass as_user explicitly as one of {', '.join(SUPPORTED_REMOTE_USERS)}."
    )


def resolve_remote_user(
    instance_id: str,
    region: str,
    *,
    profile: Optional[str] = None,
    as_user: Optional[str] = AUTO_REMOTE_USER,
) -> str:
    """Resolve the remote login user for SSM Run Command.

    ``as_user="auto"`` is explicit platform-based detection. Unknown platforms
    fail hard instead of retrying or silently falling back.
    """
    if as_user != AUTO_REMOTE_USER:
        return _require_supported_remote_user(as_user)

    session = _build_boto_session(profile=profile, region=region)
    client = session.client("ssm")
    try:
        response = client.describe_instance_information(
            Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
        )
    except (BotoCoreError, ClientError) as exc:
        raise SsmError(
            f"Unable to query SSM managed instance platform for '{instance_id}': {exc}"
        ) from exc

    info_list = response.get("InstanceInformationList", []) or []
    if not info_list:
        raise SsmInstanceUnavailableError(
            f"Head node instance '{instance_id}' is not available in SSM for remote user detection."
        )
    info = info_list[0]
    return _remote_user_from_platform(
        str(info.get("PlatformName") or ""),
        str(info.get("PlatformVersion") or ""),
    )


def _payload_guard(as_user: str) -> str:
    return "\n".join(
        [
            'actual_user="$(id -un)"',
            f'if [ "$actual_user" != "{as_user}" ]; then',
            f'  echo "Daylily SSM payload must run as {as_user}; got $actual_user." >&2',
            "  exit 64",
            "fi",
        ]
    )


def _encode_script_payload(
    script: str,
    *,
    as_user: str,
    require_startup_success: bool = True,
) -> str:
    user = _require_supported_remote_user(as_user)
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    writer = (
        "import base64, os, pathlib; "
        "path = pathlib.Path(os.environ['DAYLILY_SSM_TMP']); "
        "path.write_text(base64.b64decode(os.environ['DAYLILY_SSM_B64']).decode('utf-8'), encoding='utf-8')"
    )
    script_env_value = '"$tmp"'
    runner = (
        f"sudo -iu {shlex.quote(user)} "
        f"{_bash_login_interactive_source_bashrc_invocation(script_env_value, require_startup_success=require_startup_success)}"
    )
    return "\n".join(
        [
            # AWS-RunShellScript uses /bin/sh for the transport wrapper on Ubuntu.
            # Keep the wrapper POSIX-safe and run the real payload under the
            # supported headnode shell contract: target user + bash login/
            # interactive semantics. Normal calls require explicit startup
            # success; the configure repair path reaches its payload after a
            # broken automatic login bootstrap so it can reinstall that bootstrap.
            "set +e +u",
            "tmp=$(mktemp /tmp/daylily-ssm-XXXXXX.sh)",
            'mktemp_rc="$?"',
            'if [ "$mktemp_rc" -ne 0 ]; then exit "$mktemp_rc"; fi',
            f"export DAYLILY_SSM_B64={shlex.quote(encoded)}",
            'export DAYLILY_SSM_TMP="$tmp"',
            f"python3 -c {shlex.quote(writer)}",
            'write_rc="$?"',
            'if [ "$write_rc" -ne 0 ]; then rm -f "$tmp"; exit "$write_rc"; fi',
            f'chown {shlex.quote(user)} "$tmp"',
            'chown_rc="$?"',
            'if [ "$chown_rc" -ne 0 ]; then rm -f "$tmp"; exit "$chown_rc"; fi',
            'chmod 700 "$tmp"',
            'chmod_rc="$?"',
            'if [ "$chmod_rc" -ne 0 ]; then rm -f "$tmp"; exit "$chmod_rc"; fi',
            runner,
            "rc=$?",
            'rm -f "$tmp"',
            "exit $rc",
        ]
    )


def _run_command_payload(
    instance_id: str,
    client: object,
    payload: str,
    *,
    timeout: Optional[int],
    poll_interval: int,
    comment: str,
) -> SsmCommandResult:
    """Send one already-encoded AWS-RunShellScript payload and await it."""

    response = start_bounded_command(
        client,
        instance_id=instance_id,
        document_name="AWS-RunShellScript",
        parameters={"commands": [payload]},
        timeout=timeout,
        comment=comment,
    )

    command_id = str(response["Command"]["CommandId"])
    deadline = None if timeout is None else time.time() + timeout
    while True:
        try:
            invocation = client.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id,
            )
        except client.exceptions.InvocationDoesNotExist:
            if deadline is not None and time.time() >= deadline:
                raise TimeoutError(f"SSM command '{command_id}' did not start within {timeout}s.")
            time.sleep(poll_interval)
            continue
        except (BotoCoreError, ClientError) as exc:
            raise SsmError(f"Unable to fetch SSM command invocation '{command_id}': {exc}") from exc

        status = str(invocation.get("Status") or "")
        if status in PENDING_STATUSES:
            if deadline is not None and time.time() >= deadline:
                raise TimeoutError(f"SSM command '{command_id}' did not complete within {timeout}s.")
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


def start_bounded_command(
    client: object,
    *,
    instance_id: str,
    document_name: str,
    parameters: dict[str, list[str]],
    timeout: Optional[int] = None,
    comment: str,
) -> dict[str, object]:
    """Start one SSM Run Command after enforcing DYEC's transport limit.

    All DYEC SSM Run Command requests must use this gateway.  Shell payloads
    are automatically staged by :func:`run_shell`; other SSM documents fail
    locally if their complete request would exceed the safe limit, rather than
    reaching AWS and failing with ``MaxDocumentSizeExceeded``.
    """

    send_kwargs: dict[str, object] = {
        "InstanceIds": [instance_id],
        "DocumentName": document_name,
        "Comment": comment,
        "Parameters": parameters,
    }
    if timeout is not None:
        send_kwargs["TimeoutSeconds"] = max(timeout, 30)
    request_bytes = len(
        json.dumps(send_kwargs, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    if request_bytes > MAX_RUN_COMMAND_PAYLOAD_BYTES:
        guidance = (
            "use run_shell so DYEC stages the content in verified bounded chunks"
            if document_name == "AWS-RunShellScript"
            else "reduce the document parameters or use a document-specific staged input"
        )
        raise SsmError(
            "Refusing oversized SSM Run Command request "
            f"({request_bytes} bytes; DYEC safety limit {MAX_RUN_COMMAND_PAYLOAD_BYTES}): {guidance}."
        )
    try:
        return client.send_command(**send_kwargs)
    except (BotoCoreError, ClientError) as exc:
        raise SsmError(f"Unable to start SSM Run Command on '{instance_id}': {exc}") from exc


def _run_large_script(
    instance_id: str,
    client: object,
    script: str,
    *,
    as_user: str,
    timeout: Optional[int],
    poll_interval: int,
    comment: str,
    require_startup_success: bool,
) -> SsmCommandResult:
    """Stage an oversized script in bounded SSM chunks, verify it, then run it.

    This is a transport change only: the final script still executes under the
    same supported interactive login shell as a normal ``run_shell`` request.
    """

    token = uuid.uuid4().hex
    remote_dir = f"/tmp/daylily-ssm-{token}"
    remote_script = f"{remote_dir}/payload.sh"
    expected_sha256 = hashlib.sha256(script.encode("utf-8")).hexdigest()

    def send_small(stage_script: str, stage_comment: str) -> SsmCommandResult:
        payload = _encode_script_payload(
            stage_script,
            as_user=as_user,
            require_startup_success=require_startup_success,
        )
        if len(payload.encode("utf-8")) > MAX_RUN_COMMAND_PAYLOAD_BYTES:
            raise SsmError("Internal error: large-payload staging command exceeds the SSM safety limit.")
        return _run_command_payload(
            instance_id,
            client,
            payload,
            timeout=timeout,
            poll_interval=poll_interval,
            comment=stage_comment,
        )

    try:
        send_small(
            "\n".join(
                [
                    "set -euo pipefail",
                    "umask 077",
                    f"mkdir -p {shlex.quote(remote_dir)}",
                    f": > {shlex.quote(remote_script)}",
                ]
            ),
            "Stage Daylily large payload",
        )
        raw = script.encode("utf-8")
        for offset in range(0, len(raw), LARGE_PAYLOAD_CHUNK_BYTES):
            chunk = base64.b64encode(raw[offset : offset + LARGE_PAYLOAD_CHUNK_BYTES]).decode("ascii")
            send_small(
                "\n".join(
                    [
                        "set -euo pipefail",
                        f"printf '%s' {shlex.quote(chunk)} | base64 --decode >> {shlex.quote(remote_script)}",
                    ]
                ),
                "Stage Daylily large payload chunk",
            )
        verify = send_small(
            "\n".join(
                [
                    "set -euo pipefail",
                    f"actual=$(sha256sum {shlex.quote(remote_script)} | awk '{{print $1}}')",
                    f"test \"$actual\" = {shlex.quote(expected_sha256)}",
                    'printf "__DAYLILY_SSM_PAYLOAD_SHA256__=%s\\n" "$actual"',
                ]
            ),
            "Verify Daylily large payload",
        )
        if f"__DAYLILY_SSM_PAYLOAD_SHA256__={expected_sha256}" not in verify.stdout:
            raise SsmError("Remote Daylily large-payload SHA-256 verification marker was not returned.")
        return send_small(
            "\n".join(
                [
                    "set -euo pipefail",
                    f"trap 'rm -rf {shlex.quote(remote_dir)}' EXIT",
                    f"bash {shlex.quote(remote_script)}",
                ]
            ),
            comment,
        )
    except Exception:
        try:
            send_small(f"rm -rf {shlex.quote(remote_dir)}", "Clean Daylily large payload")
        except Exception:
            logger.warning("Unable to clean failed large SSM payload staging at %s", remote_dir)
        raise
def run_shell(
    instance_id: str,
    region: str,
    script: str,
    *,
    profile: Optional[str] = None,
    as_user: Optional[str] = DEFAULT_REMOTE_USER,
    timeout: Optional[int] = 300,
    poll_interval: int = 3,
    comment: str = "Daylily remote command",
    require_startup_success: bool = True,
) -> SsmCommandResult:
    """Run *script* on an instance via SSM Run Command and return its result.

    ``require_startup_success=False`` is reserved for the explicit headnode
    configure repair path. Ordinary commands fail when managed startup fails.
    """
    resolved_user = resolve_remote_user(
        instance_id,
        region,
        profile=profile,
        as_user=as_user,
    )
    session = _build_boto_session(profile=profile, region=region)
    client = session.client("ssm")
    protected_script = "\n".join([_payload_guard(resolved_user), script])
    payload = _encode_script_payload(
        protected_script,
        as_user=resolved_user,
        require_startup_success=require_startup_success,
    )
    if len(payload.encode("utf-8")) > MAX_RUN_COMMAND_PAYLOAD_BYTES:
        return _run_large_script(
            instance_id,
            client,
            protected_script,
            as_user=resolved_user,
            timeout=timeout,
            poll_interval=poll_interval,
            comment=comment,
            require_startup_success=require_startup_success,
        )
    return _run_command_payload(
        instance_id,
        client,
        payload,
        timeout=timeout,
        poll_interval=poll_interval,
        comment=comment,
    )


def write_remote_text(
    instance_id: str,
    region: str,
    remote_path: str,
    content: str,
    *,
    profile: Optional[str] = None,
    as_user: str = DEFAULT_REMOTE_USER,
    require_startup_success: bool = True,
) -> SsmCommandResult:
    """Write text content to *remote_path* via bounded SSM transport.

    The encoded content is supplied to a small Python writer on standard input.
    Large scripts are therefore handled by :func:`run_shell`'s existing
    chunked, SHA-verified staging path without placing one oversized value in
    the environment passed to ``execve``.
    """
    resolved_user = resolve_remote_user(
        instance_id,
        region,
        profile=profile,
        as_user=as_user,
    )
    target_path = _normalize_remote_path(remote_path, user=resolved_user)
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    heredoc_marker = f"__DAYLILY_REMOTE_TEXT_{uuid.uuid4().hex}__"
    script = "\n".join(
        [
            "set -euo pipefail",
            "python3 -c "
            + shlex.quote(
                "import base64, pathlib, sys; "
                "path = pathlib.Path(sys.argv[1]); "
                "path.parent.mkdir(parents=True, exist_ok=True); "
                "path.write_bytes(base64.b64decode(sys.stdin.buffer.read()))"
            )
            + f" {shlex.quote(target_path)} <<'{heredoc_marker}'",
            encoded,
            heredoc_marker,
        ]
    )
    return run_shell(
        instance_id,
        region,
        script,
        profile=profile,
        as_user=resolved_user,
        require_startup_success=require_startup_success,
        comment=f"Write {target_path}",
    )


def _require_session_preferences(
    region: str,
    *,
    profile: Optional[str] = None,
    as_user: str = DEFAULT_REMOTE_USER,
) -> None:
    as_user = _require_supported_remote_user(as_user)
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
            f"Unable to read Session Manager preferences for 'SSM-SessionManagerRunShell': {detail}"
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
    if inputs.get("runAsEnabled") is not True or inputs.get("runAsDefaultUser") != as_user:
        raise SsmError(
            f"Session Manager must be configured to run shell sessions as {as_user} "
            "via SSM-SessionManagerRunShell."
        )
    login_interactive_ok = (
        "bash -il" in linux_shell_profile
        or "bash -li" in linux_shell_profile
        or ("--login" in linux_shell_profile and "--interactive" in linux_shell_profile)
    )
    bashrc_ok = ".bashrc" in linux_shell_profile
    if not linux_shell_profile or not login_interactive_ok or not bashrc_ok:
        raise SsmError(
            f"Session Manager must source the {as_user} login/interactive bash shell "
            "and ~/.bashrc via "
            "SSM-SessionManagerRunShell shellProfile.linux."
        )
    if not _shell_profile_enters_user_home(linux_shell_profile, as_user=as_user):
        expected_profile = _session_shell_profile(as_user)
        raise SsmError(
            f"Session Manager must cd to {_remote_user_home(as_user)} before starting the "
            f"{as_user} login shell "
            "via SSM-SessionManagerRunShell shellProfile.linux. Expected a shell profile "
            f"like: {expected_profile!r}."
        )


def _shell_profile_enters_user_home(shell_profile: str, *, as_user: str) -> bool:
    normalized = shell_profile.replace('"', "").replace("'", "")
    return any(
        marker in normalized
        for marker in (
            f"cd {_remote_user_home(as_user)}",
            "cd ~",
            "cd $HOME",
            "cd ${HOME}",
        )
    )


def ensure_ubuntu_session_preferences(
    region: str,
    *,
    profile: Optional[str] = None,
) -> None:
    """Validate that Session Manager shell sessions land in the ubuntu login shell."""
    ensure_session_preferences(region, profile=profile, as_user=DEFAULT_REMOTE_USER)


def ensure_session_preferences(
    region: str,
    *,
    profile: Optional[str] = None,
    as_user: str = DEFAULT_REMOTE_USER,
) -> None:
    """Validate that Session Manager shell sessions land in a supported login shell."""
    _require_session_preferences(region, profile=profile, as_user=as_user)


def _disable_local_software_flow_control() -> None:
    """Let interactive tools receive Ctrl-S/Ctrl-Q through the local terminal."""
    if not os.isatty(0):
        return
    try:
        result = subprocess.run(
            ["stty", "-ixon", "-ixoff"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SsmError("stty not found on PATH; unable to prepare local terminal.") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise SsmError(f"Unable to disable local terminal software flow control: {detail}")


def _start_local_software_flow_control_guard() -> subprocess.Popen[str] | None:
    """Keep local XON/XOFF disabled while Session Manager initializes the PTY."""
    if not os.isatty(0):
        return None
    script = (
        "import os, subprocess, sys, time; "
        "parent = int(sys.argv[1]); "
        "cmd = ['stty', '-ixon', '-ixoff']; "
        "devnull = subprocess.DEVNULL; "
        "\nwhile True:\n"
        "    try:\n"
        "        os.kill(parent, 0)\n"
        "    except OSError:\n"
        "        break\n"
        "    try:\n"
        "        with open('/dev/tty', 'rb', buffering=0) as tty:\n"
        "            subprocess.run(cmd, stdin=tty, stdout=devnull, stderr=devnull)\n"
        "    except Exception:\n"
        "        pass\n"
        "    time.sleep(0.1)\n"
    )
    return subprocess.Popen(
        [sys.executable, "-c", script, str(os.getpid())],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def start_session(
    instance_id: str,
    region: str,
    *,
    profile: Optional[str] = None,
    as_user: str = AUTO_REMOTE_USER,
    replace_process: bool = False,
) -> int:
    """Start an interactive Session Manager shell."""
    as_user = resolve_remote_user(
        instance_id,
        region,
        profile=profile,
        as_user=as_user,
    )
    require_session_manager_plugin()
    ensure_session_preferences(region, profile=profile, as_user=as_user)
    _disable_local_software_flow_control()
    flow_control_guard = _start_local_software_flow_control_guard()
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
    env = _build_env(profile=profile, region=region)
    if replace_process:
        try:
            os.execvpe(cmd[0], cmd, env)
        except FileNotFoundError as exc:
            if flow_control_guard is not None:
                flow_control_guard.terminate()
            raise SsmError("aws CLI not found on PATH.") from exc
        except OSError as exc:
            if flow_control_guard is not None:
                flow_control_guard.terminate()
            raise SsmError(f"Unable to start Session Manager session: {exc}") from exc
    try:
        result = subprocess.run(cmd, env=env)
        return int(result.returncode)
    finally:
        if flow_control_guard is not None:
            flow_control_guard.terminate()
            try:
                flow_control_guard.wait(timeout=2)
            except subprocess.TimeoutExpired:
                flow_control_guard.kill()
