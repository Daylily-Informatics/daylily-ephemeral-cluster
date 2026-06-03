# bcl2fq Scratch BCL Convert To DRA Ledger

Created: 2026-06-03T01:11:21Z

## Control

- Ledger path: `docs/plans/20260603T011121Z_bcl2fq_scratch_to_dra_ledger.md`
- Log directory: `docs/plans/20260603T011121Z_bcl2fq_scratch_to_dra_logs/`
- Cluster: `dyec0602bcl`
- Profile: `lsmc`
- Region: `us-west-2`
- Queue/partition: `bcl2fq`
- Requested shape: 48 vCPU `bcl2fq` node-local `/scratch`
- Run mount: `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/`
- Requested final directory: `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/fasts_from_bclconvert`

## Guardrails

- Do not invoke Snakemake directly. This direct Slurm test is for `bcl-convert` itself; if DayOA workflow execution is needed later, use `dy-r` in an initialized persistent `ubuntu` tmux shell.
- Do not cancel, requeue, hold, release, drain/resume nodes, restart Slurm services, or otherwise administer Slurm without explicit approval.
- Do not overwrite an existing DRA destination directory. If `fasts_from_bclconvert` already exists, stop and report the blocker.
- Do not enable or use `DELETED` auto-export. The DRA is read/write for `NEW,CHANGED` only.
- Write BCL Convert output to node-local `/scratch` first, then move/copy successful outputs to the DRA directory.

## Gate 0 Baseline

- User request: run a BCL Convert test on the special queue using the 48-vCPU shape, write to fast instance scratch, then move to the DRA run directory under `fasts_from_bclconvert`.
- Prior mount ledger: `docs/plans/20260602T235433Z_dyec0602bcl_bcl2fq_run_mount_ledger.md` records DRA `dra-04d1f5b3dd1cc75a4`, lifecycle `AVAILABLE`, path `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/`, and read/write amendment with `AutoExportPolicy=NEW,CHANGED`.
- Memory-derived BCL caution: avoid `shared_thread_odirect_output=true` on this FSx/full-flowcell shape; use `false`.

## Execution Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Baseline | Record request, guardrails, queue, run mount, and destination before launch. | SUCCESS | legitimate_safety_handling | Gate 0 | Agent | This ledger. |  | Baseline recorded before launch. |
| INV-001 | Headnode inventory | Verify cluster/headnode, `bcl2fq` partition shape, run mount usability, and destination absence. | SUCCESS | legitimate_safety_handling | Gate 0 | Agent | `headnode_inventory.stdout.txt`: user `ubuntu`, host `ip-10-0-0-235`, `bcl2fq` partition includes `bcl2fq-dy-nvme48-[1-4]` with `CPUS=48` and feature `nvme48`; SampleSheet exists; destination exists `no`; parent writable by ubuntu `no`. |  | Need targeted `sudo` to create only `fasts_from_bclconvert` writable by `ubuntu`; no overwrite blocker. |
| PREP-001 | Job script | Create explicit headnode job script that writes BCL Convert outputs to `/scratch` and moves successful output to DRA `fasts_from_bclconvert`. | SUCCESS | feature_implementation | Gate 1 | Agent | Local scripts in `bclconvert_scratch_to_dra.job.sh` and `submit_bclconvert_scratch_to_dra.sh`; remote destination prepared in `remote_prepare.stdout.txt`; remote write used short-comment SSM helper after `write_remote_text` exceeded AWS SSM comment length. |  | Destination exists, is empty, and is owned by `ubuntu`; job scripts are executable under `/home/ubuntu/daylily-runs/bcl2fq_scratch_to_dra_20260603T011121Z/`. |
| RUN-001 | Launch | Submit the BCL Convert scratch job from a persistent `ubuntu` tmux shell. | SUCCESS | feature_implementation | Gate 1 | Agent | `tmux_submit.stdout.txt`: tmux session `bcl2fq_scratch_dra_20260603T011121Z`, Slurm job ID `1`, partition `bcl2fq`, initial state `CF`, node `bcl2fq-dy-nvme48-1`. |  | Submitted with `--partition=bcl2fq`, `--constraint=nvme48`, `--cpus-per-task=48`, scratch output `/scratch`, final DRA destination `fasts_from_bclconvert`. |
| MON-001 | Monitor | Monitor controller/job status and BCL logs without scheduler intervention. | BLOCKED | legitimate_safety_handling | Gate 2 | Agent | Initial `squeue` in `tmux_submit.stdout.txt`: job `1` in `CF`; `monitor_20260603T011901Z.stdout.txt`: job `1` pending with reason `BeginTime`; `monitor_20260603T025801Z.stdout.txt` and `final_status_20260603T025856Z.stdout.txt`: job `1` pending with reason `ReqNodeNotAvail`, unavailable nodes `bcl2fq-dy-nvme48-[1-4]`. | AWS returned `InsufficientInstanceCapacity` for all four requested 48-vCPU `nvme48` dynamic nodes. | Submitted job remains queued; monitoring stopped without scheduler/node intervention. |
| ACC-001 | Acceptance | Confirm final DRA directory exists, output was written after successful scratch run, and no delete/export-delete behavior occurred. | BLOCKED | feature_implementation | Gate 3 | Agent | `monitor_20260603T025801Z.stdout.txt` and `final_status_20260603T025856Z.stdout.txt`: destination count is `0`; no BCL Convert logs or Slurm stdout/stderr have been produced because the job has not started. | AWS capacity unavailable for requested 48-vCPU shape. | Acceptance is not complete; DRA destination remains empty. |

