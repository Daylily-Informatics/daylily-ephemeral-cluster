#!/usr/bin/env python3
"""Restart ILMN 20x downsampling as Slurm seqkit array jobs."""

from __future__ import annotations

import base64
import sys

from daylily_ec.aws.ssm import run_shell


INSTANCE_ID = "i-05374380b57fad901"
REGION = "us-west-2"
PROFILE = "lsmc"
DEST = "/fsx/analysis_results/4_nas_ds_to_20x"
OLD_SESSION = "ilmn_ds20x_20260606T110315Z"
ENV_PREFIX = "/fsx/references/runtime_assets/cached_envs/conda/4ccf662e3c47c1d194250b668a918cb0_"


PLAN = """sample\ttarget_coverage_x\tsource_coverage_x\tfraction\tseed\tr1\tr2\tout_r1\tout_r2
NA00232\t20\t43.00\t0.4651162791\t2302\t/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA00232-SMN_S46_R1_001.fastq.gz\t/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA00232-SMN_S46_R2_001.fastq.gz\t/fsx/analysis_results/4_nas_ds_to_20x/NA00232-SMN_S46_ds20x_R1_001.fastq.gz\t/fsx/analysis_results/4_nas_ds_to_20x/NA00232-SMN_S46_ds20x_R2_001.fastq.gz
NA09677\t20\t39.75\t0.5031446541\t9677\t/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA09677-SMN_S47_R1_001.fastq.gz\t/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA09677-SMN_S47_R2_001.fastq.gz\t/fsx/analysis_results/4_nas_ds_to_20x/NA09677-SMN_S47_ds20x_R1_001.fastq.gz\t/fsx/analysis_results/4_nas_ds_to_20x/NA09677-SMN_S47_ds20x_R2_001.fastq.gz
NA03986\t20\t35.19\t0.5683432793\t3986\t/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA03986-DMPK_S48_R1_001.fastq.gz\t/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA03986-DMPK_S48_R2_001.fastq.gz\t/fsx/analysis_results/4_nas_ds_to_20x/NA03986-DMPK_S48_ds20x_R1_001.fastq.gz\t/fsx/analysis_results/4_nas_ds_to_20x/NA03986-DMPK_S48_ds20x_R2_001.fastq.gz
NA05164\t20\t32.91\t0.6077195381\t5164\t/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA05164-DMPK_S49_R1_001.fastq.gz\t/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/NA05164-DMPK_S49_R2_001.fastq.gz\t/fsx/analysis_results/4_nas_ds_to_20x/NA05164-DMPK_S49_ds20x_R1_001.fastq.gz\t/fsx/analysis_results/4_nas_ds_to_20x/NA05164-DMPK_S49_ds20x_R2_001.fastq.gz
"""


BATCH = r'''#!/usr/bin/env bash
set -euo pipefail

dest="/fsx/analysis_results/4_nas_ds_to_20x"
env_prefix="/fsx/references/runtime_assets/cached_envs/conda/4ccf662e3c47c1d194250b668a918cb0_"
conda_sh="/home/ubuntu/miniconda3/etc/profile.d/conda.sh"
plan="$dest/downsample_plan_seqkit.tsv"
threads="${SLURM_CPUS_PER_TASK:-96}"
task_id="${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}"

source "$conda_sh"
conda activate "$env_prefix"
command -v seqkit
seqkit version
echo "SLURM_JOB_ID=${SLURM_JOB_ID:-na}"
echo "SLURM_ARRAY_TASK_ID=$task_id"
echo "SLURM_CPUS_PER_TASK=$threads"
echo "HOSTNAME=$(hostname)"
echo "START_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

line="$(awk -v n="$((task_id + 2))" 'NR == n {print}' "$plan")"
if [[ -z "$line" ]]; then
  echo "ERROR: no plan row for task $task_id" >&2
  exit 2
fi

IFS=$'\t' read -r sample target_cov source_cov fraction seed r1 r2 out_r1 out_r2 <<< "$line"
echo "sample=$sample target_cov=$target_cov source_cov=$source_cov fraction=$fraction seed=$seed"
echo "r1=$r1"
echo "r2=$r2"
echo "out_r1=$out_r1"
echo "out_r2=$out_r2"

test -s "$r1"
test -s "$r2"
if [[ -e "$out_r1" || -e "$out_r2" ]]; then
  echo "ERROR: final output already exists for $sample" >&2
  ls -lh "$out_r1" "$out_r2" 2>/dev/null || true
  exit 3
fi

tmp_r1="${out_r1}.seqkit.${SLURM_JOB_ID:-manual}_${task_id}.tmp.gz"
tmp_r2="${out_r2}.seqkit.${SLURM_JOB_ID:-manual}_${task_id}.tmp.gz"
stats="${dest}/logs/${sample}.seqkit.${SLURM_JOB_ID:-manual}_${task_id}.stats.tsv"
rm -f "$tmp_r1" "$tmp_r2" "$stats"

seqkit sample -j "$threads" --rand-seed "$seed" --proportion "$fraction" "$r1" -o "$tmp_r1"
seqkit sample -j "$threads" --rand-seed "$seed" --proportion "$fraction" "$r2" -o "$tmp_r2"

gzip -t "$tmp_r1" "$tmp_r2"
seqkit stats -j "$threads" -T "$tmp_r1" "$tmp_r2" | tee "$stats"
r1_count="$(awk 'NR==2 {gsub(",", "", $4); print $4}' "$stats")"
r2_count="$(awk 'NR==3 {gsub(",", "", $4); print $4}' "$stats")"
if [[ "$r1_count" != "$r2_count" || -z "$r1_count" ]]; then
  echo "ERROR: R1/R2 count mismatch for $sample: R1=$r1_count R2=$r2_count" >&2
  exit 4
fi

mv -- "$tmp_r1" "$out_r1"
mv -- "$tmp_r2" "$out_r2"
sha256sum "$out_r1" "$out_r2" > "${dest}/logs/${sample}.seqkit.${SLURM_JOB_ID:-manual}_${task_id}.sha256"
ls -lh "$out_r1" "$out_r2"
echo "DONE_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
'''


