from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from daylily_ec.aws.ssm import (
    SsmCommandFailedError,
    resolve_headnode_instance_id,
    run_shell,
    wait_for_ssm_online,
)


PROFILE = "lsmc"
REGION = "us-west-2"
CLUSTER = os.environ.get("DYEC_BENCHMARK_CLUSTER", "dyec5128")

if not CLUSTER.startswith("dyec5128"):
    raise SystemExit(
        f"Refusing to run HG003 benchmark preflight on {CLUSTER!r}; expected dyec5128."
    )

REQUIRED_PATHS = [
    "/fsx",
    "/fsx/references",
    "/fsx/resources",
    "/fsx/analysis_results",
    "/fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/giab/NovaSeqX_WHGS_TruSeqPF_HG002-007/downsampled/HG003_5x_R1.fastq.gz",
    "/fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/giab/NovaSeqX_WHGS_TruSeqPF_HG002-007/downsampled/HG003_5x_R2.fastq.gz",
    "/fsx/references/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG003",
    "/fsx/references/genomic_data/organism_references/H_sapiens/hg38_broad/hg38_broad_core.bed",
    "/fsx/references/runtime_assets/cached_envs",
]

ESSENTIAL_COMMANDS = ["tmux", "squeue", "sbatch", "sinfo", "day-clone", "aws", "python3"]
OPTIONAL_COMMANDS = ["sacct", "nextflow", "java", "singularity", "apptainer", "dyec"]


def _remote_script() -> str:
    required_paths = " ".join(json.dumps(path) for path in REQUIRED_PATHS)
    essential_commands = " ".join(json.dumps(cmd) for cmd in ESSENTIAL_COMMANDS)
    optional_commands = " ".join(json.dumps(cmd) for cmd in OPTIONAL_COMMANDS)
    return f"""set -euo pipefail

section() {{
  printf '\\n===== %s =====\\n' "$1"
}}

section identity
date -u
id
hostname -f
pwd
echo "SHELL=$SHELL"
echo "PATH=$PATH"

section filesystem
df -h /fsx
df -B1 /fsx

section required_paths
missing_paths=0
for p in {required_paths}; do
  if [ -e "$p" ]; then
    ls -ld "$p"
  else
    echo "MISSING_PATH $p"
    missing_paths=$((missing_paths + 1))
  fi
done

section commands
missing_commands=0
for c in {essential_commands}; do
  if command -v "$c" >/dev/null 2>&1; then
    printf 'ESSENTIAL %s %s\\n' "$c" "$(command -v "$c")"
  else
    printf 'MISSING_ESSENTIAL %s\\n' "$c"
    missing_commands=$((missing_commands + 1))
  fi
done
for c in {optional_commands}; do
  if command -v "$c" >/dev/null 2>&1; then
    printf 'OPTIONAL %s %s\\n' "$c" "$(command -v "$c")"
  else
    printf 'MISSING_OPTIONAL %s\\n' "$c"
  fi
done

section slurm_state
sinfo -Nel || true
squeue -u ubuntu -o '%i|%P|%j|%u|%T|%M|%D|%R' || true
active_jobs="$(squeue -h -u ubuntu | wc -l | tr -d ' ')"
echo "active_slurm_jobs=$active_jobs"

section slurm_accounting
if command -v sacct >/dev/null 2>&1; then
  set +e
  sacct --version
  sacct -n -P -S "$(date -u +%Y-%m-%d)" -u ubuntu -o JobID,JobName,State,Elapsed,AllocCPUS,ReqMem,MaxRSS -X | tail -40
  sacct_rc=$?
  set -e
  echo "sacct_rc=$sacct_rc"
else
  echo "sacct_missing=1"
fi

section tmux
tmux ls || true
for s in $(tmux list-sessions -F '#{{session_name}}' 2>/dev/null || true); do
  printf '\\n--- tmux:%s ---\\n' "$s"
  tmux list-windows -t "$s" || true
  tmux list-panes -t "$s" || true
  tmux capture-pane -pt "$s" -S -40 || true
done

section controller_processes
controller_count="$(
  ps -fu ubuntu | awk '/dy-r|day_run|snakemake|nextflow/ && !/awk/ {{print}}' | tee /tmp/dyec_benchmark_controllers.txt | wc -l | tr -d ' '
)"
cat /tmp/dyec_benchmark_controllers.txt
echo "active_controller_processes=$controller_count"

section nextflow_runtime
missing_nextflow_runtime=0
if [ -x /fsx/resources/environments/nextflow/24.10.5/nextflow ]; then
  PATH=/fsx/resources/environments/nextflow/24.10.5:$PATH JAVA_CMD=/fsx/resources/environments/nextflow/java-21/bin/java /fsx/resources/environments/nextflow/24.10.5/nextflow -version || true
else
  echo "MISSING_NEXTFLOW_24_10_5"
  missing_nextflow_runtime=$((missing_nextflow_runtime + 1))
fi
if [ -x /fsx/resources/environments/nextflow/java-21/bin/java ]; then
  /fsx/resources/environments/nextflow/java-21/bin/java -version || true
else
  echo "MISSING_JAVA_21"
  missing_nextflow_runtime=$((missing_nextflow_runtime + 1))
fi

section existing_analysis_dirs
find /fsx/analysis_results/ubuntu -maxdepth 2 -type d -name '*hg003*' -o -name '*sarek*' -o -name '*benchmark*' 2>/dev/null | sort | tail -80 || true

if [ "$missing_paths" -ne 0 ] || [ "$missing_commands" -ne 0 ] || [ "$active_jobs" -ne 0 ] || [ "$controller_count" -ne 0 ] || [ "$missing_nextflow_runtime" -ne 0 ]; then
  echo "PREFLIGHT_RESULT=FAIL"
  exit 70
fi
echo "PREFLIGHT_RESULT=PASS"
"""


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=180, poll_interval=5)
    payload = _remote_script()
    try:
        result = run_shell(
            target.instance_id,
            REGION,
            payload,
            profile=PROFILE,
            as_user="ubuntu",
            timeout=300,
            poll_interval=5,
            comment="HG003 5x benchmark read-only preflight",
        )
    except SsmCommandFailedError as exc:
        result = exc.result
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        return result.response_code or 1
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
