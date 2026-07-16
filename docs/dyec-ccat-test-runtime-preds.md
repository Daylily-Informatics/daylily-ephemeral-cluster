# DYEC Command Catalog Runtime Predictions

Prepared: `2026-07-08T14:20:53Z` / `2026-07-08 07:20:53 PDT`

Scope: predicted completion schedule for the `jul8itelx4` Intel command catalog plus BJuice run described as DYEC `10.0.118`, DayOA `10.0.70`, cluster `jul8itelx4`, `-j 300 -p -k`, 15 selected commands.

Boundary: this is static analysis only. No DYEC command, AWS command, headnode command, Slurm query, export, cleanup, or workflow action was run for this estimate.

## Inputs Used

- Current catalog source: `config/daylily_pipeline_command_catalog.yaml`
- Prior benchmark profile: `docs/plans/20260707T144453Z_benchmark_resource_review/command_catalog_performance_summary.tsv`
- Prior performance ledger: `docs/plans/20260708T023632Z_command_catalog_performance_profiles_ledger.md`
- Headnode update readiness ledger: `docs/plans/20260708T140150Z_dyec_10_0_118_headnode_update_ledger.md`

The active catalog-run ledger named in the pasted plan was not present locally when this was written. The runbook path named in the pasted plan, `docs/PR_runbook_dyec_10.0.118.md`, was also not present locally. Because of that, the command start/end times below are predictions anchored to a stated assumed launch schedule, not observed live status.

## Selected Command Set

Static catalog selection resolves to 15 commands:

- 14 commands matching `type: prod` and `compatible_cluster_types: daywgs`
- 1 explicit dev exception: `inflection-bjuice-product-v0.1`

Those 15 commands split into:

- 12 slim-data sample-analysis commands that can start immediately after Gate 0/render/staging.
- 3 run-analysis commands that may need run-directory DRA readiness before launch.

The catalog default DayOA ref is `10.0.70`; all selected catalog rows have command-level `git_tag: 10.0.70` except the BJuice dev exception, which is still the explicit scoped exception but is catalog-pinned to DayOA `10.0.70`.

## Schedule Assumptions

Base assumption: the operator continues from the ready headnode state and starts Gate 0/catalog orchestration at `2026-07-08T14:25:00Z` / `07:25 PDT`.

If the real catalog launch start differs, shift the command table by the difference from the predicted start times.

Assumed orchestration windows:

| Workstream | Predicted start UTC | Predicted end UTC | Predicted start PDT | Predicted end PDT | Notes |
|---|---:|---:|---:|---:|---|
| Gate 0 inventory, ledger setup, render/stage prep | 2026-07-08 14:25 | 2026-07-08 14:45 | 07:25 | 07:45 | Uses already-refreshed `jul8itelx4` headnode evidence from the `10.0.118` headnode-update ledger. |
| Sample-analysis launch wave | 2026-07-08 14:45 | 2026-07-08 14:58 | 07:45 | 07:58 | 12 sample-analysis commands launched by agents 01-12. |
| Run-data mount inspect/create/verify | 2026-07-08 14:35 | 2026-07-08 15:35 | 07:35 | 08:35 | Assumes missing or unusable run-control data requires read-only run DRAs; this is the main early uncertainty. |
| Run-analysis launch wave | 2026-07-08 15:38 | 2026-07-08 15:42 | 08:38 | 08:42 | 3 run-QC commands launched after run-directory readiness. |
| Export, S3 count/byte verification, cleanup | 2026-07-08 15:20 | 2026-07-08 21:45 | 08:20 | 14:45 | Runs per completed analysis; final tail controlled by BJuice/hybrid plus final ledger uploads. |

Expected entire-plan completion: `2026-07-08T21:45:00Z` / `14:45 PDT`.

Conservative completion band: `2026-07-08T20:45:00Z` to `2026-07-08T23:00:00Z` / `13:45` to `16:00 PDT`.

