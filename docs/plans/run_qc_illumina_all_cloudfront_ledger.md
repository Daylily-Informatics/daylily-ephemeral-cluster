# Run QC Illumina All CloudFront Ledger

Date: 2026-05-18

## Objective

Expose the MultiQC report artifacts already present at:

`s3://lsmc-dayoa-omics-analysis-us-west-2/analysis_results/ubuntu/run_qc_illumina_all/`

through the existing Basic-auth CloudFront report surface.

## Gate 0 Baseline

- Repo: `/Users/jmajor/projects/daylily/daylily-ephemeral-cluster`.
- AWS profile/region: `lsmc` / `us-west-2`.
- Existing report distribution: `E1O1EGAADAALSL` / `dlqovrcm5y71h.cloudfront.net`.
- Existing origin path before change: `/FSxLustre20260515T103052Z/analysis_results/ubuntu`.
- Requested S3 report object: `analysis_results/ubuntu/run_qc_illumina_all/illumina_runs.multiqc.html`.
- S3 head-object for aggregate HTML: content length `4644403`, content type `text/html; charset=utf-8`, last modified `2026-05-18T04:42:15Z`, ETag `596a8296853387faf10a7069496d9f1d`.
- S3 recursive listing under requested prefix: `98` objects, total size `24.1 MiB`.
- Unauthenticated CloudFront probe for `/analysis_results/ubuntu/run_qc_illumina_all/illumina_runs.multiqc.html`: `401`, Basic realm `LSMC QC`.
- Authenticated CloudFront probe for the same path before publish: `403` from S3, confirming Basic Auth works but the distribution lacks a root-prefix origin mapping/grant for this S3 destination.

## Tracking Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | DayEC/AWS | Record target S3 prefix, existing CloudFront distribution state, object inventory, and current URL behavior before mutation. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | Gate 0 Baseline above. |  | Baseline recorded before live CloudFront/S3 policy updates. |
| PUB-001 | AWS/CloudFront/S3 | Add a scoped way for the existing CloudFront distribution to serve `analysis_results/ubuntu/run_qc_illumina_all/*` from the bucket root. | SUCCESS | feature_implementation | Gate 1 | orchestrator | Added bucket-policy statement `AllowCloudFrontReadRunQcIlluminaAll20260518` granting `s3:GetObject` only for `arn:aws:s3:::lsmc-dayoa-omics-analysis-us-west-2/analysis_results/ubuntu/run_qc_illumina_all/*` from CloudFront distribution `E1O1EGAADAALSL`; updated distribution `E1O1EGAADAALSL` with origin `s3-run-qc-illumina-all-root-20260518` and cache behavior path pattern `analysis_results/ubuntu/run_qc_illumina_all/*`; distribution deployed at `2026-05-18T04:48:28Z`; invalidation `I3RNKWBUU9BZKIIFC1R73BXXNP` completed for `/analysis_results/ubuntu/run_qc_illumina_all/*`. |  | Existing FSx-origin default behavior remains unchanged; the requested root S3 destination is now addressable through the same Basic-auth CloudFront distribution. |
| VERIFY-001 | AWS/CloudFront | Verify unauthenticated and authenticated URL behavior for the aggregate MultiQC HTML and data directory. | SUCCESS | contract_test | Gate 2 | orchestrator | Unauthenticated HEAD on `/analysis_results/ubuntu/run_qc_illumina_all/illumina_runs.multiqc.html` -> `401`, `Basic realm="LSMC QC"`; authenticated HEAD on aggregate HTML -> `200`, `content-type=text/html; charset=utf-8`, `content-length=4644403`; authenticated HEAD on `illumina_runs.multiqc_data/multiqc_data.json` -> `200`, `content-length=3726004`; authenticated HEAD on per-run `20260512_LH01106_0006_A23K3H2LT4.multiqc.html` -> `200`, `content-length=4206343`. |  | Aggregate report, data file, and per-run report are reachable behind Basic Auth. |

## Final Report

Objective complete: yes. The requested S3 destination is exposed through the existing Basic-auth CloudFront distribution.

Aggregate MultiQC HTML:

`https://dlqovrcm5y71h.cloudfront.net/analysis_results/ubuntu/run_qc_illumina_all/illumina_runs.multiqc.html`

Aggregate MultiQC data directory:

`https://dlqovrcm5y71h.cloudfront.net/analysis_results/ubuntu/run_qc_illumina_all/illumina_runs.multiqc_data/`
