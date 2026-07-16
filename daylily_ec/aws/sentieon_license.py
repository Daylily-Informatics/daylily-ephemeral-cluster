"""Fail-closed Sentieon license secret ingestion and server materialization."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import stat
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

import boto3
from botocore.exceptions import ClientError

from daylily_ec.aws.ssm import run_shell

DEFAULT_SECRET_NAME = "dayec/sentieon/license-servers/usw2d-01"
DEFAULT_REMOTE_LICENSE_PATH = "/etc/sentieon/license.lic"
_REMOTE_MARKER = "SENTIEON_LICENSE_MATERIALIZED"
_METADATA_KEYS = frozenset({"secret_arn", "version_id", "sha256"})


@dataclass(frozen=True)
class SentieonLicenseSecretMetadata:
    """Non-secret evidence for one exact Secrets Manager version."""

    secret_arn: str
    version_id: str
    sha256: str

    def write(self, path: Path) -> None:
        """Atomically write only non-secret evidence with owner-only permissions."""

        _validate_metadata(self)
        _write_metadata(path, asdict(self))


def ensure_sentieon_license_secret(
    *,
    secretsmanager_client: Any,
    license_path: Path,
    secret_name: str = DEFAULT_SECRET_NAME,
) -> SentieonLicenseSecretMetadata:
    """Create a binary secret or verify that its current value is byte-identical.

    An existing value is never updated by this function. A mismatch fails and requires an
    explicit version-rotation operation rather than silently replacing the active license.
    """

    license_bytes = _read_private_license_file(license_path)
    expected_sha256 = hashlib.sha256(license_bytes).hexdigest()

    try:
        description = secretsmanager_client.describe_secret(SecretId=secret_name)
    except ClientError as exc:
        if not _is_resource_not_found(exc):
            raise RuntimeError("Unable to describe the Sentieon license secret.") from exc
        return _create_secret(
            secretsmanager_client=secretsmanager_client,
            secret_name=secret_name,
            license_bytes=license_bytes,
            expected_sha256=expected_sha256,
        )

    secret_arn = _validated_secret_arn(description, expected_name=secret_name)
    try:
        current = secretsmanager_client.get_secret_value(
            SecretId=secret_arn,
            VersionStage="AWSCURRENT",
        )
    except ClientError as exc:
        raise RuntimeError("Unable to verify the current Sentieon license secret value.") from exc

    actual_bytes = _binary_secret_value(current)
    actual_sha256 = hashlib.sha256(actual_bytes).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ValueError(
            "The existing Sentieon license secret does not match the supplied file; "
            "refusing to replace AWSCURRENT implicitly."
        )
    version_id = _required_text(current, "VersionId")
    return SentieonLicenseSecretMetadata(
        secret_arn=secret_arn,
        version_id=version_id,
        sha256=expected_sha256,
    )


def materialize_sentieon_license(
    *,
    instance_id: str,
    region: str,
    metadata: SentieonLicenseSecretMetadata,
    profile: str | None = None,
) -> SentieonLicenseSecretMetadata:
    """Materialize an exact binary secret version on the dedicated license server.

    The instance retrieves the secret directly through its IAM role. The secret never enters
    the SSM command payload, stdout, stderr, or this process. Installation is atomic and the
    destination must be a non-symlink regular file owned by ``root:sentieon`` with mode 0640.
    """

    script = _materialization_script(region=region, metadata=metadata)
    result = run_shell(
        instance_id,
        region,
        script,
        profile=profile,
        as_user="ubuntu",
        timeout=300,
        comment="Materialize Sentieon license secret",
    )
    marker = f"{_REMOTE_MARKER}\t{metadata.sha256}"
    output_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if output_lines != [marker]:
        raise RuntimeError(
            "Sentieon license materialization returned unexpected output; "
            "refusing to treat it as successful."
        )
    return metadata


def read_metadata(path: Path) -> SentieonLicenseSecretMetadata:
    """Read and strictly validate a non-secret metadata record."""

    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Metadata path must be a regular, non-symlink file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or frozenset(data) != _METADATA_KEYS:
        raise ValueError("Sentieon license metadata must contain exactly ARN, version, and hash.")
    metadata = SentieonLicenseSecretMetadata(
        secret_arn=str(data["secret_arn"]),
        version_id=str(data["version_id"]),
        sha256=str(data["sha256"]),
    )
    _validate_metadata(metadata)
    return metadata


def _create_secret(
    *,
    secretsmanager_client: Any,
    secret_name: str,
    license_bytes: bytes,
    expected_sha256: str,
) -> SentieonLicenseSecretMetadata:
    try:
        created = secretsmanager_client.create_secret(
            Name=secret_name,
            Description="Sentieon cluster license for usw2d-01.sentieon.lsmc.bio",
            SecretBinary=license_bytes,
            Tags=[
                {"Key": "dayec:component", "Value": "sentieon-license-server"},
                {"Key": "dayec:license-server", "Value": "usw2d-01"},
            ],
        )
    except ClientError as exc:
        raise RuntimeError("Unable to create the Sentieon license secret.") from exc
    secret_arn = _validated_secret_arn(
        {"ARN": created.get("ARN"), "Name": secret_name},
        expected_name=secret_name,
    )
    version_id = _required_text(created, "VersionId")
    return SentieonLicenseSecretMetadata(
        secret_arn=secret_arn,
        version_id=version_id,
        sha256=expected_sha256,
    )


def _read_private_license_file(path: Path) -> bytes:
    try:
        details = path.lstat()
    except OSError as exc:
        raise ValueError(f"Unable to inspect Sentieon license file: {path}") from exc
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode):
        raise ValueError(f"Sentieon license path must be a regular, non-symlink file: {path}")
    if details.st_uid != os.geteuid():
        raise ValueError("Sentieon license file must be owned by the current user.")
    if stat.S_IMODE(details.st_mode) & 0o077:
        raise ValueError("Sentieon license file permissions must not grant group or other access.")
    value = path.read_bytes()
    if not value:
        raise ValueError("Sentieon license file must not be empty.")
    return value


def _validated_secret_arn(description: dict[str, Any], *, expected_name: str) -> str:
    if description.get("DeletedDate") is not None:
        raise ValueError("The Sentieon license secret is scheduled for deletion.")
    if str(description.get("Name") or "") != expected_name:
        raise ValueError("Secrets Manager returned a different Sentieon license secret name.")
    arn = _required_text(description, "ARN")
    if f":secret:{expected_name}-" not in arn:
        raise ValueError("Secrets Manager returned an ARN outside the configured secret name.")
    return arn


def _binary_secret_value(response: dict[str, Any]) -> bytes:
    if response.get("SecretString") is not None:
        raise ValueError("Sentieon license secret must use SecretBinary, not SecretString.")
    value = response.get("SecretBinary")
    if not isinstance(value, (bytes, bytearray)) or not value:
        raise ValueError("Sentieon license secret has no non-empty binary value.")
    return bytes(value)


def _required_text(mapping: dict[str, Any], key: str) -> str:
    value = str(mapping.get(key) or "").strip()
    if not value:
        raise ValueError(f"Secrets Manager response is missing {key}.")
    return value


def _is_resource_not_found(exc: ClientError) -> bool:
    return str(exc.response.get("Error", {}).get("Code") or "") == "ResourceNotFoundException"


def _write_metadata(path: Path, data: dict[str, str]) -> None:
    if frozenset(data) != _METADATA_KEYS:
        raise ValueError("Refusing to write metadata with unexpected fields.")
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError(f"Metadata parent must be an existing non-symlink directory: {parent}")
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError(f"Metadata destination must be a regular, non-symlink path: {path}")

    payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(parent))
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_metadata(metadata: SentieonLicenseSecretMetadata) -> None:
    if not metadata.secret_arn.startswith("arn:aws:secretsmanager:"):
        raise ValueError("Sentieon license metadata contains an invalid secret ARN.")
    if not metadata.version_id or any(char.isspace() for char in metadata.version_id):
        raise ValueError("Sentieon license metadata contains an invalid version ID.")
    if len(metadata.sha256) != 64 or any(
        char not in "0123456789abcdef" for char in metadata.sha256
    ):
        raise ValueError("Sentieon license metadata contains an invalid SHA-256 digest.")


def _materialization_script(
    *,
    region: str,
    metadata: SentieonLicenseSecretMetadata,
) -> str:
    _validate_metadata(metadata)
    destination = DEFAULT_REMOTE_LICENSE_PATH
    parent = str(Path(destination).parent)
    return "\n".join(
        [
            "set -euo pipefail",
            "umask 077",
            f"readonly secret_arn={shlex.quote(metadata.secret_arn)}",
            f"readonly version_id={shlex.quote(metadata.version_id)}",
            f"readonly expected_sha256={shlex.quote(metadata.sha256)}",
            f"readonly destination={shlex.quote(destination)}",
            f"readonly parent={shlex.quote(parent)}",
            'readonly partial="${destination}.partial.${BASHPID}"',
            'local_tmp="$(mktemp /tmp/sentieon-license.XXXXXX)"',
            "cleanup() {",
            '  rm -f -- "$local_tmp"',
            '  sudo rm -f -- "$partial"',
            "}",
            "trap cleanup EXIT",
            "trap 'exit 129' HUP",
            "trap 'exit 130' INT",
            "trap 'exit 143' TERM",
            "command -v aws >/dev/null",
            "command -v base64 >/dev/null",
            "command -v sha256sum >/dev/null",
            "command -v install >/dev/null",
            "getent group sentieon >/dev/null",
            'sudo test -d "$parent"',
            'sudo test ! -L "$parent"',
            'test "$(sudo stat -c "%U:%G %a" "$parent")" = "root:sentieon 750"',
            'if sudo test -e "$destination"; then',
            '  sudo test -f "$destination"',
            '  sudo test ! -L "$destination"',
            "fi",
            "aws secretsmanager get-secret-value \\",
            f"  --region {shlex.quote(region)} \\",
            '  --secret-id "$secret_arn" \\',
            '  --version-id "$version_id" \\',
            "  --query SecretBinary \\",
            '  --output text | base64 --decode > "$local_tmp"',
            'test -s "$local_tmp"',
            'test "$(sha256sum "$local_tmp" | awk \'{print $1}\')" = "$expected_sha256"',
            'sudo install -o root -g sentieon -m 0640 -- "$local_tmp" "$partial"',
            'test "$(sudo stat -c "%U:%G %a" "$partial")" = "root:sentieon 640"',
            'test "$(sudo sha256sum "$partial" | awk \'{print $1}\')" = "$expected_sha256"',
            'sudo sync -f "$partial"',
            'sudo mv -fT -- "$partial" "$destination"',
            'sudo sync -f "$parent"',
            'test "$(sudo stat -c "%U:%G %a" "$destination")" = "root:sentieon 640"',
            'test "$(sudo sha256sum "$destination" | awk \'{print $1}\')" = "$expected_sha256"',
            f"printf '%s\\t%s\\n' {shlex.quote(_REMOTE_MARKER)} \"$expected_sha256\"",
        ]
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    ensure = subparsers.add_parser("ensure", help="Create or verify the binary secret")
    ensure.add_argument("--license-file", type=Path, required=True)
    ensure.add_argument("--metadata-file", type=Path, required=True)
    ensure.add_argument("--secret-name", default=DEFAULT_SECRET_NAME)
    ensure.add_argument("--region", required=True)
    ensure.add_argument("--profile")

    materialize = subparsers.add_parser(
        "materialize",
        help="Materialize an exact secret version on the dedicated server",
    )
    materialize.add_argument("--instance-id", required=True)
    materialize.add_argument("--metadata-file", type=Path, required=True)
    materialize.add_argument("--region", required=True)
    materialize.add_argument("--profile")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "ensure":
            session = boto3.Session(profile_name=args.profile, region_name=args.region)
            metadata = ensure_sentieon_license_secret(
                secretsmanager_client=session.client("secretsmanager"),
                license_path=args.license_file,
                secret_name=args.secret_name,
            )
            metadata.write(args.metadata_file)
            print(
                f"Verified Sentieon license secret {metadata.secret_arn} "
                f"version {metadata.version_id} sha256 {metadata.sha256}."
            )
            return 0

        metadata = read_metadata(args.metadata_file)
        materialize_sentieon_license(
            instance_id=args.instance_id,
            region=args.region,
            profile=args.profile,
            metadata=metadata,
        )
        print(
            f"Materialized Sentieon license secret {metadata.secret_arn} "
            f"version {metadata.version_id} sha256 {metadata.sha256}."
        )
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
