# GIAB Altair v1.1 Regional Reference Bucket Copy Ledger

## Objective

Copy the published GIAB `altair-v1.1` subset objects from the active `us-west-2` DayOA bucket to the regional LSMC DayOA reference buckets in `ap-south-1` and `eu-central-1`.

## Gate 0 Baseline

| Item | Evidence |
|---|---|
| Ledger path | `docs/plans/20260526T065022Z_giab_altair_v11_regional_copy_ledger.md` |
| Source ledger | `docs/plans/20260526T064626Z_giab_altair_v11_control_data_ledger.md` |
| Source bucket | `s3://lsmc-dayoa-omics-analysis-us-west-2` |
| Target buckets | `s3://lsmc-dayoa-omics-analysis-ap-south-1`; `s3://lsmc-dayoa-omics-analysis-eu-central-1` |
| User typo resolution | Interpreted `eu-erntal-1` as `eu-central-1`, the existing LSMC regional reference bucket. |
| Prefix | `data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/` |
| Samples | `HG001`, `HG002`, `HG003`, `HG004`, `HG005`, `HG006`, `HG007` |
| Objects per bucket | 21 total: `<sample>/altair-v1.1/<sample>.bed`, `<sample>.vcf.gz`, `<sample>.vcf.gz.tbi` for each sample. |
| Safety rule | Additive copy only. Abort before copy if any source object is missing or any destination object already exists. No delete or overwrite. |

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Inventory | Record source, target buckets, typo resolution, object set, and no-overwrite rule. | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 Baseline above; both target buckets passed `head-bucket`. |  | Baseline complete. |
| PRE-001 | S3 preflight | Verify 21 source objects exist and 42 regional destination objects are absent. | SUCCESS | legitimate_safety_handling | Gate 1 | orchestrator | DayEC-env boto3 preflight found `source_count=21`, `dest_absent_count=42`, `errors=[]`. |  | Safe to copy additively. |
| COPY-001 | S3 copy | Copy all 21 objects to each target bucket. | SUCCESS | feature_implementation | Gate 2 | orchestrator | Guarded boto3 copy completed with `copied_count=42`, `errors=[]`; ap-south-1 and eu-central-1 each received 21 objects. |  | Copied additively; no overwrite or delete. |
| VERIFY-001 | S3 verify | Verify all copied objects with S3 HEAD in each target bucket. | SUCCESS | contract_test | Gate 3 | orchestrator | Independent S3 HEAD verification found `verified_count=42`, `errors=[]`, `by_bucket` 21 for `lsmc-dayoa-omics-analysis-ap-south-1` and 21 for `lsmc-dayoa-omics-analysis-eu-central-1`; BED metadata SHA256 preserved as `394c3ef2ed8d81933bc94a8c41bff82ee2e538aad51f2d75521ba55cf28ef793`. |  | All regional objects verified. |

## Final Report

- Copied `altair-v1.1` GIAB subset objects from `s3://lsmc-dayoa-omics-analysis-us-west-2` to:
  - `s3://lsmc-dayoa-omics-analysis-ap-south-1`
  - `s3://lsmc-dayoa-omics-analysis-eu-central-1`
- For each bucket, created 21 objects under `data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/<HG00x>/altair-v1.1/`.
- Samples copied: `HG001`, `HG002`, `HG003`, `HG004`, `HG005`, `HG006`, `HG007`.
- Per sample objects: `<sample>.bed`, `<sample>.vcf.gz`, `<sample>.vcf.gz.tbi`.
- Final verification: 42 copied objects visible by S3 HEAD; no size mismatches; no missing objects; no overwrite or delete.
