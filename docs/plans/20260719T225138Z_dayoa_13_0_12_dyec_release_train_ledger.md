# DayOA 13.0.12 and DYEC release train ledger

Timestamp: `20260719T225138Z`

## Objective

Publish the merged DayOA missing-descriptive-tag warning as annotated release
`13.0.12`, advance DYEC's explicit DayOA pin to `13.0.12`, publish the
intermediate DYEC release `12.0.7`, then advance the DYEC self-pin to `12.0.7`
and publish final DYEC release `12.0.8`.

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
  push, annotated intermediate tag and push; DYEC self-pin commit, branch
  push, annotated final tag and push; PR merge after green checks.

## Plan amendment: concurrent immutable DYEC tags

After the initial branch commit, a complete remote-tag audit found annotated
tags `12.0.3` through `12.0.6` on
`origin/codex/hiomrs-inflection-acceptance`, outside `origin/main` ancestry.
No existing tag was moved or overwritten. That release lineage was merged into
this current-main branch, resolving only the intended DayOA pin forward to
`13.0.12`. The collision-free versions are therefore intermediate `12.0.7`
and final `12.0.8`.

## Execution rows

| ID | Repo | Requirement | Status | Category | Gate | Evidence | Root cause | Terminal note |
|---|---|---|---|---|---|---|---|---|
| DOA-001 | DayOA | Publish annotated `13.0.12` at merged PR 53 source | SUCCESS | feature_implementation | Gate 1 | Tag object `391ce10d0e252d6275e3b899da3f65921a62aff9`; peeled commit `6255b1de9847a8d2da6f048543abc2d3c513b946`; remote tag verified |  | Exact merged source released without moving an existing tag. |
| DYE-001 | DYEC | Advance all active and packaged DayOA defaults to `13.0.12` | SUCCESS | config_or_startup_contract | Gate 2 | Both runtime catalog copies plus four active test contracts updated; focused pytest `46 passed`; Ruff lint clean; `git diff --check` clean |  | Runtime and packaged defaults have exact pin parity; historical evidence remains unchanged. |
| DYE-002 | DYEC | Commit/push branch and publish annotated intermediate tag `12.0.7` | SUCCESS | feature_implementation | Gate 3 | Branch commit `1c2f74fef7069bebb6f1199234303a5fcecc14a2`; release-lineage merge `f150ae11713403ede595f91eb7e6e41c4c8d7635`; remote annotated tag `12.0.7` peels to `f150ae11713403ede595f91eb7e6e41c4c8d7635` |  | Concurrent `12.0.3`-`12.0.6` lineage retained and immutable; collision-free intermediate release published. |
| DYE-003 | DYEC | Advance active and packaged DYEC self-pin to `12.0.7` | SUCCESS | config_or_startup_contract | Gate 2 | Both `daylily_cli_global.yaml` copies and `DYEC_BLESSED_TAG` advanced; focused pytest `46 passed`; Ruff lint clean; runtime/payload byte parity verified; `git diff --check` clean |  | Self-pin now targets the published intermediate release exactly. |
| DYE-004 | DYEC | Commit/push branch and publish annotated final tag `12.0.8` | SUCCESS | feature_implementation | Gate 3 | Commit `574b2820de5738724c3a911608b2e8cc80f3a015`; remote annotated tag `12.0.8` peels to that exact commit |  | Final self-pinned release published without moving an existing tag. |
| PUB-001 | DYEC | Open PR, wait for required checks, and merge normally to `main` | SUCCESS | feature_implementation | Gate 5 | PR 45 merged normally at `2026-07-19T22:57:56Z`; merge commit `44ec7d4c2ac51d18b0ba8a24d225d4db2a5d83a6`; GitHub reported no required checks on the branch |  | Release branch is merged to `main` without admin bypass. |
| ACC-001 | Both | Verify remote annotated tag objects, peeled commits, ancestry, pin parity, and clean release worktrees | SUCCESS | contract_test | Gate 5 | DayOA `13.0.12` peels to `6255b1de9847a8d2da6f048543abc2d3c513b946`; DYEC `12.0.7` peels to `f150ae11713403ede595f91eb7e6e41c4c8d7635`; DYEC `12.0.8` peels to `574b2820de5738724c3a911608b2e8cc80f3a015`; all are annotated tag objects; DYEC tags `12.0.6`-`12.0.8` are ancestors of `origin/main`; runtime/payload pins have exact parity |  | Remote tags, ancestry, and pinned-version contracts all verified. |

## Final terminal-state report

- Status counts: 7 `SUCCESS`; 0 other states.
- All rows terminal: yes.
- Objective complete: yes.
