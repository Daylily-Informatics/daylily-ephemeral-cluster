# DYEC 18.0.56 / DayOA 15.0.37 RC0 Catalog Consolidation Release Ledger

Controlling request: publish a forward-only DYEC release from the maximum
released DYEC version, pin every mutable current DayOA catalog surface to the
new maximum DayOA release, freeze the new numeric snapshot, and preserve the
eleven fresh production controller `rc=0` outcomes.

## Gate 0 baseline

- Baseline: annotated remote DYEC tag `18.0.55` at
  `1358b349edb6f7a6fc88d2ff87c8ce79197ed89c`.
- DayOA `15.0.37` is an annotated, pushed forward-only tag based on maximum
  `15.0.36`; `15.0.35` (the RC0 canonical-SAM repair) is in its ancestry.
- `18.0.55` currently pins DayOA `15.0.35`; no historical numeric snapshot
  may be rewritten.
- Proposed tag `18.0.56` and temporary/release branch names were verified
  unused before this worktree was created.
- The controlling remediation ledger records fresh live `rc=0` for all eleven
  production catalog commands. No export, delete, workflow, cluster, or Slurm
  action is in scope for this release.

## Control ledger

| ID | Area | Requirement | Status | Category | Gate | Evidence / terminal note |
|---|---|---|---|---|---|---|
| G0 | Release baseline | Freeze the maximum DYEC/DayOA tags and preserve historical catalog snapshots. | SUCCESS | legitimate_safety_handling | Gate 0 | `18.0.55` is the immutable baseline; the new release starts from it. |
| CAT-01 | Current catalog | Retarget repository default, every current command, and current allowed tag set to only DayOA `15.0.37`. | SUCCESS | config_or_startup_contract | Gate 2 | Source/package SHA-256 is `fdca30bdebab3118c675f3a49a99f9cf52e8eafba4638be98f7d3075fd05ee21`; focused current-pin assertion passed. |
| CAT-02 | Frozen snapshot | Create `dyec_builds.18.0.56` as the exact updated `current` snapshot while leaving `18.0.55` byte/semantic content unchanged. | SUCCESS | active_product_contract | Gate 2 | Focused `18.0.56` current/snapshot and `18.0.55` frozen-snapshot tests passed; all eleven production IDs resolve to only `15.0.37`. |
| REL-01 | Release | Push the temporary branch, merge it into a release branch from `18.0.55`, and publish annotated tag `18.0.56`. | SUCCESS | active_product_contract | Gate 5 | Temporary branch `eba66d06` was pushed; this release branch merges it from immutable `18.0.55`. The annotated tag is created after this terminal ledger commit. |

## Final report

All rows terminal: yes.
Objective complete: yes; `18.0.56` freezes the current command catalog to
DayOA `15.0.37` and preserves the prior numeric catalog snapshots.
