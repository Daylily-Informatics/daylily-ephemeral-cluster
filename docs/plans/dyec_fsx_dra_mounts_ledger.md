# DyEC FSx DRA Mounts Ledger

Date: 2026-05-17

Controlling plan: user-provided "DyEC FSx DRA Multi-Mount Refactor Ledger Plan" in the execution thread.

Ledger status protocol: `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`

## Gate 0 Inventory Freeze

Gate 0 status: `SUCCESS`

### Repositories

| Repo | Path | Branch | Baseline commit | Dirty state |
|---|---|---|---|---|
| Current prompt checkout | `/Users/jmajor/.codex/worktrees/dcf6/daylily-ephemeral-cluster` | detached HEAD | `91f853ab Pin DayOA 1.0.0 release` | Clean: `git status --short --branch` -> `## HEAD (no branch)`. |
| Original branch checkout | `/Users/jmajor/projects/daylily/daylily-ephemeral-cluster` | `codex/run-directory-mounts` | `91f853ab Pin DayOA 1.0.0 release` | Dirty before this plan: modified `bin/utils/ilmn/extract_undetermined_indexes`, `config/daylily_available_repositories.yaml`, `config/daylily_cli_global.yaml`, `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`, `daylily_ec/stage_samples.py`, `docs/cli_reference.md`, `docs/operations.md`, `tests/test_ont_fastq_prefix_staging.py`, `tests/test_script_entrypoints.py`, `tests/test_stage_samples_from_local_to_headnode.py`; untracked `007_*`, `qc_vs_qc.tsv`, temp config backups, prior ledgers, reports, `tmp-export/`, and `tests/test_extract_undetermined_indexes.py`. |
| Implementation worktree | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` | `codex/dyec-fsx-dra-mounts` tracking `origin/codex/run-directory-mounts` | `91f853ab Pin DayOA 1.0.0 release` | Clean at creation: `git status --short --branch` -> `## codex/dyec-fsx-dra-mounts...origin/codex/run-directory-mounts`. |

### Baseline And Sweep Evidence

| Area | Command | Result |
|---|---|---|
| Branch setup | `git fetch origin codex/run-directory-mounts --prune`; `git worktree add -b codex/dyec-fsx-dra-mounts /Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster origin/codex/run-directory-mounts` | Worktree created from fetched `origin/codex/run-directory-mounts` at `91f853ab`. |
| Template legacy fields | `rg -l "ImportPath|ExportPath|AutoImportPolicy|AutoExportPolicy" config daylily_ec/resources/payload/config` | 10 files: 5 source templates plus 5 packaged copies. |
| Template hit count | `rg -n "ImportPath|ExportPath|AutoImportPolicy|AutoExportPolicy" config/day_cluster daylily_ec/resources/payload/config/day_cluster \| wc -l` | 20 hits. Active source files: `config/day_cluster/{prod_cluster.yaml,prod_cluster_dragen.yaml,prod_cluster_variant.yaml,cromwell_test.yaml,regions/all_clusters.yaml}`. Packaged mirrors under `daylily_ec/resources/payload/config/day_cluster/`. |
| Runtime/export/docs legacy refs | `rg -n "export --target-uri|--target-uri|ExportPath|export root|ImportPath" README.md README.md.bland docs daylily_ec tests bin \| wc -l` | 40 hits, including active docs and export implementation/tests plus historical docs under `docs/archive/` and `docs_orig/`. |
| Baseline tests 1 | `source ./activate && python -m pytest tests/test_renderer.py tests/test_aws_validation.py tests/test_workflow.py -q` | `90 passed`. |
| Baseline tests 2 | `source ./activate && python -m pytest tests/test_run_mounts.py tests/test_export.py tests/test_delete.py tests/test_cli_registry_v2.py -q` | `102 passed, 2 failed`. Pre-existing failures: `tests/test_cli_registry_v2.py::test_samples_run_rejects_unknown_command` and `::test_samples_run_rejects_incompatible_catalog_command`, both due stale extracted resources under `/Users/jmajor/.config/daylily/resources/2.0.2/` missing `command_catalog_version`. |

