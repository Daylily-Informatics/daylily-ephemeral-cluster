#!/usr/bin/env python3
"""Collect a bounded read-only snapshot from the live 20-AU E4 experiment.

Run this script on the E4 headnode. It reads only small report inputs and raw
benchmark TSVs, validates their schemas, and writes one compact JSON snapshot.
It never invokes DayOA, Snakemake, Slurm, or an export operation.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ANALYSIS_ID = "prerel18025-bjuice-v2-hg002-20au-18042-20260818t1255z-live"
DEFAULT_ANALYSIS_ROOT = Path("/fsx/analysis_results/pre-rel-18025") / ANALYSIS_ID
EXPECTED_SOURCE_AUS = (
    "HG002-ilmn0p5x-ont0p5x-h01",
    "HG002-ilmn0p5x-ont4x-h08",
    "HG002-ilmn0p5x-ont12x-h24",
    "HG002-ilmn0p5x-ont30x-h72",
    "HG002-ilmn2x-ont0p5x-h01",
    "HG002-ilmn2x-ont4x-h08",
    "HG002-ilmn2x-ont12x-h24",
    "HG002-ilmn2x-ont30x-h72",
    "HG002-ilmn10x-ont0p5x-h01",
    "HG002-ilmn10x-ont4x-h08",
    "HG002-ilmn10x-ont12x-h24",
    "HG002-ilmn10x-ont30x-h72",
    "HG002-ilmn20x-ont0p5x-h01",
    "HG002-ilmn20x-ont4x-h08",
    "HG002-ilmn20x-ont12x-h24",
    "HG002-ilmn20x-ont30x-h72",
    "HG002-ilmn5x-ont30x-h72",
    "HG002-ilmn15x-ont30x-h72",
    "HG002-ilmn30x-ont30x-h72",
    "HG002-ilmn43p73x-ont30x-h72",
)
CALLER_NAMES = {
    "tagged_trussv": "TrussSV",
    "sniffles2": "Sniffles2",
    "longreadsv": "LongReadSV",
    "tiddit": "TIDDIT",
}
BENCHMARK_FIELDS = (
    "sample",
    "status",
    "rule",
    "s",
    "task_cost",
    "cpu_time",
    "snakemake_threads",
    "start_datetime",
    "end_datetime",
    "attempt",
    "snakemake_jobid",
    "slurm_jobid",
    "source_path",
    "source_sha256",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-root", type=Path, default=DEFAULT_ANALYSIS_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames or any(not name for name in reader.fieldnames):
            raise ValueError(f"missing TSV header: {path}")
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"duplicate TSV header: {path}")
        rows = list(reader)
    if any(None in row for row in rows):
        raise ValueError(f"row wider than TSV header: {path}")
    return rows


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_relative(path: Path, dayoa_root: Path) -> str:
    return str(path.relative_to(dayoa_root))


def metadata(path: Path, dayoa_root: Path, category: str) -> dict[str, Any]:
    stat = path.stat()
    return {
        "category": category,
        "relative_path": source_relative(path, dayoa_root),
        "bytes": stat.st_size,
        "mtime_epoch": int(stat.st_mtime),
        "sha256": sha256_file(path),
    }


def exactly_one(paths: list[Path], label: str) -> Path:
    if len(paths) != 1:
        raise ValueError(f"expected exactly one {label}; found {len(paths)}")
    return paths[0]


def total_mean(path: Path) -> str:
    rows = read_tsv(path)
    matches = [row for row in rows if row.get("chrom") == "total"]
    if len(matches) != 1 or not matches[0].get("mean"):
        raise ValueError(f"expected one chrom=total mean in {path}")
    float(matches[0]["mean"])
    return matches[0]["mean"]


def segdup_counts(path: Path) -> tuple[int, int]:
    passed = 0
    failed = 0
    with gzip.open(path, "rt") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 10:
                raise ValueError(f"malformed SegDup VCF row in {path}")
            sample = dict(zip(fields[8].split(":"), fields[9].split(":")))
            alleles = re.split(r"[/|]", sample.get("GT", "NA"))
            if not any(allele not in {"0", ".", ""} for allele in alleles):
                continue
            if fields[6] == "PASS":
                passed += 1
            else:
                failed += 1
    return passed, failed


def git_value(dayoa_root: Path, *args: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(dayoa_root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def derive_benchmark_rule(path: Path, runtime_au: str) -> str:
    suffix = ".bench.tsv"
    if not path.name.endswith(suffix):
        raise ValueError(f"not a benchmark TSV: {path}")
    tokens = path.name[: -len(suffix)].split(".")
    matches = [index for index, token in enumerate(tokens) if token == runtime_au]
    if len(matches) != 1:
        raise ValueError(f"benchmark filename does not contain one exact AU token: {path}")
    del tokens[matches[0]]
    if not tokens:
        raise ValueError(f"benchmark filename has no rule after AU removal: {path}")
    return ".".join(tokens)


def collect_benchmarks(
    results_root: Path,
    unit_root: Path,
    runtime_au: str,
    dayoa_root: Path,
) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, str]]]:
    paths = set(unit_root.glob("benchmarks/**/*.bench.tsv"))
    global_root = results_root / "benchmarks"
    if global_root.is_dir():
        paths.update(
            path
            for path in global_root.rglob("*.bench.tsv")
            if runtime_au in path.name.removesuffix(".bench.tsv").split(".")
        )
    records: list[dict[str, str]] = []
    inventory: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for path in sorted(paths):
        item = metadata(path, dayoa_root, "benchmark")
        inventory.append(item)
        try:
            rows = read_tsv(path)
            rule = derive_benchmark_rule(path, runtime_au)
        except Exception as error:
            rejected.append({"source_path": source_relative(path, dayoa_root), "reason": str(error)})
            continue
        if not rows:
            rejected.append({"source_path": source_relative(path, dayoa_root), "reason": "header only; no completed attempt"})
            continue
        for row_number, row in enumerate(rows, start=2):
            if row.get("status") != "success":
                rejected.append(
                    {
                        "source_path": source_relative(path, dayoa_root),
                        "reason": f"row {row_number} status={row.get('status') or 'missing'}",
                    }
                )
                continue
            try:
                float(row["s"])
                if row.get("task_cost"):
                    float(row["task_cost"])
                if row.get("cpu_time"):
                    float(row["cpu_time"])
                if row.get("snakemake_threads"):
                    float(row["snakemake_threads"])
            except (KeyError, TypeError, ValueError) as error:
                rejected.append(
                    {
                        "source_path": source_relative(path, dayoa_root),
                        "reason": f"row {row_number} invalid successful benchmark: {error}",
                    }
                )
                continue
            normalized = {
                "sample": runtime_au,
                "status": "success",
                "rule": rule,
                "s": row.get("s", ""),
                "task_cost": row.get("task_cost", ""),
                "cpu_time": row.get("cpu_time", ""),
                "snakemake_threads": row.get("snakemake_threads", ""),
                "start_datetime": row.get("start_datetime", ""),
                "end_datetime": row.get("end_datetime", ""),
                "attempt": row.get("attempt", ""),
                "snakemake_jobid": row.get("snakemake_jobid", ""),
                "slurm_jobid": row.get("slurm_jobid", ""),
                "source_path": item["relative_path"],
                "source_sha256": item["sha256"],
            }
            records.append({field: normalized[field] for field in BENCHMARK_FIELDS})
    return records, inventory, rejected


def main() -> None:
    args = parse_args()
    captured_at_start = utc_now()
    analysis_root = args.analysis_root.resolve()
    dayoa_root = analysis_root / "daylily-omics-analysis"
    results_root = dayoa_root / "results/day/hg38"
    manifest_root = results_root / "reports/input_manifests"
    config_path = dayoa_root / "config/analysis_units.tsv"
    identity_path = manifest_root / "analysis_unit_identity_audit.tsv"
    resolved_units_path = manifest_root / "analysis_units.tsv"
    status_path = dayoa_root / "status.json"

    source_units = read_tsv(config_path)
    resolved_units = read_tsv(resolved_units_path)
    identities = read_tsv(identity_path)
    source_ids = {row.get("ANALYSIS_UNIT_UID") for row in source_units}
    resolved_ids = {row.get("ANALYSIS_UNIT_UID") for row in resolved_units}
    expected_ids = set(EXPECTED_SOURCE_AUS)
    if source_ids != expected_ids or resolved_ids != expected_ids:
        raise ValueError("E4 source analysis-unit set does not match the reviewed 20-AU plan")
    if len(identities) != 20:
        raise ValueError(f"expected 20 runtime identities; found {len(identities)}")
    source_to_runtime = {row["SOURCE_ANALYSIS_UNIT_UID"]: row["RUNTIME_ANALYSIS_UNIT_UID"] for row in identities}
    if set(source_to_runtime) != expected_ids or len(set(source_to_runtime.values())) != 20:
        raise ValueError("E4 source/runtime identity mapping is incomplete or non-unique")

    inventory = [
        metadata(config_path, dayoa_root, "manifest"),
        metadata(resolved_units_path, dayoa_root, "manifest"),
        metadata(identity_path, dayoa_root, "manifest"),
        metadata(status_path, dayoa_root, "workflow_status"),
    ]
    status_start = json.loads(status_path.read_text())
    output: dict[str, Any] = {
        "schema_version": "lsmc.hg002_bjuice_e4_compact_evidence.v1",
        "analysis_id": ANALYSIS_ID,
        "analysis_root": str(analysis_root),
        "dayoa_root": str(dayoa_root),
        "captured_at_start_utc": captured_at_start,
        "capture_contract": {
            "workflow_state": "in-flight read-only snapshot",
            "coverage_axes": "native SR sentdhiomr2sr/smd by LR sentdhiomr2lr/na",
            "rsr_role": "audit only",
            "benchmark_scope": "successful raw benchmark attempts present at snapshot; not final workflow accounting",
        },
        "dayoa_git": {
            "commit": git_value(dayoa_root, "rev-parse", "HEAD"),
            "exact_tag": git_value(dayoa_root, "describe", "--tags", "--exact-match"),
        },
        "workflow_status_start": status_start,
        "units": source_units,
        "resolved_units": resolved_units,
        "identity": identities,
        "coverage": {},
        "hard_vcf": {},
        "truvari": {},
        "smn12": {},
        "segdup": {},
        "benchmarks": [],
        "benchmark_rejections": [],
        "completeness": {},
        "inventory": inventory,
    }

    gene_sets: list[set[str]] = []
    for source_au in EXPECTED_SOURCE_AUS:
        runtime_au = source_to_runtime[source_au]
        unit_root = results_root / runtime_au
        sr_path = exactly_one(
            sorted(unit_root.glob("align/sentdhiomr2sr/smd/alignqc/mosdepth/*.mosdepth.summary.txt")),
            f"{runtime_au} native-SR Mosdepth summary",
        )
        rsr_path = exactly_one(
            sorted(unit_root.glob("align/sentdhiomr2rsr/na/alignqc/mosdepth/*.mosdepth.summary.txt")),
            f"{runtime_au} RSR Mosdepth summary",
        )
        lr_path = exactly_one(
            sorted(unit_root.glob("align/sentdhiomr2lr/na/alignqc/mosdepth/*.mosdepth.summary.txt")),
            f"{runtime_au} LR Mosdepth summary",
        )
        hard_path = exactly_one(
            sorted(unit_root.glob("align/sentmm2ont/na/snv/sentdhiomr2/concordance/_giabHC/*_concordance.mqc.tsv")),
            f"{runtime_au} hard-VCF GIAB-HC TSV",
        )
        smn_path = exactly_one(
            sorted(unit_root.glob("align/sentdhiomr2sr/smd/htd/smn12/*.summary.json")),
            f"{runtime_au} SMN12 JSON",
        )
        truvari_paths = sorted(
            unit_root.glob("align/sentmm2ont/na/snv/sentdhiomr2/slim-consensus/truvari/*/queries/*/truvari/summary.json")
        )
        segdup_paths = sorted(
            unit_root.glob("align/sentmm2ont/na/snv/sentdhiomr2/segdup/*/*/*.result.vcf.gz")
        )
        if len(truvari_paths) != 4:
            raise ValueError(f"{runtime_au}: expected four Truvari summaries; found {len(truvari_paths)}")
        if len(segdup_paths) != 15:
            raise ValueError(f"{runtime_au}: expected 15 SegDup VCFs; found {len(segdup_paths)}")

        core_paths = [sr_path, rsr_path, lr_path, hard_path, smn_path, *truvari_paths, *segdup_paths]
        output["inventory"].extend(metadata(path, dayoa_root, "core_metric") for path in core_paths)
        output["coverage"][runtime_au] = {
            "native_sr": total_mean(sr_path),
            "rsr": total_mean(rsr_path),
            "lr": total_mean(lr_path),
            "native_sr_source": source_relative(sr_path, dayoa_root),
            "rsr_source": source_relative(rsr_path, dayoa_root),
            "lr_source": source_relative(lr_path, dayoa_root),
        }

        hard_rows = read_tsv(hard_path)
        required_hard_fields = {"ROI", "VariantClass", "TP", "FN", "FP"}
        if not hard_rows or not required_hard_fields.issubset(hard_rows[0]):
            raise ValueError(f"{runtime_au}: malformed hard-VCF GIAB-HC TSV")
        required_classes = {"SNPts", "SNPtv", "INS_50", "DEL_50"}
        present_classes = {row["VariantClass"] for row in hard_rows if row.get("ROI") == "giabHC"}
        if not required_classes.issubset(present_classes):
            raise ValueError(f"{runtime_au}: missing hard-VCF GIAB-HC classes")
        output["hard_vcf"][runtime_au] = {
            "source_path": source_relative(hard_path, dayoa_root),
            "rows": hard_rows,
        }

        caller_entries = []
        for path in truvari_paths:
            caller_token = path.parents[1].name
            payload = json.loads(path.read_text())
            if not isinstance(payload, dict) or not {"precision", "recall", "f1"}.issubset(payload):
                raise ValueError(f"{runtime_au}: malformed Truvari summary {path}")
            caller_entries.append(
                {
                    "caller": CALLER_NAMES.get(caller_token, caller_token),
                    "source_path": source_relative(path, dayoa_root),
                    "summary": payload,
                }
            )
        if {entry["caller"] for entry in caller_entries} != set(CALLER_NAMES.values()):
            raise ValueError(f"{runtime_au}: unexpected Truvari caller set")
        output["truvari"][runtime_au] = caller_entries

        smn_payload = json.loads(smn_path.read_text())
        if not isinstance(smn_payload, dict) or len(smn_payload) != 1:
            raise ValueError(f"{runtime_au}: malformed SMN12 summary")
        output["smn12"][runtime_au] = {
            "source_path": source_relative(smn_path, dayoa_root),
            "payload": smn_payload,
        }

        output["segdup"][runtime_au] = {}
        genes: set[str] = set()
        for path in segdup_paths:
            gene = path.parent.name
            if gene in genes:
                raise ValueError(f"{runtime_au}: duplicate SegDup gene {gene}")
            genes.add(gene)
            passed, failed = segdup_counts(path)
            output["segdup"][runtime_au][gene] = {
                "source_path": source_relative(path, dayoa_root),
                "pass_count": passed,
                "failed_count": failed,
            }
        gene_sets.append(genes)

        benchmark_rows, benchmark_inventory, benchmark_rejections = collect_benchmarks(
            results_root, unit_root, runtime_au, dayoa_root
        )
        if not benchmark_rows:
            raise ValueError(f"{runtime_au}: no usable successful raw benchmark rows")
        output["benchmarks"].extend(benchmark_rows)
        output["inventory"].extend(benchmark_inventory)
        output["benchmark_rejections"].extend(
            {"runtime_au": runtime_au, **row} for row in benchmark_rejections
        )
        output["completeness"][runtime_au] = {
            "source_analysis_unit_uid": source_au,
            "native_sr_coverage": "complete",
            "rsr_audit_coverage": "complete",
            "lr_coverage": "complete",
            "hard_vcf_giabhc": "complete",
            "truvari_summaries": 4,
            "smn12_summary": "complete",
            "segdup_vcfs": len(segdup_paths),
            "benchmark_source_files": len(benchmark_inventory),
            "benchmark_success_rows": len(benchmark_rows),
            "benchmark_rejected_or_incomplete_rows": len(benchmark_rejections),
            "benchmark_snapshot": "partial_while_controller_nonterminal",
        }

    if any(genes != gene_sets[0] for genes in gene_sets[1:]):
        raise ValueError("SegDup gene set differs between E4 analysis units")
    output["segdup_gene_set"] = sorted(gene_sets[0])
    output["workflow_status_end"] = json.loads(status_path.read_text())
    output["captured_at_end_utc"] = utc_now()
    output["inventory"] = sorted(
        output["inventory"], key=lambda row: (row["relative_path"], row["category"])
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "captured_at_start_utc": output["captured_at_start_utc"],
                "captured_at_end_utc": output["captured_at_end_utc"],
                "analysis_units": len(output["identity"]),
                "core_complete_analysis_units": len(output["completeness"]),
                "successful_benchmark_rows": len(output["benchmarks"]),
                "benchmark_rejections": len(output["benchmark_rejections"]),
                "inventory_files": len(output["inventory"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
