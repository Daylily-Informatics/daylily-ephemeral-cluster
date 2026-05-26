# Split-DRA New Cluster Validation Ledger

Controlling plan: user-provided "Multi-Agent Ledger Plan: Brand-New Split-DRA Cluster Validation" in thread.
Ledger path: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260526T113326Z_splitdra_new_cluster_validation_ledger.md`
Cluster config artifact: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260526T113326Z_splitdra_smoke_cluster_request.yaml`

## Gate 0 Baseline

- Repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
- Branch: `codex/analysis-id-export-catalog-validation`
- HEAD: `36ae75a0e695298628704859e7deac87267d3d0d`
- Initial status: clean before this ledger/config artifact creation.
- AWS profile/account: `AWS_PROFILE=lsmc`, account `108782052779`, caller `arn:aws:iam::108782052779:root`
- Region/AZ: `us-west-2`, `us-west-2d`
- Cluster name: `splitdra-smoke-20260526`
- Cluster-name availability: `pcluster describe-cluster --region us-west-2 --cluster-name splitdra-smoke-20260526` reported cluster does not exist.
- Baseline LSMC bucket public posture:
  - `lsmc-dayoa-references-usw2`: public access block all `false`, policy status public `true`, default encryption `AES256`, no tag set.
  - `lsmc-dayoa-control-data-usw2`: public access block all `false`, policy status public `true`, default encryption `AES256`, no tag set.
  - `lsmc-dayoa-runtime-assets-usw2`: public access block all `false`, policy status public `true`, default encryption `AES256`, no tag set.
  - `lsmc-dayoa-staging-usw2`: public access block all `false`, policy status public `true`, default encryption `AES256`, no tag set.
  - `lsmc-dayoa-analysis-results-usw2`: public access block all `false`, policy status public `true`, default encryption `AES256`, no tag set.
  - `lsmc-ssf-sequencing-data`: public access block all `true`, no bucket policy, default encryption `AES256`, tagged `aws-parallelcluster-project=raw-sequence-data`.
- Baseline live DRA inventory: existing LSMC clusters still have `/data/` DRAs pointing to `s3://lsmc-dayoa-omics-analysis-us-west-2/data/`; run DRAs point to `s3://lsmc-ssf-sequencing-data/basecalls/...`; no split-role static DRA exists yet for the new cluster because it does not exist.
- Approval interpretation: the user's "PLEASE IMPLEMENT THIS PLAN" approves live bucket policy/tag mutations and real cluster creation for this validation. It does not provide the second explicit approval required for destructive teardown.
- Live scope exclusions: no SSE-KMS migration, no lifecycle rules, no S3 deletion, no legacy prefix cleanup, no Daylily bucket mutation, and no live cluster deletion without a second destructive approval.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| SPLITDRA-001 | Orchestration | Gate 0 inventory, dirty state, and live AWS baseline. | SUCCESS | plan_amendment | Gate 0 | orchestrator | This ledger; `git status --short --branch`; `aws sts get-caller-identity --profile lsmc`; baseline bucket/DRA reads. |  | Gate 0 recorded before live mutation and cluster creation. |
| SPLITDRA-002 | Bucket security | Keep references public; make LSMC control-data, runtime-assets, staging, analysis-results, and raw sequencing private with block-public-access on; verify anonymous access fails for private buckets. | OPEN | feature_implementation | Gate 5 | Agent A | Pending live mutation and verification. |  |  |
| SPLITDRA-003 | Bucket controls | Verify encryption, add/verify `aws-parallelcluster-project` tags on new split buckets, and confirm lifecycle rules absent. | OPEN | feature_implementation | Gate 5 | Agent B | Pending live mutation and verification. |  |  |
| SPLITDRA-004 | Config/preflight | Render explicit split-role config and run local tests plus DayEC preflight. | OPEN | contract_test | Gate 5 | Agent C | Config artifact created at `docs/plans/20260526T113326Z_splitdra_smoke_cluster_request.yaml`; tests/preflight pending. |  |  |
| SPLITDRA-005 | Cluster create | Create real cluster `splitdra-smoke-20260526`. | OPEN | feature_implementation | Gate 5 | Agent C | Pending `dyec create`. |  |  |
| SPLITDRA-006 | Static DRAs | Verify live FSx DRAs exactly cover `/references/`, `/control_data/`, `/runtime_assets/`, and `/staging/` against split buckets; verify no `/data/` DRA on new FSx. | OPEN | contract_test | Gate 5 | Agent D | Pending cluster create. |  |  |
| SPLITDRA-007 | Headnode readiness | Validate role-root paths, runtime assets, budget tags, and no accepted `/fsx/data` contract via DayEC SSM helpers as `ubuntu`. | OPEN | contract_test | Gate 5 | Agent E | Pending cluster create. |  |  |
| SPLITDRA-008 | Staging | Stage minimal sample manifest under `/fsx/staging/staged_external_sequencing_data/remote_stage_*`; verify retired paths fail. | OPEN | contract_test | Gate 5 | Agent F | Pending cluster create and readiness. |  |  |
| SPLITDRA-009 | Run DRA | Create and verify one read-only run DRA from `lsmc-ssf-sequencing-data` under `/fsx/run_dir_mounts/<mount_id>`. | OPEN | contract_test | Gate 5 | Agent F | Pending cluster create and readiness. |  |  |
| SPLITDRA-010 | Smoke workflow | Launch one small smoke workflow if staged inputs validate; capture status/logs and triage failure. | OPEN | contract_test | Gate 5 | Agent G | Pending staging validation. |  |  |
| SPLITDRA-011 | Export DRA | Export only the completed analysis directory to `s3://lsmc-dayoa-analysis-results-usw2/validation/splitdra-smoke-20260526/ubuntu/splitdra-smoke-20260526/`; verify receipt, S3 objects, and detached export DRA. | OPEN | contract_test | Gate 5 | Agent G | Pending smoke workflow. |  |  |
| SPLITDRA-012 | Daylily audit | Audit Daylily split buckets remain empty and contain no LSMC/RCRF object content; do not use them in LSMC cluster test. | OPEN | contract_test | Gate 5 | Agent H | Pending audit. |  |  |
| SPLITDRA-013 | Teardown | Dry-run teardown; keep live delete blocked until second destructive approval. | OPEN | active_product_contract | Gate 5 | orchestrator | Pending cluster lifecycle outcome. | Destructive cluster deletion requires a second explicit approval after exact effect is restated. |  |

## Terminal Report

- Status counts: `SUCCESS=1`, `OPEN=12`, `BLOCKED=0`, `IN_PROGRESS=0`, `ATTEMPTING_BUGFIX=0`, `FAIL=0`.
- Terminal acceptance pending.
