# DRAGEN RHEL Default AMI And dragain2 Delete Ledger

Controlling request: set `ami-09fd9c3c129952e5f` as the default AMI for RHEL cluster types, and delete the currently running DRAGEN cluster.

Ledger path: `docs/plans/20260708T165351Z_dragen_rhel_default_ami_delete_ledger.md`

## Gate 0 Baseline

- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch/state before this task: `jem-dev...origin/jem-dev`; pre-existing dirty files included command catalog, cost center, stage-samples, test-runner, and related tests/docs. Those files are outside this task's edit scope.
- Instruction files read: `/Users/jmajor/.agents/AGENTS.md`, `/Users/jmajor/.codex/AGENTS.md`, `/Users/jmajor/projects/lsmc/AGENTS.md`, `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/AGENTS.md`, `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`.
- AMI target: `ami-09fd9c3c129952e5f`, name `dragen-pcluster-rhel8-4.5.4-license-pending-20260703T102010Z`, source PCluster base `ami-067b5dca4fed8d19c`, source native DRAGEN AMI `ami-044bef021cb86a54c`.
- Config sweep: RHEL/DRAGEN templates use `${REGSUB_DRAGEN_PCLUSTER_AMI}`. `config/daylily_ephemeral_cluster_template.yaml` and packaged payload had empty `dragen_pcluster_ami` defaults before this task. `config/daylily_ephemeral_cluster_dragen_pcluster_image_rhel8_2c.yaml` explicitly set that AMI to empty before this task.
- Live `dragain2` state before deletion request: PCluster `clusterStatus=UPDATE_COMPLETE`, `computeFleetStatus=RUNNING`, headnode `i-04e36334d60163577` running at `44.232.45.50`, active PCluster instance list contains only the headnode.
- Queue state before deletion request: `dyec headnode jobs --profile lsmc --region us-west-2 --cluster dragain2` returned only the header row, no jobs.
- Destructive boundary: deleting `dragain2` is a live destructive AWS operation. It is not approved by the initial request alone. No delete command may run until the exact target/effect is restated and the user gives a second explicit confirmation.

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| AMI-DEFAULT-001 | DYEC config | Make `ami-09fd9c3c129952e5f` the default DRAGEN PCluster AMI for RHEL cluster-type request paths. | SUCCESS | config_or_startup_contract | Gate 2 | Codex | Added `DEFAULT_DRAGEN_PCLUSTER_AMI` in `daylily_ec/config/models.py`; `ensure_required_keys` now gives missing `dragen_pcluster_ami` that default; source and packaged `config/daylily_ephemeral_cluster_template.yaml` default to the AMI; `config/daylily_ephemeral_cluster_dragen_pcluster_image_rhel8_2c.yaml` now sets the AMI explicitly. Focused tests: `pytest tests/test_triplets.py tests/test_cluster_request_config.py tests/test_renderer.py tests/test_packaged_defaults.py -q` -> `94 passed`. Render check: default `--cluster-type rhel` for `us-west-2c` selected `config/day_cluster/rhel/us-west-2/us-west-2c/prod_cluster_rhel_us-west-2c.yaml` and rendered `CustomAmi=ami-09fd9c3c129952e5f`. |  | Default RHEL DRAGEN PCluster AMI is set and verified locally. |
| DELETE-DRAGAIN2-001 | AWS live cluster | Delete currently running DRAGEN cluster `dragain2` in `us-west-2`. | SUCCESS | live_destructive_action | Destructive Approval | Codex | User gave second explicit approval after target/effect restatement. Ran `dyec delete --cluster-name dragain2 --region us-west-2 --profile lsmc --yes`; DYEC reported `Cluster deleted`. Independent verification: CloudFormation `dragain2` -> `Stack with id dragain2 does not exist`; active EC2 instances tagged `parallelcluster:cluster-name=dragain2` -> `[]`; FSx `fs-0dd6eea983d15f6d8` -> `FileSystemNotFound`; DRA `dra-0f486024f022b8fe6` and `dra-0f97d3f9a70d7bfc1` -> `[]`. |  | `dragain2`, its headnode, cluster-managed FSx, ILMN run-mount DRA, and reference DRA were deleted. |

## Delete Confirmation Text

Before live deletion, restate:

Deleting `dragain2` in `us-west-2` will delete the ParallelCluster CloudFormation stack, terminate the running headnode `i-04e36334d60163577`, keep no active compute nodes because none are running now, and delete the cluster-managed FSx Lustre filesystem `fs-0dd6eea983d15f6d8` because the rendered config uses `DeletionPolicy: Delete`. This will remove FSx contents and the DRA `dra-0f97d3f9a70d7bfc1`; it will not delete source objects in S3 reference or sequencing buckets.

## Final State

- All rows are terminal.
- Objective complete: RHEL DRAGEN PCluster AMI default is set to `ami-09fd9c3c129952e5f`; approved `dragain2` deletion is complete.
- Tests: `pytest tests/test_triplets.py tests/test_cluster_request_config.py tests/test_renderer.py tests/test_packaged_defaults.py -q` -> `94 passed`.
- Live verification after delete: stack absent, active instances absent, FSx absent, DRA associations absent.
