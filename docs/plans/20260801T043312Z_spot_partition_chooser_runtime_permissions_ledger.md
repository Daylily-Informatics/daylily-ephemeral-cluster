# Spot partition chooser runtime permissions ledger

Controlling request: support the DayOA attempt-aware Spot partition chooser with the minimum read-only EC2 permissions on DYEC-managed headnodes, without configuring Slurm partition priority.

## Gate 0 baseline

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- HEAD: detached at `6b14f78dacdaa3733682b9dbc557170ac037c3b1`
- Pre-existing worktree state: many untracked operator ledgers, artifacts, reports, and scratch paths; preserve all unchanged.
- Active IAM templates already grant `ec2:DescribeInstanceTypes`, `ec2:DescribeInstanceTypeOfferings`, and `ec2:DescribeSpotPriceHistory`.
- They do not grant `ec2:GetSpotPlacementScores` or `ec2:DescribeAvailabilityZones`, which the attempt-1 availability decision requires.
- No tracked ParallelCluster template sets Slurm `PriorityTier`, `PriorityJobFactor`, partition QOS/preemption, or a partition-priority weight. `DynamicNodePriority`, where present, is a node weight and is outside this change.

## Control ledger

| ID | Requirement | Status | Evidence | Terminal note |
|---|---|---|---|---|
| IAM-001 | Add only the two read-only EC2 actions required for AZ mapping and placement scores to active and packaged runtime IAM templates | SUCCESS | Source and packaged `pcluster_env.yml`, `.expanded`, `.new`, and `ap-south-1-stack.yml` templates add `ec2:DescribeAvailabilityZones` and `ec2:GetSpotPlacementScores`. | Existing price and instance-description actions were preserved. No write action was added. |
| IAM-002 | Add static guardrail coverage for the runtime action set | SUCCESS | `tests/test_packaged_defaults.py` requires both new actions in every active and packaged runtime policy template. | Packaged-source equality coverage passed. |
| IAM-003 | Confirm no Slurm priority or scheduler setting changed | SUCCESS | Changed-file diff search for `PriorityTier`, `PriorityJobFactor`, `PriorityWeightPartition`, `QOS`, `Preempt`, and `DynamicNodePriority` returned no matches. | IAM and preflight capability only; no ParallelCluster queue or Slurm policy was changed. |
| IAM-004 | Run targeted template and validation tests | SUCCESS | Supported `DAY-EC` environment: `101 passed` across `tests/test_packaged_defaults.py`, `tests/test_cloudformation.py`, and `tests/test_aws_validation.py`; `git diff --check` passed. | No live IAM or CloudFormation operation was run. |

## Deployment boundary

This ledger covers source changes only. Existing deployed IAM policies and clusters are not modified in this work. A later, explicitly controlled DYEC release and stack update is required before an existing headnode can call the new read-only API actions.

## Final report

- All control rows are terminal: yes.
- Source permission objective complete: yes.
- Slurm or ParallelCluster priority changed: no.
- Live/deployed status: not deployed. The existing `pclusterTagsAndBudget` managed policy and all running clusters remain unchanged.
- Repository state: changes remain uncommitted at the pre-existing detached HEAD with unrelated untracked operator artifacts preserved.
