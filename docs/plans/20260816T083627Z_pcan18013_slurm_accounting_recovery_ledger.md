# pcan-18013 Slurm accounting recovery and DYEC create hardening ledger

Created: `2026-08-16T08:36:27Z`

Controlling request: diagnose the apparent successful creation of `pcan-18013`, repair
Slurm accounting on that cluster if needed, and correct `dyec create` so its accounting
contract is installed and reported accurately.

Ledger path: `docs/plans/20260816T083627Z_pcan18013_slurm_accounting_recovery_ledger.md`

## Gate 0 inventory and baseline

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch: `codex/active-dyec-18.0.12`
- Starting `HEAD`: `e77a7ec1a5b92c1fd7a3aed541ee1576a1cfb92b` (`18.0.13`)
- Initial status: only pre-existing untracked user artifacts under `TrusSV/`,
  `docs/plans/20260816T080528Z_*`, `docs/plans/20260816T080536Z_*`,
  `docs/plans/20260816T080946Z_*`, and `tmp/dayoa-ont-headnode-proof/`; these are
  preserved and outside this ledger's write scope.
- User transcript receipt:
  `/Users/jmajor/.config/daylily/slurm_accounting_pcan-18013_20260816065102_receipt.json`
  records `error_stage=update_wait`, `terminal_cluster_state=UPDATE_FAILED`,
  `terminal_fleet_state=STOPPED`, `fleet_restored=false`, and
  `recovery_required=true`.
- Live `pcluster describe-cluster`: cluster `UPDATE_FAILED`, CloudFormation
  `UPDATE_ROLLBACK_COMPLETE`, head node `i-0ab6afb983a662ebc` running, compute fleet
  `STOPPED`.
- Live CloudFormation failure: `HeadNodeWaitCondition20260816073244` received
  `Update failed` from the head node.
- Live head-node Chef log root cause: the ParallelCluster accounting update attempted
  to retrieve the owning accounting password secret, but the exact head-node IAM role
  had no identity policy granting `secretsmanager:GetSecretValue`; the update failed
  and its rollback also failed to restore a supported accounting plugin.
- Accounting service stack `dayec-slurm-accounting-us-west-2c` is
  `UPDATE_COMPLETE`; the service existed before this create attempt.
- Baseline focused tests will be recorded before product edits.
- Safety boundary: the user approved only the supported stopped-fleet cluster update,
  the resulting declared Slurm bootstrap/restart, fleet start after `UPDATE_COMPLETE`,
  read-only accounting proof, and deletion of the named unexecuted unsafe change set.
  No job manipulation or other resource deletion was authorized or performed.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| SACCT-001 | Live diagnosis | Establish exact cluster, fleet, stack, and head-node failure state. | SUCCESS | legitimate_safety_handling | Gate 0 | Forge | Receipt, live `pcluster` descriptions, stack events, and bounded CloudWatch Chef logs summarized above. | Head-node role lacked access to the accounting password secret. | Diagnosis is evidence-backed; this was a failed post-create update, not a successful usable accounting-enabled cluster. |
