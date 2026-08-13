# DYEC 17.0.1 / DayOA 14.0.2 candidate prerelease ledger

Controlling request: update the DYEC production-candidate release to consume the
new DayOA `14.0.2` candidate release.

Controlling plan and ledger:
`docs/plans/20260813T023957Z_dyec_17_0_1_dayoa_14_0_2_prerelease_ledger.md`.

## Gate 0 inventory freeze

- DYEC worktree:
  `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-prod-candidate-260812`,
  branch `prod-candidate-260812`, clean and synchronized with
  `origin/prod-candidate-260812` at
  `8aae539d97eb2d19190cfba1653a63d92cfff7cd`.
- Annotated DYEC tag `17.0.0` has remote tag object
  `ea757fc3923f26d459feb741009055b6d10c7021` and peels to release commit
  `336293c9adbe686c13e7b79fd5387a92a9936d27`; the branch has one later
  docs-only closeout commit. Local and remote tag `17.0.1` and its GitHub
  Release object are absent.
- DayOA annotated tag `14.0.2` has remote tag object
  `ab52f6c8adb454d302eacad4557c31186f88636c` and peels to release commit
  `8b985148f20af34fb2767b616eacfb42f89e6d93`. Its GitHub Release object is
  published with `isDraft=false` and `isPrerelease=true`.
- DYEC catalog v5 currently has 29 commands in `current`, all pinned to DayOA
  `14.0.0`; `current == 17.0.0`. The source and packaged catalogs are
  byte-identical. Historical snapshot `16.1.86` remains pinned to DayOA
  `13.4.34`.
- This patch promotion will move only active repository/default references and
  `dyec_builds.current` to DayOA `14.0.2`, preserve every existing numeric
  snapshot byte-for-byte, and add numeric snapshot `17.0.1` as an exact copy
  of the updated `current` block.
- The next free DYEC version inferred from live numeric tags is `17.0.1`.
  DYEC uses `setuptools_scm`, so the annotated numeric tag supplies the exact
  package version without a static version-field edit.
- Pull requests, merges to `main`, package-index publication, `twup`, AWS,
  headnode configuration, workflow execution, and destructive operations are
  out of scope. The GitHub Release object will be a prerelease, matching the
  candidate-release train.

## Control ledger

| ID | Area/repo | Requirement | Status | Category | Approval gate | Owner | Evidence | Root cause | Terminal note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | DYEC/DayOA | Freeze branches, commits, tag provenance, release objects, catalog state, version inference, and scope. | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 inventory above; live fetch/status/tag/release/catalog checks completed. |  | Baseline recorded before release writes. |
| DYEC-PIN | DYEC | Move active/current DayOA pins to `14.0.2`, preserve existing numeric snapshots, and add exact `current` snapshot `17.0.1`. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Active repository rows and `current` contain 29 commands pinned to DayOA `14.0.2`; numeric `17.0.1` is an exact copy of updated `current`; parsed structural comparison proves `16.1.81`, `16.1.82`, `16.1.85`, `16.1.86`, and `17.0.0` are unchanged from annotated tag `17.0.0`. |  | New patch snapshot added without altering historical release pins. |
| DYEC-VALIDATE | DYEC | Prove catalog parity, historical-snapshot preservation, selector behavior, focused lint/compile checks, and the release-focused test gate. | SUCCESS | contract_test | Gate 5 | orchestrator | Source/payload catalogs compare byte-identical; release-focused suite passed 681 tests; focused 327-test slice passed; targeted Ruff syntax/undefined-name rules, byte-compilation, and diff checks passed; CLI probes returned 29 commands on DayOA `14.0.2` for `current`/`17.0.1`, 29 on `14.0.0` for `17.0.0`, 29 on `13.4.34` for `16.1.86`, 29 on `13.4.33` for `16.1.85`, and 9 on `13.4.31` for `16.1.82`. |  | All pre-tag release gates passed. |
| DYEC-TAG | DYEC | Commit and push the candidate changes, create and push annotated tag `17.0.1`, and verify the exact tagged version. | IN_PROGRESS | feature_implementation | Gate 5 | orchestrator | Catalog and tests are validated; release commit/tag pending. |  |  |
| DYEC-PRERELEASE | DYEC | Create and verify a GitHub prerelease page for `17.0.1`. | OPEN | feature_implementation | Gate 5 | orchestrator | Pending. |  |  |
| FINAL-001 | DYEC | Verify the remote candidate branch, immutable annotated tag, prerelease page, clean worktree, catalog invariants, and terminal ledger state. | OPEN | contract_test | Gate 5 | orchestrator | Pending. |  |  |

## Final report

All rows terminal: no.

Objective complete: no.

Status counts: `SUCCESS=3`, `IN_PROGRESS=1`, `OPEN=2`, `BLOCKED=0`,
`FAIL=0`, `NO_LONGER_NEEDED=0`.

Validation, changed-file inventory, non-success terminal rows, and residual
risks will be recorded after the release gates complete.