The lower end assumes run-directory sources are already mounted/usable and BJuice behaves like the prior benchmark profile. The upper end assumes a full run-DRA wait, Slurm cold-start/configuring tails, and slower export/cleanup verification for the hybrid/BJuice analyses.

## Command-Level Predictions

`Terminal end` means the command is expected to have reached one of the plan terminal states after export verification and cleanup when applicable, normally `succeeded_exported_cleaned`. `Live end` means workflow execution is expected to be complete, before export and cleanup.

| # | Command | Class | Data profile | Predicted start UTC | Predicted live end UTC | Predicted terminal end UTC | Predicted start PDT | Predicted terminal end PDT | Confidence | Basis |
|---:|---|---|---|---:|---:|---:|---:|---:|---|---|
| 1 | `illumina_snv_alignstats` | sample | `default_reads_slim` | 2026-07-08 14:45 | 2026-07-08 15:20 | 2026-07-08 15:40 | 07:45 | 08:40 | Medium | Prior profile: 26 benchmark rows, 19 submitted jobs, 16 rules, 692 task-wall seconds; add clone/render/export buffer. |
| 2 | `illumina_snv_alignstats_relatedness_vep_multiqc` | sample | `default_reads_slim` | 2026-07-08 14:46 | 2026-07-08 16:05 | 2026-07-08 16:25 | 07:46 | 09:25 | Medium | Prior profile: 106 rows, 89 submitted jobs, 47 rules, 3,627 task-wall seconds. |
| 3 | `illumina_hg002_kitchensink_multiqc` | sample | `default_reads_slim` | 2026-07-08 14:47 | 2026-07-08 16:10 | 2026-07-08 16:35 | 07:47 | 09:35 | Medium | Prior profile: 116 rows, 93 submitted jobs, 58 rules, 3,811 task-wall seconds; includes MultiQC and evidence-manifest targets. |
| 4 | `ultima_snv_alignstats` | sample | `default_reads_slim` | 2026-07-08 14:48 | 2026-07-08 15:20 | 2026-07-08 15:35 | 07:48 | 08:35 | Medium | Prior profile: 23 rows, 19 submitted jobs, 13 rules, 407 task-wall seconds. |
| 5 | `ultima_snv_alignstats_kitchensink` | sample | `default_reads_slim` | 2026-07-08 14:49 | 2026-07-08 16:00 | 2026-07-08 16:20 | 07:49 | 09:20 | Medium | Prior profile: 97 rows, 83 submitted jobs, 39 rules, 2,923 task-wall seconds. |
| 6 | `ont_snv_alignstats` | sample | `default_reads_slim` | 2026-07-08 14:50 | 2026-07-08 15:45 | 2026-07-08 16:05 | 07:50 | 09:05 | Medium-low | Prior profile: 19 rows, 17 submitted jobs, max rule wall about 16.6 minutes; ONT tasks showed wider tails than Illumina/Ultima. |
| 7 | `ont_snv_alignstats_kitchensink` | sample | `default_reads_slim` | 2026-07-08 14:51 | 2026-07-08 16:55 | 2026-07-08 17:20 | 07:51 | 10:20 | Medium-low | Prior profile: 93 rows, 81 submitted jobs, 35 rules, 6,779 task-wall seconds. |
| 8 | `pacbio_snv_alignstats` | sample | `default_reads_slim` | 2026-07-08 14:52 | 2026-07-08 15:45 | 2026-07-08 16:05 | 07:52 | 09:05 | Medium-low | Prior profile: 19 rows, 17 submitted jobs, max rule wall about 13.1 minutes; long-read scheduler tails likely. |
| 9 | `roche_snv_alignstats` | sample | `default_reads_slim` | 2026-07-08 14:53 | 2026-07-08 15:05 | 2026-07-08 15:20 | 07:53 | 08:20 | Medium | Prior profile: 4 rows, 2 submitted jobs, 305 task-wall seconds. |
| 10 | `hybrid_ilmn_ont_snv` | sample | `default_reads_slim` | 2026-07-08 14:54 | 2026-07-08 19:15 | 2026-07-08 19:55 | 07:54 | 12:55 | Low-medium | Prior profile: 742 rows, 738 submitted jobs, 28 rules, 51,396 task-wall seconds, 188.6 allocated vCPU-hours. |
| 11 | `hybrid_ilmn_ont_snv_kitchensink` | sample | `default_reads_slim` | 2026-07-08 14:55 | 2026-07-08 19:45 | 2026-07-08 20:30 | 07:55 | 13:30 | Low-medium | Prior profile: 822 rows, 806 submitted jobs, 60 rules, 53,965 task-wall seconds, 201.9 allocated vCPU-hours. |
| 12 | `inflection-bjuice-product-v0.1` | sample | `default_reads_slim` | 2026-07-08 14:56 | 2026-07-08 20:30 | 2026-07-08 21:15 | 07:56 | 14:15 | Low | Prior profile: 680 rows, 676 submitted jobs, 36 rules, 58,206 task-wall seconds, 232.7 allocated vCPU-hours; this is the tail-risk command. |
| 13 | `illumina_run_qc` | run | `illumina_run_directory` | 2026-07-08 15:38 | 2026-07-08 16:00 | 2026-07-08 16:20 | 08:38 | 09:20 | Medium-low | Start gated by run-directory availability; prior profile itself was quick: 5 rows, 53 task-wall seconds. |
| 14 | `ont_run_qc` | run | `ont_run_directory` | 2026-07-08 15:40 | 2026-07-08 16:45 | 2026-07-08 17:10 | 08:40 | 10:10 | Medium-low | Start gated by run-directory availability; prior profile max rule wall about 40.3 minutes and 2,574 task-wall seconds. |
| 15 | `ultima_run_qc` | run | `ultima_run_directory` | 2026-07-08 15:42 | 2026-07-08 15:50 | 2026-07-08 16:05 | 08:42 | 09:05 | Low-medium | Start gated by run-directory availability; prior successful profile was tiny, but prior retries indicate config/report fragility. |

