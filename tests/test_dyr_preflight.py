from __future__ import annotations

import pytest

from daylily_ec.workflow.dyr_preflight import (
    DyrPreflightOptionsError,
    normalize_dyr_preflight_options,
)


def test_normalizer_applies_dyec_defaults() -> None:
    command = normalize_dyr_preflight_options("bin/day_run target -j 20")

    assert "--produce-analysis-artifact-manifest" not in command
    assert "--produce-rulegraph false" in command
    assert "--produce-filegraph false" in command
    assert "--produce-dag true" in command


def test_explicit_command_values_beat_defaults() -> None:
    command = normalize_dyr_preflight_options(
        "source dyoainit; dy-a slurm hg38; dy-r target --produce-rulegraph false"
    )

    assert command.startswith("source dyoainit; dy-a slurm hg38; dy-r target ")
    assert command.count("--produce-rulegraph") == 1
    assert "--produce-rulegraph false" in command


def test_top_level_overrides_beat_command_values() -> None:
    command = normalize_dyr_preflight_options(
        "dy-r target --produce-dag=false",
        overrides={"--produce-dag": True},
    )

    assert "--produce-dag true" in command


def test_removed_global_manifest_option_is_not_normalized() -> None:
    command = normalize_dyr_preflight_options(
        "dy-r target --produce-analysis-artifact-manifest true"
    )

    assert "--produce-analysis-artifact-manifest true" in command
    assert "--produce-dag true" in command


@pytest.mark.parametrize(
    "command,match",
    [
        ("echo test", "exactly one"),
        ("dy-r one; dy-r two", "found 2"),
        ("dy-r one --produce-dag maybe", "requires true or false"),
        (
            "dy-r one --produce-dag true --produce-dag false",
            "may be specified only once",
        ),
    ],
)
def test_normalizer_rejects_malformed_commands(command: str, match: str) -> None:
    with pytest.raises(DyrPreflightOptionsError, match=match):
        normalize_dyr_preflight_options(command)


def test_all_disabled_allows_non_dyr_utility_command() -> None:
    command = normalize_dyr_preflight_options(
        "echo utility",
        overrides={
            "--produce-rulegraph": False,
            "--produce-filegraph": False,
            "--produce-dag": False,
        },
    )

    assert command == "echo utility"
