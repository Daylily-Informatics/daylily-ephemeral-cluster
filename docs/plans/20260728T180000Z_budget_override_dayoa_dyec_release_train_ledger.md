# Budget override and DayOA/DYEC release-train execution ledger

## Objective

Add explicit, opt-in sbatch pass-through behavior for stale budget data and
exceeded cluster/cost-center budgets; publish the versioned sbatch asset to
both active regional runtime-asset locations; then release the proven Take8
DayOA changes and advance DYEC's DayOA and self pins.

## Gate 0 baseline

- DYEC checkout: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch
  `codex/hiomr2-catalog-repair`, with pre-existing untracked historical plans,
  backups, recordings, reports, and a modified Take8 release ledger.
- DayOA checkout: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`, branch
  `codex/hiomr2-full-kitchensink-repair`, with pre-existing edits to the Take8
  ledger, Jasmine rule, and Jasmine test.
- Current DYEC global pin is `15.0.17`; the active command catalog source and
  packaged copies must be inventoried before changing the DayOA pin.
- Current sbatch wrapper hard-fails a cluster budget at 100% (line 204) and
  hard-fails the cost-center stale/exceeded outcomes (Python exits 24/25).
- Scope excludes cost-center identity/authorization checks and all charge
  attribution; overrides may only downgrade the specified terminal conditions
  to warnings.

## Work ledger

| ID | Scope | State | Evidence / exit condition |
|---|---|---|---|
| BUD-001 | Add explicit environment parsing and warning-only stale-budget behavior. | COMPLETE | `DAY_PASS_ON_STALE_BUDGET` is fail-closed for absent/`0`/`false` and warning-only for present empty or other values; focused wrapper proof passed. |
| BUD-002 | Add explicit warning-only cluster and cost-center exceeded-budget behavior. | COMPLETE | `DAY_PASS_ON_BUDGET_EXCEEDED` has the same false-token contract for both budget checks; submitted jobs still carry the selected cost center. |
| BUD-003 | Expose explicit DYEC CLI request flags and export them before `dy-a`. | COMPLETE | `workflow launch` and `samples run` accept the two explicit flags; the rendered headnode launcher exports them before activation and `dy-r`. |
| BUD-004 | Update source and packaged sbatch assets; focused wrapper and launcher tests. | COMPLETE | Source and packaged sbatch/catalog assets are byte-identical. Focused wrapper, catalog, CLI, packaged-default, and launcher suites: 330 passed. |
| BUD-005 | Publish immutable sbatch boot-asset releases to exact US West and US East runtime buckets. | PENDING | S3 readback SHA-256 matches local source in each region. |
| DAY-001 | Inventory and commit only the DayOA changes used to make Take8 run. | COMPLETE | Local and headnode source fixes were consolidated on `codex/hiomr2-full-kitchensink-repair`; focused HIOMR2 contract/package/Jasmine suite: 43 passed. |
| DAY-002 | Tag and push the clean DayOA release commit. | COMPLETE | Annotated `13.0.71` is pushed and peels to `6ed7d18f3076b063251998a602be3faa560422f8`. |
| DYEC-001 | Advance all active DayOA pins to the released DayOA tag. | COMPLETE | All active source and packaged command-catalog DayOA pins now use `13.0.71`; annotated `15.0.21` is pushed and peels to `d79d5f94dbc206e57a245f935c4407b848d445d7`. |
| DYEC-002 | Commit, push, tag first DYEC release; then self-pin and release the follow-up DYEC tag. | COMPLETE | Source and packaged DYEC bootstrap pins now reference immutable `15.0.21`; this self-pin follow-up is released as annotated `15.0.22`. |

## Override contract

`DAY_PASS_ON_STALE_BUDGET` and `DAY_PASS_ON_BUDGET_EXCEEDED` are false only
when absent or exactly `0`/`false` (case-insensitive after surrounding
whitespace is stripped). Presence with an empty value is an explicit opt-in,
as is every other value. The wrapper emits a `WARNING:` with the relevant
budget details and continues only for its matching condition.
