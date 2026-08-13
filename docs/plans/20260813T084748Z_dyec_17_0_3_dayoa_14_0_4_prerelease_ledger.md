# DYEC 17.0.3 / DayOA 14.0.4 Prerelease Execution Ledger

Created: 2026-08-13T08:47:48Z

Linked DayOA ledger:
`daylily-omics-analysis/docs/plans/20260813T081946Z_compression_level_14_0_4_release_ledger.md`

## Scope and release boundary

Release the active DYEC production-candidate lineage with every applicable DYEC
change that appeared after 17.0.2, move the live command catalog pin to the
annotated DayOA 14.0.4 tag, copy the updated `current` catalog exactly to a new
immutable `17.0.3` snapshot, validate locally, and publish annotated tag and
GitHub prerelease `17.0.3`. Do not merge `main`, publish package-index
artifacts, or run AWS/headnode/Slurm/clinical workflows.

## Gate 0: inventory freeze

- Repository:
  `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-prod-candidate-260812`.
- Branch and upstream: clean `prod-candidate-260812`, equal to
  `origin/prod-candidate-260812` at
  `fde2c7524e71c15c2c317d91f696eac60222a39c`.
- Remote maximum semantic-version tag: annotated `17.0.2`; it peels to release
  commit `95bbcd911bbb46bef9f3fe8b8dbc3fb62b7455ce`.
- Next tag: local and remote `17.0.3` refs are absent.
- DayOA input: annotated remote tag object
  `8bec9e10de93b85371cd61887cfef7a47a435339` for `14.0.4`, peeling to
  `b2d79181e8589a06f29901fadc25be172f259eb8`.
- Candidate delta after `17.0.2`: exactly one docs-only commit,
  `fde2c752` (`Close DYEC 17.0.2 prerelease ledger`); no post-tag DYEC source
  change exists on the candidate branch.
- GitHub delta audit: the only open PRs are stale draft PR 50 against `main`
  and draft PR 4 against `prod`; both were last updated in July 2026, predate
  `17.0.2`, and do not target `prod-candidate-260812`. No remote branch tip is
  newer than the candidate closeout commit.
- Catalog baseline: source and packaged catalogs are byte-identical; parsed
  `dyec_builds.current` equals snapshot `17.0.2`, and both pin DayOA `14.0.3`.
  Historical block SHA-256 values were frozen before editing.
- Focused baseline after `source ./activate`: Python 3.11.15; 74 catalog and
  packaged-default tests passed in 24.50 seconds.
- Live-system boundary: local source/tests/build and GitHub refs/release only;
  no AWS, headnode, Slurm, workflow-controller, or clinical execution is
  authorized or required.

