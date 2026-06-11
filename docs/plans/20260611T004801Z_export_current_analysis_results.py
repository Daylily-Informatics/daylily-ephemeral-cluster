#!/usr/bin/env python3
"""Export inventoried dyecX4 analysis results through dyec export.

This helper is intentionally narrow for the 20260611T004801Z ledger:
it parses the recorded headnode inventory, writes an explicit export
inventory, launches dyec export with a fixed concurrency cap, and validates
the fsx_export.yaml receipts as the export authority.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
from typing import Any


DEST_ROOT = "s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu"
SOURCE_ROOT = "/fsx/analysis_results/ubuntu"


def parse_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        if line.startswith("SECTION "):
            current = line.split(" ", 1)[1]
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)
    return sections


def parse_inventory(path: pathlib.Path) -> list[dict[str, Any]]:
    sections = parse_sections(path.read_text())
    dirs: list[tuple[str, str]] = []
    for line in sections.get("analysis_dirs", []):
        if not line.strip():
            continue
        try:
            analysis_id, source_path = line.split("\t", 1)
        except ValueError as exc:
            raise SystemExit(f"Malformed analysis_dirs line: {line!r}") from exc
        if not source_path.startswith(f"{SOURCE_ROOT}/"):
            raise SystemExit(f"Refusing non-ubuntu source path: {source_path}")
        dirs.append((analysis_id, source_path))

    sizes: dict[str, int] = {}
    for line in sections.get("analysis_sizes_kib", []):
        if not line.strip():
            continue
        try:
            size_text, source_path = line.split(None, 1)
        except ValueError as exc:
            raise SystemExit(f"Malformed analysis_sizes_kib line: {line!r}") from exc
        sizes[source_path] = int(size_text)

    inventory = []
    for analysis_id, source_path in dirs:
        inventory.append(
            {
                "analysis_id": analysis_id,
                "source_path": source_path,
                "size_kib": sizes.get(source_path),
                "destination_s3_uri": f"{DEST_ROOT}/{analysis_id}/",
            }
        )
    if not inventory:
        raise SystemExit("No analysis directories found in inventory")
    return inventory


def write_inventory_files(inventory: list[dict[str, Any]], output_dir: pathlib.Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "export_inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
    with (output_dir / "export_inventory.tsv").open("w") as handle:
        handle.write("analysis_id\tsize_kib\tsource_path\tdestination_s3_uri\n")
        for row in inventory:
            handle.write(
                f"{row['analysis_id']}\t{row.get('size_kib') or ''}\t"
                f"{row['source_path']}\t{row['destination_s3_uri']}\n"
            )


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "true":
        return True
    if value == "false":
        return False
    if value in {"{}", "[]"}:
        return {} if value == "{}" else []
    return value.strip("'\"")


def parse_receipt(path: pathlib.Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    in_export = False
    for raw_line in path.read_text().splitlines():
        if raw_line == "fsx_export:":
            in_export = True
            continue
        if not in_export or not raw_line.startswith("  "):
            continue
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        if value.strip():
            data[key] = parse_scalar(value)
    return data


def receipt_is_success(receipt: dict[str, Any]) -> bool:
    return (
        receipt.get("status") == "success"
        and receipt.get("task_lifecycle") == "SUCCEEDED"
        and receipt.get("detached") is True
        and receipt.get("delete_data_in_file_system") is False
    )


def run_one_export(
    row: dict[str, Any],
    *,
    output_dir: pathlib.Path,
    dyec_bin: str,
    cluster: str,
    profile: str,
    region: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    analysis_id = row["analysis_id"]
    analysis_output = output_dir / "exports" / analysis_id
    analysis_output.mkdir(parents=True, exist_ok=True)
    receipt_path = analysis_output / "fsx_export.yaml"
    if receipt_path.exists():
        receipt = parse_receipt(receipt_path)
        if receipt_is_success(receipt):
            return {
                "analysis_id": analysis_id,
                "source_path": row["source_path"],
                "destination_s3_uri": row["destination_s3_uri"],
                "returncode": 0,
                "status": "skipped_existing_success",
                "receipt": receipt,
                "receipt_path": str(receipt_path),
            }

    command = [
        dyec_bin,
        "export",
        "--profile",
        profile,
        "--region",
        region,
        "--cluster",
        cluster,
        "--source-path",
        row["source_path"],
        "--destination-s3-uri",
        row["destination_s3_uri"],
        "--output-dir",
        str(analysis_output),
        "--timeout-seconds",
        str(timeout_seconds),
    ]
    (analysis_output / "command.txt").write_text(" ".join(command) + "\n")
    started_at = time.time()
    proc = subprocess.run(command, text=True, capture_output=True)
    elapsed_seconds = round(time.time() - started_at, 3)
    (analysis_output / "stdout.txt").write_text(proc.stdout)
    (analysis_output / "stderr.txt").write_text(proc.stderr)

    receipt: dict[str, Any] = {}
    if receipt_path.exists():
        receipt = parse_receipt(receipt_path)
    result = {
        "analysis_id": analysis_id,
        "source_path": row["source_path"],
        "destination_s3_uri": row["destination_s3_uri"],
        "returncode": proc.returncode,
        "status": "success" if proc.returncode == 0 and receipt_is_success(receipt) else "failed",
        "elapsed_seconds": elapsed_seconds,
        "receipt": receipt,
        "receipt_path": str(receipt_path) if receipt_path.exists() else None,
    }
    (analysis_output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def run_exports(args: argparse.Namespace, inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dyec_bin = shutil.which("dyec")
    if dyec_bin is None:
        raise SystemExit("dyec is not on PATH; run from an activated DYEC environment")
    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futures = [
            pool.submit(
                run_one_export,
                row,
                output_dir=args.output_dir,
                dyec_bin=dyec_bin,
                cluster=args.cluster,
                profile=args.profile,
                region=args.region,
                timeout_seconds=args.timeout_seconds,
            )
            for row in inventory
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            print(
                f"{result['status']}\t{result['analysis_id']}\t{result['destination_s3_uri']}",
                flush=True,
            )
    results.sort(key=lambda item: item["analysis_id"])
    (args.output_dir / "export_results.json").write_text(json.dumps(results, indent=2) + "\n")
    with (args.output_dir / "export_results.tsv").open("w") as handle:
        handle.write("status\treturncode\tanalysis_id\tsource_path\tdestination_s3_uri\treceipt_path\n")
        for result in results:
            handle.write(
                f"{result['status']}\t{result['returncode']}\t{result['analysis_id']}\t"
                f"{result['source_path']}\t{result['destination_s3_uri']}\t"
                f"{result.get('receipt_path') or ''}\n"
            )
    failures = [result for result in results if result["status"] not in {"success", "skipped_existing_success"}]
    if failures:
        (args.output_dir / "export_failures.json").write_text(json.dumps(failures, indent=2) + "\n")
        raise SystemExit(f"{len(failures)} exports failed")
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory-stdout", type=pathlib.Path, required=True)
    parser.add_argument("--output-dir", type=pathlib.Path, required=True)
    parser.add_argument("--cluster", default="dyecX4")
    parser.add_argument("--profile", default="lsmc")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    parser.add_argument("--run-exports", action="store_true")
    args = parser.parse_args()

    if args.max_workers > 4:
        raise SystemExit("This ledger caps exports at 4 concurrent workers")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    inventory = parse_inventory(args.inventory_stdout)
    write_inventory_files(inventory, args.output_dir)
    print(f"inventory_count={len(inventory)}")
    if args.run_exports:
        run_exports(args, inventory)
    return 0


if __name__ == "__main__":
    sys.exit(main())
