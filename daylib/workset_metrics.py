"""Utilities for gathering workset metrics on the head node."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

BYTES_PER_GIB = 1024 ** 3
S3_STANDARD_COST_PER_GB_MONTH = 0.023
DATA_TRANSFER_CROSS_REGION_PER_GB = 0.02
DATA_TRANSFER_INTERNET_PER_GB = 0.09

FASTQ_SUFFIXES = (".fastq", ".fastq.gz", ".fq", ".fq.gz")


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


def _gather_fastq_stats(units_path: Path, pipeline_dir: Path) -> Tuple[int, int]:
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
                            total_size += resolved.stat().st_size
                        except OSError:
                            continue
    return count, total_size


def _gather_pattern_stats(root: Path, pattern: str) -> Tuple[int, int]:
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
    return count, total


def _total_dir_size(root: Path) -> int:
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
    return total


def _parse_benchmark_costs(results_dir: Path) -> float:
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
                except ValueError:
                    continue
    return total


def gather_metrics(pipeline_dir: Path) -> Dict[str, object]:
    pipeline_dir = pipeline_dir.resolve()
    config_dir = pipeline_dir / "config"
    samples_path = config_dir / "samples.tsv"
    units_path = config_dir / "units.tsv"
    results_dir = pipeline_dir / "results"

    metrics: Dict[str, object] = {}
    metrics["samples_count"] = _count_rows(samples_path)
    metrics["sample_library_count"] = _count_rows(units_path)
    fastq_count, fastq_size = _gather_fastq_stats(units_path, pipeline_dir)
    metrics["fastq_count"] = fastq_count
    metrics["fastq_size_bytes"] = fastq_size

    cram_count, cram_size = _gather_pattern_stats(results_dir, "*.cram")
    metrics["cram_count"] = cram_count
    metrics["cram_size_bytes"] = cram_size

    vcf_count, vcf_size = _gather_pattern_stats(results_dir, "*.vcf.gz")
    metrics["vcf_count"] = vcf_count
    metrics["vcf_size_bytes"] = vcf_size

    results_size = _total_dir_size(results_dir)
    metrics["results_size_bytes"] = results_size

    if results_size:
        metrics["s3_daily_cost_usd"] = (
            (results_size / BYTES_PER_GIB) * S3_STANDARD_COST_PER_GB_MONTH / 30.0
        )
    else:
        metrics["s3_daily_cost_usd"] = 0.0

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
    metrics["ec2_cost_usd"] = _parse_benchmark_costs(results_dir)
    return metrics


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Collect metrics for a Daylily workset pipeline directory"
    )
    parser.add_argument("pipeline_dir", help="Path to the cloned pipeline directory")
    parser.add_argument(
        "--json", action="store_true", help="Emit metrics as JSON (default)"
    )
    args = parser.parse_args(argv)
    metrics = gather_metrics(Path(args.pipeline_dir))
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
