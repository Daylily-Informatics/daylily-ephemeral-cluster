# DYEC Catalog Maximum DayOA Release Ledger

Created: 2026-07-26T15:21:47Z

## Objective

Release one immutable DYEC patch in which the `daylily-omics-analysis`
repository default and every analysis command `git_tag` and
`validated_version` use the maximum published DayOA tag, `13.0.44`, so Ursa
can enforce one fail-closed workflow source contract.

## Gate 0

- Source branch: `codex/dyec-catalog-dayoa-13.0.44`
- Baseline commit/tag: `45e3c3605728af2627e9160b5240bba402ca61d3`
  / annotated `14.0.17`
- Baseline catalog: 25 commands, all pinned to `13.0.41`
- Maximum remote DayOA tag: annotated `13.0.44`
- DayOA `13.0.44` tag object: `865ee98e09e84ed6b89438e3b732e74f721e4599`
- DayOA `13.0.44` peeled commit:
  `256cfb67ed308de66c35f95a9e5049d631365251`
- Scope: both canonical DYEC catalog copies, their direct contract tests,
  this ledger, release commit, and annotated patch tag only.
- Excluded: AWS resources, clusters, DayOA workflows, Slurm, budgets, Ursa
  deployment, and unrelated files in the source checkout.

## Execution

| ID | Work item | State | Evidence |
|---|---|---|---|
| CAT-001 | Pin the repository default and all 25 commands to DayOA `13.0.44` | SUCCESS | Both catalog copies and direct contract expectations updated |
| CAT-002 | Prove both catalog copies are byte-identical and uniformly pinned | SUCCESS | Matching SHA-256 `d30b57d657b7708989b8c17d1cb64a67b9ad52e67f6049951ae8e9d8b3841908`; 25 commands; singleton tag/version set `13.0.44` |
| CAT-003 | Run focused and full DYEC tests | SUCCESS | Focused catalog contracts: 294 passed. Full suite: 2,400 passed, 11 skipped, and 11 inherited failures reproduced unchanged on untouched `14.0.17` (11 failed, 4 passed in the exact failing subset). |
| CAT-004 | Commit, push, create an annotated numeric patch tag, and verify it | IN_PROGRESS | Pending |

## Baseline Test Debt

The full suite's 11 failures are not introduced by this branch. The exact
failing subset reproduces on an untouched `14.0.17` worktree:

- one repo/package `environment.yaml` parity mismatch;
- eight existing semantic headnode commands pass `as_user=auto` while their
  tests require `ubuntu`;
- one pre-existing ephemeral-cluster template payload parity mismatch; and
- one pre-existing triplet required-key expectation that omits three
  cost-center keys.

No file involved in those failures is changed by the catalog release.

## Acceptance

- Both catalog copies are byte-identical.
- Exactly 25 commands exist.
- Every command has `git_tag: 13.0.44` and
  `validated_version: 13.0.44`.
- The repository `default_ref` is `13.0.44`.
- Required tests pass.
- The release tag is annotated and points at the clean release commit.
