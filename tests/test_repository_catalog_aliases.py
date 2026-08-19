from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from daylily_ec.repositories import AnalysisCommand, load_repository_catalog

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "config/daylily_pipeline_command_catalog.yaml"
PACKAGED_CATALOG_PATH = (
    REPO_ROOT / "daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml"
)
BASE_ID = "hiomr2_slim_kitchensink_mega"
ALIAS_ID = "inflection-bjuice-product-v0.2"
HISTORICAL_ALIAS_BUILD = "18.0.50"
OLD_DUPLICATED_ID = "hiomr2_slim_kitchensink_mega_inflection_analytical"
PCAND18015_SOLO_EVIDENCE_RUNS = {
    "illumina_hg002_kitchensink_multiqc": "pcand18015_ilmn_solo_slim_1510_ccenter_20260817t020600z_live",
    "ont_snv_alignstats_kitchensink": "pcand18015_ont_solo_slim_1510_ccenter_20260817t020900z_live",
    "ultima_snv_alignstats_kitchensink": "pcand18015_ultima_solo_slim_1510_ccenter_20260817t021200z_live",
}
PCAND18022_RUNQC_EVIDENCE_RUNS = {
    "illumina_run_qc": "pcand18022_ilmn_seq_qc_15011_live_20260817T0712Z",
    "ont_run_qc": "pcand18022_ont_seq_qc_15011_live_20260817T0752Z",
    "ultima_run_qc": "pcand18022_ultima_seq_qc_15011_live_20260817T0734Z",
}
RUNQC_EVIDENCE_PREFIXES = {
    "illumina_run_qc": (
        "s3://lsmc-ssf-sequencing-data/derived/pre-rel-18025/"
        "prerel18025_ilm_seq_qc_18026_15015_20260817T1427Z/"
        "daylily-omics-analysis/results/runs/20260618_LH01106_0011_A23MFMCLT3/"
        "run_qc/illumina/"
    ),
    "ont_run_qc": (
        "s3://lsmc-ssf-sequencing-data/derived/pcand-18022/"
        "pcand18022_ont_seq_qc_15011_live_20260817T0752Z/"
        "daylily-omics-analysis/results/runs/20260615_ONT_Set4-FC1/run_qc/ont/"
    ),
    "ultima_run_qc": (
        "s3://lsmc-ssf-sequencing-data/derived/pcand-18022/"
        "pcand18022_ultima_seq_qc_15011_live_20260817T0734Z/"
        "daylily-omics-analysis/results/runs/604834-20260717_2309/run_qc/ultima/"
    ),
}
PCAND18022_BJUICE_EVIDENCE_RUNS = {
    "inflection-bjuice-product-v0.2": "pcand18022-hg002-slim5x5x-bjuice-ifx-20260817t0648z",
    "hiomr2_slim_kitchensink_mega": "pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z",
}
NEW_TOP_LEVEL_COMMAND_IDS = {"inflection-bjuice-product-v0.9"}
REMOVED_TOP_LEVEL_COMMAND_IDS = {
    "bjuice-v2-hg002-multi-analysis-unit-hiomr2-kitchensink-mega-inflection-analytical"
}
NEW_CURRENT_COMMAND_IDS = NEW_TOP_LEVEL_COMMAND_IDS | {
    "bjuice-v2-hg002-custom-multi-analysis-unit-hiomr2-kitchensink-mega",
    "illumina_sentieon_pangenome_kitchensink",
    "ultima_sentieon_pangenome_kitchensink",
}
def _raw_catalog() -> dict:
    return yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))


def _load_mutation(tmp_path: Path, mutate) -> object:  # noqa: ANN001
    raw = _raw_catalog()
    mutate(raw)
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return load_repository_catalog(path)


def _metadata_alias(command_id: str, alias_of: str) -> dict:
    return {
        "command_id": command_id,
        "alias_of": alias_of,
        "metadata_overrides": {"display_name": f"Alias {command_id}"},
    }


