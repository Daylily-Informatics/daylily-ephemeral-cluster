# DYEC 18.0.43 / DayOA 15.0.24 current-catalog pin release ledger

Created: 2026-08-18T13:02:37Z
Controlling request: create a new DYEC branch from the maximum DYEC release, pin DYEC and every `current` command-catalog command to the maximum published DayOA release, then commit, push, annotate a new DYEC version, and push the tag.

## Gate 0 baseline

- Authoritative DYEC remote maximum tag: annotated `18.0.42`, peeling to `fe95691edf330675d761e79df199110e308c40cf`.
- Authoritative DayOA remote maximum tag: `15.0.24`; no later `15.*` release tag was present at inventory time.
- Clean release worktree: `/Users/jmajor/.codex-worktrees/dyec-release-18043-dayoa-15024` on `codex/release-18.0.43-dayoa-15.0.24`, created from `18.0.42` at `fe95691edf330675d761e79df199110e308c40cf`.
- The shared DYEC and DayOA checkouts are dirty/user-owned and are intentionally untouched.
- Both canonical and packaged catalog payloads exist. At baseline, `current` already names DayOA `15.0.24`; this release must create immutable `18.0.43` snapshot evidence and preserve exact `15.0.24` pins for all current commands.
- No live workflow, AWS, DRA, FSx, export, or Slurm operation is part of this release work.

## Control ledger

| ID | Area | Requirement | Status | Category | Gate | Evidence / terminal note |
|---|---|---|---|---|---|---|
| REL-001 | Provenance | Prove maximum published DYEC and DayOA release tags | SUCCESS | contract_test | Gate 0 | Remote `ls-remote --tags --refs` shows DYEC max `18.0.42` and DayOA max `15.0.24`. |
| REL-002 | Worktree | Create clean feature branch from maximum DYEC tag | SUCCESS | feature_implementation | Gate 0 | `codex/release-18.0.43-dayoa-15.0.24` is clean and based on `18.0.42` peeled commit `fe95691…`. |
| REL-003 | Catalog | Make `current` and immutable `18.0.43` catalog snapshot pin every command to DayOA `15.0.24` | SUCCESS | feature_implementation | Gate 1 | Appended immutable `18.0.43` snapshot by exact mechanical copy of `current` in both canonical and packaged catalogs; historical entries were not changed. |
| REL-004 | Verification | Verify canonical/payload parity and every current/snapshot command pin | SUCCESS | contract_test | Gate 5 | Semantic check passed: source and payload `current` each equal `18.0.43`; default ref, top-level 30 commands, `current` 30 commands, and `18.0.43` 30 commands each resolve only to `15.0.24`. `dyec --json catalog show ... --dyec-version 18.0.43` resolved the Bjuice custom-matrix command to `git_tag=15.0.24`; `git diff --check` passed. |
| REL-005 | Release | Commit, push branch, create annotated `18.0.43`, verify, and push tag | IN_PROGRESS | feature_implementation | Gate 5 | Clean release commit and annotated tag pending. |

## Completion

All rows terminal: no
Objective complete: no
