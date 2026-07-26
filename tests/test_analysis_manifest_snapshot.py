from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import daylily_ec.cli as cli_module
from daylily_ec.cli import (
    ANALYSIS_MANIFEST_SNAPSHOT_SCHEMA,
    _materialize_analysis_manifest_snapshot,
    app,
)
from daylily_ec.manifest_set import MANIFEST_NAMES, load_manifest_set
from daylily_ec.scripts.common import CommandError


runner = CliRunner()


def _manifest_contents() -> dict[str, bytes]:
    return {
        "specimens.tsv": b"SPECIMEN_ID\tSPECIMEN_EUID\nspecimen-1\t\n",
        "samples.tsv": b"SAMPLEID\tSAMPLE_EUID\tSPECIMEN_ID\nsample-1\towner-sample-1\tspecimen-1\n",
        "libraries.tsv": b"LIBRARY_ID\tLIBRARY_EUID\tSAMPLEID\nlibrary-1\t\tsample-1\n",
        "sequencing_inputs.tsv": (
            b"SEQUENCING_INPUT_UID\tLIBRARY_ID\tMODALITY\tLAYOUT\tILMN_R1_PATH\tILMN_R2_PATH\n"
            b"input-1\tlibrary-1\tsr\tpaired_fastq\t/fsx/r1.fastq.gz\t/fsx/r2.fastq.gz\n"
        ),
        "analysis_units.tsv": b"ANALYSIS_UNIT_UID\tSAMPLEID\nanalysis-unit-1\tsample-1\n",
        "analysis_unit_inputs.tsv": (
            b"ANALYSIS_UNIT_UID\tSEQUENCING_INPUT_UID\tROLE\tINPUT_ORDINAL\n"
            b"analysis-unit-1\tinput-1\tsr\t1\n"
        ),
    }


def _payload() -> dict[str, object]:
    contents = _manifest_contents()
    return {
        "schema_version": ANALYSIS_MANIFEST_SNAPSHOT_SCHEMA,
        "analysis_root": "/fsx/analysis_results/preval-hiomr2/live3",
        "source_config_dir": "/fsx/analysis_results/preval-hiomr2/live3/daylily-omics-analysis/config",
        "total_size_bytes": sum(len(value) for value in contents.values()),
        "files": {
            name: {
                "size_bytes": len(contents[name]),
                "sha256": hashlib.sha256(contents[name]).hexdigest(),
                "content_base64": base64.b64encode(contents[name]).decode("ascii"),
            }
            for name in MANIFEST_NAMES
        },
    }


def _activate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")
    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")


def test_materialize_analysis_manifest_snapshot_is_exact_and_non_overwriting(tmp_path: Path) -> None:
    destination = tmp_path / "exact-manifests"

    result = _materialize_analysis_manifest_snapshot(_payload(), output_dir=destination)

    manifests = load_manifest_set(destination)
    assert result["output_dir"] == str(destination)
    assert result["manifest_hashes"] == dict(manifests.hashes)
    assert set(result["manifest_hashes"]) == set(MANIFEST_NAMES)
    assert "content_base64" not in (destination / "dyec_analysis_manifest_snapshot.json").read_text(
        encoding="utf-8"
    )
    with pytest.raises(CommandError, match="refusing to overwrite"):
        _materialize_analysis_manifest_snapshot(_payload(), output_dir=destination)


def test_materialize_analysis_manifest_snapshot_rejects_digest_tampering(tmp_path: Path) -> None:
    payload = _payload()
    files = payload["files"]
    assert isinstance(files, dict)
    record = files["samples.tsv"]
    assert isinstance(record, dict)
    record["sha256"] = "0" * 64

    with pytest.raises(CommandError, match="digest mismatch"):
        _materialize_analysis_manifest_snapshot(payload, output_dir=tmp_path / "tampered")


def test_remote_snapshot_uses_dyec_managed_transport_and_writes_local_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _activate(monkeypatch)
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        cli_module,
        "_resolve_headnode_cli_target",
        lambda **_kwargs: (
            "lsmc",
            "us-west-2",
            "preval-hiomr2",
            SimpleNamespace(instance_id="i-123"),
        ),
    )
    monkeypatch.setattr("daylily_ec.aws.ssm.wait_for_ssm_online", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "daylily_ec.aws.ssm.resolve_remote_user",
        lambda *_args, **_kwargs: "ubuntu",
    )

    def fake_collect(**kwargs):
        captured.update(kwargs)
        return _payload()

    monkeypatch.setattr(cli_module, "_collect_remote_json_payload", fake_collect)
    destination = tmp_path / "remote-manifests"
    result = runner.invoke(
        app,
        [
            "--json",
            "analysis",
            "snapshot-manifests",
            "--analysis-root",
            "/fsx/analysis_results/preval-hiomr2/live3",
            "--output-dir",
            str(destination),
            "--profile",
            "lsmc",
            "--region",
            "us-west-2",
            "--cluster",
            "preval-hiomr2",
        ],
    )

    assert result.exit_code == 0, result.stdout + result.stderr
    output = json.loads(result.stdout)
    assert output["cluster"]["headnode_instance_id"] == "i-123"
    assert load_manifest_set(destination).hashes == output["manifest_hashes"]
    assert captured["operation"] == "analysis_manifest_snapshot"
    remote_argv = captured["remote_argv"]
    assert isinstance(remote_argv, list)
    assert remote_argv[:2] == ["python3", "-c"]
    assert "write_visit" in remote_argv[2]
