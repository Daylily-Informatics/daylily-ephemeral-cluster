# DYEC 17.0.6 / DayOA 14.0.8 Release Ledger

Created: `2026-08-13T13:57:05Z`

## Objective

Publish immutable DYEC `17.0.6`, pinning active DayOA commands and the new
numeric snapshot to the headnode-proven DayOA `14.0.8` FastQC Java repair.
Preserve every older numeric catalog snapshot byte-for-byte, keep source and
packaged catalogs identical, and do not reconfigure the headnode while the
accepted `prod-cand-1703` controller is active.

## Gate 0 inventory freeze

- Worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-17.0.6-dayoa-14.0.8`.
- Branch: `codex/dyec-17.0.6-dayoa-14.0.8`, created clean from commit
  `84fed87758bdd54c328c73e359875b364b1cfb82`, the synchronized head of the
  DYEC `17.0.5` release branch including its release and launch ledgers.
- Primary-checkout boundary: the primary DYEC checkout contains unrelated
  untracked user artifacts. They are outside this isolated worktree and will
  not be edited, staged, removed, or committed.
- Release-ref boundary: local and remote branch `codex/dyec-17.0.6-dayoa-14.0.8`
  and local and remote tag `17.0.6` were absent before work began.
- DayOA input: annotated tag object
  `3178cd39e5a5aff60805c5e6544b72f10b08c8dc` peels to the exact headnode-tested
  commit `ef285dc06be4b57d4a388e8b791e70f4131cff92`.
- Catalog baseline: source and packaged catalogs are byte-identical. Active
  repository rows, `dyec_builds.current`, and immutable `17.0.5` pin DayOA
  `14.0.7`; the raw immutable `17.0.5` block SHA-256 is
  `d7ef1dabbb31130358ca3e99357bdb742a2c198e1452f076977d46acd47ab0b0`.
- Execution boundary: local catalog/test/build/release work only. No AWS,
  Slurm, workflow, analysis-root, lock, budget, or headnode configuration
  action is authorized by this release lane.

Gate 0 status: `SUCCESS`.

## Release validation evidence

- Source and packaged catalogs are byte-identical. Active repository rows and
  `dyec_builds.current` pin DayOA `14.0.8`; immutable `17.0.6` equals current.
  A semantic reconstruction of current from immutable `17.0.5` by replacing
  only `14.0.7` with `14.0.8` matched exactly. Immutable `17.0.5` remains on
  DayOA `14.0.7` with raw-block SHA-256
  `d7ef1dabbb31130358ca3e99357bdb742a2c198e1452f076977d46acd47ab0b0`.
- Resolved `inflection-bjuice-product-v0.2` for `17.0.6` has exact DayOA tag
  and validated version `14.0.8`, both required HIOMR2 targets, `hg38`,
  `-j 333 -T 0 -p --rerun-triggers mtime`, no `-k`, and final `-n` only in
  the dry-run command.
- Release-focused suite: `330 passed in 67.03s`.
- Complete suite: `2515 passed, 11 skipped, 2 warnings in 272.14s`; skips are
  the expected explicitly opted-in live staging tests.
- Ruff critical syntax/undefined-name selectors and `git diff --check` passed.
- Exact-version pre-tag build used `SETUPTOOLS_SCM_PRETEND_VERSION=17.0.6` with
  the existing `TWINE` build environment. `twine check` passed for wheel and
  sdist; both embed a catalog byte-identical to source, report version `17.0.6`,
  and contain no bytecode/cache files:
  - wheel SHA-256:
    `925aca1d6a72f698c49f047b6a1f1506d1e53ea27aae7191d30f32b23f9f75d9`
  - sdist SHA-256:
    `cffbb630edb4154a1d63b2f403c2c3d00312cdc6c180fc57adaa523de3cd818e`

## Control ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Evidence | Terminal Note |
|---|---|---|---|---|---|---|---|
| REL-001 | Baseline | Freeze exact DYEC base, DayOA tag provenance, catalog parity, historical hash, and release-ref availability | SUCCESS | contract_test | Gate 0 | Gate 0 inventory above | Isolated release scope is frozen. |
| CAT-001 | Active pin | Move active repository rows and `dyec_builds.current` from DayOA 14.0.7 to exact 14.0.8 | SUCCESS | config_or_startup_contract | Gate 2 | Structural assertions and resolved CLI command inspection | Active/current commands resolve exact DayOA 14.0.8. |
| CAT-002 | Snapshot | Add immutable `17.0.6` equal to updated current and preserve every older numeric block | SUCCESS | feature_implementation | Gate 2 | Exact-transform assertion and historical raw-block hash tests | Current equals 17.0.6; 17.0.5 remains frozen. |
| TEST-001 | Validation | Prove source/package parity, catalog contracts, full tests, lint, and exact-version artifacts | SUCCESS | contract_test | Gate 5 | 330 focused and 2515 complete tests; Ruff; diff check; wheel/sdist checks above | All pre-release validation gates passed. |
| REL-002 | Release | Commit, annotate non-v tag 17.0.6, push branch and tag, and verify remote peeled refs | IN_PROGRESS | release | Gate 5 | Pending |  |
| SAFE-001 | Headnode | Defer shared headnode configuration while the accepted controller is active | SUCCESS | legitimate_safety_handling | Gate 5 | Controller and queue remain active; prior source audit found configure mutates shared checkout/environment/sbatch | No headnode configure during this release lane. |

## Acceptance boundary

The objective is complete only when every row is terminal, source and packaged
catalogs match, current equals immutable `17.0.6`, all older numeric blocks
remain unchanged, validation passes, and the annotated remote tag peels to the
clean release commit.

## Final report

All rows terminal: `no`

Objective complete: `no`

Current counts: `SUCCESS=5`, `IN_PROGRESS=1`, `OPEN=0`, `FAIL=0`, `BLOCKED=0`.
