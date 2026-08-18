# DYEC 18.0.49 Release Reconciliation Ledger

Controlling request: publish only releaseable DayOA/DYEC work, reconciled onto
the current immutable remote release tags, without running repository tests.

## Gate 0 baseline

- DayOA remote maximum: annotated tag `15.0.27`, peeled commit
  `99520d3808f68cbc379b863c8ba88356be097f25`.
- DYEC remote maximum: annotated tag `18.0.48`, peeled commit
  `c544af730e0c2b335be90617945b8619d098e9b2`.
- DayOA's four local TIDDIT source/test edits are already present in `15.0.27`;
  its untracked `tmp/` directory is not release scope and is left untouched.
- DYEC's primary checkout has unrelated deleted/untracked paths. This release
  uses the clean worktree `/Users/jmajor/.codex-worktrees/dyec-release-18.0.49`
  based exactly on `18.0.48`.
- User explicitly directed that no repository test suite be run for this
  release-only reconciliation.

## Control ledger

| ID | Repo | Requirement | Status | Category | Gate | Evidence / terminal note |
|---|---|---|---|---|---|---|
| G0 | Both | Freeze remote tags and classify local changes. | SUCCESS | plan_amendment | Gate 0 | `git ls-remote --tags` found unused `15.0.28`/`18.0.49`; exact DayOA TIDDIT markers already exist in `15.0.27`. |
| DAYOA-01 | DayOA | Publish a new DayOA tag only if source differs from `15.0.27`. | NO_LONGER_NEEDED | historical_docs_only | Gate 0 | The pending local patch duplicates released `15.0.27`; no redundant `15.0.28` tag is created. |
| DYEC-01 | DYEC | Reconcile releaseable post-`18.0.47` guidance and execution evidence onto `18.0.48`. | SUCCESS | active_product_contract | Gate 0 | Seven local commits were cherry-picked onto this clean release branch with `-x`; unrelated primary-worktree paths were excluded. |
| DYEC-02 | DYEC | Materialize immutable `18.0.49` catalog snapshot while retaining `current` pinned to DayOA `15.0.27`. | IN_PROGRESS | active_product_contract | Gate 0 | Source and packaged catalog copies will receive the same byte-preserving current-view snapshot. |
| DYEC-03 | DYEC | Commit, push, annotated-tag, and push `18.0.49`. | OPEN | active_product_contract | Gate 5 | No GitHub Release object, package build, or repository tests are in scope. |
| TEST-01 | Both | Run repository tests. | NO_LONGER_NEEDED | contract_test | Gate 5 | Explicitly omitted at the user's direction for this release-only request. |

