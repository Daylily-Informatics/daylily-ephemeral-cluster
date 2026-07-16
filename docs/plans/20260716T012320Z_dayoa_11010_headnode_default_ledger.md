# DayOA 11.0.10 Headnode Default Ledger

Controlling request: publish the exact-identity DayOA correction and make the
configured `ifx-p2-1000-120-0715` headnode `day-clone` default resolve to that
new DayOA version without restarting the paused analysis controller.

Ledger path: `docs/plans/20260716T012320Z_dayoa_11010_headnode_default_ledger.md`

## Gate 0 Baseline

- Repo: `daylily-ephemeral-cluster`
- Worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-main-release-10315-20260716`
- Branch: `codex/dyec-main-release-10315`, fast-forwarded to `origin/main`
  commit `0e400f0ff905f5f69055cb7f0d222520916490cf` before edits.
- Existing source/payload DayOA default and HIOMRS pins: `11.0.9`.
- Existing DYEC self pin: `10.3.15`.
- Target releases: DayOA `11.0.10`; DYEC `10.3.16`.
- Live scope: install source-owned headnode tools/catalog on cluster
  `ifx-p2-1000-120-0715`; do not restart `dy-r`, alter Slurm, or delete data.

## Control Ledger

| ID | Area | Requirement | Status | Category | Gate | Evidence | Terminal note |
|---|---|---|---|---|---|---|---|
| DHD-001 | Catalog | Set source and payload `daylily-omics-analysis.default_ref` to `11.0.10`. | SUCCESS | config_or_startup_contract | Gate 2 | Commit `1f498f30`; catalog and payload match; focused tests passed. | DayOA default updated without a mutable-only headnode patch. |
| DHD-002 | HIOMRS catalog | Pin both Sentieon HIOMRS command rows to DayOA `11.0.10`. | SUCCESS | config_or_startup_contract | Gate 2 | Commit `1f498f30`; both catalog rows and payload rows use `11.0.10`. | Exact HIOMRS commands now select the released DayOA correction. |
| DHD-003 | DYEC release | Advance source/payload self pins to `10.3.16` in a separate commit and push an annotated tag. | IN_PROGRESS | feature_implementation | Gate 5 | Source/payload/test self pins updated; final test and publication pending. |  |
| DHD-004 | Headnode | Install the exact DYEC release and verify `day-clone` default/auth resolves DayOA `11.0.10`. | OPEN | config_or_startup_contract | Gate 5 | Pending release publication. |  |
| DHD-005 | Safety | Keep the paused analysis controller stopped and leave Slurm/data untouched. | IN_PROGRESS | legitimate_safety_handling | Gate 5 | Queue/controller status to be verified after install. |  |

## Final Report

All rows terminal: no.

Objective complete: no; catalog tests, release publication, and headnode
verification remain in progress.
