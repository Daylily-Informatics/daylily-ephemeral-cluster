# Operations

This is the day-2 runbook for current DayEC clusters.

This guide describes the `18.0.26` CLI. For repeated work, `dyec set-vars` can
store the four supported values in `$PWD/.dyec.config.yaml`; explicit flags
still win, and direct `aws`/`pcluster` commands keep their normal environment
requirements. See [cli_reference.md](cli_reference.md) for the strict local
context contract.

## Connect

```bash
dyec headnode connect \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

Expected on the headnode:

```bash
whoami
pwd
command -v day-clone
command -v tmux
```

The supported remote user is selected by cluster/platform: `ubuntu` for Ubuntu/Intel DayOA headnodes and `ec2-user` for DRAGEN/RHEL-style headnodes. The supported working directory is that user's home directory unless a command explicitly changes it.

## Re-run Headnode Configuration

```bash
dyec headnode configure \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

Use this after a cluster exists but the DayEC headnode tools, catalog, analysis guard surface, or login shell need repair. In particular, if a DayOA run reports `No such command 'analysis'`, rerun this command from an activated local checkout and then verify `dyec analysis --help` on the headnode before workflow writes.

### Managed LSMC Bio GitHub Access

For ordinary `git clone`, `fetch`, `pull`, and `push` from the headnode, use a
dedicated GitHub fine-grained token stored as a Secrets Manager `SecretString`.
Limit it to `lsmc-bio/daylily-ephemeral-cluster` and
`lsmc-bio/daylily-omics-analysis`, with repository contents read/write access:

```bash
dyec headnode configure \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --github-token-secret-arn "$GITHUB_TOKEN_SECRET_ARN"
```

The headnode IAM role—not an IAM group, which cannot contain an EC2 role—must
have `secretsmanager:DescribeSecret` and `secretsmanager:GetSecretValue` for
that exact secret. Configure this only on the headnode role; compute queues do
not receive GitHub credential permissions. DayEC stores only the secret ARN and
region in a mode-`0600` file and retrieves the token only when Git requests a
credential. Existing SSH GitHub origins for the two allowlisted repositories
are rewritten to HTTPS, so the token supports any permitted branch or tag.
GitHub repository rules and branch protections remain authoritative.

## Inspect Cluster And Jobs

```bash
dyec cluster list --profile "$AWS_PROFILE" --region "$REGION" --verbose
dyec --json cluster describe --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec headnode jobs --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
```

To record an operator scheduling note without changing Slurm state, use cluster
stack tags:

```bash
dyec --json cluster tags --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec cluster tags --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME" \
  --set daylily-accept-jobs=false \
  --set operator-note=maintenance
dyec cluster tags --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME" \
  --set daylily-accept-jobs=true \
  --delete operator-note
```

`cluster tags` updates only the CloudFormation stack tags identified by
ParallelCluster `describe-cluster`. It does not cancel, hold, release, drain, or
resume jobs or nodes.

## Stage Sample Inputs

Use `samples stage` for sample-manifest workflows:

```bash
dyec samples stage "$ANALYSIS_SAMPLES" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --reference-s3-uri "$REF_S3_URI" \
  --control-data-s3-uri "$CONTROL_DATA_S3_URI" \
  --stage-s3-uri "$STAGE_S3_URI" \
  --config-dir "$STAGE_CFG_DIR"
```

The helper writes local staged config files and prints a remote stage directory under `/fsx/staging/staged_external_sequencing_data/...`.

For catalog-driven sample launches:

```bash
dyec samples run "$ANALYSIS_SAMPLES" \
  --command-id complete_genomics_mgi_snv_concordance \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --reference-s3-uri "$REF_S3_URI" \
  --control-data-s3-uri "$CONTROL_DATA_S3_URI" \
  --stage-s3-uri "$STAGE_S3_URI" \
  --analysis-id dayoa \
  --executing-entity "$EXECUTING_ENTITY" \
  --dry-run
```

The active catalog pin for DayOA commands is `15.0.15`. A catalog row can retain
an older `validated_version`; `validation_pending: true` reports the difference
without rewriting historical evidence or blocking a launch.

