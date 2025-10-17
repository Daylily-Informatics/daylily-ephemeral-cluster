"""Utilities for collecting and formatting workset metrics."""

from __future__ import annotations

import argparse
import contextlib
import csv
import json
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple

S3_STANDARD_COST_PER_GB_MONTH = 0.023
INTER_REGION_DATA_TRANSFER_COST_PER_GB = 0.02
INTERNET_DATA_TRANSFER_COST_PER_GB = 0.09
BYTES_PER_GIB = 1024 ** 3


@dataclass
class WorksetMetrics:
    """Raw metric values gathered from a workset clone directory."""

    samples: int = 0
    sample_libraries: int = 0
    fastq_files: int = 0
    fastq_bytes: int = 0
    cram_files: int = 0
    cram_bytes: int = 0
    vcf_files: int = 0
    vcf_bytes: int = 0
    results_bytes: int = 0
    ec2_cost: float = 0.0

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


def _read_table_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        try:
            next(reader)
        except StopIteration:
            return 0
        return sum(1 for _ in reader)


def _collect_fastq_stats(units_path: Path) -> Tuple[int, int]:
    if not units_path.exists():
        return 0, 0
    fastq_paths = set()
    with units_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            for value in row.values():
                if not value:
                    continue
                candidate = value.strip()
                if not candidate:
                    continue
                lower = candidate.lower()
                if lower.endswith((".fastq", ".fastq.gz")):
                    fastq_paths.add(candidate)
    total_bytes = 0
    for entry in fastq_paths:
        path = Path(entry)
        if not path.is_absolute():
            candidate = units_path.parent / entry
            if candidate.exists():
                path = candidate
            else:
                candidate = (units_path.parent / ".." / entry).resolve()
                if candidate.exists():
                    path = candidate
        if path.exists() and path.is_file():
            with contextlib.suppress(OSError):
                total_bytes += path.stat().st_size
    return len(fastq_paths), total_bytes


def _sum_sizes(paths: Iterable[Path]) -> Tuple[int, int]:
    count = 0
    total = 0
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        count += 1
        total += stat.st_size
    return count, total


def _scan_results(results_dir: Path, suffix: str) -> Tuple[int, int]:
    return _sum_sizes(p for p in results_dir.rglob(f"*{suffix}") if p.is_file())


def _sum_directory_bytes(results_dir: Path) -> int:
    total = 0
    for path in results_dir.rglob("*"):
        if path.is_file():
            with contextlib.suppress(OSError):
                total += path.stat().st_size
    return total


def _sum_ec2_cost(results_dir: Path) -> float:
    total = 0.0
    for path in results_dir.rglob("benchmarks"):
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("s\t") or line.startswith("s "):
                    continue
                parts = line.split()
                if not parts:
                    continue
                try:
                    total += float(parts[-1])
                except ValueError:
                    continue
    return total


def collect_metrics(pipeline_root: Path) -> WorksetMetrics:
    pipeline_root = pipeline_root.resolve()
    config_dir = pipeline_root / "config"
    results_dir = pipeline_root / "results"
    metrics = WorksetMetrics()

    metrics.samples = _read_table_count(config_dir / "samples.tsv")
    metrics.sample_libraries = _read_table_count(config_dir / "units.tsv")

    fastq_count, fastq_bytes = _collect_fastq_stats(config_dir / "units.tsv")
    metrics.fastq_files = fastq_count
    metrics.fastq_bytes = fastq_bytes

    if results_dir.exists():
        metrics.cram_files, metrics.cram_bytes = _scan_results(results_dir, ".cram")
        metrics.vcf_files, metrics.vcf_bytes = _scan_results(results_dir, ".vcf.gz")
        metrics.results_bytes = _sum_directory_bytes(results_dir)
        metrics.ec2_cost = _sum_ec2_cost(results_dir)

    return metrics


def bytes_to_gib(value: int) -> float:
    if value <= 0:
        return 0.0
    return value / BYTES_PER_GIB


def format_gib(value: int) -> str:
    gib = bytes_to_gib(value)
    return f"{gib:.2f} GB"


def format_currency(value: float) -> str:
    return f"${value:.2f}"


def storage_daily_cost(total_bytes: int) -> float:
    gib = bytes_to_gib(total_bytes)
    monthly_cost = gib * S3_STANDARD_COST_PER_GB_MONTH
    return monthly_cost / 30.0


def transfer_costs(total_bytes: int) -> Tuple[float, float]:
    gib = bytes_to_gib(total_bytes)
    return gib * INTER_REGION_DATA_TRANSFER_COST_PER_GB, gib * INTERNET_DATA_TRANSFER_COST_PER_GB


def metrics_json(pipeline_root: Path) -> str:
    metrics = collect_metrics(pipeline_root)
    return json.dumps(metrics.as_dict())


