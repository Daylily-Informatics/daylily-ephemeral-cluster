#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


PROFILE = os.environ.get("PROFILE", "lsmc")
REGION = os.environ.get("REGION", "us-west-2")
CLUSTER = os.environ.get("CLUSTER", "dyec5117")
DAYOA_TAG = os.environ.get("DAYOA_TAG", "2.0.36")
EXP_STAMP = os.environ.get("EXP_STAMP", "20260602T115314Z")
EXP_DIR = Path(
    os.environ.get(
        "EXP_DIR",
        f"docs/plans/{EXP_STAMP}_bcl_full_25b_shard008_experiment",
    )
)
RUN_CONTEXT = EXP_DIR / "runs_full.tsv"
ANALYSIS_ID = os.environ.get("ANALYSIS_ID", f"bcl25b_full_shard008_retry1_{EXP_STAMP}")
LANES_CSV = os.environ.get("LANES_CSV", "L001,L002,L003,L004,L005,L006,L007,L008")
SHARED_THREAD_ODIRECT_OUTPUT = os.environ.get("SHARED_THREAD_ODIRECT_OUTPUT", "false")


def main() -> int:
    metadata_dir = EXP_DIR / "metadata"
    command_logs_dir = EXP_DIR / "command_logs"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    command_logs_dir.mkdir(parents=True, exist_ok=True)

    bclconvert = {
        "barcode_mismatches_index1": "0",
        "barcode_mismatches_index2": "0",
        "compression_threads": "64",
        "conversion_threads": "4",
        "decompression_threads": "32",
        "fastq_gzip_compression_level": "1",
        "force": "true",
        "merge_lane_fastqs": "false",
        "merge_tile_fastqs": "false",
        "num_unknown_barcodes_reported": "1000",
        "output_legacy_stats": "true",
        "parallel_tiles": "24",
        "partition": "i192mem",
        "sample_sheet_settings": "{}",
        "sample_sheet_settings_by_lane": "{}",
        "shared_thread_odirect_output": SHARED_THREAD_ODIRECT_OUTPUT,
        "threads": "192",
        "tile_compression_threads": "24",
        "tile_conversion_threads": "2",
        "tile_decompression_threads": "8",
        "tile_parallel_tiles": "8",
        "tile_shard_lanes": LANES_CSV,
        "tile_shard_level": "8",
        "tile_shard_mem_mb": "180000",
        "tile_shard_threads": "48",
        "tmpdir": "/dev/shm",
    }
    dy_command = (
        "bin/day_run produce_bclconvert_fastqs -p -j 300 -k "
        "--config run_context_file=config/runs.tsv bootstrap_bclconvert=true "
        f"bclconvert='{json.dumps(bclconvert, separators=(',', ':'))}'"
    )
    (metadata_dir / "analysis_id_full_shard008.txt").write_text(
        ANALYSIS_ID + "\n", encoding="utf-8"
    )
    (metadata_dir / "dy_command_full_shard008.txt").write_text(
        dy_command + "\n", encoding="utf-8"
    )

    cmd = [
        "python",
        "-m",
        "daylily_ec.cli",
        "workflow",
        "launch",
        "--profile",
        PROFILE,
        "--region",
        REGION,
        "--cluster",
        CLUSTER,
        "--repository",
        "daylily-omics-analysis",
        "--analysis-id",
        ANALYSIS_ID,
        "--executing-entity",
        "ubuntu",
        "--session-name",
        ANALYSIS_ID,
        "--git-tag",
        DAYOA_TAG,
        "--run-context-file",
        str(RUN_CONTEXT),
        "--dy-command",
        dy_command,
    ]
    (metadata_dir / "launch_full_shard008.argv.json").write_text(
        json.dumps(cmd, indent=2) + "\n", encoding="utf-8"
    )
    result = subprocess.run(cmd, text=True, capture_output=True)
    (command_logs_dir / "launch_full_shard008.stdout.txt").write_text(
        result.stdout, encoding="utf-8"
    )
    (command_logs_dir / "launch_full_shard008.stderr.txt").write_text(
        result.stderr, encoding="utf-8"
    )
    print(result.stdout, end="")
    print(result.stderr, end="")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
