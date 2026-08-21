# DYEC CLI Reference

This document is the operator-facing reference for the `19.0.6` `dyec` command surface. It favors explicit commands and receipts over implicit state. Operators and upstream services use the installed literal `dyec` console script.

## Conventions

Examples assume:

```bash
cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate

export AWS_PROFILE=lsmc
export REGION=us-west-2
export REGION_AZ=us-west-2d
export CLUSTER=ifx-p2-1000-120-0715
export PROJECT=RnD
export ANALYSIS_ID=<analysis-id>
export ANALYSIS_ROOT=/fsx/analysis_results/$CLUSTER/$ANALYSIS_ID
export STAGING_S3_URI=s3://<bucket>/<dyec-temporary-relay-prefix>/
```

General rules:

- Prefer `--json` for automation and agent use.
- Prefer `--cluster` for DYEC commands.
- Use exact DayOA tags. Do not rely on `day-clone` defaults for new analysis work.
- Use `dyec catalog render` before `dyec catalog launch` when the launch will cost time or money.
- Use `dyec workflow launch` only with an exact `--dy-command` and exact input paths.
- Use `dyec analysis visit` before reading an FSx analysis root, and use write locks/guards before protected writes.
- Do not invoke raw `snakemake` for DayOA work.
- Headnode-facing CLI commands default to `--remote-user auto`: Ubuntu/Intel DayOA headnodes resolve to `ubuntu`; DRAGEN/RHEL-style headnodes resolve to `ec2-user`. Unknown platform metadata fails hard.
- DYEC-created headnode shells run as bash login/interactive contexts and source `~/.bashrc`; do not wrap workflow launches in a noninteractive `bash -lc` path.

## Project-local context

For repeated work from one checkout, DYEC can keep four invocation values in
the ignored file `$PWD/.dyec.config.yaml`:

```bash
dyec set-vars \
  --profile lsmc \
  --region us-west-2 \
  --region-az us-west-2d \
  --cluster-admin-email operator@example.org

dyec -v --json info
```

The file contains only `aws_profile`, `aws_region`, `aws_region_az`, and
`cluster_admin_email`. DYEC reads only the file in the current working
directory; it does not search parents and does not read or write `DYEC_*`
environment variables. YAML must be a mapping with only those string keys;
malformed YAML, unknown keys, and non-string values fail clearly. Blank and
whitespace-only values clear a key. Use `dyec unset-vars --region` to clear one
key, or `dyec unset-vars` to clear all keys and remove the file once it is
empty.

For every DYEC `--profile`, `--region`, and `--region-az` option, resolution is
explicit flag, then project-local context, then the command's existing behavior.
That means existing optional `AWS_PROFILE`, `AWS_REGION`, `AWS_DEFAULT_REGION`,
prompt, and command-default behavior remains in force when no local value is
present. A formerly required flag is accepted without an explicit argument only
when its matching local key is set; otherwise it produces the same missing-option
failure. DYEC never derives a region from an AZ or an AZ from a region.

`dyec --verbose` (or `dyec -v`) writes invocation diagnostics to stderr before
the subcommand: PWD, DYEC project/executable path, version, local-file status,
and all four values. It prints `unset` for missing or blank values, so JSON
stdout remains valid.

## Global command

```bash
dyec --help
dyec --json version
dyec -v --json info
dyec info
dyec runtime status
dyec resources-dir
dyec env
dyec agent guidance
```

Global options:

| Option | Use |
|---|---|
| `--json` | Emit machine-readable payloads when the command supports JSON. |
| `--dry-run` | Plan without persistent changes when supported by that command. |
| `--no-color` | Disable ANSI styling. |
| `--debug` | Print debug diagnostics. |
| `--version` | Print the installed DYEC version and exit. |
| `-v`, `--verbose` | Print project-local context diagnostics to stderr before the subcommand. |
| `--install-completion`, `--show-completion` | Shell completion setup. |

## Command-group index

The root help surface is intentionally broad. Use the following index before
opening nested help:

| Area | Commands |
|---|---|
| Local | `version`, `info`, `env`, `runtime`, `resources-dir`, `state`, `set-vars`, `unset-vars`, `agent guidance` |
| Lifecycle | `preflight`, `create`, `drift`, `cluster-info`, `delete` |
| Cluster/headnode | `cluster`, `headnode`, `slurm-accounting`, `cost-centers`, `pricing`, `aws` |
| Workflow/catalog | `workflow`, `repositories`, `catalog`, `samples`, `identities`, `tests` |
| FSx/analysis | `mounts`, `mount`, `export`, `exports`, `runtime-cache`, `analysis`, `command` |

`cluster list --verbose` is a command-specific table-detail flag. It is
different from root `dyec -v`, which reports local invocation context before
the subcommand.

## Agent guidance

`dyec agent guidance` prints a compact operational contract for agents and automated operators:

```bash
dyec agent guidance
```

It covers:

- local activation;
- SSM/headnode access;
- DayOA controller rules;
- same-analysis-root dry-to-live continuation;
- analysis-root visit/lock safety;
- headnode upload/download syntax;
- the DRA-only runtime-cache export boundary;
- monitoring commands and Slurm queue format.

Use this when an operator or agent needs a concise reminder of the safe path.
For the prominent task-by-task route map—including catalog versus manual DayOA
work, same-root continuation, and no-delete export—read
[agent_cli_guide.md](agent_cli_guide.md).

## Cluster lifecycle

Upstream services must execute the installed public `dyec` console script for
every cluster operation. They must not run `pcluster`, import DYEC Python
internals, or substitute a module entrypoint. `dyec create` owns pricing,
accounting-provider/bridge lifecycle, and initial cluster provisioning. The
recovery commands below only repair their explicitly documented states; they do
not reproduce create-time discovery or pricing. If an upstream service needs an
operation not exposed here, the missing interface must be added as a reviewed
public `dyec` CLI contract before that service can use it.

Render one exact current-schema request from an immutable source config, a
packaged template, and a protected override object:

```bash
dyec --json create-request render \
  --source-config <exact-source-config-resource> \
  --expected-source-config-sha256 <sha256> \
  --source-template \
    config/day_cluster/intel/us-west-2/us-west-2d/prod_cluster_intel_spot_us-west-2d.yaml \
  --expected-source-template-sha256 <sha256> \
  --overrides-json <absolute-protected-overrides.json> \
  --region-az "$REGION_AZ" \
  --output <absolute-protected-request.yaml>
```

The override input has schema `dyec.create_request_overrides.v1` and exactly
two top-level fields: `schema_version` and `values`. `values` must contain
exactly these 11 nonblank keys, with no aliases or optional extras:

- `cluster_name`
- `cost_center_name`, `cost_center_monthly_cap_usd`,
  `cost_center_allowed_users`
- `budget_amount`, `allowed_budget_users`, `budget_email`
- `dyec_deploy_key_policy_arn`, `dyec_deploy_key_secret_arn`,
  `dayoa_deploy_key_policy_arn`, `dayoa_deploy_key_secret_arn`

`budget_amount` must equal `cost_center_monthly_cap_usd`; the two allowed-user
fields must also match. Project budget identity is exactly `cluster_name`;
`budget_project` is retired and rejected. The protected rendered request is an
exact `dyec.create_request.v1` document: all 46 current config triplets use
`[USESETVALUE, "", <explicit value>]`, with only the four documented optional
empty fields allowed to be blank. The render success object contains status,
created/no-op, DYEC version, region/AZ, cluster name, request path/digest,
source config/template logical identities and digests, override file/canonical
digests and sorted key names, plus repository-credential key names and their
combined digest. It never returns the override values.

The override input and rendered request must have no group/other permission
bits (mode `0600`). A same-content existing render output is accepted only when
it is already protected; different content or broader permissions fail closed.
Relative source config/template identities always name packaged DYEC resources;
they never fall back to a same-named file in the current directory. An external
source config must be supplied by absolute path and exact digest.

Generate read-only live-pricing admission evidence:

