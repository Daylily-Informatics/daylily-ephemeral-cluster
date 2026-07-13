"""Install and validate the dedicated Sentieon license-server runtime."""

from __future__ import annotations

import argparse
import base64
import json
import shlex
import sys
import time
from dataclasses import dataclass
from typing import Sequence

import boto3
from botocore.exceptions import ClientError

from daylily_ec.aws.ssm import run_shell

RUNTIME_VERSION = "202503.03"
RUNTIME_ROOT = f"/opt/sentieon/{RUNTIME_VERSION}"
RUNTIME_BUCKET = "lsmc-dayoa-references-usw2"
BACKEND_FQDN = "usw2d-01.sentieon.lsmc.bio"
SERVICE_FQDN = "license.sentieon.lsmc.bio"
SERVICE_PORT = 8990
PRIVATE_IP = "10.0.0.205"
CLOUDWATCH_AGENT_VERSION = "1.300069.0b1529"
CLOUDWATCH_LOG_GROUP = "/sentieon/licsrvr/LicsrvrLog"
CLOUDWATCH_PACKAGE_NAME = "AmazonCloudWatchAgent"
_SSM_PENDING_STATUSES = {"Pending", "InProgress", "Delayed"}


@dataclass(frozen=True)
class RuntimeObject:
    """One exact object required by the minimal license-server runtime."""

    relative_path: str
    sha256: str
    mode: int

    @property
    def s3_uri(self) -> str:
        return (
            f"s3://{RUNTIME_BUCKET}/runtime_assets/cached_envs/"
            f"sentieon-genomics-{RUNTIME_VERSION}/{self.relative_path}"
        )


RUNTIME_OBJECTS = (
    RuntimeObject(
        "bin/sentieon",
        "6630a9a8e97baf2c16f9c7158eaefdda589d72d2fcbc3f42a76d26d572e0c674",
        0o755,
    ),
    RuntimeObject(
        "share/funcs",
        "2d4dbf04164a3fcef0256775ca0272d8e2bacc054aa187c69a820d9d4b96c5a2",
        0o644,
    ),
    RuntimeObject(
        "libexec/licsrvr",
        "dbc62136fe87486bbd124297cecfc9c51bbabfccc747ce1f6e5936e9976a8fbd",
        0o755,
    ),
    RuntimeObject(
        "libexec/licclnt",
        "1eb02fd2b7744e5e6a557a6d10b742844cd57ebf6fdbf9b151ddf1867a0f7b18",
        0o755,
    ),
)

SYSTEMD_UNIT = """[Unit]
Description=Sentieon dedicated license server
Documentation=https://support.sentieon.com/docs/usages/licsrvr/licsrvr/
Wants=network-online.target
After=network-online.target
ConditionPathIsExecutable=/opt/sentieon/202503.03/bin/sentieon
ConditionPathIsReadWrite=/var/log/sentieon
ConditionPathExists=/etc/sentieon/license.lic

[Service]
Type=forking
User=sentieon
Group=sentieon
UMask=0027
ExecStartPre=/usr/bin/test -r /etc/sentieon/license.lic
ExecStart=/opt/sentieon/202503.03/bin/sentieon licsrvr --start --thread_count 4 --log /var/log/sentieon/licsrvr.log /etc/sentieon/license.lic
ExecStop=/opt/sentieon/202503.03/bin/sentieon licsrvr --stop /etc/sentieon/license.lic
Restart=on-failure
RestartSec=5s
TimeoutStartSec=90s
TimeoutStopSec=90s
LimitNOFILE=262144
NoNewPrivileges=true
PrivateDevices=true
PrivateTmp=true
ProtectClock=true
ProtectControlGroups=true
ProtectHome=true
ProtectHostname=true
ProtectKernelLogs=true
ProtectKernelModules=true
ProtectKernelTunables=true
ProtectSystem=strict
ReadOnlyPaths=/opt/sentieon/202503.03 /etc/sentieon
ReadWritePaths=/var/log/sentieon /var/lib/sentieon-license-server
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
RestrictNamespaces=true
RestrictRealtime=true
RestrictSUIDSGID=true
LockPersonality=true
SystemCallArchitectures=native

[Install]
WantedBy=multi-user.target
"""


