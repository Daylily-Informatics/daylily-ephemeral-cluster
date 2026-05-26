# GIAB Altair v1.1 Control Data Publication Ledger

## Objective

Publish the local Altair v1 reportable-range BED as a new GIAB subset named `altair-v1.1` for each existing `HG00\\d` GIAB v4.2.1 truth directory, and copy each sample's existing `hg38/<sample>.vcf.gz` plus `.tbi` into the same subset directory.

## Gate 0 Baseline

| Item | Evidence |
|---|---|
| Ledger path | `docs/plans/20260526T064626Z_giab_altair_v11_control_data_ledger.md` |
| Repo | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| Branch | `codex/analysis-id-export-catalog-validation` |
| Dirty state | Pre-existing modified files: `tests/test_budgets.py`, `tests/test_packaged_defaults.py`, `tests/test_workflow.py`; pre-existing untracked logs under `docs/plans/20260526T051948Z_tstclu411c_logs/`. |
| Source BED | `/Users/jmajor/Downloads/Altair_v1_reportable_range (1).bed`; size `5,475,200` bytes; `229,156` lines; first rows begin `chr1 601181 602077`. |
| AWS profile / region | `lsmc` / `us-west-2` |
| Split bucket state | LSMC account currently lists only existing DayOA monolith bucket `lsmc-dayoa-omics-analysis-us-west-2`; no separate `dayoa-control-data` or similarly named control-data bucket was found. |
| Target bucket | Existing active DayOA bucket `s3://lsmc-dayoa-omics-analysis-us-west-2` |
| Target control-data prefix | `data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/` |
| Version resolved | Literal `v4.1*` was not present; existing GIAB truth version is `v4.2.1`. |
| Sample directories | `HG001`, `HG002`, `HG003`, `HG004`, `HG005`, `HG006`, `HG007`; stray `HG2/` ignored because it does not match `HG00\\d`. |
| Safety rule | Additive publication only. Abort if any destination `altair-v1.1` object already exists or if any source `hg38/<sample>.vcf.gz(.tbi)` is missing. No S3 delete or overwrite. |

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Inventory | Record local source BED, active bucket, version resolution, sample targets, and no-overwrite safety rule. | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 Baseline above. |  | Baseline complete. |
| PRE-001 | S3 preflight | Verify all source `hg38/<sample>.vcf.gz` and `.tbi` objects exist and no destination `altair-v1.1` object exists. | SUCCESS | legitimate_safety_handling | Gate 1 | orchestrator | Boto3 preflight in DayEC env against `lsmc`/`us-west-2` found all 14 source objects for HG001-HG007, all 21 destination objects absent, no errors. Source BED SHA256 `394c3ef2ed8d81933bc94a8c41bff82ee2e538aad51f2d75521ba55cf28ef793`. |  | Safe to publish additively. |
| PUB-001 | S3 publish | Upload `<sample>.bed` from local Altair BED and copy hg38 VCF/TBI to each `altair-v1.1/` directory. | SUCCESS | feature_implementation | Gate 2 | orchestrator | Boto3 publication uploaded 7 BED files and copied 14 VCF/TBI files with `published_count=21`, `errors=[]`. Each BED is `5,475,200` bytes with ETag `98195d53f883870190f341343a1552be`. |  | Published additively; no overwrite or delete. |
| VERIFY-001 | S3 verify | Re-read destination object sizes/ETags for all 21 expected objects. | SUCCESS | contract_test | Gate 3 | orchestrator | Independent S3 HEAD verification found `verified_count=21`, `errors=[]`; every BED carries metadata `source-sha256=394c3ef2ed8d81933bc94a8c41bff82ee2e538aad51f2d75521ba55cf28ef793`. |  | All expected objects visible in S3. |

## Target Object Pattern

For each `HG001` through `HG007`:

```text
s3://lsmc-dayoa-omics-analysis-us-west-2/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/<HG00x>/altair-v1.1/<HG00x>.bed
s3://lsmc-dayoa-omics-analysis-us-west-2/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/<HG00x>/altair-v1.1/<HG00x>.vcf.gz
s3://lsmc-dayoa-omics-analysis-us-west-2/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/<HG00x>/altair-v1.1/<HG00x>.vcf.gz.tbi
```

## Evidence Log

- `2026-05-26T06:46:26Z`: Created ledger after resolving the active GIAB truth version and sample set.
- `2026-05-26T06:48Z`: Preflight passed: all source `hg38` VCF/TBI objects exist; no `altair-v1.1` destination objects exist; local BED SHA256 is `394c3ef2ed8d81933bc94a8c41bff82ee2e538aad51f2d75521ba55cf28ef793`.
- `2026-05-26T06:49Z`: Published 21 objects under `altair-v1.1/`: for each of HG001-HG007, uploaded `<sample>.bed` from the local Altair BED and copied `hg38/<sample>.vcf.gz` plus `.tbi`.
- `2026-05-26T06:50Z`: Verification pass re-read all 21 destination objects with S3 HEAD; no missing objects and no BED size mismatches.

## Final Report

- Published in `s3://lsmc-dayoa-omics-analysis-us-west-2/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/`.
- Created `altair-v1.1/` subsets for `HG001`, `HG002`, `HG003`, `HG004`, `HG005`, `HG006`, and `HG007`.
- Each subset contains `<sample>.bed`, `<sample>.vcf.gz`, and `<sample>.vcf.gz.tbi`.
- The local BED source was `/Users/jmajor/Downloads/Altair_v1_reportable_range (1).bed`, size `5,475,200` bytes, SHA256 `394c3ef2ed8d81933bc94a8c41bff82ee2e538aad51f2d75521ba55cf28ef793`.
- No separate LSMC control-data bucket existed at publication time, so the additive copy landed in the current active monolith control-data prefix.