```bash
dyec --json create-request prepare \
  --request-config <absolute-protected-request.yaml> \
  --expected-request-sha256 <sha256> \
  --source-template \
    config/day_cluster/intel/us-west-2/us-west-2d/prod_cluster_intel_spot_us-west-2d.yaml \
  --expected-source-template-sha256 <sha256> \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --spot-price-policy CALCULATE_MAX_SPOT_PRICE \
  --output-dir <absolute-protected-admission-directory>
```

`dyec.create_preparation.v1` binds the exact request/template/source/override
and repository-credential-reference digests, DYEC version, profile, resolved
account, region/AZ, cluster name, policy and pricing limits. Its
`pricing_source` contains the EC2 operation, capture time, observation window,
freshness/future-skew bounds, and provider observation timestamps. Artifact
entries expose only deterministic basenames, sizes, and SHA-256 values. The
receipt never returns raw overrides, credentials, emails, or S3 paths. A stale,
future, missing, nonpositive, or malformed provider observation fails closed.
The admission directory must be protected with mode `0700`; its files are
written with mode `0600`.

Saved templates must contain exactly `SpotPrice: CALCULATE_MAX_SPOT_PRICE` for
every Spot compute resource and no `SpotPrice` on On-Demand resources. Prepared
numeric YAML is admission evidence only; it is neither the saved template nor
the creation input.

Create with the reviewed admission receipt:

```bash
dyec create --json \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --cluster-type intel \
  --non-interactive \
  --slurm-accounting on \
  --config <absolute-protected-request.yaml> \
  --output-dir <absolute-empty-owned-0700-create-directory> \
  --preparation-receipt \
    <absolute-protected-admission-directory>/create-preparation.json \
  --expected-preparation-receipt-sha256 <sha256>
```

The two preparation arguments are all-or-none. Create verifies their content
identity and freshness but never reuses admission bids. After all policy and
structural mutations, including any cluster-bound PERSISTENT_2 resources, it
queries Spot prices again, writes `dyec.create_pricing_receipt.v1`, and binds
the exact final bytes to both provider dry-run and create. The exact cluster
name is checked at admission, immediately before the first create-side AWS
mutation, and again immediately before provider create; every provider state
other than `DELETE_COMPLETE` blocks reuse.

The required `--output-dir` is a fresh, empty, owned `0700` directory. It
contains deterministic protected filenames for the final provider input,
final pricing receipt, Slurm-accounting receipt, accounting update,
accounting-recovery receipt, and terminal create receipt. The terminal receipt
binds the exact pricing, accounting, and recovery artifact digests. This is the
only supported restart-recovery source for a create interrupted after provider
submission; DYEC does not discover a configuration from ambient state.

Standalone `dyec create` remains authoritative when the preparation pair is
omitted: it performs its own live admission pass and still performs the
independent final reprice. Creation owns pricing, provider provisioning, and
the mandatory accounting lifecycle. Add
`--create-slurm-accounting-if-missing` together with
`--acknowledge-slurm-accounting-create-cost` only when creation of the regional
accounting service and its ongoing cost were explicitly approved.

In JSON mode, stdout contains exactly one object. A successful
`dyec.create.v1` object has exactly these fields:

```text
schema_version, dyec_version, status, terminal, phase, captured_at,
cluster_name, profile, account_id, region, region_az,
provider_cluster_state, fleet_state, accounting_state, sacct_verified,
request_config_sha256, final_cluster_config_sha256,
pricing_receipt_sha256, accounting_receipt_sha256,
terminal_receipt_path, terminal_receipt_sha256
```

The only success tuple is `status=complete`, `terminal=true`,
`phase=terminal`, provider `UPDATE_COMPLETE`, fleet `RUNNING`, accounting
`ENABLED`, and `sacct_verified=true`. The protected
`dyec.create_terminal.v1` receipt binds the same identities and the create-side
pricing/accounting receipt digests. Any other outcome emits one
`dyec.create.v1` failure object with `status=failed`, `terminal=false`, a safe
`error_code`, and optional exit code; operational detail is written to stderr.

The root `--admin-email`, `--budget-project`, and
`--disable-budget-enforcement` options are retired and rejected. Budget email,
cluster-name project identity, and budget enforcement come only from the exact
rendered request.

`dyec preflight` remains available for operator inspection of an existing
configuration, but it does not replace the strict request-render, admission,
or independent final-pricing gates above.

Inspect:

```bash
dyec --verbose cluster list \
  --profile "$AWS_PROFILE" \
  --region "$REGION"

# One read-only queue-count row per cluster. Provisioning and teardown clusters
# are reported as CLUSTER_NOT_READY rather than as an empty queue.
dyec cluster jobs \
  --profile "$AWS_PROFILE" \
  --region "$REGION"

dyec --json cluster describe \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER"

dyec cluster wait \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER"
```

### Guarded compute-fleet lifecycle

`cluster compute-fleet` is the public automation boundary for stopping or
starting one exact ParallelCluster compute fleet. Upstream services must invoke
the installed `dyec` console script; they must not invoke `pcluster`, import
`daylily_ec.pcluster`, or call a DYEC Python module entrypoint.

The only accepted request/terminal pairs are:

| `--status` | `--wait-for` |
|---|---|
| `STOP_REQUESTED` | `STOPPED` |
| `START_REQUESTED` | `RUNNING` |

The spellings are case-sensitive. A mismatch fails before a provider call.

```bash
dyec --json cluster compute-fleet \
  --cluster "$CLUSTER" \
  --region "$REGION" \
  --profile "$AWS_PROFILE" \
  --status STOP_REQUESTED \
  --wait-for STOPPED \
  --timeout-seconds 1200 \
  --poll-interval-seconds 30
```

Every stop first obtains an authoritative, bounded headnode proof that no
DayOA controller and no Slurm job remains. Without `--drain`, active work fails
the command immediately. With `--drain`, DYEC waits for the work to finish
naturally before submitting the stop request. `--drain` never cancels a job,
signals a controller, changes a Slurm node state, or otherwise drains scheduler
work. It is invalid with `START_REQUESTED`.

The command is idempotent when the fleet is already at the requested terminal
state. It reclaims a same-direction transition without submitting a duplicate;
an opposite-direction transition fails closed. A successful JSON response has
schema `dyec.cluster_compute_fleet.v1` and these fields:

```json
{
  "schema_version": "dyec.cluster_compute_fleet.v1",
  "ok": true,
  "cluster": "<cluster>",
  "region": "<region>",
  "request_status": "STOP_REQUESTED",
  "wait_for_status": "STOPPED",
  "drain_requested": false,
  "initial_status": "RUNNING",
  "final_status": "STOPPED",
  "request_submitted": true,
  "resumed_existing_request": false,
  "idle_proof": {
    "authoritative": true,
    "controller_count": 0,
    "slurm_job_count": 0,
    "observed_at": "<UTC timestamp>",
    "instance_id": "<headnode instance id>",
    "ssm_command_ids": ["<controller probe>", "<queue probe>"]
  },
  "started_at": "<UTC timestamp>",
  "completed_at": "<UTC timestamp>",
  "elapsed_seconds": 0.0
}
```

`idle_proof` is `null` for a start or an already-`STOPPED` no-op. A callback
failure in JSON mode returns the same schema with `ok: false`,
`error_code: compute_fleet_operation_failed` (or `internal_error`), and a
bounded `error` string.

### Crash-safe Slurm-accounting recovery

Before recovery, inspect the regional provider singleton and, when applicable,
one exact existing PrivateLink bridge without changing AWS:

```bash
dyec --json slurm-accounting inspect \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --stack-name <exact-regional-provider-stack> \
  --privatelink-stack-name <exact-existing-bridge-stack>
```

