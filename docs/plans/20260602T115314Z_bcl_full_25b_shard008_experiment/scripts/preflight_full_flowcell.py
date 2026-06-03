#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, wait_for_ssm_online


PROFILE = os.environ.get("PROFILE", "lsmc")
REGION = os.environ.get("REGION", "us-west-2")
CLUSTER = os.environ.get("CLUSTER", "dyec5117")
RUNID = os.environ.get("RUNID", "20260514_LH01106_0009_B23TVLGLT4")
EXP_DIR = Path(
    os.environ.get(
        "EXP_DIR",
        "docs/plans/20260602T115314Z_bcl_full_25b_shard008_experiment",
    )
)
RUN_DIR = f"/fsx/run_dir_mounts/{RUNID}"
LANE_FASTQ_BYTES = int(os.environ.get("LANE_FASTQ_BYTES", "602945262796"))


def parse_block(text: str, name: str) -> str:
    start = f"__{name}_START__"
    end = f"__{name}_END__"
    if start not in text or end not in text:
        return ""
    return text.split(start, 1)[1].split(end, 1)[0].strip()


def main() -> int:
    metadata_dir = EXP_DIR / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=180)

    script = f"""
set -euo pipefail
RUN_DIR={RUN_DIR!r}
BASE="$RUN_DIR/Data/Intensities/BaseCalls"
SAMPLE_SHEET="$RUN_DIR/SampleSheet.csv"
RUNINFO="$RUN_DIR/RunInfo.xml"
echo "__ENV_START__"
printf 'whoami=%s\\n' "$(id -un)"
printf 'hostname=%s\\n' "$(hostname)"
printf 'date_utc=%s\\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'run_dir=%s\\n' "$RUN_DIR"
printf 'sample_sheet=%s\\n' "$SAMPLE_SHEET"
printf 'runinfo=%s\\n' "$RUNINFO"
echo "__ENV_END__"
echo "__FSX_DF_H_START__"
df -h /fsx
echo "__FSX_DF_H_END__"
echo "__FSX_DF_BYTES_START__"
df -B1 /fsx
echo "__FSX_DF_BYTES_END__"
echo "__REMAINING_BCL_DIRS_START__"
find /fsx/analysis_results/ubuntu -maxdepth 1 -mindepth 1 -type d -name 'bcl25b_l003_*' -printf '%f\\t%p\\n' | sort || true
echo "__REMAINING_BCL_DIRS_END__"
echo "__RUN_PATHS_START__"
for p in "$RUN_DIR" "$BASE" "$SAMPLE_SHEET" "$RUNINFO"; do
  if [[ -e "$p" ]]; then printf 'exists\\t%s\\n' "$p"; else printf 'missing\\t%s\\n' "$p"; fi
done
echo "__RUN_PATHS_END__"
echo "__LANES_START__"
find "$BASE" -maxdepth 1 -mindepth 1 -type d -name 'L[0-9][0-9][0-9]' -printf '%f\\n' | sort
echo "__LANES_END__"
echo "__LANE_TILE_COUNTS_START__"
find "$BASE" -maxdepth 1 -mindepth 1 -type d -name 'L[0-9][0-9][0-9]' | sort | while read -r lane_dir; do
  lane="${{lane_dir##*/}}"
  filter_count="$(find "$lane_dir" -maxdepth 1 -type f -name '*.filter' | wc -l | tr -d ' ')"
  cbcl_count="$(find "$lane_dir" -type f -name '*.cbcl' | wc -l | tr -d ' ')"
  printf '%s\\tfilter_files=%s\\tcbcl_files=%s\\n' "$lane" "$filter_count" "$cbcl_count"
done
echo "__LANE_TILE_COUNTS_END__"
echo "__RUNINFO_START__"
grep -E '<Flowcell>|<Instrument>|<Read |<FlowcellLayout' "$RUNINFO" || true
echo "__RUNINFO_END__"
echo "__SAMPLESHEET_LANES_START__"
awk -F',' '
  BEGIN {{ indata=0; header=0; lane_col=0 }}
  /^\\[Data\\]/ {{ indata=1; next }}
  indata && header==0 {{ for (i=1; i<=NF; i++) if ($i=="Lane") lane_col=i; header=1; next }}
  indata && header==1 && NF>1 {{
    if (lane_col > 0 && $lane_col != "") lanes[$lane_col]=1;
    rows++;
  }}
  END {{
    printf "data_rows=%d\\n", rows;
    if (lane_col == 0) print "lane_column=absent";
    else {{
      print "lane_column=present";
      for (lane in lanes) print "sample_sheet_lane=" lane;
    }}
  }}
' "$SAMPLE_SHEET" | sort
echo "__SAMPLESHEET_LANES_END__"
echo "__SQUEUE_START__"
squeue -h -o '%i\\t%P\\t%j\\t%u\\t%T\\t%M\\t%D\\t%R' || true
echo "__SQUEUE_END__"
echo "__TMUX_START__"
tmux ls || true
echo "__TMUX_END__"
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        timeout=300,
        comment="Full 25B BCL shard008 preflight",
    )
    (metadata_dir / "full_flowcell_preflight.stdout.txt").write_text(
        result.stdout, encoding="utf-8"
    )
    (metadata_dir / "full_flowcell_preflight.stderr.txt").write_text(
        result.stderr, encoding="utf-8"
    )
    (metadata_dir / "full_flowcell_preflight.ssm.json").write_text(
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

    if result.response_code != 0:
        print(result.stdout, end="")
        print(result.stderr, end="")
        return result.response_code

    lanes = [line.strip() for line in parse_block(result.stdout, "LANES").splitlines() if line.strip()]
    remaining = parse_block(result.stdout, "REMAINING_BCL_DIRS")
    run_paths = parse_block(result.stdout, "RUN_PATHS")
    sample_sheet_lanes = parse_block(result.stdout, "SAMPLESHEET_LANES")
    df_bytes = parse_block(result.stdout, "FSX_DF_BYTES")
    squeue = parse_block(result.stdout, "SQUEUE")

    missing_paths = [line for line in run_paths.splitlines() if line.startswith("missing\t")]
    if missing_paths:
        raise SystemExit("Preflight failed: missing required run paths:\n" + "\n".join(missing_paths))
    if remaining:
        raise SystemExit("Preflight failed: remaining old bcl25b_l003 dirs:\n" + remaining)
    if not lanes:
        raise SystemExit("Preflight failed: no lane directories found")

    sample_sheet_lane_values = sorted(
        re.sub(r"^sample_sheet_lane=", "", line)
        for line in sample_sheet_lanes.splitlines()
        if line.startswith("sample_sheet_lane=")
    )
    if sample_sheet_lane_values:
        expected_numeric = [lane.removeprefix("L").lstrip("0") or "0" for lane in lanes]
        missing_lane_rows = sorted(set(expected_numeric) - set(sample_sheet_lane_values))
        if missing_lane_rows:
            raise SystemExit(
                "Preflight failed: sample sheet Lane column does not cover lanes "
                + ",".join(missing_lane_rows)
            )

    available_bytes = 0
    for line in df_bytes.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4 and parts[-1] == "/fsx":
            available_bytes = int(parts[3])
            break
    expected_bytes = LANE_FASTQ_BYTES * len(lanes)
    capacity = {
        "available_bytes": available_bytes,
        "lane_fastq_bytes_basis": LANE_FASTQ_BYTES,
        "lanes": lanes,
        "expected_full_bytes": expected_bytes,
        "available_minus_expected_bytes": available_bytes - expected_bytes,
        "squeue_rows": 0 if not squeue else len(squeue.splitlines()),
    }
    (metadata_dir / "full_flowcell_preflight_summary.json").write_text(
        json.dumps(capacity, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(capacity, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
