# Prod-candidate-260812 DayOA and DYEC release-train ledger

Controlling request: merge both `prod-candidate-260911` branches to `main`
through normal pull requests; create GitHub prerelease pages for DayOA
`13.4.33` and DYEC `16.1.85`; create `prod-candidate-260812` from each updated
`main`; publish the next DayOA release; then update DYEC's current catalog and
new release snapshot to that DayOA tag and publish the next DYEC release.

Controlling plan and ledger:
`docs/plans/20260812T163242Z_prod_candidate_260812_release_train_ledger.md`.

## Gate 0 inventory freeze

- DayOA candidate worktree:
  `/Users/jmajor/projects/lsmc/.codex-worktrees/dayoa-prod-candidate-260911`,
  branch `prod-candidate-260911`, clean and synchronized with its remote at
  `56208632627ccff4c1fb2b2525900e68de59ec12`. `origin/main` is
  `a6a7cd493eecd51e9e942215414a1822510cffa9` and is an ancestor of the
  candidate. The candidate contributes two release-ledger commits; annotated
  `13.4.33` peels to its head.
- DYEC candidate worktree:
  `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-prod-candidate-260911`,
  branch `prod-candidate-260911`, clean and synchronized with its remote at
  `eb4b018b4fb5c8e3cd2590bf589299079c6443ef`. `origin/main` is
  `cd41cd510c6ca60073006b3ed79f3251899db298` and is an ancestor of the
  candidate. Annotated `16.1.85` peels to release commit
  `fd1b583b73ccc22e3c3589357e4d3b09c8502d6a`; the branch has one later
  docs-only release-evidence commit.
- No open or closed pull request exists yet for either `prod-candidate-260911`
  branch.
- Neither local nor remote `prod-candidate-260812` exists in either repo.
- Highest matching fetched tags are DayOA `13.4.33` and DYEC `16.1.85`.
  Remote `13.4.34` and `16.1.86` are absent, so those are the inferred next
  releases. They must be rechecked immediately before tag creation.
- Both existing release tags are annotated and pushed, but neither currently
  has a GitHub Release object. The requested Release objects will be marked
  prerelease.
- Prior exact-tag DYEC release validation is recorded in the predecessor
  ledger as 681 passing tests. This train will rerun the release-focused gate
  after updating the DayOA pin and `dyec_builds.current`/`16.1.86` snapshot.
- Package-index publication, `twup`, AWS, headnode configuration, workflow
  execution, and destructive operations are out of scope.
- Merge policy: normal PR merge only after required checks pass. No admin
  merge, force merge, force push, or moved tag is authorized.

## Control ledger

| ID | Area/repo | Requirement | Status | Category | Approval gate | Owner | Evidence | Root cause | Terminal note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Cross-repo | Freeze branches, commits, tags, next versions, PR state, dirty state, and scope. | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 inventory above; fetch, status, ancestry, diff-check, tag, branch, and PR queries completed. |  | Baseline recorded before GitHub writes. |
| MERGE-DAYOA | DayOA | Open, validate, and normally merge `prod-candidate-260911` to `main`. | OPEN | feature_implementation | Gate 5 | orchestrator | Pending. |  |  |
| MERGE-DYEC | DYEC | Open, validate, and normally merge `prod-candidate-260911` to `main`. | OPEN | feature_implementation | Gate 5 | orchestrator | Pending. |  |  |
| PRERELEASE-DAYOA | DayOA | Create a GitHub prerelease page for annotated tag `13.4.33`. | OPEN | feature_implementation | Gate 5 | orchestrator | Pending. |  |  |
| PRERELEASE-DYEC | DYEC | Create a GitHub prerelease page for annotated tag `16.1.85`. | OPEN | feature_implementation | Gate 5 | orchestrator | Pending. |  |  |
| BRANCH-DAYOA | DayOA | Create and push `prod-candidate-260812` from exact updated `origin/main`. | OPEN | feature_implementation | Gate 1 | orchestrator | Pending. |  |  |
| BRANCH-DYEC | DYEC | Create and push `prod-candidate-260812` from exact updated `origin/main`. | OPEN | feature_implementation | Gate 1 | orchestrator | Pending. |  |  |
| RELEASE-DAYOA | DayOA | Create and push annotated tag `13.4.34` from the clean new candidate. | OPEN | feature_implementation | Gate 5 | orchestrator | Pending final availability recheck. |  |  |
| PIN-DYEC | DYEC | Move active/current DayOA pins to `13.4.34`, preserve prior snapshots, and copy updated `current` exactly to numeric snapshot `16.1.86`. | OPEN | config_or_startup_contract | Gate 2 | orchestrator | Pending. |  |  |
| RELEASE-DYEC | DYEC | Validate, commit, push, and create annotated tag `16.1.86`. | OPEN | feature_implementation | Gate 5 | orchestrator | Pending final availability recheck. |  |  |
| FINAL-001 | Cross-repo | Verify merged mains, clean synchronized candidates, prerelease pages, annotated tag objects, peeled commits, and terminal ledger state. | OPEN | contract_test | Gate 5 | orchestrator | Pending. |  |  |

## Final report

All rows terminal: no.

Objective complete: no.

Status counts: `SUCCESS=1`, `OPEN=10`, `IN_PROGRESS=0`, `BLOCKED=0`,
`FAIL=0`, `NO_LONGER_NEEDED=0`.
