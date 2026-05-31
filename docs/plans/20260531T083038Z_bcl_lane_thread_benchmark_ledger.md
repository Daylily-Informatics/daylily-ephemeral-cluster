# BCL Convert One-Lane Thread And /dev/shm Benchmark Ledger

## Objective

Benchmark one full Illumina BCL Convert lane on `dyec-test` in `us-west-2` to test whether more aggressive thread flags, 64-thread packing, or `/dev/shm` output staging improves wall time.

## Constraints

- Cluster: `dyec-test`
- AWS profile: `lsmc`
- Region: `us-west-2`
- Remote user: `ubuntu`
- Test lane: `L003`, because the successful full run showed it as the long-pole lane.
- All `/dev/shm` benchmark variants must install a shell trap that removes their scratch directory on `EXIT`, `INT`, and `TERM`, unless explicitly configured otherwise.
- Do not delete existing `/fsx/analysis_results/ubuntu` directories as part of this benchmark.

## Variants

| Variant | Output | Slurm allocation | BCL flags | Purpose |
|---|---|---:|---|---|
| `fsx_baseline_192` | FSx | 192 vCPU, exclusive node | `parallel_tiles=16`, `conversion_threads=8`, `compression_threads=48`, `decompression_threads=16`, `shared_thread_odirect_output=false` | Reproduce the prior successful lane shape on one lane. |
| `fsx_threadseek_192` | FSx | 192 vCPU, exclusive node | `parallel_tiles=24`, `conversion_threads=4`, `compression_threads=64`, `decompression_threads=32`, `shared_thread_odirect_output=true` | Try to use more of the 192-vCPU node while keeping CPU-heavy thread sum at 192. |
| `fsx_oversub_384` | FSx | 192 vCPU, exclusive node | `parallel_tiles=48`, `conversion_threads=4`, `compression_threads=128`, `decompression_threads=64`, `shared_thread_odirect_output=true` | Test whether oversubscribing BCL Convert's internal workers helps or hurts. |
| `fsx_pack3x64` | FSx | 192 vCPU, exclusive node | Three simultaneous BCL Convert processes, each `parallel_tiles=16`, `conversion_threads=2`, `compression_threads=24`, `decompression_threads=8` | Test running three 64-thread BCL Convert processes on one 192-vCPU node. |
| `shm_threadseek_192` | `/dev/shm`, then copy to FSx | 192 vCPU, exclusive node | Same as `fsx_threadseek_192` | Test whether tmpfs output improves conversion time enough to justify final copy time. |

## Gate 0

Inspection at `2026-05-31T08:34:45Z`:

| Check | Result |
|---|---|
| Headnode | `ip-10-0-0-88`, user `ubuntu`. |
| `/fsx` | `8.8T` total, `3.7T` used, `5.1T` available, `42%` used. |
| Headnode `/dev/shm` | `199G` total, empty at inspection. |
| Slurm queue | Empty. |
| BCL run dir | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4`, present. |
| Lane input | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/Data/Intensities/BaseCalls/L003`, present. |
| Sample sheet | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/SampleSheet.csv`, present. |
| Existing sample-sheet settings | `SoftwareVersion=4.3.16`, `OverrideCycles=Y151;I10;I10;Y151`, `FastqCompressionFormat=gzip`, `GenerateFastqcMetrics=true`. |

Local evidence:

- `docs/plans/20260531T083038Z_bcl_lane_thread_benchmark_logs/inspect.stdout.txt`
- `docs/plans/20260531T083038Z_bcl_lane_thread_benchmark_logs/inspect.stderr.txt`

## Submit Attempt 1

At `2026-05-31T08:36:37Z`, the first Slurm submission created jobs `4663`-`4667`, but the cluster `sbatch` wrapper warned that no project comment was provided and tagged the jobs as `unknown-project`. These were cancelled immediately before any benchmark metrics were produced. The driver was updated to pass `--comment daylily-global` on every benchmark `sbatch` call.

Local evidence:

- `docs/plans/20260531T083038Z_bcl_lane_thread_benchmark_logs/submit.stdout.txt`
- `docs/plans/20260531T083038Z_bcl_lane_thread_benchmark_logs/status.stdout.txt`

## Submit Attempt 2

At `2026-05-31T08:38:44Z`, the benchmark chain was resubmitted with `--comment daylily-global`.

| Variant | Slurm job |
|---|---:|
| `fsx_baseline_192` | `4668` |
| `fsx_threadseek_192` | `4669` |
| `fsx_oversub_384` | `4670` |
| `fsx_pack3x64` | `4671` |
| `shm_threadseek_192` | `4672` |

The chain uses `afterany` dependencies so later variants still run if an earlier benchmark variant fails. Generated FASTQ outputs are deleted after each variant records metrics; logs, `/usr/bin/time -v` output, and TSV summaries remain under `/fsx/analysis_results/ubuntu/bcl_lane_bench_20260531T083038Z`.

## Submit Attempt 2 Result

All five jobs exited immediately before real conversion:

| Variant | Result |
|---|---|
| `fsx_baseline_192` | `convert_rc=1`; BCL Convert rejected sample-sheet setting `GenerateFastqcMetrics=true`. |
| `fsx_threadseek_192` | `convert_rc=1`; same sample-sheet setting rejection. |
| `fsx_oversub_384` | `convert_rc=1`; `bcl-num-compression-threads=128` exceeds BCL Convert's node-local max of `64`. |
| `fsx_pack3x64` | `controller_rc=1`; each child hit the sample-sheet setting rejection. |
| `shm_threadseek_192` | `convert_rc=1`; same sample-sheet setting rejection. |

Harness corrections:

- Strip `GenerateFastqcMetrics` from the generated benchmark sample sheet to match DayOA's normal BCL Convert normalization behavior.
- Keep the oversubscription benchmark inside BCL Convert's compression-thread limit by changing it to `parallel_tiles=64`, `conversion_threads=4`, `compression_threads=64`, `decompression_threads=64`, heavy-thread sum `384`.
- Fix status reporting to use `printf --` for section dividers.

DayOA source hardening:

- `workflow/scripts/parse_bclconvert_samplesheet.py` already stripped `GenerateFastqcMetrics` from normalized BCL Convert sample sheets.
- `workflow/scripts/prepare_bclconvert_lane_samplesheet.py` now also strips `GenerateFastqcMetrics` unconditionally before writing lane-specific sample sheets.
- Focused validation passed: `python -m pytest -q tests/test_bclconvert_multiqc.py::test_bclconvert_lane_samplesheet_strips_fastqc_metrics_setting tests/test_bclconvert_multiqc.py::test_bclconvert_lane_samplesheet_injects_zero_barcode_mismatches tests/test_bclconvert_multiqc.py::test_lane_optional_bclconvert_samplesheet_generates_units_for_each_fastq_lane`; `python -m ruff check workflow/scripts/prepare_bclconvert_lane_samplesheet.py tests/test_bclconvert_multiqc.py`; `git diff --check -- workflow/scripts/prepare_bclconvert_lane_samplesheet.py tests/test_bclconvert_multiqc.py`.

## Submit Attempt 3

At `2026-05-31T08:45:23Z`, the corrected benchmark chain was submitted with `--comment daylily-global`.

| Variant | Slurm job |
|---|---:|
| `fsx_baseline_192` | `4673` |
| `fsx_threadseek_192` | `4674` |
| `fsx_oversub_384` | `4675` |
| `fsx_pack3x64` | `4676` |
| `shm_threadseek_192` | `4677` |

Checkpoint at `2026-05-31T08:46:51Z`: `4673` was running on `i192mem-dy-all-1`; dependent jobs were pending. `/fsx` was `43%` used.

Checkpoint at `2026-05-31T08:50:43Z`: `4673` was still running on `i192mem-dy-all-1` at about 5 minutes elapsed; dependent jobs `4674`-`4677` were pending. `/fsx` remained `43%` used. The status command still printed stale metrics from failed attempt-2 jobs `4668`-`4672`; these are not attempt-3 results and must be ignored until job IDs match the active submission.

Additional sample-sheet hardening validation at `2026-05-31T08:50Z`: DayOA focused tests passed for lane sample-sheet stripping, barcode-mismatch injection, and lane unit generation; Ruff passed for the modified BCL sample-sheet script and tests; `git diff --check` passed for the modified DayOA files.

At `2026-05-31T08:52Z`, the local status driver was patched so stale metric files are annotated with expected and observed Slurm job IDs. Remote `status.sh` was updated in place without touching active run scripts.

At `2026-05-31T08:53Z`, active job `4673` log showed BCL Convert had launched on compute host `i192mem-dy-all-1` with compute `/dev/shm=605G`, `/fsx=42%` used, and the generated benchmark sample sheet plus BCL Convert's copied report sample sheet both lacked `GenerateFastqcMetrics`.

Checkpoint at `2026-05-31T09:39Z`: `fsx_baseline_192` job `4673` completed with `convert_rc=0`, `total_seconds=3201`, and `output_bytes=601769593157`; `fsx_threadseek_192` job `4674` was running on `i192mem-dy-all-1`; jobs `4675`-`4677` were still dependency-pending. `/fsx` was `42%` used. Attempt-2 stale metrics for the later variants remain annotated by mismatched Slurm job IDs.

At `2026-05-31T09:43Z`, partition-specific testing was inserted:

- `fsx_threadseek_192` job `4674` is the explicit `i192mem` tuned test because Slurm placed it on `i192mem-dy-all-1`.
- Added `fsx_threadseek_i192bigmem` job `4678`, forced to `--partition i192bigmem`, with the same tuned FSx flags as `4674`.
- Updated `fsx_oversub_384` job `4675` to depend on `afterany:4678`, so the original chain resumes after the forced `i192bigmem` tuned test.
- Updated the queued `/dev/shm` case job `4677` to `Partition=i192bigmem`, because `i192mem` has about `605G` `/dev/shm` and the observed lane output is about `602G`, leaving too little margin for a meaningful RAM-output test.

Parallelism note: `/dev/shm` avoids most FSx output writes during conversion, but it still reads the BCL input from FSx and copies the final lane output back to FSx. It should not run concurrently with an FSx-output timing benchmark if the goal is clean timing; it can be overlapped only when measuring throughput under shared FSx input pressure.

At `2026-05-31T09:45Z`, the explicit `i192bigmem` FSx comparison was removed per operator direction. Rationale: treat `i192mem` and `i192bigmem` as equivalent for this benchmark unless `i192mem` trips a memory cap. Job `4678` was cancelled before running, and `fsx_oversub_384` job `4675` was restored to `afterany:4674`. The `/dev/shm` case remains forced to `i192bigmem` because the observed one-lane output size is too close to `i192mem` `/dev/shm` capacity.