def remote_metrics_script() -> str:
    """Return a standalone Python script that prints metrics as JSON.

    The returned script is embedded in SSH commands so that the monitor can
    gather metrics without requiring this module to be installed on the
    headnode. Keep the script self-contained and avoid external dependencies.
    """

    return textwrap.dedent(
        f"""
        import contextlib
        import csv
        import json
        from pathlib import Path

        S3_STANDARD_COST_PER_GB_MONTH = {S3_STANDARD_COST_PER_GB_MONTH}
        INTER_REGION_DATA_TRANSFER_COST_PER_GB = {INTER_REGION_DATA_TRANSFER_COST_PER_GB}
        INTERNET_DATA_TRANSFER_COST_PER_GB = {INTERNET_DATA_TRANSFER_COST_PER_GB}
        BYTES_PER_GIB = {BYTES_PER_GIB}

        def _read_table_count(path):
            if not path.exists():
                return 0
            with path.open("r", encoding="utf-8") as handle:
                reader = csv.reader(handle, delimiter="\t")
                try:
                    next(reader)
                except StopIteration:
                    return 0
                return sum(1 for _ in reader)

        def _collect_fastq_stats(units_path):
            if not units_path.exists():
                return 0, 0
            fastq_paths = set()
            with units_path.open("r", encoding="utf-8") as handle:
                reader = csv.DictReader(handle, delimiter="\t")
                for row in reader:
                    for value in row.values():
                        if not value:
                            continue
                        candidate = value.strip()
                        if not candidate:
                            continue
                        lower = candidate.lower()
                        if lower.endswith((".fastq", ".fastq.gz")):
                            fastq_paths.add(candidate)
            total_bytes = 0
            for entry in fastq_paths:
                path = Path(entry)
                if not path.is_absolute():
                    candidate = units_path.parent / entry
                    if candidate.exists():
                        path = candidate
                    else:
                        candidate = (units_path.parent / ".." / entry).resolve()
                        if candidate.exists():
                            path = candidate
                if path.exists() and path.is_file():
                    with contextlib.suppress(OSError):
                        total_bytes += path.stat().st_size
            return len(fastq_paths), total_bytes

        def _sum_sizes(paths):
            count = 0
            total = 0
            for path in paths:
                if not path.exists() or not path.is_file():
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                count += 1
                total += stat.st_size
            return count, total

        def _scan_results(results_dir, suffix):
            return _sum_sizes(p for p in results_dir.rglob(f"*{{suffix}}") if p.is_file())

        def _sum_directory_bytes(results_dir):
            total = 0
            for path in results_dir.rglob("*"):
                if path.is_file():
                    with contextlib.suppress(OSError):
                        total += path.stat().st_size
            return total

        def _sum_ec2_cost(results_dir):
            total = 0.0
            for path in results_dir.rglob("benchmarks"):
                if not path.is_file():
                    continue
                with path.open("r", encoding="utf-8", errors="ignore") as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("s\t") or line.startswith("s "):
                            continue
                        parts = line.split()
                        if not parts:
                            continue
                        try:
                            total += float(parts[-1])
                        except ValueError:
                            continue
            return total

        root = Path('.').resolve()
        config_dir = root / 'config'
        results_dir = root / 'results'

        samples = _read_table_count(config_dir / 'samples.tsv')
        sample_libraries = _read_table_count(config_dir / 'units.tsv')
        fastq_count, fastq_bytes = _collect_fastq_stats(config_dir / 'units.tsv')

        cram_files = cram_bytes = vcf_files = vcf_bytes = results_bytes = 0
        ec2_cost = 0.0
        if results_dir.exists():
            cram_files, cram_bytes = _scan_results(results_dir, '.cram')
            vcf_files, vcf_bytes = _scan_results(results_dir, '.vcf.gz')
            results_bytes = _sum_directory_bytes(results_dir)
            ec2_cost = _sum_ec2_cost(results_dir)

        print(
            json.dumps(
                {{
                    'samples': samples,
                    'sample_libraries': sample_libraries,
                    'fastq_files': fastq_count,
                    'fastq_bytes': fastq_bytes,
                    'cram_files': cram_files,
                    'cram_bytes': cram_bytes,
                    'vcf_files': vcf_files,
                    'vcf_bytes': vcf_bytes,
                    'results_bytes': results_bytes,
                    'ec2_cost': ec2_cost,
                }}
            )
        )
        """
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect workset pipeline directory metrics")
    parser.add_argument("pipeline", type=Path, help="Path to the pipeline working tree")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human readable output")
    args = parser.parse_args(list(argv) if argv is not None else None)

    metrics = collect_metrics(args.pipeline)
    if args.json:
        print(json.dumps(metrics.as_dict()))
        return 0

    print(f"Samples: {metrics.samples}")
    print(f"Sample libraries: {metrics.sample_libraries}")
    print(f"Fastqs: {metrics.fastq_files} ({format_gib(metrics.fastq_bytes)})")
    print(f"CRAMs: {metrics.cram_files} ({format_gib(metrics.cram_bytes)})")
    print(f"VCFs: {metrics.vcf_files} ({format_gib(metrics.vcf_bytes)})")
    print(f"Results size: {format_gib(metrics.results_bytes)}")
    print(f"EC2 task cost: {format_currency(metrics.ec2_cost)}")
    print(
        "S3 daily cost: "
        f"{format_currency(storage_daily_cost(metrics.results_bytes))}"
    )
    region_cost, internet_cost = transfer_costs(metrics.cram_bytes)
    print(
        "CRAM transfer cost: "
        f"region {format_currency(region_cost)}, internet {format_currency(internet_cost)}"
    )
    region_cost, internet_cost = transfer_costs(metrics.vcf_bytes)
    print(
        "VCF transfer cost: "
        f"region {format_currency(region_cost)}, internet {format_currency(internet_cost)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
