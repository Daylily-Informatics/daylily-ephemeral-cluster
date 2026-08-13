# DYEC 17.0.2 HIOMR2 Prerelease Execution Ledger

Created: 2026-08-13T04:05:22Z

Linked DayOA ledger: `daylily-omics-analysis/docs/plans/20260813T040522Z_hiomr2_14_0_3_prerelease_ledger.md`

## Scope and release boundary

After DayOA 14.0.3 is released, implement command catalog schema v6 with one-hop typed aliases, resolve the HIOMR2 base and Bjuice commands, update `current` to DayOA 14.0.3, create the exact immutable `17.0.2` snapshot, and release DYEC 17.0.2 from `prod-candidate-260812`. Do not merge `main`, publish a package-index artifact, or run AWS/headnode workflows.

## Gate 0: inventory freeze

- Repository: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-prod-candidate-260812`
- Branch and upstream: `prod-candidate-260812...origin/prod-candidate-260812`
- Baseline commit: `759b50e13df1dee04ca0164a694a1f46bbd586fe`
- Worktree at inventory: clean; no pre-existing modified or untracked files.
- Requested tag check: local and remote `17.0.2` refs absent; the tag is available in this repository. DYEC's unrelated existing `14.0.3` tag was explicitly not treated as the DayOA tag.
- Tracked-file count: 19,585.
- Relevant source sweep: `rg -l 'DyecBuildCommandSet|AnalysisCommand|command_catalog' --glob '!docs/plans/**'` -> 59 files.
- Existing catalog contract: schema v5, `current` and numeric snapshot `17.0.1` are byte-identical, both point commands at DayOA 14.0.2, and both current Bjuice/Inflection command IDs duplicate complete `AnalysisCommand` definitions.
- Baseline focused tests: `python -m pytest -q tests/test_catalog_validation.py tests/test_hiomrs_command_catalog.py tests/test_hg002_bjuice_5x5x_catalog_fixture.py tests/test_repository_catalog.py tests/test_packaged_defaults.py` -> 60 passed.
- Validation limit: local schema, resolver, rendering, payload, wheel, and static evidence only. No AWS/headnode workflow execution is authorized or claimed.

Gate 0 status: `SUCCESS`.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DYEC-001 | Baseline | Freeze branch, tag, worktree, catalog, and focused-test baseline | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 inventory above; 60 focused tests passed |  | Baseline recorded before catalog edits |
| DYEC-002 | Schema v6 | Add typed one-hop same-build alias collection with typed metadata overrides | SUCCESS | feature_implementation | Gate 1 | orchestrator | `AnalysisCommandAlias*` models in `daylily_ec/repositories.py`; focused catalog gate 78 passed |  | Alias metadata is typed and extra fields fail validation |
| DYEC-003 | Alias resolution | Support declarative target/config extension or mutually exclusive complete replacement and keep accessors returning resolved `AnalysisCommand` | SUCCESS | feature_implementation | Gate 1 | orchestrator | Resolver, public payload, accessor, render, and complete-replacement tests in `tests/test_repository_catalog_aliases.py` |  | Existing APIs return resolved `AnalysisCommand` records |
| DYEC-004 | Rejections | Reject chains, cycles, missing bases, cross-build refs, duplicate IDs, and partial replacements | SUCCESS | contract_test | Gate 1 | orchestrator | Parameterized negative tests passed for every requested invalid shape |  | Config extension also fails hard without exactly one `--config` anchor |
| DYEC-005 | Commands | Define `hiomr2_slim_kitchensink_mega` base and `inflection-bjuice-product-v0.2` extending alias with analytical package mode and `$ANALYSIS_ID` | SUCCESS | feature_implementation | Gate 1 | orchestrator | Base resolves one slim target; alias adds only analytical package target, package mode, and environment-bound analysis ID |  | Both commands exclude NICU, Jasmine, Manta, Dysgu, Severus, SURVIVOR, OctopusV, Sniffles1, and Iris invocation |
| DYEC-006 | Catalog pins | Update `current` to DayOA 14.0.3 and copy it exactly to numeric snapshot `17.0.2` | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Raw YAML equality and resolved model tests passed; each build exposes 29 resolved commands pinned to 14.0.3 |  | DayOA annotated tag and prerelease 14.0.3 already verified |
| DYEC-007 | History/parity | Preserve every older numeric snapshot byte-for-byte and keep source/packaged catalogs byte-identical | SUCCESS | contract_test | Gate 1 | orchestrator | Six prior numeric block SHA256 values match baseline; source and packaged catalog `cmp` passed |  | Old duplicated Inflection-named ID remains only in immutable historical snapshots |
| DYEC-008 | Validation | Run alias, accessor, rendering, historical, payload, full tests, wheel, and whitespace validation | SUCCESS | contract_test | Gate 5 | orchestrator | Expanded release-focused gate: 367 passed; complete suite: 2,495 passed, 11 skipped, 20 failed; an untouched baseline replay produced the identical 20 failures; source/payload `cmp`, focused Ruff, `git diff --check`, wheel/sdist build, 17.0.2 metadata, and wheel catalog parity passed | The repository baseline already fails four activation tests, six CLI callback tests, one analysis-lock precedence test, eight headnode transport tests, and one provider-neutrality test | No new full-suite failure was introduced; the baseline failures are outside this release's catalog scope and are preserved explicitly below |
| DYEC-009 | Release | Commit/push candidate branch; create/verify annotated `17.0.2`; publish GitHub prerelease with local-only caveat | SUCCESS | feature_implementation | Gate 5 | orchestrator | Release commit `95bbcd911bbb46bef9f3fe8b8dbc3fb62b7455ce` pushed to `origin/prod-candidate-260812`; annotated tag object `d665e82978565725bf823771c393170408553bbe` peels to that commit locally and remotely; exact-tag wheel/sdist and `twine check` passed; prerelease published at `https://github.com/lsmc-bio/daylily-ephemeral-cluster/releases/tag/17.0.2` |  | GitHub reports non-draft prerelease, published 2026-08-13T05:19:47Z, with no attached assets |
| DYEC-010 | Boundary | Do not merge main, publish package-index artifacts, or run AWS/headnode workflows | SUCCESS | legitimate_safety_handling | Gate 5 | orchestrator | Release commit is not an ancestor of `origin/main` (`b7c1b056feb3ee1b24c0daa338d5f11ec015944d`); GitHub release assets are empty; no package upload, AWS, headnode, Slurm, or live clinical command was run |  | Candidate branch, annotated tag, and GitHub prerelease are the complete authorized external changes |

