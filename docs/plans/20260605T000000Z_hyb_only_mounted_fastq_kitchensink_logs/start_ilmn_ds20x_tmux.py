#!/usr/bin/env python3
"""Start paired ILMN FASTQ downsampling to approximately 20x on hyb-only."""

from __future__ import annotations

import base64
import sys
import textwrap

from daylily_ec.aws.ssm import run_shell


INSTANCE_ID = "i-05374380b57fad901"
REGION = "us-west-2"
PROFILE = "lsmc"
SESSION = "ilmn_ds20x_20260606T110315Z"
DEST = "/fsx/analysis_results/4_nas_ds_to_20x"


PAIRED_DOWNSAMPLER = r'''#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import random
import subprocess
import sys
from pathlib import Path


def read_record(handle):
    header = handle.readline()
    if not header:
        return None
    seq = handle.readline()
    plus = handle.readline()
    qual = handle.readline()
    if not seq or not plus or not qual:
        raise RuntimeError("truncated FASTQ record")
    return header, seq, plus, qual


def read_name(header: bytes) -> bytes:
    name = header[1:].split(None, 1)[0]
    if name.endswith(b"/1") or name.endswith(b"/2"):
        name = name[:-2]
    return name


def write_record(proc, record):
    for part in record:
        proc.stdin.write(part)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", required=True)
    parser.add_argument("--r1", required=True)
    parser.add_argument("--r2", required=True)
    parser.add_argument("--out-r1", required=True)
    parser.add_argument("--out-r2", required=True)
    parser.add_argument("--fraction", type=float, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--pigz-threads", type=int, default=4)
    args = parser.parse_args()
    if not 0 < args.fraction <= 1:
        raise SystemExit(f"invalid fraction: {args.fraction}")

    rng = random.Random(args.seed)
    total = 0
    kept = 0
    out1_path = Path(args.out_r1)
    out2_path = Path(args.out_r2)
    out1_path.parent.mkdir(parents=True, exist_ok=True)
    out2_path.parent.mkdir(parents=True, exist_ok=True)

    with gzip.open(args.r1, "rb") as r1, gzip.open(args.r2, "rb") as r2, out1_path.open("wb") as raw1, out2_path.open("wb") as raw2:
        p1 = subprocess.Popen(["pigz", "-p", str(args.pigz_threads), "-c"], stdin=subprocess.PIPE, stdout=raw1)
        p2 = subprocess.Popen(["pigz", "-p", str(args.pigz_threads), "-c"], stdin=subprocess.PIPE, stdout=raw2)
        try:
            while True:
                rec1 = read_record(r1)
                rec2 = read_record(r2)
                if rec1 is None and rec2 is None:
                    break
                if rec1 is None or rec2 is None:
                    raise RuntimeError("R1/R2 ended at different record counts")
                total += 1
                if total % 1000000 == 0:
                    print(f"{args.sample}\tprocessed={total}\tkept={kept}", flush=True)
                if read_name(rec1[0]) != read_name(rec2[0]):
                    raise RuntimeError(
                        f"R1/R2 name mismatch at pair {total}: "
                        f"{read_name(rec1[0])!r} vs {read_name(rec2[0])!r}"
                    )
                if rng.random() < args.fraction:
                    write_record(p1, rec1)
                    write_record(p2, rec2)
                    kept += 1
        finally:
            for proc in (p1, p2):
                if proc.stdin:
                    proc.stdin.close()
        rc1 = p1.wait()
        rc2 = p2.wait()
        if rc1 != 0 or rc2 != 0:
            raise RuntimeError(f"pigz failed: R1 rc={rc1}, R2 rc={rc2}")
    print(f"{args.sample}\ttotal_pairs={total}\tkept_pairs={kept}\tfraction_observed={kept / total if total else 0:.8f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


RUNNER = r'''#!/usr/bin/env bash
set -euo pipefail

dest="/fsx/analysis_results/4_nas_ds_to_20x"
scripts="$dest/scripts"
logs="$dest/logs"
tmp="$dest/tmp"
mkdir -p "$scripts" "$logs" "$tmp"

