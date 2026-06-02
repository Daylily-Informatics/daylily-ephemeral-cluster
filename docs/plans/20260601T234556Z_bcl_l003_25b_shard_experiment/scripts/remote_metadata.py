#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, wait_for_ssm_online

PROFILE = os.environ.get("PROFILE", "lsmc")
REGION = os.environ.get("REGION", "us-west-2")
CLUSTER = os.environ.get("CLUSTER", "dyec5117")
DAYOA_TAG = os.environ.get("DAYOA_TAG", "2.0.34")
RUNID = os.environ.get("RUNID", "20260514_LH01106_0009_B23TVLGLT4")
EXP_STAMP = os.environ.get("EXP_STAMP", "20260601T234556Z")
EXP_DIR = Path(os.environ.get("EXP_DIR", f"docs/plans/{EXP_STAMP}_bcl_l003_25b_shard_experiment"))
METADATA_DIR = EXP_DIR / "metadata"
RUN_DIR = f"/fsx/run_dir_mounts/{RUNID}"


def local_git_show(path: str) -> str:
    proc = subprocess.run(
        ["git", "show", f"{DAYOA_TAG}:{path}"],
        cwd="/Users/jmajor/.codex/worktrees/dayoa-2034-release",
        text=True,
        capture_output=True,
        check=True,
    )
    return proc.stdout


def main() -> None:
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=180)

    script = f"""
set -euo pipefail
RUN_DIR={RUN_DIR!r}
echo "whoami=$(id -un)"
echo "hostname=$(hostname)"
echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "run_dir=$RUN_DIR"
echo "sample_sheet=$RUN_DIR/SampleSheet.csv"
echo "runinfo=$RUN_DIR/RunInfo.xml"
echo "runparameters=$RUN_DIR/RunParameters.xml"
echo "basecalls=$RUN_DIR/Data/Intensities/BaseCalls"
echo "day_clone_path=$(command -v day-clone || true)"
echo "__DAY_CLONE_LIST_START__"
if command -v day-clone >/dev/null 2>&1; then day-clone --list; else echo "day-clone missing"; fi
echo "__DAY_CLONE_LIST_END__"
echo "__FSX_DF_START__"
df -h /fsx || true
echo "__FSX_DF_END__"
echo "__FSX_MOUNT_START__"
findmnt /fsx || mount | grep ' /fsx ' || true
echo "__FSX_MOUNT_END__"
echo "__RUN_ROOT_LS_START__"
ls -la "$RUN_DIR" | sed -n '1,80p'
echo "__RUN_ROOT_LS_END__"
echo "__LANE_DIRS_START__"
find "$RUN_DIR/Data/Intensities/BaseCalls" -maxdepth 1 -type d -name 'L*' -printf '%f\n' | sort
echo "__LANE_DIRS_END__"
echo "lane003_filter_count=$(find "$RUN_DIR/Data/Intensities/BaseCalls/L003" -maxdepth 1 -type f -name '*.filter' | wc -l | tr -d ' ')"
echo "__RUNINFO_FLOWCELL_START__"
grep -E '<Flowcell>|<Instrument>|<Read ' "$RUN_DIR/RunInfo.xml" || true
echo "__RUNINFO_FLOWCELL_END__"
echo "__RUNPARAMETERS_FLOWCELL_START__"
grep -Ei 'FlowCell|Flowcell|Flow Cell|Instrument|InstrumentType|ApplicationName|ReagentKit|Side' "$RUN_DIR/RunParameters.xml" | sed -n '1,120p' || true
echo "__RUNPARAMETERS_FLOWCELL_END__"
echo "__BCL_CONVERT_PATH_START__"
command -v bcl-convert || true
echo "__BCL_CONVERT_PATH_END__"
echo "__BCL_CONVERT_VERSION_START__"
if command -v bcl-convert >/dev/null 2>&1; then bcl-convert --version || true; else echo "bcl-convert not on headnode PATH outside workflow/container"; fi
echo "__BCL_CONVERT_VERSION_END__"
echo "__SNAKEMAKE_VERSION_START__"
if command -v snakemake >/dev/null 2>&1; then snakemake --version || true; else echo "snakemake not on bare headnode PATH"; fi
echo "__SNAKEMAKE_VERSION_END__"
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        timeout=240,
        comment="BCL Lane003 experiment metadata preflight",
    )
    (METADATA_DIR / "remote_metadata.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (METADATA_DIR / "remote_metadata.stderr.txt").write_text(result.stderr, encoding="utf-8")
    (METADATA_DIR / "remote_metadata.ssm.json").write_text(
        json.dumps(
            {
                "command_id": result.command_id,
                "instance_id": result.instance_id,
                "status": result.status,
                "response_code": result.response_code,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    bcl_rule = local_git_show("workflow/rules/bclconvert.smk")
    configured = ""
    for line in bcl_rule.splitlines():
        if line.startswith("BCL_RUNTIME_VERSION"):
            configured = line.strip()
            break
    (METADATA_DIR / "dayoa_2.0.34_bcl_runtime_version.txt").write_text(
        configured + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