## Validation record

- Expanded schema, accessor, rendering, history, payload, and compatibility gate: `367 passed`.
- Complete local suite: `2,495 passed, 11 skipped, 20 failed` in 129.44 seconds.
- The exact 51 tests containing those failures were replayed from untouched baseline commit `759b50e13df1dee04ca0164a694a1f46bbd586fe`: `20 failed, 31 passed`. The failure identities and assertions were identical, proving zero new full-suite failures from this change.
- Existing baseline failures: four fake-Conda activation/TOS tests; six monkeypatched CLI callback tests; one analysis-lock error-precedence test; eight semantic headnode transport tests expecting `as_user=ubuntu` where baseline supplies `auto`; and one provider-neutrality scan that already finds `ursa` in the catalog.
- Source and packaged catalog byte comparison: passed.
- Focused Ruff `F,I` static checks and `git diff --check`: passed.
- Isolated PyPA validation build using explicit pre-tag SCM version `17.0.2`: wheel SHA256 `9ab061fc6dbd0746f2b5a24b2a50b642f104589e9a5da1658ae8dddfd0f6f89f`; sdist SHA256 `86cea2294c1ff2d6812bad910a79b7a08a917bea91861180a9174b35785f226e`.
- Wheel metadata reported `17.0.2`, and its embedded command catalog was byte-identical to source (SHA256 `43970ca8366d55295f012279d3f484a76f733c54f339dd89340dcfcba3e3d608`).

## Release record

- Release commit: `95bbcd911bbb46bef9f3fe8b8dbc3fb62b7455ce`.
- Annotated tag object: `d665e82978565725bf823771c393170408553bbe`; local and remote peeled commit: `95bbcd911bbb46bef9f3fe8b8dbc3fb62b7455ce`.
- Exact-tag wheel: `daylily_ephemeral_cluster-17.0.2-py3-none-any.whl`, SHA256 `153e67f0fe96c7c33f654327a2818dbcbdc213c850e66a020e1b395a765eb19a`.
- Exact-tag sdist: `daylily_ephemeral_cluster-17.0.2.tar.gz`, SHA256 `f012c08702f2491bdb846598869d3569ea1593f934dc3a75979e3d41d5aa62b6`.
- `twine check` passed for both locally built artifacts; neither artifact was uploaded or attached.
- GitHub prerelease: `https://github.com/lsmc-bio/daylily-ephemeral-cluster/releases/tag/17.0.2`, published 2026-08-13T05:19:47Z.
- Validation and release evidence is local and fixture-backed. No AWS/headnode, Slurm, or live clinical workflow execution is claimed.

## Final report

All rows terminal: yes

Objective complete: yes

Status counts: SUCCESS 10; OPEN 0; DUPLICATE 0; NO_LONGER_NEEDED 0; FAIL 0; BLOCKED 0.