cat > "$dest/downsample_plan.tsv" <<'EOF'
sample	target_coverage_x	source_coverage_x	fraction	seed	r1	r2	out_r1	out_r2
NA00232	20	43.00	0.4651162791	2302	/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA00232-SMN_S46_R1_001.fastq.gz	/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA00232-SMN_S46_R2_001.fastq.gz	/fsx/analysis_results/4_nas_ds_to_20x/NA00232-SMN_S46_ds20x_R1_001.fastq.gz	/fsx/analysis_results/4_nas_ds_to_20x/NA00232-SMN_S46_ds20x_R2_001.fastq.gz
NA09677	20	39.75	0.5031446541	9677	/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA09677-SMN_S47_R1_001.fastq.gz	/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA09677-SMN_S47_R2_001.fastq.gz	/fsx/analysis_results/4_nas_ds_to_20x/NA09677-SMN_S47_ds20x_R1_001.fastq.gz	/fsx/analysis_results/4_nas_ds_to_20x/NA09677-SMN_S47_ds20x_R2_001.fastq.gz
NA03986	20	35.19	0.5683432793	3986	/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA03986-DMPK_S48_R1_001.fastq.gz	/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA03986-DMPK_S48_R2_001.fastq.gz	/fsx/analysis_results/4_nas_ds_to_20x/NA03986-DMPK_S48_ds20x_R1_001.fastq.gz	/fsx/analysis_results/4_nas_ds_to_20x/NA03986-DMPK_S48_ds20x_R2_001.fastq.gz
NA05164	20	32.91	0.6077195381	5164	/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA05164-DMPK_S49_R1_001.fastq.gz	/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA05164-DMPK_S49_R2_001.fastq.gz	/fsx/analysis_results/4_nas_ds_to_20x/NA05164-DMPK_S49_ds20x_R1_001.fastq.gz	/fsx/analysis_results/4_nas_ds_to_20x/NA05164-DMPK_S49_ds20x_R2_001.fastq.gz
EOF

run_one() {
  local sample="$1" target_cov="$2" source_cov="$3" fraction="$4" seed="$5" r1="$6" r2="$7" out_r1="$8" out_r2="$9"
  local log="$logs/${sample}.downsample.log"
  local tmp_r1="$tmp/${sample}.R1.$$.fastq.gz"
  local tmp_r2="$tmp/${sample}.R2.$$.fastq.gz"
  {
    date -u +"START %Y-%m-%dT%H:%M:%SZ"
    echo "sample=$sample target_cov=$target_cov source_cov=$source_cov fraction=$fraction seed=$seed"
    echo "r1=$r1"
    echo "r2=$r2"
    echo "out_r1=$out_r1"
    echo "out_r2=$out_r2"
    test -s "$r1"
    test -s "$r2"
    test ! -e "$out_r1"
    test ! -e "$out_r2"
    python3 "$scripts/paired_downsample_fastq.py" \
      --sample "$sample" \
      --r1 "$r1" \
      --r2 "$r2" \
      --out-r1 "$tmp_r1" \
      --out-r2 "$tmp_r2" \
      --fraction "$fraction" \
      --seed "$seed" \
      --pigz-threads 4
    gzip -t "$tmp_r1" "$tmp_r2"
    mv -- "$tmp_r1" "$out_r1"
    mv -- "$tmp_r2" "$out_r2"
    ls -lh "$out_r1" "$out_r2"
    date -u +"DONE %Y-%m-%dT%H:%M:%SZ"
  } > "$log" 2>&1
}

status=0
pids=()
while IFS=$'\t' read -r sample target_cov source_cov fraction seed r1 r2 out_r1 out_r2; do
  run_one "$sample" "$target_cov" "$source_cov" "$fraction" "$seed" "$r1" "$r2" "$out_r1" "$out_r2" &
  echo "$!" > "$tmp/${sample}.pid"
done < <(tail -n +2 "$dest/downsample_plan.tsv")

for pidfile in "$tmp"/*.pid; do
  pid="$(cat "$pidfile")"
  if ! wait "$pid"; then
    status=1
  fi
done

if [[ "$status" -eq 0 ]]; then
  gzip -t "$dest"/*.fastq.gz
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$dest/DONE"
else
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$dest/FAILED"
fi
exit "$status"
'''


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


PAIRED_B64 = _b64(PAIRED_DOWNSAMPLER)
RUNNER_B64 = _b64(RUNNER)


REMOTE_SCRIPT = f"""
set -euo pipefail
dest={DEST!r}
session={SESSION!r}
mkdir -p "$dest/scripts" "$dest/logs" "$dest/tmp"
if tmux has-session -t "$session" 2>/dev/null; then
  echo "tmux session already exists: $session" >&2
  exit 2
fi
python3 - <<'PY'
from pathlib import Path
import base64
dest = Path({DEST!r})
paired_path = dest / "scripts" / "paired_downsample_fastq.py"
runner_path = dest / "scripts" / "run_downsample_20x.sh"
paired_path.parent.mkdir(parents=True, exist_ok=True)
paired_path.write_bytes(base64.b64decode({PAIRED_B64!r}))
runner_path.write_bytes(base64.b64decode({RUNNER_B64!r}))
paired_path.chmod(0o755)
runner_path.chmod(0o755)
PY
tmux new-session -d -s "$session" "bash '$dest/scripts/run_downsample_20x.sh'"
echo "SESSION=$session"
echo "DEST=$dest"
tmux list-sessions | grep "$session"
"""


def main() -> int:
    result = run_shell(
        INSTANCE_ID,
        REGION,
        REMOTE_SCRIPT,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=180,
        comment="start ILMN ds20x tmux",
    )
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    return int(result.response_code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
