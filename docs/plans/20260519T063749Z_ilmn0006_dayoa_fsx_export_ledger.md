# ILMN 0006 DayOA Directory FSx-to-S3 Export Ledger

Date opened: 2026-05-19T06:37:49Z

## Control

Controlling request: start an FSx-to-S3 export of the Illumina run 0006 DayOA directory and report back while the export runs in the background.

Ledger path: `/Users/jmajor/projects/daylily/daylily-ephemeral-cluster/docs/plans/20260519T063749Z_ilmn0006_dayoa_fsx_export_ledger.md`

Execution scope:
- Local repo: `/Users/jmajor/projects/daylily/daylily-ephemeral-cluster`
- AWS profile: `lsmc`
- AWS region: `us-west-2`
- Cluster: `may26-d`
- FSx filesystem: `fs-0c43ddf4b70dc87d8`
- Export method: AWS CLI single data-repository task, `EXPORT_TO_REPOSITORY`
- FSx path: `analysis_results/ubuntu/ilmn_0006_align_dedup_alignstats_20260517T185626Z/daylily-omics-analysis`
- Expected S3 URI: `s3://lsmc-dayoa-omics-analysis-us-west-2/FSxLustre20260515T103052Z/analysis_results/ubuntu/ilmn_0006_align_dedup_alignstats_20260517T185626Z/daylily-omics-analysis`

## Gate 0 Baseline

- Local repo status: `## codex/docs-plans-ledgers...origin/codex/docs-plans-ledgers` with existing untracked working artifacts.
- Prior 0006 export evidence: `tmp-export/ilmn0006-full-repo-20260518T135640Z/fsx_export.yaml` exported parent path `analysis_results/ubuntu/ilmn_0006_align_dedup_alignstats_20260517T185626Z` to the same S3 root with FSx filesystem `fs-0c43ddf4b70dc87d8`.
- User direction from prior ledger: use old-fashioned AWS CLI single-DRA export path rather than `daylily-ec export`.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | DayEC/AWS | Record export target, prior FSx/S3 mapping, local repo state, and user-directed export method. | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 Baseline section. |  | Baseline recorded before live export task creation. |
| EXP-001 | AWS FSx | Create asynchronous single-DRA FSx export task for the 0006 `daylily-omics-analysis` directory. | SUCCESS | feature_implementation | Gate 1 | orchestrator | AWS CLI `aws fsx create-data-repository-task --file-system-id fs-0c43ddf4b70dc87d8 --type EXPORT_TO_REPOSITORY --paths analysis_results/ubuntu/ilmn_0006_align_dedup_alignstats_20260517T185626Z/daylily-omics-analysis --report Enabled=true,Path=s3://lsmc-dayoa-omics-analysis-us-west-2/FSxLustre20260515T103052Z/daylily-monitor/20260519T063749Z/export-report,Format=REPORT_CSV_20191124,Scope=FAILED_FILES_ONLY` created task `task-09b26c2c4b85deb91`. Receipt dir: `tmp-export/ilmn0006-dayoa-dir-20260519T063749Z`. |  | Export task started asynchronously. |
| STATUS-001 | AWS FSx | Capture initial task lifecycle/counts and report back without waiting for terminal completion. | SUCCESS | legitimate_safety_handling | Gate 1 | orchestrator | Initial describe: `PENDING`, counts `null`. Follow-up describe after 8 seconds: `EXECUTING`, `total=0`, `succeeded=0`, `failed=0`. |  | Task is running in the background; no terminal completion check was requested in this step. |

## Current Export Status

- Task id: `task-09b26c2c4b85deb91`
- Lifecycle at last poll: `EXECUTING`
- Export source path: `analysis_results/ubuntu/ilmn_0006_align_dedup_alignstats_20260517T185626Z/daylily-omics-analysis`
- Expected S3 URI: `s3://lsmc-dayoa-omics-analysis-us-west-2/FSxLustre20260515T103052Z/analysis_results/ubuntu/ilmn_0006_align_dedup_alignstats_20260517T185626Z/daylily-omics-analysis`
- Export report path: `s3://lsmc-dayoa-omics-analysis-us-west-2/FSxLustre20260515T103052Z/daylily-monitor/20260519T063749Z/export-report`
- Local receipt directory: `tmp-export/ilmn0006-dayoa-dir-20260519T063749Z`
