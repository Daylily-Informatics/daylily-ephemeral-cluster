# Bjuice prevalence E1/E2 benchmark tuning ledger

Created: 2026-08-18T05:44:54Z

## Control ledger

Controlling request: copy the exported E1 and E2 combined benchmark TSVs locally; reconcile planned versus observed rules; calculate costs; identify CPU, memory, and I/O tuning candidates; compare `us-west-2c` (E1) and `us-west-2d` (E2); write `docs/candidate-pre-pre-release-tuning.md`.

Ledger path: `docs/plans/20260818T054454Z_bjuice_preval_benchmark_tuning_ledger.md`

### Gate 0 baseline

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch `codex/dayoa-15-0-18-pinned` at `8a7c5348` (`18.0.28`); no tracked or staged changes.
- Pre-existing untracked paths are preserved: `.playwright-cli/`, `TrusSV/`, prior `docs/plans/` ledgers/artifacts, and `tmp/dayoa-ont-headnode-proof/`.
- Authoritative E1 export: `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022-bjuice-preval6-15014-dry-20260817t112900z/daylily-omics-analysis/` (`us-west-2c`, 6 AUs).
- Authoritative E2 export: `s3://lsmc-ssf-sequencing-data/derived/pre-rel-18025/prerel18025-bjuice-preval14-15015-dry-20260817t151033z/daylily-omics-analysis/` (`us-west-2d`, 14 AUs).
- Downloaded only benchmark TSVs and preserved planning/configuration evidence under `/tmp/bjuice-pre-pre-release-tuning-20260818/`; no S3, FSx, controller, Slurm, or catalog state is changed.
- The relevant summary files are `results/day/hg38/reports/benchmarks_summary.tsv`; raw `benchmarks.tsv`, run configs, AU manifests, planned Mermaid graphs, and the exported workflow catalog are local comparison evidence.

| ID | Area | Requirement | Status | Category | Approval gate | Owner | Evidence | Root cause | Terminal note |
|---|---|---|---|---|---|---|---|---|---|
| DATA-001 | Exported inputs | Validate both benchmark summaries against raw benchmark rows and preserve exact local copies. | IN_PROGRESS | contract_test | Gate 1 | Codex | Local copies under `/tmp/bjuice-pre-pre-release-tuning-20260818/`. |  |  |
| PLAN-001 | Planned versus observed rules | Derive the execution-plan rule universe and identify missing/extra rules without treating optional or conditional rules as failures. | OPEN | contract_test | Gate 1 | Codex | Preserved plan graphs, config, AU manifests, and workflow catalog. |  |  |
| COST-001 | Task cost | Sum valid task costs per execution and combined; report the requested total divided by 14. | OPEN | contract_test | Gate 1 | Codex | Benchmark task-cost columns. |  |  |
| TUNE-001 | CPU, memory, and I/O | Identify only evidence-supported over/under-resourced or I/O-limited rule families with bounded suggested fixes. | OPEN | contract_test | Gate 1 | Codex | Benchmark CPU, memory, I/O, wall-time, and instance fields. |  |  |
| AZ-001 | AZ/instance efficiency | Compare comparable observed rule/instance cohorts between E1 `us-west-2c` and E2 `us-west-2d`; do not infer an AZ effect from different input cohorts. | OPEN | contract_test | Gate 1 | Codex | Captured instance, cost, runtime, and resource fields. |  |  |
| DOC-001 | Candidate tuning note | Write `docs/candidate-pre-pre-release-tuning.md` with data provenance, results, limitations, and no unapproved production changes. | OPEN | historical_docs_only | Gate 5 | Codex | User-requested durable report. |  |  |
