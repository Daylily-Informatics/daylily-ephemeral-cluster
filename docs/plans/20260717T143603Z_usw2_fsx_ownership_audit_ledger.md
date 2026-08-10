# us-west-2 FSx Ownership And Deletion-Safety Audit Ledger

Datetime: 2026-07-17T14:36:03Z

## Objective

Determine why both `fs-0942c7bce60871db8` (`fsx-ifx-sacctpost-10318`) and
`fs-0cc0657362d4140c2` (`fsx-ifx-p2-1000-120-0715`) exist in `us-west-2`, map
each to current AWS/ParallelCluster ownership and use, and decide whether either
is a safe deletion candidate. This audit is read-only. No FSx, CloudFormation,
ParallelCluster, DRA, backup, or data deletion is authorized.

## Gate 0: Inventory Freeze

- Controlling ledger: this file.
- Owning repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`.
- Repo baseline: `main...origin/main [behind 3]`; unrelated existing untracked
  file `docs/plans/20260717T093053Z_inflection_release_train_ledger.md` preserved.
- AWS scope: account `108782052779`, profile `lsmc`, region `us-west-2`.
- Toolchain: activated checkout; AWS CLI `2.34.29`; ParallelCluster `3.15.0`.
- Requested file systems: `fs-0942c7bce60871db8` and
  `fs-0cc0657362d4140c2`.
- Assumptions: resource names are hints only; current tags, CloudFormation
  resources, mount targets, DRAs, backups, and live instances are authoritative.
- Safety boundary: deletion is destructive and requires a separate explicit
  approval after this audit states the exact effect. No deletion command or
  destructive confirmation will be issued during this audit.

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| FSX-001 | Regional inventory | Inventory live ParallelCluster clusters and both FSx file systems | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | `pcluster list-clusters`: exactly one current cluster, `ifx-p2-1000-120-0715`, `UPDATE_COMPLETE`. Both requested FSx file systems are `AVAILABLE`. |  | Current regional cluster/FSx inventory is recorded. |
| FSX-002 | Ownership | Resolve tags, CloudFormation stack resources, cluster configuration, network attachment, and mount identity for each FSx | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | `fs-0cc0657362d4140c2` tags name live cluster `ifx-p2-1000-120-0715`; interactive ubuntu headnode `findmnt` showed `/fsx` mounted from Lustre mount `xfuonb4v`. `fs-0942c7bce60871db8` tags name `ifx-sacctpost-10318`; CloudFormation history shows that stack `DELETE_COMPLETE` at `2026-07-16T04:51:33Z`, with CloudTrail `DeleteStack` by `daylily-service`. |  | The second FSx is the retained external filesystem of a separate deleted proof cluster, not a second filesystem of the one live cluster. |
| FSX-003 | Data/use safety | Check live mounts/instances, DRAs, backups, capacity, and available activity evidence | SUCCESS | legitimate_safety_handling | Gate 4 | orchestrator | Live `fs-0cc...`: `/fsx`, `12T`, `3.8T` used, `34%`, active I/O, three available DRAs and completed export tasks. Old `fs-0942...`: zero `ClientConnections` and zero `DataWriteBytes` since old stack deletion, utilization metric `0%`, one available reference-import DRA `dra-0468354fff8b1bbdc`, no backups, no pending/executing data-repository tasks; its only metadata-import task ended `FAILED` with `968381/968382` successes. Prior proof ledger explicitly retained the filesystem/DRA; resource tags include `ursa-preserve=true`, `dyec:fsx-lifecycle=CLUSTER_BOUND`, and `sweep_preserve=true` in the local receipt. |  | The live filesystem is not a deletion candidate. The old filesystem has no current clients or data writes but carries an explicit historical preservation decision and no recoverable backup. |
| FSX-004 | Decision | Classify any deletion candidate and state exact effect and required approval | SUCCESS | active_product_contract | Gate 5 | orchestrator | AWS FSx deletion contract: deleting a Lustre filesystem permanently removes its data; this S3-linked filesystem cannot take a final FSx backup. `fs-0942...` is the only candidate. Deletion would permanently remove that filesystem and any local-only bytes and retire its reference DRA; the S3 reference bucket is the owning repository and is not in deletion scope. |  | Candidate classified, but no deletion is authorized or performed. A separate explicit destructive approval must name `fs-0942c7bce60871db8` and accept loss of local-only data and the retained proof resource. |

## Final Terminal-State Report

All four rows are terminal `SUCCESS`; the audit objective is complete.

- `fs-0cc0657362d4140c2` is the live cluster filesystem and must remain.
- `fs-0942c7bce60871db8` is the retained filesystem of deleted proof cluster
  `ifx-sacctpost-10318`. It is the only cleanup candidate, subject to an
  explicit decision to supersede the preservation tags/ledger and accept
  unrecoverable loss of any local-only data.
- No AWS, FSx, DRA, backup, cluster, mount, or data mutation was performed.
