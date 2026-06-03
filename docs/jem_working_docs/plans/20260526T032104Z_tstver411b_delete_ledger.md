# tstVer4-1-1b Delete Ledger

Created: 2026-05-26T03:21:04Z

## Objective

Delete the DAY-EC / ParallelCluster cluster `tstVer4-1-1b` in `us-west-2` using profile `lsmc` after explicit second confirmation from the user.

## Safety Gate

- Initial destructive request: `delete tstVer4-1-1b`
- Dry-run/prep completed before live deletion.
- User second confirmation: `confirm deletion of tstVer4-1-1b`
- Live destructive command authorized after the second confirmation.

## Pre-Delete Evidence

| Field | Value |
|---|---|
| Cluster | `tstVer4-1-1b` |
| Region | `us-west-2` |
| Profile | `lsmc` |
| Pre-delete cluster status | `CREATE_COMPLETE` |
| Pre-delete compute fleet | `RUNNING` |
| Headnode | `i-0e08d1087dcce4d0a` |
| FSx | `fs-0445f465f1a8d6b48` |
| FSx data note | `/fsx/analysis_results/johnm` contained the `tstVer4-1-1b` validation outputs at pre-delete inspection. |
| Dry-run command | `dyec delete --cluster-name tstVer4-1-1b --region us-west-2 --profile lsmc --dry-run` |
| Dry-run result | No AWS resources changed; warned that FSx and DRAs were attached. |

## Ledger Rows

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| `G0-001` | Record pre-delete state and explicit confirmation. | `SUCCESS` | Pre-delete evidence and confirmation recorded above. |
| `DEL-001` | Run live delete. | `SUCCESS` | `dyec delete --cluster-name tstVer4-1-1b --region us-west-2 --profile lsmc --yes` completed successfully and reported `Cluster deleted`. |
| `VERIFY-001` | Verify cluster is deleted/gone. | `SUCCESS` | `AWS_PROFILE=lsmc pcluster describe-cluster --cluster-name tstVer4-1-1b --region us-west-2` returned `Cluster 'tstVer4-1-1b' does not exist or belongs to an incompatible ParallelCluster major version.` |

## Final Status

`tstVer4-1-1b` deletion completed successfully. ParallelCluster no longer describes the cluster in `us-west-2`.
