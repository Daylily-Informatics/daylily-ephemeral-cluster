# Cluster-create job-submit boot-order ledger

- Started: 2026-07-14T15:40:11Z
- Repository: `daylily-ephemeral-cluster-sentieon-single`
- Branch: `sentieon-single`
- Failed cluster: `ifx-20260719g`, `us-west-2`, account `108782052779`
- Objective: remove the boot-order race that lets `dyec create` pass dry-run and then fail while starting Slurm accounting.

## Gate 0 evidence

- The create transcript resolved `dayec-slurm-accounting-us-west-2c` successfully at `10.0.1.237:3306`; accounting-service selection was not the failure.
- ParallelCluster reported `HeadNodeBootstrapFailure` and CloudFormation reported `bootstrap_slurm_accounting` failure after waiting 30 times for cluster registration.
- The retained CloudWatch `slurmctld` stream shows the causal failure at `2026-07-14T15:30:04Z`: `job_submit/lua: Unable to stat /opt/slurm/etc/job_submit.lua`, followed by `fatal: failed to initialize job_submit plugin`.
- The rendered config enables `JobSubmitPlugins: lua`, but installs `job_submit.lua` only from the head-node `OnNodeConfigured` script. ParallelCluster starts `slurmctld` before `OnNodeConfigured`, so the configured plugin file cannot exist in time.
- The missing controller prevents registration with `slurmdbd`; the later `sacctmgr` timeout is a consequence, not the root cause.
- Rollback is independently stuck at `ROLLBACK_FAILED` because the references DRA had an active data-repository task during deletion. No cleanup is authorized by this ledger.

## Fix contract

1. Every active Slurm cluster template that enables `JobSubmitPlugins: lua` must install the immutable-release `job_submit.lua` in the head-node `OnNodeStart` phase.
2. `OnNodeStart` must call the existing fail-hard `install_slurm_job_submit_policy.sh` with the rendered region and immutable boot-config release URI.
3. The CPU-only Slurm validator must reject rendered configs that enable the plugin without that exact pre-bootstrap action, so `dyec create` fails before AWS mutation rather than discovering the error on the head node.
4. Existing concurrent partition/template work must be preserved.

## Execution ledger

| ID | Work | State | Evidence |
|---|---|---|---|
| CBO-001 | Capture live root-cause evidence | SUCCESS | ParallelCluster describe, CloudFormation failure events, CloudWatch `chef-client`, `slurmctld`, and `slurmdbd` streams |
| CBO-002 | Add pre-bootstrap installer to active templates | SUCCESS | Every non-archived source and packaged Slurm template that enables `JobSubmitPlugins: lua` now defines the exact head-node `OnNodeStart` installer. The Intel and Sentieon-template portion entered through concurrent commit `051a276d`; DRAGEN/RHEL portions entered through `f89c92a3`. |
| CBO-003 | Add fail-fast rendered-config validation | SUCCESS | `validate_cpu_only_slurm_contract` rejects missing or malformed pre-bootstrap installer actions before the `pcluster` dry-run/create boundary; terminal monitor output now preserves structured ParallelCluster failure details. |
| CBO-004 | Add regression tests and validate | SUCCESS | `407 passed`; focused Ruff and `git diff --check` passed; installer scripts passed `bash -n`. |
| CBO-005 | Live create proof | PENDING | Requires a new create attempt; not performed implicitly |

## Safety boundary

- Read-only AWS inspection is permitted.
- Do not delete or continue rollback of `ifx-20260719g` without the required separate destructive approval.
- Do not create a replacement cluster without explicit user direction after the local fix is validated.

## Current boundary

- Root cause: proved.
- Local implementation and regression validation: complete.
- Publication state: Intel/Sentieon template boot action entered the branch through concurrent commit `051a276d`; validator, diagnostic output, remaining active templates, tests, and this ledger are committed together by the subsequent `Harden Slurm accounting cluster creation` commit.
- Live proof: incomplete. The failed cluster is still `CREATE_FAILED` / `ROLLBACK_FAILED`, and no replacement cluster was launched.