def test_historical_alias_resolves_to_an_analysis_command_and_renders_extensions() -> None:
    catalog = load_repository_catalog(CATALOG_PATH)
    build = catalog.dyec_builds[HISTORICAL_ALIAS_BUILD]
    base = catalog.get_command_for_dyec_build(BASE_ID, HISTORICAL_ALIAS_BUILD)
    alias = catalog.get_command_for_dyec_build(ALIAS_ID, HISTORICAL_ALIAS_BUILD)

    assert isinstance(base, AnalysisCommand)
    assert isinstance(alias, AnalysisCommand)
    assert BASE_ID in build.commands
    assert ALIAS_ID not in build.commands
    assert ALIAS_ID in build.aliases
    assert ALIAS_ID not in catalog.dyec_builds["current"].aliases
    assert build.aliases[ALIAS_ID].alias_of == BASE_ID
    assert base.git_tag == "15.0.28"
    assert alias.git_tag == base.git_tag
    assert base.targets == ["produce_sentdhiomr2_slim_kitchensink_mega"]
    assert alias.targets == [
        "produce_sentdhiomr2_slim_kitchensink_mega",
        "produce_sentdhiomr2_inflection_analytical_package",
    ]
    assert "produce_sentdhiomr2_inflection_analytical_package" not in base.dy_command
    assert "produce_sentdhiomr2_inflection_analytical_package" in alias.dy_command
    assert "hiomr2_inflection_package_mode=analytical" in alias.dy_command
    assert '"seqone_delivery_batch_id=$ANALYSIS_ID"' in alias.dy_command
    assert alias.dryrun_dy_command == f"{alias.dy_command} -n"
    assert alias.display_name.startswith("Inflection BJuice")
    assert alias.description.startswith("BJuice analytical-product alias")
    assert "schema-2.2 analytical Inflection package" in alias.description
    assert alias.return_results is False

    previous_alias = catalog.get_command_for_dyec_build(ALIAS_ID, "17.0.8")
    released_alias = catalog.get_command_for_dyec_build(ALIAS_ID, "17.0.9")
    assert "schema-2.0 analytical Inflection package" in previous_alias.description
    assert "schema-2.1 analytical Inflection package" in released_alias.description

    launch = alias.launch_argv(
        analysis_id="alias-render",
        executing_entity="fixture-user",
        manifest_dir="/tmp/six-manifest",
        dry_run=True,
    )
    rendered = launch[launch.index("--dy-command") + 1]
    assert "$ANALYSIS_ID" not in rendered
    assert "seqone_delivery_batch_id=alias-render" in rendered


def test_existing_accessors_resolve_frozen_aliases_but_not_removed_current_aliases() -> None:
    catalog = load_repository_catalog(CATALOG_PATH)

    with pytest.raises(KeyError, match="Unknown analysis command"):
        catalog.get_command(ALIAS_ID)
    with pytest.raises(KeyError, match="not eligible for DYEC build 'current'"):
        catalog.get_command_for_dyec_build(ALIAS_ID)
    assert isinstance(
        catalog.get_command_for_dyec_build(ALIAS_ID, HISTORICAL_ALIAS_BUILD),
        AnalysisCommand,
    )
    assert isinstance(catalog.get_command_for_dyec_build(ALIAS_ID, "17.0.2"), AnalysisCommand)
    assert isinstance(catalog.get_command_for_dyec_build(ALIAS_ID, "17.0.3"), AnalysisCommand)
    assert isinstance(catalog.get_command_for_dyec_build(ALIAS_ID, "17.0.4"), AnalysisCommand)
    assert isinstance(catalog.get_command_for_dyec_build(ALIAS_ID, "17.0.5"), AnalysisCommand)
    assert isinstance(catalog.get_command_for_dyec_build(ALIAS_ID, "17.0.6"), AnalysisCommand)
    assert isinstance(catalog.get_command_for_dyec_build(ALIAS_ID, "17.0.7"), AnalysisCommand)
    assert isinstance(catalog.get_command_for_dyec_build(ALIAS_ID, "17.0.8"), AnalysisCommand)
    assert isinstance(catalog.get_command_for_dyec_build(ALIAS_ID, "17.0.9"), AnalysisCommand)
    assert ALIAS_ID not in {command.command_id for command in catalog.commands()}
    payload = catalog.to_public_payload()
    assert ALIAS_ID not in payload["dyec_builds"]["current"]["aliases"]
    assert ALIAS_ID not in {command["command_id"] for command in payload["commands"]}


