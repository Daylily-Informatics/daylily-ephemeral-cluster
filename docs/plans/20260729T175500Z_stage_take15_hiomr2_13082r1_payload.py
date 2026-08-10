#!/usr/bin/env python3
"""Run the declared Take15 r1 payload staging helper at one fresh path only."""

from __future__ import annotations

import importlib.util
from pathlib import Path


PLAN_DIR = Path(__file__).resolve().parent
SOURCE = PLAN_DIR / "20260729T173700Z_stage_take15_hiomr2_13082_payload.py"
spec = importlib.util.spec_from_file_location("take15_13082_stage", SOURCE)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot load declared staging helper: {SOURCE}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.REMOTE_ROOT = "/home/ubuntu/t15s_13082r1"
module.FILES = dict(module.FILES)
module.FILES["ledger.md"] = (
    PLAN_DIR / "20260729T175500Z_take15_hg003_na23687_hiomr2_13082r1_execution_ledger.md"
)


if __name__ == "__main__":
    module.main()
