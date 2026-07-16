from __future__ import annotations

from pathlib import Path

import daylily_ec.cli  # noqa: F401 - initialize workflow imports before catalog model
from daylily_ec.repositories import CLUSTER_TYPES, load_repository_catalog


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CATALOG = REPO_ROOT / "config/daylily_pipeline_command_catalog.yaml"
PACKAGED_CATALOG = (
    REPO_ROOT
    / "daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml"
)


def test_hiomrs_catalog_entry_is_serial_native_dyr_and_mirrored() -> None:
    assert {"daywgs", "dragen", "sentieon-single"} <= CLUSTER_TYPES
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()

    command = load_repository_catalog(SOURCE_CATALOG).get_command(
        "hybrid_ilmn_ont_hiomrs"
    )
    expected_live = (
        "dy-r produce_hiomrs produce_snv_concordances --config "
        "'aligners=[\"ont\"]' 'dedupers=[\"na\"]' "
        "'snv_callers=[\"hiomrs\"]' 'sv_callers=[]' -j 1"
    )

    assert command.type == "dev"
    assert command.sample_manifest_template == (
        "examples/staging/hybrid_ilmn_ont_hg003_5x5x/"
        "analysis_samples_manifest.tsv"
    )
    assert command.targets == ["produce_hiomrs", "produce_snv_concordances"]
    assert command.jobs == 1
    assert command.keep_going is False
    assert command.restart_times == 0
    assert command.aligners == ["ont"]
    assert command.dedupers == ["na"]
    assert command.snv_callers == ["hiomrs"]
    assert command.sv_callers == []
    assert command.dy_command == expected_live
    assert command.dryrun_dy_command == f"{expected_live} -n"
    assert command.compatible_platforms == ["ILMN", "ONT"]
    assert command.compatible_cluster_types == ["sentieon-single"]
    assert command.compatible_data_modes == ["hybrid_ilmn_ont"]
    assert command.git_tag == "11.0.14"
    assert command.validated_version == "11.0.14"
    assert command.input_requirements.accepted_source_column_sets == [
        [
            "ILMN_R1_FQ",
            "ILMN_R2_FQ",
            "ONT_CRAM",
            "ONT_CRAM_ALIGNER",
            "ONT_CRAM_SNV_CALLER",
        ]
    ]

    for forbidden in ("bin/day_run", "sentdhiomr", " -k", ".partial", "rsync"):
        assert forbidden not in command.dy_command
        assert forbidden not in command.dryrun_dy_command


def test_hiomrs_kitchensink_has_explicit_native_targets_and_retires_hiomr() -> None:
    catalog = load_repository_catalog(SOURCE_CATALOG)
    command = catalog.get_command("hybrid_ilmn_ont_hiomrs_kitchensink")

    assert command.type == "dev"
    assert command.sample_manifest_template == (
        "examples/staging/hybrid_ilmn_ont_hg003_5x5x/"
        "analysis_samples_manifest.tsv"
    )
    assert command.targets == [
        "produce_hiomrs",
        "produce_snv_concordances",
        "produce_tiddit_sv_vcf",
        "produce_alignstats",
        "produce_relatedness",
        "produce_peddy",
        "produce_gatk_contam_estimate",
        "produce_site_mix_contam_estimate",
        "produce_vep",
        "produce_htd_calls",
        "produce_smn12_orthogonal_calls",
        "produce_metagenomics",
        "produce_multiqc_all",
        "results/day/hg38/reports/DAY_final_multiqc.html",
        "results/day/hg38/reports/dayoa_evidence_manifest.json",
    ]
    assert command.jobs == 250
    assert command.keep_going is False
    assert command.restart_times == 0
    assert command.aligners == ["sent"]
    assert command.dedupers == ["na"]
    assert command.snv_callers == ["hiomrs"]
    assert command.sv_callers == ["tiddit"]
    assert command.compatible_cluster_types == ["sentieon-single"]
    assert command.git_tag == "11.0.14"
    assert command.validated_version == "11.0.14"
    assert command.dy_command.startswith("dy-r produce_hiomrs ")
    assert command.dryrun_dy_command == f"{command.dy_command} -n"
    assert "produce_snv_concordances" in command.dy_command
    assert "produce_tiddit_sv_vcf" in command.dy_command
    assert "produce_smn12_orthogonal_calls" in command.dy_command
    assert "produce_metagenomics" in command.dy_command
    assert "produce_multiqc_all" in command.dy_command
    assert 'snv_callers=["hiomrs"]' in command.dy_command
    assert 'sv_callers=["tiddit"]' in command.dy_command
    assert 'htd_callers=["smn12"]' in command.dy_command
    assert command.dy_command.endswith(
        "-j 250 -p -T 0 --rerun-triggers mtime --rerun-incomplete"
    )
    for forbidden in ("sentdhiomr", "produce_expansionhunter", " -k"):
        assert forbidden not in command.dy_command
        assert forbidden not in command.dryrun_dy_command

    command_ids = {item.command_id for item in catalog.commands()}
    assert "hybrid_ilmn_ont_snv" not in command_ids
    assert "hybrid_ilmn_ont_snv_kitchensink" not in command_ids
