# tstVer4-1-1 Cluster Delete Ledger

## Objective

Prepare deletion of ParallelCluster `tstVer4-1-1` in `us-west-2` for AWS profile `lsmc`. This ledger records read-only state before any destructive action.

## Safety Boundary

No live delete has been run. Deleting this cluster is destructive because it will delete the ParallelCluster CloudFormation stack and managed cluster resources, including the headnode and the cluster-managed FSx for Lustre scratch filesystem. A separate explicit confirmation is required before running the delete command.

## Gate 0 Baseline

| Item | Evidence |
|---|---|
| Cluster | `tstVer4-1-1` |
| Profile / region | `lsmc` / `us-west-2` |
| `pcluster describe-cluster` | `clusterStatus=CREATE_COMPLETE`, `cloudFormationStackStatus=CREATE_COMPLETE`, `computeFleetStatus=RUNNING`, ParallelCluster `3.13.2` |
| Headnode | `i-05d8f894dc3466001`, `r7i.4xlarge`, state `running`, private IP `10.0.0.29`, public IP `54.187.51.167` |
| CloudFormation stack | `arn:aws:cloudformation:us-west-2:108782052779:stack/tstVer4-1-1/bf26e910-5640-11f1-9d11-02fffc42152d` |
| FSx file system | `fs-08ad90e0ae5dd62a1`, `AVAILABLE`, Lustre `SCRATCH_2`, SSD, `4800` GiB, mount name `lzlz7b4v` |
| DRA | `dra-00ae17bd9eee386a9`, `AVAILABLE`, `/data/` to `s3://lsmc-dayoa-omics-analysis-us-west-2/data/` |
| Slurm queue | Empty at `2026-05-23T07:00:18Z` from headnode SSM command `c1ee4696-4e92-46eb-9ea0-5a97bf184878` |
| FSx usage | `/fsx` `4.4T` total, `128G` used, `4.3T` available, `3%` use |
| Analysis dirs | `/fsx/analysis_results/ubuntu` `3.3G`; `/fsx/analysis_results/daylily` `33K`; `/fsx/analysis_results/cromwell_executions` `33K` |

## Tracking Rows

| ID | Area | Requirement | Status | Evidence | Terminal Note |
|---|---|---|---|---|---|
| G0-001 | Inventory | Record current cluster, stack, FSx, DRA, queue, and FSx usage before delete. | SUCCESS | Gate 0 Baseline above. | Read-only inventory complete. |
| CONFIRM-001 | Safety | Request separate explicit confirmation before live destructive delete. | SUCCESS | User replied `CONFIRM DELETE CLUSTER tstVer4-1-1` on `2026-05-23`. | Destructive delete approved. |
| DELETE-001 | Cluster delete | Run `AWS_PROFILE=lsmc pcluster delete-cluster -n tstVer4-1-1 --region us-west-2` only after confirmation. | SUCCESS | Delete command returned `clusterStatus=DELETE_IN_PROGRESS` and `cloudformationStackStatus=DELETE_IN_PROGRESS` at `2026-05-23T08:07Z`; final verification at `2026-05-23T08:17Z` showed `pcluster describe-cluster` says cluster does not exist, CloudFormation stack does not exist, FSx `fs-08ad90e0ae5dd62a1` does not exist, and DRA `dra-00ae17bd9eee386a9` returns no associations. | Cluster deleted. |

## Evidence Log

- `2026-05-23T08:07Z`: Ran `AWS_PROFILE=lsmc pcluster delete-cluster -n tstVer4-1-1 --region us-west-2` after explicit confirmation. Command returned `clusterStatus=DELETE_IN_PROGRESS` and stack ARN `arn:aws:cloudformation:us-west-2:108782052779:stack/tstVer4-1-1/bf26e910-5640-11f1-9d11-02fffc42152d`.
- `2026-05-23T08:07Z` through `2026-05-23T08:17Z`: Polling showed headnode removed immediately, compute fleet `UNKNOWN`, and CloudFormation `DELETE_IN_PROGRESS`.
- `2026-05-23T08:12Z`: CloudFormation events showed DRA cleanup complete and FSx `fs-08ad90e0ae5dd62a1` in `DELETE_IN_PROGRESS`; direct FSx DRA lookup returned no associations for `dra-00ae17bd9eee386a9`.
- `2026-05-23T08:17Z`: Final checks showed `pcluster describe-cluster` returned `Cluster 'tstVer4-1-1' does not exist or belongs to an incompatible ParallelCluster major version.`, CloudFormation returned `Stack with id tstVer4-1-1 does not exist`, FSx returned `File system 'fs-08ad90e0ae5dd62a1' does not exist`, and DRA lookup returned an empty `Associations` list.

## Final Report

- Cluster `tstVer4-1-1` deleted.
- CloudFormation stack `tstVer4-1-1` deleted.
- Headnode `i-05d8f894dc3466001` removed with the stack.
- Managed FSx filesystem `fs-08ad90e0ae5dd62a1` deleted.
- DRA `dra-00ae17bd9eee386a9` deleted.
- No S3 objects were deleted by these commands.
