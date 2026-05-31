#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell, write_remote_text

CLUSTER = "dyec-test"
REGION = "us-west-2"
PROFILE = "lsmc"
RUN_ID = "20260514_LH01106_0009_B23TVLGLT4"
LANE = "3"
LANE_NAME = "L003"
REMOTE_WORK = "/home/ubuntu/bcl_lane_bench_20260531T083038Z"
REMOTE_BASE = "/fsx/analysis_results/ubuntu/bcl_lane_bench_20260531T083038Z"
RUN_DIR = f"/fsx/run_dir_mounts/{RUN_ID}"
SAMPLE_SHEET = f"{RUN_DIR}/SampleSheet.csv"
CONTAINER = "docker://nfcore/bclconvert:4.0.3"
LOCAL_LOG_DIR = Path("docs/plans/20260531T083038Z_bcl_lane_thread_benchmark_logs")


def _target():
    return resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)


def _record(name: str, stdout: str, stderr: str = "") -> None:
    LOCAL_LOG_DIR.mkdir(parents=True, exist_ok=True)
    (LOCAL_LOG_DIR / f"{name}.stdout.txt").write_text(stdout or "", encoding="utf-8")
    (LOCAL_LOG_DIR / f"{name}.stderr.txt").write_text(stderr or "", encoding="utf-8")


def _run_remote(name: str, script: str, *, timeout: int = 300):
    target = _target()
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        timeout=timeout,
        comment=f"BCL lane benchmark {name}",
    )
    _record(name, result.stdout, result.stderr)
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    return result


PREPARE_SAMPLESHEET = r'''#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import re
from pathlib import Path

SECTION_RE = re.compile(r"^\[(?P<name>[^\]]+)\]")
UPDATES = {
    "BarcodeMismatchesIndex1": "0",
    "BarcodeMismatchesIndex2": "0",
}
DROP_KEYS = {"GenerateFastqcMetrics"}


def csv_line(row: list[str]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="")
    writer.writerow(row)
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-sheet", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    source = Path(args.sample_sheet)
    output = Path(args.out)
    lines = source.read_text(encoding="utf-8-sig").splitlines()
    section_start = None
    section_end = len(lines)
    for index, raw in enumerate(lines):
        match = SECTION_RE.match(raw.strip())
        if not match:
            continue
        if match.group("name").strip() == "BCLConvert_Settings":
            section_start = index
            continue
        if section_start is not None and index > section_start:
            section_end = index
            break
    if section_start is None:
        raise SystemExit("missing [BCLConvert_Settings] in sample sheet")
    remaining = dict(UPDATES)
    for index in range(section_start + 1, section_end):
        if not lines[index].strip():
            continue
        row = next(csv.reader([lines[index]]))
        key = row[0].strip() if row else ""
        if key in DROP_KEYS:
            lines[index] = ""
            continue
        if key in remaining:
            lines[index] = csv_line([key, remaining.pop(key)])
    insert_at = section_end
    for key, value in remaining.items():
        lines.insert(insert_at, csv_line([key, value]))
        insert_at += 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"prepared_sample_sheet={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


RUN_ONE = rf'''#!/usr/bin/env bash
set -uo pipefail

variant="$1"
output_mode="$2"
parallel_tiles="$3"
conversion_threads="$4"
compression_threads="$5"
decompression_threads="$6"
shared_thread_odirect_output="$7"
num_unknown_barcodes_reported="$8"

base="{REMOTE_BASE}"
work="{REMOTE_WORK}"
run_dir="{RUN_DIR}"
sample_sheet="{SAMPLE_SHEET}"
lane="{LANE}"
container="{CONTAINER}"
variant_dir="$base/results/$variant"
log_dir="$base/logs"
metrics_dir="$base/metrics"
sample_dir="$base/sample_sheets"
mkdir -p "$variant_dir" "$log_dir" "$metrics_dir" "$sample_dir"

log="$log_dir/$variant.log"
time_log="$log_dir/$variant.time.txt"
meta="$metrics_dir/$variant.tsv"
lane_sheet="$sample_dir/$variant.SampleSheet.csv"
scratch_root="/dev/shm/bcl_lane_bench_20260531T083038Z/$variant"
cleanup_paths=()

