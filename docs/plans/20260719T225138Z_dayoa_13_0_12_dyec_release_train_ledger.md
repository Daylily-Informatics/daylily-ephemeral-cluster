# DayOA 13.0.12 and DYEC release train ledger

Timestamp: `20260719T225138Z`

## Objective

Publish the merged DayOA missing-descriptive-tag warning as annotated release
`13.0.12`, advance DYEC's explicit DayOA pin to `13.0.12`, publish the
intermediate DYEC release `12.0.3`, then advance the DYEC self-pin to `12.0.3`
and publish final DYEC release `12.0.4`.

## Gate 0: inventory freeze

- DayOA source: `lsmc-bio/daylily-omics-analysis` `origin/main` at
  `6255b1de9847a8d2da6f048543abc2d3c513b946`, merged PR 53.
- DayOA prior highest numeric release: `13.0.11`; remote `13.0.12` was absent.
- DYEC source: isolated clean worktree
  `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-dayoa-13.0.12-release-20260719`
  on `codex/dayoa-13.0.12-dyec-release-20260719`, based on `origin/main`
  `aa9dc1ad6248d81d88f14c5f253feecea21ac685`.
- DYEC prior highest numeric release: `12.0.2`; active DayOA default pin:
  `13.0.3`; active DYEC self-pin: `12.0.2`.
- The user-owned canonical checkouts have unrelated untracked work and are not
  used for staging or release commits.
- Release order: DayOA annotated tag and push; DYEC DayOA-pin commit, branch
  push, annotated `12.0.3` tag and push; DYEC self-pin commit, branch push,
  annotated `12.0.4` tag and push; PR merge after green checks.

## Execution rows

| ID | Repo | Requirement | Status | Category | Gate | Evidence | Root cause | Terminal note |
|---|---|---|---|---|---|---|---|---|
| DOA-001 | DayOA | Publish annotated `13.0.12` at merged PR 53 source | SUCCESS | feature_implementation | Gate 1 | Tag object `391ce10d0e252d6275e3b899da3f65921a62aff9`; peeled commit `6255b1de9847a8d2da6f048543abc2d3c513b946`; remote tag verified |  | Exact merged source released without moving an existing tag. |
| DYE-001 | DYEC | Advance all active and packaged DayOA defaults to `13.0.12` | SUCCESS | config_or_startup_contract | Gate 2 | Both runtime catalog copies plus four active test contracts updated; focused pytest `46 passed`; Ruff lint clean; `git diff --check` clean |  | Runtime and packaged defaults have exact pin parity; historical evidence remains unchanged. |
| DYE-002 | DYEC | Commit/push branch and publish annotated intermediate tag `12.0.3` | IN_PROGRESS | feature_implementation | Gate 3 | Pending commit, push, and remote tag proof |  |  |
| DYE-003 | DYEC | Advance active and packaged DYEC self-pin to `12.0.3` | OPEN | config_or_startup_contract | Gate 2 | Pending diff and focused tests |  |  |
| DYE-004 | DYEC | Commit/push branch and publish annotated final tag `12.0.4` | OPEN | feature_implementation | Gate 3 | Pending |  |  |
| PUB-001 | DYEC | Open PR, wait for required checks, and merge normally to `main` | OPEN | feature_implementation | Gate 5 | Pending |  |  |
| ACC-001 | Both | Verify remote annotated tag objects, peeled commits, ancestry, pin parity, and clean release worktrees | OPEN | contract_test | Gate 5 | Pending |  |  |

## Final terminal-state report

- All rows terminal: no.
- Objective complete: no.
