# Slurm accounting default-off and follow-on attach ledger

Created: 2026-07-14T17:56:21Z

Release target: `10.3.7`

## Objective

Keep AWS ParallelCluster creation independent of Slurm accounting by default,
then provide an explicit post-create command that attaches a compatible,
existing regional accounting service to a healthy cluster through a supported
`pcluster update-cluster` operation.

## Gate 0 baseline

- Checkout: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster-sentieon-single`
- Branch: `sentieon-single`
- Starting commit: `1208a0aa`
- The default configuration currently sets `slurm_accounting_enabled=true`.
- `dyec create` currently resolves accounting before cluster submission and
  therefore aborts when the selected cluster VPC differs from the regional
  accounting stack VPC.
- The observed `us-west-2d` failure occurred before ParallelCluster creation:
  canonical stack `dayec-slurm-accounting-us-west-2c` is in
  `vpc-0f41176d568ae7b1e`; the selected cluster subnet is in
  `vpc-06b01782f2abece1c`.
- AWS ParallelCluster 3.15 supports changing
  `Scheduling.SlurmSettings.Database` with `pcluster update-cluster`, but the
  compute fleet must already be stopped. Head-node
  `AdditionalSecurityGroups` is updateable.
- No live AWS mutation is authorized or performed by this implementation
  ledger. In particular, no cluster, compute fleet, Slurm daemon, accounting
  database, or stack is changed.
- Unrelated modified and untracked workspace files are preserved and will not
  be staged.

## Execution ledger

| ID | Scope | Requirement | State | Evidence / notes |
|---|---|---|---|---|
| SACCT-FOLLOW-001 | Create defaults | Default `slurm_accounting_enabled` to false in source and packaged configuration. | SUCCESS | Both source and packaged templates use `false`; template loading regression updated. |
| SACCT-FOLLOW-002 | Create workflow | Confirm a default create renders no `SlurmSettings.Database` and does not resolve an accounting service. | SUCCESS | Initial accounting CLI options and resolution code removed; true accounting config fails before baseline-stack or cluster mutation; render substitutions are empty. |
| SACCT-FOLLOW-003 | Follow-on attach | Add an explicit command that requires a `CREATE_COMPLETE` cluster, a stopped compute fleet, a compatible existing accounting service, and a successful update dry-run before the real update. | SUCCESS | `dyec slurm-accounting attach`; `daylily_ec/workflow/attach_slurm_accounting.py`; update runner coverage. |
| SACCT-FOLLOW-004 | Safety | Do not stop compute capacity, force an update, create a second accounting stack, or expose database credentials. | SUCCESS | Attach requires pre-stopped fleet, uses `create_if_missing=False`, never passes force-update, writes separate YAML; endpoint and secret values removed from ensure JSON/text and duplicate-service warnings. |
| SACCT-FOLLOW-005 | Regression | Cover default-off behavior, update-config rendering, compatibility failures, command registration, and dry-run-before-update ordering. | SUCCESS | Focused accounting/CLI suite: `188 passed`; workflow/CLI/render/runner suite: `354 passed`. |
| SACCT-FOLLOW-006 | Documentation | Replace default-on guidance with default-off creation and explicit attach instructions. | SUCCESS | `README.md`; `docs/cli_reference.md`. |
| SACCT-FOLLOW-007 | Verification | Run focused tests, formatting/static checks, then the repository test suite in the activated DYEC environment. | SUCCESS | Ruff passed; new files Black-clean; mypy passed for attach/runner; full suite `1515 passed, 11 skipped, 1 warning` in 63.58s. |
| SACCT-FOLLOW-008 | Live proof/release | Keep live attach/create and release mutations separate until code verification and explicit operator direction. | PENDING | Gate 5 |

## Supported operational sequence

1. `dyec create` omits Slurm accounting by default.
2. The cluster reaches `CREATE_COMPLETE` and remains usable without `sacct`
   persistence.
3. The operator ensures the compute fleet is `STOPPED` using the supported
   ParallelCluster command after confirming no workload must remain running.
4. `dyec slurm-accounting attach` finds a same-VPC existing accounting service,
   writes a separate update configuration, runs `pcluster update-cluster
   --dryrun true`, and only then submits the real update.
5. A missing or incompatible accounting service fails the attach command while
   leaving the already-created cluster intact.

## Verification notes

- Installed `pcluster 3.15.0` help confirms `update-cluster` supports `-n`,
  `-c`, and `--dryrun`, and `describe-compute-fleet` supports cluster/region
  selection.
- The installed ParallelCluster source uses the same exact successful dry-run
  response already enforced by DYEC:
  `Request would have succeeded, but DryRun flag is set.`
- `dyec create --help` contains no Slurm-accounting option.
- `dyec slurm-accounting attach --help` exposes the post-create operation and
  its non-mutating `--dry-run` mode.
- No live AWS, ParallelCluster, compute-fleet, Slurm, or database operation has
  occurred as part of Gates 0-4.
