# Stale us-west-2c Baseline Network Stack Ledger

Date: 2026-07-08

## Control Ledger

Controlling plan: user approved deletion of stale `pcluster-vpc-stack-2c` and a DYEC code fix.
Ledger path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260708T112418Z_stale_usw2c_network_stack_ledger.md`

Gate 0 baseline:
- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch: `jem-dev`
- Repo state: `git status --short --branch` -> `## jem-dev...origin/jem-dev`; pre-existing untracked `docs/plans/20260708T104737Z_remove_jemdev10_refs_ledger.md`
- Live failure: `dyec create --region-az us-west-2c --profile lsmc --cluster-type rhel` selected `pub=subnet-014e2aeb1c01eca30 priv=subnet-0ebd1948b31c82ac1`, then failed resolving the private subnet VPC.
- Live evidence: `aws --profile lsmc ec2 describe-subnets --region us-west-2 --subnet-ids subnet-014e2aeb1c01eca30 subnet-0ebd1948b31c82ac1` -> `InvalidSubnetID.NotFound`.
- Stack evidence: `aws --profile lsmc cloudformation describe-stacks --region us-west-2 --stack-name pcluster-vpc-stack-2c` -> `CREATE_COMPLETE` with stale subnet/VPC outputs.
- Drift evidence: `aws --profile lsmc cloudformation describe-stack-drift-detection-status --region us-west-2 --stack-drift-detection-id 2a1d3c50-7abe-11f1-a8de-06f537c629f7` -> `StackDriftStatus=DRIFTED`, `DriftedStackResourceCount=8`.
- Safety boundary: user explicitly approved deleting the drifted `pcluster-vpc-stack-2c` stack after being told this is destructive. Do not delete, stop, or mutate any ParallelCluster cluster or Slurm resource.

## Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| NET-001 | AWS live network | Delete stale `pcluster-vpc-stack-2c` so the next `us-west-2c` create can rebuild the baseline network stack. | SUCCESS | legitimate_safety_handling | Gate 2: Config And Startup Behavior | Codex | `aws --profile lsmc cloudformation delete-stack --region us-west-2 --stack-name pcluster-vpc-stack-2c && aws --profile lsmc cloudformation wait stack-delete-complete --region us-west-2 --stack-name pcluster-vpc-stack-2c` completed; follow-up `describe-stacks` returns `ValidationError: Stack with id pcluster-vpc-stack-2c does not exist`; `pcluster-vpc-stack-2d` remains `CREATE_COMPLETE`. |  | Stale `us-west-2c` baseline stack deleted; no cluster or Slurm resources modified. |
| CODE-001 | DYEC create validation | Make DYEC validate complete baseline stack outputs against live EC2 and fail hard with a clear stale/drifted stack message instead of selecting dead subnet IDs. | SUCCESS | feature_implementation | Gate 2: Config And Startup Behavior | Codex | Added `validate_stack_outputs()` and `_validated_stack_outputs()` in `daylily_ec/aws/cloudformation.py`; complete and newly created baseline stacks now validate VPC, public subnet, private subnet, VPC ownership, AZ, and subnet state before outputs are returned. |  | DYEC now fails hard with `Baseline CFN stack <name> is stale or drifted...` before create-time subnet selection can reuse dead output IDs. |
| TEST-001 | DYEC tests | Add focused regression tests for stale complete baseline outputs and successful complete baseline output validation. | SUCCESS | contract_test | Gate 5: Final Acceptance | Codex | Added `test_complete_stack_with_deleted_subnet_outputs_fails_clear` in `tests/test_cloudformation.py`; updated existing complete-stack tests to model live EC2 output validation. `pytest tests/test_cloudformation.py tests/test_workflow.py tests/test_ec2.py tests/test_aws_validation.py -q` -> 202 passed. `ruff check daylily_ec/aws/cloudformation.py tests/test_cloudformation.py` -> all checks passed. |  | Regression coverage added and focused validation checks passed. |

## Final Status

- Terminal rows: 3/3
- `SUCCESS`: NET-001, CODE-001, TEST-001
- `OPEN`: 0
- `IN_PROGRESS`: 0
- `ATTEMPTING_BUGFIX`: 0
- `BLOCKED`: 0
- `FAIL`: 0

Objective state: complete. The stale `us-west-2c` baseline stack was deleted, and DYEC now detects stale/drifted complete baseline stack outputs before returning them for cluster creation.