cleanup() {{
  rc=$?
  if [[ "${{KEEP_BCL_BENCH_OUTPUTS:-0}}" != "1" ]]; then
    for path in "${{cleanup_paths[@]:-}}"; do
      if [[ -n "$path" && "$path" == "$base"/results/* ]]; then
        rm -rf "$path"
      fi
    done
  fi
  if [[ -n "${{scratch_root:-}}" && "${{KEEP_BCL_BENCH_SHM:-0}}" != "1" ]]; then
    rm -rf "$scratch_root"
  fi
  exit "$rc"
}}
trap cleanup EXIT INT TERM

: > "$log"
printf 'variant=%s\n' "$variant" >> "$log"
printf 'started=%s\n' "$(date -Is)" >> "$log"
printf 'host=%s\n' "$(hostname)" >> "$log"
printf 'slurm_job_id=%s\n' "${{SLURM_JOB_ID:-}}" >> "$log"
printf 'lane=%s\n' "$lane" >> "$log"
printf 'output_mode=%s\n' "$output_mode" >> "$log"
rm -rf "$scratch_root"
mkdir -p "$scratch_root/tmp"
export TMPDIR="$scratch_root/tmp"
printf 'TMPDIR=%s\n' "$TMPDIR" >> "$log"
heavy_threads=$((parallel_tiles * conversion_threads + compression_threads + decompression_threads))
nproc >> "$log" 2>&1 || true
lscpu >> "$log" 2>&1 || true
df -h /fsx /dev/shm "$run_dir" >> "$log" 2>&1 || true

if [[ ! -d "$run_dir/Data/Intensities/BaseCalls/{LANE_NAME}" ]]; then
  printf 'missing lane directory: %s\n' "$run_dir/Data/Intensities/BaseCalls/{LANE_NAME}" >> "$log"
  exit 2
fi
if [[ ! -s "$sample_sheet" ]]; then
  printf 'missing sample sheet: %s\n' "$sample_sheet" >> "$log"
  exit 2
fi

python3 "$work/prepare_samplesheet.py" --sample-sheet "$sample_sheet" --out "$lane_sheet" >> "$log" 2>&1

fsx_output="$variant_dir/bcl_output"
if [[ "$output_mode" == "shm" ]]; then
  shm_available_bytes=$(df -PB1 /dev/shm | awk 'NR==2{{print $4}}')
  required_shm_bytes=$((700 * 1024 * 1024 * 1024))
  printf 'shm_available_bytes=%s\n' "$shm_available_bytes" >> "$log"
  printf 'required_shm_bytes=%s\n' "$required_shm_bytes" >> "$log"
  if (( shm_available_bytes < required_shm_bytes )); then
    printf 'SKIPPED: /dev/shm does not have enough margin for one full lane output plus temp overhead.\n' >> "$log"
    printf 'variant\toutput_mode\theavy_threads\tconvert_rc\tcopy_rc\tconvert_seconds\tcopy_seconds\ttotal_seconds\toutput_bytes\thost\tslurm_job_id\n' > "$meta"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$variant" "$output_mode" "$heavy_threads" "SKIPPED_SHM_SPACE" "0" \
      "0" "0" "0" "0" "$(hostname)" "${{SLURM_JOB_ID:-}}" >> "$meta"
    exit 0
  fi
  bcl_output="$scratch_root/bcl_output"
  mkdir -p "$bcl_output"
  singularity_bind_args=(--bind /fsx:/fsx --bind "$scratch_root:$scratch_root")
else
  bcl_output="$fsx_output"
  mkdir -p "$bcl_output"
  cleanup_paths+=("$variant_dir")
  singularity_bind_args=(--bind /fsx:/fsx --bind "$scratch_root:$scratch_root")
fi

printf 'bcl_output=%s\n' "$bcl_output" >> "$log"
printf 'fsx_output=%s\n' "$fsx_output" >> "$log"
printf 'parallel_tiles=%s\n' "$parallel_tiles" >> "$log"
printf 'conversion_threads=%s\n' "$conversion_threads" >> "$log"
printf 'compression_threads=%s\n' "$compression_threads" >> "$log"
printf 'decompression_threads=%s\n' "$decompression_threads" >> "$log"
printf 'shared_thread_odirect_output=%s\n' "$shared_thread_odirect_output" >> "$log"
printf 'num_unknown_barcodes_reported=%s\n' "$num_unknown_barcodes_reported" >> "$log"
printf 'bcl_cpu_heavy_threads=%s\n' "$heavy_threads" >> "$log"

bcl_flags=(
  --bcl-input-directory "$run_dir"
  --output-directory "$bcl_output"
  --sample-sheet "$lane_sheet"
  --bcl-only-lane "$lane"
  --strict-mode false
  --first-tile-only false
  --bcl-sampleproject-subdirectories false
  --fastq-gzip-compression-level 1
  --bcl-num-parallel-tiles "$parallel_tiles"
  --bcl-num-conversion-threads "$conversion_threads"
  --bcl-num-compression-threads "$compression_threads"
  --bcl-num-decompression-threads "$decompression_threads"
  --shared-thread-odirect-output "$shared_thread_odirect_output"
  --output-legacy-stats true
  --num-unknown-barcodes-reported "$num_unknown_barcodes_reported"
  -f
)

printf 'bcl_command=' >> "$log"
printf ' %q' singularity exec "${{singularity_bind_args[@]}}" "$container" bcl-convert "${{bcl_flags[@]}}" >> "$log"
printf '\n' >> "$log"

convert_start=$(date +%s)
set +e
/usr/bin/time -v -o "$time_log" singularity exec "${{singularity_bind_args[@]}}" "$container" bcl-convert "${{bcl_flags[@]}}" >> "$log" 2>&1
convert_rc=$?
set -e
convert_end=$(date +%s)
copy_seconds=0
copy_rc=0
output_bytes=0

if [[ "$convert_rc" == "0" ]]; then
  output_bytes=$(du -sb "$bcl_output" 2>/dev/null | awk '{{print $1}}')
  if [[ "$output_mode" == "shm" ]]; then
    mkdir -p "$fsx_output"
    cleanup_paths+=("$variant_dir")
    copy_start=$(date +%s)
    set +e
    cp -a "$bcl_output/." "$fsx_output/" >> "$log" 2>&1
    copy_rc=$?
    set -e
    copy_end=$(date +%s)
    copy_seconds=$((copy_end - copy_start))
  fi
fi
end_epoch=$(date +%s)

printf 'variant\toutput_mode\theavy_threads\tconvert_rc\tcopy_rc\tconvert_seconds\tcopy_seconds\ttotal_seconds\toutput_bytes\thost\tslurm_job_id\n' > "$meta"
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
  "$variant" "$output_mode" "$heavy_threads" "$convert_rc" "$copy_rc" \
  "$((convert_end - convert_start))" "$copy_seconds" "$((end_epoch - convert_start))" \
  "$output_bytes" "$(hostname)" "${{SLURM_JOB_ID:-}}" >> "$meta"
printf 'finished=%s convert_rc=%s copy_rc=%s\n' "$(date -Is)" "$convert_rc" "$copy_rc" >> "$log"

if [[ "$convert_rc" != "0" ]]; then
  exit "$convert_rc"
fi
if [[ "$copy_rc" != "0" ]]; then
  exit "$copy_rc"
fi
exit 0
'''


RUN_PACK = rf'''#!/usr/bin/env bash
set -uo pipefail
base="{REMOTE_BASE}"
work="{REMOTE_WORK}"
log_dir="$base/logs"
metrics_dir="$base/metrics"
mkdir -p "$log_dir" "$metrics_dir"
log="$log_dir/fsx_pack3x64.controller.log"
meta="$metrics_dir/fsx_pack3x64.tsv"
: > "$log"
printf 'started=%s\n' "$(date -Is)" >> "$log"
printf 'host=%s\n' "$(hostname)" >> "$log"
printf 'slurm_job_id=%s\n' "${{SLURM_JOB_ID:-}}" >> "$log"
start_epoch=$(date +%s)

bash "$work/run_bcl_one.sh" fsx_pack3x64_a fsx 16 2 24 8 true 1000 >> "$log" 2>&1 &
p1=$!
bash "$work/run_bcl_one.sh" fsx_pack3x64_b fsx 16 2 24 8 true 1000 >> "$log" 2>&1 &
p2=$!
bash "$work/run_bcl_one.sh" fsx_pack3x64_c fsx 16 2 24 8 true 1000 >> "$log" 2>&1 &
p3=$!

rc=0
wait "$p1" || rc=1
wait "$p2" || rc=1
wait "$p3" || rc=1
end_epoch=$(date +%s)
printf 'variant\tcontroller_rc\ttotal_seconds\thost\tslurm_job_id\n' > "$meta"
printf 'fsx_pack3x64\t%s\t%s\t%s\t%s\n' "$rc" "$((end_epoch - start_epoch))" "$(hostname)" "${{SLURM_JOB_ID:-}}" >> "$meta"
printf 'finished=%s rc=%s\n' "$(date -Is)" "$rc" >> "$log"
exit "$rc"
'''


SUBMIT = rf'''#!/usr/bin/env bash
set -euo pipefail
base="{REMOTE_BASE}"
work="{REMOTE_WORK}"
run_dir="{RUN_DIR}"
sample_sheet="{SAMPLE_SHEET}"
mkdir -p "$base/logs" "$base/metrics" "$base/results" "$base/sample_sheets"
printf 'submitted_at=%s\n' "$(date -Is)" > "$base/jobs.tsv"
printf 'run_dir=%s\n' "$run_dir" >> "$base/jobs.tsv"
printf 'sample_sheet=%s\n' "$sample_sheet" >> "$base/jobs.tsv"
if [[ ! -d "$run_dir/Data/Intensities/BaseCalls/{LANE_NAME}" ]]; then
  printf 'missing lane directory: %s\n' "$run_dir/Data/Intensities/BaseCalls/{LANE_NAME}" >&2
  exit 2
fi
if [[ ! -s "$sample_sheet" ]]; then
  printf 'missing sample sheet: %s\n' "$sample_sheet" >&2
  exit 2
fi

submit_one() {{
  local name="$1"; shift
  local dep_arg=()
  if [[ "${{1:-}}" == "--dependency" ]]; then
    dep_arg=(--dependency "$2")
    shift 2
  fi
    sbatch --parsable \
    --job-name "$name" \
    --comment daylily-global \
    --partition i192mem,i192bigmem \
    --nodes 1 \
    --cpus-per-task 192 \
    --mem 360G \
    --exclusive \
    --output "$base/logs/slurm-%x-%j.out" \
    --error "$base/logs/slurm-%x-%j.err" \
    "${{dep_arg[@]}}" \
    "$@"
}}

j1=$(submit_one bcl_fsx_base "$work/run_bcl_one.sh" fsx_baseline_192 fsx 16 8 48 16 false 10000)
printf 'fsx_baseline_192\t%s\n' "$j1" >> "$base/jobs.tsv"
j2=$(submit_one bcl_fsx_192 --dependency "afterany:$j1" "$work/run_bcl_one.sh" fsx_threadseek_192 fsx 24 4 64 32 true 1000)
printf 'fsx_threadseek_192\t%s\n' "$j2" >> "$base/jobs.tsv"
j3=$(submit_one bcl_fsx_384 --dependency "afterany:$j2" "$work/run_bcl_one.sh" fsx_oversub_384 fsx 64 4 64 64 true 1000)
printf 'fsx_oversub_384\t%s\n' "$j3" >> "$base/jobs.tsv"
j4=$(submit_one bcl_pack3x64 --dependency "afterany:$j3" "$work/run_pack3x64.sh")
printf 'fsx_pack3x64\t%s\n' "$j4" >> "$base/jobs.tsv"
j5=$(submit_one bcl_shm_192 --dependency "afterany:$j4" "$work/run_bcl_one.sh" shm_threadseek_192 shm 24 4 64 32 true 1000)
printf 'shm_threadseek_192\t%s\n' "$j5" >> "$base/jobs.tsv"

cat "$base/jobs.tsv"
'''


STATUS = rf'''#!/usr/bin/env bash
set -euo pipefail
base="{REMOTE_BASE}"
printf 'SECTION time\n'; date -Is
printf 'SECTION fs\n'; df -h /fsx /dev/shm
printf 'SECTION jobs_tsv\n'; if [[ -f "$base/jobs.tsv" ]]; then cat "$base/jobs.tsv"; else true; fi
printf 'SECTION queue\n'; squeue -h -o '%i|%j|%T|%M|%D|%R' || true
printf 'SECTION metrics\n'
if [[ -d "$base/metrics" ]]; then
  for f in "$base"/metrics/*.tsv; do
    [[ -e "$f" ]] || continue
    variant="${{f##*/}}"
    variant="${{variant%.tsv}}"
    expected_job=""
    if [[ -f "$base/jobs.tsv" ]]; then
      lookup_variant="$variant"
      case "$variant" in
        fsx_pack3x64_a|fsx_pack3x64_b|fsx_pack3x64_c) lookup_variant="fsx_pack3x64" ;;
      esac
      expected_job=$(awk -v v="$lookup_variant" '$1 == v {{print $2}}' "$base/jobs.tsv" | tail -n 1)
    fi
    observed_job=$(awk -F '\t' 'NR == 2 {{print $NF}}' "$f" 2>/dev/null || true)
    stale_note=""
    if [[ -n "$expected_job" && -n "$observed_job" && "$expected_job" != "$observed_job" ]]; then
      stale_note=" stale_expected_job=$expected_job observed_job=$observed_job"
    fi
    printf -- '--- %s%s ---\n' "$(basename "$f")" "$stale_note"
    cat "$f"
  done
fi
printf 'SECTION shm_leftovers\n'
find /dev/shm/bcl_lane_bench_20260531T083038Z -maxdepth 3 -mindepth 1 -print 2>/dev/null || true
printf 'SECTION result_dirs\n'
find "$base/results" -maxdepth 2 -mindepth 1 -type d -printf '%p\n' 2>/dev/null | sort || true
'''


def install() -> None:
    target = _target()
    files = {
        f"{REMOTE_WORK}/prepare_samplesheet.py": PREPARE_SAMPLESHEET,
        f"{REMOTE_WORK}/run_bcl_one.sh": RUN_ONE,
        f"{REMOTE_WORK}/run_pack3x64.sh": RUN_PACK,
        f"{REMOTE_WORK}/submit_benchmarks.sh": SUBMIT,
        f"{REMOTE_WORK}/status.sh": STATUS,
    }
    for remote_path, content in files.items():
        write_remote_text(target.instance_id, REGION, remote_path, content, profile=PROFILE)
    _run_remote(
        "install_chmod",
        f"chmod 700 {REMOTE_WORK}/*.sh {REMOTE_WORK}/*.py && ls -l {REMOTE_WORK}",
        timeout=120,
    )


def inspect() -> None:
    _run_remote(
        "inspect",
        (
            "set -euo pipefail\n"
            "printf 'SECTION identity\\n'; hostname; id; date -Is\n"
            "printf 'SECTION fs\\n'; df -h /fsx /dev/shm\n"
            "printf 'SECTION run_dir\\n'; "
            f"ls -ld {RUN_DIR} {RUN_DIR}/Data/Intensities/BaseCalls/{LANE_NAME} {SAMPLE_SHEET}\n"
            "printf 'SECTION sample_sheet_settings\\n'; "
            f"awk 'BEGIN{{p=0}} /^\\[BCLConvert_Settings\\]/{{p=1;next}} /^\\[/&&p{{exit}} p{{print}}' {SAMPLE_SHEET} | head -40\n"
            "printf 'SECTION queue\\n'; squeue -h -o '%i|%j|%T|%M|%D|%R' || true\n"
        ),
        timeout=120,
    )


def submit() -> None:
    install()
    _run_remote("submit", f"bash {REMOTE_WORK}/submit_benchmarks.sh", timeout=120)


def status() -> None:
    _run_remote("status", f"bash {REMOTE_WORK}/status.sh", timeout=120)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["inspect", "install", "submit", "status"])
    args = parser.parse_args()
    if args.action == "inspect":
        inspect()
    elif args.action == "install":
        install()
    elif args.action == "submit":
        submit()
    elif args.action == "status":
        status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
