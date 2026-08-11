from pathlib import Path

from daylily_ec.complete_genomics_manifest import generate_complete_genomics_six_manifest
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
