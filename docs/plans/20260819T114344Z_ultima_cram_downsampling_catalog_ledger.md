# Ultima CRAM Downsampling Catalog Execution Ledger

Created: 2026-08-19T11:43:44Z

Controlling plan and ledger: `docs/plans/20260819T114344Z_ultima_cram_downsampling_catalog_ledger.md`

Companion DayOA ledger: `/Users/jmajor/.codex-worktrees/dayoa-downsample-ultima-cram-in-config/docs/plans/20260819T114344Z_ultima_cram_downsampling_ledger.md`

## Objective

Publish a scoped DYEC catalog build that pins only `ultima_snv_alignstats_kitchensink` and `ultima_sentieon_pangenome_kitchensink` to the new DayOA release implementing per-analysis-unit Ultima input-CRAM downsampling. Preserve all other current commands at their prior pin, historical snapshots, command targets/arguments, provider-neutral manifests, and dry-only evidence truth.

## Gate 0: Inventory Freeze

- Repository: `/Users/jmajor/.codex-worktrees/dyec-downsample-ultima-cram-in-config`
- Branch: `codex/downsample_ultima_cram_in_config`
- Base: annotated tag `18.0.58`, peeled commit `7115851c9b19bdf3749cad5f5a2b5ac9d00ba4a2`
- Proposed release: annotated tag `18.0.59`; local and remote tag were absent at Gate 0.
- Existing user checkout preserved: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` has unrelated untracked work; no implementation will occur there.
- Baseline status: clean feature worktree.
- Catalog inventory: `current` contains 31 commands pinned to DayOA `15.0.37`; canonical and packaged catalogs compare byte-identical.
- Sweep: the solo command appears across 7 catalog/test files and the pangenome command across 10; historical numeric snapshots are immutable.
- Baseline focused catalog tests: `python -m pytest tests/test_repository_catalog.py tests/test_release_18_0_56_rc0_catalog_consolidation.py -q --tb=short` -> 8 failed, 17 passed. Failures are stale expectations at the exact `18.0.58` base: command count 33 vs 31, DayOA `15.0.28` vs `15.0.37`, two removed current BJuice commands, and an invalid assertion that frozen `18.0.56` equals mutable `current`.
- Execution boundary: only supported catalog render/dry launch is authorized. Require attributable controller rc=0 and zero Slurm submissions; do not continue live, manage jobs, alter Slurm, or mutate cluster infrastructure.
- Current dry input evidence exists in the preserved user checkout, but its provenance and cluster state must be re-verified before reuse; no unfamiliar staging data may be inferred.

## Control Ledger

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DYE-000 | DYEC | Freeze source, branch, dirty-checkout boundary, catalog parity, and baseline failures | SUCCESS | feature_implementation | Gate 0 | root | Exact tag/commit, clean worktree, catalog inventory, and 8-failure baseline recorded above |  | Gate 0 complete before catalog edits |
| DYE-001 | Test baseline | Repair stale catalog expectations against frozen/current source truth without changing production behavior | SUCCESS | contract_test | Gate 1 | root | Test-only commit `20325e84`; original focused baseline 25 passed; broader sweep exposed and corrected 10 additional stale tests; standalone amended-commit checks passed | Initial Gate 0 counted only the two focused files, while the complete catalog suite contained additional stale current/alias/release assumptions | Repairs record 31 current commands, DayOA 15.0.37, current evidence counts, frozen 18.0.50 BJuice selection, and immutable numeric releases |
| DYE-002 | Catalog | Add build `18.0.59`; permit DayOA `15.0.37` and `15.0.38`, pin only the two Ultima commands to `15.0.38`, keep default at `15.0.37` | SUCCESS | active_product_contract | Gate 2 | root | Parsed candidate: 31 commands; 29 at 15.0.37 and exactly the two Ultima commands at 15.0.38; `current == 18.0.59`; default_ref 15.0.37 |  | Candidate contract complete |
| DYE-003 | Catalog invariants | Preserve the two command target/argv/input contracts, freeze `18.0.58`, and keep canonical/package catalogs identical | SUCCESS | contract_test | Gate 5 | root | Dedicated release tests prove exact target/argv/input parity, all historical snapshots match tagged 18.0.58 source, and canonical/package bytes match |  | Invariants complete before remote validation |
| DYE-004 | Local verification | Pass focused catalog tests and the full DYEC suite | SUCCESS | contract_test | Gate 5 | root | Complete catalog suite: 65 passed. Full suite: 2647 passed, 11 skipped, 35 failed in 1112.46s; exact 35-node replay on production-identical test-only commit `20325e84` reproduced all 35 failures | Pre-existing activation/CLI/docs/removed-alias/headnode-mock debt at 18.0.58 | Zero feature regressions; no unrelated production repair attempted |
| DYE-005 | Solo dry proof | Exact-tag catalog render and dry launch with `ULTIMA_SUBSAMPLE_PCT=0.75`; rc=0, zero Slurm, one seed-33 threaded CRAM sampling rule | SUCCESS | contract_test | Gate 5 | root | Analysis `pclu18045_u075_solo_18059_15038_20260819t130742z`: DayOA `15.0.38`/`95cabdbf`; attributed controller/day-run/Snakemake rc=0; submitted jobs 0; controller log contains one `pre_prep_ultima_cram`, one `-s 33.75`, `samtools view -@ 48`, and `samtools index -@ 48`; see `docs/plans/20260819T114344Z_ultima_cram_downsampling_catalog_artifacts/solo_dry_evidence.json` |  | Dry-only capsule succeeded; no CRAM records were processed |
| DYE-006 | Pangenome dry proof | Exact-tag catalog render and dry launch with the same fraction; rc=0, zero Slurm, canonicalizer consumes the prepared CRAM | SUCCESS | contract_test | Gate 5 | root | Analysis `pclu18045_u075_pang_18059_15038_20260819t130742z`: DayOA `15.0.38`/`95cabdbf`; attributed controller/day-run/Snakemake rc=0; submitted jobs 0; exactly one seeded prep; `canonicalize_pangenome_ug_input_cram` consumes the prepared ug CRAM and `sentieon_pangenome_ug` consumes its canonical output; see `docs/plans/20260819T114344Z_ultima_cram_downsampling_catalog_artifacts/pangenome_dry_evidence.json` |  | Dry-only capsule succeeded; no CRAM records were processed |
| DYE-007 | Evidence truth | Record new runs as dry-only; do not relabel prior live evidence or claim runtime/read-count proof | OPEN | legitimate_safety_handling | Gate 5 | root | Pending |  |  |
| DYE-008 | Release | Commit, push feature branch, create/push annotated `18.0.59`, and verify tag type/commit | OPEN | feature_implementation | Gate 5 | root | Pending |  |  |
| DYE-009 | Final report | Terminalize every row and record changed files, validation, non-actions, and residual risk | OPEN | plan_amendment | Gate 5 | root | Pending |  |  |

## Final Report

All rows terminal: no

Objective complete: no

Status counts: SUCCESS 7; OPEN 3; other terminal states 0.
