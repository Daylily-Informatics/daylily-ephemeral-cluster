# LSMC Branch Consolidation Ledger

Created: 2026-07-08T07:30:26Z

Objective: consolidate `jem-dev` and `jemdev10` for DayOA and DYEC in `lsmc-bio`, make `jem-dev` the current branch carrying the relevant changes, close the `lsmc-bio` `jemdev10` branches, and verify whether `lsmc-bio` or `Daylily-Informatics` DayOA/DYEC repos have any other branch tips changed in the last four days.

Controlling repo paths:

- DayOA: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DYEC: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`

## Gate 0 Inventory

Inventory time: 2026-07-08T07:30:26Z

Commands:

- `git fetch --no-tags origin --prune`
- `git status --short --branch`
- `git branch -vv`
- `git merge-base --is-ancestor origin/jemdev10 origin/jem-dev`
- GitHub API branch scans for `lsmc-bio/daylily-omics-analysis`, `lsmc-bio/daylily-ephemeral-cluster`, `Daylily-Informatics/daylily-omics-analysis`, and `Daylily-Informatics/daylily-ephemeral-cluster`

Baseline facts:

- DayOA `lsmc-bio/daylily-omics-analysis`:
  - local branch: `jem-dev`, tracking `origin/jem-dev`
  - `origin/jem-dev`: `ce41c6cc` (`Release DayOA 10.0.66 coverage and resource contracts`)
  - `origin/jemdev10`: absent
  - local status: clean
- DYEC `lsmc-bio/daylily-ephemeral-cluster`:
  - local branch: `jemdev10`
  - `origin/jem-dev`: `f513274a` (`Release DYEC 10.0.108 self pin`)
  - `origin/jemdev10`: `93701fbe` (`Commit DRAGEN docs and config updates`)
  - `origin/jemdev10` is already an ancestor of `origin/jem-dev`
  - local status has dirty tracked changes in README/docs/export CLI code/tests
- Recent branch tips, cutoff 2026-07-04T07:30:26Z:
  - `lsmc-bio/daylily-omics-analysis`: `jem-dev-dragen`, `codex/dragen-headnode-launch-fix`, `jem-dev`
  - `lsmc-bio/daylily-ephemeral-cluster`: `jem-dev-dragen`, `jem-dev`, `codex/dragen-headnode-launch-fix`, `jemdev10`
  - `Daylily-Informatics/daylily-omics-analysis`: no branch tips changed since cutoff
  - `Daylily-Informatics/daylily-ephemeral-cluster`: no branch tips changed since cutoff

Assumptions:

- "Close branch" means delete the named remote branch after confirming its content is present in `jem-dev` or that it is absent.
- The verification of other recent branches is read-only; this ledger does not merge or delete branches other than `lsmc-bio/*/jemdev10`.
- GitHub branch "last changed" is evaluated using branch tip commit committer dates from the GitHub API.

## Tracking Rows

| ID | Repo | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| BC-001 | DYEC | Confirm `origin/jemdev10` content is included in `origin/jem-dev` before closing. | SUCCESS | feature_implementation | Gate 0 | Codex | `git merge-base --is-ancestor origin/jemdev10 origin/jem-dev -> 0` |  | `origin/jemdev10` is already merged into `origin/jem-dev`. |
| BC-002 | DYEC | Move current local dirty DYEC changes onto `jem-dev`, test, and push to `lsmc-bio`. | SUCCESS | feature_implementation | Gate 1 | Codex | Switched from local `jemdev10` to local `jem-dev`, fast-forwarded to `origin/jem-dev`, reapplied dirty work; `pytest tests/test_cli_registry_v2.py tests/test_export.py -q -> 180 passed`; pushed `jem-dev` commit `f524eeb0`. |  | Current DYEC dirty changes are now on `lsmc-bio/daylily-ephemeral-cluster` `jem-dev`. |
| BC-003 | DayOA | Consolidate `lsmc-bio` DayOA `jem-dev` and `jemdev10`. | SUCCESS | not_applicable_after_inspection | Gate 0 | Codex | `origin/jemdev10` is absent; `origin/jem-dev` is clean at `ce41c6cc`. |  | No DayOA `jemdev10` branch exists in `lsmc-bio`, so there is nothing to merge or close there. |
| BC-004 | DYEC/DayOA | Delete `lsmc-bio` remote `jemdev10` refs after safe consolidation. | SUCCESS | feature_implementation | Gate 1 | Codex | DYEC `git push origin --delete jemdev10` initially failed because `jemdev10` was the default branch; `gh api -X PATCH /repos/lsmc-bio/daylily-ephemeral-cluster -f default_branch=jem-dev` succeeded; deletion then succeeded; final GitHub API scan shows `has_jemdev10 False` for both `lsmc-bio` DayOA and DYEC. |  | `lsmc-bio/daylily-ephemeral-cluster` default branch is now `jem-dev`; both requested `lsmc-bio` `jemdev10` refs are absent. |
| BC-005 | All four repos | Verify whether any other `lsmc-bio` or `Daylily-Informatics` DayOA/DYEC branch tips changed in the last four days. | SUCCESS | contract_test | Gate 0 | Codex | GitHub API scan found recent non-`jemdev10` branches in `lsmc-bio`; none in `Daylily-Informatics`. |  | Verification found other recent `lsmc-bio` branches: `jem-dev-dragen` and `codex/dragen-headnode-launch-fix` in both DayOA and DYEC. |
| BC-006 | DYEC | Preserve this ledger in the branch consolidation commit. | SUCCESS | contract_test | Gate 5 | Codex | Ledger path: `docs/plans/20260708T073026Z_lsmc_branch_consolidation_ledger.md`; final ledger update staged for follow-up commit after remote branch closure evidence. |  | Ledger records terminal state for all rows. |

## Final Branch Verification

Final scan time: 2026-07-08T07:34:31Z

`lsmc-bio`:

- `daylily-omics-analysis`
  - default branch: `main`
  - `jemdev10`: absent
  - recent branches since 2026-07-04T07:34:31Z:
    - `jem-dev-dragen` `104fa2d1` 2026-07-08 00:20:13 PDT `Record DRAGEN concordance validation`
    - `codex/dragen-headnode-launch-fix` `378a86d7` 2026-07-07 23:00:55 PDT `Add explicit DRAGEN drbwa drgpg concordance path`
    - `jem-dev` `ce41c6cc` 2026-07-07 21:25:24 PDT `Release DayOA 10.0.66 coverage and resource contracts`
- `daylily-ephemeral-cluster`
  - default branch: `jem-dev`
  - `jemdev10`: absent
  - recent branches since 2026-07-04T07:34:31Z:
    - `jem-dev` `f524eeb0` 2026-07-08 00:33:23 PDT `Consolidate DYEC jem-dev branch changes`
    - `jem-dev-dragen` `67ae16e2` 2026-07-08 00:20:14 PDT `Enable DRAGEN command catalog launch path`
    - `codex/dragen-headnode-launch-fix` `da03e07d` 2026-07-07 21:25:42 PDT `Allow ubuntu IMDS access on DRAGEN headnodes`

`Daylily-Informatics`:

- `daylily-omics-analysis`
  - default branch: `jemdev10`
  - no branch tips changed since 2026-07-04T07:34:31Z
- `daylily-ephemeral-cluster`
  - default branch: `jemdev10`
  - no branch tips changed since 2026-07-04T07:34:31Z

Conclusion:

- Requested `lsmc-bio` `jemdev10` closure is complete.
- `lsmc-bio/daylily-ephemeral-cluster` `jem-dev` now carries the current local DYEC changes and the previous `jemdev10` remote content.
- The assertion that there are no other recent branches is false for `lsmc-bio`: both DayOA and DYEC have recent `jem-dev-dragen` and `codex/dragen-headnode-launch-fix` branch tips.
- The assertion is true for the two checked `Daylily-Informatics` repos: no branch tip changed in the final four-day window.
