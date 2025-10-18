#!/usr/bin/env python3
"""Generate reports for Daylily worksets."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional, Sequence

from daylib.workset_monitor import MonitorConfig, WorksetMonitor, configure_logging

LOGGER = logging.getLogger("daylily.workset_report.cli")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a report of the monitored worksets",
    )
    parser.add_argument("config", type=Path, help="Path to the YAML configuration file")
    parser.add_argument(
        "target",
        nargs="?",
        default="term",
        help="Report destination: 'term', a local .tsv/.csv file, or an s3:// URI",
    )
    parser.add_argument(
        "--process-directory",
        dest="process_directories",
        metavar="NAME",
        nargs="+",
        help="Only include the specified workset directory names",
    )
    parser.add_argument(
        "--min-deets",
        "-min-deets",
        action="store_true",
        dest="min_deets",
        help="Limit reports to the legacy summary columns",
    )
    parser.add_argument(
        "--include-archive",
        action="store_true",
        dest="include_archive",
        help="Include archived worksets in the report",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--force-recalculate",
        action="store_true",
        dest="force_recalculate",
        help="Recalculate all remote workset metrics regardless of cache",
    )
    return parser.parse_args(argv)


def validate_target(target: str) -> None:
    if target.lower() == "term":
        return
    if target.startswith("s3://"):
        if target.lower().endswith(".csv") or target.lower().endswith(".tsv"):
            return
        raise argparse.ArgumentTypeError("s3 targets must end with .csv or .tsv")
    suffix = Path(target).suffix.lower()
    if suffix not in {".csv", ".tsv"}:
        raise argparse.ArgumentTypeError("target must be 'term' or a .csv/.tsv file path")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        validate_target(args.target)
    except argparse.ArgumentTypeError as exc:
        LOGGER.error("%s", exc)
        return 2

    configure_logging(args.verbose)

    config = MonitorConfig.load(args.config)
    monitor = WorksetMonitor(
        config,
        dry_run=True,
        debug=False,
        process_directories=args.process_directories,
        attempt_restart=False,
        force_recalculate_metrics=args.force_recalculate,
    )

    monitor.report(
        args.target,
        min_details=args.min_deets,
        include_archive=args.include_archive,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
