# DYEC Dirty-Tree Double Release Ledger

Created: 2026-07-16T01:33:05Z

Objective: preserve and publish every current non-ignored DYEC worktree change, merge it to `main`, then complete the repository's two-step release contract: DayOA-pin release followed by DYEC self-pin release.

## Gate 0: Inventory

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Release branch: `codex/fsx-create-selection-contract` at `0e400f0f`, two commits behind `origin/main`.
- Current upstream releases: DayOA `11.0.10`; DYEC annotated tag `10.3.16` at `origin/main`.
- Dirty scope: FSx create-selection lifecycle work, Ursa completion link, AWS Price List idle-cost reporting, AWS API audit/report work, tests, documentation, ledgers, and the existing read-only cost-utilization evidence bundle.
- Target releases: `10.3.17` for the DayOA `11.0.11` pin plus all current dirty work, then `10.3.18` for the DYEC self-pin to `10.3.17`.

## Control Ledger

| ID | Requirement | Status | Evidence | Terminal note |
|---|---|---|---|---|
| DYE-001 | Freeze the exact dirty inventory and preserve all non-ignored files. | SUCCESS | `git status --short`, `git diff --stat`, 62-file cost evidence bundle inventory | No dirty file is silently discarded. |
| DYE-002 | Run focused and full validation on the complete dirty work. | SUCCESS | Focused `263 passed`; full `1573 passed, 11 skipped`; focused Ruff and `git diff --check` passed | Full suite includes AWS API audit and idle-cost tests. |
| DYE-003 | Commit the complete dirty scope on the release branch. | SUCCESS | `5711e8d9` (`263,319 insertions`, complete non-ignored inventory) | All requested dirty work is preserved in the release commit. |
| DYE-004 | Rebase the release branch onto current `origin/main` and update DayOA catalog pins to `11.0.11`. | SUCCESS | `5711e8d9` parent `1af6b55e`; source/package catalog pins and fork-contract test now name `11.0.11` | Rebase was clean and the release pin is explicit in both payload trees. |
| DYE-005 | Revalidate, push, open the first DYEC PR, wait for checks, and merge. | OPEN | Focused release validation: `250 passed` plus `5 passed`; full `1573 passed, 11 skipped`; Ruff and scoped `git diff --check` passed. Push/PR/checks/merge pending. |  |
| DYE-006 | Fast-forward local `main`, create annotated tag `10.3.17`, and push it. | OPEN |  |  |
| DYE-007 | Create a follow-up branch, advance source/package DYEC self-pins to `10.3.17`, and revalidate. | OPEN |  |  |
| DYE-008 | Push the self-pin branch, open and merge its PR after checks. | OPEN |  |  |
| DYE-009 | Fast-forward local `main`, create annotated tag `10.3.18`, and push it. | OPEN |  |  |

## Completion

All rows terminal: no

Objective complete: no