def install_license_server(
    *,
    instance_id: str,
    region: str,
    profile: str | None = None,
) -> None:
    """Install the exact runtime and unit without starting or restarting it."""

    result = run_shell(
        instance_id,
        region,
        _install_script(),
        profile=profile,
        as_user="ubuntu",
        timeout=600,
        comment="Install pinned Sentieon license-server runtime",
    )
    if result.stdout.strip() != f"SENTIEON_LICENSE_SERVER_INSTALLED\t{RUNTIME_VERSION}":
        raise RuntimeError("Sentieon license-server installation returned unexpected output.")


def start_license_server(
    *,
    instance_id: str,
    region: str,
    profile: str | None = None,
) -> None:
    """Start the installed service without restarting an already-active service."""

    _run_service_action(
        action="start",
        instance_id=instance_id,
        region=region,
        profile=profile,
    )


def restart_license_server(
    *,
    instance_id: str,
    region: str,
    profile: str | None = None,
    approve_restart: bool = False,
) -> None:
    """Restart the service only after an explicit interruption acknowledgement."""

    if not approve_restart:
        raise ValueError("restart requires --approve-restart")
    _run_service_action(
        action="restart",
        instance_id=instance_id,
        region=region,
        profile=profile,
    )


def validate_license_server(
    *,
    instance_id: str,
    region: str,
    profile: str | None = None,
) -> None:
    """Validate the active service, DNS, listener, and both supported endpoints."""

    _run_service_action(
        action="validate",
        instance_id=instance_id,
        region=region,
        profile=profile,
    )


def _run_service_action(
    *,
    action: str,
    instance_id: str,
    region: str,
    profile: str | None,
) -> None:
    result = run_shell(
        instance_id,
        region,
        _service_action_script(action),
        profile=profile,
        as_user="ubuntu",
        timeout=180,
        comment=f"Sentieon license-server {action}",
    )
    expected = f"SENTIEON_LICENSE_SERVER_{action.upper()}_OK"
    if result.stdout.strip() != expected:
        raise RuntimeError(f"Sentieon license-server {action} returned unexpected output.")


def install_cloudwatch_agent(
    *,
    instance_id: str,
    region: str,
    profile: str | None = None,
    timeout: int = 600,
) -> None:
    """Install the exact CloudWatch Agent build through SSM Distributor."""

    session = (
        boto3.Session(profile_name=profile, region_name=region)
        if profile
        else boto3.Session(region_name=region)
    )
    client = session.client("ssm")
    response = client.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-ConfigureAWSPackage",
        Parameters={
            "action": ["Install"],
            "installationType": ["Uninstall and reinstall"],
            "name": [CLOUDWATCH_PACKAGE_NAME],
            "version": [CLOUDWATCH_AGENT_VERSION],
        },
        TimeoutSeconds=timeout,
        Comment="Install pinned CloudWatch Agent for Sentieon license server",
    )
    command_id = str(response["Command"]["CommandId"])
    deadline = time.monotonic() + timeout
    while True:
        try:
            invocation = client.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id,
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "InvocationDoesNotExist":
                raise
            if time.monotonic() >= deadline:
                raise TimeoutError("Pinned CloudWatch Agent installation timed out.") from exc
            time.sleep(3)
            continue
        status = str(invocation.get("Status") or "")
        if status == "Success":
            break
        if status not in _SSM_PENDING_STATUSES:
            raise RuntimeError(
                "Pinned CloudWatch Agent installation failed with SSM status "
                f"{status or 'unknown'}."
            )
        if time.monotonic() >= deadline:
            raise TimeoutError("Pinned CloudWatch Agent installation timed out.")
        time.sleep(3)

    result = run_shell(
        instance_id,
        region,
        _cloudwatch_version_script(),
        profile=profile,
        as_user="ubuntu",
        timeout=60,
        comment="Validate pinned CloudWatch Agent version",
    )
    if result.stdout.strip() != f"SENTIEON_CLOUDWATCH_AGENT_READY\t{CLOUDWATCH_AGENT_VERSION}":
        raise RuntimeError("Pinned CloudWatch Agent validation returned unexpected output.")


def configure_cloudwatch_logging(
    *,
    instance_id: str,
    region: str,
    profile: str | None = None,
) -> None:
    """Configure an already-installed pinned CloudWatch agent for the server log."""

    result = run_shell(
        instance_id,
        region,
        _cloudwatch_script(),
        profile=profile,
        as_user="ubuntu",
        timeout=300,
        comment="Configure Sentieon license-server CloudWatch logging",
    )
    if result.stdout.strip() != "SENTIEON_CLOUDWATCH_LOGGING_READY":
        raise RuntimeError("CloudWatch logging configuration returned unexpected output.")


