# DayOA/DYEC Peddy Release Train Ledger

Date: 2026-07-31

## Control Ledger

Controlling request: merge the outstanding DayOA and DYEC changes through pull requests, release DayOA, advance the DYEC DayOA pin and release it, then advance the DYEC self-pin and release it.

Ledger path: `docs/plans/20260731T112332Z_dayoa_dyec_peddy_release_train_ledger.md`

Gate 0 baseline:

- DayOA remote `main`: `88a94017e4561e17f20f17d9e20b44e377ed57cf` before the Peddy PR; the original checkout was preserved and release work used `/Users/jmajor/.codex/worktrees/dayoa-peddy-main-13108`.
- DayOA Peddy source commit: `9479e65e4844e56b7058d784c7bebb05bb0d0bc0`; its six-file patch was cherry-picked onto current `main` as `8223cf61f686e24dc0d44449acd84ea8d9a7e5df`.
- DYEC remote `main`: `7110269f3dbff626a346ac4001df90a5eb234553`; the original detached checkout contains unrelated untracked user artifacts and is not used for release edits.
- DYEC outstanding source branch: `origin/codex/cmd-catalog-slim-execution-20260731` at `f968f45a7c407d2b233680d0c11a7b8ac44a8bb2`; the four coherent commits were cherry-picked onto current `main` in `/Users/jmajor/.codex/worktrees/dyec-cmd-catalog-main-16123`.
- Current highest release tags at inventory: DayOA `13.0.107`; DYEC `16.1.22`. Tags are rechecked immediately before each release and are never moved.
- Release tags must be unprefixed annotated tags on exact merged `main` commits.
- No package-index publishing, live workflow execution, Slurm manipulation, AWS mutation, or dirty-checkout cleanup is authorized by this release train.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DAYOA-001 | DayOA | Transplant only the six-file Peddy native-output fix onto current `main`, run focused tests, open a PR, and merge normally after checks pass | SUCCESS | feature_implementation | Gate 1 | orchestrator | PR `#80`; focused pytest `4 passed`; CodeQL Python and JavaScript checks passed; merge commit `364cee5f7f42d24b0c804455ec91703e9994bdca` |  | Narrow Peddy fix merged to `main` without the divergent feature-branch lineage. |
| DAYOA-002 | DayOA | Create and push the next free annotated DayOA release tag on the merged Peddy commit | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Remote annotated tag `13.0.108`; peeled commit `364cee5f7f42d24b0c804455ec91703e9994bdca` |  | DayOA `13.0.108` is published and immutable. |
| DYEC-001 | DYEC | Rebase the coherent outstanding command-catalog/headnode-startup changes onto current `main`, test them, open a PR, and merge normally | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | PR `#69`; four source commits rebased onto current `main`; shell syntax and payload parity passed; affected-file pytest suite `282 passed`; merge commit `a8dad3098fd208f96309f9e2787e1a60e9a5f0ea` |  | Outstanding startup/catalog changes merged normally to `main`; the repository had no configured PR checks. |
| DYEC-002 | DYEC | Update all authoritative DayOA pins to `13.0.108`, test, open a PR, and merge normally | IN_PROGRESS | config_or_startup_contract | Gate 2 | orchestrator | Source and packaged command catalogs plus seven active contract-test files updated; DayOA release commit constant advanced to `364cee5f7f42d24b0c804455ec91703e9994bdca`; historical ledgers retained; catalog parity and diff checks passed; focused suite `298 passed` |  | Awaiting PR checks and normal merge. |
| DYEC-003 | DYEC | Create and push the next free annotated DYEC tag for the DayOA-pin release | OPEN | config_or_startup_contract | Gate 2 | orchestrator | Pending; expected candidate `16.1.23`, subject to remote recheck |  |  |
| DYEC-004 | DYEC | Advance all authoritative DYEC self-pins to the DYEC tag from DYEC-003, test, open a PR, and merge normally | OPEN | config_or_startup_contract | Gate 2 | orchestrator | Pending |  |  |
| DYEC-005 | DYEC | Create and push the next free annotated DYEC tag for the self-pin release | OPEN | config_or_startup_contract | Gate 2 | orchestrator | Pending; expected candidate `16.1.24`, subject to remote recheck |  |  |
| VERIFY-001 | Both | Verify PR merge commits, clean release worktrees, annotated tag object types, remote tag objects, and peeled commits | OPEN | contract_test | Gate 5 | orchestrator | Pending |  |  |

## Final Report

All rows terminal: no

Objective complete: no

Status counts:

- SUCCESS: 3
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
- IN_PROGRESS: 1
- OPEN: 4

Validation to date:

- DYEC shell syntax and checked-in/payload installer parity: passed.
- DYEC affected-file suite: `282 passed in 7.99s`.
- DYEC DayOA-pin source/package catalog parity and focused suite: `298 passed in 13.06s`.

Exact remote release evidence will be added as each row reaches a terminal state.
