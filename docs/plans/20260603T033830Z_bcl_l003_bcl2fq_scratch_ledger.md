# L003 BCL Convert Scratch Test On bcl2fq Ledger

Created: 2026-06-03T03:38:30Z

## Control

- Ledger path: `docs/plans/20260603T033830Z_bcl_l003_bcl2fq_scratch_ledger.md`
- Log directory: `docs/plans/20260603T033830Z_bcl_l003_bcl2fq_scratch_logs/`
- Cluster: `dyec0602bcl`
- Profile: `lsmc`
- Region: `us-west-2`
- Headnode: `i-0c36c39770c533c8e`
- Queue/partition: `bcl2fq`
- Constraint: intentionally empty; use the scratch-backed BCL queue without forcing `nvme48`
- Requested lane: `L003`
- Run mount: `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4`
- Final DRA directory: `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/fasts_from_bclconvert_l003_scratch_test`
- Scratch output root: `/scratch/dayoa_bclconvert`
- Existing all-lane run policy: inspect only; do not cancel or alter jobs.

## Guardrails

- Use DayOA only through `dy-r` in a persistent initialized `ubuntu` tmux shell.
- Do not invoke `snakemake` directly for dry-run, live run, unlock, or recovery.
- Do not cancel, requeue, hold, release, drain/resume nodes, restart Slurm services, alter partitions, or otherwise administer Slurm without explicit approval.
- Do not use direct Slurm or raw BCL Convert fallback.
- Do not overwrite a non-empty final output directory.
- Write BCL Convert output to instance-local `/scratch` first, then move successful outputs to the DRA-backed final directory.

## Execution Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Ledger | Create durable ledger and log directory before remote execution. | SUCCESS | legitimate_safety_handling | Gate 0 | Orchestrator | This ledger and `docs/plans/20260603T033830Z_bcl_l003_bcl2fq_scratch_logs/`. |  | Control surface created before headnode work. |
| INV-001 | Inventory | Verify headnode, mount, SampleSheet, destination state, `bcl2fq`, and scratch-node visibility. | SUCCESS | legitimate_safety_handling | Gate 0 | Headnode Agent | `gate0_inventory.stdout.txt`: headnode `ip-10-0-0-235`, user `ubuntu`; run dir, SampleSheet, and `BaseCalls/L003` exist; destination does not exist; `bcl2fq` is up with `nvme64`, `nvme96`, and `nvme128` nodes visible idle; prior constrained jobs remain pending. |  | Parent mount is not writable by `ubuntu`, so prep may use targeted `sudo` to create/chown only the fresh final directory. |
| PREP-001 | DayOA workset | Prepare fresh DayOA checkout/workset, config, and `samples.tsv` without touching existing all-lane controller/jobs. | SUCCESS | feature_implementation | Gate 1 | Repo/DayOA Agent | `prep_workset_complete.stdout.txt`: workset `/fsx/analysis_results/dyec0602bcl/bcl_l003_bcl2fq_scratch_20260603T033830Z/daylily-omics-analysis`, patched scratch-support files, `config/bclconvert_l003_scratch.yaml`, `config/samples.tsv` with 41 samples, destination exists with `dest_file_count=0`. |  | Initial prep attempt parsed `[Data]`; `prep_failure_inspect.stdout.txt` showed actual `[BCLConvert_Data]` section, then prep completed using that section. |
| DRY-001 | Dry-run | Run `dy-r produce_bclconvert_fastqs` dry-run for L003 only in initialized tmux. | SUCCESS | feature_implementation | Gate 2 | Runner Agent | `dryrun_launch.stdout.txt`: tmux session `dayoa_bcl_l003_bcl2fq_scratch_20260603`; `RETURN CODE: 0`; job stats include exactly one `run_bclconvert_lane`; wildcard `lane=L003`; resources `partition=bcl2fq`, `threads=48`, `constraint=`; command passes `/scratch/dayoa_bclconvert`. |  | Dry-run proved no L001/L002/L004-L008 lane jobs are planned. |
| LIVE-001 | Live launch | Launch live `dy-r` only if dry-run proves exactly one L003 lane job on `bcl2fq` with scratch output. | SUCCESS | feature_implementation | Gate 3 | Runner Agent | `live_launch.stdout.txt`: live `dy-r` sent in the initialized tmux session; validation job finished; one L003 `run_bclconvert_lane` submitted as Slurm job `10`; resources show `partition=bcl2fq`, `threads=48`, `constraint=` and scratch root `/scratch/dayoa_bclconvert`. |  | Destination contains validation/provenance files only at launch capture; BCL Convert lane output has not completed yet. |
| MON-001 | Monitor | Monitor Slurm, tmux, scratch, DRA output, logs, and benchmarks read-only. | RUNNING | legitimate_safety_handling | Gate 4 | Monitor Agent | `monitor_20260603T035323Z.stdout.txt` and `monitor_20260603T035730Z.stdout.txt`: job `10` remains `PD` with reason `BeginTime`; DayOA controller processes remain alive; destination has validation/provenance only (`total_files=6`, `fastq_files=0`, `done_files=0`, `report_csv_files=0`); scratch root absent on headnode. |  | No scheduler intervention performed. |
| ACC-001 | Acceptance | Confirm L003 outputs, scratch-to-DRA move, benchmark runtime, and no unintended lane outputs. | PENDING | feature_implementation | Gate 5 | Acceptance Agent | `monitor_20260603T035730Z.stdout.txt`: only `bclconvert_validate_inputs.bench.tsv` exists (`s=0.6368`); `run_bclconvert.L003.bench.tsv` is not present yet. |  | Acceptance is not complete because the L003 Slurm job has not started. |

## Current State

- Previous all-lane pending work is deliberately out of scope except for read-only inventory.
- Gate 0 inventory completed at 2026-06-03T03:39:36Z. Existing all-lane jobs `1` through `9` were inspected but not modified.
- Prep completed at 2026-06-03T03:45:15Z. Workset is fresh and separate from the existing all-lane controller.
- Dry-run completed at 2026-06-03T03:46:23Z with return code 0 and exactly one L003 lane conversion job planned.
- Live run launched at 2026-06-03T03:48:39Z. Slurm job `10` was submitted for L003 and initially observed pending with reason `BeginTime`.
- First monitor at 2026-06-03T03:53:29Z: job `10` still pending with `BeginTime`; validation benchmark exists (`s=0.6368`), but L003 BCL Convert benchmark/output files do not exist yet.
- Delayed monitor at 2026-06-03T03:57:36Z: job `10` still pending with `BeginTime`; DayOA controller remains alive; destination remains validation-only with no FASTQs, no report CSVs, no `bclconvert.done`, and no L003 BCL Convert benchmark.

## Current Live State

- Tmux session: `dayoa_bcl_l003_bcl2fq_scratch_20260603`
- Workset: `/fsx/analysis_results/dyec0602bcl/bcl_l003_bcl2fq_scratch_20260603T033830Z/daylily-omics-analysis`
- Config: `/fsx/analysis_results/dyec0602bcl/bcl_l003_bcl2fq_scratch_20260603T033830Z/daylily-omics-analysis/config/bclconvert_l003_scratch.yaml`
- Slurm job: `10`
- Job state: `PD`
- Pending reason: `BeginTime`
- Destination: `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/fasts_from_bclconvert_l003_scratch_test`
- Destination file state: validation/provenance only; no L003 BCL Convert outputs yet.
- Existing all-lane jobs `1` through `9` remain untouched.
