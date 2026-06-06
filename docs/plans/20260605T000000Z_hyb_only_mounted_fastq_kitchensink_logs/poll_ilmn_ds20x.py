#!/usr/bin/env python3
"""Poll ILMN 20x downsampling tmux/log/output state."""

from __future__ import annotations

import sys

from daylily_ec.aws.ssm import run_shell


INSTANCE_ID = "i-05374380b57fad901"
REGION = "us-west-2"
PROFILE = "lsmc"
SESSION = "ilmn_ds20x_20260606T110315Z"
DEST = "/fsx/analysis_results/4_nas_ds_to_20x"


SCRIPT = f"""
set -euo pipefail
session={SESSION!r}
dest={DEST!r}
echo "SESSION_STATUS"
tmux has-session -t "$session" 2>/dev/null && echo present || echo missing
echo "MARKERS"
for marker in DONE FAILED; do
  if [ -f "$dest/$marker" ]; then
    echo "$marker=$(cat "$dest/$marker")"
  else
    echo "$marker=missing"
  fi
done
echo "OUTPUTS"
find "$dest" -maxdepth 1 -type f -name '*.fastq.gz' -printf '%f\\t%s\\n' 2>/dev/null | sort || true
echo "TMP_OUTPUTS"
find "$dest/tmp" -maxdepth 1 -type f -name '*.fastq.gz' -printf '%f\\t%s\\n' 2>/dev/null | sort || true
echo "LOG_TAILS"
for log in "$dest"/logs/*.downsample.log; do
  [ -f "$log" ] || continue
  echo "--- $(basename "$log")"
  tail -n 12 "$log" || true
done
echo "PROCS"
ps -fu ubuntu | awk '/paired_downsample_fastq.py|run_downsample_20x.sh|pigz/ && !/awk/ {{print}}' || true
echo "DF"
df -h /fsx
"""


def main() -> int:
    result = run_shell(
        INSTANCE_ID,
        REGION,
        SCRIPT,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=180,
        comment="poll ILMN ds20x",
    )
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    return int(result.response_code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
