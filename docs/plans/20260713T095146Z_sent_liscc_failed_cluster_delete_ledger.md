## Control Ledger

Controlling request: delete failed ParallelCluster `sent-liscC` in `us-west-2` using AWS profile `lsmc`.

Ledger path: `docs/plans/20260713T095146Z_sent_liscc_failed_cluster_delete_ledger.md`

Gate 0 baseline:

- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster-sentieon-single`
- Branch/ref: `sentieon-single` at `745735931a358d1cec32aa5fe67769b6138361c8` (`10.3.0`).
- Pre-existing dirty state preserved: `daylily_ec/aws/slurm_accounting.py`, `tests/test_slurm_accounting.py`, `docs/plans/20260713T083000Z_sent_hg003_hiomrs_kitchensink_1x_monitor_ledger.md`, and untracked `docs/plans/20260712T192000Z_sent_hg003_runtime_cache_publish.py`.
- Dry run: `dyec delete --cluster-name sent-liscC --region us-west-2 --profile lsmc --dry-run` -> no AWS changes; cluster `CREATE_FAILED`; FSx and DRA present.
- Cluster status: ParallelCluster `CREATE_FAILED`, CloudFormation `ROLLBACK_FAILED`, compute fleet `UNKNOWN`; no tagged EC2 instances remain.
- Destructive scope: delete cluster stack `sent-liscC`, FSx `fs-01468846161689480` (Lustre, 12,000 GiB, `AVAILABLE`), DRA `dra-0f5ef47a1120cf03a` (`/references/` -> `s3://lsmc-dayoa-references-usw2`, `AVAILABLE`), and remaining stack-owned networking/resources. The retained ParallelCluster CloudWatch log group and AWS Budget are outside the supported `dyec delete` teardown.
- DRA metadata task `task-056afe775cf667f98` is terminal `FAILED`: 892,474 succeeded, 1 failed, 892,475 total. No import/export task is currently running.
- Budget `sent-liscC` remains configured at USD 200/month with reported actual spend USD 0.00; budget deletion is not part of this request.
- Approval boundary: the user's deletion request is first approval. Live deletion requires a second explicit approval after this exact scope is presented.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DEL-001 | AWS ParallelCluster | Delete exactly `sent-liscC` and monitor teardown to terminal absence | SUCCESS | legitimate_safety_handling | Destructive AWS second approval | orchestrator | Second approval: `please delete sent-liscC`; `dyec delete --cluster-name sent-liscC --region us-west-2 --profile lsmc --yes` -> `Cluster deleted`; independent checks: ParallelCluster absent, CloudFormation stack absent, FSx tag query `[]`, DRA query `Associations: []`, tagged EC2 query `[]` |  | Cluster stack, FSx, DRA, heartbeat resources, and remaining stack-owned resources were deleted successfully |

## Current Report

All rows terminal: yes.

Objective complete: yes.

Status counts:

- SUCCESS: 1
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0

Live AWS deletion completed in approximately 13 minutes 19 seconds. The source S3 reference data was not deleted. The AWS Budget `sent-liscC` (USD 200/month) and retained log group `/aws/parallelcluster/sent-liscC-202607130911` remain outside the supported cluster teardown, as scoped.
