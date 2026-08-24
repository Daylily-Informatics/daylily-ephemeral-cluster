# DYEC Agent and Operator CLI Guide

> **Read this first before operating a DYEC cluster or a DayOA analysis.**
> Start with `dyec agent guidance` for the short terminal reminder, then use
> this guide for the full command path. It is written for both human operators
> and agents.

DYEC is the cluster, headnode, FSx, launch, monitoring, and export control
plane. DayOA owns workflow rules and runs only through its `dy-r` wrapper.
DYEC is neither an identity service nor a replacement for DayOA.

## The safe command map

| Need | Start with | Important boundary |
|---|---|---|
| Identify the installed CLI and catalog pin | `dyec --json version`, `dyec --json catalog list` | A release tag is not a DayOA tag; inspect the rendered catalog row. |
| Inspect cluster, headnode, controllers, or queue | `dyec cluster describe`, `dyec headnode dayoa-controllers`, `dyec headnode jobs` | Inspection does not authorize Slurm or node intervention. |
| Create a cluster | `dyec preflight`, then `dyec create` | The normal create entrypoint resolves the shipped config and needs only profile, region/AZ, and cluster type. |
| Stop/start a compute fleet | `dyec cluster compute-fleet` | Exact state pairs only; every stop proves controllers/jobs idle, and `--drain` only waits naturally. |
| Inspect accounting topology | `dyec slurm-accounting inspect` | Read-only exact provider/bridge evidence; it never creates, reconciles, or selects a bridge. |
| Make an S3 run directory available on FSx | `dyec mounts create`, then `dyec mounts verify` | Run mounts are read-only by default. Wait generously for DRA availability. |
| Run a known production workflow | `dyec catalog show`, `dyec catalog render`, `dyec catalog launch` | Render first; honor the command's exact input contract and DayOA pin. |
| Run a reviewed non-catalog workflow | `dyec workflow launch` | Supply the exact DayOA tag, input contract, and `--dy-command`; do not improvise defaults. |
| Monitor one analysis | `dyec workflow status`, `dyec workflow logs`, `dyec analysis status full` | Queue emptiness is not workflow success. |
| Export completed results | `dyec analysis visit --mode export`, then `dyec export` | Export is a separate no-delete DRA action after a successful controller. |
| Share one exported S3 object | `dyec aws s3 presign` | The object must already exist; the read-only URL lifetime is explicitly bounded to seven days. |
| Work interactively in DayOA | `dyec headnode connect`, then named `tmux` + `dy-r` | Never use raw `snakemake` or a noninteractive headnode command to run a controller. |

## 1. Start locally and identify the exact release

Run DYEC from its activated checkout. Set only explicit, reviewed context:

```bash
cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate

export AWS_PROFILE=<profile>
export REGION=us-west-2
export CLUSTER=<cluster-name>
export EXECUTING_ENTITY=<analysis-owner>
export ANALYSIS_ID=<unique-analysis-id>
export ANALYSIS_ROOT="/fsx/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID"

dyec --json version
dyec -v --json info
dyec agent guidance
dyec --json catalog list --dyec-version <dyec-release>
```

For repeated local DYEC work, `dyec set-vars` may store the supported profile,
region, AZ, and cluster-admin email in the ignored `$PWD/.dyec.config.yaml`.
Explicit flags always win. The local context file is not an identity source and
does not replace explicit manifests, run contexts, S3 prefixes, or DayOA tags.

Use `dyec <group> --help` before an unfamiliar mutation. Prefer `--json` for
status, evidence capture, and automation.

## 2. Read-only cluster and controller triage

These commands inspect current state without administering Slurm:

```bash
dyec --json cluster describe \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"

dyec --json headnode dayoa-controllers \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"

dyec headnode jobs \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"

dyec --json workflow status \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --session <controller-session>

dyec workflow logs \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --session <controller-session> --stream controller --lines 200
```

