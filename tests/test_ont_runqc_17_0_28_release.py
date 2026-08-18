from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "config/daylily_pipeline_command_catalog.yaml"
PAYLOAD = (
    REPO_ROOT
    / "daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml"
)
DAYOA_TARGET_TAG = "15.0.24"
CURRENT_DAYOA_TARGET_TAG = "15.0.28"
DAYOA_VALIDATED_TAGS = {"15.0.1", "15.0.3", "15.0.9"}
HISTORICAL_DAYOA_TAG = "14.0.21"
ONT_RUN_ID = "pc1703-ont-set4fc1-seqqc-17018-20260814"
ONT_EVIDENCE_PREFIX = (
    "s3://lsmc-ssf-sequencing-data/derived/prod-cand-1703/"
    "pc1703-ont-set4fc1-seqqc-17018-20260814/daylily-omics-analysis/"
    "results/runs/20260615_ONT_Set4-FC1/run_qc/ont/"
)
CURRENT_ONT_EVIDENCE_PREFIX = (
    "s3://lsmc-ssf-sequencing-data/derived/pcand-18022/"
    "pcand18022_ont_seq_qc_15011_live_20260817T0752Z/daylily-omics-analysis/"
    "results/runs/20260615_ONT_Set4-FC1/run_qc/ont/"
)
CG_RUN_ID = "prod-cand-1703-cg-slim-20260814-1032"
BJUICE_RUN_ID = (
    "prod-cand-1703-hg002-slim5x5x-hiomr2-ifx-bjuice-v02-20260814T080546Z"
)
BJUICE_CURRENT_EVIDENCE_RUN_ID = "pcand18022-hg002-slim5x5x-bjuice-ifx-20260817t0648z"


def _run(command: dict, run_id: str) -> dict:
    return next(item for item in command.get("validation_runs", []) if item["run_id"] == run_id)


def test_current_catalog_promotion_preserves_17_0_28_evidence() -> None:
    assert SOURCE.read_bytes() == PAYLOAD.read_bytes()
    raw = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    repo = raw["repositories"]["daylily-omics-analysis"]
    active = {item["command_id"]: item for item in repo["analysis_commands"]}
    current = raw["dyec_builds"]["current"]

    assert repo["default_ref"] == CURRENT_DAYOA_TARGET_TAG
    assert current != raw["dyec_builds"]["17.0.28"]
    assert raw["dyec_builds"]["17.0.28"]["dayoa_git_tags"] == [HISTORICAL_DAYOA_TAG]
    assert current["dayoa_git_tags"] == [CURRENT_DAYOA_TARGET_TAG]
    assert {item["git_tag"] for item in active.values()} == {DAYOA_TARGET_TAG}
    assert {item["validated_version"] for item in active.values()} == DAYOA_VALIDATED_TAGS
    assert {item["git_tag"] for item in current["commands"].values()} == {
        CURRENT_DAYOA_TARGET_TAG
    }
    assert {
        item["validated_version"] for item in current["commands"].values()
    } == DAYOA_VALIDATED_TAGS | {"unvalidated"}

    for command in (active["ont_run_qc"], current["commands"]["ont_run_qc"]):
        record = _run(command, ONT_RUN_ID)
        assert record["status"] == "success"
        assert record["dryrun_status"] == "success"
        assert record["live_status"] == "success"
        assert record["stage_or_context"] == ONT_EVIDENCE_PREFIX
        assert record["report_path"] == ONT_EVIDENCE_PREFIX + "multiqc_report.html"
        assert record["dayec_tag"] == "17.0.18"
        assert record["dayoa_tag"] == "14.0.16"
        assert command["validation_evidence_s3_uri_prefix"] == CURRENT_ONT_EVIDENCE_PREFIX

    for command in (
        active["complete_genomics_cg_snv_concordance"],
        current["commands"]["complete_genomics_cg_snv_concordance"],
    ):
        assert _run(command, CG_RUN_ID)["status"] == "success"
        assert not command.get("validation_evidence_s3_uri_prefix")

    assert _run(active["inflection-bjuice-product-v0.2"], BJUICE_RUN_ID)["status"] == "success"
    alias_runs = current["aliases"]["inflection-bjuice-product-v0.2"][
        "metadata_overrides"
    ]["validation_runs"]
    assert [item["run_id"] for item in alias_runs] == [
        BJUICE_RUN_ID,
        BJUICE_CURRENT_EVIDENCE_RUN_ID,
    ]
