# `jul8itelx4` Cluster Deletion Ledger

Created: 2026-07-11T06:36:17Z

## Control Ledger

Controlling plan: this ledger
Ledger path: `docs/plans/20260711T063617Z_jul8itelx4_delete_ledger.md`

Gate 0 baseline:

- Scope: inspect and, only after a second explicit approval, delete ParallelCluster `jul8itelx4` in AWS account `108782052779`, profile `lsmc`, region `us-west-2`.
- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch `jem-dev` tracking `origin/jem-dev`.
- Pre-existing repo state: `M AGENTS.md`; this is user-owned and outside this ledger's write scope.
- Runtime: DYEC `10.0.160.dev0+gbe84e437d.d20260711`, CLI Core `2.1.1`, project root `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`.
- Safety boundary: the user's request is first approval only. `dyec delete --dry-run` and read-only inventory are authorized. No `dyec delete --yes`, confirmation response, or other destructive AWS action is authorized until the exact effect is restated and the user gives a second explicit approval.
- Assumptions and live limits: cluster state, jobs, controllers, FSx, DRA, CloudFormation, EC2, and SSM evidence must be refreshed live. S3 objects are outside the deletion scope unless live tooling proves otherwise; no S3 delete commands are authorized.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| JUL8-001 | AWS/DYEC | Freeze current cluster, queue, controller, FSx, DRA, EC2, CloudFormation, and SSM inventory | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | 2026-07-11T06:37:29Z: cluster and stack `CREATE_COMPLETE`; compute fleet `RUNNING`; headnode `i-02946c880916d6dbc` running and SSM-online; no compute EC2 instances; `squeue` header only; no `snakemake` controller; FSx `fs-021b9667d227d3f65` `AVAILABLE`, `SCRATCH_2`, 7,200 GB provisioned; mounted usage 638 GB of 6.6 TiB; four `AVAILABLE` DRAs; no active export task |  | Gate 0 inventory frozen without changing AWS state. |
| JUL8-002 | AWS/DYEC | Run `dyec delete --dry-run` for exact target | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | `dyec delete --dry-run --profile lsmc --region us-west-2 --cluster-name jul8itelx4` -> exit 0; reported `No AWS resources were changed`, FSx warning, and all four DRAs |  | Dry-run completed against the exact live target. |
| JUL8-003 | Approval | Restate exact destructive effect and obtain second explicit user approval | SUCCESS | active_product_contract | Destructive approval | user | User gave the second explicit approval: `do not export fsx, delete the cluster jul8itelx4`, after being told the FSx held about 638 GB and would be permanently destroyed with four DRAs |  | Destructive deletion is explicitly authorized without an FSx export. |
| JUL8-004 | AWS/DYEC | Execute live cluster deletion only after JUL8-003 succeeds | SUCCESS | feature_implementation | Destructive approval | orchestrator | 2026-07-11T06:39:32Z immediate drift check: zero Slurm jobs and zero `snakemake` controllers. `dyec delete --yes --profile lsmc --region us-west-2 --cluster-name jul8itelx4` removed heartbeat resources, accepted teardown, monitored `DELETE_IN_PROGRESS`, and exited 0 with `Cluster deleted` after about 14 minutes |  | Approved deletion completed without an FSx export. |
| JUL8-005 | AWS/DYEC | Verify terminal absence across PCluster, CloudFormation, headnode/compute EC2, managed FSx, DRAs, and SSM | SUCCESS | contract_test | Final acceptance | orchestrator | 2026-07-11T06:55:31Z: PCluster list excludes `jul8itelx4`; CloudFormation returns `Stack ... does not exist`; no non-terminated cluster-tagged EC2 instances; headnode `i-02946c880916d6dbc` is `terminated`; FSx returns `FileSystemNotFound`; DRA query returns `[]`; SSM query returns `[]`; ParallelCluster artifact prefix has `KeyCount: 0` |  | Terminal absence verified. The retained 3-day CloudWatch log group `/aws/parallelcluster/jul8itelx4-202607081149` remains by stack policy. |

## Final Report

All rows terminal: yes
Objective complete: yes

Status counts:

- SUCCESS: 5

Changed files:

- `docs/plans/20260711T063617Z_jul8itelx4_delete_ledger.md`

Validation:

- Live PCluster, EC2, FSx, DRA, CloudFormation, SSM, Slurm, controller-process, and filesystem-usage inspection completed.
- DYEC deletion dry-run exited 0 and changed no AWS resources.
- The processed stack template sets `DeletionPolicy: Delete` on `fs-021b9667d227d3f65`.

Non-success terminal rows: none.

Residual state:

- The approved deletion permanently destroyed scratch FSx `fs-021b9667d227d3f65` and its approximately 638 GB of mounted contents without export.
- All four DRAs are gone with the filesystem. Their source sequencing/reference S3 repositories were not deletion targets; no source-data S3 delete command was run.
- The ParallelCluster-owned artifact prefix was cleaned and is empty.
- CloudWatch log group `/aws/parallelcluster/jul8itelx4-202607081149` is intentionally retained for 3 days and currently reports 82,997,864 stored bytes.

Current boundary: cluster deletion and terminal verification are complete.
