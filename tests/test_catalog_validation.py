from __future__ import annotations

import io
import json

import pytest

from daylily_ec.catalog_validation import (
    CatalogValidationError,
    compare_command_validation_evidence,
)
from daylily_ec.repositories import AnalysisCommand


def _command(*, evidence_prefix: str = "s3://validation-bucket/command-a/") -> AnalysisCommand:
    return AnalysisCommand.model_validate(
        {
            "command_id": "command_a",
            "repository": "repo",
            "type": "prod",
            "validated_version": "13.4.28",
            "validation_evidence_s3_uri_prefix": evidence_prefix,
            "test_data_profile": "profile",
            "display_name": "Command A",
            "datasource": "test",
            "launcher": "workflow_launch",
            "command_class": "utility",
            "input_contract": "none",
            "requires_staging": False,
            "requires_run_mount": False,
            "targets": ["help"],
            "genome": "hg38",
            "jobs": 1,
            "aligners": [],
            "dedupers": [],
            "snv_callers": [],
            "dy_command": "source dyoainit; dy-a local hg38; dy-r help",
            "dryrun_dy_command": "source dyoainit; dy-a local hg38; dy-r help -n",
            "compatible_platforms": ["test"],
            "compatible_cluster_types": ["daywgs"],
            "compatible_data_modes": ["none"],
            "git_tag": "13.4.28",
            "day_profile": "local",
            "default_activation": False,
        }
    )


class _BodyClient:
    def __init__(self, objects: dict[str, object]) -> None:
        self.objects = objects

    def get_object(self, *, Bucket: str, Key: str):
        if Bucket != "validation-bucket" or Key not in self.objects:
            raise RuntimeError("not found")
        return {"Body": io.BytesIO(json.dumps(self.objects[Key]).encode("utf-8"))}


def test_compare_command_validation_evidence_matches_successful_receipts() -> None:
    client = _BodyClient(
        {
            "command-a/command_registry.json": {
                "command_ids": ["command_a"],
                "dayoa_version": "13.4.28",
            },
            "command-a/summary.json": {
                "rc": 0,
                "phases": [{"command_id": "command_a", "launch_rc": 0, "exit_code": 0}],
            },
        }
    )

    result = compare_command_validation_evidence(_command(), s3_client=client)

    assert result.to_payload()["matches"] is True
    assert result.matching_successful_phases == 1


def test_compare_command_validation_evidence_fails_hard_without_declared_prefix() -> None:
    with pytest.raises(CatalogValidationError, match="no validation_evidence_s3_uri_prefix"):
        compare_command_validation_evidence(_command(evidence_prefix=""), s3_client=_BodyClient({}))


def test_compare_command_validation_evidence_rejects_wrong_dayoa_pin() -> None:
    client = _BodyClient(
        {
            "command-a/command_registry.json": {
                "command_ids": ["command_a"],
                "dayoa_version": "13.4.27",
            },
            "command-a/summary.json": {"rc": 0, "phases": []},
        }
    )
    with pytest.raises(CatalogValidationError, match="does not match catalog pin"):
        compare_command_validation_evidence(_command(), s3_client=client)