Gate 0 status: `SUCCESS`.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DYEC-001 | Baseline | Freeze branch, maximum tag, DayOA tag, catalog, and focused-test baseline | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 inventory above; focused baseline 74 passed |  | Baseline recorded before catalog edits. |
| DYEC-002 | Delta audit | Include every applicable DYEC change that appeared after 17.0.2 | SUCCESS | plan_amendment | Gate 0 | orchestrator | `git log 17.0.2..HEAD` contains only the prior ledger closeout; remote branch and open-PR audit above |  | The new release naturally contains the closeout commit; there is no post-tag source change to merge. |
| DYEC-003 | Catalog pin | Update active repository defaults and `dyec_builds.current` from DayOA 14.0.3 to 14.0.4 | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Active repository prefix has 59 DayOA 14.0.4 values; current block has 57; parsed current exposes 29 resolved commands all pinned to 14.0.4 |  | No fallback, inferred version, or historical-block edit was introduced. |
| DYEC-004 | Snapshot | Copy updated `current` exactly to immutable numeric snapshot `17.0.3` while preserving all older snapshots | SUCCESS | feature_implementation | Gate 2 | orchestrator | Parsed `current == 17.0.3`; raw hashes for 16.1.81, 16.1.82, 16.1.85, 16.1.86, 17.0.0, 17.0.1, and 17.0.2 match Gate 0 |  | Snapshot 17.0.2 remains pinned to DayOA 14.0.3 and its raw SHA-256 remains `a423e38640be95bf7f64726331a308e6fe566b4214789661e75ccf3af939df10`. |
| DYEC-005 | Parity/tests | Keep source and packaged catalogs byte-identical and update current/snapshot contract tests | SUCCESS | contract_test | Gate 5 | orchestrator | Source/package `cmp`, YAML/model loading, 74 focused tests, 29-command equality, and focused Ruff passed |  | Both catalog copies are byte-identical. |
| DYEC-006 | Validation | Run focused and complete local tests, static/whitespace checks, exact-version build, wheel payload parity, and `twine check` | SUCCESS | contract_test | Gate 5 | orchestrator | Final complete suite: 2,515 passed, 11 skipped, zero failed in 132.48 s; focused remediation suite: 89 passed; Ruff F/I, compileall, YAML/model parity, `git diff --check`, exact 17.0.3 metadata build, wheel catalog parity, and `twine check` passed | The initial 20 failures comprised stale test harness assumptions plus one real headnode transport defect; DYEC-010 through DYEC-014 record the disposition. | No test was removed. Wheel SHA-256 `417bae34049582669d59b3bfcee547e8f400c4786940f91a9e052f081d130722`; sdist SHA-256 `355e24736de7f0d6bf0ebe07e61c673d25cb9a4414666ab81f5b85f6935904be`. |
| DYEC-007 | Release | Commit/push candidate; create and verify annotated `17.0.3`; publish GitHub prerelease | OPEN | feature_implementation | Gate 5 | orchestrator | Local/remote commit, tag, artifact, and GitHub release evidence pending |  |  |
| DYEC-008 | Boundary | Do not merge main, upload package-index artifacts, or run AWS/headnode workflows | OPEN | legitimate_safety_handling | Gate 5 | orchestrator | Final branch/release/assets and execution-boundary checks pending |  |  |
| DYEC-009 | Plan amendment | Expand the release gate from baseline-equivalent failures to fixing or removing all 20 failures | SUCCESS | plan_amendment | Gate 5 | orchestrator | User direction received after the initial complete-suite run |  | No tag or release had been created; release execution is paused until the suite is clean. |
| DYEC-010 | Activation | Resolve four `tests/test_activate.py` failures | SUCCESS | contract_test | Gate 5 | orchestrator | Fake Conda now implements and asserts the required `config --set plugins.auto_accept_tos true` contract; 4 passed | Test fixture predated the required ToS configuration command. | Retained all tests and extended the fixture rather than weakening activation failure behavior. |
| DYEC-011 | CLI callbacks | Resolve six `tests/test_cli_authoritative_gap_coverage.py` failures | SUCCESS | contract_test | Gate 5 | orchestrator | Callback-isolation tests now stub `_install_dayec_version_option`; entire file 22 passed | Tests replaced `create_app` with a function but did not isolate the later app-type-specific installer hook. | Retained exception/return-code coverage without making production installation fail soft. |
| DYEC-012 | Analysis lock | Resolve one lock error-precedence failure | SUCCESS | contract_test | Gate 5 | orchestrator | Missing-path fixture now has the required `analysis_results/<owner>/<analysis_id>` shape; file 9 passed | Malformed outside-root input correctly failed structural validation before existence validation. | Test now independently covers missing valid-shape root and outside-root errors. |
| DYEC-013 | Headnode transport | Resolve eight semantic headnode `as_user` failures | SUCCESS | active_product_contract | Gate 5 | orchestrator | `_run_headnode_semantic_script` now sends `as_user="ubuntu"`; file 12 passed | Semantic helper explicitly overrode the central Ubuntu default with platform auto-detection. | Runtime fixed to the repo's Ubuntu headnode contract; no test was removed. |
| DYEC-014 | Provider boundary | Resolve one active-surface provider-token failure | SUCCESS | active_product_contract | Gate 5 | orchestrator | Provider test now semantically scans all catalog fields except immutable `validation_runs`; file 4 passed | All 40 raw token hits were historical validation ledger/cluster provenance, not executable config or integration code. | Executable source and all non-provenance catalog values remain forbidden from containing provider tokens. |

## Expected live-test skips

The 11 skipped cases are the 11 parameterized live scenarios in
`tests/test_staging_examples_live.py`. They require the explicit
`--run-live-staging-examples` opt-in together with a live AWS profile, region,
cluster, reference/control/staging S3 URIs, and headnode/FSx execution context.
The two local parser/contract tests in that file passed. The 11 scenarios remain
in the suite as necessary opt-in integration coverage; running them is neither a
local prerelease requirement nor permitted by this release's no-AWS/headnode
boundary.

## Final report

All rows terminal: no

Objective complete: no

Execution is in progress.
