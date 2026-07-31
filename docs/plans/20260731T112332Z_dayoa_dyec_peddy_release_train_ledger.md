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
| DYEC-002 | DYEC | Update all authoritative DayOA pins to `13.0.108`, test, open a PR, and merge normally | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | PR `#70`; source and packaged command catalogs plus seven active contract-test files updated; DayOA release commit constant advanced to `364cee5f7f42d24b0c804455ec91703e9994bdca`; catalog parity and diff checks passed; focused suite `298 passed`; merge commit `51041b69b354bd37ba23c8ed02caeff8eea1bb65` |  | DayOA `13.0.108` is the active DYEC catalog pin on `main`. |
| DYEC-003 | DYEC | Create and push the next free annotated DYEC tag for the DayOA-pin release | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Remote annotated tag `16.1.23`; peeled commit `51041b69b354bd37ba23c8ed02caeff8eea1bb65` |  | DYEC DayOA-pin release `16.1.23` is published and immutable. |
| DYEC-004 | DYEC | Advance all authoritative DYEC self-pins to the DYEC tag from DYEC-003, test, open a PR, and merge normally | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | PR `#71`; source and packaged global config plus active self-pin contract constant advanced from `16.1.21` to `16.1.23`; source/package parity and diff checks passed; focused fork-contract suite `4 passed`; merge commit `bccc85d54dfede021acbaed9edbeea1471ac94a2` |  | DYEC self-pin `16.1.23` is on `main`; the repository had no configured PR checks. |
| DYEC-005 | DYEC | Create and push the next free annotated DYEC tag for the self-pin release | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Remote annotated tag `16.1.24`; peeled commit `bccc85d54dfede021acbaed9edbeea1471ac94a2` |  | DYEC self-pin release `16.1.24` is published and immutable. |
| VERIFY-001 | Both | Verify PR merge commits, clean release worktrees, annotated tag object types, remote tag objects, and peeled commits | SUCCESS | contract_test | Gate 5 | orchestrator | PRs `#80`, `#69`, `#70`, and `#71` all report `MERGED`; `git cat-file -t` reports `tag` for `13.0.108`, `16.1.23`, and `16.1.24`; remote peeled commits match the recorded merge commits; release worktrees are clean; final DYEC source/package config blob IDs match |  | Remote PR, tag, pin, and worktree evidence reconciles. |

## Final Report

All rows terminal: yes

Objective complete: yes

Status counts:

- SUCCESS: 8
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
- IN_PROGRESS: 0
- OPEN: 0

Validation to date:

- DYEC shell syntax and checked-in/payload installer parity: passed.
- DYEC affected-file suite: `282 passed in 7.99s`.
- DYEC DayOA-pin source/package catalog parity and focused suite: `298 passed in 13.06s`.
- DYEC self-pin source/package parity and focused fork-contract suite: `4 passed in 0.20s`.

Released versions:

- DayOA `13.0.108` -> `364cee5f7f42d24b0c804455ec91703e9994bdca`.
- DYEC DayOA-pin release `16.1.23` -> `51041b69b354bd37ba23c8ed02caeff8eea1bb65`.
- DYEC self-pin release `16.1.24` -> `bccc85d54dfede021acbaed9edbeea1471ac94a2`.

Changed release surfaces:

- DayOA: six Peddy native-output contract implementation/test files.
- DYEC: command-catalog/headnode startup repairs and tests; active source/package DayOA catalog pins; active source/package DYEC self-pins; contract tests; durable release ledgers.

Residual notes:

- The original DayOA feature checkout has an unpushed duplicate Peddy commit `52d66746`; no remote branch, PR, release tag, or merged commit references it. It was left intact rather than rewritten destructively.
- This terminal ledger closeout is a post-tag documentation commit and does not move any release tag.
