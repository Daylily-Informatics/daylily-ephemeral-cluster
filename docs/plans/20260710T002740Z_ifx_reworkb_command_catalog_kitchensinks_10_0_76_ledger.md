# 20260710T002740Z ifx-reworkB command catalog kitchen-sinks 10.0.76 ledger

## Objective

Run the updated DYEC command catalog rows for:

- `illumina_hg002_kitchensink_multiqc`
- `hybrid_ilmn_ont_snv_kitchensink`

Use DYEC `10.0.129`, DayOA `10.0.76`, cluster `ifx-reworkB`, profile `lsmc`, region `us-west-2`, and report F-scores, wall runtimes, and benchmark-derived costs after completion.

## Launch Parameters

- DYEC checkout: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DYEC commit/tag: `07aae755` / `10.0.129`
- DayOA commit/tag: `280daae` / `10.0.76`
- Cluster: `ifx-reworkB`
- Profile/region: `lsmc` / `us-west-2`
- Command codes: `illumina_hg002_kitchensink_multiqc,hybrid_ilmn_ont_snv_kitchensink`
- Jobs: `200`
- Parallel command rows: `1`
- Stamp: `20260710T002740Z`
- Output dir: `docs/plans/20260710T002740Z_ifx_reworkb_command_catalog_kitchensinks_10_0_76_logs`
- Driver log: `docs/plans/20260710T002740Z_ifx_reworkb_command_catalog_kitchensinks_10_0_76_driver.log`
- Evidence S3 root: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.129/dayoa-10.0.76/20260710T002740Z/`

## Execution Rows

| Row | State | Started UTC | Ended UTC | Notes |
| --- | --- | --- | --- | --- |
| PUSH-001 | SUCCESS | 2026-07-10T00:25:00Z | 2026-07-10T00:26:00Z | Pushed DYEC `jem-dev` and annotated tag `10.0.129` |
| RUN-001 | IN_PROGRESS | 2026-07-10T00:28:20Z |  | Launch both command catalog rows with `dyec tests command-catalog` |
| MON-001 | IN_PROGRESS | 2026-07-10T00:29:00Z |  | Monitor driver phases, Slurm queue, and controller status |
| ANALYZE-001 | PENDING |  |  | Collect F-scores, wall runtimes, and benchmark-derived costs |
| REPORT-001 | PENDING |  |  | Report result table and artifact locations |

## Live Notes

- 2026-07-10T00:27:40Z - Ledger opened for clean rerun after invalid `10.0.75` attempt. DYEC `dyec --json info` resolved `Version: 10.0.129`.
- 2026-07-10T00:28:20Z - Started local driver tmux session `dyec_ifx_reworkb_catalog_kitchensinks_10_0_76_20260710T002740Z` with evidence root `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.129/dayoa-10.0.76/20260710T002740Z/`.
- 2026-07-10T00:29:46Z - `ccv_warmup_illumina_hg002_kitchensink_multiqc_20260710T002740Z` completed with `exit_code=0`; clone reference was DayOA `10.0.76` / `280daae`.
- 2026-07-10T00:31:27Z - `ccv_warmup_hybrid_ilmn_ont_snv_kitchensink_20260710T002740Z` completed with `exit_code=0`.
- 2026-07-10T00:32:43Z - `ccv_dryrun_illumina_hg002_kitchensink_multiqc_20260710T002740Z` started. Slurm queue empty, as expected for dryrun.
- 2026-07-10T00:33:09Z - `ccv_dryrun_illumina_hg002_kitchensink_multiqc_20260710T002740Z` completed with `exit_code=0`.
- 2026-07-10T00:34:23Z - `ccv_dryrun_hybrid_ilmn_ont_snv_kitchensink_20260710T002740Z` started. No live sessions or Slurm jobs yet.
- 2026-07-10T00:34:49Z - `ccv_dryrun_hybrid_ilmn_ont_snv_kitchensink_20260710T002740Z` completed with `exit_code=0`.
- 2026-07-10T00:36:05Z - `ccv_live_illumina_hg002_kitchensink_multiqc_20260710T002740Z` started.
- 2026-07-10T00:40:00Z - ILMN live submitted Slurm jobs `2738`, `2739`, and `2740`; partitions observed were `i128` and `i128nvme`, with no `i384*` usage. HIOMR live is queued behind ILMN live because the catalog driver was launched with `--parallel 1`.
- 2026-07-10T00:43:00Z - Verified live status: catalog driver process still running; ILMN live `exit_code=null`, started `2026-07-10T00:36:05Z`; HIOMR live status missing/not launched yet. Current Slurm rows are `2739` on `i128` and `2740` on `i128nvme`; no `i384*` jobs observed.
