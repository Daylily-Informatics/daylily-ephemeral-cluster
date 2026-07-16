# tstpartition Delete Ledger

Date: 2026-06-24T20:13:26Z

## Scope

Delete AWS ParallelCluster cluster `tstpartition` in `us-west-2` using AWS profile `lsmc`, after dry-run inspection and explicit second user approval.

## Gate 0 Inventory

| Item | Evidence |
|---|---|
| Repo | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` |
| Branch | `codex/release-10.0.64-prod` |
| Git status | Pre-existing dirty/untracked files present; deletion ledger is the only intended repo edit for this task. |
| AWS account | `108782052779` from `AWS_PROFILE=lsmc aws sts get-caller-identity --region us-west-2` |
| Target cluster | `tstpartition` |
| Region | `us-west-2` |
| Cluster status before delete | `CREATE_COMPLETE` |
| Compute fleet before delete | `RUNNING` |
| Running instances before delete | Headnode only: `i-0657bfbc8ec3c41ae`, public IP `16.144.178.120`, type `r7i.4xlarge`; no compute nodes. |
| FSx filesystem | `fs-0ba146a98ca409017` |
| Dry-run command | `source ./activate && dyec delete --cluster-name tstpartition --region us-west-2 --profile lsmc --dry-run` |
| Dry-run result | No AWS resources changed; warned that FSx and active DRAs are attached. |
| User approval | User first requested deletion, then explicitly confirmed live destructive action with `delete tstpartition now`. |

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DEL-001 | Live AWS | Dry-run `tstpartition` deletion before live action. | SUCCESS | legitimate_safety_handling | Gate 0 | Codex | Dry-run command returned `0` and listed attached FSx/DRAs. |  | Dry-run completed without changes. |
| DEL-002 | Live AWS | Delete `tstpartition` only after second explicit approval. | SUCCESS | legitimate_safety_handling | Destructive approval | Codex | `source ./activate && dyec delete --cluster-name tstpartition --region us-west-2 --profile lsmc --yes` exited `0`; DYEC reported `Cluster deleted`. |  | Live delete completed for the approved target only. |
| VERIFY-001 | Live AWS | Verify cluster absence after deletion completes. | SUCCESS | legitimate_safety_handling | Gate 5 | Codex | `dyec cluster-info --region us-west-2 --profile lsmc` lists only `jemx3` and `vclu10-0-64`; `pcluster describe-cluster --cluster-name tstpartition --region us-west-2` reports cluster does not exist; `aws fsx describe-file-systems --file-system-ids fs-0ba146a98ca409017` returns `FileSystemNotFound`; `aws fsx describe-data-repository-associations --filters Name=file-system-id,Values=fs-0ba146a98ca409017` returns `Associations: []`. |  | Cluster, FSx filesystem, and filesystem DRAs verified absent. |

## Final Status

All rows are terminal. `tstpartition` was deleted and verified absent from `us-west-2`.
