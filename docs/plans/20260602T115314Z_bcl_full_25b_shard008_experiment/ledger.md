# 25B Full-Flowcell Shard008 Cleanup And Launch Ledger

Created: 2026-06-02T11:53:14Z

## Control Ledger

Controlling plan: user-approved chat plan, 2026-06-02
Ledger path: `docs/plans/20260602T115314Z_bcl_full_25b_shard008_experiment/ledger.md`
Prior Lane003 experiment: `docs/plans/20260601T234556Z_bcl_l003_25b_shard_experiment/`
Local artifact root: `bench_expts/`
Cluster: `dyec5117`
Profile: `lsmc`
Region: `us-west-2`
Run ID: `20260514_LH01106_0009_B23TVLGLT4`
Mounted run dir: `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/`
DayOA tag for full-flowcell launch: `2.0.36`
Full-flowcell Snakemake cap: `-j 300`

## Gate 0 Baseline

- Repo: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster`
- Branch: `codex/dyec515-full-catalog-20260531`
- Initial dirty state observed before new ledger creation: modified prior tuned status JSON and untracked tuned benchmark/harvest artifacts under `bench_expts/` and the prior plan directory.
- Existing cleanup evidence: `bench_expts/delete_collected_outputs.stdout.txt` records deletion of seven older `bcl25b_l003_*_20260602T000733Z` directories and `/fsx` free space moving from 702 GiB to 4.5 TiB.
- Known local evidence gap before this ledger: `bench_expts/` had only `shard008_cpu_tuned_odirect_on__fastq_sizes.tsv`; older shard FASTQ sizes were present under the prior ledger, while `whole_lane_odirect_off` and `shard008_odirect_off` lacked local FASTQ-size files.
- Destructive boundary: no further `/fsx/analysis_results` deletion without a second explicit confirmation against the generated `bench_expts/deletion_manifest.tsv`.

## Execution Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| FF-001 | Ledger | Create durable control ledger before further execution. | SUCCESS | plan_amendment | Gate 0 | orchestrator | This file. |  | Ledger created before new artifact harvest or deletion. |
| FF-002 | Local Evidence | Copy all generated Snakemake benchmark TSVs for completed cases into `bench_expts/` with case-prefixed names. | SUCCESS | feature_implementation | Gate 0 | orchestrator | `bench_expts/successful_shard_benchmark_manifest.tsv`; command log `command_logs/harvest_successful_shards_and_delete.ssm.json` response_code 0. |  | Saved 24 benchmark TSVs from currently remaining successful shard cases: `shard008_odirect_off` and `shard008_cpu_tuned_odirect_on`. Earlier successful shard benchmarks were already present locally. |
| FF-003 | FASTQ Sizes | Save raw FASTQ byte rows for each completed case and calculate case-level total, undetermined, and assigned FASTQ sizes. | NO_LONGER_NEEDED | feature_implementation | Gate 0 | orchestrator | User correction: "just save the benchmark.tsv files for all successful shard cases". |  | FASTQ-size capture removed from the pre-cleanup requirement by user direction. |
| FF-004 | Remote Inventory | Inventory current `/fsx/analysis_results/ubuntu/bcl25b_l003_*` directories and block on unknown paths. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | `command_logs/harvest_successful_shards_and_delete.stdout.txt`; `bench_expts/deletion_manifest.tsv`. |  | Inventory found five remaining BCL experiment directories with expected `bcl25b_l003_*` names. |
| FF-005 | Delete Manifest | Generate exact deletion manifest only for existing remote analysis dirs whose local artifacts are complete. | SUCCESS | legitimate_safety_handling | Gate 1 | orchestrator | `bench_expts/deletion_manifest.tsv`. |  | Manifest contains the five remaining BCL experiment analysis directories. |
| FF-006 | Destructive Approval | Get second explicit approval before deleting manifest paths. | SUCCESS | legitimate_safety_handling | Gate 1 | user | User replied `ONFIRM DELETE MANIFEST` after exact five-path manifest was shown. |  | Approval accepted as explicit confirmation for the displayed manifest. |
| FF-007 | FSx Cleanup | Delete only paths in `bench_expts/deletion_manifest.tsv`, then verify absence and `/fsx` free space. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `bench_expts/deleted_analysis_dirs.tsv`; `command_logs/harvest_successful_shards_and_delete.stdout.txt`; SSM command `409fae32-75d8-4d21-a199-df321b2febd0`. |  | Deleted five manifest paths; verification found no remaining `bcl25b_l003_*` dirs and `/fsx` showed 4.7T available. |
| FF-008 | Full-Flowcell Preflight | Verify mounted run path, lanes, sample sheet, RunInfo, FSx free space, and no conflicting active workflow. | SUCCESS | feature_implementation | Gate 2 | orchestrator | `metadata/full_flowcell_preflight.stdout.txt`; `metadata/full_flowcell_preflight_summary.json`. |  | Eight lanes found; each had 784 filter files; sample sheet had no Lane column; `squeue` empty; `/fsx` available bytes `6751276892160`; no old `bcl25b_l003_*` dirs remained. |
| FF-009 | Run Context | Write full-flowcell run context TSV using the mounted run and verified lane list. | SUCCESS | feature_implementation | Gate 2 | orchestrator | `runs_full.tsv`; `scripts/launch_full_flowcell.py`. |  | Run context written for mounted 25B run and launch wrapper set lanes to `L001,L002,L003,L004,L005,L006,L007,L008`. |
| FF-010 | Launch | Launch full-flowcell `shard008` with DayOA `2.0.36`, no merge, ODIRECT on, and `-j 300`. | SUCCESS | feature_implementation | Gate 2 | orchestrator | First launch `bcl25b_full_shard008_20260602T115314Z` exited 1 before jobs; retry `bcl25b_full_shard008_retry1_20260602T115314Z` status has no exit code and Slurm shows 64 submitted shard jobs. | Initial nested JSON was not single-quoted inside `--dy-command`, so DayOA saw `bclconvert` as a string. | Relaunch wrapper corrected to `bclconvert='{\"...\"}'`; retry entered Snakemake scheduling. |
| FF-010A | Failed Attempt Cleanup | Stop failed ODIRECT full-flowcell attempt and delete its analysis output before replacement launch. | SUCCESS | legitimate_safety_handling | User emergency cleanup approval | orchestrator | `command_logs/stop_and_delete_failed_full_attempt.stdout.txt`; SSM response_code 0. | BCL Convert DRAGEN watchdog hung with ODIRECT/shared-thread output on FSx. | Killed tmux controller `bcl25b_full_shard008_retry1_20260602T115314Z`, canceled 53 Slurm jobs whose `WorkDir` exactly matched the failed repo, verified absence, and deleted `/fsx/analysis_results/ubuntu/bcl25b_full_shard008_retry1_20260602T115314Z` (`du` 563G). |
| FF-010B | Replacement Launch | Relaunch full-flowcell `shard008` with ODIRECT disabled, no merge, DayOA `2.0.36`, and `-j 300`. | RUNNING | feature_implementation | User emergency relaunch approval | orchestrator | `metadata/dy_command_full_shard008.txt`; workflow status for `bcl25b_full_shard008_odirect_off_20260602T115314Z`; queue check showed 64 submitted jobs with most running and 8 configuring. |  | Replacement session `bcl25b_full_shard008_odirect_off_20260602T115314Z`; command has `shared_thread_odirect_output=false`, `merge_lane_fastqs=false`, and `merge_tile_fastqs=false`. |
| FF-011 | Full-Flowcell Harvest | Copy full-flowcell benchmarks and FASTQ-size rows after completion. | OPEN | feature_implementation | Gate 3 | orchestrator | Pending full-flowcell completion. |  |  |
| FF-012 | Report | Report benchmark-provided metrics plus calculated FASTQ-size totals, without recomputing benchmark metrics. | OPEN | feature_implementation | Gate 3 | orchestrator | Pending final report. |  |  |

## Full-Flowcell Intended Command Shape

The full-flowcell launch must use:

- `--git-tag 2.0.36`
- `bin/day_run produce_bclconvert_fastqs -p -j 300 -k`
- `tile_shard_level=8`
- `tile_shard_threads=48`
- `tile_parallel_tiles=8`
- `tile_conversion_threads=2`
- `tile_compression_threads=24`
- `tile_decompression_threads=8`
- `merge_lane_fastqs=false`
- `merge_tile_fastqs=false`
- `shared_thread_odirect_output=true`
- `tile_shard_lanes=<verified lanes>`

With eight verified lanes, the expected shape is 64 BCL Convert shard jobs, six running concurrently under `-j 300`.

## Live Status Notes

- 2026-06-02T13:01:37Z: Workflow `bcl25b_full_shard008_retry1_20260602T115314Z` still running on `dyec5117`; `workflow status` returned `exit_code: null`, `completed_at: null`.
- 2026-06-02T13:01:37Z: `headnode jobs` showed 56 running `run_bclconvert_tile_shard` jobs on `i192mem`; visible active jobs were using 48 CPUs and 180000M each.
- 2026-06-02T12:59:33Z: Compute-node SSH sample saved to `live_status/node_load_io_compact.tsv`; active nodes appeared mostly idle from OS counters: load near 0-1 on 192-vCPU hosts, available memory near 741 GiB, and measured network/block IO near zero. `bcl-convert` processes were present but using roughly 0-2% aggregate CPU per node at the sample moment.
- 2026-06-02T13:01:37Z: Controller log tail showed Snakemake had retried earlier failures for `L008/0006_tiles0491-0588` and `L002/0002_tiles0099-0196`; no Slurm or job intervention performed.
- 2026-06-02T13:06:44Z: Focused failed-shard diagnostics saved to `live_status/terminal_failed_bcl_logs.stdout.txt`. Three shards had durable failure evidence after retry: `L008/0007_tiles0589-0686`, `L002/0005_tiles0393-0490`, and `L005/0002_tiles0099-0196`. All three logs showed host `i192mem-dy-all-7` and BCL Convert internal DRAGEN watchdog failure: `Hang detected - there has been no system activity for 600 seconds`, `No thread activity for 600 seconds`, `No I/O activity detected for 600 seconds`, followed by `WatchDogException`. Logs also emitted `shared-thread-linux-native-asio output could have low performance or hang if output directory is on a distributed file system`.
- 2026-06-02T13:12:39Z: Emergency cleanup executed for failed ODIRECT attempt after user approval. Script stopped tmux controller, canceled only Slurm jobs whose `WorkDir` exactly matched `/fsx/analysis_results/ubuntu/bcl25b_full_shard008_retry1_20260602T115314Z/daylily-omics-analysis`, verified matched jobs absent, and deleted `/fsx/analysis_results/ubuntu/bcl25b_full_shard008_retry1_20260602T115314Z`.
- 2026-06-02T13:13:21Z: Replacement launch started as `bcl25b_full_shard008_odirect_off_20260602T115314Z` with `shared_thread_odirect_output=false`, `merge_lane_fastqs=false`, `merge_tile_fastqs=false`, DayOA `2.0.36`, and `-j 300`.
- 2026-06-02T13:14:xxZ: Replacement queue check showed 64 submitted BCL tile-shard jobs; most running on existing `i192mem` nodes and 8 still configuring on nodes 15/16.
