# ILMN 0006 Final MultiQC Export And Cluster Delete Prep Ledger

Date opened: 2026-05-19T08:40:33Z

## Control

Controlling request: run a fresh FSx-to-S3 export of the ILMN 0006 DayOA directory now that final MultiQC exists, provide a CloudFront URL to the MultiQC report, prepare to delete the current cluster plus `dra-test4`, then after separate explicit confirmation delete both clusters.

Ledger path: `/Users/jmajor/projects/daylily/daylily-ephemeral-cluster/docs/plans/20260519T084033Z_ilmn0006_final_multiqc_export_and_delete_prep_ledger.md`

Scope:
- AWS profile: `lsmc`
- AWS region: `us-west-2`
- Current analysis cluster: `may26-d`
- Additional deletion-prep cluster: `dra-test4`
- FSx filesystem for ILMN 0006 export: `fs-0c43ddf4b70dc87d8`
- Export method: AWS CLI single data-repository task, `EXPORT_TO_REPOSITORY`
- Export source path: `analysis_results/ubuntu/ilmn_0006_align_dedup_alignstats_20260517T185626Z/daylily-omics-analysis`
- S3 destination prefix: `s3://lsmc-dayoa-omics-analysis-us-west-2/FSxLustre20260515T103052Z/analysis_results/ubuntu/ilmn_0006_align_dedup_alignstats_20260517T185626Z/daylily-omics-analysis`
- CloudFront distribution: `E1O1EGAADAALSL` / `dlqovrcm5y71h.cloudfront.net`
- CloudFront origin path: `/FSxLustre20260515T103052Z/analysis_results/ubuntu`

Hard boundary:
- Preparing cluster deletion is allowed.
- Live deletion of `may26-d` or `dra-test4` is destructive and requires a separate explicit confirmation after the exact effect is stated.
- Separate explicit confirmation received: `Confirm delete may26-d and dra-test4 in us-west-2 using profile lsmc`.

## Gate 0 Baseline

- Local repo status: `## codex/docs-plans-ledgers...origin/codex/docs-plans-ledgers`, with existing untracked run/export artifacts.
- Prior final MultiQC proof: `docs/plans/20260519T070647Z_ilmn0006_multiqc_1014_run_ledger.md` records `phase=success`, final report size `96071925`, and final report path under the ILMN 0006 DayOA directory.
- Prior export proof before final report completion: `docs/plans/20260519T063749Z_ilmn0006_dayoa_fsx_export_ledger.md` used AWS CLI single-DRA export task `task-09b26c2c4b85deb91` for the same source path.
- Existing CloudFront proof: `docs/plans/ilmn_0006_export_peddy_touch_multiqc_ledger.md` records distribution `E1O1EGAADAALSL` serving origin path `/FSxLustre20260515T103052Z/analysis_results/ubuntu` behind Basic auth.

## Terminal Evidence

- Fresh export task: `task-0220446f053914e0d`.
- Export task lifecycle: `SUCCEEDED`.
- Export counts: `total=7527`, `succeeded=7527`, `failed=0`.
- Local receipt: `tmp-export/ilmn0006-dayoa-final-multiqc-20260519T084033Z/fsx_export.yaml`.
- S3 final report object:
  - Bucket/key: `s3://lsmc-dayoa-omics-analysis-us-west-2/FSxLustre20260515T103052Z/analysis_results/ubuntu/ilmn_0006_align_dedup_alignstats_20260517T185626Z/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc.html`
  - `ContentLength=96071925`
  - `ContentType=text/html; charset=utf-8`
  - `LastModified=2026-05-19T08:43:03+00:00`
- CloudFront invalidation: `I48NVRQ4BIJJ1F9IJD1DETUESD`, `Completed`.
- CloudFront URL:
  - `https://dlqovrcm5y71h.cloudfront.net/ilmn_0006_align_dedup_alignstats_20260517T185626Z/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc.html`
