# 20260709T232804Z ifx-reworkB command catalog kitchen-sinks ledger

## Objective

Run the updated DYEC command catalog rows for:

- `hybrid_ilmn_ont_snv_kitchensink`
- `illumina_hg002_kitchensink_multiqc`

Use DayOA tag `10.0.75` (max semver tag resolved on 2026-07-09), cluster `ifx-reworkB`, profile `lsmc`, region `us-west-2`, and report F-scores, wall runtimes, and benchmark-derived costs.

## Launch Parameters

- DYEC checkout: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch: `jem-dev`
- Local catalog state: dirty working tree containing command-specific mounted read templates
- Cluster: `ifx-reworkB`
- Profile/region: `lsmc` / `us-west-2`
- DayOA tag: `10.0.75`
- Command codes: `illumina_hg002_kitchensink_multiqc,hybrid_ilmn_ont_snv_kitchensink`
- Jobs: `200`
- Stamp: `20260709T232804Z`
- Output dir: `docs/plans/20260709T232804Z_ifx_reworkb_command_catalog_kitchensinks_logs`
- Driver log: `docs/plans/20260709T232804Z_ifx_reworkb_command_catalog_kitchensinks_driver.log`
- Evidence S3 root: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.129-dev/dayoa-10.0.75/20260709T232804Z/`

## Gate 0 Inventory

| Item | Status | Evidence |
| --- | --- | --- |
| DayOA max semver tag | SUCCESS | `10.0.75` resolved from local `daylily-omics-analysis` tags after fetch |
| DYEC cluster | SUCCESS | `ifx-reworkB` is `CREATE_COMPLETE`, compute fleet `RUNNING`, headnode `i-059642d9ee4d5c9ea` |
| Command catalog templates | SUCCESS | Catalog rows render mounted `/fsx/data/...` read paths with `STAGE_DIRECTIVE=pass_through` |
| Catalog unit tests | SUCCESS | `pytest -q tests/test_repository_catalog.py tests/test_tests_runner.py::test_write_sample_manifest_uses_command_specific_templates tests/test_staging_examples.py` passed, 35 tests |
| Existing Slurm activity | NOTE | Prior Betelgeuse HIOMR jobs were active on `i128nvme`; no cancellation requested for this launch |

## Execution Rows

| Row | State | Started UTC | Ended UTC | Notes |
| --- | --- | --- | --- | --- |
| RUN-001 | FAILED_INVALID | 2026-07-09T23:28:04Z | 2026-07-10T00:13:00Z | Aborted after DayOA `10.0.75` emitted `i384nvme` partition candidates and one job entered `CONFIGURING` on an i384 node |
| MON-001 | SUCCESS | 2026-07-09T23:31:00Z | 2026-07-10T00:13:00Z | Monitored driver phases, Slurm queue, and controller status through abort |
| ANALYZE-001 | PENDING |  |  | Collect F-scores, wall runtimes, and benchmark-derived costs |
| REPORT-001 | PENDING |  |  | Report concise result table and artifact locations |

## Live Notes

- 2026-07-09T23:28:04Z - Ledger opened before live command-catalog launch.
- 2026-07-09T23:28:04Z - Starting command-catalog driver.
- 2026-07-09T23:31:00Z - Warmup sessions created for both catalog rows. Headnode tmux logs show `--conda-create-envs-only` running through `dy-r`; no new Slurm jobs submitted yet.
- 2026-07-09T23:35:00Z - `ccv_warmup_hybrid_ilmn_ont_snv_kitchensink_20260709T232804Z` exited `1` during shared conda env creation: `CondaError: Cannot link a source that does not exist` for `somalier.yaml`. Likely cause is concurrent warmups sharing the same `/fsx/resources/environments/conda/...` prefix.
- 2026-07-09T23:40:59Z - Both dryruns completed `0`. ILMN dryrun DAG: 152 jobs. HIOMR dryrun DAG: 416 jobs. Dryrun resource strings still include `i384nvme` in the default partition list; live `squeue` must be checked for actual submissions.
- 2026-07-09T23:43:15Z - Live sessions active: `ccv_live_illumina_hg002_kitchensink_multiqc_20260709T232804Z` and `ccv_live_hybrid_ilmn_ont_snv_kitchensink_20260709T232804Z`. ILMN is running mounted-input staging/seqfu; HIOMR is removing the incomplete `somalier` env from the warmup race.
- 2026-07-09T23:44:00Z - Live Slurm submissions observed on `i128` and `i128nvme`; no `i384*` jobs in `squeue`. DYEC sbatch enforcement accepted cost center/budget `ifx-reworkB`.
- 2026-07-09T23:49:00Z - HIOMR jobs `2639` and `2640` are pending with `Reason=BeginTime`; their submit lines include `--partition=i128nvme,i192nvme,i384nvme,i192hugenvme`. No i384 node allocated yet, but DayOA tag `10.0.75` still permits i384 for these rules.
- 2026-07-09T23:52:00Z - HIOMR rule `relatedness_batch_somalier_extract` failed because the shared `somalier` conda env existed but lacked `bin/somalier`; extract log: `somalier: command not found`.
- 2026-07-09T23:55:00Z - Quarantined corrupt env as `/fsx/resources/environments/conda/ubuntu/ip-10-0-0-180/855b54c4a0d20318c3c6245cfe1ae09e_.corrupt_20260709T235447Z`, recreated from `workflow/envs/somalier.yaml`, and verified `somalier version: 0.2.19`.
- 2026-07-09T23:58:00Z - Live progress: ILMN 23/152, HIOMR 27/416. `10.0.75` still permits i384 in direct rule partition strings for several high-vCPU jobs; current allocations observed on `i128`/`i128nvme`, with pending 192-core job submitted as `i192nvme,i384nvme,i192hugenvme`.
- 2026-07-10T00:09:00Z - HIOMR burst submitted many jobs with `i384nvme` first in partition candidates. Attempted to update pending jobs to remove `i384nvme`; Slurm accepted some updates and returned `Resource temporarily unavailable` for others while scheduling.
- 2026-07-10T00:13:00Z - Job `2720` entered `CONFIGURING` on `i384nvme-dy-mem384nvme-4`. Acquired kill locks for the two live roots, cancelled matching live Slurm jobs, killed the two live tmux sessions, and released locks after `squeue` cleared. This run is invalid for result reporting.
- 2026-07-10T00:22:00Z - Patched DayOA to remove `i384nvme` from Slurm routing, reduced the 384-thread BWA-MEM2 rule to the 192-core NVMe family, validated focused DayOA tests, committed `280daae`, pushed `jem-dev`, and pushed annotated tag `10.0.76`.
- 2026-07-10T00:31:00Z - Updated DYEC command catalog, packaged catalog copy, `pyproject.toml`, and `config/**` DayOA pins from `10.0.75` to `10.0.76`; focused DYEC validation passed (`183` tests) and `git diff --check` passed. A clean rerun will use a new stamp and evidence root under `dayoa-10.0.76`.
- 2026-07-10T00:35:00Z - Local DYEC release commit `5183b0a7` and annotated tag `10.0.129` were created. Remote push and the clean rerun were blocked by the active Codex sandbox network restriction: `ssh: Could not resolve hostname github.com`.
