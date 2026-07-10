from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from daylily_ec.pcluster.backport import (
    BACKPORT_SCHEMA_VERSION,
    load_operational_backport,
)


def _write_manifest(tmp_path: Path, **overrides: str) -> Path:
    executable = tmp_path / "pcluster"
    executable.write_text("#!/bin/sh\necho '3.15.0'\n", encoding="utf-8")
    executable.chmod(0o755)
    payload = {
        "schema_version": BACKPORT_SCHEMA_VERSION,
        "parallelcluster": {
            "version": "3.15.0",
            "repository": "https://github.com/iamh2o/aws-parallelcluster.git",
            "commit": "a" * 40,
            "executable": str(executable),
        },
        "cookbook": {
            "repository": "https://github.com/iamh2o/aws-parallelcluster-cookbook.git",
            "commit": "b" * 40,
            "bundle_uri": "s3://private-assets/backports/cookbook-bbbbbbbb.tgz",
            "bundle_sha256": "c" * 64,
        },
        "image": {
            "ami_id": "ami-0123456789abcdef0",
            "region": "us-west-2",
            "qualification_status": "passed",
            "qualification_id": "qualification-20260710",
        },
    }
    for dotted_key, value in overrides.items():
        section, key = dotted_key.split("__", 1)
        payload[section][key] = value
    path = tmp_path / "backport.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def test_load_operational_backport_requires_exact_pins(tmp_path: Path) -> None:
    spec = load_operational_backport(_write_manifest(tmp_path))

    assert spec.parallelcluster_version == "3.15.0"
    assert spec.cli_commit == "a" * 40
    assert spec.cookbook_commit == "b" * 40
    assert spec.image_ami_id == "ami-0123456789abcdef0"
    assert spec.image_qualification_id == "qualification-20260710"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"parallelcluster__commit": "develop"}, "40-character git commit"),
        ({"parallelcluster__version": "3.14.0"}, "must be 3.15.0"),
        ({"cookbook__bundle_sha256": "not-a-digest"}, "SHA-256"),
        ({"image__qualification_status": "pending"}, "exactly 'passed'"),
        ({"image__ami_id": "ami-pending"}, "explicit AMI id"),
    ],
)
def test_load_operational_backport_rejects_unpinned_or_unqualified_values(
    tmp_path: Path,
    overrides: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        load_operational_backport(_write_manifest(tmp_path, **overrides))


def test_load_operational_backport_rejects_stock_or_wrong_version_executable(
    tmp_path: Path,
) -> None:
    manifest = _write_manifest(tmp_path)
    executable = tmp_path / "pcluster"
    executable.write_text("#!/bin/sh\necho '3.14.0'\n", encoding="utf-8")

    with pytest.raises(ValueError, match="did not report the pinned version"):
        load_operational_backport(manifest)
