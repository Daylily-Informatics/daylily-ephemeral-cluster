#!/usr/bin/env python3
"""Collect remaining-GIAB evidence with the established compact collector."""

from __future__ import annotations

import importlib.util
from pathlib import Path


COLLECTOR = Path(__file__).with_name("20260804T173058Z_collect_take333lc_report_evidence.py")
OUTPUT = Path("/Users/jmajor/Downloads/remaining-giab-hiomr2-final-report/source-data")


def main() -> int:
    print(f"loading={COLLECTOR}", flush=True)
    spec = importlib.util.spec_from_file_location("take333lc_collector", COLLECTOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load collector: {COLLECTOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    print("collector_loaded=true", flush=True)
    module.ROOT = "/fsx/analysis_results/preval-hiomr2/remaining-giab"
    module.OUTPUT = OUTPUT
    print(f"output={OUTPUT}", flush=True)
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
