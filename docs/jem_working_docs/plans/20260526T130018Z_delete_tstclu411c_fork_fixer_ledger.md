# Delete tstClu-4-1-1c And fork-fixer Ledger

Created: 2026-05-26T13:00:18Z

Controlling request: delete clusters `tstClu-4-1-1c` and `fork-fixer` in `us-west-2`.

Destructive approval: user provided the second explicit confirmation string `CONFIRM DELETE CLUSTERS tstClu-4-1-1c fork-fixer` in this thread after dry-run scope was reported.

## Gate 0 Inventory

| Item | Evidence |
|---|---|
| Repo | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| Branch | `codex/analysis-id-export-catalog-validation...origin/codex/analysis-id-export-catalog-validation` |
| Pre-existing dirty state | `docs/plans/20260526T113326Z_splitdra_new_cluster_validation_ledger.md` was already modified before this delete ledger. |
| AWS profile and region | `AWS_PROFILE=lsmc`, `us-west-2` |
| Target clusters | `tstClu-4-1-1c`, `fork-fixer` |
| Pre-delete cluster state | Both `pcluster describe-cluster` calls reported `clusterStatus=CREATE_COMPLETE` and `computeFleetStatus=RUNNING`. |
| Pre-delete Slurm state | `dyec headnode jobs --profile lsmc --region us-west-2 --cluster tstClu-4-1-1c` and the same command for `fork-fixer` returned only the header; no Slurm jobs. |
| Dry-run effect for `tstClu-4-1-1c` | Would delete cluster stack plus FSx `fs-000b2a8e8c15aae8b`; active DRAs: `dra-024eaa89ab141a664`, `dra-0d6c4bb354c08ffd8`, `dra-03e636ae2e0c6b0d7`. |
| Dry-run effect for `fork-fixer` | Would delete cluster stack plus FSx `fs-0b734921119395885`; active DRAs: `dra-0a592634650dd2f5c`, `dra-08f17b5dc6c296b25`, `dra-0d9808292112c9ed6`, `dra-0d656ef58546677d9`. |

## Execution Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DEL-001 | Safety | Verify destructive approval and empty queues before deletion. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | User confirmation string received; both `dyec headnode jobs` checks returned no Slurm jobs. |  | Preconditions satisfied for the approved destructive action. |
| DEL-002 | Cluster delete | Delete `tstClu-4-1-1c` and verify disappearance. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `dyec delete --profile lsmc --region us-west-2 --cluster-name tstClu-4-1-1c --yes` reached `Cluster deleted`; spot checks showed FSx `fs-000b2a8e8c15aae8b` progressed through `DELETING` and then `FileSystemNotFound`. |  | Cluster monitor completed and the target cluster no longer exists. |
| DEL-003 | Cluster delete | Delete `fork-fixer` and verify disappearance. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `dyec delete --profile lsmc --region us-west-2 --cluster-name fork-fixer --yes` reached `Cluster deleted`; FSx `fs-0b734921119395885` returned `FileSystemNotFound`. |  | Cluster monitor completed and the target cluster no longer exists. |
| DEL-004 | Final verification | Verify both clusters no longer describe after delete monitors finish. | SUCCESS | contract_test | Gate 5 | orchestrator | `pcluster list-clusters --region us-west-2` listed only `splitdra-smoke-20260526` and `hyb-hg003`; `pcluster describe-cluster` for both deleted targets returned `does not exist`; CloudFormation `describe-stacks` for both deleted targets returned stack-not-found validation errors; both FSx IDs returned `FileSystemNotFound`. |  | Final independent verification passed at 2026-05-26T13:17:40Z. |

## Final State

All tracked rows are terminal `SUCCESS`.

Deleted clusters:

- `tstClu-4-1-1c`
- `fork-fixer`

Verification at 2026-05-26T13:17:40Z:

- ParallelCluster no longer describes either deleted cluster.
- CloudFormation stacks for both deleted clusters no longer exist.
- FSx filesystems `fs-000b2a8e8c15aae8b` and `fs-0b734921119395885` no longer exist.