def test_alias_can_use_mutually_exclusive_complete_command_replacement(tmp_path: Path) -> None:
    def mutate(raw: dict) -> None:
        base = raw["dyec_builds"]["current"]["commands"][BASE_ID]
        raw["dyec_builds"]["current"]["aliases"]["independent-command"] = {
            "command_id": "independent-command",
            "alias_of": BASE_ID,
            "metadata_overrides": {
                "display_name": "Independent command",
                "description": "Uses the base metadata with an independent command closure.",
            },
            "replace": {
                "targets": ["produce_sentdhiomr2_slim_consensus"],
                "dy_command": base["dy_command"].replace(
                    "produce_sentdhiomr2_slim_kitchensink_mega",
                    "produce_sentdhiomr2_slim_consensus",
                ),
                "dryrun_dy_command": base["dryrun_dy_command"].replace(
                    "produce_sentdhiomr2_slim_kitchensink_mega",
                    "produce_sentdhiomr2_slim_consensus",
                ),
            },
        }

    catalog = _load_mutation(tmp_path, mutate)
    command = catalog.get_command("independent-command")
    assert command.targets == ["produce_sentdhiomr2_slim_consensus"]
    assert "produce_sentdhiomr2_slim_consensus" in command.dy_command
    assert "produce_sentdhiomr2_slim_kitchensink_mega" not in command.dy_command


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda raw: raw["dyec_builds"]["current"]["aliases"].update(
                {
                    "base-alias": _metadata_alias("base-alias", BASE_ID),
                    "chain": _metadata_alias("chain", "base-alias"),
                }
            ),
            "chain or cycle",
        ),
        (
            lambda raw: raw["dyec_builds"]["current"]["aliases"].update(
                {
                    "cycle-a": _metadata_alias("cycle-a", "cycle-b"),
                    "cycle-b": _metadata_alias("cycle-b", "cycle-a"),
                }
            ),
            "chain or cycle",
        ),
        (
            lambda raw: raw["dyec_builds"]["current"]["aliases"].update(
                {"missing": _metadata_alias("missing", "not-a-command")}
            ),
            "missing same-build base command",
        ),
        (
            lambda raw: raw["dyec_builds"]["current"]["aliases"].update(
                {"cross-build": _metadata_alias("cross-build", f"17.0.1/{BASE_ID}")}
            ),
            "cross-build reference",
        ),
        (
            lambda raw: raw["dyec_builds"]["current"]["aliases"].update(
                {BASE_ID: _metadata_alias(BASE_ID, BASE_ID)}
            ),
            "Duplicate DYEC build command and alias id",
        ),
        (
            lambda raw: raw["dyec_builds"]["current"]["aliases"].update(
                {
                    "duplicate-a": _metadata_alias("duplicate", BASE_ID),
                    "duplicate-b": _metadata_alias("duplicate", BASE_ID),
                }
            ),
            "Duplicate DYEC build alias command id",
        ),
    ],
)
def test_alias_rejects_non_one_hop_or_duplicate_id_shapes(
    tmp_path: Path, mutate, message: str  # noqa: ANN001
) -> None:
    with pytest.raises(ValidationError, match=message):
        _load_mutation(tmp_path, mutate)


def test_alias_rejects_partial_or_mixed_replacement(tmp_path: Path) -> None:
    def partial(raw: dict) -> None:
        raw["dyec_builds"]["current"]["aliases"]["partial"] = {
            "command_id": "partial",
            "alias_of": BASE_ID,
            "replace": {
                "targets": ["produce_sentdhiomr2_slim_consensus"],
                "dy_command": "dy-r produce_sentdhiomr2_slim_consensus",
            },
        }

    with pytest.raises(ValidationError, match="dryrun_dy_command"):
        _load_mutation(tmp_path, partial)

    def mixed(raw: dict) -> None:
        base = raw["dyec_builds"]["current"]["commands"][BASE_ID]
        raw["dyec_builds"]["current"]["aliases"]["mixed"] = {
            "command_id": "mixed",
            "alias_of": BASE_ID,
            "extend": {"targets": ["produce_sentdhiomr2_slim_consensus"]},
            "replace": {
                "targets": ["produce_sentdhiomr2_slim_consensus"],
                "dy_command": base["dy_command"],
                "dryrun_dy_command": base["dryrun_dy_command"],
            },
        }

    with pytest.raises(ValidationError, match="mutually exclusive"):
        _load_mutation(tmp_path, mixed)