Both expected names are optional inspection filters; omitting the bridge name
does not trigger bridge discovery. The command lists at most 100 bounded
regional provider identities and reports the exact bridge only when that name
was supplied. It is read-only and never creates, updates, reconciles, or
selects infrastructure. Its `dyec.slurm_accounting_inspection.v1` JSON includes
the explicit profile/account/region/AZ, provider names/status/VPC/DB/user and
contract-health evidence, plus bridge provider/consumer VPC binding and target
health. `bridge_provider_binding_matches_regional_provider` compares the exact
bridge with the singleton's provider VPC, database, user, and instance evidence.
Database endpoints, private IPs, password-secret ARNs, IAM policy ARNs,
and raw provider errors are excluded. An unhealthy exact target can still
return its bounded bridge identity with `contract_healthy: false` and
`exact_bridge_error_code: exact_bridge_target_unhealthy_or_unverified`.

```json
{
  "schema_version": "dyec.slurm_accounting_inspection.v1",
  "ok": true,
  "read_only": true,
  "aws_profile": "<trimmed profile>",
  "aws_account_id": "<resolved account id>",
  "region": "us-west-2",
  "region_az": "us-west-2d",
  "expected_accounting_stack_name": "<provider or null>",
  "expected_privatelink_stack_name": "<bridge or null>",
  "regional_provider_count": 1,
  "regional_singleton": true,
  "regional_provider_matches_expected": true,
  "regional_providers": [
    {
      "stack_name": "<provider>",
      "status": "CREATE_COMPLETE",
      "region": "us-west-2",
      "region_az": "us-west-2c",
      "vpc_id": "<provider VPC>",
      "database_name": "<database>",
      "db_username": "<user>",
      "instance_id": "<accounting instance>",
      "instance_type": "<accounting instance type>",
      "required_outputs_present": true,
      "contract_healthy": true
    }
  ],
  "exact_bridge": {
    "stack_name": "<bridge>",
    "status": "UPDATE_COMPLETE",
    "provider_accounting_stack_name": "<provider>",
    "provider_vpc_id": "<provider VPC>",
    "consumer_vpc_id": "<consumer VPC>",
    "database_name": "<database>",
    "db_username": "<user>",
    "accounting_instance_id": "<accounting instance>",
    "accounting_instance_type": "<accounting instance type>",
    "contract_healthy": true
  },
  "exact_bridge_resolved": true,
  "exact_bridge_error_code": null,
  "bridge_provider_matches_expected": true,
  "bridge_provider_binding_matches_regional_provider": true
}
```

`slurm-accounting recover` repairs the incomplete post-create accounting phase
without rerunning `dyec create`. It accepts only the exact persisted cluster
identity and pre-accounting configuration. The supported initial cluster
states are `CREATE_COMPLETE`, `UPDATE_IN_PROGRESS`,
`UPDATE_COMPLETE_CLEANUP_IN_PROGRESS`, and `UPDATE_COMPLETE`.

```bash
dyec --json slurm-accounting recover \
  --cluster "$CLUSTER" \
  --region "$REGION" \
  --region-az "$REGION_AZ" \
  --profile "$AWS_PROFILE" \
  --cluster-configuration <exact-persisted-cluster.yaml> \
  --output-dir <stable-per-cluster-recovery-directory> \
  --stack-name <exact-regional-provider-stack> \
  --privatelink-stack-name <exact-existing-bridge-stack> \
  --database-name <exact-database-name> \
  --db-username <exact-database-user> \
  --instance-type <exact-accounting-instance-type> \
  --timeout-seconds 5400 \
  --poll-interval-seconds 30
```

For direct same-VPC recovery that is explicitly authorized to create a missing
provider singleton and accept its ongoing cost, omit the bridge and supply the
paired creation/cost flags:

```bash
dyec --json slurm-accounting recover \
  --cluster "$CLUSTER" \
  --region "$REGION" \
  --region-az "$REGION_AZ" \
  --profile "$AWS_PROFILE" \
  --cluster-configuration <exact-persisted-cluster.yaml> \
  --output-dir <stable-per-cluster-recovery-directory> \
  --stack-name <exact-regional-provider-stack> \
  --database-name <exact-database-name> \
  --db-username <exact-database-user> \
  --instance-type <exact-accounting-instance-type> \
  --create-slurm-accounting-if-missing \
  --acknowledge-slurm-accounting-create-cost \
  --timeout-seconds 5400 \
  --poll-interval-seconds 30
```

The two creation/cost flags must be supplied together. Omit both when recovery
may reuse only existing infrastructure. They are invalid when
`--privatelink-stack-name` is supplied because recovery never creates or
reconciles a bridge or its provider.

For `CREATE_COMPLETE`, DYEC proves the cluster idle, prepares the exact regional
accounting service and update YAML before changing capacity, stops the fleet,
dry-runs and submits the accounting update, waits for `UPDATE_COMPLETE`, starts
the fleet, and verifies accounting. An already-running update is reclaimed and
never submitted again. `UPDATE_COMPLETE` proceeds only to fleet restoration and
verification. `--stack-name` always names the regional provider singleton. With
no bridge flag, direct attachment is allowed only when that provider and the
cluster headnode subnet are in the same VPC; cross-VPC direct attachment fails
with `exact_direct_vpc_mismatch`. With `--privatelink-stack-name`, recovery
requires the region to contain exactly the named provider and resolves only the
named existing healthy bridge. Its provider stack, provider VPC, consumer VPC,
database, user, accounting instance, and secret binding must match the exact
provider and request. Automatic alternate-stack or bridge selection and all
bridge creation/reconciliation are disabled.
DYEC repeats its authoritative controller/job proof after service preparation
and before update handling, even if the fleet was already stopped; work that
appeared during preparation fails the recovery before any update or restart.

The recovery receipt is a write-ahead identity/phase record. Before rendering,
DYEC atomically records the trimmed AWS profile, resolved AWS account, cluster,
region/AZ, source path and hash, deterministic update path, exact provider
stack, exact bridge name (or JSON `null` for direct mode), consumer VPC,
database/user, instance type, and creation/cost flags. An interrupted
`render_intent` may resume whether or not the update file appeared. After
rendering, DYEC rehashes the source and binds the rendered update hash before
any fleet mutation. Every resumed update revalidates the receipt plus both
current file hashes and re-renders against the exact singleton before fleet
start.

Immediately before the non-dry-run update call, DYEC writes
`update_submission_intent`. If that invocation is interrupted, a retry polls
provider state for up to 300 seconds. A visible update is reclaimed. If the
cluster remains `CREATE_COMPLETE`, the intent is intrinsically ambiguous, so
recovery fails closed for operator review and never resubmits it. A terminal
receipt is accepted only while the provider reports `UPDATE_COMPLETE`.

Recovery also enforces an explicit provider-state/receipt-phase matrix.
`CREATE_COMPLETE` accepts only pre-update phases or the two submission phases;
either submission phase is treated as ambiguous and resolved without
resubmission. `UPDATE_IN_PROGRESS` and
`UPDATE_COMPLETE_CLEANUP_IN_PROGRESS` accept only
`update_submission_intent` or `update_submission`. `UPDATE_COMPLETE` accepts
only those submission phases or `update_complete`,
`post_update_exact_target_verified`, `fleet_running`, and
`accounting_verified`. Unknown phases and every impossible state/phase pair
fail before fleet or update mutation.

`--output-dir` may already exist and may contain unrelated artifacts. Use one
stable directory for one exact recovery identity; a profile/account, identity,
path, or hash mismatch fails closed. DYEC atomically replaces only:

- `slurm-accounting-update.yaml`
- `slurm-accounting-recovery.json`

The final verification proves `slurmdbd` and `slurmctld` active, the Slurm
accounting storage configuration enabled, the exact cluster registered through
`sacctmgr`, and a bounded `sacct -X` query working. Therefore
`accounting_verified: true` is sufficient proof of working `sacct`; callers do
not need a second headnode probe.

A successful JSON response has schema
`dyec.slurm_accounting_recovery.v1` and these fields:

