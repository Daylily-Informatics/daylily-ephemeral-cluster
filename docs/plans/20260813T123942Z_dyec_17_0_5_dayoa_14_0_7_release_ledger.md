# DYEC 17.0.5 / DayOA 14.0.7 Release Ledger

Created: `2026-08-13T12:39:42Z`

## Objective

Publish a new immutable DYEC `17.0.5` catalog release from exact annotated
DYEC `17.0.4`, pinning active DayOA commands and the new `17.0.5` snapshot to
the exact annotated DayOA `14.0.7` repair release. Preserve all older numeric
catalog snapshots byte-for-byte, keep source and packaged catalogs identical,
and do not touch the active headnode workflow.

## Gate 0 inventory freeze

- Worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-17.0.5-dayoa-14.0.7`.
- Branch: `codex/dyec-17.0.5-dayoa-14.0.7`, created clean from annotated tag
  `17.0.4`, peeled commit `2ef2c50353e1f05f37375da1097b6f851f035d1f`.
- Main checkout boundary: the primary checkout contains extensive pre-existing
  untracked user artifacts. None are in this worktree and none will be edited,
  staged, removed, or committed.
- Release refs: remote branch and tag `17.0.5` were absent before edits.
- DayOA input: local and remote annotated tag object
  `e0ac5e41a368b2a052d2255273916c67fac1e0a5` peels to repair commit
  `4e0029753244606e809cc5c431c06431c3d8bc6e`.
- Catalog baseline: source and packaged catalogs are byte-identical; active
  repository rows, `dyec_builds.current`, and immutable `17.0.4` pin DayOA
  `14.0.6`; every prior numeric snapshot is historical and immutable.
- Activated baseline: `dyec --json version` reports exact `17.0.4`; focused
  catalog/repository/package suite passed `82/82` in 30.64 seconds.
- Execution boundary: source, tests, build, git branch, commit, and tag push
  only. No headnode, AWS, Slurm, controller, analysis root, or lock is touched.

Gate 0 status: `SUCCESS`.

## Release validation evidence

- Active repository rows and `dyec_builds.current` now pin exact DayOA
  `14.0.7`; immutable `dyec_builds.17.0.5` is structurally equal to current.
  The resolved `inflection-bjuice-product-v0.2` command has both required
  HIOMR2 targets, `hg38`, `-j 333 -T 0 -p`, no `-k`, and only the dry command
  adds final `-n`.
- Source and packaged catalogs are byte-identical. Immutable `17.0.4` retains
  DayOA `14.0.6`, 29 resolved commands, and raw-block SHA-256
  `ed70d79c7e35d65dee4625ea9e039402aa5a3bd84ab520534b418a83b57a6d77`.
  A semantic exact-transform check independently reconstructed the candidate
  from `17.0.4` by changing only active/current `14.0.6` values to `14.0.7`
  and appending `17.0.5`; it matched exactly, and every prior numeric snapshot
  remained equal to the baseline object.
- Focused catalog/repository/package suite: `364 passed in 64.67s`.
- Complete suite: `2515 passed, 11 skipped, 2 warnings in 136.40s`. The
  skipped tests are the expected explicitly opted-in live staging tests.
- Ruff critical-error/import selectors on all changed Python tests passed.
  A whole-file `ruff format --check` identified four pre-existing formatting
  regions outside this release's one-line test updates, so those unrelated
  files were not mechanically reformatted. `git diff --check` passed.
- Exact-version pre-tag build used
  `SETUPTOOLS_SCM_PRETEND_VERSION=17.0.5` because the activated `DAY-EC`
  environment does not include the optional `build` frontend. The existing
  `TWINE` environment supplied `build 1.5.0`; no environment or repository
  dependency was changed. `twine check` passed for both artifacts, wheel
  metadata reports `Version: 17.0.5`, the embedded catalog is byte-identical
  to source, and neither artifact contains bytecode/cache files:
  - wheel SHA-256:
    `547f0d5551af73a100c091acbd230e58bd0ad58c1206e97234f74ed937c01723`
  - sdist SHA-256:
    `9e2b8a98b96b1b5dac46c257c83a967b9971b3f02128f2fcad2f346ff2b60f76`
- `dyec headnode configure` is not documented or implemented as safe during
  an active controller. It resets/cleans the shared headnode DYEC checkout,
  prunes/updates the shared `DAY-EC` environment, reinstalls DYEC and tools,
  and rewrites the shared `sbatch`; there is no controller/tmux/analysis-lock
  guard. Recommendation: defer configuration until the active `17.0.4`
  controller is terminal and its status/lock cleanup is verified. This audit
  was source-only; the headnode and live run were not touched.
- Release commit `01d56f9c4f9897f1ba9678e5796f800a2334f572` was pushed to
  `origin/codex/dyec-17.0.5-dayoa-14.0.7`. Annotated tag object
  `cc4d3b787e573a6d0f39228e1051b344610a371a` has message
  `Release DYEC 17.0.5 with DayOA 14.0.7`, was pushed as `17.0.5`, and its
  remote peeled ref is the exact release commit. No existing tag was moved.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | Baseline | Freeze exact DYEC and DayOA tag objects, branch/worktree state, catalog parity, and focused tests | SUCCESS | contract_test | Gate 0 | dyec_1705_release | Gate 0 inventory above |  | Isolated release worktree is clean and exact. |
| CAT-001 | Active pin | Move active repository defaults and current command pins from DayOA 14.0.6 to exact 14.0.7 | SUCCESS | config_or_startup_contract | Gate 2 | dyec_1705_release | Structural catalog assertions plus resolved CLI command inspection |  | Active/current pins resolve exact annotated DayOA 14.0.7. |
| CAT-002 | Immutable snapshot | Add exact numeric snapshot 17.0.5 equal to updated current while preserving every older numeric block | SUCCESS | feature_implementation | Gate 2 | dyec_1705_release | Current/snapshot equality, historical hash guard, and resolved command counts |  | 17.0.5 is immutable current copy; 17.0.4 remains frozen on 14.0.6. |
| PARITY-001 | Package/test contract | Keep source and packaged catalogs byte-identical and update current-release tests without weakening history guards | SUCCESS | contract_test | Gate 5 | dyec_1705_release | Catalog byte comparison; focused 364/364; complete 2515 passed, 11 skipped |  | Package/source parity and history guards pass. |
| BUILD-001 | Version/build | Prove exact 17.0.5 metadata and packaged catalog in clean wheel/sdist artifacts | SUCCESS | contract_test | Gate 5 | dyec_1705_release | Wheel/sdist hashes, metadata/catalog inspection, and twine checks above |  | Exact 17.0.5 release artifacts validate. |
| SAFE-001 | Headnode configure audit | Determine whether supported headnode configure is explicitly safe during an active 17.0.4 controller without touching it | SUCCESS | legitimate_safety_handling | Gate 5 | dyec_1705_release | Docs/source inspection; no live access |  | Not explicitly safe; defer until controller terminal and cleanup verified. |
| REL-002 | Release | Commit, create annotated non-v 17.0.5 tag, verify clean refs, and push branch and tag | SUCCESS | feature_implementation | Gate 5 | dyec_1705_release | Release commit, annotated tag object, and remote refs above |  | Exact release commit and annotated tag are present on origin. |

## Acceptance boundary

The objective is complete only when every row is terminal, source and packaged
catalogs match, current equals immutable `17.0.5`, historical snapshots remain
unchanged, tests/build checks pass, and the clean release commit, annotated tag,
branch, and tag are verified on `origin`.

## Final report

All rows terminal: `yes`

Objective complete: `yes`

Current counts: `SUCCESS=7`, `IN_PROGRESS=0`, `OPEN=0`, `FAIL=0`, `BLOCKED=0`.
