#!/usr/bin/env python3
"""Inspect Snakemake progress and DAG artifacts on a Daylily headnode."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path


INSTANCE_ID = "i-05374380b57fad901"
REGION = "us-west-2"


REMOTE_SCRIPT = r"""#!/usr/bin/env bash
set -euo pipefail
for id in hybonly_ont_kitchensink_mounted_20260606T053415Z_retry1 hybonly_ilmn_kitchensink_mounted_20260606T053415Z; do
  repo="/fsx/analysis_results/ubuntu/${id}/daylily-omics-analysis"
  echo "## ${id}"
  echo "repo=${repo}"
  if [ ! -d "${repo}" ]; then
    echo "missing_repo=1"
    continue
  fi

  latest="$(ls -1t "${repo}"/.snakemake/log/*.log 2>/dev/null | head -1 || true)"
  echo "latest_log=${latest}"
  if [ -n "${latest}" ]; then
    echo "summary_counts"
    python3 - "${latest}" <<'PY'
import re
import sys

path = sys.argv[1]
lines = open(path, errors="replace").read().splitlines()
progress = []
finished = 0
submitted = 0
errors = []
for line in lines:
    if "Finished job" in line:
        finished += 1
    if "Submitted job" in line:
        submitted += 1
    if "Error in rule" in line or "Failed jobs" in line or "Exiting because" in line:
        errors.append(line)
    match = re.search(r"(\d+) of (\d+) steps \(([^)]+)\) done", line)
    if match:
        progress.append((int(match.group(1)), int(match.group(2)), match.group(3), line))
done = total = pct = None
if progress:
    done, total, pct, _ = progress[-1]
print(f"finished_lines={finished}")
print(f"submitted_lines={submitted}")
print(f"latest_done={done}")
print(f"latest_total={total}")
print(f"latest_pct={pct}")
if total is not None and done is not None:
    print(f"remaining_by_latest_progress={total - done}")
print(f"error_marker_count={len(errors)}")
for marker in errors[-10:]:
    print("error_marker=" + marker[:500])
PY
    echo "progress_tail"
    grep -E "[0-9]+ of [0-9]+ steps|Finished job|Submitted job|Error in rule|Failed jobs|Exiting because|Complete log" "${latest}" | tail -n 80 || true
  fi

  echo "dag_files"
  find "${repo}" -maxdepth 6 -type f \( -name "*.dag" -o -iname "*dag*.svg" -o -iname "*dag*.png" -o -iname "*dag*.pdf" -o -name "dag.svg" -o -name "dag.png" -o -name "dag.pdf" \) -printf "%p\t%s\t%TY-%Tm-%TdT%TH:%TM:%TS%TZ\n" 2>/dev/null | sort || true
  echo
done
"""


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, text=True, capture_output=True)


def main() -> int:
    remote_path = "/tmp/inspect_snakemake_progress_dag.sh"
    write_script = (
        f"cat > {remote_path} <<'DAYOA_INSPECT_EOF'\n"
        f"{REMOTE_SCRIPT}\n"
        "DAYOA_INSPECT_EOF\n"
    )
    send = run(
        [
            "aws",
            "ssm",
            "send-command",
            "--region",
            REGION,
            "--instance-ids",
            INSTANCE_ID,
            "--document-name",
            "AWS-RunShellScript",
            "--parameters",
            json.dumps(
                {
                    "commands": [
                        write_script,
                        f"chmod 755 {remote_path}",
                        f"runuser -u ubuntu -- bash {remote_path}",
                    ]
                }
            ),
            "--query",
            "Command.CommandId",
            "--output",
            "text",
        ]
    )
    command_id = send.stdout.strip()
    print(f"COMMAND_ID={command_id}")
    wait = subprocess.run(
        [
            "aws",
            "ssm",
            "wait",
            "command-executed",
            "--region",
            REGION,
            "--command-id",
            command_id,
            "--instance-id",
            INSTANCE_ID,
        ],
        text=True,
        capture_output=True,
    )
    if wait.returncode != 0:
        print(wait.stderr, file=sys.stderr)
    invocation = run(
        [
            "aws",
            "ssm",
            "get-command-invocation",
            "--region",
            REGION,
            "--command-id",
            command_id,
            "--instance-id",
            INSTANCE_ID,
            "--query",
            "{Status:Status,Stdout:StandardOutputContent,Stderr:StandardErrorContent}",
            "--output",
            "json",
        ]
    )
    decoded = json.loads(invocation.stdout)
    print(json.dumps(decoded, indent=2))
    if decoded.get("Status") != "Success":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
