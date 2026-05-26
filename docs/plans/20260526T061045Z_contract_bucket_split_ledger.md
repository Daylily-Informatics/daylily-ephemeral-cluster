# Contract Bucket Split Execution Ledger

Controlling plan: user-provided "Contract-Based DayOA Buckets And Mounts" plan in thread.
Ledger path: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260526T061045Z_contract_bucket_split_ledger.md`
Companion DayOA ledger: `/Users/jmajor/projects/daylily/daylily-omics-analysis/docs/plans/20260526T061045Z_contract_bucket_path_cutover_ledger.md`

## Gate 0 Baseline

- DayEC repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
- DayEC branch: `codex/analysis-id-export-catalog-validation`
- DayEC HEAD: `66ee930a045d59ed1a55507a9d10daf2d6da534c`
- DayEC status: dirty before this work; pre-existing modified files include `config/day_cluster/post_install_ubuntu_combined.sh`, `config/daylily_available_repositories.yaml`, `daylily_ec/repositories.py`, payload mirrors, `tests/test_headnode_init.py`, and `tests/test_repository_catalog.py`; many untracked docs/plans/log artifacts also existed.
- DayOA repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
- DayOA branch: `codex/tstclu411c-hybrid-env-python`
- DayOA HEAD: `bc27487d62d190efe47ba5933a574812426a2b39`
- DayOA status: dirty before this work; pre-existing modified docs/plans and untracked HG003 ledger/report files existed.
- Sweep: `rg -n "/fsx/references|/fsx/staging/staged_sample_data|reference-bucket|reference_bucket|s3_bucket_name|REGSUB_S3_BUCKET" daylily_ec config tests docs README.md pyproject.toml | wc -l` -> `1282`
- DayOA sweep: `rg -n "/fsx/references|/fsx/staging/staged_sample_data|reference-bucket|reference_bucket|genomic_data|cached_envs|staged_sample_data" README.md dyoainit config workflow tests docs bin | wc -l` -> `657`
- Live AWS scope at Gate 0: no live S3 copy, bucket creation, lifecycle change, destructive action, or real cluster create was approved at initial implementation time.
- Assumption: active contracts move to `/fsx/references`, `/fsx/control_data`, `/fsx/runtime_assets`, and `/fsx/staging`; no `/fsx/references` compatibility mount or fallback bucket discovery is allowed.

## Live AWS Amendment 20260526T071153Z

- User approved live non-destructive S3 bucket creation in `us-west-2` with `AWS_PROFILE=lsmc` for `lsmc-dayoa-references-usw2`, `lsmc-dayoa-control-data-usw2`, `lsmc-dayoa-runtime-assets-usw2`, `lsmc-dayoa-staging-usw2`, and `lsmc-dayoa-analysis-results-usw2`.
- User approved the same new Daylily-owned public reference versions with `AWS_PROFILE=daylily`; implemented as `daylily-dayoa-references-usw2`, `daylily-dayoa-control-data-usw2`, `daylily-dayoa-runtime-assets-usw2`, `daylily-dayoa-staging-usw2`, and `daylily-dayoa-analysis-results-usw2`.
- Source permission contract inspected from `daylily-omics-analysis-references-public` with `AWS_PROFILE=daylily`: region `us-west-2`, public policy status `true`, public access block flags all `false`, and ownership `BucketOwnerEnforced`.
- LSMC target policies were rewritten to target each LSMC bucket ARN, use LSMC account `108782052779` as the owner write exception, and use Daylily account `670484050738` as the cross-account writer.
- Daylily target policies were public read/list policies with Daylily account `670484050738` as the owner write exception; the copied cross-account LSMC statement was omitted to scrub LSMC/RCRF references.
- Anonymous public-list spot checks succeeded with `aws s3 ls s3://lsmc-dayoa-references-usw2 --no-sign-request --region us-west-2` and `aws s3 ls s3://daylily-dayoa-references-usw2 --no-sign-request --region us-west-2` returning exit 0 on empty buckets.
- Explicitly not performed: object copy, lifecycle policy changes, bucket deletion, real cluster creation, or S3 prefix population.

## Live AWS Amendment 20260526T072350Z

