"""Strict operational source contract for ParallelCluster backports."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import yaml


BACKPORT_SCHEMA_VERSION = "dyec.parallelcluster_backport.v1"
SUPPORTED_PARALLELCLUSTER_VERSION = "3.15.0"
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_AMI_PATTERN = re.compile(r"^ami-[0-9a-f]{17}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_REGION_PATTERN = re.compile(r"^[a-z]{2}(?:-gov)?-[a-z]+-\d$")


@dataclass(frozen=True)
class OperationalBackport:
    """Pinned CLI, cookbook, and qualified image used by one cluster build."""

    manifest_path: Path
    parallelcluster_version: str
    cli_repository: str
    cli_commit: str
    cli_executable: Path
    cookbook_repository: str
    cookbook_commit: str
    cookbook_bundle_uri: str
    cookbook_bundle_sha256: str
    image_ami_id: str
    image_region: str
    image_qualification_id: str


def load_operational_backport(path: str | Path) -> OperationalBackport:
    """Load a fully pinned operational manifest or fail before AWS work starts."""

    manifest_path = Path(path).expanduser()
    if not manifest_path.is_file():
        raise ValueError(f"ParallelCluster backport manifest not found: {manifest_path}")
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("ParallelCluster backport manifest must be a YAML mapping.")
    if raw.get("schema_version") != BACKPORT_SCHEMA_VERSION:
        raise ValueError(
            "ParallelCluster backport manifest schema_version must be "
            f"{BACKPORT_SCHEMA_VERSION!r}."
        )

    cli = _required_mapping(raw, "parallelcluster")
    cookbook = _required_mapping(raw, "cookbook")
    image = _required_mapping(raw, "image")

    version = _required_string(cli, "version", "parallelcluster.version")
    if version != SUPPORTED_PARALLELCLUSTER_VERSION:
        raise ValueError(
            "Operational ParallelCluster backport version must be "
            f"{SUPPORTED_PARALLELCLUSTER_VERSION}; got {version!r}."
        )

    cli_repository = _validate_https_repository(
        _required_string(cli, "repository", "parallelcluster.repository"),
        "parallelcluster.repository",
    )
    cli_commit = _validate_commit(
        _required_string(cli, "commit", "parallelcluster.commit"),
        "parallelcluster.commit",
    )
    executable_value = _required_string(cli, "executable", "parallelcluster.executable")
    cli_executable = Path(executable_value).expanduser()
    if not cli_executable.is_absolute():
        raise ValueError("parallelcluster.executable must be an absolute path.")
    if not cli_executable.is_file() or not os.access(cli_executable, os.X_OK):
        raise ValueError(
            "parallelcluster.executable must exist and be executable: "
            f"{cli_executable}"
        )
    version_probe = subprocess.run(
        [str(cli_executable), "version"],
        check=False,
        capture_output=True,
        text=True,
    )
    version_output = "\n".join(
        part.strip() for part in (version_probe.stdout, version_probe.stderr) if part.strip()
    )
    if version_probe.returncode != 0 or not re.search(
        rf"(?<![0-9.]){re.escape(version)}(?![0-9.])",
        version_output,
    ):
        raise ValueError(
            "parallelcluster.executable did not report the pinned version "
            f"{version}: {cli_executable}"
        )

    cookbook_repository = _validate_https_repository(
        _required_string(cookbook, "repository", "cookbook.repository"),
        "cookbook.repository",
    )
    cookbook_commit = _validate_commit(
        _required_string(cookbook, "commit", "cookbook.commit"),
        "cookbook.commit",
    )
    cookbook_bundle_uri = _validate_s3_uri(
        _required_string(cookbook, "bundle_uri", "cookbook.bundle_uri"),
        "cookbook.bundle_uri",
    )
    cookbook_bundle_sha256 = _required_string(
        cookbook,
        "bundle_sha256",
        "cookbook.bundle_sha256",
    )
    if not _SHA256_PATTERN.fullmatch(cookbook_bundle_sha256):
        raise ValueError("cookbook.bundle_sha256 must be a lowercase SHA-256 digest.")

    ami_id = _required_string(image, "ami_id", "image.ami_id")
    if not _AMI_PATTERN.fullmatch(ami_id):
        raise ValueError(f"image.ami_id must be an explicit AMI id; got {ami_id!r}.")
    image_region = _required_string(image, "region", "image.region")
    if not _REGION_PATTERN.fullmatch(image_region):
        raise ValueError(f"image.region is invalid: {image_region!r}.")
    qualification_status = _required_string(
        image,
        "qualification_status",
        "image.qualification_status",
    )
    if qualification_status != "passed":
        raise ValueError("image.qualification_status must be exactly 'passed'.")
    qualification_id = _required_string(
        image,
        "qualification_id",
        "image.qualification_id",
    )

    return OperationalBackport(
        manifest_path=manifest_path.resolve(),
        parallelcluster_version=version,
        cli_repository=cli_repository,
        cli_commit=cli_commit,
        cli_executable=cli_executable.resolve(),
        cookbook_repository=cookbook_repository,
        cookbook_commit=cookbook_commit,
        cookbook_bundle_uri=cookbook_bundle_uri,
        cookbook_bundle_sha256=cookbook_bundle_sha256,
        image_ami_id=ami_id,
        image_region=image_region,
        image_qualification_id=qualification_id,
    )


def _required_mapping(parent: dict, key: str) -> dict:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"ParallelCluster backport manifest requires mapping {key!r}.")
    return value


def _required_string(parent: dict, key: str, label: str) -> str:
    value = str(parent.get(key) or "").strip()
    if not value:
        raise ValueError(f"ParallelCluster backport manifest requires {label}.")
    return value


def _validate_commit(value: str, label: str) -> str:
    if not _COMMIT_PATTERN.fullmatch(value):
        raise ValueError(f"{label} must be an exact lowercase 40-character git commit.")
    return value


def _validate_https_repository(value: str, label: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or not parsed.path.endswith(".git")
    ):
        raise ValueError(f"{label} must be an explicit https://github.com/...git URL.")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError(f"{label} must not include parameters, query, or fragment.")
    return value


def _validate_s3_uri(value: str, label: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.strip("/"):
        raise ValueError(f"{label} must be an explicit s3://bucket/key URI.")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError(f"{label} must not include parameters, query, or fragment.")
    return value
