# DYEC CLI Reference

This document is the operator-facing reference for the `18.0.15` `dyec` command surface. It favors explicit commands and receipts over implicit state. `daylily-ec` is an installed compatibility entrypoint for the same CLI, but current docs and ledgers use `dyec`.

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
- analysis-root visit/lock safety;
- headnode upload/download syntax;
- the DRA-only runtime-cache export boundary;
- monitoring commands and Slurm queue format.

Use this when an operator or agent needs a concise reminder of the safe path.

## Cluster lifecycle

Preflight:

```bash
dyec preflight \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config ~/.config/daylily/daylily_ephemeral_cluster.yaml
```

Create:

```bash
dyec create \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config ~/.config/daylily/daylily_ephemeral_cluster.yaml
```

For this command only, `--admin-email` overrides the AWS Budget notification
email. Its precedence is `--admin-email`, then `budget_email` in the create
YAML, then local `cluster_admin_email`, then the pre-existing default. It does
not change heartbeat email behavior:

```bash
dyec create --admin-email oncall@example.org --region-az us-west-2d
```

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
dyec --json catalog show package_inflection_hybrid_data
dyec --json catalog show illumina_run_qc
```

The catalog exposes:

- command id and display name;
- command class (`sample_analysis`, `run_analysis`, or `utility`);
- repository and DayOA git tag;
- `validated_version` and derived `validation_pending` state;
- input contract;
- exact `dy-r` or `bin/day_run` command string;
- dry-run command string;
- targets, callers, aligners, dedupers, jobs, and keep-going settings;
- validated version metadata when present.

The active catalog targets DayOA `15.0.8`. `validation_pending: true` means a
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
| `--export-destination-s3-uri` | Optional auto-export root/destination. |
| `--export-trigger none|on-success|on-fail|all` | Auto-export trigger. |
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

Launch live after the dry-run plan is reviewed:

```bash
dyec --json catalog launch hybrid_ilmn_ont_hiomr_kitchensink \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$CLUSTER" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --manifest-dir ./config \
  --payload-staging-s3-uri "$STAGING_S3_URI" \
  --session-name "$ANALYSIS_ID" \
  --project "$PROJECT"
```

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
  --git-tag 15.0.8 \
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
  --intent "export completed pipeline results to $DESTINATION_S3_URI without FSx cleanup" \
  --s3-visit-uri "$DESTINATION_S3_URI"

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
the analysis root. DayOA does not export results.

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
```

Use these before live cluster creation or quota-heavy launches.

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

7. Launch live only if the plan is correct:

   ```bash
   dyec --json catalog launch hybrid_ilmn_ont_hiomr_kitchensink \
     --analysis-id "$ANALYSIS_ID" \
     --executing-entity "$CLUSTER" \
     --profile "$AWS_PROFILE" \
     --region "$REGION" \
     --cluster "$CLUSTER" \
     --manifest-dir ./config \
     --payload-staging-s3-uri "$STAGING_S3_URI" \
     --session-name "$ANALYSIS_ID" \
     --project "$PROJECT"
   ```

8. Monitor the exact analysis root:

   ```bash
   dyec analysis status full \
     --analysis-root "$ANALYSIS_ROOT" \
     --profile "$AWS_PROFILE" \
     --region "$REGION" \
     --cluster "$CLUSTER" \
     --tail-lines 1000
   ```

9. Export after success:

   ```bash
   dyec export \
     --profile "$AWS_PROFILE" \
     --region "$REGION" \
     --cluster "$CLUSTER" \
     --source-path "$ANALYSIS_ROOT" \
     --destination-s3-uri s3://<analysis-results-bucket>/<prefix>/$CLUSTER/$ANALYSIS_ID/ \
     --output-dir ./export-receipts/$ANALYSIS_ID
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
