#!/usr/bin/env python3
"""Build a pre-teardown manifest of dyecX4 analysis dirs not exported to S3."""

from __future__ import annotations

import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, wait_for_ssm_online


PROFILE = "lsmc"
REGION = "us-west-2"
CLUSTER = "dyecX4"
BUCKET = "lsmc-ssf-sequencing-data"
S3_PREFIX_ROOT = "derived/analysis_results/hyb-only"
STAMP = "20260616T001451Z"
OUTDIR = Path("docs/plans")
JSON_OUT = OUTDIR / f"{STAMP}_dyecx4_unexported_export_manifest.json"
TSV_OUT = OUTDIR / f"{STAMP}_dyecx4_unexported_export_manifest.tsv"
MD_OUT = OUTDIR / f"{STAMP}_dyecx4_unexported_export_manifest.md"


REMOTE_SCRIPT = r"""
set -euo pipefail
python3 -c '
import json
import os
import subprocess
from pathlib import Path

def run(cmd):
    proc = subprocess.run(cmd, text=True, capture_output=True)
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }

ps = run(["ps", "-fu", "ubuntu"])
process_lines = [
    line
    for line in ps["stdout"].splitlines()
    if any(token in line for token in ("dy-r", "day_run", "snakemake", "day-clone"))
    and "python3 -c" not in line
    and "daylily-ssm" not in line
]
ps["stdout"] = "\n".join(process_lines)
tmux = run(["tmux", "list-sessions"])

base = Path("/fsx/analysis_results")
rows = []
if base.exists():
    for owner_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        for analysis_dir in sorted(p for p in owner_dir.iterdir() if p.is_dir()):
            stat = analysis_dir.stat()
            analysis_id = analysis_dir.name
            try:
                immediate_entries = sum(1 for _ in analysis_dir.iterdir())
            except OSError:
                immediate_entries = -1
            rows.append([
                owner_dir.name,
                analysis_id,
                __import__("datetime").datetime.fromtimestamp(stat.st_mtime, __import__("datetime").timezone.utc).isoformat(),
                immediate_entries,
                (analysis_dir / "daylily-omics-analysis").is_dir(),
                (analysis_dir / "daylily-omics-analysis" / ".snakemake").exists() or (analysis_dir / ".snakemake").exists(),
                (analysis_dir / "daylily-omics-analysis" / "day_cmd.log").exists(),
                (analysis_dir / "fsx_export.yaml").exists(),
                analysis_id in tmux["stdout"],
                analysis_id in ps["stdout"],
            ])

payload = {
    "analysis_dirs": rows,
    "squeue": run(["squeue", "-o", "%i  %P  %C  %t  %N  %c  %T  %m  %M  %D  %j"]),
    "tmux_session_count": len([line for line in tmux["stdout"].splitlines() if line.strip()]),
    "process_line_count": len([line for line in ps["stdout"].splitlines() if line.strip()]),
}
print(json.dumps(payload, sort_keys=True))
'
"""


def _s3_prefix_stats(s3_client: Any, prefix: str) -> dict[str, Any]:
    response = s3_client.list_objects_v2(Bucket=BUCKET, Prefix=prefix, MaxKeys=10)
    size = 0
    latest = ""
    contents = response.get("Contents", []) or []
    for obj in contents:
        size += int(obj.get("Size") or 0)
        last_modified = obj.get("LastModified")
        if last_modified:
            value = last_modified.astimezone(timezone.utc).isoformat()
            latest = max(latest, value)
    return {
        "s3_prefix_exists": bool(contents),
        "s3_sample_object_count": len(contents),
        "s3_sample_total_bytes": size,
        "s3_latest_last_modified_utc": latest,
        "s3_sample_is_truncated": bool(response.get("IsTruncated")),
    }


