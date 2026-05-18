# DayEC Major Docs DRA Cutover Ledger

Date: 2026-05-18

Controlling plan: user-provided "Execute DayEC Docs And DayOA Pin Cutover" in the execution thread.

Ledger status protocol: `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`

## Gate 0 Inventory Freeze

Gate 0 status: `SUCCESS`

### Repository

| Repo | Path | Branch | Baseline commit | Dirty state |
|---|---|---|---|---|
| DayEC | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` | `codex/dyec-fsx-dra-mounts` tracking `origin/codex/dyec-fsx-dra-mounts` | `c7b9b3f9 Fix DRA reference bootstrap wait` | Dirty before this plan. Existing modified files included active docs, DRA/export/runtime/test changes, packaged payload mirrors, and untracked `docs/plans/dyec_fsx_dra_mounts_ledger.md`. These are treated as pre-existing user/thread-owned changes and must not be reverted. |

### Gate 0 Commands

| Area | Command | Result |
|---|---|---|
| Git status | `git status --short --branch` | Branch `codex/dyec-fsx-dra-mounts...origin/codex/dyec-fsx-dra-mounts`; dirty active docs and broader DRA/export/runtime/test files present before this plan. |
| Git identity | `git rev-parse --show-toplevel && git branch --show-current && git rev-parse --short HEAD` | Root `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`; branch `codex/dyec-fsx-dra-mounts`; HEAD `c7b9b3f9`. |
| Instruction files | `find . -maxdepth 3 ... AGENTS.md/CLAUDE.md/.agents/.codex` | Only `./AGENTS.md` found in repo-local instruction surfaces. |
| Initial stale sweep | `rg -n "0\\.7\\.758\|git_tag: 1\\.0\\.0\|default_ref: 1\\.0\\.0\|--target-uri\|ImportPath\|ExportPath\|--scope both" ...` | Active catalog and packaged catalog contained DayOA pins at `0.7.758` and `1.0.0`; active CLI docs contained stale `--scope both`; test files contained expected old pin values and intentional code/test guardrail strings for `ImportPath`/`ExportPath`. |

### Scope

Active docs for this plan are `README.md`, `README.md.bland`, and direct `docs/*.md`. Historical archive content under `docs/archive/**` and prior plan ledgers are not rewritten except to label current active stale planning surfaces as historical when needed.

No live AWS action is approved or required for this plan.

## Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Planning | Record Gate 0 inventory before edits. | `SUCCESS` | `plan_amendment` | Gate 0 | orchestrator | This ledger. |  | Gate 0 recorded before catalog/test/doc edits. |
| PIN-001 | Catalog | Update all DayOA catalog `default_ref` and `git_tag` pins to `1.0.7` in source and packaged catalogs. | `SUCCESS` | `config_or_startup_contract` | Gate 1 | orchestrator | `config/daylily_available_repositories.yaml`; `daylily_ec/resources/payload/config/daylily_available_repositories.yaml`; catalog mirror compare passed. |  | Source and packaged catalogs now match and use DayOA `1.0.7` for every DayOA default ref and command git tag. |
| PIN-002 | Tests | Update pin-related tests from old DayOA pins to `1.0.7`. | `SUCCESS` | `contract_test` | Gate 1 | orchestrator | `tests/test_repository_catalog.py`; `tests/test_cli_registry_v2.py`; focused pytest returned `131 passed`. |  | Pin expectations now assert `1.0.7`; old pin sweep over catalogs and tests returned no hits. |
| DOC-001 | Top-level docs | Refresh README surfaces for current DRA FSx strategy and supported CLI path. | `SUCCESS` | `feature_implementation` | Gate 2 | orchestrator | `README.md`; `README.md.bland`; active-doc stale sweep returned no hits. |  | Top-level docs now describe `dyec`, reference DRA `/fsx/data`, run input DRAs, results, and explicit export DRA workflow. |
| DOC-002 | Operator docs | Refresh quickstart, ultra rapid start, operations, and CLI reference. | `SUCCESS` | `feature_implementation` | Gate 2 | orchestrator | `docs/quickest_start.md`; `docs/ultra_rapid_start.md`; `docs/operations.md`; `docs/cli_reference.md`; active-doc stale sweep returned no hits. |  | Operator docs now use the current DRA lifecycle and no longer advertise stale helper-script paths, `--scope both`, or import/export path wording. |
| DOC-003 | Support docs | Refresh overview, AWS setup, troubleshooting, testing, environment, and pip install docs. | `SUCCESS` | `feature_implementation` | Gate 2 | orchestrator | `docs/overview.md`; `docs/aws_setup.md`; `docs/monitoring_and_troubleshooting.md`; `docs/testing_and_debugging.md`; `docs/DAY_EC_ENVIRONMENT.md`; `docs/pip_install.md`. |  | Support docs now align with the active CLI, regional S3 behavior, DRA-mounted reference/run/export paths, and DayOA `1.0.7` catalog pins. |
| DOC-004 | Historical labeling | Relabel the old run-directory implementation spec as historical/currently superseded. | `SUCCESS` | `historical_docs_only` | Gate 2 | orchestrator | `docs/LSMC_run_directory_mounting_run_analysis_spec.md`; `docs/plans/README.md`. |  | The old run-directory spec and plan-ledger directory are clearly marked as historical provenance, not current operator guidance. |
| DOC-005 | Diagrams | Add Mermaid diagrams for DRA lifecycle, FSx/S3 topology, and catalog-driven pipeline execution. | `SUCCESS` | `feature_implementation` | Gate 2 | orchestrator | `README.md`; `docs/dra_fsx_strategy.md`; `docs/overview.md`. |  | Active docs now include diagrams for cluster DRA lifecycle, FSx/S3 topology, and catalog-driven multi-pipeline launch flow. |
| QA-001 | Validation | Run planned tests, catalog mirror compare, stale sweeps, and `git diff --check`. | `SUCCESS` | `contract_test` | Gate 3 | orchestrator | `pytest ... -> 131 passed`; `cmp -s ... -> exit 0`; stale pin sweep -> no hits; active-doc stale sweep -> no hits; `git diff --check -> exit 0`. |  | All planned validation commands completed successfully; no live AWS actions were run. |

## Status Counts

- `SUCCESS`: 9
- `OPEN`: 0
- `BLOCKED`: 0
- `NO_LONGER_NEEDED`: 0
- `IN_PROGRESS`: 0
- `ATTEMPTING_BUGFIX`: 0
- `FAIL`: 0

## Final Acceptance

All ledger rows are terminal. The requested objective is complete for local source, package-resource, documentation, and test validation scope.

No live AWS action was part of this execution. Existing dirty worktree changes outside this documentation/catalog/test cutover remain preserved.

Final validation evidence:

- `source ./activate >/dev/null && python -m pytest tests/test_repository_catalog.py tests/test_cli_registry_v2.py tests/test_packaged_defaults.py tests/test_run_mounts.py tests/test_export.py tests/test_environment_contract.py -q` -> `131 passed`
- `cmp -s config/daylily_available_repositories.yaml daylily_ec/resources/payload/config/daylily_available_repositories.yaml` -> exit `0`
- `rg -n "0\\.7\\.758|git_tag: 1\\.0\\.0|default_ref: 1\\.0\\.0" config/daylily_available_repositories.yaml daylily_ec/resources/payload/config/daylily_available_repositories.yaml tests` -> no hits
- `rg -n -- "--target-uri|ImportPath|ExportPath|--scope both" README.md README.md.bland docs/*.md` -> no hits
- `git diff --check` -> exit `0`