Treat a workflow as successful only when its attributed controller has a
terminal `rc=0` / terminal exit code of `0`. A finished tmux pane, an empty
queue, or the exit code of the status command is not proof of workflow success.

Do not cancel, requeue, hold, release, drain, resume, restart, or otherwise
administer Slurm merely because the queue is slow or a node is configuring.
Those are separate, explicitly approved operations.

## 3. Cluster lifecycle and headnode access

Use `dyec preflight` when you want a read-only validation pass before an
approved cluster creation. Root `dyec create` owns the complete 19.0.4 create
workflow: it resolves the shipped config and inputs, renders and prices the
cluster, creates it, configures the headnode, and runs post-create accounting.
Do not substitute raw `pcluster create-cluster` for DYEC.

The normal entrypoint needs only the original three operator flags:

```bash
dyec preflight \
  --profile "$AWS_PROFILE" --region-az <region-az>

dyec create \
  --profile "$AWS_PROFILE" --region-az <region-az> \
  --cluster-type intel
```

`--config <approved-cluster-config.yaml>` remains available when an operator
wants to supply explicit triplet values. It is optional; root create does not
require a `create-request` receipt, an output directory, or a separate recovery
workflow.

The newer `create-request`, `cluster compute-fleet`, `slurm-accounting inspect`,
and `slurm-accounting recover` commands remain separately registered tools.
They are not prerequisites for, phases of, or commands invoked by root
`dyec create`; their standalone option contracts remain in
[cli_reference.md](cli_reference.md).

For an interactive headnode shell, use DYEC rather than an ad hoc SSM command:

```bash
dyec headnode connect \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
```

Leave `--remote-user` at `auto` unless the platform is known and an override is
needed. DYEC resolves Ubuntu/Intel DayOA headnodes to `ubuntu` and
DRAGEN/RHEL-style headnodes to `ec2-user`; unknown platform identity fails
instead of guessing.

## 4. Inputs: validate rather than discover

First inspect the catalog row. Its input contract decides the only accepted
input shape:

```bash
dyec --json catalog show <command-id> --dyec-version <dyec-release>
```

| Contract | Required operator input |
|---|---|
| `six_manifest` | An exact local directory containing the six validated DayOA manifests. |
| `run_context` | A reviewed local `runs.tsv` and the exact verified run mount(s). |
| `sample_manifest` / `sample_manifest_v12` | The explicit legacy staged-manifest input specified by that row. |
| `none` | No input file arguments; do not invent a manifest. |

For a six-manifest analysis, validate the exact directory before rendering:

```bash
dyec --json identities validate --manifest-dir <manifest-dir>
dyec --json identities status --manifest-dir <manifest-dir>
```

For a run analysis, create and verify the exact DRA-backed mount before using
its path in `runs.tsv`. Large run directories can remain in `CREATING` for more
than 40 minutes, so use an explicit, patient wait timeout instead of duplicating
the association:

```bash
dyec --json mounts create "s3://<bucket>/<run-prefix>/" \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --platform <ILMN|ONT|ULTIMA> --read-only --wait --timeout-seconds 5400

dyec --json mounts verify \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --mount-id <mount-id>
```

Do not infer an input path, a mate, an analysis unit, a run mount, or a DayOA
configuration from older results or another analysis root. Missing explicit
inputs are a blocker.

## 5. Preferred path: catalog render, dry controller, and live controller

Known production work should enter through the catalog. Render before any
controller launch; it exposes the pinned DayOA tag, input contract, exact
targets, effective `dy-r`/`bin/day_run` command, and required launch options.

```bash
dyec --json catalog render <command-id> \
  --dyec-version <dyec-release> \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$EXECUTING_ENTITY" \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --manifest-dir <manifest-dir-if-required> \
  --run-context-file <runs.tsv-if-required> \
  --payload-staging-s3-uri "s3://<bucket>/<temporary-relay-prefix>/" \
  --session-name "${ANALYSIS_ID}-dry" \
  --project <project> --cost-center <active-cost-center> \
  --dry-run
```

