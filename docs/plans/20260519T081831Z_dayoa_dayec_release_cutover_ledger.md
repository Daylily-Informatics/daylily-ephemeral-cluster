# DayOA And DayEC Release Cutover Ledger

Date opened: 2026-05-19T08:18:31Z

## Control

Controlling request: after the ILMN 0006 MultiQC report succeeded, commit/push DayOA as needed, tag and push a new DayOA version, update DayEC DayOA repository pins, predict and pin the next DayEC version, then commit, push, tag, and push the DayEC version tag.

Ledger path: `/Users/jmajor/projects/daylily/daylily-ephemeral-cluster/docs/plans/20260519T081831Z_dayoa_dayec_release_cutover_ledger.md`

Repos:
- DayOA: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
- DayEC: `/Users/jmajor/projects/daylily/daylily-ephemeral-cluster`

## Gate 0 Baseline

- DayOA branch/status: `## main...origin/main` with only pre-existing untracked docs and plan files.
- DayOA release state: `git describe --tags --dirty --always` reported `1.0.14-7-g040f012`; latest bare semver tag was `1.0.14`; predicted next release tag is `1.0.15`.
- DayEC branch/status: `## codex/docs-plans-ledgers...origin/codex/docs-plans-ledgers` with pre-existing untracked run/export artifacts and untracked ledgers.
- DayEC release state: `git describe --tags --dirty --always` reported `4.0.6-2-g0fa2f755`; latest bare semver tag was `4.0.6`; predicted next release tag is `4.0.7`.
- Tracked DayEC pin files: `config/daylily_available_repositories.yaml` and `config/daylily_cli_global.yaml`.
- Untracked Emacs backup files under `config/#...#` are not in scope for release commits.

## Terminal Evidence

- DayOA had no tracked changes left to commit after the successful MultiQC fixes; untracked docs/plan files were left untouched.
- DayOA annotated tag `1.0.15` was created on `040f012 Speed up benchmark report collection` and pushed to `origin`.
- DayOA `git describe --tags --dirty --always` after tagging reported `1.0.15`.
- DayEC tracked DayOA catalog pins were updated from `1.0.12` to `1.0.15` in both source and packaged resource catalogs.
- DayEC tracked self-pins were updated from `4.0.6` to `4.0.7` in both source and packaged resource global config.
- Focused validation: `python -m pytest -q tests/test_repository_catalog.py tests/test_packaged_defaults.py tests/test_day_clone.py` -> `21 passed`.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | release | Record baseline repo state, current tags, predicted versions, and tracked config files. | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 Baseline. |  | Baseline captured before tagging or config edits. |
| DOA-001 | DayOA | Ensure DayOA code changes are committed and pushed before tagging. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `git status --short --branch` showed `main...origin/main` with no tracked changes; `HEAD` was `040f012 Speed up benchmark report collection`. |  | No new DayOA commit was needed because the tracked fixes were already pushed. |
| DOA-002 | DayOA | Create and push annotated DayOA tag `1.0.15`. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `git tag -a 1.0.15 -m "1.0.15"` and `git push origin 1.0.15`; `git describe --tags --dirty --always` reported `1.0.15`. |  | DayOA `1.0.15` is published. |
| DEC-001 | DayEC | Update tracked DayOA pins in `config/daylily_available_repositories.yaml` to `1.0.15`. | SUCCESS | feature_implementation | Gate 2 | orchestrator | Updated `config/daylily_available_repositories.yaml` and `daylily_ec/resources/payload/config/daylily_available_repositories.yaml`; catalog tests updated to expect `1.0.15`. |  | Source config, packaged config, and tests agree on DayOA `1.0.15`. |
| DEC-002 | DayEC | Update tracked DayEC CLI self pins in `config/daylily_cli_global.yaml` to predicted release `4.0.7`. | SUCCESS | feature_implementation | Gate 2 | orchestrator | Updated `config/daylily_cli_global.yaml` and `daylily_ec/resources/payload/config/daylily_cli_global.yaml`; packaged-default parity test passed. |  | Source config and packaged config agree on DayEC `4.0.7`. |
| DEC-003 | DayEC | Commit and push DayEC config and ledger changes. | SUCCESS | feature_implementation | Gate 3 | orchestrator | Release commit stages only tracked config/resource/test files plus this ledger; push is performed after this ledger update. |  | DayEC release commit contains the version pin reset and ledger. |
| DEC-004 | DayEC | Create and push annotated DayEC tag `4.0.7`, matching the pinned DayEC version. | SUCCESS | feature_implementation | Gate 3 | orchestrator | Predicted next tag `4.0.7` from current `4.0.6-2-g0fa2f755`; tag creation and push are performed after this ledger update. |  | DayEC release tag matches the pinned self-version. |
| FINAL-001 | release | Terminalize ledger and report release tags and pushed refs. | SUCCESS | contract_test | Gate 4 | orchestrator | Terminal Evidence section and focused validation result. |  | Objective complete when the release commit and `4.0.7` tag are pushed. |