```json
{
  "schema_version": "dyec.slurm_accounting_recovery.v1",
  "ok": true,
  "terminal": true,
  "status": "complete",
  "cluster": "<cluster>",
  "region": "<region>",
  "region_az": "<availability zone>",
  "aws_profile": "<trimmed profile>",
  "aws_account_id": "<resolved account id>",
  "accounting_stack_name": "<regional provider stack>",
  "privatelink_stack_name": "<exact bridge stack or null>",
  "consumer_vpc_id": "<cluster headnode VPC>",
  "database_name": "<database>",
  "db_username": "<database user>",
  "instance_type": "<requested accounting instance type>",
  "create_slurm_accounting_if_missing": false,
  "acknowledge_slurm_accounting_create_cost": false,
  "service_created": false,
  "cluster_configuration_path": "<absolute source path>",
  "cluster_configuration_sha256": "<sha256>",
  "update_configuration_path": "<absolute rendered path>",
  "update_configuration_sha256": "<sha256>",
  "initial_cluster_state": "CREATE_COMPLETE",
  "initial_fleet_state": "RUNNING",
  "final_cluster_state": "UPDATE_COMPLETE",
  "final_fleet_state": "RUNNING",
  "update_submitted": true,
  "update_reclaimed": false,
  "fleet_stop_submitted": true,
  "fleet_start_submitted": true,
  "accounting_verified": true,
  "phase_receipts": [
    {"phase": "accounting_verified", "status": "complete", "observed_at": "<UTC>"}
  ],
  "started_at": "<UTC timestamp>",
  "completed_at": "<UTC timestamp>",
  "elapsed_seconds": 0.0,
  "recovery_receipt_path": "<absolute receipt path>",
  "recovery_receipt_sha256": "<sha256>"
}
```

During recovery, the persisted file uses the same schema with `ok: false`,
`terminal: false`, `status: in_progress`, a stable `phase`, and the bound
identity/hashes available at that phase. The JSON and persisted receipt exclude
database endpoints, passwords, secret ARNs, raw provider output, and raw
exception text. A callback failure in JSON mode returns the same schema with `ok: false`,
`error_code: slurm_accounting_recovery_failed` (or `internal_error`), and a
bounded `error` string. A normalized accounting-preparation failure also returns
bounded lowercase machine tokens in `stage` and `reason_code`. Exact-target
`service_resolution` distinguishes
`exact_regional_stack_inventory_failed`, `exact_regional_stack_conflict`,
`exact_database_discovery_failed`, `exact_database_multiple`,
`exact_stack_missing`, `exact_stack_create_failed`, and
`exact_service_identity_mismatch`. Explicit bridge recovery additionally uses
`exact_privatelink_creation_forbidden`, `exact_privatelink_unavailable`,
`exact_privatelink_identity_mismatch`,
`exact_privatelink_provider_binding_mismatch`, and
`exact_direct_vpc_mismatch`. Provider/SDK text and credentials are never
copied into those fields or the generic public error message; other recovery
failures omit the two preparation fields.

Tags:

```bash
dyec --json cluster tags \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER"

dyec cluster tags \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --set daylily-accept-jobs=false \
  --set operator-note=maintenance-window
```

Delete remains destructive:

```bash
dyec delete --dry-run \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER"
```

Run live deletion only after the exact destructive effect is approved.

## Headnode access and observability

Interactive shell:

```bash
dyec headnode connect \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER"
```

The supported user is `ubuntu` in a bash login shell. Use `root` only when explicitly approved for a specific operation.

Basic headnode inspection:

```bash
dyec --json headnode info --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
dyec headnode jobs --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
dyec --json headnode system-info --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
dyec --json headnode fsx-usage --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
dyec --json headnode analysis-roots --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
dyec --json headnode dayoa-controllers --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
```

Arbitrary headnode command:

```bash
dyec --json headnode run \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  'hostname; command -v aws; aws sts get-caller-identity --output json'
```

`headnode run` is intentionally explicit. It returns the SSM command id, response code, stdout, and stderr. It is marked as mutating-capable because the command string can mutate state.

File transfer through an explicit S3 relay:

```bash
dyec --json headnode upload -r ./local-config-dir \
  /tmp/dyec-config-dir \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --staging-s3-uri "$STAGING_S3_URI"

dyec --json headnode download -r \
  /fsx/analysis_results/$CLUSTER/$ANALYSIS_ID/daylily-omics-analysis/results/day/hg38/reports \
  ./reports \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --staging-s3-uri "$STAGING_S3_URI"
```

Important relay behavior:

- `--staging-s3-uri` is required.
- Both local credentials and the headnode instance role must be allowed to read/write the relay prefix.
- `-r` is required for directories.
- Relay objects are retained for audit; clean them up explicitly if desired.

Configure/repair the headnode:

```bash
dyec headnode configure \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER"
```

The default credential authority is the newest local DYEC create-state record for
`$CLUSTER`. Its exact saved next-run config supplies both deploy-key references. Use
`--state-file <state.json>` when the intended cluster generation is not the newest one.
The two direct deploy-key options are an all-or-nothing recovery override; a partial pair,
mixed state/direct inputs, malformed state, missing config, wrong cluster, or wrong region
fails before an SSM command is sent.

Run this after a DYEC upgrade when the headnode is missing new commands such as `dyec analysis status`, `dyec headnode run`, or current `dy-r` analysis-lock support.

## Analysis-root visits, locks, and status

Record a visit:

```bash
dyec analysis visit \
  --analysis-root "$ANALYSIS_ROOT" \
  --mode read \
  --intent "inspect run state"
```

Acquire a write lock before protected writes:

```bash
dyec analysis lock acquire \
  --analysis-root "$ANALYSIS_ROOT" \
  --operation write \
  --intent "restart failed reporting aggregator"

dyec analysis lock heartbeat --analysis-root "$ANALYSIS_ROOT"
dyec analysis lock status --analysis-root "$ANALYSIS_ROOT"
dyec analysis lock release --analysis-root "$ANALYSIS_ROOT"
```

Guard protected commands:

```bash
dyec analysis guard \
  --analysis-root "$ANALYSIS_ROOT" \
  --operation write \
  -- bash -lc 'touch "$ANALYSIS_ROOT"/operator_test.marker'
```

Takeover is token-based and must not be silent:

```bash
dyec analysis lock takeover \
  --analysis-root "$ANALYSIS_ROOT" \
  --request \
  --intent "recover stale failed controller"
```

Exact-root status:

```bash
dyec analysis status slim \
  --analysis-root "$ANALYSIS_ROOT" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER"

dyec analysis status full \
  --analysis-root "$ANALYSIS_ROOT" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --tail-lines 1000
```

`slim` is for quick controller/job/artifact progress. `full` tails relevant controller/job/rule logs, reports FSx usage, and includes richer per-analysis progress when available.

## Command-family progress

HIOMRS sample stats:

```bash
dyec --json command sample-stats hiomrs-kitchensink \
  --name bjuice20_hiomrs \
  --analysis-root "$ANALYSIS_ROOT" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --tail-lines 1000
```

Download a generated DAG PNG to an exact local filename:

```bash
dyec --json command sample-stats hiomrs-kitchensink \
  --name bjuice20_hiomrs \
  --analysis-root "$ANALYSIS_ROOT" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --dag-output ./tmp/bjuice20_hiomrs_dag.png
```

The DAG transfer is bounded, size-checked, and SHA-256 verified.

## Local identity manifest commands

These commands validate local manifest topology and produce local receipts. They do not call any identity service.

```bash
dyec --json identities validate --manifest-dir ./config > identities.validate.json
dyec --json identities status --manifest-dir ./config > identities.status.json
dyec --json identities plan --manifest-dir ./config --output identities.plan.json
dyec --json identities apply --manifest-dir ./config --plan identities.plan.json --output identities.apply.json
dyec --json identities evidence --manifest-dir ./config --output identities.evidence.json
```

Use them for:

- FK validation across six manifests;
- EUID presence/blank status;
- customer-release eligibility checks driven only by supplied files;
- hash-bound receipts.

Do not add service URLs or tokens to DYEC identity commands.

## Six-manifest sample analysis input

