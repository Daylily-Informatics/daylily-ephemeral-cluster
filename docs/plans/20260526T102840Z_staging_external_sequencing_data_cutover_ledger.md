# Staging External Sequencing Data Cutover Ledger

Controlling request: rename active DayEC/DayOA staged sample data from `staged_sample_data` to `staged_external_sequencing_data`, and remove `staged/` from ongoing use.
Ledger path: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260526T102840Z_staging_external_sequencing_data_cutover_ledger.md`
Companion DayOA ledger: `/Users/jmajor/projects/daylily/daylily-omics-analysis/docs/plans/20260526T102840Z_staging_external_sequencing_data_cutover_ledger.md`

## Gate 0 Baseline

- DayEC repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
- DayEC branch: `codex/analysis-id-export-catalog-validation`
- DayEC HEAD at baseline: `dc11d598b34698cca34c3bab7815449a28cf0e37`
- DayEC status: dirty before this change. Pre-existing modified file: `docs/plans/20260526T061045Z_contract_bucket_split_ledger.md`; many untracked `docs/plans/20260526T051948Z_tstclu411c_logs/*` logs existed.
- DayOA repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
- DayOA branch: `codex/tstclu411c-hybrid-env-python`
- DayOA HEAD at baseline: `398ca8b0d457ff1b0c9fa350b52961db9185404d`
- DayOA status: dirty before this change with many pre-existing modified fixtures, docs, scripts, workflow files, and untracked plan/spec artifacts.
- Source evidence: active DayEC defaults and tests use `/fsx/staging/staged_sample_data`; active code has no normal destination for `/fsx/staging/staged`.
- Live S3 evidence: old `data/staged/` newest sampled objects were from `2026-04-14` and looked like copied Illumina run-folder artifacts; old `data/staged_sample_data/` newest sampled objects were from `2026-05-26` and contained `remote_stage_*` sample staging outputs.
- Live AWS scope: no S3 copy, delete, lifecycle mutation, or real cluster creation is approved in this request.
- Assumption: this is a hard contract cutover. New generated staging must use `/fsx/staging/staged_external_sequencing_data`; old `/fsx/staging/staged_sample_data` and `/fsx/staging/staged` stage targets must fail hard rather than aliasing.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DYEC-SED-001 | Orchestration | Record Gate 0 inventory and scope before edits. | SUCCESS | plan_amendment | Gate 0 | orchestrator | This ledger plus companion DayOA ledger. |  | Gate 0 recorded before implementation. |
| DYEC-SED-002 | Staging CLI | Rename active stage target default from `staged_sample_data` to `staged_external_sequencing_data`. | SUCCESS | feature_implementation | Gate 2 | orchestrator | Updated `daylily_ec/stage_samples.py`, `daylily_ec/cli.py`, `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`, and packaged headnode helper defaults to `/fsx/staging/staged_external_sequencing_data`. |  | Active generated remote stages now use `/fsx/staging/staged_external_sequencing_data/remote_stage_*`. |
| DYEC-SED-003 | Staging guardrails | Reject `/fsx/staging/staged_sample_data`, `/fsx/staging/staged`, `/fsx/staged_sample_data`, and `/fsx/staged` as stage targets. | SUCCESS | contract_test | Gate 2 | orchestrator | `tests/test_stage_samples_from_local_to_headnode.py::test_retired_staging_paths_are_rejected`; `source ./activate && python -m pytest -q tests/test_stage_samples_from_local_to_headnode.py tests/test_ont_fastq_prefix_staging.py tests/test_staging_examples.py tests/test_cli_registry_v2.py tests/test_ssm_e2e_runner.py tests/test_headnode_init.py tests/test_s3.py` passed, 219 tests. |  | Retired paths fail hard rather than aliasing. |
| DYEC-SED-004 | Docs/config/tests | Update active DayEC docs, templates, repository catalog examples, packaged payload, and tests to the new staging subpath. | SUCCESS | feature_implementation | Gate 5 | orchestrator | Updated README, quickstart/operations/CLI docs, active config catalogs, resource templates, staging examples, and test fixtures; active sweep found retired names only in rejection tests/constants after excluding historical command-catalog reports. |  | Historical reports retain old paths as evidence of prior runs. |
| DYEC-SED-005 | Live S3 prefixes | Rename or delete existing S3 prefixes. | BLOCKED | feature_implementation | Gate 5 | orchestrator | Existing copied prefixes remain `s3://lsmc-dayoa-staging-usw2/staged/` and `s3://lsmc-dayoa-staging-usw2/staged_sample_data/`. | S3 rename requires copy plus destructive delete; no exact source/destination copy approval or destructive delete approval was given in this request. | Blocked pending explicit live S3 copy/delete decision. |

## Terminal Report

- Status counts: `SUCCESS=4`, `BLOCKED=1`, `OPEN=0`, `IN_PROGRESS=0`, `ATTEMPTING_BUGFIX=0`, `FAIL=0`.
- Validation:
  - `source ./activate && python -m pytest -q tests/test_stage_samples_from_local_to_headnode.py tests/test_ont_fastq_prefix_staging.py tests/test_staging_examples.py tests/test_cli_registry_v2.py tests/test_ssm_e2e_runner.py tests/test_headnode_init.py tests/test_s3.py` passed, 219 tests.
  - Active DayEC sweep for retired staging spellings found only rejection tests/constants and historical command-catalog reports.
- Terminal acceptance met for code/docs/tests. Live S3 prefix rename/delete remains blocked pending explicit approval.
