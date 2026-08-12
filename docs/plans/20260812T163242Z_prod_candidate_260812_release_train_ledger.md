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
| MERGE-DAYOA | DayOA | Open, validate, and normally merge `prod-candidate-260911` to `main`. | SUCCESS | feature_implementation | Gate 5 | orchestrator | PR [#105](https://github.com/lsmc-bio/daylily-omics-analysis/pull/105); all three CodeQL checks passed; normal merge commit `f799ba3d5a7bc67bbed112ef4c3f77ca2f9da41a`. |  | Merged without admin override. |
| MERGE-DYEC | DYEC | Open, validate, and normally merge `prod-candidate-260911` to `main`. | SUCCESS | feature_implementation | Gate 5 | orchestrator | PR [#96](https://github.com/lsmc-bio/daylily-ephemeral-cluster/pull/96); GitHub reported no checks and a clean merge; normal merge commit `b7c1b056feb3ee1b24c0daa338d5f11ec015944d`. |  | Merged without admin override. |
| PRERELEASE-DAYOA | DayOA | Create a GitHub prerelease page for annotated tag `13.4.33`. | SUCCESS | feature_implementation | Gate 5 | orchestrator | [DayOA 13.4.33 prerelease](https://github.com/lsmc-bio/daylily-omics-analysis/releases/tag/13.4.33), verified `isPrerelease=true`. |  | Published from the existing immutable tag. |
| PRERELEASE-DYEC | DYEC | Create a GitHub prerelease page for annotated tag `16.1.85`. | SUCCESS | feature_implementation | Gate 5 | orchestrator | [DYEC 16.1.85 prerelease](https://github.com/lsmc-bio/daylily-ephemeral-cluster/releases/tag/16.1.85), verified `isPrerelease=true`. |  | Published from the existing immutable tag. |
| BRANCH-DAYOA | DayOA | Create and push `prod-candidate-260812` from exact updated `origin/main`. | SUCCESS | feature_implementation | Gate 1 | orchestrator | Branch and `origin/prod-candidate-260812` created at `f799ba3d5a7bc67bbed112ef4c3f77ca2f9da41a`; worktree `/Users/jmajor/projects/lsmc/.codex-worktrees/dayoa-prod-candidate-260812`. |  | Exact updated main branch point. |
| BRANCH-DYEC | DYEC | Create and push `prod-candidate-260812` from exact updated `origin/main`. | SUCCESS | feature_implementation | Gate 1 | orchestrator | Branch and `origin/prod-candidate-260812` created at `b7c1b056feb3ee1b24c0daa338d5f11ec015944d`; worktree `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-prod-candidate-260812`. |  | Exact updated main branch point. |
| RELEASE-DAYOA | DayOA | Create and push annotated tag `13.4.34` from the clean new candidate. | SUCCESS | feature_implementation | Gate 5 | orchestrator | Remote tag object `9b1084ed3cd5b74fdf1b3ca3d8f26e91c823bda1` peels to candidate commit `f799ba3d5a7bc67bbed112ef4c3f77ca2f9da41a`; local type is `tag`. |  | Availability was rechecked immediately before creation and push. |
| PIN-DYEC | DYEC | Move active/current DayOA pins to `13.4.34`, preserve prior snapshots, and copy updated `current` exactly to numeric snapshot `16.1.86`. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Source and packaged catalogs are byte-identical; structural comparison preserved `16.1.81`, `16.1.82`, and `16.1.85`; `current == 16.1.86`; CLI probes returned 29 commands on DayOA `13.4.34` for `current`/`16.1.86`, 29 on `13.4.33` for `16.1.85`, and 9 on `13.4.31` for `16.1.82`; release-focused suite passed 681 tests; targeted Ruff, byte-compilation, and diff checks passed. |  | Active default and new release snapshot updated without changing historical pins. |
| RELEASE-DYEC | DYEC | Validate, commit, push, and create annotated tag `16.1.86`. | IN_PROGRESS | feature_implementation | Gate 5 | orchestrator | Release inputs validated; commit, final tag-availability recheck, annotated tag, push, and remote verification remain. |  |  |
| FINAL-001 | Cross-repo | Verify merged mains, clean synchronized candidates, prerelease pages, annotated tag objects, peeled commits, and terminal ledger state. | OPEN | contract_test | Gate 5 | orchestrator | Pending. |  |  |

## Final report

All rows terminal: no.

Objective complete: no.

Status counts: `SUCCESS=9`, `OPEN=1`, `IN_PROGRESS=1`, `BLOCKED=0`,
`FAIL=0`, `NO_LONGER_NEEDED=0`.
