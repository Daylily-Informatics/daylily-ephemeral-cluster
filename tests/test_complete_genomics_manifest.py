import json
from pathlib import Path

from daylily_ec.complete_genomics_manifest import (
    finalize_complete_genomics_slim_mounted_reference_materialization,
    generate_complete_genomics_six_manifest,
    generate_complete_genomics_slim_mounted_reference_six_manifest,
)
from daylily_ec.manifest_set import load_manifest_set


def test_complete_genomics_v1_fixture_declares_deterministic_staging_mapping(
    tmp_path: Path,
) -> None:
    root = generate_complete_genomics_six_manifest(
        source=Path("examples/staging/complete_genomics_solo/analysis_samples_manifest.tsv"),
        output_dir=tmp_path / "complete",
        stage_s3_uri="s3://lsmc-dayoa-control-data-usw2/staged_external_sequencing_data",
    )
    manifests = load_manifest_set(root)
    source = manifests.rows["sequencing_inputs.tsv"][0]
    assert source["SEQ_VENDOR"] == "CG"
    assert source["SEQ_PLATFORM"] == "CG"
    assert manifests.rows["samples.tsv"][0]["ORDER_TYPE"] == "RESEARCH"
    assert manifests.rows["specimens.tsv"][0]["SPECIMEN_EUID"] == (
        "Z-CG-TVBCG5X-HG003-5X-D0-SPECIMEN"
    )
    assert manifests.rows["samples.tsv"][0]["SAMPLE_EUID"] == ("Z-CG-TVBCG5X-HG003-5X-SAMPLE")
    assert manifests.rows["libraries.tsv"][0]["LIBRARY_EUID"] == (
        "Z-CG-TVBCG5X-HG003-5X-D0-SR-LIBRARY"
    )
    assert source["ILMN_R1_PATH"] == (
        "/fsx/staging/staged_external_sequencing_data/complete-genomics-solo-six-manifest-v1/"
        "TVBCG5X/HG003/5x/lane-1/D0/T7plus_WGS_PE150_HG003_PCR_Free_Read_1.fq.gz"
    )
    receipt = (root / "staging_receipt.json").read_text(encoding="utf-8")
    assert '"state": "materialization_required"' in receipt
    assert "reviewed_planner_bundle" in receipt
    assert "Reserved Z- fixture identifiers only" in receipt
    assert "T7plus_WGS_PE150_HG003_PCR_Free_Read_1.fq.gz" in receipt


def test_complete_genomics_slim_mounted_reference_fixture_requires_fresh_pair_evidence(
    tmp_path: Path,
) -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "examples/staging/complete_genomics_solo_slim_mounted_reference_v1"
        / "analysis_samples_manifest.tsv"
    )
    root = generate_complete_genomics_slim_mounted_reference_six_manifest(
        source=source,
        output_dir=tmp_path / "complete-slim",
        reference_s3_uri="s3://lsmc-dayoa-references-usw2",
        reference_fsx_root="/fsx/references",
    )
    manifests = load_manifest_set(root)
    [sequencing_input] = manifests.rows["sequencing_inputs.tsv"]
    expected_paths = [
        (
            "/fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/complete_genomics/"
            "T7plus_WGS_PE150_HG003_PCR_Free/downsampled/"
            "T7plus_WGS_PE150_HG003_PCR_Free_10pct_Read_1.fq.gz"
        ),
        (
            "/fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/complete_genomics/"
            "T7plus_WGS_PE150_HG003_PCR_Free/downsampled/"
            "T7plus_WGS_PE150_HG003_PCR_Free_10pct_Read_2.fq.gz"
        ),
    ]
    assert [sequencing_input["ILMN_R1_PATH"], sequencing_input["ILMN_R2_PATH"]] == expected_paths
    planned = json.loads((root / "staging_receipt.json").read_text(encoding="utf-8"))
    assert planned["state"] == "materialization_required"
    assert planned["access_mode"] == "mounted_reference_dra"

    finalized = finalize_complete_genomics_slim_mounted_reference_materialization(
        manifest_dir=root,
        files_verified=[
            {
                "workflow_path": expected_paths[0],
                "size_bytes": 10251454933,
                "gzip_magic": "1f8b",
            },
            {
                "workflow_path": expected_paths[1],
                "size_bytes": 10405048250,
                "gzip_magic": "1f8b",
            },
        ],
        verified_at="2026-08-14T14:00:00+00:00",
        headnode={
            "cluster": "prod-cand-1703",
            "instance_id": "i-abc123",
            "ssm_command_id": "cmd-1",
        },
    )

    assert finalized["state"] == "materialized"
    assert finalized["materialization"]["copy_performed"] is False
    assert finalized["materialization"]["files_verified"][0]["size_bytes"] == 10251454933
