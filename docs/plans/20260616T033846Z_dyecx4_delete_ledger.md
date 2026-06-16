# dyecX4 Delete Ledger

## Gate 0 Baseline

- Created UTC: `2026-06-16T03:38:46Z`
- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- AWS profile: `lsmc`
- Region: `us-west-2`
- Target cluster: `dyecX4`
- User approval: after destructive warning and altairval impact check, user said `then delete dyecX4`.
- Precheck: `pcluster describe-cluster --region us-west-2 --cluster-name dyecX4`
- Precheck result: `dyecX4 CREATE_COMPLETE CREATE_COMPLETE arn:aws:cloudformation:us-west-2:108782052779:stack/dyecX4/aa2b72b0-63c4-11f1-add4-0a91d4575483 i-05815cdeec4a6dad8`
- Scope boundary: delete only `dyecX4`; do not target `altairval`.
- Data boundary: previous manifest `docs/plans/20260616T001451Z_dyecx4_unexported_export_manifest.md` recorded 106 analysis dirs inspected, 82 needing export review, and no active workflow process lines.

## Control Ledger

| ID | Requirement | Status | Evidence | Terminal Note |
|---|---|---|---|---|
| DEL-001 | Verify target cluster and approval before deletion | SUCCESS | Precheck listed `dyecX4` stack and headnode; explicit user approval received | Ready to delete `dyecX4` only. |
| DEL-002 | Run live `pcluster delete-cluster` for `dyecX4` only | SUCCESS | `pcluster delete-cluster --region us-west-2 --cluster-name dyecX4` returned `clusterStatus=DELETE_IN_PROGRESS`, `cloudformationStackStatus=DELETE_IN_PROGRESS` | Delete request accepted by ParallelCluster. |
| DEL-003 | Poll deletion until terminal state or cluster absent from active list | SUCCESS | Final poll at `2026-06-16T03:51:38Z`: `dyecX4=NOT_DESCRIBABLE`; active cluster list contained only `altairval=CREATE_COMPLETE`; final `describe-cluster dyecX4` returned `Cluster 'dyecX4' does not exist or belongs to an incompatible ParallelCluster major version.` | `dyecX4` is deleted/absent from ParallelCluster. |
| DEL-004 | Verify `altairval` remains present | SUCCESS | `pcluster describe-cluster --cluster-name altairval` -> `altairval CREATE_COMPLETE CREATE_COMPLETE i-05b2743c3c3fffa93 running` | `altairval` remains present and running. |

## Final Report

- `dyecX4` delete command accepted and completed to absent/not describable state.
- Final active cluster list in `us-west-2` under profile `lsmc`: `altairval=CREATE_COMPLETE`.
- No command targeted `altairval`.
