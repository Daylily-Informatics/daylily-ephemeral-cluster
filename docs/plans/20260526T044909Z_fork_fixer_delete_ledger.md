# fork-fixer Delete Ledger

Created: 2026-05-26T04:49:09Z

## Objective

Prepare deletion of the DAY-EC / ParallelCluster cluster `fork-fixer` in `us-west-2` using profile `lsmc`. Live deletion is destructive and requires a second explicit confirmation after this dry-run gate.

## Safety Gate

- Initial destructive request: `delete cluster fork-fixer`
- Live destructive command status: not run.
- Required second confirmation: pending.

## Pre-Delete Evidence

| Field | Value |
|---|---|
| Cluster | `fork-fixer` |
| Region | `us-west-2` |
| Profile | `lsmc` |
| Pre-delete cluster status | `CREATE_COMPLETE` |
| Pre-delete compute fleet | `RUNNING` |
| Headnode | `i-031d99598446e6d56` |
| Headnode state/type | `running` / `r7i.2xlarge` |
| Created | `2026-05-23T14:02:34.644Z` |
| FSx | `fs-0b734921119395885`, mounted at `/fsx`, 9600 GiB configured, about `8.6T` available at inspection. |
| Slurm queue | Empty at `2026-05-26T04:49:09Z`. |
| FSx data note | `/fsx/analysis_results/johnm` contained `ff_*` fork-fixer validation result directories at inspection. |
| Dry-run command | `dyec delete --cluster-name fork-fixer --region us-west-2 --profile lsmc --dry-run` |
| Dry-run result | No AWS resources changed; warned that FSx and DRAs were attached. |
| Active DRAs | `/data/`, `/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/`, `/run_dir_mounts/20260513_ONT_HG003/`, `/run_dir_mounts/602221-20260417_2346/`. |

## Ledger Rows

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| `G0-001` | Record pre-delete state and dry-run evidence. | `SUCCESS` | Pre-delete evidence recorded above. |
| `CONFIRM-001` | Obtain second explicit confirmation for destructive deletion. | `PENDING` | Waiting for user confirmation. |
| `DEL-001` | Run live delete after confirmation. | `BLOCKED` | Live deletion not run. |
| `VERIFY-001` | Verify cluster is deleted/gone after live delete. | `BLOCKED` | Live deletion not run. |
