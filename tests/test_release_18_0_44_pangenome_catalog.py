from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from daylily_ec.repositories import load_repository_catalog


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CATALOG = REPO_ROOT / "config/daylily_pipeline_command_catalog.yaml"
PACKAGED_CATALOG = (
    REPO_ROOT
    / "daylily_ec"
    / "resources"
    / "payload"
    / "config"
    / "daylily_pipeline_command_catalog.yaml"
)
DYEC_RELEASE = "18.0.44"
DAYOA_RELEASE = "15.0.26"
BASELINE_DYEC_RELEASE = "18.0.43"

NINE_EXISTING_LANE_IDS = (
    "hiomr2_slim_kitchensink_mega",
    "inflection-bjuice-product-v0.9",
    "illumina_run_qc",
    "ont_run_qc",
    "ultima_run_qc",
    "illumina_hg002_kitchensink_multiqc",
    "ont_snv_alignstats_kitchensink",
    "ultima_snv_alignstats_kitchensink",
    "complete_genomics_cg_snv_concordance",
)
PANGENOME_LANE_IDS = (
    "illumina_sentieon_pangenome_kitchensink",
    "ultima_sentieon_pangenome_kitchensink",
)
ALL_LANE_IDS = NINE_EXISTING_LANE_IDS + PANGENOME_LANE_IDS


def _raw_catalog() -> dict:
    return yaml.safe_load(SOURCE_CATALOG.read_text(encoding="utf-8"))


def _release_tag_catalog() -> dict:
    source = subprocess.check_output(
        ["git", "show", f"{BASELINE_DYEC_RELEASE}:config/daylily_pipeline_command_catalog.yaml"],
        cwd=REPO_ROOT,
        text=True,
    )
    return yaml.safe_load(source)


def _render_kwargs(command) -> dict[str, str]:
    kwargs: dict[str, str] = {}
    if command.input_contract == "six_manifest":
        kwargs["manifest_dir"] = "/tmp/pre-rel-18025-manifests"
    elif command.input_contract == "run_context":
        kwargs["run_context_file"] = "config/runs.tsv"
    if command.cost_center_required:
        kwargs["cost_center"] = "pre-rel-18025-ccenter"
    return kwargs


def test_18_0_44_is_a_current_parity_snapshot_pinned_only_to_dayoa_15_0_25() -> None:
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()
    raw = _raw_catalog()
    release = raw["dyec_builds"][DYEC_RELEASE]
    current = raw["dyec_builds"]["current"]
    baseline = _release_tag_catalog()

    assert release == current
    assert raw["repositories"]["daylily-omics-analysis"]["default_ref"] == DAYOA_RELEASE
    assert release["dayoa_git_tags"] == [DAYOA_RELEASE]
    assert {command["git_tag"] for command in release["commands"].values()} == {DAYOA_RELEASE}
    assert raw["dyec_builds"][BASELINE_DYEC_RELEASE] == baseline["dyec_builds"][
        BASELINE_DYEC_RELEASE
    ]
    assert raw["dyec_builds"][BASELINE_DYEC_RELEASE]["dayoa_git_tags"] == ["15.0.24"]


def test_18_0_44_all_eleven_production_lanes_have_exact_rc0_controller_shapes() -> None:
    catalog = load_repository_catalog(SOURCE_CATALOG)

    for command_id in ALL_LANE_IDS:
        command = catalog.get_command_for_dyec_build(command_id, DYEC_RELEASE)

        assert command.type == "prod"
        assert command.git_tag == DAYOA_RELEASE
        assert command.genome == "hg38"
        assert command.jobs == 333
        assert command.dy_command.startswith(
            ("bin/day_run ", "DAY_CONTAINERIZED=true dy-r ")
        )
        if command_id in PANGENOME_LANE_IDS:
            assert command.dy_command.startswith("bin/day_run ")
            assert command.validated_version == "unvalidated"
            assert command.validation_pending is True
        assert " -j 333 -T 0 -p" in command.dy_command
        assert command.dryrun_dy_command == f"{command.dy_command} -n"

        argv = command.launch_argv(
            analysis_id="release-18044-catalog-render",
            executing_entity="pre-rel-18025",
            dry_run=True,
            **_render_kwargs(command),
        )
        rendered = argv[argv.index("--dy-command") + 1]
        assert argv[argv.index("--git-tag") + 1] == DAYOA_RELEASE
        assert argv[argv.index("--genome") + 1] == "hg38"
        assert "--dry-run" in argv
        assert command.targets[0] in rendered
        assert " -j 333 -T 0 -p" in rendered
        assert " -n" in rendered


