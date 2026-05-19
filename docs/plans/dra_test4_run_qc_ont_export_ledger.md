# dra-test4 run_qc_ont_all FSx Export Ledger

Date: 2026-05-18

## Objective

Export the dra-test4 headnode path `/fsx/analysis_results/ubuntu/run_qc_ont_all` to the active DayOA us-west-2 bucket at `s3://lsmc-dayoa-omics-analysis-us-west-2/analysis_results/ubuntu/run_qc_ont_all/` using the explicit `dyec export` DRA workflow.

## Gate 0: Inventory Freeze

- Controlling SOP: `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`
- Ledger path: `docs/plans/dra_test4_run_qc_ont_export_ledger.md`
- Repo path: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
- Branch/status: `main...origin/main`; pre-existing dirty files: `README.md`, `daylily_ec/cli.py`, `docs/LSMC_run_directory_mounting_run_analysis_spec.md`, `docs/cli_reference.md`, `docs/dra_fsx_strategy.md`, `docs/operations.md`, `docs/overview.md`, `docs/quickest_start.md`, `tests/test_run_mounts.py`
- Activation: `source ./activate` resolved `CONDA_DEFAULT_ENV=DAY-EC`, `dyec=/Users/jmajor/miniconda3/envs/DAY-EC/bin/dyec`
- Cluster inventory: `AWS_PROFILE=lsmc AWS_REGION=us-west-2 pcluster list-clusters --region us-west-2` showed `dra-test4` as `CREATE_COMPLETE`
- Headnode info: `dyec --json headnode info --profile lsmc --region us-west-2 --cluster dra-test4` showed headnode `i-0d85f5c6569c7e475`, state `running`, compute fleet `RUNNING`
- FSx inventory: `aws fsx describe-file-systems` for `parallelcluster:cluster-name=dra-test4` resolved `fs-0bcf5a60d9b48f03e`, lifecycle `AVAILABLE`, `SCRATCH_2`, 2400 GiB
- Bucket inventory: `aws s3api head-bucket --bucket lsmc-dayoa-omics-analysis-us-west-2` succeeded with bucket region `us-west-2`
- Existing destination inventory: `aws s3api list-objects-v2 --bucket lsmc-dayoa-omics-analysis-us-west-2 --prefix analysis_results/ubuntu/run_qc_ont_all/ --max-items 10` returned no contents
- Existing DRA inventory for `fs-0bcf5a60d9b48f03e`: active run mounts under `/run_dir_mounts/`, active `/data/`, active `/analysis_results/ubuntu/run_qc_illumina_all/`, and misconfigured `/analysis_results/ubuntu/illumina_run_qc/`; no overlap with `/analysis_results/ubuntu/run_qc_ont_all/`
- Source path proof: SSM via `daylily_ec.aws.ssm.run_shell` as `ubuntu` verified `/fsx/analysis_results/ubuntu/run_qc_ont_all` exists, owner `ubuntu:ubuntu`, mtime `2026-05-18 08:49:42 +0000`, 6 top-level entries, 192 files and 23 directories at max depth 4, with `/fsx` at 42G used of 2.2T

## Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Baseline | Record repo, live cluster, FSx, bucket, destination, DRA, and source-path inventory before export. | `SUCCESS` | `legitimate_safety_handling` | Gate 0 | orchestrator | Gate 0 section above. |  | Baseline complete before live export. |
| PRE-001 | Source | Prove the requested headnode path exists on dra-test4 as `ubuntu`. | `SUCCESS` | `legitimate_safety_handling` | Gate 0 | orchestrator | SSM command `a8352ab0-16f6-49bc-b54e-81927466aa0d`; source directory exists with 6 top-level entries and 192 files at max depth 4. |  | Requested source path is present. |
| PRE-002 | Destination | Resolve and validate the explicit DayOA us-west-2 destination prefix. | `SUCCESS` | `legitimate_safety_handling` | Gate 0 | orchestrator | `s3://lsmc-dayoa-omics-analysis-us-west-2/analysis_results/ubuntu/run_qc_ont_all/`; bucket region `us-west-2`; no listed existing objects under the prefix. |  | Destination is explicit and empty at preflight. |
| EXP-001 | Export | Run explicit `dyec export` from source path to destination S3 prefix and preserve `fsx_export.yaml`. | `SUCCESS` | `feature_implementation` | Gate 1 | orchestrator | First `dyec export` wrote failure receipt `reports/fsx_exports/dra-test4_run_qc_ont_all_20260518T085756Z/fsx_export.yaml`; focused fix moved report path under the export destination; `pytest tests/test_export.py -q -> 17 passed`; retry wrote success receipt `reports/fsx_exports/dra-test4_run_qc_ont_all_20260518T090219Z/fsx_export.yaml`. |  | Export task `task-09dd75221119a5311` completed `SUCCEEDED`; source `/analysis_results/ubuntu/run_qc_ont_all/` exported to `s3://lsmc-dayoa-omics-analysis-us-west-2/analysis_results/ubuntu/run_qc_ont_all/`. |
| VER-001 | Verification | Verify export receipt success, DRA detach, and S3 object presence after export. | `SUCCESS` | `legitimate_safety_handling` | Gate 5 | orchestrator | Receipt status `success`, `task_lifecycle: SUCCEEDED`, `detached: true`, `detach_lifecycle: DELETED`; `describe-data-repository-associations` for `dra-004d5751b19bf2eae` and for `/analysis_results/ubuntu/run_qc_ont_all/` returned no active associations; S3 prefix contains 214 objects totaling 13,784,915,480 bytes; headnode source regular files total 13,784,915,480 bytes; report prefix contains 0 failed-file report objects. |  | Post-export verification complete; all rows are terminal and the objective is complete. |

## Final Status

- Rows terminal: 5/5
- Objective complete: yes
- Export receipt: `reports/fsx_exports/dra-test4_run_qc_ont_all_20260518T090219Z/fsx_export.yaml`
- S3 destination: `s3://lsmc-dayoa-omics-analysis-us-west-2/analysis_results/ubuntu/run_qc_ont_all/`
- Focused test: `pytest tests/test_export.py -q -> 17 passed`

## Rerun: 2026-05-18T13:38:09Z

User confirmed a fresh export to the corrected destination
`s3://lsmc-dayoa-omics-analysis-us-west-2/analysis_results/ubuntu/run_qc_ont_all/`
after rejecting the misspelled `analyis_results` prefix.

- Source precheck: `/fsx/analysis_results/ubuntu/run_qc_ont_all` existed on `dra-test4` as `ubuntu`, owner `ubuntu:ubuntu`, mtime `2026-05-18 13:33:16 +0000`, with `3557` regular files and `13,998,766,551` bytes.
- Command: `dyec export --profile lsmc --region us-west-2 --cluster dra-test4 --source-path /fsx/analysis_results/ubuntu/run_qc_ont_all/ --destination-s3-uri s3://lsmc-dayoa-omics-analysis-us-west-2/analysis_results/ubuntu/run_qc_ont_all/ --output-dir reports/fsx_exports/dra-test4_run_qc_ont_all_20260518T133809Z --wait --timeout-seconds 7200`.
- Receipt: `reports/fsx_exports/dra-test4_run_qc_ont_all_20260518T133809Z/fsx_export.yaml`.
- Temporary DRA: `dra-0a1d444f47e53de71`, final `detach_lifecycle: DELETED`.
- Export task: `task-092aab06bcc1b24d5`, `SUCCEEDED`, `TotalCount=3611`, `SucceededCount=3611`, `FailedCount=0`.
- Failed-file report prefix: `s3://lsmc-dayoa-omics-analysis-us-west-2/analysis_results/ubuntu/run_qc_ont_all/_daylily_monitor/fsx-export/20260518T134029Z/export-report/` contained `0` objects.
- Destination prefix after export: `3825` objects, total size `13.0 GiB` by `aws s3 ls --summarize --human-readable`.