| SACCT-002 | Source contract | Make the accounting stack own and output a least-privilege client secret-read managed policy, require it during discovery, and attach it only to the rendered head-node IAM configuration. | SUCCESS | feature_implementation | Gate 1 | Forge | Both direct and PrivateLink templates export `AccountingClientSecretReadPolicyArn`; resolvers require it; render tests prove head-node-only attachment. | Existing stack contract exported the secret and client security group but no client IAM policy. | Forward-only contract: a stack missing the required output fails hard; no inferred policy or migration shim exists. |
| SACCT-003 | CLI result contract | Make default `dyec create` return failure and avoid a success banner whenever requested accounting is not enabled; retain explicit opt-out only through `--slurm-accounting off`. | SUCCESS | feature_implementation | Gate 1 | Forge | Create workflow and CLI tests prove non-enabled requested accounting emits the failure panel, suppresses `...fin!`, and returns `EXIT_AWS_FAILURE`; removed `--fail-on-sacct-error`. | Previous default fail-soft behavior returned exit 0 and titled the final panel `CLUSTER CREATION COMPLETE` even for `RECOVERY REQUIRED`. | Accounting-on is now strict. The only opt-out is `--slurm-accounting off`. |
| SACCT-004 | Local verification | Run focused accounting/create tests, lint/format checks, and diff checks. | SUCCESS | contract_test | Gate 2 | Forge | Full suite: `2620 passed, 11 skipped`; focused suites passed; both CloudFormation templates validated; `git diff --check` passed. |  | Repository-wide Ruff/Black checks expose pre-existing baseline findings in untouched code, so no unrelated mass formatting was performed. |
| SACCT-005 | Live accounting-stack contract | Update the existing accounting singleton to add the exact client secret-read policy/output without replacing the retained DB, secret, instance, or networking resources. | SUCCESS | active_product_contract | Gate 3 | Forge | Safe change set `dyec-client-secret-policy-safe-20260816T090100Z` contained one IAM managed-policy add and reached `UPDATE_COMPLETE`; DB instance `i-088957ddbc7fcf3d1` and private IP `10.0.1.237` were preserved. | The first change set also included an unintended DB replacement because its template resolved a newer AMI. | The unsafe unexecuted change set `dyec-client-secret-policy-20260816T085649Z` is confirmed deleted. No database, secret, instance, stack, or cluster was deleted. |
| SACCT-006 | Live cluster repair | Retry a supported stopped-fleet ParallelCluster update using the corrected config, allow its declared Slurm bootstrap/restart, reach a stable update state, then start the fleet and prove `slurmdbd`, `slurmctld`, registered cluster, and `sacct`. | SUCCESS | active_product_contract | Gate 3 | Forge | Approved `dyec --json slurm-accounting attach` returned `update_submitted=true`; cluster and stack reached `UPDATE_COMPLETE` with fleet stopped; approved fleet request reached `RUNNING`; central SSM helper returned code 0 as `ubuntu` with both daemons active, exact storage type and registration, and bounded `sacct=success`. | Head-node role lacked access to the accounting password secret. | No jobs were inspected, submitted, cancelled, requeued, held, released, or otherwise manipulated. |
| SACCT-007 | Final acceptance | Record terminal row counts, exact live proof, and residual risks; objective is complete only if all source and live rows succeed. | SUCCESS | contract_test | Gate 4 | Forge | All seven rows are terminal `SUCCESS`; annotated DYEC tag `18.0.14` points to release commit `ef7c78dcf181d2a8231798788dd0fa38bca30b72` and is pushed with branch `codex/dyec-18014-slurm-accounting`. |  | The live cluster is healthy and the released current interface is forward-only. Existing stacks missing the newly required output fail hard and must be explicitly updated; there is no compatibility shim. |

## Acceptance contract

1. A new accounting stack exports a dedicated head-node client policy ARN whose only
   secret access is the owning password secret.
2. The post-create update config contains that policy under
   `HeadNode.Iam.AdditionalIamPolicies` and never places it on compute queues.
3. An existing stack missing that required output fails before any compute-fleet
   mutation; there is no compatibility shim or guessed IAM policy.
4. Default accounting-on creation does not print a success banner or return zero unless
   accounting reaches `ENABLED`.
5. Live repair is accepted only from stable ParallelCluster state plus active
   `slurmdbd`/`slurmctld`, `AccountingStorageType=accounting_storage/slurmdbd`, exact
   cluster registration, and successful bounded `sacct` as `ubuntu`.

## Final acceptance

- Terminal rows: `7 SUCCESS`, `0 BLOCKED`, `0 OPEN`, `0 IN_PROGRESS`.
- Live cluster: `pcan-18013` is `UPDATE_COMPLETE`; compute fleet is `RUNNING`.
- Read-only head-node proof as `ubuntu`: `slurmdbd=active`, `slurmctld=active`,
  `AccountingStorageType=accounting_storage/slurmdbd`, `ClusterName=pcan-18013`,
  registered cluster `pcan-18013`, and bounded `sacct` exit code `0`.
- Destructive boundary: only the explicitly approved unexecuted change set
  `dyec-client-secret-policy-20260816T085649Z` was deleted. No database, secret,
  instance, stack, job, or cluster was deleted, and no job was manipulated.
- Release: annotated `18.0.14` at
  `ef7c78dcf181d2a8231798788dd0fa38bca30b72`.
