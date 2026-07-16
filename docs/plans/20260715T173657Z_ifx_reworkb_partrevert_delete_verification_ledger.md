# ifx-reworkB and partrevert deletion verification ledger

Created: 2026-07-15T17:36:57Z

## Objective

Delete exactly the ParallelCluster clusters `ifx-reworkB` and `partrevert` in
`us-west-2` after the required destructive-action approval gate, or verify that
the requested deletion is already terminal and perform no mutation.

## Gate 0 inventory

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch: `jem-dev`, 34 commits behind `origin/jem-dev` at inspection time.
- Pre-existing untracked plan artifacts were preserved and were not modified.
- AWS profile/region: `lsmc`, `us-west-2`.
- Read-only inventory commands:
  - `pcluster list-clusters --region us-west-2`
  - `pcluster describe-cluster --cluster-name <cluster> --region us-west-2`
  - `aws cloudformation describe-stacks --stack-name <cluster>`
  - `aws cloudformation list-stacks --stack-status-filter DELETE_COMPLETE`
  - `aws ec2 describe-instances` by cluster tag and known headnode ID
  - `aws fsx describe-file-systems` by cluster tag and known filesystem ID
  - `aws fsx describe-data-repository-associations` by known filesystem ID

## Control ledger

| ID | Area | Requirement | Status | Category | Approval gate | Owner | Evidence | Root cause | Terminal note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Inventory | Freeze current ParallelCluster, CloudFormation, EC2, FSx, and DRA state for exactly the two requested clusters | SUCCESS | plan_amendment | Gate 0 | orchestrator | ParallelCluster list contains neither name; both `describe-cluster` calls report that the cluster does not exist; both active CloudFormation stack lookups report absent; no cluster-tagged EC2 or FSx resources exist |  | Read-only baseline completed; no AWS mutation occurred |
| DEL-001 | `ifx-reworkB` | Delete the cluster and cluster-owned resources | NO_LONGER_NEEDED | legitimate_safety_handling | Destructive action | orchestrator | CloudFormation deleted-stack record: `DELETE_COMPLETE`, deletion time `2026-07-12T13:43:35.195000+00:00`; known FSx `fs-0d7596cf840aa0302` returns `FileSystemNotFound`; zero DRAs; known headnode `i-059642d9ee4d5c9ea` absent | Requested resource was already terminally deleted before this turn | No delete command was submitted; no S3 object was changed or deleted |
| DEL-002 | `partrevert` | Delete the cluster and cluster-owned resources | NO_LONGER_NEEDED | legitimate_safety_handling | Destructive action | orchestrator | CloudFormation deleted-stack record: `DELETE_COMPLETE`, deletion time `2026-07-13T10:27:26.822000+00:00`; known FSx `fs-0b7bbbf0ff7f81436` returns `FileSystemNotFound`; zero DRAs; known headnode `i-061e6053f5e015e5a` absent | Requested resource was already terminally deleted before this turn | No delete command was submitted; no S3 object was changed or deleted |
| VAL-001 | Closeout | Verify no requested live resource remains and no unrelated resource was touched | SUCCESS | contract_test | Gate 5 | orchestrator | Both names absent from current ParallelCluster inventory and active CloudFormation stacks; both appear only as `DELETE_COMPLETE`; no live EC2, FSx, or DRA remains |  | All rows terminal; requested end state was already satisfied |

## Final state

- All ledger rows are terminal.
- Objective is satisfied because both requested clusters were already deleted.
- No destructive API call, S3 mutation, or unrelated cluster action occurred in
  this verification turn.