def _status_for(row: dict[str, Any]) -> str:
    if not row["s3_prefix_exists"]:
        return "not_exported"
    if row["s3_sample_object_count"] < 10 and not row["s3_sample_is_truncated"]:
        return "partial_or_staged"
    return "exported_candidate"


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=120)
    result = run_shell(
        target.instance_id,
        REGION,
        REMOTE_SCRIPT,
        profile=PROFILE,
        timeout=600,
        comment="Collect dyecX4 analysis dirs for export manifest",
    )
    json_start = result.stdout.find("{")
    if json_start < 0:
        raise RuntimeError(f"Remote collector did not emit JSON. stdout={result.stdout!r}")
    remote = json.loads(result.stdout[json_start:])
    s3 = boto3.Session(profile_name=PROFILE, region_name=REGION).client("s3")
    rows: list[dict[str, Any]] = []
    for raw_row in remote["analysis_dirs"]:
        (
            owner,
            analysis_id,
            mtime_utc,
            immediate_entry_count,
            has_dayoa_checkout,
            has_snakemake_state,
            has_day_cmd_log,
            has_export_receipt_at_root,
            tmux_match,
            process_match,
        ) = raw_row
        prefix = f"{S3_PREFIX_ROOT}/{owner}/{analysis_id}/"
        stats = _s3_prefix_stats(s3, prefix)
        enriched = {
            "owner": owner,
            "analysis_id": analysis_id,
            "fsx_path": f"/fsx/analysis_results/{owner}/{analysis_id}",
            "mtime_utc": mtime_utc,
            "immediate_entry_count": immediate_entry_count,
            "has_dayoa_checkout": has_dayoa_checkout,
            "has_snakemake_state": has_snakemake_state,
            "has_day_cmd_log": has_day_cmd_log,
            "has_export_receipt_at_root": has_export_receipt_at_root,
            "tmux_match": tmux_match,
            "process_match": process_match,
            "cluster": CLUSTER,
            "expected_s3_uri": f"s3://{BUCKET}/{prefix}",
            **stats,
        }
        enriched["export_status"] = _status_for(enriched)
        rows.append(enriched)

    rows.sort(key=lambda r: (r["export_status"], r["owner"], r["analysis_id"]))
    payload = {
        "schema_version": "dyec.pre_teardown_export_manifest.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "profile": PROFILE,
        "region": REGION,
        "cluster": CLUSTER,
        "headnode_instance_id": target.instance_id,
        "s3_prefix_root": f"s3://{BUCKET}/{S3_PREFIX_ROOT}/",
        "squeue": remote["squeue"],
        "tmux_session_count": remote["tmux_session_count"],
        "process_line_count": remote["process_line_count"],
        "rows": rows,
    }
    JSON_OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    fieldnames = [
        "export_status",
        "cluster",
        "owner",
        "analysis_id",
        "fsx_path",
        "expected_s3_uri",
        "immediate_entry_count",
        "s3_prefix_exists",
        "s3_sample_object_count",
        "s3_sample_total_bytes",
        "s3_sample_is_truncated",
        "mtime_utc",
        "s3_latest_last_modified_utc",
        "has_dayoa_checkout",
        "has_snakemake_state",
        "has_day_cmd_log",
        "tmux_match",
        "process_match",
    ]
    with TSV_OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    needs_export = [r for r in rows if r["export_status"] != "exported_candidate"]
    lines = [
        "# dyecX4 Pre-Teardown Export Manifest",
        "",
        f"- Created UTC: `{payload['created_utc']}`",
        f"- Cluster: `{CLUSTER}`",
        f"- Headnode: `{target.instance_id}`",
        f"- Analysis directories inspected: `{len(rows)}`",
        f"- Needs export review: `{len(needs_export)}`",
        f"- Slurm status command rc: `{remote['squeue']['returncode']}`",
        f"- Tmux sessions on headnode: `{payload['tmux_session_count']}`",
        f"- Active workflow process lines: `{payload['process_line_count']}`",
        "",
        "## Needs Export Review",
        "",
        "| Status | FSx path | Expected S3 URI | Top-level entries | S3 sample objects | S3 sample bytes |",
        "|---|---|---|---:|---:|---:|",
    ]
    for row in needs_export:
        lines.append(
            "| {export_status} | `{fsx_path}` | `{expected_s3_uri}` | {immediate_entry_count} | {s3_sample_object_count} | {s3_sample_total_bytes} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- JSON: `{JSON_OUT}`",
            f"- TSV: `{TSV_OUT}`",
        ]
    )
    MD_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {JSON_OUT}")
    print(f"Wrote {TSV_OUT}")
    print(f"Wrote {MD_OUT}")
    print(f"needs_export_review={len(needs_export)} total={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