## Current Live State

- Direct Slurm job: `1`
- Direct tmux session: `bcl2fq_scratch_dra_20260603T011121Z`
- DayOA tmux session: `dayoa_bcl2fq_scratch_dra_20260603`
- DayOA checkout: `/fsx/analysis_results/dyec0602bcl/bcl2fq_scratch_dra_dayoa_20260603/daylily-omics-analysis`
- DayOA run config: `/fsx/analysis_results/dyec0602bcl/bcl2fq_scratch_dra_dayoa_20260603/daylily-omics-analysis/config/bclconvert_scratch_dra.yaml`
- Work directory: `/home/ubuntu/daylily-runs/bcl2fq_scratch_to_dra_20260603T011121Z`
- Final destination: `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/fasts_from_bclconvert`
- Current blocker: all requested `bcl2fq` `nvme48` dynamic nodes are unavailable with `InsufficientInstanceCapacity`.
- Scheduler boundary: no cancel, requeue, node resume, drain/resume, partition change, or alternate-shape fallback was performed.

## DayOA Amendment

- User correction: the BCL Convert test must run through DayOA/`dy-r`, not a direct Slurm one-off, so the scratch-output behavior works again on other clusters.
- Local source repo updated: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
  - `workflow/rules/bclconvert.smk`: added `bclconvert.scratch_output_root` and `bclconvert.constraint` wiring into BCL Convert Slurm resources and helper invocation.
  - `workflow/scripts/run_bclconvert_lane.sh`: added scratch-output staging, non-empty final output refusal, validation of scratch reports, and `rsync --remove-source-files` move to the normal DayOA output path.
  - `config/day/day_env_installer.sh`: added Mermaid CLI browser-payload install/smoke-render validation so live DayOA runs do not fail before Snakemake when Puppeteer Chrome is absent.
  - Tests updated for the new BCL scratch/constraint and Mermaid browser contracts.
- Local verification:
  - `python -m pytest tests/test_bclconvert_multiqc.py tests/test_shell_wrapper_contracts.py -q`: 28 passed.
  - `bash tests/test_bclconvert_bootstrap.sh`: 11 passed.
- Headnode DayOA workset:
  - Cloned via `day-clone -t codex/dayoa-bclconvert-tile-shards-20260601 -d bcl2fq_scratch_dra_dayoa_20260603`.
  - Patched from local repo diffs and configured with `config/bclconvert_scratch_dra.yaml`.
  - Generated `config/samples.tsv` with 41 Sample_ID rows from the mounted SampleSheet.
  - Installed and smoke-tested `chrome-headless-shell@148.0.7778.97` for `mmdc`.