Use `--project <project>` on `dyec samples run` or `dyec workflow launch` when
the cost-center/comment string should differ from the default. DYEC passes that
value to `dyoainit`, DayOA exports it as `DAY_PROJECT`, and Slurm receives it as
`sbatch --comment "$DAY_PROJECT"`. The value is not the cluster AWS Budget name.

## Collect DayOA Benchmark Summary

Use this after a DayOA checkout already exists under an analysis result root:

```bash
dyec --json workflow collect-benchmarks \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --analysis-root "/fsx/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID" \
  --genome-build hg38_broad
```

DYEC runs the collector as the platform-resolved remote user, from
`<analysis-root>/daylily-omics-analysis`. The remote command acquires an
analysis-root write lock, runs `source dyoainit`, `dy-a local <genome-build>`,
then runs `bash bin/util/benchmarks/collect_day_benchmark_data.sh <genome-build>`.
The combined output is
`results/day/<genome-build>/reports/benchmarks_summary.tsv`.

## Attach Run Folders

Use run DRAs for raw run folders that should stay in S3 until read by the workflow:

```bash
dyec --json mounts create "s3://sequencer-run-bucket/runs/RUN123/" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --platform ILMN \
  --read-only \
  --batch-import-metadata-on-create \
  --auto-import NEW,CHANGED \
  --wait \
  --timeout-seconds 3600
```

Rules:

- FSx API path is `/run_dir_mounts/<mount_id>/`.
- Headnode path is `/fsx/run_dir_mounts/<mount_id>/`.
- AutoExport is not configured by default.
- Source prefixes and FSx paths must not overlap active DRAs.
- Run mounts are input paths, not result paths.

Verify on the headnode:

```bash
dyec --json mounts verify \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --mount-id RUN123
```

Detach when done:

```bash
dyec --json mounts delete \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --mount-id RUN123 \
  --wait \
  --timeout-seconds 3600
```

Deletion detaches the DRA with `DeleteDataInFileSystem=False`; it does not delete S3 objects.

## Launch Workflows

DYEC launch mechanics are manager-agnostic at the FSx boundary: the repository
checkout and durable outputs must stay under
`/fsx/analysis_results/<executing_entity>/<analysis_id>/`, then `dyec export`
exports that whole analysis directory. DayOA catalog rows are Snakemake 7
workflows; Nextflow, Snakemake 8, and future Cromwell/WDL repositories need
manager-native commands and output paths. See
[`pipeline_manager_launches.md`](pipeline_manager_launches.md).

For a current six-manifest catalog command, render before launching. The
catalog declares the exact input contract; do not substitute a legacy
`--stage-dir` shape for a command that requires `--manifest-dir`.

```bash
dyec --json catalog render hybrid_ilmn_ont_hiomr_kitchensink \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$EXECUTING_ENTITY" \
  --manifest-dir ./config \
  --payload-staging-s3-uri "$STAGING_S3_URI" \
  --dry-run
```

Launch the reviewed catalog plan by changing `render` to `launch`, keeping the
same explicit inputs and a new live session name if needed.

For a direct run-context workflow, declare the `run_context` contract and the
DayOA release explicitly:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --input-contract run_context \
  --run-context-file ./runs.tsv \
  --analysis-id run-qc \
  --executing-entity "$EXECUTING_ENTITY" \
  --git-tag 15.0.15 \
  --genome hg38_broad \
  --jobs 5 \
  --target produce_illumina_run_qc \
  --snakemake-extra "--config run_context_file=config/runs.tsv"
