from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from importlib.machinery import SourceFileLoader


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "bin"
    / "daylily-stage-samples-from-local-to-headnode"
)


def _load_stage_script():
    loader = SourceFileLoader("daylily_stage_samples_from_local_to_headnode", str(SCRIPT_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


def test_headnode_visible_path_maps_data_prefix_to_fsx() -> None:
    module = _load_stage_script()

    assert module.headnode_visible_path("/data") == "/fsx/data"
    assert (
        module.headnode_visible_path("/data/staged_sample_data/remote_stage_1")
        == "/fsx/data/staged_sample_data/remote_stage_1"
    )
    assert module.headnode_visible_path("/tmp/local") == "/tmp/local"