def _install_script() -> str:
    unit_b64 = base64.b64encode(SYSTEMD_UNIT.encode("ascii")).decode("ascii")
    lines = [
        "set -euo pipefail",
        "umask 077",
        'tmp_dir="$(mktemp -d /tmp/sentieon-runtime.XXXXXX)"',
        'tmp_unit="$(mktemp /tmp/sentieon-license-server.XXXXXX)"',
        "cleanup() {",
        '  rm -rf -- "$tmp_dir"',
        '  rm -f -- "$tmp_unit"',
        "}",
        "trap cleanup EXIT",
        "trap 'exit 129' HUP",
        "trap 'exit 130' INT",
        "trap 'exit 143' TERM",
        "command -v /usr/local/bin/aws >/dev/null",
        "command -v sha256sum >/dev/null",
        "getent passwd sentieon >/dev/null",
        "getent group sentieon >/dev/null",
        "sudo test -f /etc/sentieon/license.lic",
        "sudo test ! -L /etc/sentieon/license.lic",
        'test "$(sudo stat -c "%U:%G %a" /etc/sentieon/license.lic)" = "root:sentieon 640"',
    ]
    for index, item in enumerate(RUNTIME_OBJECTS):
        destination = f'$tmp_dir/object-{index}'
        lines.extend(
            [
                f"/usr/local/bin/aws s3 cp --only-show-errors "
                f"{shlex.quote(item.s3_uri)} \"{destination}\"",
                f'test "$(sha256sum \"{destination}\" | awk \'{{print $1}}\')" = '
                f"{item.sha256}",
            ]
        )
    for directory in ("", "bin", "share", "libexec"):
        destination = RUNTIME_ROOT if not directory else f"{RUNTIME_ROOT}/{directory}"
        lines.append(f"sudo install -d -o root -g root -m 0755 {shlex.quote(destination)}")
    lines.append("sudo install -d -o root -g root -m 0755 /opt/sentieon")
    for index, item in enumerate(RUNTIME_OBJECTS):
        lines.append(
            f"sudo install -o root -g root -m {item.mode:04o} "
            f'\"$tmp_dir/object-{index}\" {shlex.quote(f"{RUNTIME_ROOT}/{item.relative_path}")}'
        )
    lines.extend(
        [
            f"printf '%s' {shlex.quote(unit_b64)} | base64 --decode > \"$tmp_unit\"",
            "sudo install -o root -g root -m 0644 "
            '"$tmp_unit" /etc/systemd/system/sentieon-license-server.service',
            "sudo install -d -o sentieon -g sentieon -m 0750 /var/log/sentieon",
            "sudo touch /var/log/sentieon/licsrvr.log",
            "sudo chown sentieon:sentieon /var/log/sentieon/licsrvr.log",
            "sudo chmod 0640 /var/log/sentieon/licsrvr.log",
            "sudo systemctl daemon-reload",
            "sudo systemctl enable sentieon-license-server.service >/dev/null",
            "sudo systemctl is-enabled --quiet sentieon-license-server.service",
            f"printf 'SENTIEON_LICENSE_SERVER_INSTALLED\\t{RUNTIME_VERSION}\\n'",
        ]
    )
    return "\n".join(lines)