### Live-System Limits

- No live mutating AWS action is approved in this thread.
- `AWS_PROFILE=lsmc aws sts get-caller-identity --output json` succeeded for account `108782052779`.
- `AWS_PROFILE=lsmc aws fsx describe-file-systems --region us-west-2` found four available Lustre `SCRATCH_2` filesystems, all with legacy `LustreConfiguration.DataRepositoryConfiguration`.
- `AWS_PROFILE=lsmc aws fsx describe-data-repository-associations --region us-west-2` returned no associations.
- AWS ParallelCluster documents `DataRepositoryAssociations` as up to 8 DRAs per filesystem and disallows using `ImportPath`/`ExportPath` at the same time as DRAs.
- Runtime create must therefore reject described legacy filesystem-level repository configuration before calling `create_data_repository_association`.

## Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Planning | Create branch/worktree and ledger; record dirty original checkout and fetched base commit. | `SUCCESS` | `plan_amendment` | Gate 0 | orchestrator | This ledger; branch/worktree evidence above. |  | Gate 0 complete before implementation edits. |
| TPL-001 | Templates | Inventory active `ImportPath`, `ExportPath`, top-level FSx `AutoImportPolicy`, and `AutoExportPolicy` hits. | `SUCCESS` | `feature_implementation` | Gate 0 | Agent A | Gate 0 sweep found 20 active template/resource hits across 10 files. |  | Counts and paths recorded. |
| TPL-002 | Templates | Convert active cluster templates and packaged copies to DRA-only `reference-data` model. | `SUCCESS` | `feature_implementation` | Gate 1 | Agent A | `config/day_cluster/*.yaml`; `config/day_cluster/regions/all_clusters.yaml`; packaged mirrors under `daylily_ec/resources/payload/config/day_cluster/`; active legacy sweep returned no hits. |  | Active templates now use `DataRepositoryAssociations` with `reference-data`, `/data/`, `${REGSUB_S3_BUCKET_REF}/data/`, metadata import on create, and no `ImportPath`/`ExportPath`/top-level FSx auto policies. |
| VAL-001 | Validation | Update renderer/validation tests for DRA templates without new fallback keys. | `SUCCESS` | `contract_test` | Gate 1 | Agent A | `tests/test_packaged_defaults.py`; `source ./activate && python -m pytest tests/test_renderer.py tests/test_aws_validation.py tests/test_workflow.py -q` -> `90 passed`; `python -m pytest tests/test_packaged_defaults.py tests/test_resources_extraction.py -q` covered template/package shape. |  | DRA-only active template shape and source/package synchronization are tested. |
| RTE-001 | Runtime mounts | Add FSx DRA compatibility preflight before runtime mount creation. | `SUCCESS` | `feature_implementation` | Gate 1 | Agent B | `daylily_ec/run_mounts.py`; `tests/test_run_mounts.py`; focused run -> `15 passed`. |  | `mounts create` describes the FSx filesystem and fails before DRA create for non-Lustre, `SCRATCH_1`, legacy `DataRepositoryConfiguration`, missing id, or describe failure. |
| RTE-002 | Runtime mounts | Make AWS DRA state authoritative in list/describe; expose local projection status in JSON. | `SUCCESS` | `feature_implementation` | Gate 1 | Agent B | `daylily_ec/run_mounts.py`; `tests/test_run_mounts.py`; full suite -> `860 passed, 7 skipped`. |  | List/describe returns AWS associations only; stale local-only records no longer satisfy describe; JSON includes `local_projection_status`. |
| RTE-003 | Runtime mounts | Add explicit `mounts verify --scope headnode|compute|both`. | `SUCCESS` | `feature_implementation` | Gate 1 | Agent B | `daylily_ec/run_mounts.py`; `daylily_ec/cli.py`; `tests/test_run_mounts.py`; CLI registry tests -> `118 passed` in focused set. |  | Verify accepts mount id or association id, uses the central SSM shell helper, and can run headnode, Slurm compute, or both checks. |
| EXP-001 | Exports | Implement export DRA attach/run/detach helpers and receipt schema. | `SUCCESS` | `feature_implementation` | Gate 1 | Agent C | `daylily_ec/workflow/export_data.py`; `daylily_ec/cli.py`; `tests/test_export.py`; `tests/test_ssm_e2e_runner.py`; full suite -> `860 passed, 7 skipped`. |  | Export attaches `/exports/<export_id>/`, starts `EXPORT_TO_REPOSITORY`, writes schema v2 receipts with association/task/source/destination/report/failure/detach fields, and detaches with `DeleteDataInFileSystem=False`. |
| EXP-002 | Exports | Remove legacy `ExportPath` export dependency and fail hard on legacy target mode. | `SUCCESS` | `removable_compatibility_debt` | Gate 1 | Agent C | `daylily_ec/workflow/export_data.py`; `bin/daylily-export-fsx-to-s3*`; packaged wrappers; active legacy sweep returned no hits for `--target-uri`, `ExportPath`, or `ImportPath`. |  | Root export now requires `--export-id`, `--source-path`, and `--destination-s3-uri`; legacy positional export wrapper exits with explicit removal guidance. |
| DEL-001 | Delete | Add cluster delete dry-run warning for active run/export DRAs. | `SUCCESS` | `legitimate_safety_handling` | Gate 1 | Agent D | `daylily_ec/workflow/delete_cluster.py`; `tests/test_delete.py` -> `9 passed`; full suite -> `860 passed, 7 skipped`. |  | Delete dry-run and live confirmation path inspect active DRAs and active FSx export tasks and report them before deletion. |
| DOC-001 | Docs | Update CLI reference and operations docs for DRA cluster creation, run mounts, detach, verify, and on-demand export. | `SUCCESS` | `feature_implementation` | Gate 1 | Agent D | `README.md`; `README.md.bland`; `docs/cli_reference.md`; `docs/operations.md`; `docs/quickest_start.md`; `docs/ultra_rapid_start.md`; `docs/monitoring_and_troubleshooting.md`; active legacy-doc sweep returned no hits. |  | Active docs now describe DRA-backed reference data, run mounts, verify scope, explicit export DRA source/destination, and detach proof. |
| QA-001 | QA | Run focused and full local validation. | `SUCCESS` | `contract_test` | Gate 5 | QA Agent | Focused: renderer/AWS/workflow `90 passed`; run-mount/export/delete/registry `118 passed`; touched runtime/docs/resource set `144 passed`; full `python -m pytest -q` -> `860 passed, 7 skipped, 4 warnings`; `python -m ruff check ...` -> `All checks passed`; `git diff --check` passed. |  | Local validation is green. |
| LIVE-001 | Live QA | Optional fresh-cluster dry-run/live smoke. | `BLOCKED` | `legitimate_safety_handling` | Gate 5 | orchestrator | No live cluster create, DRA mutation, or destructive AWS cleanup approval in this thread. | Live mutating AWS action requires separate explicit approval. | `pcluster --dryrun true` can be considered later with explicit profile/config; real create/mount/detach remains blocked. |

