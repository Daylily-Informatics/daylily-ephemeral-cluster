"""Strict operational source contract for ParallelCluster backports."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from daylily_ec.state.models import CheckResult, CheckStatus, PreflightReport


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
    cli_source_root: Path
    cli_executable: Path
    node_repository: str
    node_commit: str
    node_bundle_uri: str
    node_bundle_sha256: str
    cookbook_repository: str
    cookbook_commit: str
    cookbook_bundle_uri: str
    cookbook_bundle_sha256: str
    image_ami_id: str
    image_parent_ami_id: str
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
    node = _required_mapping(raw, "node")
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
    source_root_value = _required_string(
        cli,
        "source_root",
        "parallelcluster.source_root",
    )
    cli_source_root = Path(source_root_value).expanduser()
    if not cli_source_root.is_absolute() or not cli_source_root.is_dir():
        raise ValueError(
            "parallelcluster.source_root must be an existing absolute directory."
        )
    cli_source_root = cli_source_root.resolve()
    git_top_level = Path(
        _run_checkout_git(
            cli_source_root,
            ["rev-parse", "--show-toplevel"],
            label="parallelcluster.source_root",
        )
    ).resolve()
    if git_top_level != cli_source_root:
        raise ValueError(
            "parallelcluster.source_root must be the exact Git worktree root."
        )
    checkout_repository = _run_checkout_git(
        cli_source_root,
        ["remote", "get-url", "origin"],
        label="parallelcluster.repository",
    )
    if checkout_repository != cli_repository:
        raise ValueError(
            "parallelcluster.source_root origin does not match "
            "parallelcluster.repository."
        )
    checkout_commit = _run_checkout_git(
        cli_source_root,
        ["rev-parse", "HEAD"],
        label="parallelcluster.commit",
    )
    if checkout_commit != cli_commit:
        raise ValueError(
            "parallelcluster.source_root HEAD does not match parallelcluster.commit."
        )
    tracked_changes = _run_checkout_git(
        cli_source_root,
        ["status", "--porcelain", "--untracked-files=no"],
        label="parallelcluster.source_root cleanliness",
    )
    if tracked_changes:
        raise ValueError(
            "parallelcluster.source_root has tracked changes; the operational checkout "
            "must be clean."
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
    cli_executable = cli_executable.resolve()
    try:
        cli_executable.relative_to(cli_source_root)
    except ValueError as exc:
        raise ValueError(
            "parallelcluster.executable must be located inside parallelcluster.source_root."
        ) from exc
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

    node_repository = _validate_https_repository(
        _required_string(node, "repository", "node.repository"),
        "node.repository",
    )
    node_commit = _validate_commit(
        _required_string(node, "commit", "node.commit"),
        "node.commit",
    )
    node_bundle_uri = _validate_s3_uri(
        _required_string(node, "bundle_uri", "node.bundle_uri"),
        "node.bundle_uri",
    )
    node_bundle_sha256 = _required_string(
        node,
        "bundle_sha256",
        "node.bundle_sha256",
    )
    if not _SHA256_PATTERN.fullmatch(node_bundle_sha256):
        raise ValueError("node.bundle_sha256 must be a lowercase SHA-256 digest.")

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
    parent_ami_id = _required_string(image, "parent_ami_id", "image.parent_ami_id")
    if not _AMI_PATTERN.fullmatch(parent_ami_id):
        raise ValueError(
            f"image.parent_ami_id must be an explicit AMI id; got {parent_ami_id!r}."
        )
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
        cli_source_root=cli_source_root,
        cli_executable=cli_executable,
        node_repository=node_repository,
        node_commit=node_commit,
        node_bundle_uri=node_bundle_uri,
        node_bundle_sha256=node_bundle_sha256,
        cookbook_repository=cookbook_repository,
        cookbook_commit=cookbook_commit,
        cookbook_bundle_uri=cookbook_bundle_uri,
        cookbook_bundle_sha256=cookbook_bundle_sha256,
        image_ami_id=ami_id,
        image_parent_ami_id=parent_ami_id,
        image_region=image_region,
        image_qualification_id=qualification_id,
    )


def make_operational_backport_preflight_step(
    *,
    s3_client: Any,
    ec2_client: Any,
    backport: OperationalBackport,
):
    """Validate immutable cookbook metadata and qualified AMI tags without mutation."""

    def step(report: PreflightReport) -> PreflightReport:
        try:
            parsed = urlparse(backport.cookbook_bundle_uri)
            bucket = parsed.netloc
            key = parsed.path.lstrip("/")
            head = s3_client.head_object(Bucket=bucket, Key=key)
            metadata = {
                str(name).lower(): str(value).lower()
                for name, value in (head.get("Metadata") or {}).items()
            }
            expected_cookbook_metadata = {
                "sha256": backport.cookbook_bundle_sha256,
                "pcluster-cli-commit": backport.cli_commit,
                "pcluster-cookbook-commit": backport.cookbook_commit,
            }
            if any(
                metadata.get(name) != expected
                for name, expected in expected_cookbook_metadata.items()
            ):
                raise ValueError(
                    "Cookbook object metadata does not match the operational manifest."
                )

            node_parsed = urlparse(backport.node_bundle_uri)
            node_head = s3_client.head_object(
                Bucket=node_parsed.netloc,
                Key=node_parsed.path.lstrip("/"),
            )
            node_metadata = {
                str(name).lower(): str(value).lower()
                for name, value in (node_head.get("Metadata") or {}).items()
            }
            expected_node_metadata = {
                "sha256": backport.node_bundle_sha256,
                "pcluster-node-commit": backport.node_commit,
                "pcluster-node-version": backport.parallelcluster_version,
            }
            if any(
                node_metadata.get(name) != expected
                for name, expected in expected_node_metadata.items()
            ):
                raise ValueError(
                    "Node package object metadata does not match the operational manifest."
                )

            images = ec2_client.describe_images(ImageIds=[backport.image_ami_id]).get(
                "Images", []
            )
            if len(images) != 1:
                raise ValueError("Qualified AMI did not resolve to exactly one image.")
            image = images[0]
            if image.get("State") != "available":
                raise ValueError("Qualified AMI is not available.")
            if image.get("Architecture") != "x86_64":
                raise ValueError("Qualified AMI architecture must be x86_64.")
            if str(image.get("OwnerId") or "") != report.account_id:
                raise ValueError("Qualified AMI must be owned by the active AWS account.")

            tags = {
                str(tag.get("Key") or ""): str(tag.get("Value") or "")
                for tag in image.get("Tags") or []
            }
            required_tags = {
                "dayec:qualification-status": "passed",
                "dayec:qualification-id": backport.image_qualification_id,
                "dayec:source-parent-ami": backport.image_parent_ami_id,
                "dayec:pcluster-cli-commit": backport.cli_commit,
                "dayec:pcluster-node-commit": backport.node_commit,
                "dayec:node-package-sha256": backport.node_bundle_sha256,
                "dayec:pcluster-cookbook-commit": backport.cookbook_commit,
                "dayec:cookbook-sha256": backport.cookbook_bundle_sha256,
            }
            mismatches = {
                key: {"expected": expected, "actual": tags.get(key)}
                for key, expected in required_tags.items()
                if tags.get(key) != expected
            }
            if mismatches:
                raise ValueError(
                    "Qualified AMI provenance tags do not match the operational manifest: "
                    + ", ".join(sorted(mismatches))
                )
        except Exception as exc:
            report.checks.append(
                CheckResult(
                    id="pcluster.backport_artifacts",
                    status=CheckStatus.FAIL,
                    details={"error": str(exc)},
                    remediation=(
                        "Publish the exact cookbook bundle with sha256 object metadata and "
                        "qualify/tag the account-owned child AMI before cluster creation."
                    ),
                )
            )
            return report

        report.checks.append(
            CheckResult(
                id="pcluster.backport_artifacts",
                status=CheckStatus.PASS,
                details={
                    "cookbook_sha256_verified": True,
                    "node_package_sha256_verified": True,
                    "qualified_image_verified": True,
                    "qualification_id": backport.image_qualification_id,
                },
            )
        )
        return report

    return step


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


def _run_checkout_git(source_root: Path, args: list[str], *, label: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(source_root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"{label} could not be verified as a Git worktree.")
    return result.stdout.strip()


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
