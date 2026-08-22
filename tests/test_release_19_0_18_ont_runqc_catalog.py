from __future__ import annotations

import copy
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CATALOG = REPO_ROOT / "config/daylily_pipeline_command_catalog.yaml"
PACKAGED_CATALOG = (
    REPO_ROOT / "daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml"
)


def test_19_0_18_removes_only_ont_runqc_rulegraph_from_19_0_17() -> None:
    assert SOURCE_CATALOG.read_bytes() == PACKAGED_CATALOG.read_bytes()
    builds = yaml.safe_load(SOURCE_CATALOG.read_text(encoding="utf-8"))["dyec_builds"]
    previous = builds["19.0.17"]
    expected = copy.deepcopy(previous)
    ont = expected["commands"]["ont_run_qc"]
    ont["dy_command"] = ont["dy_command"].replace(" --produce-rulegraph true", "")
    ont["dryrun_dy_command"] = ont["dryrun_dy_command"].replace(
        " --produce-rulegraph true", ""
    )

    assert builds["19.0.18"] == expected
    assert "--produce-analysis-artifact-manifest true" in ont["dy_command"]
    assert "--produce-rulegraph" not in ont["dy_command"]
    assert "--produce-rulegraph" in previous["commands"]["ont_run_qc"]["dy_command"]
