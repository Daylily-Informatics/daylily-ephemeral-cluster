# Illumina 94 Export And Delete Ledger

Created: 2026-07-07T11:50:24Z

## Scope

User request: determine whether `illumina-94-c02` and `illumina-94-c01` have anything running on the headnodes or in Slurm. If not, export `/fsx/analysis_results/**` for each cluster to S3, then delete the clusters.

Safety boundary: cluster deletion is destructive and requires a separate explicit confirmation after export status is known. Export and read-only inspection are approved by the user request.

## Gate 0 Inventory

- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch/status command: `git status --short --branch`
- Baseline branch output: `## jemdev10`
- Cluster inventory command: `source ./activate; dyec cluster-info --profile lsmc --region us-west-2`
- Active cluster output: `illumina-94-c02 CREATE_COMPLETE 184.34.55.247`; `illumina-94-c01 CREATE_COMPLETE 54.218.236.156`
- Ledger path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260707T115024Z_illumina94_export_delete_ledger.md`

## Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| ILM94-001 | Inventory | Confirm target cluster/headnode state for `illumina-94-c02` and `illumina-94-c01`. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | `dyec cluster-info --profile lsmc --region us-west-2` shows both targets `CREATE_COMPLETE`; EC2 tag inventory shows each cluster has 1 running headnode plus 5 running compute nodes. |  | Both target clusters are active. |
| ILM94-002 | Runtime | Determine whether Slurm has running/pending jobs on either cluster. | BLOCKED | legitimate_safety_handling | Gate 0 | orchestrator | `dyec headnode jobs --cluster illumina-94-c02` shows 5 RUNNING and 42 PENDING; `dyec headnode jobs --cluster illumina-94-c01` shows 5 RUNNING and 42 PENDING. | Active Slurm jobs and pending jobs exist on both clusters. | Export/delete condition is not met. |
| ILM94-003 | Runtime | Determine whether headnode controller/tmux/workflow processes are active on either cluster. | BLOCKED | legitimate_safety_handling | Gate 0 | orchestrator | Read-only SSM process probe at 2026-07-07T11:51Z shows live DayOA `day_run`/Snakemake processes on both headnodes; c02 session `illumina_dnascope_94samples_c02_20260707T052406Z`; c01 sessions include active `illumina_dnascope_94samples_c01_20260707T052406Z`. | Active DayOA/Snakemake controllers exist on both headnodes. | Export/delete condition is not met. |
| ILM94-004 | Export | If no jobs/processes are running, export `/fsx/analysis_results/**` from each cluster to S3. | BLOCKED | legitimate_safety_handling | Gate 1 | orchestrator | Export command shape inspected with `dyec export --help`; no export run because runtime checks found active jobs/controllers. | User conditioned export on no running headnode or Slurm work; active work is present. | Blocked until both clusters have no active controller processes and empty Slurm queues. |
| ILM94-005 | Delete | Delete `illumina-94-c02` and `illumina-94-c01` after successful export. | BLOCKED | legitimate_safety_handling | Destructive Approval | orchestrator | Deletion requested conditionally, but destructive AWS policy requires second explicit confirmation after export evidence. | Separate explicit destructive approval required after export status is known. | Blocked until user confirms exact deletion after export. |

## Final Counts

- `SUCCESS`: 1
- `BLOCKED`: 4