- DayOA execution:
  - Dry-run command in tmux: `dy-r produce_bclconvert_fastqs -p -k -j 8 --rerun-triggers mtime --configfile config/bclconvert_scratch_dra.yaml -n`, return code `0`.
  - Live command in tmux: `dy-r produce_bclconvert_fastqs -p -k -j 8 --rerun-triggers mtime --configfile config/bclconvert_scratch_dra.yaml`.
  - `dayoa_monitor_20260603T031808Z.stdout.txt`: DayOA submitted Slurm jobs `2` through `9`, each in partition `bcl2fq` with `constraint=--constraint=nvme48`, 48 threads, and scratch root `/scratch/dayoa_bclconvert`; all are pending because `bcl2fq-dy-nvme48-[1-4]` are unavailable.
  - `dayoa_final_status_20260603T032104Z.stdout.txt`: DayOA controller processes remain alive; jobs `2` through `9` remain pending on `bcl2fq` with `ReqNodeNotAvail, UnavailableNodes:bcl2fq-dy-nvme48-[1-4]`; destination currently contains six validation/provenance files and no FASTQ outputs.

## Final State At 2026-06-03T03:21:12Z

- DayOA/`dy-r` implementation and launch are complete through submission.
- Acceptance is still blocked by AWS capacity for the requested 48-vCPU `nvme48` dynamic nodes.
- No Slurm job, node, partition, or scheduler intervention was performed.
- The earlier direct Slurm job `1` is still pending on the same unavailable nodes and was not cancelled because cancellation is a scheduler/job intervention requiring explicit approval.
- The durable DayOA code changes are present in `/Users/jmajor/projects/daylily/daylily-omics-analysis` and were also applied to the headnode checkout used by the live `dy-r` controller.

## Status Refresh At 2026-06-03T03:23:11Z

- Evidence: `docs/plans/20260603T011121Z_bcl2fq_scratch_to_dra_logs/status_refresh_20260603T032306Z.stdout.txt`.
- DayOA tmux session `dayoa_bcl2fq_scratch_dra_20260603` is still present and the `dy-r`/Snakemake controller processes are still alive.
- DayOA jobs `2` through `9` remain `PD` in partition `bcl2fq` with reason `ReqNodeNotAvail, UnavailableNodes:bcl2fq-dy-nvme48-[1-4]`.
- Direct job `1` also remains `PD` on the same unavailable node set.
- `bcl2fq-dy-nvme48-[1-4]` are `idle~` with reason `Enabling node since insufficient capacity timeout expired`; alternate larger `bcl2fq` nodes are visible but were not used because that would be an alternate-shape fallback.
- Destination `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/fasts_from_bclconvert` has `total_files=6`, `fastq_files=0`, and `done_files=0`.
- Scratch root `/scratch/dayoa_bclconvert` is absent, which is consistent with no lane job having started.

## Status Refresh At 2026-06-03T03:25:36Z

- Evidence: `docs/plans/20260603T011121Z_bcl2fq_scratch_to_dra_logs/status_refresh_20260603T032530Z.stdout.txt`.
- No BCL Convert lane jobs have run yet. Jobs `2` through `9` remain pending; jobs `5` through `9` show `ReqNodeNotAvail` on `bcl2fq-dy-nvme48-[1-4]`, and jobs `2` through `4` are pending with `BeginTime`.
- The requested `nvme48` nodes are `down#` with `(Code:InsufficientInstanceCapacity)Failure when resuming nodes`.
- The DRA destination contains only DayOA validation/provenance files from the controller: `total_files=6`, `fastq_files=0`, `done_files=0`, `report_csv_files=0`.
- The only DRA destination directories present are the top directory plus `benchmarks`, `logs`, and `tables`; there are no `lane_fastqs` or `lane_reports` directories.
- Scratch root `/scratch/dayoa_bclconvert` is absent, confirming that no successful or partial scratch-stage BCL Convert lane output is present on a compute node.

## Benchmark Check At 2026-06-03T03:26:24Z

- Evidence: `docs/plans/20260603T011121Z_bcl2fq_scratch_to_dra_logs/benchmarks_status_20260603T032618Z.stdout.txt`.
- The only benchmark file in the DRA destination is `benchmarks/bclconvert_validate_inputs.bench.tsv`.
- Validation benchmark values: `s=0.5314`, `h:m:s=0:00:00`, `cpu_time=0.04`, `snakemake_threads=1`.
- Expected lane BCL Convert benchmark files `run_bclconvert.L001.bench.tsv` through `run_bclconvert.L008.bench.tsv` are all missing, so there is no benchmark-recorded runtime for BCL Convert lane jobs yet.
