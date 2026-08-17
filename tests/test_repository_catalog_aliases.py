from __future__ import annotations

import hashlib
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
HISTORICAL_BUILD_HASHES = {
    "16.1.81": "219606c84c6a24b12ad84499580788b46301549b9c521c3583a6ddf07c869fc9",
    "16.1.82": "106dded9e9d8329966d418b08217c0d674ec22fb5795388565ce7e6f7b511ed5",
    "16.1.85": "67ae45a0184c0f1e316616ddcf239479aa50f9a4635eb6da86d2ee3588d7c747",
    "16.1.86": "3386317b17f07335e4decf339ad54a6120f7ad3ec99f1e3e24ec21e9629b3f10",
    "17.0.0": "4b8766a3a4c639c99c08fb702a391b5cbb6455921c2d3e333f0b8953387bc384",
    "17.0.1": "4e2650a84868f6a732e015d495a53ecd40878389fd34d242dc70cd7c7c7a7c31",
    "17.0.2": "a423e38640be95bf7f64726331a308e6fe566b4214789661e75ccf3af939df10",
    "17.0.3": "a36b3eabdd4c3d6e8d22cca31543b739b2ab63ef556e4c7390ec9b657390d243",
    "17.0.4": "ed70d79c7e35d65dee4625ea9e039402aa5a3bd84ab520534b418a83b57a6d77",
    "17.0.5": "d7ef1dabbb31130358ca3e99357bdb742a2c198e1452f076977d46acd47ab0b0",
    "17.0.6": "b8cb52a26e74a4757850f048d3f903df45393014cc596db50ad97ae27b4242b6",
    "17.0.7": "55d2e0e106dfb61f8aa38c28b8f4cf2c24b1efcbe486832fe9ca1666d1cf051f",
    "17.0.8": "6dac4a6f5724191ee1c930a07d209b29c90c1a8171b2574d0afc94e1628efc8e",
    "17.0.9": "8065f45dec35d88277dba5e0d2b2995eaab84829b029fe337c25be0ce1001ce7",
    "17.0.10": "9542314e9433e62020aa43f61e9375eb73ce7e7432f6cb1553c36d23daab027c",
    "17.0.11": "45bdfcb75f6cc67bdbf7054ae29d63ad687d5c7abaa5bb7cb0bea9eabdbb278c",
    "17.0.12": "0b1b6eb5bd1b00ce492c15cd18f91ce0cd1398deabe1e4e989d5398f441fceeb",
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


def _raw_build_blocks(text: str) -> dict[str, bytes]:
    tail = text[text.index("dyec_builds:\n") + len("dyec_builds:\n") :]
    starts: list[tuple[str, int]] = []
    offset = 0
    for line in tail.splitlines(keepends=True):
        if line.startswith("  ") and not line.startswith("    ") and line.rstrip().endswith(":"):
            starts.append((line.strip()[:-1], offset))
        offset += len(line)
    return {
        key: tail[start : starts[index + 1][1] if index + 1 < len(starts) else len(tail)].encode()
        for index, (key, start) in enumerate(starts)
    }


def test_current_alias_resolves_to_an_analysis_command_and_renders_extensions() -> None:
    catalog = load_repository_catalog(CATALOG_PATH)
    build = catalog.dyec_builds["current"]
    base = catalog.get_command(BASE_ID)
    alias = catalog.get_command(ALIAS_ID)

    assert isinstance(base, AnalysisCommand)
    assert isinstance(alias, AnalysisCommand)
    assert BASE_ID in build.commands
    assert ALIAS_ID not in build.commands
    assert ALIAS_ID in build.aliases
    assert build.aliases[ALIAS_ID].alias_of == BASE_ID
    assert base.git_tag == "15.0.12"
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


def test_existing_accessors_and_public_payload_return_resolved_aliases() -> None:
    catalog = load_repository_catalog(CATALOG_PATH)

    assert isinstance(catalog.get_command(ALIAS_ID), AnalysisCommand)
    assert isinstance(catalog.get_command_for_dyec_build(ALIAS_ID), AnalysisCommand)
    assert isinstance(catalog.get_command_for_dyec_build(ALIAS_ID, "17.0.2"), AnalysisCommand)
    assert isinstance(catalog.get_command_for_dyec_build(ALIAS_ID, "17.0.3"), AnalysisCommand)
    assert isinstance(catalog.get_command_for_dyec_build(ALIAS_ID, "17.0.4"), AnalysisCommand)
    assert isinstance(catalog.get_command_for_dyec_build(ALIAS_ID, "17.0.5"), AnalysisCommand)
    assert isinstance(catalog.get_command_for_dyec_build(ALIAS_ID, "17.0.6"), AnalysisCommand)
    assert isinstance(catalog.get_command_for_dyec_build(ALIAS_ID, "17.0.7"), AnalysisCommand)
    assert isinstance(catalog.get_command_for_dyec_build(ALIAS_ID, "17.0.8"), AnalysisCommand)
    assert isinstance(catalog.get_command_for_dyec_build(ALIAS_ID, "17.0.9"), AnalysisCommand)
    assert ALIAS_ID in {command.command_id for command in catalog.commands()}
    payload = catalog.to_public_payload()
    assert ALIAS_ID in payload["dyec_builds"]["current"]["aliases"]
    payload_alias = next(
        command for command in payload["commands"] if command["command_id"] == ALIAS_ID
    )
    assert payload_alias["targets"][-1] == "produce_sentdhiomr2_inflection_analytical_package"


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
                {"chain": _metadata_alias("chain", ALIAS_ID)}
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


def test_current_snapshot_history_and_packaged_payload_are_exact() -> None:
    source = CATALOG_PATH.read_text(encoding="utf-8")
    assert CATALOG_PATH.read_bytes() == PACKAGED_CATALOG_PATH.read_bytes()
    raw = yaml.safe_load(source)
    baseline_source = subprocess.check_output(
        ["git", "show", "18.0.17:config/daylily_pipeline_command_catalog.yaml"],
        cwd=REPO_ROOT,
        text=True,
    )
    baseline = yaml.safe_load(baseline_source)

    assert raw["dyec_builds"]["current"] != raw["dyec_builds"]["17.0.29"]
    assert raw["repositories"]["daylily-omics-analysis"]["default_ref"] == "15.0.12"
    assert raw["dyec_builds"]["current"]["dayoa_git_tags"] == ["15.0.12"]
    assert {
        command["git_tag"]
        for command in raw["repositories"]["daylily-omics-analysis"]["analysis_commands"]
    } == {"15.0.12"}
    assert {
        command["git_tag"]
        for command in raw["dyec_builds"]["current"]["commands"].values()
    } == {"15.0.12"}
    top_level_commands = {
        command["command_id"]
        for command in raw["repositories"]["daylily-omics-analysis"]["analysis_commands"]
    }
    baseline_top_level_commands = {
        command["command_id"]: command
        for command in baseline["repositories"]["daylily-omics-analysis"]["analysis_commands"]
    }
    for command in raw["repositories"]["daylily-omics-analysis"]["analysis_commands"]:
        baseline_command = baseline_top_level_commands[command["command_id"]]
        assert command["validated_version"] == baseline_command["validated_version"]
        if command["command_id"] in PCAND18015_SOLO_EVIDENCE_RUNS:
            assert command.get("validation_runs", [])[:-1] == baseline_command.get(
                "validation_runs", []
            )
            assert command["validation_runs"][-1]["run_id"] == PCAND18015_SOLO_EVIDENCE_RUNS[
                command["command_id"]
            ]
            assert command["validation_evidence_s3_uri_prefix"].startswith(
                "s3://lsmc-ssf-sequencing-data/derived/pcand-18015/"
            )
        elif command["command_id"] in PCAND18022_RUNQC_EVIDENCE_RUNS:
            assert command.get("validation_runs", [])[:-1] == baseline_command.get(
                "validation_runs", []
            )
            assert command["validation_runs"][-1]["run_id"] == PCAND18022_RUNQC_EVIDENCE_RUNS[
                command["command_id"]
            ]
            assert command["validation_evidence_s3_uri_prefix"].startswith(
                "s3://lsmc-ssf-sequencing-data/derived/pcand-18022/"
            )
        else:
            assert command.get("validation_runs", []) == baseline_command.get(
                "validation_runs", []
            )
    assert top_level_commands == set(baseline_top_level_commands)
    for command_id, command in raw["dyec_builds"]["current"]["commands"].items():
        baseline_command = baseline["dyec_builds"]["current"]["commands"][command_id]
        assert command["validated_version"] == baseline_command["validated_version"]
        if command_id in PCAND18015_SOLO_EVIDENCE_RUNS:
            assert command.get("validation_runs", [])[:-1] == baseline_command.get(
                "validation_runs", []
            )
            assert command["validation_runs"][-1]["run_id"] == PCAND18015_SOLO_EVIDENCE_RUNS[
                command_id
            ]
            assert command["validation_evidence_s3_uri_prefix"].startswith(
                "s3://lsmc-ssf-sequencing-data/derived/pcand-18015/"
            )
        elif command_id in PCAND18022_RUNQC_EVIDENCE_RUNS:
            assert command.get("validation_runs", [])[:-1] == baseline_command.get(
                "validation_runs", []
            )
            assert command["validation_runs"][-1]["run_id"] == PCAND18022_RUNQC_EVIDENCE_RUNS[
                command_id
            ]
            assert command["validation_evidence_s3_uri_prefix"].startswith(
                "s3://lsmc-ssf-sequencing-data/derived/pcand-18022/"
            )
        else:
            assert command.get("validation_runs", []) == baseline_command.get(
                "validation_runs", []
            )
    assert raw["dyec_builds"]["current"]["aliases"] == baseline["dyec_builds"]["current"]["aliases"]
    assert raw["dyec_builds"]["17.0.29"]["dayoa_git_tags"] == ["14.0.22"]
    assert raw["dyec_builds"]["17.0.16"]["dayoa_git_tags"] == ["14.0.16"]
    assert raw["dyec_builds"]["17.0.17"]["dayoa_git_tags"] == [
        "14.0.14",
        "14.0.15",
    ]
    assert raw["dyec_builds"]["17.0.15"]["dayoa_git_tags"] == [
        "14.0.14",
        "14.0.15",
    ]
    assert raw["dyec_builds"]["17.0.14"]["dayoa_git_tags"] == ["14.0.14"]
    assert raw["dyec_builds"]["17.0.13"]["dayoa_git_tags"] == ["14.0.14"]
    assert raw["dyec_builds"]["17.0.2"]["dayoa_git_tags"] == ["14.0.3"]
    assert raw["dyec_builds"]["17.0.3"]["dayoa_git_tags"] == ["14.0.4"]
    assert raw["dyec_builds"]["17.0.4"]["dayoa_git_tags"] == ["14.0.6"]
    assert raw["dyec_builds"]["17.0.5"]["dayoa_git_tags"] == ["14.0.7"]
    assert raw["dyec_builds"]["17.0.6"]["dayoa_git_tags"] == ["14.0.8"]
    assert raw["dyec_builds"]["17.0.7"]["dayoa_git_tags"] == ["14.0.9"]
    assert raw["dyec_builds"]["17.0.8"]["dayoa_git_tags"] == ["14.0.9"]
    assert raw["dyec_builds"]["17.0.9"]["dayoa_git_tags"] == ["14.0.10"]
    assert raw["dyec_builds"]["17.0.10"]["dayoa_git_tags"] == ["14.0.11"]
    assert raw["dyec_builds"]["17.0.11"]["dayoa_git_tags"] == ["14.0.13"]
    assert raw["dyec_builds"]["17.0.12"]["dayoa_git_tags"] == ["14.0.13"]
    assert OLD_DUPLICATED_ID not in raw["dyec_builds"]["current"]["commands"]
    assert OLD_DUPLICATED_ID not in raw["dyec_builds"]["current"]["aliases"]
    for build in ("16.1.82", "16.1.85", "16.1.86", "17.0.0", "17.0.1"):
        assert OLD_DUPLICATED_ID in raw["dyec_builds"][build]["commands"]

    blocks = _raw_build_blocks(source)
    baseline_blocks = _raw_build_blocks(baseline_source)
    assert {
        build: hashlib.sha256(blocks[build]).hexdigest()
        for build in blocks
        if build != "current"
    } == {
        build: hashlib.sha256(baseline_blocks[build]).hexdigest()
        for build in baseline_blocks
        if build != "current"
    }
    assert {
        build: hashlib.sha256(blocks[build]).hexdigest() for build in HISTORICAL_BUILD_HASHES
    } == HISTORICAL_BUILD_HASHES


def test_two_hiomr2_catalog_commands_exclude_unwanted_callers_and_mergers() -> None:
    catalog = load_repository_catalog(CATALOG_PATH)
    for command_id in (BASE_ID, ALIAS_ID):
        command = catalog.get_command(command_id)
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