def test_18_0_44_pangenome_lanes_use_graph_targets_without_a_pangenome_genome_build() -> None:
    catalog = load_repository_catalog(SOURCE_CATALOG)
    illumina = catalog.get_command_for_dyec_build(
        "illumina_sentieon_pangenome_kitchensink", DYEC_RELEASE
    )
    ultima = catalog.get_command_for_dyec_build(
        "ultima_sentieon_pangenome_kitchensink", DYEC_RELEASE
    )
    standard_illumina = catalog.get_command_for_dyec_build(
        "illumina_hg002_kitchensink_multiqc", DYEC_RELEASE
    )
    standard_ultima = catalog.get_command_for_dyec_build(
        "ultima_snv_alignstats_kitchensink", DYEC_RELEASE
    )

    assert illumina.input_contract == "six_manifest"
    assert illumina.aligners == ["sent", "pangenome_sr"]
    assert illumina.dedupers == ["dmd"]
    assert illumina.snv_callers == ["sentd", "sentpg"]
    assert illumina.input_requirements.required_source_columns == ["ILMN_R1_FQ", "ILMN_R2_FQ"]
    assert illumina.targets == [
        *standard_illumina.targets[:3],
        "produce_sentpg_sr_snv_vcf",
        *standard_illumina.targets[3:],
    ]
    assert "'htd_callers=[\"cyrius\"]'" in illumina.dy_command

    assert ultima.input_contract == "six_manifest"
    assert ultima.aligners == ["ug", "pangenome_ug"]
    assert ultima.dedupers == ["na"]
    assert ultima.snv_callers == ["sentdug", "sentpg"]
    assert ultima.input_requirements.required_source_columns == ["ULTIMA_CRAM", "ULTIMA_CRAM_ALIGNER"]
    assert ultima.targets == [
        *standard_ultima.targets[:3],
        "produce_sentpg_ug_snv_vcf",
        *standard_ultima.targets[3:],
    ]

    for command in (illumina, ultima):
        assert command.genome == "hg38"
        assert "'genome_build=hg38'" in command.dy_command
        assert "spmd" not in command.dedupers
        assert "genome_build=pangenome" not in command.dy_command


def test_18_0_44_leaves_legacy_dev_pangenome_closures_unmodified() -> None:
    raw = _raw_catalog()
    baseline = _release_tag_catalog()
    commands = raw["dyec_builds"][DYEC_RELEASE]["commands"]
    baseline_commands = baseline["dyec_builds"][BASELINE_DYEC_RELEASE]["commands"]

    expected_targets = {
        "illumina_pangenome_snv": ["produce_sentpg_snv_vcf"],
        "ultima_pangenome_snv": ["produce_pangenome_ug_vcf"],
    }
    for command_id, targets in expected_targets.items():
        command = commands[command_id]
        baseline_command = baseline_commands[command_id]
        assert command["type"] == "dev"
        assert command["targets"] == targets
        assert command["dy_command"] == baseline_command["dy_command"]
        assert command["dryrun_dy_command"] == baseline_command["dryrun_dy_command"]
        assert command["aligners"] == baseline_command["aligners"]
        assert command["dedupers"] == baseline_command["dedupers"]
        assert command["snv_callers"] == baseline_command["snv_callers"]