- CloudFront verification:
  - Unauthenticated `HEAD`: `HTTP/2 401`, `Basic realm="LSMC QC"`
  - Authenticated `HEAD`: `HTTP/2 200`, `ContentType=text/html; charset=utf-8`, `ContentLength=96071925`
- Final delete dry-runs:
  - `may26-d`: `CREATE_COMPLETE`, FSx still associated: `fs-0c43ddf4b70dc87d8`; no active export-task warning after the fresh export completed.
  - `dra-test4`: `CREATE_COMPLETE`, dry-run reported no associated FSx filesystems.
- Live deletes:
  - `daylily-ec delete --profile lsmc --region us-west-2 --cluster-name dra-test4 --yes` completed; `daylily-ec` reported `Cluster deleted`.
  - `daylily-ec delete --profile lsmc --region us-west-2 --cluster-name may26-d --yes` completed; `daylily-ec` reported `Cluster deleted`.
- Post-delete CloudFormation evidence:
  - `dra-test4`: `DELETE_COMPLETE`, `DeletionTime=2026-05-19T09:13:23.039Z`.
  - `may26-d`: `DELETE_COMPLETE`, `DeletionTime=2026-05-19T09:13:23.680Z`.
- Post-delete ParallelCluster active-list check with `AWS_PROFILE=lsmc` returned no matching active clusters for `may26-d` or `dra-test4`.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | DayEC/AWS | Record export source, S3/CloudFront mapping, cluster delete boundary, and repo state. | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 Baseline. |  | Baseline recorded before live export task. |
| EXP-001 | AWS FSx | Run a fresh AWS CLI single-DRA export task for the ILMN 0006 DayOA directory. | SUCCESS | feature_implementation | Gate 1 | orchestrator | AWS CLI `create-data-repository-task` created `task-0220446f053914e0d`; final lifecycle `SUCCEEDED`, `7527/7527` files, `0` failures. |  | Fresh export completed after final MultiQC generation. |
| EXP-002 | AWS S3 | Verify the final MultiQC HTML object exists at the expected S3 key after export. | SUCCESS | contract_test | Gate 2 | orchestrator | `head-object` for the final report returned `ContentLength=96071925`, `ContentType=text/html; charset=utf-8`, `LastModified=2026-05-19T08:43:03+00:00`. |  | S3 now contains the final MultiQC HTML. |
| CF-001 | AWS CloudFront | Verify/provide CloudFront URL for the final MultiQC HTML. | SUCCESS | contract_test | Gate 3 | orchestrator | Targeted invalidation `I48NVRQ4BIJJ1F9IJD1DETUESD` completed; unauthenticated `HEAD` returned `401`; authenticated `HEAD` returned `200` and `ContentLength=96071925`. |  | CloudFront URL is live behind the existing Basic-auth gate. |
| DELPREP-001 | AWS ParallelCluster | Prepare deletion of `may26-d` and `dra-test4` with read-only inventory/dry-run only. | SUCCESS | legitimate_safety_handling | Gate 4 | orchestrator | `daylily-ec delete --dry-run` for `may26-d` reported `CREATE_COMPLETE` and FSx `fs-0c43ddf4b70dc87d8`; `dra-test4` reported `CREATE_COMPLETE` and no associated FSx filesystems. | Separate explicit confirmation was required before destructive AWS cluster deletion. | Prepared only until the user provided separate explicit confirmation. |
| DEL-001 | AWS ParallelCluster | Delete `may26-d` and `dra-test4` only after separate explicit confirmation. | SUCCESS | destructive_operation | Gate 4A | orchestrator | `daylily-ec delete --yes` completed for both clusters; CloudFormation lists both stacks as `DELETE_COMPLETE`; active ParallelCluster listing returned no matching clusters. |  | Live deletion completed after explicit confirmation. |
| FINAL-001 | DayEC/AWS | Terminalize ledger and report export receipt, CloudFront URL, and deletion outcome. | SUCCESS | contract_test | Gate 5 | orchestrator | Terminal Evidence section. |  | Export, CloudFront, and confirmed cluster deletion are complete. |
