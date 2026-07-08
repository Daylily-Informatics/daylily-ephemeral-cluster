# Remove `jemdev10` Remote Refs Ledger

Date: 2026-07-08T10:47:37Z

## Control Ledger

Controlling request: user stated there should be no remaining `jemdev10`.
Ledger path: `docs/plans/20260708T104737Z_remove_jemdev10_refs_ledger.md`

Gate 0 baseline:
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, local branch `jem-dev`, tracking `origin/jem-dev`.
- DYEC local worktree has uncommitted custom-action-args fix files; branch cleanup must not overwrite or stage those edits.
- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`, local branch `jem-dev`, tracking `origin/jem-dev`, clean at baseline.
- `lsmc-bio/daylily-ephemeral-cluster`: default branch `jem-dev`; branches matching `jem*`: `jem-dev`, `jem-dev-dragen`; no `jemdev10`.
- `lsmc-bio/daylily-omics-analysis`: default branch `main`; branches matching `jem*`: `jem-dev`, `jem-dev-dragen`; no `jemdev10`.
- `Daylily-Informatics/daylily-ephemeral-cluster`: default branch `jemdev10`; branch `jemdev10` at `26aacae038ac5e21b9de49efb43c3fc47fdacf29`.
- `Daylily-Informatics/daylily-omics-analysis`: default branch `jemdev10`; branch `jemdev10` at `aed7c0078339e79459f4db3e30d7e89438467e19`.
- DYEC containment check: `origin/jem-dev` contains `upstream/jemdev10`; `origin/jem-dev...upstream/jemdev10` -> `173 0`.
- DayOA containment check: `origin/jem-dev` contains fetched upstream `jemdev10`; `origin/jem-dev...upstream/jemdev10` -> `157 0`.

## Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| J10-001 | Inventory | Find all remaining `jemdev10` refs in DYEC/DayOA lsmc-bio and upstream repos | SUCCESS | config_or_startup_contract | Gate 0 | Codex | GitHub metadata found only upstream Daylily-Informatics repos still using `jemdev10`; lsmc-bio repos have no `jemdev10`. |  | Remaining refs identified. |
| J10-002 | Preservation | Confirm upstream `jemdev10` commits are contained in lsmc-bio `jem-dev` before deletion | SUCCESS | contract_test | Gate 0 | Codex | DYEC `173 0` and DayOA `157 0` ahead/behind counts from `origin/jem-dev...upstream/jemdev10`; both upstream tips are ancestors. |  | No unique upstream `jemdev10` commits need merging. |
| J10-003 | DYEC upstream | Create/update upstream `jem-dev`, switch default from `jemdev10`, delete upstream `jemdev10` | SUCCESS | config_or_startup_contract | Gate 2 | Codex | `Daylily-Informatics/daylily-ephemeral-cluster` was changed to default `jem-dev`, branch `jemdev10` deleted, then user corrected that Daylily-Informatics branches should not be active work targets. |  | Superseded by correction row J10-006; no lsmc-bio commits were left out. |
| J10-004 | DayOA upstream | Create/update upstream `jem-dev`, switch default from `jemdev10`, delete upstream `jemdev10` | SUCCESS | config_or_startup_contract | Gate 2 | Codex | `Daylily-Informatics/daylily-omics-analysis` was changed to default `jem-dev`, branch `jemdev10` deleted, then user corrected that Daylily-Informatics branches should not be active work targets. |  | Superseded by correction row J10-006; no lsmc-bio commits were left out. |
| J10-005 | Verification | Verify no `jemdev10` branch remains on checked repos and clean local tracking refs | SUCCESS | contract_test | Gate 5 | Codex | Four-repo scan showed zero `jemdev10` refs in lsmc-bio DYEC/DayOA and Daylily-Informatics DYEC/DayOA. |  | Verified after initial cleanup. |
| J10-006 | Correction | Rename the Daylily-Informatics `jem-dev` branches created by mistake to `not-to-be-used-w-out-approval` | SUCCESS | plan_amendment | Gate 2 | Codex | Created `Daylily-Informatics/daylily-ephemeral-cluster:not-to-be-used-w-out-approval` at `b3e7d8e342826bb59fcb7d29adf6bbc89b8caaef`, set it as default, deleted upstream `jem-dev`; created `Daylily-Informatics/daylily-omics-analysis:not-to-be-used-w-out-approval` at `c0acb423d95beebf9d31006dbad941ef672c5c5d`, set it as default, deleted upstream `jem-dev`. |  | Final upstream touched repos have no `jem-dev` or `jemdev10`; default branch is the explicit guard branch. |
| J10-007 | Local hygiene | Remove accidental local-only DayOA `refs/remotes/upstream/*` refs created during verification fetch | SUCCESS | test_helper_only | Gate 5 | Codex | `git for-each-ref refs/remotes/upstream ... git update-ref -d`; DayOA `git branch -r` shows no `upstream/*`; status clean on `jem-dev...origin/jem-dev`. |  | Local DayOA checkout returned to origin-only tracking shape. |

## Correction Final State

- `Daylily-Informatics/daylily-ephemeral-cluster`: default branch `not-to-be-used-w-out-approval`; `jem-dev` count `0`; `jemdev10` count `0`; guard branch SHA `b3e7d8e342826bb59fcb7d29adf6bbc89b8caaef`.
- `Daylily-Informatics/daylily-omics-analysis`: default branch `not-to-be-used-w-out-approval`; `jem-dev` count `0`; `jemdev10` count `0`; guard branch SHA `c0acb423d95beebf9d31006dbad941ef672c5c5d`.
- `lsmc-bio/daylily-ephemeral-cluster`: current `origin/jem-dev` contains deleted upstream `jemdev10` SHA `26aacae038ac5e21b9de49efb43c3fc47fdacf29`; commit count from deleted SHA to lsmc-bio tip was `174`, reverse count `0`.
- `lsmc-bio/daylily-omics-analysis`: current `origin/jem-dev` contains deleted upstream `jemdev10` SHA `aed7c0078339e79459f4db3e30d7e89438467e19`; commit count from deleted SHA to lsmc-bio tip was `157`, reverse count `0`.

All rows are terminal: 7 `SUCCESS`, 0 `BLOCKED`, 0 `FAIL`.
