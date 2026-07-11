# dragain12 No-Export Deletion Ledger

Created: `2026-07-11T08:31:59Z`

## Approval And Gate 0

| Surface | Evidence |
|---|---|
| Scope | Delete only ParallelCluster `dragain12` in `us-west-2`. |
| First request | User requested deletion without an FSx-to-S3 export. |
| Destructive boundary | Deletion destroys the cluster stack, headnode and compute instances, FSx `fs-0a53b2609fd97934e`, unexported FSx data, and attached DRAs. Source S3 objects are not deleted. |
| Second approval | `I approve deleting dragain12 in us-west-2 now without export.` received after the exact destructive effect was restated. |
| Pre-delete state | `dyec delete --dry-run` reports cluster status `UPDATE_COMPLETE`, FSx `fs-0a53b2609fd97934e`, and eight active DRAs. The BCL workflow queue had drained and returned `0` before approval. |
| Export boundary | No FSx-to-S3 export will be started or awaited for this deletion. |

## Control Ledger

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| DELETE-001 | Delete `dragain12` in `us-west-2` after second approval. | SUCCESS | `dyec delete --profile lsmc --region us-west-2 --cluster-name dragain12 --yes` reached `Cluster deleted` after approximately `14m 24s`; no export ran. |
| VERIFY-001 | Verify cluster, FSx, and attached DRAs are absent. | SUCCESS | ParallelCluster reports `dragain12` absent; CloudFormation reports no stack; FSx reports `fs-0a53b2609fd97934e` absent; DRA query for that filesystem returns `[]`; EC2 query for nonterminated `dragain12` instances returns `[]`. |
| EXPORT-001 | Do not export FSx data to S3. | SUCCESS | User explicitly required deletion without export; no export command is authorized. |

## Terminal State

All three rows are terminal `SUCCESS`. `dragain12` and its FSx/DRA/EC2
resources are absent. No FSx-to-S3 export was performed; source S3 objects were
not deleted.
