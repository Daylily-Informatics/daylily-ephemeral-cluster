# `ursa-m-rgx-br75` Delete Ledger

- Created: `2026-07-14T22:37:29Z`
- AWS account: `108782052779`
- AWS profile: `lsmc`
- AWS region: `us-west-2`
- Cluster: `ursa-m-rgx-br75`
- Objective: delete the named ParallelCluster only after dry-run inventory and a second explicit destructive approval following disclosure of the exact effect.

## Gate 0 inventory

- Controlling ledger: `docs/plans/20260714T223729Z_ursa_m_rgx_br75_delete_ledger.md`
- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch `jem-dev`, 34 commits behind `origin/jem-dev`.
- Pre-existing repo state: seven untracked `docs/plans/` artifacts were present before this ledger; they were not changed.
- Live limits: inspection and dry-run only. No AWS resource mutation is authorized until the exact effect is disclosed and a second explicit approval is received.

| Surface | State | Evidence |
| --- | --- | --- |
| ParallelCluster | `CREATE_COMPLETE`; compute fleet `RUNNING` | `pcluster describe-cluster --region us-west-2 --cluster-name ursa-m-rgx-br75`; ParallelCluster `3.15.0`, Slurm scheduler. |
| Headnode | `RUNNING` | EC2 `i-0eb29aeecd07951c5`, `r7i.4xlarge`, private IP `10.0.0.45`. |
| Compute instances | None active | Cluster-tagged EC2 inventory returned only the headnode. |
| Slurm jobs | None | At `2026-07-14T22:38:29Z`, the standard Daylily `squeue` format returned only the header. |
| Workflow controllers | None | `ps -fu ubuntu` found only the inspection login shell and `ps`; no `dy-r`, `bin/day_run`, or Snakemake controller process was active. |
| Headnode root EBS | `IN_USE` | `vol-0a5cc72a38a2bbfb0`, encrypted `421 GiB` `gp3`, `DeleteOnTermination=true`. |
| Cluster FSx | `AVAILABLE` | `fs-04c889bc3282054ee`, Lustre `SCRATCH_2`, `4,800 GiB` SSD. CloudFormation logical resource `FSXE99c7363dff844d2` has `DeletionPolicy: Delete` and `UpdateReplacePolicy: Delete`. |
| FSx contents | Present | Headnode `df -h /fsx` reported about `61 MiB` used. Top-level paths: `analysis_results`, `data`, `logs`, `references`, `resources`, `run_dir_mounts`, `scratch`, `tmp`, and `work`. |
| FSx backups | None | `describe-backups` returned an empty list for `fs-04c889bc3282054ee`. |
| DRA | `AVAILABLE` | `dra-0d02b228cba2397e2`, `/references/ -> s3://lsmc-dayoa-references-usw2`, auto-import only; no auto-export policy was reported. |

## Execution ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DEL-001 | Inventory | Inventory cluster, EC2, Slurm, controller, FSx, backup, DRA, and deletion-policy state. | `SUCCESS` | `legitimate_safety_handling` | Gate 0 | orchestrator | Gate 0 table above. |  | Exact live deletion scope recorded. |
| DEL-002 | Dry-run | Run `dyec delete --dry-run --profile lsmc --region us-west-2 --cluster-name ursa-m-rgx-br75`. | `SUCCESS` | `legitimate_safety_handling` | Gate 0 | orchestrator | Dry-run reported `CREATE_COMPLETE`, FSx `fs-04c889bc3282054ee`, and DRA `dra-0d02b228cba2397e2`; no AWS resources changed. |  | Supported dry-run completed. |
| DEL-003 | Approval | Obtain second explicit destructive approval after restating the exact effect. | `BLOCKED` | `legitimate_safety_handling` | Destructive approval | user | Exact effect is recorded below. | Required second approval has not yet been received after effect disclosure. | Unblock only with a new explicit approval after the user sees the exact effect. |
| DEL-004 | Live deletion | Execute `dyec delete --profile lsmc --region us-west-2 --cluster-name ursa-m-rgx-br75 --yes`. | `BLOCKED` | `feature_implementation` | Destructive approval | orchestrator | Not executed. | DEL-003 is blocked. | No live deletion has occurred. |
| DEL-005 | Verification | Verify terminal absence across ParallelCluster, CloudFormation, EC2, EBS, FSx, DRA, and SSM. | `BLOCKED` | `contract_test` | Destructive approval | orchestrator | Not executed. | Live deletion has not occurred. | Verification follows successful live deletion. |

## Exact destructive effect requiring second approval

Live deletion will:

- delete the ParallelCluster/CloudFormation stack `ursa-m-rgx-br75` and its cluster-owned supporting resources;
- terminate running headnode `i-0eb29aeecd07951c5` and delete encrypted `421 GiB` root EBS volume `vol-0a5cc72a38a2bbfb0`;
- delete Scratch2 Lustre FSx `fs-04c889bc3282054ee` under the stack's `DeletionPolicy: Delete`, permanently removing all remaining `/fsx` contents (currently about `61 MiB`) with no FSx backup present;
- delete reference DRA `dra-0d02b228cba2397e2`.

The source S3 bucket `s3://lsmc-dayoa-references-usw2` is not a deletion target. No Slurm jobs, compute instances, or workflow controllers were active at the inventory timestamp.

## Current boundary

All current rows are terminal, but the objective is not complete: inventory and dry-run succeeded, while live deletion and verification are blocked on the required second explicit approval after disclosure of the exact destructive effect. No live AWS resources have been changed.
