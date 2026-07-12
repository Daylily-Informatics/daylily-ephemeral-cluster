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
    assert command.git_tag == "sentieon-single"
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
