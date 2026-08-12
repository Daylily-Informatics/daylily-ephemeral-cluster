# DayOA 14.0.0 and DYEC 17.0.0 prerelease ledger

Controlling request: promote DayOA `13.4.34` to `14.0.0`, promote DYEC
`16.1.86` to `17.0.0`, and create GitHub prerelease pages from both new
versions.

Controlling plan and ledger:
`docs/plans/20260812T171630Z_major_prerelease_14_17_ledger.md`.

## Gate 0 inventory freeze

- DayOA worktree:
  `/Users/jmajor/projects/lsmc/.codex-worktrees/dayoa-prod-candidate-260812`,
  branch `prod-candidate-260812`, clean and synchronized with
  `origin/prod-candidate-260812` at
  `f799ba3d5a7bc67bbed112ef4c3f77ca2f9da41a`. Annotated tag `13.4.34`
  peels to the same commit. Local and remote tag `14.0.0` and its GitHub
  Release object are absent.
- DayOA uses `setuptools_scm` with numeric, non-`v` tags and has no static
  package-version field. This is a version-only major promotion: the new
  annotated `14.0.0` tag will identify the existing clean candidate commit;
  `13.4.34` will remain immutable.
- DYEC worktree:
  `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-prod-candidate-260812`,
  branch `prod-candidate-260812`, clean and synchronized with
  `origin/prod-candidate-260812` at
  `becfeeaa574520133c0c24cd9ffd335164188aca`. Annotated tag `16.1.86`
  peels to release commit `df3559e1ab6666695743325d92a3e08d2af86112`;
  the branch has one later docs-only closeout commit. Local and remote tag
  `17.0.0` and its GitHub Release object are absent.
- DYEC catalog v5 currently has snapshots `16.1.81`, `16.1.82`, `16.1.85`,
  and `16.1.86`, plus `current`. The source and packaged catalogs are
  byte-identical, `current == 16.1.86`, and both contain 29 commands pinned to
  DayOA `13.4.34`.
- This promotion will move active DayOA references and `current` to `14.0.0`,
  preserve all existing numeric snapshots exactly, and create numeric snapshot
  `17.0.0` as an exact copy of the updated `current`.
- The preceding exact-tag DYEC release gate passed 681 tests. This promotion
  will rerun that release-focused gate before and after tagging `17.0.0`.
- Pull requests, merges to `main`, package-index publication, `twup`, AWS,
  headnode configuration, workflow execution, and destructive operations are
  out of scope.
- Both GitHub Release objects requested here will be published as prereleases.
  Tags will be annotated, numeric, immutable, and rechecked for availability
  immediately before creation.

## Control ledger

| ID | Area/repo | Requirement | Status | Category | Approval gate | Owner | Evidence | Root cause | Terminal note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Cross-repo | Freeze branches, commits, version derivation, tags, releases, catalog state, validation baseline, and scope. | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 inventory above; fetch, clean/sync status, tag, release, package-config, and catalog-structure checks completed. |  | Baseline recorded before release writes. |
| DAYOA-TAG | DayOA | Create and push annotated tag `14.0.0` on the clean candidate commit and verify its derived package version. | OPEN | feature_implementation | Gate 5 | orchestrator | Pending final availability recheck. |  |  |
| DAYOA-PRERELEASE | DayOA | Create and verify a GitHub prerelease page for `14.0.0`. | OPEN | feature_implementation | Gate 5 | orchestrator | Pending tag publication. |  |  |
| DYEC-PIN | DYEC | Move active/current DayOA pins to `14.0.0`, preserve existing snapshots, and add exact `current` snapshot `17.0.0`. | OPEN | config_or_startup_contract | Gate 2 | orchestrator | Pending. |  |  |
| DYEC-VALIDATE | DYEC | Prove catalog parity, historical-snapshot preservation, selector behavior, and the release-focused test gate. | OPEN | contract_test | Gate 5 | orchestrator | Pending. |  |  |
| DYEC-TAG | DYEC | Commit, push, create annotated tag `17.0.0`, and verify the exact tagged version. | OPEN | feature_implementation | Gate 5 | orchestrator | Pending final availability recheck. |  |  |
| DYEC-PRERELEASE | DYEC | Create and verify a GitHub prerelease page for `17.0.0`. | OPEN | feature_implementation | Gate 5 | orchestrator | Pending tag publication. |  |  |
| FINAL-001 | Cross-repo | Verify synchronized candidate branches, immutable annotated tag objects and peeled commits, both prerelease pages, and terminal ledger state. | OPEN | contract_test | Gate 5 | orchestrator | Pending. |  |  |

## Final report

All rows terminal: no.

Objective complete: no.

Status counts: `SUCCESS=1`, `OPEN=7`, `IN_PROGRESS=0`, `BLOCKED=0`,
`FAIL=0`, `NO_LONGER_NEEDED=0`.
