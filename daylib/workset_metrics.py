"""Utilities for gathering workset metrics on the head node."""

from __future__ import annotations

import argparse
import json
import os
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

BYTES_PER_GIB = 1024 ** 3
S3_STANDARD_COST_PER_GB_MONTH = 0.023
DATA_TRANSFER_CROSS_REGION_PER_GB = 0.02
DATA_TRANSFER_INTERNET_PER_GB = 0.09

FASTQ_SUFFIXES = (".fastq", ".fastq.gz", ".fq", ".fq.gz")


LOGGER = logging.getLogger("daylib.workset_metrics")


def _debug_command(debug: bool, metric: str, command: str) -> None:
    """Emit a debug log describing the action used to compute a metric."""

    if not debug:
        return
    LOGGER.debug("Gathering %s using: %s", metric, command)


def _count_rows(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if not line.strip():
                continue
            if count == 0:
                count += 1
                continue
            count += 1
    return max(0, count - 1)


def _iter_fastq_values(cell: str) -> Iterable[str]:
    if not cell:
        return []
    for delimiter in (";", ","):
        if delimiter in cell:
            return (part.strip() for part in cell.split(delimiter) if part.strip())
    return (cell.strip(),)


def _resolve_fastq_path(
    value: str, units_path: Path, pipeline_dir: Path
) -> Optional[Path]:
    candidate = Path(value)
    if candidate.exists():
        return candidate
    candidates = [
        units_path.parent / value,
        pipeline_dir / value,
        pipeline_dir / "sample_data" / value,
    ]
    for option in candidates:
        if option.exists():
            return option
    return None


def _gather_fastq_stats(
    units_path: Path, pipeline_dir: Path, *, debug: bool = False
) -> Tuple[int, int]:
    if not units_path.exists():
        return 0, 0
    count = 0
    total_size = 0
    with units_path.open("r", encoding="utf-8", errors="ignore") as handle:
        header = handle.readline()
        for line in handle:
            line = line.strip()
            if not line:
                continue
            for raw_value in line.split("\t"):
                for candidate in _iter_fastq_values(raw_value):
                    if not candidate:
                        continue
                    lower = candidate.lower()
                    if not any(lower.endswith(ext) for ext in FASTQ_SUFFIXES):
                        continue
                    count += 1
                    resolved = _resolve_fastq_path(candidate, units_path, pipeline_dir)
                    if resolved and resolved.exists():
                        try:
                            if debug:
                                LOGGER.debug(
                                    "Resolved FASTQ %s for metric fastq_size_bytes", resolved
                                )
                            total_size += resolved.stat().st_size
                        except OSError:
                            continue
    return count, total_size


def _gather_pattern_stats(
    root: Path, pattern: str, *, debug: bool = False
) -> Tuple[int, int]:
    if not root.exists():
        return 0, 0
    import fnmatch

    count = 0
    total = 0
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            if fnmatch.fnmatch(filename, pattern):
                count += 1
                full_path = Path(dirpath) / filename
                try:
                    total += full_path.stat().st_size
                except OSError:
                    continue
                if debug:
                    LOGGER.debug(
                        "Matched %s while searching for pattern %s", full_path, pattern
                    )
    return count, total


def _total_dir_size(root: Path, *, debug: bool = False) -> int:
    if not root.exists():
        return 0
    total = 0
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            full_path = Path(dirpath) / filename
            try:
                total += full_path.stat().st_size
            except OSError:
                continue
            if debug:
                LOGGER.debug("Counting size for %s", full_path)
    return total


def _parse_benchmark_costs(results_dir: Path, *, debug: bool = False) -> float:
    if not results_dir.exists():
        return 0.0
    total = 0.0
    for path in results_dir.rglob("benchmarks"):
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                if text.startswith("s\t") or text.startswith("s "):
                    continue
                parts = text.split()
                if not parts:
                    continue
                try:
                    total += float(parts[-1])
                    if debug:
                        LOGGER.debug("Read benchmark cost %.2f from %s", float(parts[-1]), path)
                except ValueError:
                    continue
    return total


def gather_metrics(pipeline_dir: Path, *, debug: bool = False) -> Dict[str, object]:
    pipeline_dir = pipeline_dir.resolve()
    config_dir = pipeline_dir / "config"
    samples_path = config_dir / "samples.tsv"
    units_path = config_dir / "units.tsv"
    results_dir = pipeline_dir / "results"

    metrics: Dict[str, object] = {}
    _debug_command(debug, "samples_count", f"count_rows {samples_path}")
    metrics["samples_count"] = _count_rows(samples_path)
    _debug_command(debug, "sample_library_count", f"count_rows {units_path}")
    metrics["sample_library_count"] = _count_rows(units_path)
    _debug_command(debug, "fastq_count", f"scan FASTQ paths from {units_path}")
    fastq_count, fastq_size = _gather_fastq_stats(
        units_path, pipeline_dir, debug=debug
    )
    metrics["fastq_count"] = fastq_count
    metrics["fastq_size_bytes"] = fastq_size

    _debug_command(debug, "cram_count", f"find {results_dir} pattern *.cram")
    cram_count, cram_size = _gather_pattern_stats(
        results_dir, "*.cram", debug=debug
    )
    metrics["cram_count"] = cram_count
    metrics["cram_size_bytes"] = cram_size

    _debug_command(debug, "vcf_count", f"find {results_dir} pattern *.vcf.gz")
    vcf_count, vcf_size = _gather_pattern_stats(
        results_dir, "*.vcf.gz", debug=debug
    )
    metrics["vcf_count"] = vcf_count
    metrics["vcf_size_bytes"] = vcf_size

    _debug_command(debug, "results_size_bytes", f"du -sb {results_dir}")
    results_size = _total_dir_size(results_dir, debug=debug)
    metrics["results_size_bytes"] = results_size

    if results_size:
        metrics["s3_daily_cost_usd"] = (
            (results_size / BYTES_PER_GIB) * S3_STANDARD_COST_PER_GB_MONTH / 30.0
        )
    else:
        metrics["s3_daily_cost_usd"] = 0.0

    _debug_command(debug, "s3_daily_cost_usd", "calculate from results_size_bytes")
    metrics["cram_transfer_cross_region_cost"] = (
        cram_size / BYTES_PER_GIB * DATA_TRANSFER_CROSS_REGION_PER_GB
        if cram_size
        else 0.0
    )
    metrics["cram_transfer_internet_cost"] = (
        cram_size / BYTES_PER_GIB * DATA_TRANSFER_INTERNET_PER_GB
        if cram_size
        else 0.0
    )
    metrics["vcf_transfer_cross_region_cost"] = (
        vcf_size / BYTES_PER_GIB * DATA_TRANSFER_CROSS_REGION_PER_GB
        if vcf_size
        else 0.0
    )
    metrics["vcf_transfer_internet_cost"] = (
        vcf_size / BYTES_PER_GIB * DATA_TRANSFER_INTERNET_PER_GB
        if vcf_size
        else 0.0
    )
    _debug_command(debug, "transfer_costs", "derive from cram/vcf sizes")
    metrics["ec2_cost_usd"] = _parse_benchmark_costs(results_dir, debug=debug)
    return metrics


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Collect metrics for a Daylily workset pipeline directory"
    )
    parser.add_argument("pipeline_dir", help="Path to the cloned pipeline directory")
    parser.add_argument(
        "--json", action="store_true", help="Emit metrics as JSON (default)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print commands executed to compute each metric",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    metrics = gather_metrics(Path(args.pipeline_dir), debug=args.debug)
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
