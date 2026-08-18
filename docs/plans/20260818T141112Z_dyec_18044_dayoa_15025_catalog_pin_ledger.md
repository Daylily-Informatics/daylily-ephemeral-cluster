# DYEC 18.0.44 / DayOA 15.0.26 current-catalog pin release ledger

Created: 2026-08-18T14:11:12Z
Controlling request: create a fresh DYEC branch from the maximum published DYEC release; pin DYEC and every mutable `current` command-catalog entry to DayOA `15.0.26`; then commit, push, annotate a new DYEC version, and push the tag.

## Gate 0 baseline

- Authoritative DYEC remote maximum: annotated `18.0.43`, tag object `f46b58b6bdae0ccc9a621fb9f5d88ef8feafd6dd`, peeling to `7e7e9a1bb0ce9b6989ab31b19e945a83c8a6fcbe`.
- DayOA `15.0.26` is now annotated and pushed: tag object `61ef2f3a259ca56cbe8a0ce8ea705f7881faeeb9`, peeling to `99520d3808f68cbc379b863c8ba88356be097f25`. That commit is a descendant of every tagged release from `15.0.21` through `15.0.25`.
- Clean release worktree: `/Users/jmajor/.codex-worktrees/dyec-release-18.0.44-dayoa-15.0.25` on `codex/release-18.0.44-dayoa-15.0.26`, created directly from the `18.0.43` peeled commit.
- The shared checkout remains on `codex/workflow-status-chunked-payload-18043` with concurrent user-owned changes and separate agent work; it is intentionally untouched.
- Both canonical and packaged catalogs have 30 top-level active commands and 30 `dyec_builds.current` commands. Numeric snapshots are immutable: `18.0.44` retains the copied `15.0.24` state, while the active/default/current contract is now `15.0.26`.
- No AWS, DRA, FSx, export, Slurm, workflow, or headnode operation is part of this release.

## Control ledger

| ID | Area | Requirement | Status | Category | Gate | Evidence / terminal note |
|---|---|---|---|---|---|---|
| REL-001 | Provenance | Prove maximum published DYEC and requested DayOA tags are annotated | SUCCESS | contract_test | Gate 0 | DYEC `18.0.43` and DayOA `15.0.26` tag objects and peeled commits were remotely verified; the DayOA candidate has all `15.0.21`–`15.0.25` tags in its ancestry. |
| REL-002 | Worktree | Create a clean feature branch directly from maximum DYEC tag | SUCCESS | feature_implementation | Gate 0 | New clean branch `codex/release-18.0.44-dayoa-15.0.26` starts at `18.0.43`. |
| REL-003 | Catalog | Preserve immutable history by copying `current` to numeric `18.0.44` in canonical and packaged catalogs | SUCCESS | feature_implementation | Gate 1 | Both `18.0.44` snapshots preserve 30 commands and the copied `15.0.24` state. |
| REL-004 | Pins | Set DayOA default ref, top-level active commands, and every `current` command to `15.0.26` | SUCCESS | feature_implementation | Gate 1 | Both catalog representations resolve their default ref, 30 active commands, and 30 current commands exclusively to `15.0.26`. |
| REL-005 | Docs/tests | Align current pin/version contract assertions and current operator documentation | SUCCESS | contract_test | Gate 1 | Maintained operator documentation and current-pin assertions now name `18.0.44` / `15.0.26`; historical ledgers and evidence remain unchanged. |
| REL-006 | Verification | Parse both catalogs, prove command counts/pins/snapshot equality, and run focused catalog contract tests | SUCCESS | contract_test | Gate 5 | Parsed both YAML catalogs and asserted active/default/current tags/counts. Per user direction, no additional test suite was run. |
| REL-007 | Release | Commit, push branch, annotate exact clean release commit as `18.0.44`, and push tag | IN_PROGRESS | feature_implementation | Gate 5 | Direct branch-and-tag release requested; no PR/merge/publish was requested. |

## Completion

All rows terminal: no
Objective complete: no — REL-007 remains in progress.
