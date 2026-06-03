# jem-bucktst1 / jem-bucktst2 Delete Ledger

Date: 2026-05-28T14:27:10Z

## Objective

Prepare the requested ParallelCluster deletion for `jem-bucktst2` and `jem-bucktst1` in account `108782052779`, region `us-west-2`, without executing destructive AWS changes until the user gives a second explicit confirmation in this thread.

## Gate 0 Inventory

| Item | Evidence |
|---|---|
| Ledger path | `docs/plans/20260528T142710Z_jem_bucktst_delete_ledger.md` |
| Repo path | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| Branch | `codex/dyec-dewey-registration-refactor-20260528...origin/codex/dyec-dewey-registration-refactor-20260528` |
| Pre-existing dirty state | `?? docs/plans/20260528T132738Z_hg003_20x10x_qc_j300_ledger.md` was present before this ledger. |
| User request | "can you pcluster delete jem-bucktst2 and jem-bucktst1" |
| Destructive approval state | Initial request permitted inspection/prep only; second explicit approval was received before live deletion. |
| Profiles checked | `AWS_PROFILE=lsmc aws sts get-caller-identity --region us-west-2` and `AWS_PROFILE=daylily-service-lsmc aws sts get-caller-identity --region us-west-2` both resolved account `108782052779`. |
| ParallelCluster CLI | `pcluster version` returned `3.13.2`. |
| Cluster list | `AWS_PROFILE=daylily-service-lsmc pcluster list-clusters --region us-west-2` listed `goodole3` and `jem-bucktst1`; it did not list `jem-bucktst2`. |
| `jem-bucktst1` pcluster state | `AWS_PROFILE=daylily-service-lsmc pcluster describe-cluster --cluster-name jem-bucktst1 --region us-west-2` returned `clusterStatus=CREATE_FAILED`, `cloudFormationStackStatus=ROLLBACK_COMPLETE`, `computeFleetStatus=UNKNOWN`, stack ARN `arn:aws:cloudformation:us-west-2:108782052779:stack/jem-bucktst1/c17806c0-593a-11f1-8b9c-028ec9dd1601`. |
| `jem-bucktst1` CloudFormation state | `AWS_PROFILE=daylily-service-lsmc aws cloudformation describe-stacks --stack-name jem-bucktst1 --region us-west-2` returned `StackStatus=ROLLBACK_COMPLETE`, `DeletionTime=2026-05-26T20:02:28.355Z`, termination protection disabled. |
| `jem-bucktst1` resources | `AWS_PROFILE=daylily-service-lsmc aws cloudformation list-stack-resources --stack-name jem-bucktst1 --region us-west-2` showed prior EC2, FSx, DRA, IAM, Route53, DynamoDB, dashboard, and security-group resources already `DELETE_COMPLETE`; CloudWatch log groups were `DELETE_SKIPPED`. |
| `jem-bucktst1` FSx/DRA live check | `AWS_PROFILE=daylily-service-lsmc aws fsx describe-file-systems --region us-west-2 --query ...` returned `[]` for `jem-bucktst1` / `jem-bucktst2` cluster tags. |
| `jem-bucktst2` pcluster state | `AWS_PROFILE=daylily-service-lsmc pcluster describe-cluster --cluster-name jem-bucktst2 --region us-west-2` returned `Cluster 'jem-bucktst2' does not exist or belongs to an incompatible ParallelCluster major version.` |
| `jem-bucktst2` CloudFormation state | `AWS_PROFILE=daylily-service-lsmc aws cloudformation describe-stacks --stack-name jem-bucktst2 --region us-west-2` returned `Stack with id jem-bucktst2 does not exist`. |
| `jem-bucktst2` resource state | `AWS_PROFILE=daylily-service-lsmc aws cloudformation list-stack-resources --stack-name jem-bucktst2 --region us-west-2` returned `Stack with id jem-bucktst2 does not exist`; FSx tag query returned no file systems. |

## Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DEL-001 | Approval | Restate the destructive effect and obtain second explicit approval before live deletion. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | User replied: `Confirm delete jem-bucktst1 in us-west-2 using AWS_PROFILE=daylily-service-lsmc or lsmc`. |  | Second explicit destructive approval received; using the prepared `daylily-service-lsmc` profile. |
| DEL-002 | jem-bucktst1 | Delete the remaining ParallelCluster/CloudFormation rollback-complete stack. | SUCCESS | feature_implementation | Gate 0 | orchestrator | Delete command was run with `AWS_PROFILE=daylily-service-lsmc`. The command returned a ParallelCluster lookup error after the delete request, but post-checks showed the intended live state: `pcluster list-clusters` no longer listed `jem-bucktst1`; `aws cloudformation list-stacks --stack-status-filter DELETE_COMPLETE ...` showed `jem-bucktst1` `DELETE_COMPLETE` with `DeletionTime=2026-05-28T14:27:12.348Z`; `aws cloudformation describe-stacks --stack-name jem-bucktst1` returned stack-not-found; FSx `fs-05d11bd2f84ed72ad` returned `FileSystemNotFound`; DRA `dra-03e7a9955d64a5843` returned no associations; EC2 headnode `i-0872529b14bbb75b0` returned no instances. |  | Cluster stack deletion complete and live cluster resources are absent. |
| DEL-003 | jem-bucktst2 | Delete the requested cluster/stack if present. | NO_LONGER_NEEDED | not_applicable_after_inspection | Gate 0 | orchestrator | `pcluster describe-cluster` says cluster does not exist; CloudFormation says stack does not exist; FSx tag query returned no file systems. |  | No live `jem-bucktst2` pcluster/CloudFormation target remains to delete in account `108782052779`, region `us-west-2`. |

## Executed Command

```bash
AWS_PROFILE=daylily-service-lsmc pcluster delete-cluster --cluster-name jem-bucktst1 --region us-west-2
```

## Final Status

As of 2026-05-28T14:27Z, all ledger rows are terminal.

- `jem-bucktst1`: `DELETE_COMPLETE`.
- `jem-bucktst2`: no live ParallelCluster target remained; CloudFormation stack history shows `DELETE_COMPLETE` at `2026-05-28T14:23:35.110Z`.
- Remaining live ParallelCluster list in `us-west-2` under `daylily-service-lsmc`: `goodole3`.
- Retained log group: `/aws/parallelcluster/jem-bucktst1-202605261940`, `storedBytes=248675`, `retentionInDays=3`.
