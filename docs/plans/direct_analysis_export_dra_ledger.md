# Direct Analysis-Directory DRA Export Ledger

Date: 2026-05-18

Controlling plan: user-provided "Direct Analysis-Directory DRA Export" in the execution thread.

Ledger status protocol: `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`

## Gate 0 Inventory Freeze

Gate 0 status: `SUCCESS`

### Repository

| Repo | Path | Branch | Baseline commit | Dirty state |
|---|---|---|---|---|
| DayEC | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` | `codex/direct-analysis-export-dra` | `40c390b8 Merge pull request #250 from Daylily-Informatics/codex/dyec-fsx-dra-mounts` | Clean before implementation: `git status --short --branch` -> `## codex/direct-analysis-export-dra`. |

### Gate 0 Commands

| Area | Command | Result |
|---|---|---|
| Git status | `git status --short --branch` | Clean branch `codex/direct-analysis-export-dra`. |
| Git identity | `git rev-parse --show-toplevel && git branch --show-current && git rev-parse --short HEAD` | Root `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`; branch `codex/direct-analysis-export-dra`; HEAD `40c390b8`. |
| Instruction files | `find .. -name AGENTS.md -o -name CLAUDE.md -o -path '*/.agents/*' -o -path '*/.codex/*'` | Repo-local instruction surface: `../daylily-ephemeral-cluster/AGENTS.md`. |
| Baseline focused tests | `source ./activate >/dev/null && python -m pytest tests/test_export.py tests/test_cli_registry_v2.py tests/test_ssm_e2e_runner.py tests/test_delete.py tests/test_packaged_defaults.py -q` | `128 passed`. |
| Staging-export sweep | `rg -n "/fsx/exports|/exports/<export_id>|/exports/\\$EXPORT_ID|/exports/export-1|--export-id|export_id|EXPORT_ROOT|HEADNODE_EXPORT_ROOT" daylily_ec tests docs README.md README.md.bland bin config -S` | Active code, docs, wrappers, and tests use the `/fsx/exports/<export_id>` staging-copy model and require `--export-id`. Historical plan ledgers also document the old model. |
| Receipt/export sweep | `rg -n "schema_version: 2|EXPORT_SCHEMA_VERSION = 2|fsx_export|EXPORT_TO_REPOSITORY|DeleteDataInFileSystem" daylily_ec tests docs README.md README.md.bland bin -S` | Current export receipt schema is v2; export task and `DeleteDataInFileSystem=False` detach behavior are already present. |

### Scope

Active docs for this plan are `README.md`, `README.md.bland`, and direct `docs/*.md`. Historical plan ledgers and archive docs are not rewritten except for this new control ledger.

No live AWS action is approved or required for implementation validation.

## Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Planning | Record Gate 0 inventory before edits. | `SUCCESS` | `plan_amendment` | Gate 0 | orchestrator | This ledger. |  | Gate 0 recorded before implementation edits. |
| EXP-001 | Workflow | Replace `/exports/<export_id>` staging DRA creation with direct analysis-directory DRA creation. | `SUCCESS` | `feature_implementation` | Gate 1 | orchestrator | `daylily_ec/workflow/export_data.py`; `tests/test_export.py`; focused suite `138 passed`; full suite `873 passed, 7 skipped`. |  | `dyec export` creates a DRA directly at `/analysis_results/ubuntu/<analysis_dir>/`, runs `EXPORT_TO_REPOSITORY`, and detaches. |
| EXP-002 | Validation | Normalize source paths to `/analysis_results/ubuntu/<analysis_dir>/` and reject unsafe/non-analysis paths. | `SUCCESS` | `contract_test` | Gate 1 | orchestrator | `normalize_export_source_path`; `tests/test_export.py::test_normalize_export_source_accepts_analysis_dir`; `test_normalize_export_source_rejects_non_analysis_dir`. |  | Accepts `/fsx/analysis_results/ubuntu/foo` and `/analysis_results/ubuntu/foo/`; rejects run mounts, reference data, old export staging, nested paths, duplicate slashes, and `..`. |
| EXP-003 | Validation | Require destination S3 suffix to match `analysis_results/ubuntu/<analysis_dir>/` with explicit bucket. | `SUCCESS` | `contract_test` | Gate 1 | orchestrator | `validate_export_destination_s3_uri`; `tests/test_export.py::test_validate_export_destination_requires_matching_suffix`. |  | Destination bucket remains explicit and key suffix must match the normalized analysis directory. |
| EXP-004 | Receipt | Bump `fsx_export.yaml` to schema v3 with direct source, destination, task/report, failure, and detach details. | `SUCCESS` | `feature_implementation` | Gate 1 | orchestrator | `EXPORT_SCHEMA_VERSION = 3`; `daylily_ec/resources/payload/etc/fsx_export.yaml`; `tests/test_export.py::test_run_export_workflow_success_writes_v3_receipt`; task-failure and detach-failure tests. |  | Receipt records normalized source, destination, association id, task lifecycle, report path, detach state, fixed `delete_data_in_file_system: false`, and failure details. |
| EXP-005 | Cleanup | Capture the temporary association id immediately after create so attach wait failures still detach and write a receipt. | `SUCCESS` | `legitimate_safety_handling` | Gate 1 | orchestrator | `daylily_ec/workflow/export_data.py`; `tests/test_export.py::test_run_export_workflow_attach_timeout_still_detaches`; focused command `source ./activate >/dev/null && python -m pytest tests/test_export.py tests/test_cli_registry_v2.py tests/test_ssm_e2e_runner.py tests/test_delete.py -q` -> `134 passed`. |  | A timeout while waiting for the DRA to become `AVAILABLE` records `association_id`, skips task creation, detaches with `DeleteDataInFileSystem=false`, and writes failure details. |
| CLI-001 | CLI | Remove public `--export-id` requirement from primary `dyec export`; keep no public staging-copy mode. | `SUCCESS` | `removable_compatibility_debt` | Gate 1 | orchestrator | `daylily_ec/cli.py`; `tests/test_cli_registry_v2.py`; `tests/test_export.py::test_cli_export_passes_direct_analysis_options`. |  | Primary export requires `--source-path`, `--destination-s3-uri`, cluster or FSx id, region, and output dir. |
| CLI-002 | CLI | Update or remove `dyec exports attach|run` so active public CLI does not preserve stale staging semantics; retain detach. | `SUCCESS` | `removable_compatibility_debt` | Gate 1 | orchestrator | `daylily_ec/cli.py`; `tests/test_cli_registry_v2.py`; focused suite `138 passed`. |  | `exports attach` and `exports run` now use direct `--source-path`; `exports detach --association-id` remains unchanged. |
| WRAP-001 | Wrappers/E2E | Update packaged wrappers and SSM E2E runner export arguments for direct analysis-directory export. | `SUCCESS` | `feature_implementation` | Gate 1 | orchestrator | `bin/daylily-export-fsx-to-s3*`; packaged copies; `daylily_ec/ssh_to_ssm_e2e_runner.py`; wrapper `cmp` checks passed; `tests/test_ssm_e2e_runner.py`. |  | Wrappers no longer accept or forward export ids; E2E runner validates normalized source and explicit destination. |
| DOC-001 | Docs | Remove active `/fsx/exports` guidance and document direct analysis-directory export flow. | `SUCCESS` | `feature_implementation` | Gate 2 | orchestrator | `README.md`; `README.md.bland`; direct `docs/*.md`; stale sweep `rg -n "export-id\|--export-id\|/fsx/exports\|/exports/<export_id>\|/exports/\\$EXPORT_ID\|/exports/export\|/exports/old" README.md README.md.bland docs/*.md bin daylily_ec/resources/payload/bin daylily_ec/resources/payload/etc -S` returned no hits. |  | Active docs show direct export from `/fsx/analysis_results/ubuntu/<analysis_dir>` to explicit `s3://bucket/analysis_results/ubuntu/<analysis_dir>/`. |
| QA-001 | Validation | Run focused tests, full suite, ruff, stale sweeps, and `git diff --check`. | `SUCCESS` | `contract_test` | Gate 5 | orchestrator | Focused suite `134 passed`; full `python -m pytest -q` -> `874 passed, 7 skipped`; `ruff check` -> passed; `git diff --check` -> passed; stale schema sweep returned no hits; wrapper payload `cmp` checks passed. |  | Validation completed without live AWS actions. |

## Status Counts

- `SUCCESS`: 11
- `OPEN`: 0
- `BLOCKED`: 0
- `NO_LONGER_NEEDED`: 0
- `IN_PROGRESS`: 0
- `ATTEMPTING_BUGFIX`: 0
- `FAIL`: 0
