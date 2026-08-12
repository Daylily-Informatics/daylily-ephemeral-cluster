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
| DAYOA-TAG | DayOA | Create and push annotated tag `14.0.0` on the clean candidate commit and verify its derived package version. | SUCCESS | feature_implementation | Gate 5 | orchestrator | Annotated remote tag object `118d018924ececa937e4153e279795384978e61d` peels to `f799ba3d5a7bc67bbed112ef4c3f77ca2f9da41a`; isolated `pip wheel --no-deps --no-cache-dir` built `daylily_omics_analysis-14.0.0-py3-none-any.whl`. |  | The missing direct helper was resolved through isolated build validation; immutable tag remained unchanged. |
| DAYOA-PRERELEASE | DayOA | Create and verify a GitHub prerelease page for `14.0.0`. | SUCCESS | feature_implementation | Gate 5 | orchestrator | [DayOA 14.0.0 prerelease](https://github.com/lsmc-bio/daylily-omics-analysis/releases/tag/14.0.0), verified `isDraft=false` and `isPrerelease=true`, published `2026-08-12T17:18:58Z`. |  | Published from the existing remote annotated tag. |
| DYEC-PIN | DYEC | Move active/current DayOA pins to `14.0.0`, preserve existing snapshots, and add exact `current` snapshot `17.0.0`. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Active repository rows and `current` contain 29 commands pinned to DayOA `14.0.0`; numeric `17.0.0` is an exact copy of updated `current`; structural comparison proves `16.1.81`, `16.1.82`, `16.1.85`, and `16.1.86` are unchanged. |  | New major snapshot added without altering historical releases. |
| DYEC-VALIDATE | DYEC | Prove catalog parity, historical-snapshot preservation, selector behavior, and the release-focused test gate. | SUCCESS | contract_test | Gate 5 | orchestrator | Source/payload catalogs compare byte-identical; release-focused suite passed 681 tests; targeted Ruff, byte-compilation, and diff checks passed; CLI probes returned 29 commands on DayOA `14.0.0` for `current`/`17.0.0`, 29 on `13.4.34` for `16.1.86`, 29 on `13.4.33` for `16.1.85`, and 9 on `13.4.31` for `16.1.82`. |  | All pre-tag release gates passed. |
| DYEC-TAG | DYEC | Commit, push, create annotated tag `17.0.0`, and verify the exact tagged version. | IN_PROGRESS | feature_implementation | Gate 5 | orchestrator | Release inputs validated; commit, availability recheck, annotated tag, push, and exact-tag rerun remain. |  |  |
| DYEC-PRERELEASE | DYEC | Create and verify a GitHub prerelease page for `17.0.0`. | OPEN | feature_implementation | Gate 5 | orchestrator | Pending tag publication. |  |  |
| FINAL-001 | Cross-repo | Verify synchronized candidate branches, immutable annotated tag objects and peeled commits, both prerelease pages, and terminal ledger state. | OPEN | contract_test | Gate 5 | orchestrator | Pending. |  |  |

## Final report

All rows terminal: no.

Objective complete: no.

Status counts: `SUCCESS=5`, `OPEN=2`, `IN_PROGRESS=1`, `BLOCKED=0`,
`FAIL=0`, `NO_LONGER_NEEDED=0`.
