# DYEC patch-line to major-line integration ledger

## Objective

Preserve all released DYEC `18.0.*` work on `max-pre-major-breaking`, integrate it into a `new-break-ver` 19-series release, pin active DYEC and command-catalog DayOA references to the newly published maximum DayOA `16.0.*`, and publish an annotated DYEC `19.0.*` tag without discarding user work in the existing checkout.

Cross-repository ledger: `/Users/jmajor/.codex-worktrees/dayoa-max-pre-major-breaking/docs/plans/20260819T220501Z_cross_major_patch_line_integration_ledger.md`

## Gate 0 inventory

| Item | Evidence |
|---|---|
| Existing checkout | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` is on `codex/bjuice-validation-seqqc-20260819` with untracked user artifacts; release work is isolated in a new worktree until the requested final fast-forward. |
| Maximum remote `18.0.*` | Annotated tag `18.0.59`, tag object `b5dacde291c50e972d960a3a21929cfdb11e53ea`, peeled commit `a4b1defc197798fa2125398c9e547a2a4caaaf60`. |
| Patch-line ancestry | Every remote tag `18.0.0` through `18.0.59` is an ancestor of `18.0.59`; no released 18-series work is missing. |
| Requested branches | Neither `max-pre-major-breaking` nor `new-break-ver` existed locally or on `origin` at inventory time. |
| Remote `19.0.*` state | No `19.0.*` tag exists on `origin`. The older local `codex/betelgeuse-v1-dyec-19` name points to historical `10.3.34`, and `codex/betelgeuse-v1-dyec-19-current` points to the `18.0.58` commit; neither is a released 19-series base. |
| Existing 19-series design | `docs/plans/20260819T113034Z_betelgeuse_v1_bjuice_rc0_ledger.md` records an open, unreleased design for first tag `19.0.0`, including DayOA `16.0.0` and the `dy-r` boundary. The release implementation must inspect this contract before treating `19.0.0` as the next tag. |
| Verification boundary | Per explicit user instruction, no repository test suite will run. Verification is limited to ref/ancestry checks, catalog/config inspection, canonical/package equality, clean-state checks, `git diff --check`, requested CLI version verification, annotated-tag verification, and remote peeled-commit verification. |

## Execution rows

| ID | Scope | Action | Status | Evidence / terminal condition |
|---|---|---|---|---|
| DYEC-001 | patch line | Create `max-pre-major-breaking` at `18.0.59`. | SUCCESS | Worktree created at `/Users/jmajor/.codex-worktrees/dyec-max-pre-major-breaking`, starting at `a4b1defc197798fa2125398c9e547a2a4caaaf60`. |
| DYEC-002 | patch line | Commit and push `max-pre-major-breaking`. | OPEN | Only the Gate 0 ledger is expected beyond the complete 18-series history. |
| DYEC-003 | major line | Resolve the absent-19-base discrepancy from repository evidence and create `new-break-ver` without overwriting any ref. | OPEN | If the open first-19 design is compatible, create `19.0.0` from the complete 18-series integration; otherwise stop. |
| DYEC-004 | pins/catalog | Pin active DYEC DayOA references and command-catalog `current` entries to the new maximum DayOA `16.0.*`; preserve historical numeric snapshots and canonical/package equality. | OPEN | Exact new DayOA tag is supplied by the sibling release ledger. |
| DYEC-005 | release | Commit, push, create the next valid annotated `19.0.*` tag, and verify the remote peel. | OPEN | Expected candidate is `19.0.0` only because no 19-series tag currently exists. |
| DYEC-006 | local install | Bring the primary checkout forward without losing untracked artifacts, activate `DAY-EC`, and verify `dyec --version`. | OPEN | Must return the exact newly published DYEC tag. |

## Terminal gate

This ledger is complete only when every execution row is terminal, both requested remote branches exist, the new annotated `19.0.*` tag peels to the clean `new-break-ver` release commit, the active catalog pins the new DayOA tag, and the primary `DAY-EC` CLI reports the new DYEC version.
