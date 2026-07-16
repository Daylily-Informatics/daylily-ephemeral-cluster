# `ursa-m-rgx-bk3j` Delete Ledger

- Created: `2026-07-13T07:50:49Z`
- AWS profile: `lsmc`
- AWS region: `us-west-2`
- Cluster: `ursa-m-rgx-bk3j`
- Objective: delete the named ParallelCluster only after dry-run inventory and a second explicit destructive approval.

## Gate 0 inventory

| Surface | State | Evidence |
| --- | --- | --- |
| ParallelCluster | `CREATE_COMPLETE` | `pcluster list-clusters --region us-west-2` listed `ursa-m-rgx-bk3j`, ParallelCluster `3.15.0`, Slurm scheduler. |
| Headnode | `RUNNING` | EC2 `i-03c72fd0408b5401b`, `r7i.4xlarge`, private IP `10.0.0.81`. |
| Compute instances | None active | Cluster-tagged EC2 inventory returned only the headnode. |
| Slurm jobs | None | At `2026-07-13T07:50:49Z`, the standard Daylily `squeue` format returned only the header. |
| Workflow controllers | None | `ps -fu ubuntu` found no `dy-r`, `bin/day_run`, or `snakemake` controller processes. |
| Headnode root EBS | `IN_USE` | `vol-04d0d7a1be0169381`, `421 GiB` `gp3`, `DeleteOnTermination=true`. |
| Cluster FSx | `AVAILABLE` | `fs-04708883369863067`, Lustre `SCRATCH_2`, `4,800 GiB` SSD. CloudFormation logical resource `FSX58a0df7fe73f7b6b` has `DeletionPolicy: Delete` and `UpdateReplacePolicy: Delete`. |
| FSx contents | Present | Headnode `df -h /fsx` reported about `61 MiB` used. Top-level paths: `analysis_results`, `data`, `logs`, `references`, `resources`, `run_dir_mounts`, `scratch`, `tmp`, and `work`. |
| FSx backups | None | `describe-backups` returned an empty list for `fs-04708883369863067`. |
| DRA | `AVAILABLE` | `dra-0453466176956c8da`, `/references/ -> s3://lsmc-dayoa-references-usw2`, auto-import only; no auto-export policy was reported. |

## Execution ledger

| ID | Action | State | Evidence / next gate |
| --- | --- | --- | --- |
| DEL-001 | Inventory cluster, EC2, Slurm, controller, FSx, backup, and DRA state. | `SUCCESS` | Gate 0 table above. |
| DEL-002 | Run `dyec delete --profile lsmc --region us-west-2 --cluster-name ursa-m-rgx-bk3j --dry-run`. | `SUCCESS` | Dry-run reported `CREATE_COMPLETE`, FSx `fs-04708883369863067`, and DRA `dra-0453466176956c8da`; it explicitly changed no AWS resources. |
| DEL-003 | Obtain second explicit destructive approval after restating the exact effect. | `PENDING` | Deletion will terminate headnode `i-03c72fd0408b5401b`, delete its `421 GiB` root EBS volume, delete the cluster stack and Slurm state, delete Scratch2 FSx `fs-04708883369863067` and all remaining `/fsx` contents, and remove DRA `dra-0453466176956c8da`. The S3 reference bucket is not itself a deletion target. |
| DEL-004 | Execute live `dyec delete ... --yes`. | `PENDING` | Blocked on DEL-003. |
| DEL-005 | Verify terminal absence across ParallelCluster, CloudFormation, EC2, EBS, FSx, DRA, and SSM. | `PENDING` | Runs only after successful live deletion. |

## Current boundary

The dry run and inventory are complete. No live deletion has happened. The objective is not complete because the required second explicit approval has not yet been received after disclosure of the exact destructive effect.