## Completion Drivers

The plan completion tail is not the small sample commands. It is:

1. Run-directory DRA readiness for the 3 run-analysis rows, if `/fsx/control_data/run_data/*` is absent or unusable.
2. Slurm cold-start and spot capacity/configuring time on the large sample-analysis rows.
3. The three high-job-count rows: `hybrid_ilmn_ont_snv`, `hybrid_ilmn_ont_snv_kitchensink`, and `inflection-bjuice-product-v0.1`.
4. Post-success export verification and cleanup. This is correctly serialized per analysis root by the plan and must not be skipped to claim terminal success.

## Risk Notes

- The prior benchmark profile is from DYEC `10.0.103` and DayOA `10.0.64`, while this run is DYEC `10.0.118` and DayOA `10.0.70`. It is still the best local evidence for runtime shape, but the estimate should be treated as a forecast, not a measured SLA.
- `total_wall_s` in the benchmark profile is task-wall aggregation, not controller wall-clock. The command table applies an empirical orchestration/scheduler/export buffer to that task evidence.
- The plan says all live commands should be normalized to `-j 300 -p -k`. Prior profiles mostly used `-j 250`; `-j 300` helps only if Slurm capacity exists and rule resource requests permit useful packing.
- If run DRAs enter long `CREATING`, do not declare mount failure before the plan's 40-minute minimum patience window. The prediction already allows about 60 minutes for mount readiness.
- Cleanup must wait for object-count and byte-count export verification. Ending a workflow successfully is not enough for the plan's acceptance condition.

## Rebase Formula

If the real first sample-command start is available from the live ledger, rebase every command prediction by:

```text
delta = actual_first_sample_start - 2026-07-08T14:45:00Z
rebased_time = predicted_time + delta
```

For run-analysis commands, rebase against the actual run-directory-ready timestamp if run mounts are the controlling delay.
