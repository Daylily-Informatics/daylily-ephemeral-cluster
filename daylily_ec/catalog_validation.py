"""Read-only comparison of catalog command definitions with stored validation evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from daylily_ec.repositories import AnalysisCommand


class CatalogValidationError(RuntimeError):
    """Raised when a catalog command lacks or disagrees with its validation evidence."""


@dataclass(frozen=True)
class CatalogValidationComparison:
    command_id: str
    validation_evidence_s3_uri_prefix: str
    expected_dayoa_git_tag: str
    observed_dayoa_git_tag: str
    evidence_rc: int
    matching_successful_phases: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "validation_evidence_s3_uri_prefix": self.validation_evidence_s3_uri_prefix,
            "expected_dayoa_git_tag": self.expected_dayoa_git_tag,
            "observed_dayoa_git_tag": self.observed_dayoa_git_tag,
            "evidence_rc": self.evidence_rc,
            "matching_successful_phases": self.matching_successful_phases,
            "matches": True,
        }


def _s3_bucket_and_prefix(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.strip("/"):
        raise CatalogValidationError(f"Invalid validation evidence S3 prefix: {uri!r}")
    return parsed.netloc, parsed.path.lstrip("/").rstrip("/") + "/"


def _read_json(s3_client: Any, *, bucket: str, key: str) -> dict[str, Any]:
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        raw = response["Body"].read()
    except Exception as exc:  # boto3 has several service-specific exception classes
        raise CatalogValidationError(f"Unable to read s3://{bucket}/{key}: {exc}") from exc
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CatalogValidationError(
            f"Validation evidence is not valid JSON: s3://{bucket}/{key}"
        ) from exc
    if not isinstance(value, dict):
        raise CatalogValidationError(
            f"Validation evidence must be a JSON object: s3://{bucket}/{key}"
        )
    return value


def compare_command_validation_evidence(
    command: AnalysisCommand,
    *,
    profile: str | None = None,
    region: str | None = None,
    s3_client: Any | None = None,
) -> CatalogValidationComparison:
    """Compare immutable command facts with its explicitly configured S3 evidence.

    The prefix must contain the two receipts written by ``dyec tests
    command-catalog``: ``command_registry.json`` and ``summary.json``.  The
    function is intentionally read-only and fails hard for absent evidence.
    """

    prefix_uri = command.validation_evidence_s3_uri_prefix
    if not prefix_uri:
        raise CatalogValidationError(
            f"Catalog command {command.command_id!r} has no validation_evidence_s3_uri_prefix. "
            "Declare an explicit successful validation prefix before comparing it."
        )
    if s3_client is None:
        try:
            import boto3

            session = boto3.Session(profile_name=profile, region_name=region)
            s3_client = session.client("s3")
        except Exception as exc:
            raise CatalogValidationError(f"Unable to create S3 client: {exc}") from exc

    bucket, prefix = _s3_bucket_and_prefix(prefix_uri)
    registry = _read_json(s3_client, bucket=bucket, key=prefix + "command_registry.json")
    summary = _read_json(s3_client, bucket=bucket, key=prefix + "summary.json")
    command_ids = registry.get("command_ids")
    observed_tag = registry.get("dayoa_version")
    if not isinstance(command_ids, list) or command.command_id not in command_ids:
        raise CatalogValidationError(
            f"Validation registry at {prefix_uri} does not include command {command.command_id!r}"
        )
    if not isinstance(observed_tag, str) or observed_tag != command.git_tag:
        raise CatalogValidationError(
            f"Validation registry DayOA version {observed_tag!r} does not match catalog pin "
            f"{command.git_tag!r} for {command.command_id!r}"
        )
    evidence_rc = summary.get("rc")
    if evidence_rc != 0:
        raise CatalogValidationError(
            f"Validation summary at {prefix_uri} is not successful: rc={evidence_rc!r}"
        )
    phases = summary.get("phases")
    if not isinstance(phases, list):
        raise CatalogValidationError(f"Validation summary at {prefix_uri} has no phases list")
    successful_phases = [
        phase
        for phase in phases
        if isinstance(phase, dict)
        and phase.get("command_id") == command.command_id
        and phase.get("launch_rc") == 0
        and phase.get("exit_code") == 0
    ]
    if not successful_phases:
        raise CatalogValidationError(
            f"Validation summary at {prefix_uri} has no successful phase for {command.command_id!r}"
        )
    return CatalogValidationComparison(
        command_id=command.command_id,
        validation_evidence_s3_uri_prefix=prefix_uri,
        expected_dayoa_git_tag=command.git_tag,
        observed_dayoa_git_tag=observed_tag,
        evidence_rc=evidence_rc,
        matching_successful_phases=len(successful_phases),
    )