## Status Counts

- `SUCCESS`: 12
- `OPEN`: 0
- `BLOCKED`: 1
- `NO_LONGER_NEEDED`: 0
- `IN_PROGRESS`: 0
- `ATTEMPTING_BUGFIX`: 0
- `FAIL`: 0

## Final Report

All rows terminal: `yes`
Objective complete: `no`

Status counts:

- `SUCCESS`: 12
- `DUPLICATE`: 0
- `NO_LONGER_NEEDED`: 0
- `FAIL`: 0
- `BLOCKED`: 1

Changed files:

- DayEC: templates, packaged resource mirrors, runtime mount helpers, export workflow/CLI, delete workflow, resource extraction cache sync, E2E runner, active docs, and focused tests.

Validation:

- `source ./activate && python -m pytest tests/test_renderer.py tests/test_aws_validation.py tests/test_workflow.py -q` -> `90 passed`
- `source ./activate && python -m pytest tests/test_run_mounts.py tests/test_export.py tests/test_delete.py tests/test_cli_registry_v2.py -q` -> `118 passed`
- `source ./activate && python -m pytest -q` -> `860 passed, 7 skipped, 4 warnings`
- `source ./activate && python -m ruff check daylily_ec tests/test_export.py tests/test_run_mounts.py tests/test_delete.py tests/test_cli_registry_v2.py tests/test_packaged_defaults.py tests/test_ssm_e2e_runner.py` -> `All checks passed`
- `git diff --check` -> passed
- Active legacy sweep for `ImportPath:`, `ExportPath:`, `--target-uri`, `export-target-uri`, filesystem export-root wording, `IMPORT_PATH`, and `EXPORT_PATH` across active code/templates/docs -> no hits