Pass only the input flags required by `catalog show`; for example, a
`run_context` command does not accept a made-up six-manifest directory. Do not
override `--git-tag` unless the release plan specifically authorizes that exact
tag.

Launch the reviewed dry controller with the same explicit values:

```bash
dyec --json catalog launch <command-id> \
  --dyec-version <dyec-release> \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$EXECUTING_ENTITY" \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  <the same required input and project options> \
  --session-name "${ANALYSIS_ID}-dry" --dry-run
```

A dry controller passes only when it returns `rc=0` and submits zero workflow
work. Capture the rendered effective command and the controller status in the
ledger.

For a direct `dyec workflow launch`, `--dry-run` appends `-n` to the effective
`dy-r`/`bin/day_run` command even when the caller supplies `--dy-command`.
Use repeatable `--rerun-triggers` for an explicit trigger set, for example
`--rerun-triggers mtime`; do not embed that option in `--dy-command` as well.
For a same-root live continuation, remove only `--dry-run` and retain the
identical trigger selection, DayOA commit, manifests, and in-clone config.

`$ANALYSIS_ID` names one analysis capsule: its FSx root, DayOA checkout/commit,
staged inputs, and runtime config. The `-dry` and `-live` suffixes below are
only controller-session labels. A passing dry run is the preflight of the live
command in that same capsule; creating a replacement live root invalidates that
proof. Use a new root only for a deliberately new analysis with a changed
command, pin, inputs, or config, followed by a new dry run.
Do not encode `-dry` or `-live` into `$ANALYSIS_ID`; use those suffixes only in
the controller session name.

To run the validated command, do not issue a second catalog launch against the
existing root. Use the exact rendered workflow command for a new controller
with the same analysis ID and the supported continuation controls:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --analysis-id "$ANALYSIS_ID" --executing-entity "$EXECUTING_ENTITY" \
  --git-tag <exact-dayoa-tag> \
  --reuse-existing-analysis-dir \
  --input-contract none --no-input-staging \
  --reuse-local-git-ref --reuse-local-git-commit <40-character-commit> \
  --session-name "${ANALYSIS_ID}-live" \
  --project <project> --cost-center <active-cost-center> \
  --dy-command "<exact dry command with only -n removed>"
```

The controller owns the analysis-root write lock. Do not pre-acquire a second
write lock for a DYEC-launched controller; it can block the controller itself.
Do not use `--replace-existing-analysis-dir` as a continuation shortcut.

## 6. Lower-level and interactive DayOA work

Use `dyec workflow launch` only after the exact DayOA tag, input contract,
analysis ID, `--dy-command`, and staging paths are known. It starts a supported
headnode tmux controller. It is not a place to omit tags or let DYEC discover
inputs.

For genuinely manual DayOA work, use a persistent interactive headnode session
and a named single-pane tmux session. The setup commands are deliberately
separate:

```bash
# Opened by `dyec headnode connect`; run as the platform-resolved login user.
tmux new-session -s <meaningful-analysis-session> 'bash -l'

# Inside that tmux pane, after the exact DayOA checkout is present:
cd /fsx/analysis_results/<executing-entity>/<analysis-id>/daylily-omics-analysis
source dyoainit
dy-a slurm hg38
dy-r <exact-targets> <exact-flags>
```

Before a manually launched live controller writes the analysis root, record
the required analysis visit and acquire the documented lock. See
[analysis_root_agent_locking.md](analysis_root_agent_locking.md) for the
exact owner, guard, release, and takeover commands.

Never invoke raw `snakemake`, run a DayOA controller through `dyec headnode
run`, use a one-shot noninteractive SSM script, or patch the pinned DayOA
checkout. If the release lacks required behavior, release that behavior in
DayOA first; do not repair it on the headnode.

## 7. Monitor one exact root

Use a controller session for workflow status/logs and an analysis-root status
for durable root evidence:

```bash
dyec --json workflow status \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --session <session-name>

