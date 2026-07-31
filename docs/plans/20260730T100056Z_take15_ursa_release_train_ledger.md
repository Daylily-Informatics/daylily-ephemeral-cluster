# Take15 DYEC DayOA-pin and Ursa integration release ledger

**Created:** 2026-07-30T10:00:56Z
**Controlling request:** After DayOA is released, update DYEC's explicit DayOA
pin, commit that work on a fresh feature branch, fold in the DYEC
`ursa-changes` work, publish a release, then advance the source and packaged
DYEC self-pins and publish the final release.

## Gate 0 inventory

- DYEC feature branch: `codex/take15-hiomr2-ursa-release` in
  `/Users/jmajor/.codex/worktrees/dyec-take15-hiomr2-ursa-release`.
- Its clean baseline is `16.1.4`,
  `c55620fc7391c73e53f09801dbfb25b9d1e60383`.
- The source checkout at
  `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` is deliberately
  dirty.  Only its three tracked, in-scope HIOMR2 catalog/test changes will be
  reproduced here: source catalog, packaged catalog, and
  `tests/test_repository_catalog.py`.  Its historical/untracked artifacts
  are excluded.
- DYEC `ursa-changes` is the clean, already published `16.1.7` commit
  `1d7407bbfc1cc058407639798333e5ee3e6a0921`, descendant of `16.1.4`.
- Because `16.1.7` is already immutable and published, the integrated
  release target is `16.1.8`; the final self-pin release target is
  `16.1.9`.  Both tags were absent from `origin` before work began.
- Active source and packaged catalogs currently use `13.0.85`; historical
  validation receipts are evidence and will not be rewritten.

## Control ledger

| ID | Area | Requirement | Status | Category | Gate | Evidence / terminal note |
|---|---|---|---|---|---|---|
| DYEC-001 | Baseline | Freeze clean feature worktree, the exact three in-scope source edits, and the published Ursa branch. | SUCCESS | plan_amendment | Gate 0 | Baseline/ancestry and excluded dirty artifacts are recorded above. |
| DYEC-002 | DayOA pin | Set active source and packaged DayOA catalog pins and their tests to published `13.0.90`. | SUCCESS | config_or_startup_contract | Gate 2 | All active catalog pins are `13.0.90`; contract test now records DayOA commit `35b43ce46a52ef9d86d8653edfb87909f4e75764`. Historical `13.0.61` validation evidence is unchanged. |
| DYEC-003 | HIOMR2 catalog | Carry the in-scope native TIDDIT and paired-library-summary catalog/test changes from the dirty source checkout. | SUCCESS | feature_implementation | Gate 1 | Source/package catalogs are byte-identical; the focused suite passed 266 tests on the feature worktree. |
| DYEC-004 | Ursa integration | Fold `ursa-changes` into the feature branch and resolve any catalog/test overlap without dropping either change. | SUCCESS | feature_implementation | Gate 1 | Merged `1d7407bbfc1cc058407639798333e5ee3e6a0921`; the sole test overlap retains `DAYOA_BLESSED_TAG` and the Ursa `run_context_only=true` runtime contract. Source/package catalogs remain byte-identical and the focused suite passed 266 tests. |
| DYEC-005 | First release | Validate, commit/push the integrated branch, create/verify/push annotated `16.1.8`. | SUCCESS | release | Gate 6 | Annotated tag object `96d833482b424bdc37764a82933c1625b79bfe87` is pushed and peels to integration commit `cd2de834dff02aeff290d3fedb15018b27a58271`. |
| DYEC-006 | Self pin | Advance source and packaged DYEC self-pins to `16.1.9` and update affected tests. | SUCCESS | config_or_startup_contract | Gate 2 | Source/package global configs are byte-identical, contain no active `16.1.3` pin, and the focused suite passed 266 tests. |
| DYEC-007 | Final release | Revalidate, commit/push, create/verify/push annotated `16.1.9`. | IN PROGRESS | release | Gate 6 | Final tag will point at the clean self-pin commit. |

## Intended scope boundary

No main-branch merge, PR creation, package-index publish, budget change,
headnode reconfiguration, scheduler action, or live workflow submission is part
of this release request.