def b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


REMOTE = f"""
set -euo pipefail
dest={DEST!r}
old_session={OLD_SESSION!r}
env_prefix={ENV_PREFIX!r}
mkdir -p "$dest/logs" "$dest/scripts"
echo "STOP_OLD_SESSION"
if tmux has-session -t "$old_session" 2>/dev/null; then
  root_pids="$(tmux list-panes -t "$old_session" -F '#{{pane_pid}}' | tr '\\n' ' ')"
  python3 - "$root_pids" <<'PY'
import os, signal, subprocess, sys, time
roots = [int(x) for x in " ".join(sys.argv[1:]).split() if x.strip()]
rows = subprocess.check_output(["ps", "-eo", "pid=,ppid=,cmd="], text=True).splitlines()
children = {{}}
cmds = {{}}
for row in rows:
    parts = row.strip().split(None, 2)
    if len(parts) < 3:
        continue
    pid, ppid, cmd = int(parts[0]), int(parts[1]), parts[2]
    children.setdefault(ppid, []).append(pid)
    cmds[pid] = cmd
kill = []
stack = roots[:]
while stack:
    pid = stack.pop()
    if pid in kill:
        continue
    kill.append(pid)
    stack.extend(children.get(pid, []))
print("killing_pids=" + ",".join(map(str, sorted(kill))))
for sig in (signal.SIGTERM, signal.SIGKILL):
    for pid in sorted(kill, reverse=True):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            pass
    time.sleep(2)
PY
  tmux kill-session -t "$old_session" 2>/dev/null || true
else
  echo "old_session_missing"
fi

echo "CLEAN_PARTIALS"
find "$dest" -maxdepth 1 -type f -name '*.seqkit.*.tmp.gz' -delete
find "$dest/tmp" -maxdepth 1 -type f -name '*.fastq.gz' -delete 2>/dev/null || true
find "$dest/tmp" -maxdepth 1 -type f -name '*.pid' -delete 2>/dev/null || true
rm -f "$dest/FAILED" "$dest/DONE"
find "$dest" -maxdepth 1 -type f -name '*_ds20x_R[12]_001.fastq.gz' -print

test -f /home/ubuntu/miniconda3/etc/profile.d/conda.sh
test -x "$env_prefix/bin/seqkit"
source /home/ubuntu/miniconda3/etc/profile.d/conda.sh
conda activate "$env_prefix"
seqkit version
python3 - <<'PY'
from pathlib import Path
import base64
dest = Path({DEST!r})
(dest / "logs").mkdir(parents=True, exist_ok=True)
(dest / "scripts").mkdir(parents=True, exist_ok=True)
(dest / "downsample_plan_seqkit.tsv").write_bytes(base64.b64decode({b64(PLAN)!r}))
script = dest / "scripts" / "seqkit_downsample_one.sh"
script.write_bytes(base64.b64decode({b64(BATCH)!r}))
script.chmod(0o755)
PY

echo "SUBMIT"
cmd=(sbatch --partition=i192,i192mem,i192bigmem --cpus-per-task=96 --array=0-3 --job-name=ilmn_ds20x_seqkit --output="$dest/logs/seqkit_%A_%a.out" --error="$dest/logs/seqkit_%A_%a.err" "$dest/scripts/seqkit_downsample_one.sh")
printf 'SBATCH_CMD='
printf '%q ' "${{cmd[@]}}"
printf '\\n'
"${{cmd[@]}}"
squeue -u ubuntu -o "%.18i %.9P %.8j %.2t %.10M %.6D %R" | sed -n '1,40p'
"""


def main() -> int:
    result = run_shell(
        INSTANCE_ID,
        REGION,
        REMOTE,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="restart ILMN ds20x seqkit sbatch",
    )
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    return int(result.response_code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
