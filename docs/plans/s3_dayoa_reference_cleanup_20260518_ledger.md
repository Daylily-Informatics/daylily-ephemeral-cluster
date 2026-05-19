# S3 DayOA Reference Cleanup Ledger

Created: 2026-05-18T01:30Z

## Objective

Prepare deletion of requested staged data from the DayOA reference bucket:

`s3://lsmc-dayoa-omics-analysis-us-west-2`

Requested surfaces:

- ILMN run 007 staged data.
- ONT staged data.

No live delete is authorized until the operator gives a second explicit confirmation after reviewing the exact destructive effect.

## Gate 0: Inventory Freeze

Status: `SUCCESS`

Repo path:

```text
/Users/jmajor/projects/daylily/daylily-ephemeral-cluster
```

Safety rule:

```text
Do not execute destructive AWS resource changes unless the user gives a second explicit approval after being told the action is destructive.
```

Reference bucket:

```text
s3://lsmc-dayoa-omics-analysis-us-west-2
```

Inspection commands:

```text
AWS_PROFILE=lsmc AWS_REGION=us-west-2
boto3 list_objects_v2 on s3://lsmc-dayoa-omics-analysis-us-west-2/data/staged_sample_data/
```

## Candidate Prefix Inventory

| Surface | Prefix | Objects | Bytes | Status |
|---|---:|---:|---:|---|
| ILMN run 007 assigned staged data | `s3://lsmc-dayoa-omics-analysis-us-west-2/data/staged_sample_data/remote_stage_20260516T132807Z/` | 0 | 0 | No S3 objects found. |
| ILMN run 007 recovered FASTQs | `s3://lsmc-dayoa-omics-analysis-us-west-2/data/recovered_undetermined/20260512_LH01106_0007_B23K5JKLT4/` | 0 | 0 | No S3 objects found. |
| ILMN run 007 recovered staged data | `s3://lsmc-dayoa-omics-analysis-us-west-2/data/staged_sample_data/recovered_undetermined/` | 0 | 0 | No S3 objects found. |
| ONT PCA100 20260513 staged data | `s3://lsmc-dayoa-omics-analysis-us-west-2/data/staged_sample_data/remote_stage_20260517T155831Z/` | 69 | 41,901,872,070 | Live delete candidate. |
| Older ONT example solo staged data | `s3://lsmc-dayoa-omics-analysis-us-west-2/data/staged_sample_data/remote_stage_20260424T110647Z/` | 0 | 0 | No S3 objects found. |
| Older ONT example hybrid staged data | `s3://lsmc-dayoa-omics-analysis-us-west-2/data/staged_sample_data/remote_stage_20260424T113324Z/` | 0 | 0 | No S3 objects found. |

Broad filtered scan under `data/staged_sample_data/` found `0` keys containing `0007`, `B23K5JKLT4`, or `Altair-Run-2`.

The ONT prefix `remote_stage_20260517T155831Z` is identified by its units TSV:

```text
data/staged_sample_data/remote_stage_20260517T155831Z/20260517T155831Z_units.tsv
RUNID=20260513-ONT-HG003
PLATFORM=PROMETHION
```

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| S3CLEAN-001 | Safety | Inventory and exact destructive effect before live delete. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | Candidate prefix inventory above; ONT delete candidate has 69 objects / 41,901,872,070 bytes; run 007 S3 candidates have 0 objects. |  | Inventory complete; live delete still blocked pending explicit confirmation. |
| S3CLEAN-002 | AWS/S3 | Delete ILMN run 007 staged data from DayOA reference bucket. | NO_LONGER_NEEDED | feature_implementation | Gate 1 | orchestrator | Known run 007 candidate prefixes and broad filtered `data/staged_sample_data/` scan found 0 matching objects. | No run 007 staged S3 objects were found in the DayOA reference bucket. | Nothing to delete from S3 for run 007 unless a different prefix is provided. |
| S3CLEAN-003 | AWS/S3 | Delete ONT staged data from DayOA reference bucket. | SUCCESS | feature_implementation | Gate 1 | orchestrator | Candidate prefix `s3://lsmc-dayoa-omics-analysis-us-west-2/data/staged_sample_data/remote_stage_20260517T155831Z/` had 69 objects / 41,901,872,070 bytes and units TSV `RUNID=20260513-ONT-HG003`, `PLATFORM=PROMETHION`. Operator explicitly confirmed deletion of the 69 objects. Boto3 deletion with `AWS_PROFILE=lsmc`, `region=us-west-2` at `2026-05-18T02:26:21Z` saw `pre_delete_count=69`, `pre_delete_bytes=41901872070`, `deleted_responses=69`, `delete_errors=0`; post-delete list at `2026-05-18T02:26:23Z` showed `post_delete_count=0`, `post_delete_bytes=0`. |  | Exact ONT staged-data prefix is empty after deletion. |

## Prepared Destructive Command

Do not run until explicitly confirmed:

```bash
AWS_PROFILE=lsmc AWS_REGION=us-west-2 \
aws s3 rm --recursive \
  s3://lsmc-dayoa-omics-analysis-us-west-2/data/staged_sample_data/remote_stage_20260517T155831Z/
```

## Final Status

The operator confirmed the destructive delete. The 69 current objects under:

```text
s3://lsmc-dayoa-omics-analysis-us-west-2/data/staged_sample_data/remote_stage_20260517T155831Z/
```

were deleted successfully. Post-delete inventory found 0 current objects under the prefix.
