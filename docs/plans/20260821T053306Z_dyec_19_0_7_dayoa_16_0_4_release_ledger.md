# DYEC 19.0.7 / DayOA 16.0.4 release ledger

Created: 2026-08-21T05:33:06Z

## Scope

Cut DYEC `19.0.7` from the LSMC fork's `19.0.6` release-candidate branch,
carry the already-pushed Bundle 1b Bjuice + Inflection catalog feature, and
retarget the active DYEC and active command-catalog DayOA pin from `16.0.3`
to annotated DayOA `16.0.4`. Historical numeric catalog snapshots remain
unchanged.

## Gate 0 inventory

| Item | Evidence |
| --- | --- |
| Fork / remote | `lsmc-bio/daylily-ephemeral-cluster` / `origin` |
| Private release worktree | `/Users/jmajor/.codex-worktrees/dyec-release-19.0.7-dayoa-16.0.4` |
| Release branch | `codex/release-19.0.7-dayoa-16.0.4` |
| DYEC base | Annotated `19.0.6`, tag object `745bb45fe4ada4f35f9df53c6c257c24a92648b4`, peeled commit `71094ee138430175e8ffcc96c0a4522b454fa868` |
| Feature provenance | `3f390f77b4dd5aa2c2104c33a70764901c1dbecf`, already pushed as `codex/bundle1b-bjuice-inflection-dry-20260821` |
| Carried feature commit | `2972653f` (`cherry-pick -x` provenance retained) |
| DayOA source release | Annotated `16.0.4`, peeled commit `b464bc0e4bc18361e4cf7119b2bf263321a98ab3` |
| Target DayOA pin | `16.0.4` in the active repository pin and active catalog view only |
| Remote release target | `19.0.7` did not exist before this release branch was created |

## Execution record

| Step | Status | Evidence |
| --- | --- | --- |
| Feature branch state | complete | Branch was clean and its remote head matched `3f390f77b4dd5aa2c2104c33a70764901c1dbecf`. |
| Release worktree | complete | Created directly from the LSMC fork's annotated 19.0.6 commit `71094ee1`. |
| Feature integration | complete | Cherry-pick completed cleanly as `2972653f`. |
| DayOA pin and numeric catalog update | complete | Retargeted only the active repository entries and new immutable `19.0.7` snapshot to `16.0.4`; preserved `19.0.6` and every older numeric snapshot unchanged. |
| Release commit, push, and annotated tag | complete | This exact clean release commit is tagged `19.0.7` and both refs are pushed to the LSMC `origin`; the final receipt records the remote tag object and peeled commit. |

## Verification boundary

At the user's explicit instruction, no pytest invocation, `git diff --check`,
or other test command will be run for this release. This ledger records
repository provenance and push/tag verification only; it makes no workflow,
cluster, export, or live-validation claim.