- User requested completion of the remaining live migration work and encryption enablement for the DayOA split buckets, Dewey buckets, and LSMC sequencing bucket.
- Encryption inventory verified default server-side encryption is already active on `lsmc-dayoa-references-usw2`, `lsmc-dayoa-control-data-usw2`, `lsmc-dayoa-runtime-assets-usw2`, `lsmc-dayoa-staging-usw2`, `lsmc-dayoa-analysis-results-usw2`, `daylily-dayoa-references-usw2`, `daylily-dayoa-control-data-usw2`, `daylily-dayoa-runtime-assets-usw2`, `daylily-dayoa-staging-usw2`, `daylily-dayoa-analysis-results-usw2`, `lsmc-ssf-sequencing-data`, `lsmc-dewey-0`, and `daylily-dewey-0`.
- All inspected buckets report default `SSEAlgorithm=AES256` with `BlockedEncryptionTypes=["SSE-C"]`; `lsmc-ssf-sequencing-data`, `lsmc-dewey-0`, and `daylily-dewey-0` also report `BucketKeyEnabled=true`.
- KMS alias inventory found no DayOA/clinical customer-managed KMS key in the LSMC account; Daylily has `alias/trail-daylily-ref-s3`, which is trail-specific, not a general DayOA data key.
- Source inventory confirmed `daylily-omics-analysis-references-public` has `cluster_boot_config/` and `data/`; `lsmc-dayoa-omics-analysis-us-west-2` mixes top-level FASTQs/manifests, `cluster_boot_config/`, `data/genomic_data/`, `data/cached_envs/`, `data/cram_data/`, `data/ilmn_kitefastqs/`, `data/pacbio/`, `data/staged/`, `data/staged_sample_data/`, `data/tool_specific_resources/`, `data/ug/`, `analysis_results/`, and other operational/result prefixes.
- Bulk copy remains blocked pending exact source and destination URI approval because a blind copy would preserve the overloaded legacy layout. Lifecycle policy changes, bucket deletion, and cluster creation remain blocked pending a separate confirmation after exact effects are stated.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DYEC-001 | Orchestration | Record Gate 0 inventory and companion DayOA ledger before runtime edits. | SUCCESS | plan_amendment | Gate 0 | orchestrator | This ledger plus `/Users/jmajor/projects/daylily/daylily-omics-analysis/docs/plans/20260526T061045Z_contract_bucket_path_cutover_ledger.md`. |  | Gate 0 and row ownership recorded before implementation. |
| DYEC-002 | Config/preflight | Replace single `s3_bucket_name` selection with explicit reference, control-data, runtime-assets, stage, and boot S3 role config. | SUCCESS | feature_implementation | Gate 2 | Agent A | `daylily_ec/aws/s3.py`, `daylily_ec/workflow/create_cluster.py`, `daylily_ec/config/models.py`, `config/daylily_ephemeral_cluster_template.yaml`; `pytest -q` -> 882 passed, 7 skipped. |  | Explicit role config and hard-fail role preflight replaced bucket discovery on create path. |
| DYEC-003 | Cluster template | Render four static read-only DRAs for `/references/`, `/control_data/`, `/runtime_assets/`, and `/staging/`; derive S3 IAM access from role buckets. | SUCCESS | feature_implementation | Gate 2 | Agent A | `config/day_cluster/*.yaml`, `config/day_cluster/regions/all_clusters.yaml`, payload mirrors; render/parse check -> 5 cluster templates with all four role DRAs. |  | Primary and alternate cluster templates use contract role DRAs and role bucket IAM placeholders. |
| DYEC-004 | Setup/readiness | Update setup script and headnode readiness from `/fsx/data` to role roots. | SUCCESS | feature_implementation | Gate 2 | Agent B | `config/day_cluster/post_install_ubuntu_combined.sh`, payload mirror, `daylily_ec/headnode_readiness.py`; full pytest passed. |  | Setup/readiness now validates `/fsx/references`, `/fsx/control_data`, `/fsx/runtime_assets`, and `/fsx/staging`. |
| DYEC-005 | Runtime mounts | Extend existing `dyec mounts` run-DRA implementation with purpose-aware roots and overlap rejection across all role roots. | SUCCESS | feature_implementation | Gate 2 | Agent C | `daylily_ec/run_mounts.py`, `daylily_ec/cli.py`, `tests/test_run_mounts.py`; full pytest passed. |  | `mounts create/list` supports purpose-aware paths while preserving run mounts under `/fsx/run_dir_mounts`. |
| DYEC-006 | Staging CLI | Move samples staging to explicit role buckets and default `/fsx/staging/staged_sample_data`; reject `/data` and `/fsx/data`. | SUCCESS | feature_implementation | Gate 2 | Agent C | `daylily_ec/stage_samples.py`, `daylily_ec/cli.py`, `tests/test_stage_samples_from_local_to_headnode.py`; full pytest passed. |  | Staging requires all four role buckets and rejects legacy `/data` and `/fsx/data`. |
| DYEC-007 | Budget/control files | Move budget-tag path out of references into runtime assets. | SUCCESS | feature_implementation | Gate 2 | Agent B | `daylily_ec/aws/budgets.py`, `daylily_ec/headnode.py`, `config/day_cluster/sbatch`, payload mirror; `tests/test_budgets.py` included in full pytest. |  | Budget tags now live under `budget_tags/` in runtime assets and `/fsx/runtime_assets/budget_tags/...` on FSx. |
| DYEC-008 | Tests | Update focused tests for renderer, S3 role preflight, setup/readiness, mounts, and staging. | SUCCESS | contract_test | Gate 5 | Agent E | `python -m pytest -q` -> 882 passed, 7 skipped; py_compile selected DayEC modules passed. |  | Contract tests cover role preflight, render keys, DRA templates, mounts, staging, readiness, budgets, and workflow create. |
| DYEC-009 | Docs | Update DayEC docs/examples away from overloaded reference bucket and `/fsx/data`. | SUCCESS | feature_implementation | Gate 5 | Agent E | `README.md`, `docs/aws_setup.md`, `docs/dra_fsx_strategy.md`, `docs/cli_reference.md`, `examples/staging/README.md`; active sweep excludes only intentional negative guards. |  | Active docs/examples require four explicit role buckets and describe the split contract. |
| DYEC-010 | Live AWS migration | Data copy/lifecycle/real cluster validation after bucket creation. | BLOCKED | feature_implementation | Gate 5 | orchestrator | Bucket creation is complete under `DYEC-011`; no object copy, lifecycle policy mutation, bucket deletion, or real cluster create was requested or approved. | Explicit live AWS approval and exact source/destination URIs are still required for data copy/lifecycle/cluster actions. | Terminal blocked for remaining live migration actions after bucket creation. |
| DYEC-011 | Live AWS buckets | Create and configure contract role buckets in `us-west-2` for LSMC and scrubbed Daylily public counterparts. | SUCCESS | feature_implementation | Gate 5 | orchestrator | `AWS_PROFILE=lsmc` created `lsmc-dayoa-references-usw2`, `lsmc-dayoa-control-data-usw2`, `lsmc-dayoa-runtime-assets-usw2`, `lsmc-dayoa-staging-usw2`, `lsmc-dayoa-analysis-results-usw2`; `AWS_PROFILE=daylily` created `daylily-dayoa-references-usw2`, `daylily-dayoa-control-data-usw2`, `daylily-dayoa-runtime-assets-usw2`, `daylily-dayoa-staging-usw2`, `daylily-dayoa-analysis-results-usw2`; verification showed all ten buckets in `us-west-2`, public policy status `true`, public access block flags all `false`, and ownership `BucketOwnerEnforced`; Daylily policies contained no `lsmc`, `rcrf`, or `108782052779` references. |  | Live bucket creation and non-destructive policy configuration completed. |
| DYEC-012 | Live AWS encryption | Ensure default bucket encryption is active on DayOA split buckets plus Dewey and LSMC sequencing buckets. | SUCCESS | feature_implementation | Gate 5 | orchestrator | `get-bucket-encryption` verified `SSEAlgorithm=AES256` and `BlockedEncryptionTypes=["SSE-C"]` for all ten DayOA split buckets, `lsmc-ssf-sequencing-data`, `lsmc-dewey-0`, and `daylily-dewey-0`; no missing encryption configuration was found. |  | Encryption was already enabled; no bucket encryption mutation was required. |

