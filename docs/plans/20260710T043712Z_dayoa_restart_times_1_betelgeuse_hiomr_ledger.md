# DayOA `-T 1` Default And Betelgeuse HIOMR Execution Ledger

Date: 2026-07-10

## Objective

Set DayOA's global restart default and DYEC command-catalog rendering to one retry, release the complete dirty DayOA and DYEC worktrees, leave the three active HG003 5x DayOA 10.0.78 controllers undisturbed, and launch the HG002/HG003 Betelgeuse 24-hour HIOMR workflow from the new DayOA release.

## Gate 0 Baseline

- Controlling ledger: `docs/plans/20260710T043712Z_dayoa_restart_times_1_betelgeuse_hiomr_ledger.md`
- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`, branch `jem-dev`, HEAD/tag `3503e72` / `10.0.78`, `origin/jem-dev` has no divergence.
- DayOA pre-existing dirty files: `tests/test_dragen_native_workflow.py`, `workflow/rules/dragen_all_callers.smk`, `workflow/rules/sent_aln_sort_snv.smk`.
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch `jem-dev`, HEAD/tag `e20a0757` / `10.0.133`, `origin/jem-dev` has no divergence.
- DYEC pre-existing dirty work includes the AlmaLinux/ParallelCluster backport files, public-contribution audit files, live command-catalog evidence, and generated HG003/Betelgeuse manifests listed by `git status --short` at 2026-07-10T04:37Z.
- DayOA sweep: four `restart-times: 0` entries across Slurm, Slurm RHEL, and local profile templates.
- DYEC sweep: command rendering appends `-T 0`; four catalog command pairs explicitly use `-T 0`; focused tests assert the old value.
- Live boundary: HG003 5x hybrid, ILMN, and ONT controllers already run DayOA `10.0.78`; they must not be restarted.
- Betelgeuse boundary: HG002/HG003 only, one ILMN validation run, Set4-FC1/FC2/FC3 ONT data limited to 0-24 hours; SMN12-positive controls excluded.

## Control Ledger

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| RETRY-001 | DayOA | Set all active profile defaults to `restart-times: 1` while preserving `keep-going: False`. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Slurm, Slurm RHEL, and local templates now parse as `restart-times: 1`; Slurm profiles retain `keep-going: False`. |  | DayOA retry default is one. |
| RETRY-002 | DYEC | Normalize command-catalog execution to `-T 1` and update source/package catalogs. | SUCCESS | feature_implementation | Gate 2 | orchestrator | `render_dy_command` appends `-T 1`; explicit catalog `-T 0` rows changed to `-T 1`; source/package catalog `cmp` returned 0. |  | DYEC catalog rendering and persisted commands use one retry. |
| TEST-001 | DayOA/DYEC | Add or update tests for profile defaults, rendering, and catalog parity. | SUCCESS | contract_test | Gate 5 | orchestrator | DayOA focused tests: 23 passed. DYEC focused tests: 218 passed. |  | Retry, pin, catalog, DRAGEN backport, and dirty-worktree contracts pass. |
| RELEASE-001 | DayOA | Commit all dirty changes, push `jem-dev`, and publish annotated tag `10.0.79`. | SUCCESS | feature_implementation | Gate 5 | orchestrator | Commit `7b3b80a`; annotated tag type verified as `tag`; branch and tag pushed to origin. |  | DayOA `10.0.79` is published. |
| RELEASE-002 | DYEC | Pin DayOA `10.0.79`, commit all dirty changes, push/tag `10.0.134`, self-pin, then push/tag `10.0.135`. | IN_PROGRESS | feature_implementation | Gate 5 | orchestrator | DayOA pin updated across pyproject, catalogs, overrides, and tests. |  |  |
| LIVE-001 | HG003 5x | Preserve and monitor the existing hybrid, ILMN, and ONT `10.0.78` controllers. | OPEN | active_product_contract | Gate 5 | orchestrator | Existing tmux sessions and Slurm jobs observed. |  |  |
| LIVE-002 | Betelgeuse | Release the unused `10.0.78` lock/session without deleting its root. | OPEN | legitimate_safety_handling | Gate 5 | orchestrator | No `dy-r` controller was started in that session. |  |  |
| LIVE-003 | Betelgeuse | Create a fresh `10.0.79` checkout, validate HG002/HG003 24-hour manifests, and launch full HIOMR with explicit `-T 1`. | OPEN | feature_implementation | Gate 5 | orchestrator | Required mounts are already AVAILABLE. |  |  |
| REPORT-001 | Final | Record controller/job status, tests, commits, tags, run roots, and residual risks. | OPEN | contract_test | Gate 5 | orchestrator | Final evidence pending. |  |  |

## Terminal Summary

Pending execution.