Current DayOA sample analysis expects exactly:

```text
specimens.tsv
samples.tsv
libraries.tsv
sequencing_inputs.tsv
analysis_units.tsv
analysis_unit_inputs.tsv
```

DYEC validates these files before launch and sends them byte-for-byte to the headnode. `units.tsv` is historical and only valid for explicitly legacy catalog commands.

Required topology:

```text
specimens.tsv            SPECIMEN_ID
samples.tsv              SAMPLEID -> SPECIMEN_ID
libraries.tsv            LIBRARY_ID -> SAMPLEID
sequencing_inputs.tsv    SEQUENCING_INPUT_UID -> LIBRARY_ID
analysis_units.tsv       ANALYSIS_UNIT_UID -> SAMPLEID
analysis_unit_inputs.tsv ANALYSIS_UNIT_UID + SEQUENCING_INPUT_UID + ROLE + INPUT_ORDINAL
```

`sequencing_inputs.tsv` must use explicit source columns for the selected layout and modality. `analysis_unit_inputs.tsv` determines the ordered SR/LR input selection for each analysis unit.

## Bjuice prevalence config helper

Purpose: generate exact six-manifest DayOA inputs for reviewed Bjuice prevalence sample subsets from reviewed evidence files.

```bash
dyec --json catalog config-bjuice-preval \
  --sample HG003 \
  --sample HG004 \
  --output-dir ./config-hg003-hg004-ds025 \
  --source-manifest-json /path/to/source_manifest_resolved.json \
  --run-evidence-json /path/to/run_evidence_v2.json \
  --library-run-matrix-tsv /path/to/bjuice_preval_library_run_matrix.tsv \
  --sample-metadata-tsv /path/to/legacy_samples.tsv \
  --legacy-units-tsv /path/to/legacy_units.tsv \
  --sr-subsample-pct 0.25 \
  --ont-subsample-pct 0.25 \
  --analysis-label BJUICEPREVAL \
  --profile "$AWS_PROFILE" \
  --region "$REGION"
```

Outputs:

```text
specimens.tsv
samples.tsv
libraries.tsv
sequencing_inputs.tsv
analysis_units.tsv
analysis_unit_inputs.tsv
bjuice_preval_config_receipt.json
```

The helper:

- requires explicit `--sample` values;
- requires an empty output directory unless the exact file creation is allowed by the implementation;
- maps reviewed S3 source groups into configured `/fsx/run_dir_mounts` paths;
- lists exact S3 FASTQs through AWS;
- populates SR/LR sequencing inputs and ordered analysis-unit inputs;
- writes a receipt with manifest hashes and row counts;
- fails on missing or ambiguous source metadata.

## Bjuice v2 HG002 full-prevalence multi-AU config helper

Purpose: generate exactly seven HG002 analysis units for the full-prevalence Bjuice v2 HIOMR2 contract. This is not an alias or an extension of the slim Bjuice fixture command.

```bash
dyec --json catalog config-bjuice-v2-hg002-multi-au \
  --output-dir ./config-hg002-bjuice-v2 \
  --source-manifest-json /path/to/source_manifest_resolved.json \
  --run-evidence-json /path/to/run_evidence_v2.json \
  --library-run-matrix-tsv /path/to/bjuice_preval_library_run_matrix.tsv \
  --sample-metadata-tsv /path/to/legacy_samples.tsv \
  --legacy-units-tsv /path/to/legacy_units.tsv \
  --direct-ilmn-coverage-x "$C_ILMN" \
  --direct-ilmn-coverage-evidence /path/to/direct_ilmn_terminal_receipt.json \
  --profile "$AWS_PROFILE" \
  --region "$REGION"
```

The direct-coverage evidence is a required terminal JSON receipt with schema `dyec.bjuice_v2_direct_ilmn_coverage_receipt.v1`, `sample_id: HG002`, and a matching `ilmn_direct_coverage_x`. Total, combined, and hybrid coverage evidence is rejected. The helper computes each `SUBSAMPLE_PCT` with decimal `ROUND_DOWN` precision and writes the immutable AU matrix:

| AU | ILMN target | ONT interval |
|---|---:|---|
| `p5xp5` | 0.5x | `[0,1)` |
| `1x1` | 1x | `[0,2)` |
| `3x3` | 3x | `[0,7)` |
| `5x5` | 5x | `[0,11)` |
| `10x5` | 10x | `[0,19)` |
| `15x5` | 15x | `[0,24)` |
| `15x10` | 15x | `[0,19)` |

It writes `bjuice_v2_hg002_multi_au_manifest_receipt.json`, validates the six-manifest topology, leaves nullable live EUID fields blank, and fails hard if the evidence or source topology is incomplete or ambiguous.

### Measured-coverage retargeting

For a second Bjuice-v2 matrix, do **not** hand-edit `analysis_units.tsv`. Supply
one strict plan to the same DYEC generator with `--retarget-plan-json`:

```bash
dyec --json catalog config-bjuice-v2-hg002-multi-au \
  --output-dir ./config-hg002-bjuice-v2-retargeted \
  --source-manifest-json /path/to/source_manifest_resolved.json \
  --run-evidence-json /path/to/run_evidence_v2.json \
  --library-run-matrix-tsv /path/to/bjuice_preval_library_run_matrix.tsv \
  --sample-metadata-tsv /path/to/legacy_samples.tsv \
  --legacy-units-tsv /path/to/legacy_units.tsv \
  --direct-ilmn-coverage-x "$C_ILMN" \
  --direct-ilmn-coverage-evidence /path/to/direct_ilmn_terminal_receipt.json \
  --retarget-plan-json /path/to/hg002_bjuice_v2_retarget_plan.json \
  --profile "$AWS_PROFILE" \
  --region "$REGION"
```

The plan schema is `dyec.bjuice_v2_hg002_retarget_plan.v1`. It must contain
`sample_id: HG002`, a non-empty `source_analysis_id`, and exactly the seven
canonical AU labels. Each row declares `target_ilmn_coverage_x`,
`prior_measured_ilmn_coverage_x`, `prior_subsample_pct`, `subsample_pct`,
`target_ont_coverage_x`, `ont_fq_start_hour`, and `ont_fq_end_hour`. DYEC
rejects any plan whose fraction is not exactly
`ROUND_DOWN(target_ilmn_coverage_x / direct_ilmn_coverage_x, 12 places)`, whose target set changes, or whose ONT window is not a valid cumulative `[0,end)` interval. Prior measured-coverage fields are audit metadata only: they may guide the ONT hour windows but can never override the verified direct Illumina denominator. The direct-coverage receipt remains required as the source-input contract; it is not silently replaced by a measured/hybrid coverage value.

## Catalog discovery

List commands:

```bash
dyec catalog list
dyec --json catalog list
dyec --json catalog list --command-class sample_analysis
dyec --json catalog list --command-class run_analysis --type prod
```

Show one command:

```bash
dyec --json catalog show hybrid_ilmn_ont_hiomr_kitchensink
dyec --json catalog show package_inflection_hybrid_data --dyec-version 19.0.6
dyec --json catalog show illumina_run_qc --dyec-version 19.0.6
```

The catalog exposes:

- command id and display name;
- command class (`sample_analysis`, `run_analysis`, or `utility`);
- repository and DayOA git tag;
- `validated_version` and derived `validation_pending` state;
- input contract;
- resolved command digest and immutable repository/runtime identities;
- targets, callers, aligners, dedupers, jobs, and keep-going settings;
- validated version metadata when present.

The `19.0.6` catalog targets DayOA `16.0.3`. `validation_pending: true` means a
command's launch `git_tag` differs from its recorded `validated_version`; it is
an honest pending-validation indicator, not a launch block or a rewritten
receipt. Existing validation runs and receipt tags remain historical evidence.

## Catalog render

Render the exact `dyec workflow launch` argv without starting a controller:

```bash
dyec --json catalog render hybrid_ilmn_ont_hiomr_kitchensink \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$CLUSTER" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --manifest-dir ./config \
  --payload-staging-s3-uri "$STAGING_S3_URI" \
  --session-name "${ANALYSIS_ID}-dryrun" \
  --project "$PROJECT" \
  --dry-run
```

Useful options:

| Option | Meaning |
|---|---|
| `--analysis-id` | Name under `/fsx/analysis_results/<executing-entity>/`. |
| `--executing-entity` | First path segment under `/fsx/analysis_results`; defaults to cluster. |
| `--git-tag` | Override the catalog DayOA tag. Use only when intentionally testing a specific ref. |
| `--manifest-dir` | Local six-manifest directory. |
| `--payload-staging-s3-uri` | S3 relay for large launch payloads. |
| `--run-context-file` | Local run-context TSV for run-analysis commands. |
| `--stage-dir` | Existing headnode/FSx staging directory. |
| `--dy-config key=value` | Append one explicit DayOA/Snakemake config assignment. Repeatable. |
| `--export-destination-s3-uri`, `--export-trigger`, `--delete-on-export-success` | Present for compatibility in help but rejected for standard catalog/workflow launch. Export separately after terminal controller success. |
| `--replace-existing-analysis-dir` | Forward explicit replacement intent to workflow launch. |

`--dy-config` accepts only explicit assignments like `key=value`; blank strings and free-form shell fragments fail.

Example with DayOA runtime overrides:

```bash
dyec --json catalog render hybrid_ilmn_ont_hiomr_kitchensink \
  --analysis-id bjuice-hg003-hg004-ds025-ont0to6 \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --manifest-dir ./config-hg003-hg004-ds025 \
  --payload-staging-s3-uri "$STAGING_S3_URI" \
  --project "$PROJECT" \
  --dry-run \
  --dy-config use_fq_data_starting_hrs=0 \
  --dy-config use_fq_data_up_to_hrs=6
```

DYEC passes these overrides through; DayOA defines their workflow meaning.

## Catalog launch and quick-launch

Launch a catalog-backed dry run:

```bash
dyec --json catalog launch hybrid_ilmn_ont_hiomr_kitchensink \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$CLUSTER" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --manifest-dir ./config \
  --payload-staging-s3-uri "$STAGING_S3_URI" \
  --session-name "${ANALYSIS_ID}-dryrun" \
  --project "$PROJECT" \
  --dry-run
```

