# Latest Ultima MultiQC CloudFront Ledger

Date opened: 2026-05-17

## Control

Controlling request: expose on CloudFront the most recent Ultima run MultiQC HTML report and data directory.

Ledger path: `/Users/jmajor/projects/daylily/daylily-ephemeral-cluster/docs/plans/latest_ultima_multiqc_cloudfront_20260517_ledger.md`

Execution scope:
- AWS profile: `lsmc`
- AWS region: `us-west-2`
- DayEC repo: `/Users/jmajor/projects/daylily/daylily-ephemeral-cluster`
- Candidate latest Ultima run: `ultima_602202_20260512_1805_ksink105_20260517T190121Z`
- Candidate report path: `/fsx/analysis_results/ubuntu/ultima_602202_20260512_1805_ksink105_20260517T190121Z/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc.html`
- Candidate data dir: `/fsx/analysis_results/ubuntu/ultima_602202_20260512_1805_ksink105_20260517T190121Z/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc_data`

Hard boundaries:
- Use the existing Basic-auth CloudFront report surface; do not invent a new exposure mechanism.
- Do not delete or overwrite AWS objects.
- If the existing CloudFront distribution already serves the exported prefix, prefer verification over mutation.

## Gate 0 Baseline

- DayEC status: branch `codex/run-directory-mounts...origin/codex/run-directory-mounts`; existing unrelated untracked files and prior ledger/report artifacts are present.
- Relevant prior ledger: `docs/plans/ultima_602201_602202_ksink105_ledger.md` records `ultima_602202_20260512_1805_ksink105_20260517T190121Z` completed at `2026-05-17T21:54:47Z` with final MultiQC size `11,929,236` bytes.
- Relevant prior export surface: `docs/plans/stage_ultima_ilmn_recovery_ledger.md` and `docs/plans/ilmn_20x_hg002_hg003_sent_kitchen_ledger.md` record existing CloudFront distribution `E1O1EGAADAALSL` / `dlqovrcm5y71h.cloudfront.net` serving origin path `/FSxLustre20260515T103052Z/analysis_results/ubuntu` with Basic realm `LSMC QC`.
- Existing local export receipts include `tmp-export/may26-d_20260517T230139Z/fsx_export.yaml` for `s3://lsmc-dayoa-omics-analysis-us-west-2/FSxLustre20260515T103052Z/analysis_results/ubuntu`.

## Control Ledger

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| GATE-000 | DayEC/AWS | Record repo state, target run, prior export surface, and assumptions before live CloudFront/S3 work. | SUCCESS | plan_amendment | Gate 0 | orchestrator | Gate 0 Baseline section above. |  | Baseline recorded before live checks. |
| TARGET-001 | DayOA/AWS | Confirm the most recent Ultima run report and data directory to publish. | SUCCESS | contract_test | Gate 1 | orchestrator | S3 origin listing under `FSxLustre20260515T103052Z/analysis_results/ubuntu/` shows only two Ultima run prefixes: `ultima_602202_20260512_1805_snv_alignstats_20260517T142728Z/` and later `ultima_602202_20260512_1805_ksink105_20260517T190121Z/`; prior ledger records the later run completed at `2026-05-17T21:54:47Z`. |  | Target confirmed as the `ksink105` run. |
| EXPORT-001 | DayEC/AWS | Confirm the final report and `DAY_final_multiqc_data/` are exported to S3 under the CloudFront origin path, exporting only if missing. | SUCCESS | feature_implementation | Gate 2 | orchestrator | `aws s3api head-object` for `.../reports/DAY_final_multiqc.html` returned `ContentLength=11929236`, `ContentType=text/html; charset=utf-8`, `LastModified=2026-05-17T23:04:37Z`; recursive S3 summary for `DAY_final_multiqc_data/` returned `Total Objects: 57`, `Total Size: 31787596`. |  | Artifacts were already exported under the existing CloudFront origin path; no new FSx export was needed. |
| PUBLISH-001 | AWS/CloudFront | Expose the report and data directory through the existing Basic-auth CloudFront distribution. | SUCCESS | feature_implementation | Gate 3 | orchestrator | Distribution `E1O1EGAADAALSL` / `dlqovrcm5y71h.cloudfront.net` is `Deployed`, origin path `/FSxLustre20260515T103052Z/analysis_results/ubuntu`, Basic-auth function `lsmc-giab-20x30x-v2-basic-auth-20260511`; bucket policy already includes `AllowCloudFrontReadMay26dSelectedAnalysis20260517T014107Z` for `.../FSxLustre20260515T103052Z/analysis_results/ubuntu/*` and distribution `E1O1EGAADAALSL`. Created targeted invalidation `I81LY2MWVJCJYJ6C2LC6JZROQ5` for the report HTML and data subtree; status `Completed`. |  | Existing distribution and policy covered the new prefix; only targeted invalidation was needed. |
| VERIFY-001 | AWS/CloudFront | Verify the final report URL and data URL behavior, including unauthenticated Basic-auth gate. | SUCCESS | contract_test | Gate 4 | orchestrator | Unauthenticated `curl -I` to the report URL returned `401` with `www-authenticate: Basic realm="LSMC QC"`; authenticated `curl -I` to the report returned `200`, `content-type=text/html; charset=utf-8`, `content-length=11929236`; authenticated `curl -I` to `DAY_final_multiqc_data/multiqc_data.json` returned `200`, `content-length=28055877`. |  | Share URL and data directory are live behind the existing Basic-auth gate. |

## Final Report

Status counts: `SUCCESS=5`, `OPEN=0`, `IN_PROGRESS=0`, `ATTEMPTING_BUGFIX=0`, `FAIL=0`, `BLOCKED=0`.

Objective complete: yes. The most recent Ultima run report and `DAY_final_multiqc_data/` are exported to S3 and reachable through the existing Basic-auth CloudFront distribution.

Report URL:

`https://dlqovrcm5y71h.cloudfront.net/ultima_602202_20260512_1805_ksink105_20260517T190121Z/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc.html`

Data directory URL prefix:

`https://dlqovrcm5y71h.cloudfront.net/ultima_602202_20260512_1805_ksink105_20260517T190121Z/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc_data/`
