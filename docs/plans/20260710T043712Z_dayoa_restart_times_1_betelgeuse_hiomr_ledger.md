# DayOA `-T 1` Default And Betelgeuse HIOMR Execution Ledger

Date: 2026-07-10

## Objective

Set DayOA's global restart default and DYEC command-catalog rendering to one retry, release the complete dirty DayOA and DYEC worktrees, leave the three active HG003 5x DayOA 10.0.78 controllers undisturbed, and launch the HG002/HG003 Betelgeuse 24-hour HIOMR workflow from the new DayOA release.

Scope amendment at 2026-07-10T05:17Z: add Ganon2 through `produce_metagenomics` to every kitchen-sink catalog command, stage Ganon/Peddy/Somalier and all other supported native MultiQC inputs using the pinned MultiQC fork's parser contracts, retain custom-data summaries for non-native QC/information outputs, and fail report validation when an expected native or custom parser is absent.

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
| RELEASE-002 | DYEC | Pin DayOA `10.0.79`, commit all dirty changes, push/tag `10.0.134`, self-pin, then push/tag `10.0.135`. | SUCCESS | feature_implementation | Gate 5 | orchestrator | Release commit `4ee81bc8`, annotated tag `10.0.134`; self-pin commit `45eec1e0`, annotated tag `10.0.135`; branch and both tags pushed. |  | DYEC retry-default release train is published. |
| LIVE-001 | HG003 5x | Preserve and monitor the existing hybrid, ILMN, and ONT `10.0.78` controllers. | SUCCESS | active_product_contract | Gate 5 | orchestrator | Baseline correction at 2026-07-10T05:20Z: all three named tmux sessions exist as live Bash panes, but contain only `DAY-EC activated`; process inventory shows no `dy-r`/Snakemake controller and Slurm has no associated HG003 5x jobs. | The sessions were setup-only, not running controllers. | No duplicate or implicit high-cost launch was made. |
| LIVE-002 | Betelgeuse | Release the unused `10.0.78` lock/session without deleting its root. | SUCCESS | legitimate_safety_handling | Gate 5 | orchestrator | Both owned write locks were released and tmux session `ccv_live_betelgeuse_hg002_hg003_hiomr_24h_10_0_78_20260710T040250Z` was retired; no analysis root was deleted. |  | Old setup retired without deleting data. |
| LIVE-003 | Betelgeuse | Create a fresh `10.0.79` checkout, validate HG002/HG003 24-hour manifests, and launch full HIOMR with explicit `-T 1`. | SUCCESS | feature_implementation | Gate 5 | orchestrator | Root `/fsx/analysis_results/ifx-reworkB/ccv_live_betelgeuse_hg002_hg003_hiomr_24h_10_0_79_20260710T044825Z`; manifests contain only HG002/HG003, 144 ONT files per sample across Set4-FC1/2/3 and the validation ILMN run; bounded path probe found 0 missing files; dry run 642 steps rc=0; live controller command includes `-j 250 -p -k --rerun-triggers mtime -T 1`; Slurm jobs 3687-3690 running on i128nvme/i192nvme. |  | DayOA `10.0.79` controller launched with one retry. |
| MQC-001 | DayOA | Preserve Ganon classify stdout as a declared native MultiQC input and require native Ganon parsing. | SUCCESS | feature_implementation | Gate 5 | orchestrator | Pinned fork parser contract audited at commit `1955aa4`; Ganon classify stdout is a declared output, staged as native module `ganon`, and focused MultiQC invokes `-m ganon --require-logs`. |  | Native Ganon parsing is required, including the zero-unmapped sentinel. |
| MQC-002 | DayOA | Stage complete native inputs for Peddy, Somalier, Kraken, Ganon, Sourmash, and enforce expected native/custom raw-data sections. | SUCCESS | feature_implementation | Gate 5 | orchestrator | Peddy stages PED, background PCA, and CSVs; Somalier cohort files remain native; Kraken/Ganon/Sourmash use native modules; report validator fails on absent expected native/custom raw-data keys; DayOA full suite 484 passed. |  | Native and custom report contracts are fail-fast. |
| CATALOG-001 | DYEC | Add `produce_metagenomics` and `multiqc_qc.enable_tools=['vep','metagenomics']` to all four kitchen-sink rows in source/package catalogs. | SUCCESS | feature_implementation | Gate 5 | orchestrator | Illumina, Ultima, ONT, and hybrid kitchen-sink targets/commands include `produce_metagenomics`; source/package catalogs are identical; DYEC full suite 1323 passed, 11 skipped. |  | Every kitchen-sink row runs Kraken2, Ganon2, and sourmash. |
| MQC-RELEASE-001 | DayOA/DYEC | Publish follow-on releases that pin the Ganon/MultiQC contracts without changing active controllers. | SUCCESS | feature_implementation | Gate 5 | orchestrator | DayOA Ganon/MultiQC release `10.0.80` (`7192088`) and DYEC `10.0.136`/self-pin `10.0.137` were published. A final detected concurrent DayOA delta passed 486 tests and was published as immutable tag `10.0.81` (`40136d9`); the superseding DYEC catalog/pins target `10.0.81`, the full DYEC suite passed 1323 with 11 skipped, and annotated tags `10.0.138`/self-pin `10.0.139` were created without moving prior tags. |  | Superseding release train complete. |
| REPORT-001 | Final | Record controller/job status, tests, commits, tags, run roots, and residual risks. | SUCCESS | contract_test | Gate 5 | orchestrator | DayOA 484 passed; DYEC 1323 passed/11 skipped; Betelgeuse controller process present with jobs 3689-3694 on i128nvme/i192nvme and no i384; release commits/tags and setup-only HG003 session boundary recorded above. |  | Release objective complete; Betelgeuse workflow remains live. |

## Terminal Summary

- DayOA retry default and catalog rendering use one retry while `keep-going: False` remains unchanged.
- DayOA `10.0.79`, DYEC `10.0.134`, and DYEC self-pin tag `10.0.135` delivered the requested retry-default release train.
- DayOA `10.0.81` supersedes `10.0.80` with the final detected concurrent input/sex-complement fixes; superseding DYEC tags `10.0.138`/`10.0.139` pin this DayOA release. The earlier immutable DYEC `10.0.136`/`10.0.137` tags remain published and unmoved.
- The Betelgeuse HG002/HG003 24-hour HIOMR controller is live from DayOA `10.0.79` with explicit `-T 1`; latest jobs use i128nvme/i192nvme and no i384 partition.
- The three named HG003 5x `10.0.78` sessions were setup-only, not running controllers. They were left untouched and no duplicate/high-cost launch was made.