def test_alias_config_extension_fails_without_a_single_config_anchor(tmp_path: Path) -> None:
    def mutate(raw: dict) -> None:
        raw["dyec_builds"]["current"]["aliases"]["bad-config-anchor"] = {
            "command_id": "bad-config-anchor",
            "alias_of": "simple-test",
            "extend": {"config": [{"key": "mode", "value": "analytical"}]},
        }

    with pytest.raises(ValidationError, match="exactly one --config token"):
        _load_mutation(tmp_path, mutate)


def test_catalog_version_five_rejects_aliases(tmp_path: Path) -> None:
    def mutate(raw: dict) -> None:
        raw["command_catalog_version"] = 5

    with pytest.raises(ValidationError, match="aliases require command_catalog_version 6"):
        _load_mutation(tmp_path, mutate)


def test_current_snapshot_history_and_packaged_payload_retain_active_semantics() -> None:
    assert CATALOG_PATH.read_bytes() == PACKAGED_CATALOG_PATH.read_bytes()

    raw = _raw_catalog()
    packaged = yaml.safe_load(PACKAGED_CATALOG_PATH.read_text(encoding="utf-8"))
    tagged_source = subprocess.check_output(
        ["git", "show", "18.0.58:config/daylily_pipeline_command_catalog.yaml"],
        cwd=REPO_ROOT,
        text=True,
    )
    tagged = yaml.safe_load(tagged_source)

    assert raw["repositories"] == packaged["repositories"]
    assert raw["dyec_builds"]["current"] == packaged["dyec_builds"]["current"]
    assert raw["repositories"] == tagged["repositories"]
    assert raw["repositories"]["daylily-omics-analysis"]["default_ref"] == "15.0.37"
    assert {
        command["git_tag"]
        for command in raw["repositories"]["daylily-omics-analysis"]["analysis_commands"]
    } == {"15.0.28"}
    assert raw["dyec_builds"]["current"] == tagged["dyec_builds"]["current"]
    assert raw["dyec_builds"]["current"]["dayoa_git_tags"] == ["15.0.37"]
    assert {
        command["git_tag"]
        for command in raw["dyec_builds"]["current"]["commands"].values()
    } == {"15.0.37"}
    assert raw["dyec_builds"]["18.0.58"] == tagged["dyec_builds"]["18.0.58"]

    current = raw["dyec_builds"]["current"]
    historical_alias_build = raw["dyec_builds"][HISTORICAL_ALIAS_BUILD]
    assert current["aliases"] == {}
    assert ALIAS_ID not in current["commands"]
    assert ALIAS_ID in historical_alias_build["aliases"]
    assert historical_alias_build["aliases"][ALIAS_ID]["alias_of"] == BASE_ID
    assert historical_alias_build["dayoa_git_tags"] == ["15.0.28"]
    assert OLD_DUPLICATED_ID not in current["commands"]
    assert OLD_DUPLICATED_ID not in current["aliases"]
    for build in ("16.1.82", "16.1.85", "16.1.86", "17.0.0", "17.0.1"):
        assert OLD_DUPLICATED_ID in raw["dyec_builds"][build]["commands"]
def test_two_hiomr2_catalog_commands_exclude_unwanted_callers_and_mergers() -> None:
    catalog = load_repository_catalog(CATALOG_PATH)
    commands = (
        catalog.get_command(BASE_ID),
        catalog.get_command_for_dyec_build(ALIAS_ID, HISTORICAL_ALIAS_BUILD),
    )
    for command in commands:
        assert command.targets[0] == "produce_sentdhiomr2_slim_kitchensink_mega"
        for unwanted in (
            "manta",
            "dysgu",
            "severus",
            "jasmine",
            "survivor",
            "octopusv",
            "sniffles1",
            "iris",
            "produce_sentdhiomr2_nicu_research",
        ):
            assert unwanted not in command.dy_command.casefold()
            assert all(unwanted not in target.casefold() for target in command.targets)