dyec workflow logs \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --session <session-name> --stream snakemake --lines 200

dyec analysis status full \
  --analysis-root "$ANALYSIS_ROOT" \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --tail-lines 1000
```

For large workflows, `workflow status` preserves complete job totals and Slurm
state counts while returning at most 20 recent records per growing collection;
inspect the explicit returned-count and truncation fields.

For a manual/recovery controller, provide the explicit `--repo-path` and
`--controller-pid`; do not use newest-log or newest-repository discovery.

## 8. Export a successful root without deletion

Export is always a post-controller DYEC operation. Standard catalog and
workflow launch paths intentionally reject `--export-destination-s3-uri`,
`--export-trigger`, and `--delete-on-export-success`; those options are not an
alternative to the explicit receipt-producing export below.

Use a unique, currently empty destination that maps to the complete analysis
root. **Do not pass `--s3-visit-uri` for the intended export destination:** the
visit marker would create an object before `dyec export` performs its
fail-closed empty-prefix preflight.

```bash
export DESTINATION_S3_URI="s3://<results-bucket>/<prefix>/$EXECUTING_ENTITY/$ANALYSIS_ID/"

dyec --json exports preflight \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --source-path "$ANALYSIS_ROOT" \
  --destination-s3-uri "$DESTINATION_S3_URI"

dyec analysis visit \
  --analysis-root "$ANALYSIS_ROOT" \
  --mode export \
  --intent "export completed analysis root without FSx deletion"

dyec export \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --source-path "$ANALYSIS_ROOT" \
  --destination-s3-uri "$DESTINATION_S3_URI" \
  --output-dir "./export-receipts/$ANALYSIS_ID" \
  --wait --timeout-seconds 5400
```

`dyec exports preflight` is read-only. It verifies the FSx identity and DRA
compatibility, the exact source/destination suffix contract, destination
emptiness, and absence of any active DRA overlap without creating an
association or task. Run it before seeking approval for a destructive export.

Record the `fsx_export.yaml` path, export task ID, destination, effective
controller command, and manifest/config hashes. Accept the export only when
the receipt reports `status: success`, `phase: complete`,
`task_lifecycle: SUCCEEDED`, `detached: true`, preserved FSx data, and
clone-status-v2 verification.

Deletion, DRA detachment that deletes data, and cleanup are separate destructive
actions; they need their own explicit approval.

Presign one exact exported object only after the export receipt and object path
have been verified:

```bash
dyec --json aws s3 presign \
  --profile "$AWS_PROFILE" --region "$REGION" \
  --s3-uri "s3://<results-bucket>/<exact-object-key>" \
  --expires-in-seconds 604800
```

The command performs `HeadObject` first, rejects bucket/prefix URIs, and emits
the exact object metadata, issue/expiration timestamps, and read-only GET URL.
Treat the URL as an ephemeral credential and do not persist it in a ledger.

## 9. Common stop conditions

Stop and report the blocker rather than inventing a fallback when any of the
following is true:

- the requested numeric DYEC catalog snapshot does not exist;
- the catalog render resolves a different DayOA tag than the approved plan;
- the manifest, mount, DRA, S3 prefix, or required source file is missing;
- the destination export prefix is nonempty or overlaps another DRA;
- an analysis root is owned by another writer;
- the pinned DayOA checkout is dirty or does not resolve the requested commit;
- the task would raise a budget/cost-center cap, delete data, alter cluster
  infrastructure, or administer Slurm without the required separate approval.

## Related references

- [CLI reference](cli_reference.md): complete option-level reference and longer examples.
- [Quickest Start](quickest_start.md): public-safe operator flow.
- [Operations](operations.md): day-2 cluster and headnode runbook.
- [Analysis-root locking](analysis_root_agent_locking.md): visit, lock, guard, and takeover protocol.
- [Overview](overview.md): DYEC/DayOA responsibility boundaries.