```

The launcher creates `/home/<resolved-remote-user>/daylily-runs/<session>/` with the controller launch script, `tmux.log`, `status.json`, and controller receipt files.
Controller output is written directly to the regular
`<analysis-repo>/.dyec/controller.log`; the launcher does not put `dy-r` behind
`tee` or another pipeline. It atomically writes `workflow_completed_at` and
`workflow_exit_code` immediately after the foreground workflow command returns,
before DAG synchronization and export. This prevents inherited background file
descriptors from delaying the terminal workflow receipt. The later
`completed_at`/`exit_code` pair remains the final controller result.

## Budget Enforcement

New clusters enforce the cluster AWS Budget by default. `dyec create` creates or
checks an AWS Budget whose name is the cluster name, renders
`aws-parallelcluster-project` as the cluster name, and renders
`aws-parallelcluster-enforce-budget=true` unless
`--disable-budget-enforcement` is explicitly set.

The staged Slurm wrapper always requires `sbatch --comment <cost-center>`.
That cost center must be active in the global DynamoDB registry, allowed for
the submitting user or group, and not have reached its optional `active_until`.
`active_until` is an exclusive UTC boundary stored exactly as
`YYYY-MM-DDTHH:MM:SSZ`; omitting it keeps the cost center active until it is
explicitly disabled. Reaching the boundary automatically ends eligibility for
that cost center without requiring its registry row to be disabled and without
blocking unrelated cost centers. Global readiness retains expired rows as
nonblocking lifecycle details on a passing check. Month rollover does not affect admission.
Monthly cap, spend, freshness, and usage rows remain available as reporting
telemetry, but missing, stale, or at-cap monthly data does not block a
submission. When a job is blocked, the wrapper prints the cluster budget
monitor URL and the cost-center report URL.

Create a time-bounded cost center or remove an existing time boundary with:

```bash
dyec cost-centers create RnD \
  --monthly-cap-usd 200 \
  --allowed-user ubuntu \
  --active-until 2026-12-31T23:59:59Z
dyec cost-centers edit RnD --clear-active-until
```

Disabling budget enforcement skips only the cluster AWS Budget lookup. It does
not remove the `--comment <cost-center>` requirement or cost-center validation.

To change the cluster AWS Budget, first record the exact current cap and obtain
the required budget-change approvals. Validate the intended old/new cap pair
without mutating AWS:

```bash
dyec aws budget set-limit "$CLUSTER" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --expected-current-monthly-cap-usd 200 \
  --monthly-cap-usd 300 \
  --dry-run
```

After approval, repeat the same command without `--dry-run`. The command fails
before mutation if the current limit changed or the budget is not a fixed
monthly USD cost budget, and it fails if the post-update readback does not
match. An equal old/new cap is an idempotent no-op. This command changes only
the AWS Budget; cost-center caps remain a separate control.

## Create-Time Spot Bid Safeguards

`dyec create` caps generated ParallelCluster `SpotPrice` values with:

```text
min(reference_median_spot_price * spot_cost_limit_pct, global_spot_max_cost)
```

The default flags are `--global-spot-max-cost 9.99`,
`--spot-cost-limit-pct 1.7`, and
`--write-spot-pricing-warn-threshold 6.00`. Values outside the hard limits fail
before cluster submission. Every resource uses its own median reference price,
including i384 resources.

Each create writes `config/<cluster>_spot_price_summary_<run_id>.json` and the
state record stores the summary path plus partition rows for local reporting.
Compute nodes append runtime high-price JSONL rows to
`/fsx/scratch/spot_price_warn_exception_messages.log`, or
`/var/log/daylily/spot_price_warn_exception_messages.log` for DRAGEN no-FSx
mode.

## Hourly Cost-Center Accounting

Cost-center spend is computed from hourly CUR EC2 instance cost joined to
Slurm accounting job intervals. Allocation is time-weighted within each
instance-hour. If one cost center runs for the full hour and a second cost
center overlaps for 10 minutes, the first receives 50 minutes solo plus half of
the 10-minute overlap, or 55/60 of that instance-hour. The second receives
5/60. Time with no jobs is assigned to the reserved system cost center `idle`.

For a dedicated cluster whose cost-center name exactly matches the cluster
name, refresh a stale usage snapshot from authoritative CUR rows with:

```bash
dyec --json cost-centers refresh-usage "$CLUSTER_NAME" \
  --cluster "$CLUSTER_NAME" \
  --month "$(date -u +%Y-%m)" \
  --profile "$AWS_PROFILE" \
  --dry-run
