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
- Live AWS scope: no live S3 copy, bucket creation, lifecycle change, destructive action, or real cluster create is approved in this thread.
- Assumption: active contracts move to `/fsx/references`, `/fsx/control_data`, `/fsx/runtime_assets`, and `/fsx/staging`; no `/fsx/references` compatibility mount or fallback bucket discovery is allowed.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DYEC-001 | Orchestration | Record Gate 0 inventory and companion DayOA ledger before runtime edits. | IN_PROGRESS | plan_amendment | Gate 0 | orchestrator | This ledger plus companion DayOA ledger. |  |  |
| DYEC-002 | Config/preflight | Replace single `s3_bucket_name` selection with explicit reference, control-data, runtime-assets, stage, and boot S3 role config. | OPEN | feature_implementation | Gate 2 | Agent A |  |  |  |
| DYEC-003 | Cluster template | Render four static read-only DRAs for `/references/`, `/control_data/`, `/runtime_assets/`, and `/staging/`; derive S3 IAM access from role buckets. | OPEN | feature_implementation | Gate 2 | Agent A |  |  |  |
| DYEC-004 | Setup/readiness | Update setup script and headnode readiness from `/fsx/references` to role roots. | OPEN | feature_implementation | Gate 2 | Agent B |  |  |  |
| DYEC-005 | Runtime mounts | Extend existing `dyec mounts` run-DRA implementation with purpose-aware roots and overlap rejection across all role roots. | OPEN | feature_implementation | Gate 2 | Agent C |  |  |  |
| DYEC-006 | Staging CLI | Move samples staging to explicit role buckets and default `/fsx/staging/staged_sample_data`; reject `/data` and `/fsx/references`. | OPEN | feature_implementation | Gate 2 | Agent C |  |  |  |
| DYEC-007 | Budget/control files | Move budget-tag path out of references into runtime assets. | OPEN | feature_implementation | Gate 2 | Agent B |  |  |  |
| DYEC-008 | Tests | Update focused tests for renderer, S3 role preflight, setup/readiness, mounts, and staging. | OPEN | contract_test | Gate 5 | Agent E |  |  |  |
| DYEC-009 | Docs | Update DayEC docs/examples away from overloaded reference bucket and `/fsx/references`. | OPEN | feature_implementation | Gate 5 | Agent E |  |  |  |
| DYEC-010 | Live AWS migration | Bucket creation/copy/lifecycle/real cluster validation. | BLOCKED | feature_implementation | Gate 5 | orchestrator | User approved implementation only; no live S3 mutation approval was provided. | Explicit live AWS approval and exact source/destination URIs required. | Terminal blocked by approval gate. |

## Terminal Report

Pending implementation.