def _service_action_script(action: str) -> str:
    if action not in {"start", "restart", "validate"}:
        raise ValueError(f"Unsupported service action: {action}")
    lines = ["set -euo pipefail"]
    if action in {"start", "restart"}:
        lines.append(f"sudo systemctl {action} sentieon-license-server.service")
    lines.extend(
        [
            "sudo systemctl is-enabled --quiet sentieon-license-server.service",
            "sudo systemctl is-active --quiet sentieon-license-server.service",
            'main_pid="$(sudo systemctl show --property MainPID --value '
            'sentieon-license-server.service)"',
            'test "$main_pid" -gt 1',
            f"listener_pid=\"$(sudo ss -H -ltnp 'sport = :{SERVICE_PORT}' "
            "| sed -n 's/.*pid=\\([0-9]\\+\\).*/\\1/p' | sort -u)\"",
            'test -n "$listener_pid"',
            'test "$(printf \'%s\\n\' "$listener_pid" | wc -l)" -eq 1',
            'current_pid="$listener_pid"',
            "listener_owned=false",
            'while [[ "$current_pid" -gt 1 ]]; do',
            '  if [[ "$current_pid" = "$main_pid" ]]; then listener_owned=true; break; fi',
            '  current_pid="$(ps -o ppid= -p "$current_pid" | tr -d \'[:space:]\')"',
            '  test -n "$current_pid"',
            "done",
            'test "$listener_owned" = true',
            f'test "$(getent ahostsv4 {BACKEND_FQDN} | awk \'NR==1 {{print $1}}\')" = '
            f"{PRIVATE_IP}",
            f'test "$(getent ahostsv4 {SERVICE_FQDN} | awk \'NR==1 {{print $1}}\')" = '
            f"{PRIVATE_IP}",
            f"{RUNTIME_ROOT}/bin/sentieon licclnt ping --server "
            f"{BACKEND_FQDN}:{SERVICE_PORT} >/dev/null",
            f"{RUNTIME_ROOT}/bin/sentieon licclnt ping --server "
            f"{SERVICE_FQDN}:{SERVICE_PORT} >/dev/null",
            f"printf 'SENTIEON_LICENSE_SERVER_{action.upper()}_OK\\n'",
        ]
    )
    return "\n".join(lines)


def _cloudwatch_version_script() -> str:
    return "\n".join(
        [
            "set -euo pipefail",
            f'test "$(/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent '
            f'--version 2>&1)" = "CWAgent/{CLOUDWATCH_AGENT_VERSION} '
            f'(go1.26.3; linux; amd64)"',
            f"printf 'SENTIEON_CLOUDWATCH_AGENT_READY\\t{CLOUDWATCH_AGENT_VERSION}\\n'",
        ]
    )


def _cloudwatch_script() -> str:
    config = {
        "agent": {"metrics_collection_interval": 60, "run_as_user": "root"},
        "logs": {
            "logs_collected": {
                "files": {
                    "collect_list": [
                        {
                            "file_path": "/var/log/sentieon/licsrvr.log",
                            "log_group_name": CLOUDWATCH_LOG_GROUP,
                            "log_stream_name": "{instance_id}",
                            "timezone": "UTC",
                        }
                    ]
                }
            }
        },
    }
    encoded = base64.b64encode((json.dumps(config, indent=2) + "\n").encode()).decode()
    return "\n".join(
        [
            "set -euo pipefail",
            "umask 077",
            f'test "$(/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent '
            f'--version 2>&1)" = "CWAgent/{CLOUDWATCH_AGENT_VERSION} '
            f'(go1.26.3; linux; amd64)"',
            'tmp_config="$(mktemp /tmp/sentieon-cloudwatch.XXXXXX)"',
            "cleanup() { rm -f -- \"$tmp_config\"; }",
            "trap cleanup EXIT HUP INT TERM",
            f"printf '%s' {shlex.quote(encoded)} | base64 --decode > \"$tmp_config\"",
            "sudo install -o root -g root -m 0644 \"$tmp_config\" "
            "/opt/aws/amazon-cloudwatch-agent/etc/sentieon-license.json",
            "sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl "
            "-a fetch-config -m ec2 -s "
            "-c file:/opt/aws/amazon-cloudwatch-agent/etc/sentieon-license.json >/dev/null",
            "sudo systemctl is-enabled --quiet amazon-cloudwatch-agent.service",
            "sudo systemctl is-active --quiet amazon-cloudwatch-agent.service",
            "printf 'SENTIEON_CLOUDWATCH_LOGGING_READY\\n'",
        ]
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=(
            "install",
            "start",
            "restart",
            "validate",
            "install-cloudwatch-agent",
            "configure-logging",
        ),
    )
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--profile")
    parser.add_argument("--approve-restart", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        kwargs = {
            "instance_id": args.instance_id,
            "region": args.region,
            "profile": args.profile,
        }
        if args.operation == "install":
            install_license_server(**kwargs)
        elif args.operation == "start":
            start_license_server(**kwargs)
        elif args.operation == "restart":
            restart_license_server(**kwargs, approve_restart=args.approve_restart)
        elif args.operation == "validate":
            validate_license_server(**kwargs)
        elif args.operation == "install-cloudwatch-agent":
            install_cloudwatch_agent(**kwargs)
        else:
            configure_cloudwatch_logging(**kwargs)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Sentieon license-server {args.operation} completed on {args.instance_id}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
