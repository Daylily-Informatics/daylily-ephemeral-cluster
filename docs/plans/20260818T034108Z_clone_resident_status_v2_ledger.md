# Clone-resident execution status v2 control ledger

Controlling plan: clone-resident execution status v2

Linked DayOA ledger: `/Users/jmajor/projects/lsmc/.codex-worktrees/clone-resident-status-v2-dayoa/docs/plans/20260818T034108Z_clone_resident_status_v2_release_ledger.md`

## Gate 0: inventory freeze

- DYEC implementation worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/clone-resident-status-v2-dyec`
  - Branch: `codex/clone-resident-status-v2`
  - Baseline: annotated tag `18.0.28`, commit `8a7c5348273758c2f8e2cd8dcb9ab94ad1cdc597`
  - Initial worktree state: clean.
- DayOA implementation worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/clone-resident-status-v2-dayoa`
  - Branch: `codex/clone-resident-status-v2`
  - Baseline: annotated tag `15.0.18`, commit `ed76a54c40d3fba695728a39295b1a813d659eca`
  - Initial worktree state: clean.
- Preserved user-owned checkout: `/Users/jmajor/projects/lsmc/daylily-omics-analysis` has modified versioned files in `tests/test_hiomr2_core_rules.py`, `tests/test_multiqc_qc_targets.py`, `workflow/rules/sent_hybrid_ilmn_ont_modular2.smk`, and `workflow/rules/tiddit.smk`, plus user-owned `tmp/` content. This worktree is not part of this implementation.
- Existing DYEC writer: `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` writes `$DAYLILY_RUN_DIR/status.json`, conventionally under `/home/ubuntu/daylily-runs/<session>/status.json`.
- Existing DayOA `bin/day_run` captures the underlying Snakemake result in `workflow_ret_code` but persists no JSON execution record in the clone.
- Existing DYEC consumers include workflow observability, workflow CLI status/logs, analysis status, and the SSM E2E runner. They currently read the home-run receipt.
- Contract decisions: canonical file is `<analysis-root>/daylily-omics-analysis/status.json`; retain all controller attempts; support only v2; do not migrate, read, or silently fall back to historic home-run receipts.
- No tests or live workflow operations have run at Gate 0. No raw Snakemake invocation is permitted. Live controller/DRA export proof needs separate authorization.

## Tracking rows

| ID | Area | Requirement | Status | Category | Gate | Evidence / terminal note |
| --- | --- | --- | --- | --- | --- | --- |
| STV2-001 | Contract | Define and document strict `daylily.analysis_status.v2` with append-only attempts and three independent return-code records. | SUCCESS | feature_implementation | 1 | DayOA writer and DYEC reader enforce exact schema keys, UUID/sequence/order, immutable root/clone identity, and distinct `controller`, `day_run`, and `snakemake` results. |
| STV2-002 | DayOA | Add a standard-library status writer and wire `bin/day_run` to record exact day-run and composed-Snakemake results. | SUCCESS | feature_implementation | 1 | DayOA `bin/util/analysis_status.py` uses `flock` and atomic replacement; `bin/day_run` starts direct attempts only after `$DAY_ROOT` validation and records the wrapped command around execution plus final wrapper rc in its exit trap. |
| STV2-003 | DYEC launch | Create/finalize a DYEC controller attempt, pass its ID/path to DayOA, and permit only intended runtime artifacts in pinned-source checks. | SUCCESS | feature_implementation | 1 | `controller_target.json` v2 names a fresh UUID; the controller creates/finishes the attempt around its post-run integrity/DAG checks, and the pinned-source matcher permits only root `status.json` plus `.dyec/status.json.lock`/temporary artifacts. |
| STV2-004 | DYEC readers | Move workflow status/logs, observability, analysis status, and SSM runner reads to the clone-root v2 status. | SUCCESS | feature_implementation | 1 | Workflow observability, CLI logs/status, analysis status, and SSM E2E parsing resolve the clone from `controller_target.json`, select its exact attempt, and expose separately named exit codes. Home-run receipt paths are rejected. |
| STV2-005 | Tests | Add focused DayOA and DYEC contract tests for append history, divergent return codes, malformed/missing data, and no legacy fallback. | SUCCESS | contract_test | 5 | DayOA: `bash -n bin/day_run && python -m pytest tests/test_execution_status_v2.py -q` passed 7. DYEC focused suite passed 403, including status, export, controller, observability, analysis-status, SSM, runner, and registry coverage. No workflow or DRA command ran. |
| STV2-006 | Documentation | Publish schema/location/CLI semantics and export-evidence expectations. | SUCCESS | feature_implementation | 5 | `docs/execution_status_v2.md` (DayOA) and `docs/clone_resident_execution_status_v2.md` (DYEC) document the schema/location/no-legacy contract; export accepts optional post-SUCCEEDED clone-status evidence without changing historic exports. |
| STV2-007 | Releases | Cut DayOA `15.0.19`, pin all current catalog commands, then cut DYEC `18.0.29` with annotated tags. | IN_PROGRESS | feature_implementation | 5 | DayOA annotated tag `15.0.19` is pushed and peels to `7c3377fd543f6c987736f81792159452646510d4`. Source/payload catalog parity holds; all 30 top-level and 30 `dyec_builds.current` tags are `15.0.19`. DYEC commit/tag/push pending. |
| STV2-008 | Live acceptance | Prove a clone export contains retained v2 status using an authorized controller and no-delete DRA export. | BLOCKED | active_product_contract | 5 | Explicit live controller/export authorization is not yet present in this implementation request. |

## Amendment log

| ID | Change | Evidence | Status |
| --- | --- | --- | --- |
| AMD-001 | Use clean tagged worktrees rather than the dirty DayOA checkout. | Gate 0 source inventory. | SUCCESS |
| AMD-002 | Retain the pre-existing Bjuice catalog-metadata drift outside this status-v2 release. | Exploratory catalog checks still reference the retired `bjuice-v2-hg002-multi-analysis-unit-hiomr2-kitchensink-mega-inflection-analytical` ID and assume an older one-entry validation history; current catalog has `inflection-bjuice-product-v0.9` and an additional retained validation receipt. The focused v2 suite is green; this release does not rewrite unrelated Bjuice provenance. | SUCCESS |

## Completion criteria

The source objective requires STV2-001 through STV2-007 to be `SUCCESS`. The operational objective remains incomplete until STV2-008 receives explicit authorization and is independently proven.