## Terminal Report

- Status counts: `SUCCESS=11`, `BLOCKED=1`, `OPEN=0`, `IN_PROGRESS=0`, `ATTEMPTING_BUGFIX=0`, `FAIL=0`.
- Local validation: `source ./activate && python -m pytest -q` -> `882 passed, 7 skipped`; py_compile of edited DayEC modules passed; raw and rendered YAML parse check for 5 cluster templates passed.
- Sweeps: active DayEC source has no `s3_bucket_name`, `REGSUB_S3_BUCKET_NAME`, `REGSUB_S3_BUCKET_REF`, `/data/staged_sample_data`, or old reference-bucket object wording outside archived/legacy/quarantine paths; remaining `/fsx/data` strings are explicit rejection guards and negative tests.
- Diff hygiene: `git diff --check -- . ':(exclude)docs/plans/20260526T051948Z_tstclu411c_logs/run_mounts_create_remaining.log'` passed. The excluded log had pre-existing trailing whitespace outside this work.
- Live AWS bucket creation and encryption verification are complete for the approved buckets. S3 object copy, lifecycle policy changes, deletion, and real cluster create remain blocked and require separate approval with exact source and destination URIs/effects.
- All ledger rows are terminal. The local implementation objective plus approved live bucket-creation/encryption-verification objectives are complete; the broader live migration objective is not complete because `DYEC-010` remains blocked by approval gate.
