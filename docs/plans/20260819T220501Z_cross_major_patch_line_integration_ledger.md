# DYEC patch-line to major-line integration ledger

## Objective

Preserve all released DYEC `18.0.*` work on `max-pre-major-breaking`, integrate it into a `new-break-ver` 19-series release, pin active DYEC and command-catalog DayOA references to the newly published maximum DayOA `16.0.*`, and publish an annotated DYEC `19.0.*` tag without discarding user work in the existing checkout.

Cross-repository ledger: `/Users/jmajor/.codex-worktrees/dayoa-new-break-ver/docs/plans/20260819T220501Z_cross_major_patch_line_integration_ledger.md`

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
| DYEC-002 | patch line | Commit and push `max-pre-major-breaking`. | SUCCESS | `origin/max-pre-major-breaking` was created without force at `d1bfa5b63a7b2347b3865c2c0ade6e943102e08d`; this ledger closeout is fast-forwarded afterward. No released 18-series behavior needed merging. |
| DYEC-003 | major line | Resolve the absent-19-base discrepancy from repository evidence and create `new-break-ver` without overwriting any ref. | SUCCESS | No 19-series release existed, while the prior open Betelgeuse design explicitly named first release `19.0.0` and required the DayOA 16 `dy-r` boundary. `new-break-ver` was created at `18.0.59` and merged with the complete published pre-major branch in `9c740d0e`. |
| DYEC-004 | pins/catalog | Pin active DYEC DayOA references and command-catalog `current` entries to the new maximum DayOA `16.0.*`; preserve historical numeric snapshots and canonical/package equality. | SUCCESS | Both byte-identical catalogs now use DayOA `16.0.1`: default ref, all 30 active rows, `current.dayoa_git_tags`, and all 31 current rows. Direct active/current command fields contain 122 `dy-r` references and zero `bin/day_run` references. `19.0.0 == current`; all 46 older numeric snapshots retain baseline semantic SHA-256 `d3421dfc23e3fafd17656c1f94952290140374726475eb937b77dcee08d6255b`. Historical tested commands remain unchanged. Contract-test sources were updated, but no test command was run per user instruction. |
| DYEC-005 | release | Commit, push, create the next valid annotated `19.0.*` tag, and verify the remote peel. | SUCCESS | `origin/new-break-ver` was created without force. Annotated tag object `414c89bdbae5d4f2546f89c79e3797bf557da105` for `19.0.0` peels locally and remotely to clean release commit `ece9195fd5da90731d38a89ea15131fa66e35293`. |
| DYEC-006 | local install | Bring the primary checkout forward without losing untracked artifacts, activate `DAY-EC`, and verify `dyec --version`. | SUCCESS | Preserved branch `codex/bjuice-validation-seqqc-20260819` at `a4e41502917ea39adec1fc976129982dfbc716e0` and all listed untracked artifacts, then detached the primary checkout at immutable tag `19.0.0`. `source ./activate` reported `DAY-EC`; both exact `dyec version` and `dyec --version` returned `Daylily Ephemeral Cluster 19.0.0` from `/Users/jmajor/miniconda3/envs/DAY-EC/bin/dyec`. |

## Terminal gate

All DYEC rows are terminal. Both requested remote branches exist, annotated tag `19.0.0` peels to the clean release commit, active/default/current catalog surfaces pin DayOA `16.0.1`, and the primary `DAY-EC` CLI reports `19.0.0`. This post-tag ledger closeout changes documentation only and does not move the immutable release tag.
