# Forked Catalog J100 Jitter Validation Ledger

Created: 2026-06-04T02:03:27Z

## Objective

Run every command in `config/daylily_pipeline_command_catalog.yaml` on cluster `forked` with AWS profile `lsmc` and region `us-west-2`, after adding DayOA `dy-r --sentieon-start-jitter`. Use mounted slim data where available, create missing run-directory mounts with an explicit long wait, force `-j 100 -p -k`, and promote both repositories from `jem-dev` to `prod` only after all catalog rows pass and the protected branch review contract is satisfied.

## Gate 0 Baseline

- Controlling ledger path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260604T020327Z_forked_catalog_j100_jitter_validation/ledger.md`
- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DayOA baseline branch/status: `jem-dev...origin/jem-dev`, clean
- DYEC baseline branch/status: `jem-dev...origin/jem-dev`, clean before this ledger directory was created
- DayOA baseline commit: `29211abf9eec106b5caeb439425e3b84730b4f5e`
- DYEC baseline commit: `428e998abc3cf7a01e9c970e5aededbbae556a86`
- Target cluster/profile/region: `forked` / `lsmc` / `us-west-2`
- Active DayOA Sentieon includes recorded by `rg -n "include: .*sent|sentieon|sent_DNA|sent_snv|sent_hybrid|sentmm2" workflow/Snakefile workflow/rules/global_common.smk`: `workflow/Snakefile` lines 316-334 include the active Sentieon/Sentieon-adjacent rule files.
- Safety boundary: no raw DayOA Snakemake workflow execution; live workflow execution must go through initialized `dy-r`. Monitoring only for Slurm and jobs unless a separate explicit approval is given.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Baseline | Record repo state, commits, active Sentieon rule surface, cluster target, and safety boundary before implementation. | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 baseline above. |  | Baseline recorded before DayOA source edits. |
| DAYOA-001 | DayOA | Add `dy-r --sentieon-start-jitter` parsing in `bin/day_run`; strip the flag before Snakemake and export `DAYOA_SENTIEON_START_JITTER_MAX_SECONDS=max(1, floor(jobs/50))`. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `bin/day_run` parses `--sentieon-start-jitter`, strips it from `_dy_forward_args`, requires explicit `-j/--jobs/--cores`, and exports `DAYOA_SENTIEON_START_JITTER_MAX_SECONDS`. |  | Flag implementation complete. |
| DAYOA-002 | DayOA | Add a Sentieon jitter helper and route all active Sentieon executable invocations through it, including absolute `/fsx/.../sentieon` paths. | SUCCESS | feature_implementation | Gate 1 | orchestrator | Added `bin/day_sentieon_jitter.bash`, `bin/dayoa_sentieon`, and `bin/dayoa_sentieon_cli`; active Sentieon rule executable calls are routed through `bin/dayoa_sentieon` or `bin/dayoa_sentieon_cli`. |  | Active Sentieon executable calls are wrapped. |
| DAYOA-003 | DayOA | Add focused tests for flag stripping, job parsing, env export, helper bash syntax, and active-rule wrapper coverage. | SUCCESS | contract_test | Gate 1 | orchestrator | Updated `tests/test_shell_wrapper_contracts.py`, `tests/test_snakemake_parser_contracts.py`, and `tests/test_ont_fastq_contracts.py`. |  | Tests added. |
| DAYOA-004 | DayOA | Run focused DayOA validation before committing. | SUCCESS | contract_test | Gate 1 | orchestrator | `python -m pytest -q tests/test_shell_wrapper_contracts.py tests/test_snakemake_parser_contracts.py tests/test_ont_fastq_contracts.py tests/test_complete_genomics_sentieon.py` -> 32 passed; `python -m pytest -q tests/test_workflow_target_aliases.py tests/test_workflow_catalog.py` -> 16 passed. |  | Focused DayOA validation passed. |
| DYEC-001 | DYEC | Add a durable forked catalog driver/report surface that pins DayOA launches to the new exact commit and forces `-j 100 -p -k --sentieon-start-jitter`. | SUCCESS | feature_implementation | Gate 2 | orchestrator | Added `docs/plans/20260604T020327Z_forked_catalog_j100_jitter_validation/driver.py`; driver requires `--dayoa-git-ref`, targets `forked`, forces J100/print/keep/jitter, uses `5400` second run-mount waits, and batches catalog commands 2-3 at a time. |  | Forked driver added. |
| DYEC-002 | DYEC | Add focused DYEC tests for forced jobs/flags, git ref pinning, jitter flag injection, config-only slim data, and run-mount timeout handling. | SUCCESS | contract_test | Gate 2 | orchestrator | Added `tests/test_forked_catalog_jitter_driver.py`; current focused driver coverage passes as part of `python -m pytest -q tests/test_day_clone.py tests/test_forked_catalog_jitter_driver.py` -> 22 passed. Broader probe `tests/test_repository_catalog.py tests/test_cli_registry_v2.py tests/test_script_entrypoints.py` has 4 failures from current-source/test drift: catalog expects `2.0.44` while checked-in source/payload catalog use `5.0.1`, and BCL script test expects `shared_thread_odirect_output=auto` while source sets `false`. |  | Focused forked driver validation passed; unrelated broad-suite drift recorded. |
| DYEC-003 | DYEC | Make `day-clone --git-tag <40-hex-sha>` clone and detach-checkout the exact commit instead of treating the SHA as a remote branch. | SUCCESS | feature_implementation | Gate 2 | orchestrator | Patched `bin/headnode_utils/day-clone` and `daylily_ec/resources/payload/bin/headnode_utils/day-clone`; added `test_day_clone_full_sha_clones_then_detaches`; `python -m pytest -q tests/test_day_clone.py tests/test_forked_catalog_jitter_driver.py` -> 22 passed. |  | SHA-pinned workflow launches can clone the pushed DayOA commit. |
| LIVE-001 | Live catalog | Record live Gate 0 inventory for `forked`: AWS identity, cluster state, headnode access, Slurm queue, `/fsx/references`, slim roots, and current run mounts. | OPEN | contract_test | Gate 3 | orchestrator |  |  |  |
| LIVE-002 | Live catalog | Run all 14 slim sample-analysis catalog commands in batches of 2-3 live workflows using mounted slim data and generated config-only sample tables. | OPEN | contract_test | Gate 4 | orchestrator |  |  |  |
| LIVE-003 | Live catalog | Create any missing run-directory mounts with `--wait --timeout-seconds 5400`, verify mounted paths, then run the 5 run-analysis catalog commands in batches of 2-3 workflows. | OPEN | contract_test | Gate 4 | orchestrator |  |  |  |
| LIVE-004 | Live catalog | Run the utility catalog command and produce a final matrix with dry-run/live IDs, exports, source roots, mount IDs, commits, and jitter evidence. | OPEN | contract_test | Gate 4 | orchestrator |  |  |  |
| PROD-001 | Promotion | Commit and push DayOA `jem-dev` after local validation and use that exact SHA for catalog launches. | SUCCESS | feature_implementation | Gate 5 | orchestrator | DayOA commit `9f442ed1f32ecb19cf0163c41d196974f8198364` pushed to `origin/jem-dev`. This SHA is the `--dayoa-git-ref` for forked catalog launches. |  | DayOA SHA is available on GitHub for live workflow clones. |
| PROD-002 | Promotion | Commit and push DYEC `jem-dev` with ledger/driver/report evidence after local validation. | OPEN | feature_implementation | Gate 5 | orchestrator |  |  |  |
| PROD-003 | Promotion | Open PRs from `jem-dev` to `prod` for both repos; complete prod blessing only after 2 reviewer approvals per protected branch rule and merge. | OPEN | active_product_contract | Gate 6 | orchestrator |  |  |  |

## Status Notes

- 2026-06-04T02:03:27Z: Created ledger and Gate 0 baseline from clean `jem-dev` checkouts.
- 2026-06-04T02:16Z: Implemented DayOA jitter flag/wrappers and passed focused DayOA validation.
- 2026-06-04T02:27Z: Added forked catalog driver and focused DYEC tests. Focused driver test passed; broader existing DYEC tests exposed unrelated current-source/test drift.
- 2026-06-04T02:31Z: Committed and pushed DayOA `jem-dev` at `9f442ed1f32ecb19cf0163c41d196974f8198364`.
- 2026-06-04T02:19Z: First full-driver attempt exposed that the `simple-test` source-initialized catalog command still rendered `dy-a local hg38`; the local driver was stopped without Slurm/job cancellation. Patched the renderer so source-initialized commands are rewritten to `dy-a slurm <genome>` and moved new launches to analysis ID prefix `ccvforked_j100_jitter_r2`.
- 2026-06-04T02:24Z: R2 dry-run launches failed before Snakemake because `day-clone` passed `--branch 9f442ed1f32ecb19cf0163c41d196974f8198364`, producing `fatal: Remote branch ... not found in upstream origin`. Stopped only the local driver/launcher process tree; no Slurm/node/job intervention was performed.
- 2026-06-04T02:29Z: Patched `day-clone` full-SHA handling and isolated the driver to current-prefix dry-run/live events. New launches use analysis ID prefix `ccvforked_j100_jitter_r3`.
- 2026-06-04T02:33Z: Wrote the patched `day-clone` helper to headnode `i-01fdf39c363930bff` at `~/.local/bin/day-clone`, set mode `0755`, verified `FULL_COMMIT_SHA_RE` is present, and verified `day-clone --list` succeeds.