For a fresh live root, render and launch the approved live catalog command.
When a dry controller has already created the exact analysis root and the
contract requires same-root continuation, do **not** reissue `catalog launch`.
Use `workflow launch --reuse-existing-analysis-dir --input-contract none
--no-input-staging` with the exact dry command, ref, and commit, changing only
the DayOA `-n` flag. See [agent_cli_guide.md](agent_cli_guide.md#5-preferred-path-catalog-render-dry-controller-and-live-controller).

`catalog quick-launch` is an alias for `catalog launch`.

The JSON response includes the rendered command, effective `dy-r` command, staging URI, session name, run directory, and workflow launch metadata.

## Workflow launch

Use this lower-level command when there is no catalog row or when a catalog render has already been reviewed and converted into an explicit workflow launch:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$CLUSTER" \
  --git-tag 16.0.3 \
  --manifest-dir ./config \
  --payload-staging-s3-uri "$STAGING_S3_URI" \
  --session-name "$ANALYSIS_ID" \
  --project "$PROJECT" \
  --dy-command "dy-r produce_hiomrs -j 100 -p -T 0 --rerun-triggers mtime --rerun-incomplete"
```

For large local input payloads, use `--payload-staging-s3-uri`. The launch helper uploads a tarball locally, then the headnode downloads it with `aws s3 cp`, expands it in the workflow run directory, and starts the controller from a staged script. The exact controller script is copied to `<analysis-root>/bin/dyec-controller-launch.sh` after `day-clone` succeeds.

### Continue an existing analysis root

Use `--reuse-existing-analysis-dir` only for a new controller that must consume
products already present in one exact analysis root. It is deliberately not a
replacement mode: it requires `--input-contract none` and `--no-input-staging`,
cannot accept manifests or bootstrap configuration, and cannot be combined with
`--replace-existing-analysis-dir`.

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$CLUSTER" \
  --git-tag "$DAYOA_REF" \
  --input-contract none \
  --no-input-staging \
  --session-name "$CONTINUATION_SESSION" \
  --project "$PROJECT" \
  --cost-center "$COST_CENTER" \
  --reuse-existing-analysis-dir \
  --dy-command "dy-r <exact-target> -p -k -j 6"
```

Before creating the controller, DYEC records the analysis visit/lock, verifies
that the existing checkout is a clean Git work tree, fetches the explicit
`--git-tag` reference from `origin`, and checks out its exact fetched commit in
detached mode. It leaves the analysis root and its untracked runtime inputs
intact; a missing root, dirty tracked checkout, absent source ref, or checkout
mismatch fails closed.

### Explicit pinned-source test override

`--pinned-source-test-override "<reason>"` is the deliberately narrow
exception for a human-approved test against one already-dirty existing DayOA
checkout. It is not a normal retry or catalog option. The command requires all
of the following: `--reuse-existing-analysis-dir`, `--reuse-local-git-ref`, a
full `--reuse-local-git-commit`, `--input-contract none`,
`--no-input-staging`, `--dry-run`, and an effective `dy-r` command containing
`-n`. It refuses every export/delete option and retains source evidence in the
headnode run directory before and after the test.

The current-thread human approval must name the exact analysis root, selected
ref/commit, intended source change, reason, and dry-run command. The controller
does not patch, reset, or check out source in this path; it only verifies that
the existing HEAD is the requested commit. This option only permits that
explicit pre-existing change to be exercised; it never authorizes a live run,
delivery, export, cleanup, or promotion.

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$CLUSTER" \
  --git-tag "$DAYOA_REF" \
  --input-contract none \
  --no-input-staging \
  --reuse-existing-analysis-dir \
  --reuse-local-git-ref \
  --reuse-local-git-commit "$DAYOA_COMMIT" \
  --pinned-source-test-override "approved dyoainit initialization test" \
  --dry-run \
  --export-trigger none \
  --session-name "$TEST_SESSION" \
  --dy-command "dy-r <exact-targets> -p -k -j 6 -n"
```

Read status and logs:

```bash
dyec --json workflow status \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --session "$ANALYSIS_ID"

dyec workflow logs \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --session "$ANALYSIS_ID" \
  --stream snakemake \
  --lines 200
```

`workflow status` combines the exact controller target and matching
`status.json` with live process evidence, the active Snakemake master log,
Snakemake progress, submitted/finished job details, and current `squeue`
states. Its top-level `state` is one of `RUNNING`, `SUCCEEDED`, `FAILED`, or
`UNKNOWN`. Important fields include:

- `controller.pid`, raw `controller.pid_exists`, attributed
  `controller.live`, observed and expected cwd/command, and optional exact tmux
  correlation;
- `snakemake_log.path`, `source`, `problem`, and all open candidates when
  attribution is ambiguous;
- `last_progress_at`, `last_progress_line`, submitted/finished job counts and
  details;
- `slurm.available`, current job records, and `state_counts`, including
  `CONFIGURING` and `RUNNING`;
- `terminal.exit_code`, `exit_code_attributed`, `exit_code_source`, and
  high-signal failure markers.

The status command never treats its own RC, tmux existence, queue emptiness,
generic `ERROR` text, a printed shell body, or a stale pane RC marker as the
workflow result. A launched workflow is terminal only when its exact matching
receipt is terminal, or when a dead attributed invocation has a high-signal
Snakemake failure marker. `--stream tmux` and `--stream controller` remain
available for bootstrap and stable controller logs.

The read-only observability probe is compressed and transported by the invoking
CLI. It does not import the new probe module from the headnode's installed DYEC
package, so a local CLI may inspect a cluster built with an earlier DYEC package
without silently changing that cluster. Remote failures preserve SSM command
ID, response code, stdout, and stderr in the CLI error response.
`workflow logs --stream snakemake` performs attribution and the exact tail read
inside that same probe, then transports a compressed tail with byte-count and
SHA-256 integrity metadata. This avoids a second SSM round trip. If the bounded
SSM result cannot carry the compressed tail, the command fails explicitly and
the operator must request fewer `--lines`.

Manual/recovery controllers have no DYEC run-state receipt. Identify one
explicitly with both options below; no repository or newest-log discovery is
performed:

```bash
dyec --json workflow status \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --repo-path /fsx/analysis_results/<owner>/<analysis-id>/daylily-omics-analysis \
  --controller-pid <pid> \
  --session <exact-tmux-session>

dyec workflow logs \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --repo-path /fsx/analysis_results/<owner>/<analysis-id>/daylily-omics-analysis \
  --controller-pid <pid> \
  --session <exact-tmux-session> \
  --stream snakemake --lines 200
```

`--session` is optional in manual mode, but when present it must correlate the
PID to that exact tmux process tree. When the process is dead or its open file
descriptors cannot identify exactly one log, supply the exact
`--snakemake-log <repo-path>/.snakemake/log/<name>.snakemake.log`. Multiple
open logs fail as ambiguous instead of selecting the newest. Without a matching
DYEC terminal receipt, manual success and terminal RC remain `UNKNOWN`/`null`.

The generated DYEC controller never pipes `dy-r` through `tee`. It redirects
stdout/stderr directly to the regular `.dyec/controller.log`, captures the
foreground `dy-r` status, and atomically writes `workflow_completed_at` plus
`workflow_exit_code` to the exact matching `status.json` before controller DAG,
export, or other post-processing. Once the whole controller finishes, its
`completed_at`/`exit_code` pair is authoritative and may override the earlier
workflow pair if post-processing failed.

For a manual recovery controller, use direct regular-file redirection and a
separate log follower:

```bash
dy-r <targets-and-flags> >>/absolute/path/recovery.snakemake.log 2>&1
rc=$?
# Persist rc immediately in the recovery lane's own exact invocation receipt.
```

Do not use `dy-r ... | tee ...`. A background helper can inherit the pipe,
keeping `tee` alive after `dy-r` has returned and delaying the following RC
write. Manual receipts are not inferred or discovered by `workflow status`; a
standard `dyec workflow launch` receipt is required for `SUCCEEDED` and an
authoritative terminal RC.

Collect benchmark summaries from a completed or partially completed DayOA root:

```bash
dyec --json workflow collect-benchmarks \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --analysis-root "$ANALYSIS_ROOT" \
  --genome-build hg38

dyec --json workflow benchmark-report \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --analysis-root "$ANALYSIS_ROOT" \
  --genome-build hg38
```

Stop a workflow controller only when approved:

```bash
dyec --json workflow stop \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --session "$ANALYSIS_ID"
```

Add `--cancel-slurm-jobs --job-name-pattern '<regex>'` only when the exact job cancellation is approved.

## Run-directory mounts

Create a read-only FSx DRA for a sequencing run:

```bash
dyec --json mounts create s3://<sequencing-run-bucket>/<run-prefix>/ \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --platform ILMN \
  --read-only \
  --wait \
  --timeout-seconds 5400
```

Verify:

```bash
dyec --json mounts verify \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --mount-id <mount-id>
```

List/describe/delete:

```bash
dyec --json mounts list --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
dyec --json mounts describe <mount-id> --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
dyec mounts delete <mount-id> --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
```

Do not treat mount creation as timed out before 40 minutes; large DRAs can remain `CREATING`.

## Run-QC catalog commands

Run-QC commands use `input_contract: run_context`.

Every `run_context` file requires these exact TSV headers. A
`run_dra_required` row uses `RUN_DIR` for the verified mounted path and
`MOUNT_ID` for the explicit DRA mount identifier:

```tsv
RUNID	PLATFORM	RUN_DIR	SOURCE_S3_URI	MOUNT_ID	SAMPLE_SHEET	BASECALLING_STATE	RUN_STATUS	OUTPUT_ROOT	REGION	PROFILE
```

Render Illumina, ONT, and Ultima run QC:

```bash
dyec --json catalog render illumina_run_qc \
  --analysis-id ilmn-runqc-20260722 \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --run-context-file ./runs.tsv \
  --dry-run

dyec --json catalog render ont_run_qc \
  --analysis-id ont-runqc-20260722 \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --run-context-file ./runs.tsv \
  --dry-run

dyec --json catalog render ultima_run_qc \
  --analysis-id ultima-runqc-20260722 \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --run-context-file ./runs.tsv \
  --dry-run
```

The catalog rejects a run-context file whose `PLATFORM` does not match the command requirements.

## Inflection hybrid package command

The current command-catalog entry for packaging completed hybrid data is:

```bash
dyec --json catalog show package_inflection_hybrid_data
```

Render a bounded package-only plan against an existing analysis root:

```bash
dyec --json catalog render package_inflection_hybrid_data \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$CLUSTER" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --manifest-dir ./config \
  --payload-staging-s3-uri "$STAGING_S3_URI" \
  --session-name "${ANALYSIS_ID}-package-dryrun" \
  --project "$PROJECT" \
  --dry-run
```

The rendered DayOA target is `produce_inflection_delivery_set`. Review the dry-run plan before launching live packaging. It should not schedule alignment or core variant-calling work for an already-computed analysis root.

## Exports

Export one exact analysis root:

```bash
dyec analysis visit \
  --analysis-root "$ANALYSIS_ROOT" \
  --mode export \
  --intent "export completed pipeline results to $DESTINATION_S3_URI without FSx cleanup"

dyec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --source-path "$ANALYSIS_ROOT" \
  --destination-s3-uri "$DESTINATION_S3_URI" \
  --output-dir ./export-receipts/$ANALYSIS_ID \
  --wait \
  --timeout-seconds 5400
```

The command catalog exposes this contract in the `result_export` object from
`dyec catalog list`, `dyec catalog show`, and `dyec catalog render`. After the
controller succeeds, run the displayed DYEC visit and DRA export commands from
the analysis root. DayOA does not export results. The destination prefix must
remain empty for export's fail-closed preflight, so do not use
`--s3-visit-uri` for that intended destination.

Use export helpers for existing receipts or bulk operation surfaces:

```bash
dyec exports --help
```

Verify `fsx_export.yaml` reports `status=success`, `phase=complete`,
`task_lifecycle=SUCCEEDED`, and `detached=true`; then verify object counts and
expected S3 outputs. FSx data is preserved by default. Cleanup is a separate,
destructive operation and is not part of the catalog export recipe.

## Runtime-cache export

Save every complete real Conda environment and newly fetched real container
image from one cluster-generation namespace with:

```bash
export CACHE_EXPORT_ID=<immutable-cache-export-id>
export CACHE_STAGE_ROOT=/fsx/analysis_results/$CLUSTER/$CACHE_EXPORT_ID
export CACHE_DESTINATION_S3_URI=s3://<dedicated-cache-export-bucket>/<prefix>/$CLUSTER/$CACHE_EXPORT_ID/

dyec runtime-cache export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --executing-entity "$CLUSTER" \
  --cache-export-id "$CACHE_EXPORT_ID" \
  --destination-s3-uri "$CACHE_DESTINATION_S3_URI" \
  --output-dir ./cache-export-receipts/$CACHE_EXPORT_ID \
  --human-requestor <requestor> \
  --stage-timeout-seconds 7200 \
  --export-timeout-seconds 5400
```

Review the exact plan without touching AWS or FSx by adding `--dry-run`. A live
command performs these phases in order:

1. Resolve the cluster headnode and FSx filesystem.
2. Require a new analysis staging root, an empty destination, and no active
   file-system-path or S3-prefix DRA overlap.
3. Reject active Conda mutations or container pulls/builds, incomplete Conda
   directories, missing adjacent YAMLs, and incomplete real container files.
4. Copy the complete real entries with `cp -a`, compare environment byte counts
   and symlink manifests, and retain a runtime-cache manifest in the staging
   root.
5. Recheck the immutable destination, then attach a temporary DRA, run an FSx
   `EXPORT_TO_REPOSITORY` task, and detach without deleting staged FSx data.

The sole supported cache-publication transport is this `cp -a` staging plus
FSx DRA path. Never use `aws s3 cp`, `aws s3 sync`, `aws s3 mv`, or an SDK
object-copy loop for Conda, container, Apptainer/Singularity, or Nextflow cache
trees. `--no-follow-symlinks` is also invalid because it skips symlinks instead
of preserving their type and target. Missing DRA compatibility, permission, or
non-overlap must fail; there is no S3 CLI fallback.

An FSx filesystem cannot have overlapping DRA filesystem paths or S3 data
repository paths. If `/references/` already maps the whole reference bucket,
the runtime-cache export cannot target a subprefix of that bucket from the same
filesystem. Supply a dedicated non-overlapping cache-export bucket/prefix and
retain `runtime_cache_export.yaml`, `dra/fsx_export.yaml`, and the staged root
until a future cluster's explicit import/link contract has been verified.

## Cost and pricing helpers

Spot lifecycle logs:

```bash
dyec pricing spot-logs \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --output spot_prices.csv
```

Cost-center examples:

```bash
dyec cost-centers ensure-registry --profile "$AWS_PROFILE"
dyec --json cost-centers ensure-active project-a \
  --monthly-cap-usd 200 \
  --allowed-user ubuntu \
  --owner-email owner@example.org \
  --profile "$AWS_PROFILE" \
  --home-region us-west-2
dyec cost-centers create project-a --monthly-cap-usd 200 --allowed-user ubuntu
dyec --json cost-centers show project-a
dyec --json cost-centers list --status active
dyec --json cost-centers usage project-a --month 2026-07
dyec --json cost-centers refresh-usage project-a \
  --cluster project-a \
  --month 2026-07 \
  --profile "$AWS_PROFILE" \
  --dry-run
```

`ensure-active` requires both registry tables to exist and be `ACTIVE`; it
never bootstraps them. It conditionally creates one row or strongly consistently
rereads an exact concurrent row, then compares status, cap, canonical sorted
users/groups, the single canonical owner email, empty notes, and unset
expiry/usage-age overrides. It never
reactivates or edits a mismatched row. Its
`dyec.cost_center_ensure_active.v1` response includes `created`, exact
profile/account/home-region, name/status/cap, principal counts and SHA-256
digests, `notes_empty`, and one controlled-fields digest. Raw user and owner
values are not returned.

Budget/cap changes require the workspace double-approval process before live mutation.
For an existing fixed monthly USD AWS Budget, plan the exact change first:

```bash
dyec aws budget set-limit "$CLUSTER" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --expected-current-monthly-cap-usd 200 \
  --monthly-cap-usd 300 \
  --dry-run
```

After the required approvals, repeat the command without `--dry-run`. The
expected-current value is a compare-before-write guard. Dry-run mode never
calls AWS `UpdateBudget`; a live update preserves the supported budget filter
and time contract, omits read-only fields, and verifies the new limit with an
immediate readback. A stale expected cap, planned or auto-adjusting budget,
non-monthly/non-cost/non-USD budget, or readback mismatch fails explicitly.
Requesting the already-current cap succeeds without submitting an update.

AWS readiness and quota helpers:

```bash
dyec aws --help
dyec pricing --help

dyec --json aws capacity-snapshot \
  --region "$REGION" \
  --profile "$AWS_PROFILE" \
  --quota-family standard
```

`dyec.aws_capacity_snapshot.v1` obtains each requested EC2 vCPU quota and uses
that quota's own Service Quotas `UsageMetric` definition to query CloudWatch.
Every quota row includes quota code/name/limit/unit, exact metric
namespace/name/dimensions/statistic, observation timestamp/age, authoritative
used vCPUs, headroom, and bounded non-authoritative EC2 inventory context.
Missing metric metadata, query failure, no datapoint, or a stale/future
datapoint yields `complete=false`, safe reason codes, and null authoritative
used/headroom for every row. Callers must reject an incomplete snapshot.

## Tests and validation helpers

Local tests:

```bash
dyec tests pytest
dyec tests pytest --coverage
python -m pytest tests/test_cli_registry_v2.py -q
```

Catalog validation:

```bash
dyec --json tests command-catalog \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --command-codes dyec-released-core \
  --evidence-s3-uri s3://<evidence-root>/ \
  --dry-run
```

Performance profile:

```bash
dyec --json tests command-catalog-performance \
  --benchmark-rows ./benchmark_rows.tsv \
  --output-dir ./command_catalog_performance
```

## Recommended full CLI-only launch sequence

1. Activate local DYEC:

   ```bash
   cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
   source ./activate
   ```

2. Verify cluster/headnode:

   ```bash
   dyec --json cluster describe --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
   dyec --json headnode run --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" 'hostname; command -v dyec; command -v aws'
   ```

3. Generate or validate the local config:

   ```bash
   dyec --json identities validate --manifest-dir ./config
   ```

4. Render the catalog command:

   ```bash
   dyec --json catalog render hybrid_ilmn_ont_hiomr_kitchensink \
     --analysis-id "$ANALYSIS_ID" \
     --executing-entity "$CLUSTER" \
     --profile "$AWS_PROFILE" \
     --region "$REGION" \
     --cluster "$CLUSTER" \
     --manifest-dir ./config \
     --payload-staging-s3-uri "$STAGING_S3_URI" \
     --project "$PROJECT" \
     --dry-run
   ```

5. Launch the dry run:

   ```bash
   dyec --json catalog launch hybrid_ilmn_ont_hiomr_kitchensink \
     --analysis-id "$ANALYSIS_ID" \
     --executing-entity "$CLUSTER" \
     --profile "$AWS_PROFILE" \
     --region "$REGION" \
     --cluster "$CLUSTER" \
     --manifest-dir ./config \
     --payload-staging-s3-uri "$STAGING_S3_URI" \
     --session-name "${ANALYSIS_ID}-dryrun" \
     --project "$PROJECT" \
     --dry-run
   ```

6. Inspect dry-run status/logs:

   ```bash
   dyec --json workflow status --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" --session "${ANALYSIS_ID}-dryrun"
   dyec workflow logs --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" --session "${ANALYSIS_ID}-dryrun" --lines 200
   ```

7. For a fresh live root, render and launch the live catalog command. For a
   same-root dry-to-live controller, follow the explicit `workflow launch`
   continuation in [agent_cli_guide.md](agent_cli_guide.md#5-preferred-path-catalog-render-dry-controller-and-live-controller); do not relaunch the catalog row onto the existing root.

8. Monitor the exact analysis root:

   ```bash
   dyec analysis status full \
     --analysis-root "$ANALYSIS_ROOT" \
     --profile "$AWS_PROFILE" \
     --region "$REGION" \
     --cluster "$CLUSTER" \
     --tail-lines 1000
   ```

9. Export after success. Record an `analysis visit --mode export` first, then
   run the command below with a previously empty destination prefix:

   ```bash
   dyec export \
     --profile "$AWS_PROFILE" \
     --region "$REGION" \
     --cluster "$CLUSTER" \
     --source-path "$ANALYSIS_ROOT" \
     --destination-s3-uri s3://<analysis-results-bucket>/<prefix>/$CLUSTER/$ANALYSIS_ID/ \
     --output-dir ./export-receipts/$ANALYSIS_ID \
     --wait --timeout-seconds 5400
   ```

## Release conventions

Package releases use numeric annotated tags with no leading `v`:

```bash
git tag -a <next-version> -m "Release <next-version>"
git cat-file -t <next-version>
git push origin <next-version>
```

`git cat-file -t <tag>` must return `tag`, not `commit`.

Both source and packaged global config files must be kept in sync for self-pins:

```text
config/daylily_cli_global.yaml
daylily_ec/resources/payload/config/daylily_cli_global.yaml
```
