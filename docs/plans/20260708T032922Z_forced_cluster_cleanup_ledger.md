# 20260708T032922Z Forced Cluster Cleanup Ledger

## Scope

Destructive cleanup requested after explicit destructive-action warning:

- Leave `dragen-fix5-20260708` creating/running and do not delete it.
- Force deletion targets: `dragen-fix2-20260708`, `dragen-fix3-20260708`, `dragen-fix-20260708`, `dragen-103-pg-20260707`.
- For `cmdcat-103-all-20260707`: delete running controllers, kill Slurm jobs, do not export to S3, delete cluster.
- Ensure FSx and EBS volumes are cleaned up for all deletion targets.

## Gate 0 Baseline

| Item | Evidence |
|---|---|
| Approval | User repeated destructive request after warning; `dragen-fix5-20260708` explicitly excluded. |
| Repo | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` |
| Branch/status | `jemdev10`; repo dirty before this ledger with command-catalog changes and untracked evidence files. |
| Region/profile | Assumption from current DYEC context: `us-west-2`, AWS profile `lsmc`. |
| No-export boundary | No S3 export commands will be run for `cmdcat-103-all-20260707`. |

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| CLEAN-001 | Safety | Confirm `dragen-fix5-20260708` is excluded from deletion. | SUCCESS | active_product_contract | Gate 0 | codex | Baseline and final direct verification: `dragen-fix5-20260708` remained `CREATE_COMPLETE`, FSx `fs-0c5cbdc0e04eb3080` `AVAILABLE`, volume `vol-08c15f357d7dab6ff` `in-use`, instance `i-02c50caa38e43e08d` `running`. |  | Excluded cluster left intact. |
| CLEAN-002 | DRAGEN clusters | Delete `dragen-fix2-20260708`, `dragen-fix3-20260708`, `dragen-fix-20260708`, `dragen-103-pg-20260707`. | SUCCESS | live_destructive_cleanup | Gate 1 | codex | `pcluster delete-cluster` returned `DELETE_IN_PROGRESS` for all four; final verification returned `cluster=NOT_FOUND` for all four. |  | Requested DRAGEN delete targets removed from ParallelCluster. |
| CLEAN-003 | cmdcat controllers | Kill controllers and Slurm jobs for `cmdcat-103-all-20260707`; do not export to S3. | SUCCESS | live_destructive_cleanup | Gate 1 | codex | Before: 16 pending `run_bclconvert_lane-*` Slurm jobs and two `ccv_live_*` controller trees. Ran `scancel -u ubuntu`, controller `pkill`, and `tmux` cleanup through DYEC SSM helper. After: empty `squeue` and no matching controller processes. |  | Controllers/jobs killed; no S3 export command run. |
| CLEAN-004 | cmdcat cluster | Delete `cmdcat-103-all-20260707`. | SUCCESS | live_destructive_cleanup | Gate 1 | codex | `pcluster delete-cluster` returned `DELETE_IN_PROGRESS`; final verification returned `cluster=NOT_FOUND`. |  | Cluster deleted. |
| CLEAN-005 | Storage cleanup | Verify/clean FSx and EBS volumes for deletion targets only. | SUCCESS | live_destructive_cleanup | Gate 2 | codex | Direct AWS verification after deletion: all five delete targets had `fsx=[]`, `volumes=[]`, `instances=[]`. `cmdcat` FSx `fs-0e89a93ffac2f0d93` moved through `DELETING` then disappeared. |  | No FSx, EBS, or live EC2 leftovers found for delete targets. |
| CLEAN-006 | Final verification | Report terminal states and any remaining AWS resources. | SUCCESS | final_acceptance | Gate 5 | codex | Final verification loop ended with `__ALL_TARGETS_DIRECT_CLEAN__`; non-target `dragen-fix5-20260708` still running with FSx/volume/instance intact. |  | All rows terminal; objective complete. |

## Execution Notes

- No S3 export is in scope.
- No deletion action may target `dragen-fix5-20260708`.
- Final result: delete targets are absent from ParallelCluster and have no direct FSx, EBS volume, or live EC2 instance matches in `us-west-2`; `dragen-fix5-20260708` remains intact.