```

Repeat without `--dry-run` only after checking the row count, amount, and
latest processed hour. The command fails closed for shared clusters; those
require Slurm job-time allocation.

Before live CUR-backed allocation can run in a new AWS account, create or
validate the billing source:

```bash
dyec --json cost-centers ensure-cur-export --profile "$AWS_PROFILE"
```

The command creates or validates the dedicated S3 delivery bucket, BCM Data
Export, Glue database/table, and current billing-period Athena partition. It is
configured for the CUR 2.0 normalized resource tag key
`user_parallelcluster_cluster_name`, which corresponds to EC2 tag
`parallelcluster:cluster-name`. It is
explicit about drift: a same-name export with a different definition requires
`--update-existing-export`, and a same-name Glue table not marked
`dayec:managed=true` requires `--adopt-glue-table`. New exports may have no
queryable rows until AWS Data Exports refreshes the current CUR partition.

For repo-native work that is not a catalog workflow command, clone the pinned repository on the headnode and then follow that repository's documented launch path:

```bash
day-clone --list
day-clone --repository daylily-omics-analysis --destination "$ANALYSIS_ID" --git-tag 15.0.15 --executing-entity "$EXECUTING_ENTITY"
day-clone -d "$ANALYSIS_ID" -t 15.0.15
```

`-t` is the short form of `--git-tag`; `-d` is required and is the short form of `--destination`. The clone target is `/fsx/analysis_results/<executing_entity>/<analysis_id>/<relative_path>`.

## Monitor

```bash
dyec --json workflow status \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --session <session>

dyec workflow logs \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --session <session> \
  --stream snakemake \
  --lines 100
```

The status response derives `RUNNING`, `SUCCEEDED`, `FAILED`, or `UNKNOWN`
from the exact controller target, matching run receipt, controller/descendant
open file descriptors, Snakemake progress, and current Slurm evidence.
`CONFIGURING` and `RUNNING` allocations are healthy ongoing states; an empty
queue is not success. Only the current matching DYEC receipt supplies a
terminal RC, and generic `ERROR` text or an old pane RC marker is not terminal
evidence.

For a manually restarted recovery controller, replace the run-state selector
with explicit attribution:

```bash
dyec --json workflow status \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME" \
  --repo-path /fsx/analysis_results/<owner>/<analysis-id>/daylily-omics-analysis \
  --controller-pid <pid> \
  --session <exact-tmux-session>
```

Add `--snakemake-log <exact-path>` only when the live PID cannot expose exactly
one log through `/proc`. DYEC refuses missing or ambiguous attribution and does
not guess the newest file. A manual run without a DYEC receipt cannot be called
successful and has no attributable terminal RC.

Inside the headnode shell:

```bash
tmux ls
tmux attach -t <session>
squeue
```

## Export Results

Export is a separate output DRA flow. It does not write back through the reference DRA or run-input DRA. It attaches a temporary DRA directly to one completed analysis directory.

From the operator machine:

```bash
dyec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --source-path "/fsx/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID" \
  --destination-s3-uri "$EXPORT_S3_URI" \
  --output-dir "$EXPORT_DIR"
```

Verify:

```bash
cat "$EXPORT_DIR/fsx_export.yaml"
```

Success means `status: success`, `task_lifecycle: SUCCEEDED`, `detached: true`,
`delete_data_in_file_system: false`, a completed FSx export task id, and an
explicit `fsx_root` to `s3_root` mapping. The destination must be an explicit S3
URI ending in `<executing_entity>/<analysis_id>/`.

`dyec export` is provider-neutral. It writes the explicit FSx-to-S3 receipt and
does not accept metadata-service URL, token, registration, or external identity
options.

Use the command catalog's `test_data_profile.source_mount_mode` before launch:
`default_mounted` data should already be visible through the cluster's default
reference/control-data DRAs; `run_dra_required` data must have the complete
`run_context` `runs.tsv` schema, including `RUNID`, `RUN_DIR`, `SOURCE_S3_URI`,
and `MOUNT_ID`, plus a verified `/fsx/run_dir_mounts/<MOUNT_ID>/` projection;
`none` commands should not receive sample or run-source inputs.

## Delete

```bash
dyec delete --dry-run \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"

dyec delete \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

Use `--yes` only after the exact delete has already been approved.