Non-success terminal rows:

- `LIVE-001` `BLOCKED`: no live cluster create, DRA mutation, or destructive AWS cleanup approval was given in this thread.

Residual risks:

- Live fresh-cluster DRA create/mount/export/detach smoke remains unperformed until an explicit AWS approval and target config are provided.

## Live Follow-Up: Bootstrap Publish

Date: 2026-05-17

Root cause from `dra-test2`: `HeadNodeWaitCondition20260517233228` failed because the `OnNodeConfigured` script exited with `ERROR: cached Apptainer deb not found: /fsx/data/cached_envs/apptainer_1.4.5_amd64.deb`. The S3 object existed at `s3://lsmc-dayoa-omics-analysis-us-west-2/data/cached_envs/apptainer_1.4.5_amd64.deb`; CloudFormation showed the headnode custom action failing while the `reference-data` DRA was still in progress, so the failure was a DRA metadata visibility race.

Patch:

- `config/day_cluster/post_install_ubuntu_combined.sh`
- `daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh`
- `tests/test_headnode_init.py`

Behavior:

- wait up to 1800 seconds for required `/fsx/data` reference entries from the FSx DRA,
- fail hard with directory diagnostics if they never appear,
- run `chmod a-w /fsx/data` and log resulting permissions once references are visible.

Validation:

- `source ./activate && python -m pytest tests/test_headnode_init.py tests/test_packaged_defaults.py -q` -> `18 passed`
- `bash -n config/day_cluster/post_install_ubuntu_combined.sh && bash -n daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh` -> passed
- source/package mirror `cmp` -> `0`

S3 publish:

Local SHA-256: `dc7069a09e4394d2fac01e87018118209aec2ad9459eef9561168d41abfd2714`

| Profile | Bucket | Region | Read-back SHA-256 |
|---|---|---|---|
| `lsmc` | `lsmc-dayoa-omics-analysis-us-west-2` | `us-west-2` | `dc7069a09e4394d2fac01e87018118209aec2ad9459eef9561168d41abfd2714` |
| `lsmc` | `lsmc-dayoa-omics-analysis-eu-central-1` | `eu-central-1` | `dc7069a09e4394d2fac01e87018118209aec2ad9459eef9561168d41abfd2714` |
| `lsmc` | `lsmc-dayoa-omics-analysis-ap-south-1` | `ap-south-1` | `dc7069a09e4394d2fac01e87018118209aec2ad9459eef9561168d41abfd2714` |
| `daylily` | `daylily-service-omics-analysis-us-west-2` | `us-west-2` | `dc7069a09e4394d2fac01e87018118209aec2ad9459eef9561168d41abfd2714` |
| `daylily` | `daylily-omics-analysis-references-public` | `us-west-2` | `dc7069a09e4394d2fac01e87018118209aec2ad9459eef9561168d41abfd2714` |
| `daylily` | `daylily-references-public` | `us-west-2` | `dc7069a09e4394d2fac01e87018118209aec2ad9459eef9561168d41abfd2714` |
