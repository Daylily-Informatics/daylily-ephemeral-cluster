# Take8 DayOA / DYEC double-release ledger

Created: 2026-07-28T11:25:42Z

## Scope

The controlling request is to publish the complete DayOA source used for the
active Take8 lane, then make two consecutive DYEC releases: first pin the
DayOA catalog to that release, then advance DYEC's own bootstrap/self-pin.

## Gate 0 — baseline

- Take8 is a detached DayOA checkout at `f8073803646d897601d2c63272d4092cc92ab926`
  and annotated tag `13.0.68`; it has no modified tracked source files. Its
  untracked files are runtime manifests, profile-refresh markers, and generated
  workflow artifacts, not DayOA source code.
- DayOA branch `codex/hiomr2-full-kitchensink-repair` is clean at
  `a65833bde94130a6fbfa164a5d17b21d1a0c5429`. It contains all Take8 source code
  plus the post-launch ledger update. Annotated tag `13.0.69` targets that
  commit and is pushed to `origin`.
- DYEC branch `codex/hiomr2-catalog-repair` begins at `4edb0b97`; its tracked
  tree is clean. User-owned untracked history/artifact directories are excluded
  from staging.
- The current source and packaged command catalogs are byte-identical, use
  DayOA `13.0.61` as `default_ref`/command `git_tag`, and contain 56 matching
  pin occurrences across the two payload copies. The current source and
  packaged DYEC self-pins are both `15.0.13`.
- The next available numeric DYEC tags are `15.0.16` and `15.0.17`; both must
  be annotated and never moved.

| ID | Objective | Status | Evidence / terminal note |
| --- | --- | --- | --- |
| DAYOA-001 | Push and annotate the complete DayOA source release `13.0.69`. | COMPLETE | `13.0.69` is an annotated tag on `a65833bd`, pushed to `origin`. |
| DYEC-001 | Pin source and packaged command catalogs to DayOA `13.0.69`; commit, push, annotate, and push DYEC `15.0.16`. | COMPLETE | Commit `56ee1a40066f445f4ce658539e0df14c5bb78e42` is pushed on `origin/codex/hiomr2-catalog-repair`; annotated tag object `e4bbc1f00fee98fd86ce8cce0a401e463bef5f66` is pushed as `15.0.16`. Focused catalog/CLI validation: 232 passed. |
| DYEC-002 | Advance source and packaged DYEC self-pins to `15.0.17`; commit, push, annotate, and push the final release. | COMPLETE | Commit `d0b3d1fb7e754e6cd0a30deff0b3b96693f1fdd7` is pushed on `origin/codex/hiomr2-catalog-repair`; annotated tag object `262411afe9b89784d209bdbd3b61259e6148c4a4` is pushed as `15.0.17`. Focused fork/catalog/CLI validation: 236 passed. |
| TAKE8-001 | After Take8 overall RC 0, ensure analytical Inflection packaging completes. | PENDING | The active `dy-r` invocation already includes `produce_sentdhiomr2_inflection_analytical_package`; it is dependency-gated behind the kitchen-sink outputs. Launch a separate package controller only if the completed DAG did not produce it. |
| TAKE8-002 | After the controller is terminal, DRA-export Take8 regardless of package outcome, preserving FSx. | PENDING | Destination is the established `s3://lsmc-ssf-sequencing-data/derived/for-mike-k/preval-hiomr2/take8/` prefix. Use DYEC export without `--delete-data-in-file-system` and do not run cleanup; retain a successful immutable receipt and verify the source remains on FSx. |
