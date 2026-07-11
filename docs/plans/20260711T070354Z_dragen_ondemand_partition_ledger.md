# DRAGEN On-Demand Partition Ledger

Created: `2026-07-11T07:03:54Z`

Objective: preserve the existing Spot-backed `dragen` partition and add an
explicit, separately selected `dragen-ondemand` partition backed by one
on-demand `f2.6xlarge`. No automatic fallback from Spot to on-demand is
permitted.

## Gate 0

| Surface | Evidence |
|---|---|
| Repository | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster-dragain12-merge` |
| Branch | `codex/dragain12-checkpoint-jem-dev`, clean before work and merged with `origin/jem-dev` at `7da5d338`. |
| Current topology | Canonical `dragen` and active RHEL templates expose only the Spot-backed `dragen` f2 queue. |
| Current live blocker | `dragain12` native BCL conversion job `28` reached workflow validation but EC2 rejected two Spot launches with `UnfulfillableCapacity`; no f2 instance or native DRAGEN runtime started. |
| On-demand price | AWS Price List SKU `9ZB96DY4PFEHEQPE`, effective `2026-07-01T00:00:00Z`, lists Linux shared-tenancy `f2.6xlarge` in US West (Oregon) at `$1.98` per instance-hour. This excludes headnode, FSx, EBS, transfer, and other cluster costs. |
| Safety boundary | Gate 0 initially allowed additive configuration and tests only. The user subsequently explicitly requested the live `dragain12` ParallelCluster update. No job manipulation, budget increase, deletion, forced update, or automatic Spot-to-on-demand routing was authorized or performed. |

## Control Ledger

| ID | Requirement | Status | Evidence / Next Gate |
|---|---|---|---|
| TEMPLATE-001 | Add explicit `dragen-ondemand` to canonical DRAGEN and active RHEL templates. | SUCCESS | Canonical `dragen`, all four supported RHEL AZ templates, and four legacy DRAGEN templates now preserve `dragen` as Spot and add explicit `dragen-ondemand` with the qualified DRAGEN AMI/bootstrap, `/scratch`, one `f2.6xlarge`, `MinCount: 0`, and `MaxCount: 1`. The canonical queue also attaches the private license policy and passes the secret ARN to the bootstrap without exposing its value. |
| PRICING-001 | Keep Spot-price resolution limited to Spot queues. | SUCCESS | Spot-price processing now filters on explicit `CapacityType: SPOT`. Regression proof confirms the on-demand resource receives no `SpotPrice`, performs no Spot lookup, and is absent from Spot resource/partition summaries. |
| CONTRACT-001 | Extend canonical DRAGEN topology validation for both f2 queues. | SUCCESS | Validator requires queue order `dragen`, `dragen-ondemand`, `i192`, `i192nvme`; validates capacity types, AMI, DRAGEN bootstrap role, license policy, resource names, f2 type, `249036` MiB schedulable memory, disabled EFA, and count limits; rejects `SpotPrice` on the on-demand resource. |
| PACKAGE-001 | Keep source and packaged templates identical. | SUCCESS | Canonical DRAGEN and all RHEL source templates match packaged payloads byte-for-byte; structured YAML tests validate both f2 partitions in every supported template. |
| TEST-001 | Run focused tests and a rendered ParallelCluster dry-run. | SUCCESS | Focused tests: `29 passed`; renderer/workflow set: `179 passed`; full suite: `1381 passed, 11 skipped`; Ruff and `git diff --check` passed. ParallelCluster `3.15.0` create dry-run against the qualified `dragain12` topology reported `Request would have succeeded, but DryRun flag is set.` with no error-level validation messages. |
| LIVE-001 | Add the partition to running cluster `dragain12` without unrelated changes. | SUCCESS | `pcluster describe-cluster` exposed the authoritative versioned config URL. The retrieved object was byte-identical to the prior local config (SHA-256 `68c0a79d...bfb59`); an unchanged update dry-run reproduced the same duplicate-S3-access normalization rows, proving they were not introduced by the new queue. Saved candidate `/Users/jmajor/.config/daylily/dragain12_cluster_ondemand_20260711T071618Z.yaml` (SHA-256 `31a90c5b...508b`) was structurally asserted to differ only by `dragen-ondemand`. Non-forced `pcluster update-cluster` completed at `UPDATE_COMPLETE`; compute fleet remained `RUNNING`. Persisted config contains Spot `dragen` plus on-demand `dragen-ondemand`, and no on-demand resource has `SpotPrice`. Headnode Slurm reports `dragen-ondemand` `UP`, one `idle~` node, `24` CPUs, and `249036M`. AWS reported no pending/running compute instances, so adding the partition incurred no f2 runtime charge. |

## Cost Notes

- One continuously running on-demand f2 node: `$1.98/hour`, `$47.52/day`, or
  `$1,425.60` per 30-day month, excluding all non-compute cluster costs.
- Billing for a runtime of `82` minutes would be approximately `$2.706` for the
  f2 instance alone.
- Users must request `--partition=dragen-ondemand` explicitly. Existing rules
  that request `dragen` remain Spot-only.
