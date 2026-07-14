# CLI Reference

This reference is grounded in the current `dyec` command surface. `daylily-ec` may exist as a compatibility alias, but new docs, ledgers, and runbooks should use `dyec`.

## Global Options

```bash
dyec --help
dyec --json version
```

Global options:

- `--json`: emit machine-readable JSON where supported
- `--dry-run`: plan the command without persistent changes when the command supports it
- `--no-color`: disable ANSI styling
- `--debug`: enable debug diagnostics

## Root Commands

Current root commands:

- `version`
- `info`
- `create`
- `preflight`
- `drift`
- `cluster-info`
- `export`
- `delete`
- `resources-dir`
- `env`
- `runtime`
- `pricing`
- `aws`
- `slurm-accounting`
- `cluster`
- `headnode`
- `samples`
- `workflow`
- `repositories`
- `exports`
- `mounts`
- `mount`
- `state`

## Allowed Command Model

DYEC commands should either inspect state, create an explicit cluster resource from config, launch a documented repository command, attach a documented input mount, export one completed analysis directory, or delete a named cluster after approval. Do not use DYEC docs or examples to smuggle in guessed buckets, guessed references, root SSH, PEM files, direct scheduler intervention, or legacy helper paths.

Manual DayOA workflow commands on a headnode must use the DayOA wrapper sequence:

```bash
source dyoainit
dy-a slurm hg38_broad
dy-r <targets> <flags>
```

DYEC may launch DayOA through `dyec samples run` or `dyec workflow launch`; agents should not invoke `snakemake` directly for DayOA work.

## Create And Preflight

```bash
dyec preflight \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG"

dyec create \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG" \
  --global-spot-max-cost 9.99 \
  --spot-cost-limit-pct 1.7 \
  --write-spot-pricing-warn-threshold 6.00
```

`create` runs preflight, renders the ParallelCluster YAML, creates the cluster, waits for the headnode, configures DayEC on the headnode over SSM, and validates the supported `ubuntu` login shell. In non-interactive automation, storage URIs and identity values must be explicit in config or flags.

Important options:

- `--region-az`
- `--profile`
- `--config`
- `--pass-on-warn`
- `--debug`
- `--non-interactive`
- `--budget-project <project>`: retired; cluster budgets are named by cluster name
- `--disable-budget-enforcement`: render the cluster budget-enforcement tag as `skip`
- `--global-spot-max-cost <usd>`: default and hard maximum `9.99`; hard fails if `<= 0` or `> 9.99`
- `--spot-cost-limit-pct <multiplier>`: default `1.7`; hard fails if `< 1.0` or `> 2.2`
- `--write-spot-pricing-warn-threshold <usd>`: default `6.00`; hard fails if `<= 0`

Spot bid policy is deterministic and capped. For each compute resource, DYEC
looks up the current Linux/UNIX spot prices for the configured instance types in
the selected AZ, calculates the reference median, and writes the PCluster
`SpotPrice` as:

```text
min(reference_median_spot_price * spot_cost_limit_pct, global_spot_max_cost)
```

The old median-plus-dollar bump behavior and `--bump-price` helper flag are
removed. Each resource uses its own median spot price; i384 resources no
longer borrow i192 reference pricing.

Slurm accounting is a regional singleton. Discovery considers every DayEC
accounting stack in the AWS region, regardless of AZ, explicit stack name, or
validation-style name. Legacy component-tagged stacks without the newer region
tag also count, and discovery fails if more than one exists. The singleton uses
a private address and must be in the selected cluster VPC. If the selected VPC
differs, DYEC fails before cluster or database creation; it never creates a
second accounting database as a fallback.

Each create run writes an Ursa-readable summary JSON:

```text
config/<cluster>_spot_price_summary_<run_id>.json
```

The same partition summary is printed as a table after spot prices are applied.
The state record stores `spot_price_summary_path` and `spot_price_partitions`
so Ursa can render the values in its cluster card view.

Compute nodes also write normal per-node spot lifecycle logs. When a
`ComputeFleet` node observes a runtime spot price above
`--write-spot-pricing-warn-threshold`, it appends a JSONL row to the special
Ursa exception log beside the per-node spot logs:

```text
/fsx/scratch/spot_price_warn_exception_messages.log
/var/log/daylily/spot_price_warn_exception_messages.log   # DRAGEN no-FSx mode
```

Each warning row uses schema `dyec.spot_price_warn_exception.v1` and includes
timestamp, event, cluster, partition, compute resource, hostname, instance id,
region/AZ, instance type, observed spot price, warning threshold, and source
host log path. The warning log is intentionally separate from
`dyec pricing spot-logs` lifecycle cost rows.

Budget enforcement is on by default for new clusters. `dyec create` ensures an
AWS Budget named by the cluster name, renders `aws-parallelcluster-project` as
the cluster name, and stages the `sbatch` wrapper used by Slurm. The wrapper
requires every submission to include `--comment <cost-center>`. The cost center
must be active in the global DynamoDB registry, authorized for the submitting
user or group, have a fresh usage snapshot, and be under its monthly cap. Failed
checks point users to the Ursa cluster budget monitor and cost-center report.

## Cost Centers

```bash
dyec cost-centers ensure-registry --profile "$AWS_PROFILE"
dyec cost-centers create project-a --monthly-cap-usd 200 --allowed-user ubuntu
dyec cost-centers edit project-a --monthly-cap-usd 300
dyec cost-centers disable project-a --reason "closed"
dyec --json cost-centers show project-a
dyec --json cost-centers list --status active
dyec --json cost-centers usage project-a --month 2026-07
dyec --json cost-centers ensure-cur-export --profile "$AWS_PROFILE"
```

The registry defaults to DynamoDB tables `dayec-cost-centers` and
`dayec-cost-center-usage` in `us-west-2`. The reserved `idle` cost center is
system-owned and cannot be used in Slurm submissions.

`ensure-cur-export` creates or validates the explicit CUR 2.0 billing source
used by hourly cost-center accounting: a dedicated S3 bucket, the required BCM
Data Exports bucket policy, an hourly/resource CUR 2.0 Data Export with
Parquet/Parquet overwrite delivery, a Glue database/table, and the current
monthly Athena partition. The default CUR 2.0 cluster tag key is
`user_parallelcluster_cluster_name`, which is the normalized Data Exports map
key for EC2 tag `parallelcluster:cluster-name`. Existing same-name exports with different definitions
fail unless `--update-existing-export` is passed. Existing same-name Glue tables
that are not marked `dayec:managed=true` fail unless `--adopt-glue-table` is
passed. New Data Exports can take until AWS refreshes billing data before CUR
files are available to Athena.

## Cluster

```bash
dyec cluster list --profile "$AWS_PROFILE" --region "$REGION" --verbose
dyec --json cluster describe --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec cluster wait --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec --json cluster tags --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec cluster tags --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME" \
  --set daylily-accept-jobs=false \
  --set ursa-drain-reason=maintenance
```

`cluster-info` remains available, but `cluster list` and `cluster describe` are the preferred current inspection surfaces.

`cluster tags` reads and edits the CloudFormation stack tags returned by
ParallelCluster `describe-cluster` as `cloudformationStackArn`. Use repeated
`--set KEY=VALUE` to add or replace tags and repeated `--delete KEY` to remove
existing tags. With no `--set` or `--delete`, it lists the current tags. Ursa
can use a conventional tag such as `daylily-accept-jobs=true|false` to decide
whether a cluster is eligible for new jobs; DYEC only records the tag and does
not change Slurm state.

## Headnode

```bash
dyec headnode connect --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec headnode configure --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec headnode info --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec headnode jobs --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
```

Supported headnode command payloads run as `ubuntu`. Interactive sessions use AWS Session Manager and must land in `/home/ubuntu` in a bash login shell.

Use `--cluster` for DYEC headnode commands. `--cluster-name` is for command surfaces such as `pcluster` that require that spelling. After `headnode configure`, verify workflow-lock support with `dyec analysis --help` on the headnode; current DayOA `dy-r` locking expects `analysis visit`, `analysis guard`, and `analysis lock`.

## Samples

`samples stage` translates `analysis_samples.tsv` into workflow-ready staged manifests:

```bash
dyec samples stage "$ANALYSIS_SAMPLES" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --reference-s3-uri "$REF_S3_URI" \
  --control-data-s3-uri "$CONTROL_DATA_S3_URI" \
  --stage-s3-uri "$STAGE_S3_URI" \
  --config-dir "$STAGE_CFG_DIR"
```

`samples run` stages the manifest, validates it against a catalog command, and launches the workflow:

Set `EXPORT_S3_ROOT` to the S3 prefix that should receive auto-exported analysis directories; DYEC appends `<cluster>/<analysis-id>/`.

```bash
dyec samples run "$ANALYSIS_SAMPLES" \
  --command-id illumina_snv_alignstats \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --reference-s3-uri "$REF_S3_URI" \
  --control-data-s3-uri "$CONTROL_DATA_S3_URI" \
  --stage-s3-uri "$STAGE_S3_URI" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$EXECUTING_ENTITY" \
  --export-destination-s3-uri "$EXPORT_S3_ROOT" \
  --export-trigger on-success \
  --dry-run
```

Important options include `--command-id`, `--analysis-id`, `--executing-entity`, `--export-destination-s3-uri`, `--export-trigger`, `--artifact-registration-command-id`, `--dewey-url`, `--dewey-token-env`, `--git-tag`, and `--project`. For `samples run` and `workflow launch`, `--export-destination-s3-uri` may be a full destination or an export root; export roots are expanded to `<root>/<cluster>/<analysis-id>/`.

`--project <project>` is passed through to DayOA as `dyoainit --project <project>`, which sets `DAY_PROJECT`; DayOA's Slurm profile submits `sbatch ... --comment "$DAY_PROJECT"`. The value is a cost-center string, not the cluster AWS Budget name.

Collect benchmark summaries from a completed DayOA checkout on the headnode:

```bash
dyec --json workflow collect-benchmarks \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --analysis-root "/fsx/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID" \
  --genome-build hg38_broad
```

The command runs from `<analysis-root>/daylily-omics-analysis`, initializes DayOA with
`source dyoainit` and `dy-a local <genome-build>`, then runs
`bash bin/util/benchmarks/collect_day_benchmark_data.sh <genome-build>`.
Supported builds are `hg38`, `hg38_broad`, and `b37`. The expected output is
`results/day/<genome-build>/reports/benchmarks_summary.tsv`.

Run command-catalog validation with explicit selectors:

```bash
dyec tests command-catalog \
  --cluster "$CLUSTER_NAME" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --command-codes dyec-released-core \
  --evidence-s3-uri "s3://<evidence-root>/" \
  --dry-run
```

`dyec-released-core` selects the released core validation set.
`dyec-released-all` selects all released non-research catalog commands. BCL
Convert commands are `research` type and are excluded from `dyec-released-all`;
launch them only by explicit command id when research validation is intended.

Summarize command-catalog benchmark evidence and update the version-keyed
performance comparator profile:

```bash
dyec --json tests command-catalog-performance \
  --benchmark-rows docs/plans/<run>_benchmark_resource_review/benchmark_rows.tsv \
  --rule-summary docs/plans/<run>_benchmark_resource_review/rule_resource_summary.tsv \
  --slurm-jobs docs/plans/<run>_benchmark_resource_review/slurm_jobs_with_packing.tsv \
  --catalog-config config/daylily_pipeline_command_catalog.yaml \
  --dyec-version 10.0.103 \
  --dayoa-version 10.0.65 \
  --cluster cmdcat-103-all-20260707 \
  --run-id 20260707T144453Z \
  --include-all-catalog-commands \
  --dev-command-id illumina_bclconvert \
  --dev-command-id illumina_run_qc_bclconvert \
  --dev-command-id inflection-bjuice-product-v0.1 \
  --output-dir docs/plans/<run>_benchmark_resource_review \
  --history-json config/command_catalog_performance_history.json
```

The command writes `command_catalog_performance_summary.tsv`,
`command_catalog_performance_profile.json`, and updates
`config/command_catalog_performance_history.json`. The history file is keyed by
DYEC version under `dyec_versions`, so later runs can compare wall time,
allocated vCPU-hours, observed CPU-hours, cost, peak RSS, and I/O against the
latest prior profile.

## Run Mounts

Run mounts are FSx Data Repository Associations from selected S3 run prefixes to `/run_dir_mounts/<mount_id>/`, visible on the headnode as `/fsx/run_dir_mounts/<mount_id>/`. The mount id defaults to the final folder in the S3 URI unless explicitly supplied.

```bash
dyec --json mounts create "s3://<sequencing-run-bucket>/<run-prefix>/" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --platform ILMN \
  --read-only \
  --batch-import-metadata-on-create \
  --auto-import NEW,CHANGED \
  --wait \
  --timeout-seconds 5400

dyec --json mounts list \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"

dyec --json mounts describe \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --mount-id <mount_id>

dyec --json mounts verify \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --mount-id <mount_id>
```

Default behavior is read-oriented:

- no AutoExport policy
- no source S3 writeback
- no deletion of S3 objects on detach
- overlapping active FSx paths or S3 prefixes are rejected

Do not treat run-mount creation as failed only because it has been in `CREATING` for a few minutes. Large dynamic FSx associations can legitimately take more than 40 minutes; use an explicit timeout comfortably above that when waiting.

## Workflow

Sample-manifest launch with staged manifests:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --stage-dir "/fsx/staging/staged_external_sequencing_data/remote_stage_<timestamp>" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$EXECUTING_ENTITY" \
  --repository daylily-omics-analysis \
  --git-tag 10.0.69 \
  --genome hg38_broad \
  --jobs 20 \
  --target produce_alignstats
```

Run-context launch with an explicit `runs.tsv`:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --run-context-file ./runs.tsv \
  --analysis-id run-qc \
  --executing-entity "$EXECUTING_ENTITY" \
  --repository daylily-omics-analysis \
  --git-tag 10.0.69 \
  --genome hg38_broad \
  --jobs 5 \
  --target produce_illumina_run_qc \
  --snakemake-extra "--config run_context_file=config/runs.tsv"
```

`workflow launch` requires `--analysis-id`; `--executing-entity` should be a stable safe path segment. The headnode checkout root is `/fsx/analysis_results/<executing_entity>/<analysis_id>/`, and the repository checkout sits below it. Use `--project <project>` to override the DayOA `DAY_PROJECT` value and therefore the Slurm `--comment` cost-center string for this launch.

Auto-export options:

- `--export-destination-s3-uri`: full S3 destination prefix or export root; export roots are expanded to `<root>/<cluster>/<analysis-id>/`
- `--export-trigger`: one of `none`, `on-success`, `on-fail`, or `all`; default `none`
- `--delete-on-export-success`: deletes only the FSx analysis directory after a successful requested export
- `--artifact-registration-command-id`: command-catalog policy to apply after successful export
- `--dewey-url`: Dewey base URL for DYEC registration requests
- `--dewey-token-env`: environment variable containing the Dewey bearer token on the headnode

Inspect:

```bash
dyec --json workflow status --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME" --session <session>
dyec workflow logs --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME" --session <session> --lines 100
```

## Repository Catalog

```bash
dyec --json repositories commands
dyec repositories commands --config config/daylily_pipeline_command_catalog.yaml
dyec repositories commands --command-id illumina_snv_alignstats
```

The catalog is version 2. The current DayOA repository default and DayOA command pins are `10.0.69`; `daylily-sarek` is present as a Nextflow/nf-core Sarek repository entry.

Headnode repository cloning uses the same catalog:

```bash
day-clone --list
day-clone --check-auth --repository daylily-omics-analysis --git-tag 10.0.69
day-clone --repository daylily-omics-analysis --destination "$ANALYSIS_ID" --git-tag 10.0.69 --executing-entity "$EXECUTING_ENTITY"
day-clone -d "$ANALYSIS_ID" -t 10.0.69
```

`-t` is the short form of `--git-tag`; `-d` is the short form of `--destination` and is required for every clone. If `--repository` is omitted, `day-clone` uses `default_repository` from `daylily_pipeline_command_catalog.yaml`. If `--git-tag`/`-t` is omitted, it uses the selected repository row's `default_ref`. Missing catalog rows, missing URLs, missing cluster identity, unsafe path segments, or an existing destination directory are hard failures.

Private DayOA access uses the catalog's explicit SSH/deploy-key contract. `dyec create`
requires `dayoa_deploy_key_secret_arn` and `dayoa_deploy_key_policy_arn` config values.
For an older cluster whose headnode lacks the ARN reference, rerun
`dyec headnode configure ... --dayoa-deploy-key-secret-arn <exact-secret-arn>` after
attaching the shared headnode-only `DayECHeadnodeGitHubClone` policy. That policy can
read explicit secrets in the `dayec/github-deploy-keys/lsmc-bio*` namespace but cannot
list secrets and is never attached to compute roles. `--check-auth` verifies the
configured repository/ref without creating an analysis directory.

Command classes:

- `utility`: no sample or run source data
- `sample_analysis`: uses `analysis_samples.tsv`, staging, `samples.tsv`, and `units.tsv`
- `run_analysis`: uses `runs.tsv` and requires a run mount

## Export

Root export runs the explicit output-DRA workflow on one completed analysis directory:

```bash
dyec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --source-path "/fsx/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID" \
  --destination-s3-uri "$EXPORT_S3_URI" \
  --output-dir "$EXPORT_DIR"
```

Required:

- `--cluster` or `--fsx-file-system-id`
- `--source-path`
- `--destination-s3-uri`
- `--region`
- `--output-dir`

Optional artifact registration:

- `--artifact-registration-command-id`
- `--repository-catalog`
- `--dewey-url`
- `--dewey-token-env`

The source path must be `/fsx/analysis_results/<executing_entity>/<analysis_id>` or `/analysis_results/<executing_entity>/<analysis_id>`. Direct `dyec export` destinations must be explicit S3 URIs ending in `<executing_entity>/<analysis_id>/` or, when `--cluster` is supplied, `<cluster>/<analysis_id>/`. Run mounts, reference data, nested paths, old export staging paths, unsafe path segments, and non-empty destination prefixes are rejected.

Lower-level helpers:

```bash
dyec --json exports attach --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME" --source-path "/fsx/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID" --destination-s3-uri "$EXPORT_S3_URI"
dyec --json exports run --profile "$AWS_PROFILE" --region "$REGION" --source-path "/fsx/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID" --destination-s3-uri "$EXPORT_S3_URI" --fsx-file-system-id "$FSX_FILE_SYSTEM_ID"
dyec --json exports detach --profile "$AWS_PROFILE" --region "$REGION" --association-id "$EXPORT_DRA_ID"
```

## Slurm Accounting

```bash
dyec slurm-accounting ensure --help
dyec slurm-accounting attach --help
```

New clusters omit Slurm accounting by default. This keeps a missing or
cross-VPC accounting service from preventing a usable ParallelCluster from
being created. A cluster without accounting can run jobs, but historical
`sacct` persistence is unavailable.

AWS ParallelCluster requires the compute fleet to be stopped before
`Scheduling.SlurmSettings.Database` can be updated. After confirming that no
jobs must remain running, stop it explicitly, validate the attachment, then
submit it:

```bash
pcluster update-compute-fleet \
  --cluster-name "$CLUSTER_NAME" \
  --region "$REGION" \
  --status STOP_REQUESTED

pcluster describe-compute-fleet \
  --cluster-name "$CLUSTER_NAME" \
  --region "$REGION"

dyec slurm-accounting attach \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --dry-run

dyec slurm-accounting attach \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

The attach command uses only an existing compatible accounting service. It
does not create a second stack, stop the compute fleet, force an update, alter
the original cluster YAML, or print database connection or credential values.
It writes a separate update YAML and requires a successful
`pcluster update-cluster --dryrun true` before submitting the real update. If
the service is missing or in an incompatible VPC, attachment fails and the
already-created cluster remains intact. Restart the compute fleet only after
the cluster update reaches its successful terminal state.

## Delete

```bash
dyec delete --dry-run --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
```

Live delete is destructive. Use non-dry-run delete only after a separate explicit approval for the exact cluster.

## AWS Validation

```bash
dyec aws validate permissions --profile "$AWS_PROFILE" --region-az "$REGION_AZ" --config "$DAY_EX_CFG" --gap-analysis aws_permissions_gap.md
dyec aws validate quotas --profile "$AWS_PROFILE" --region-az "$REGION_AZ" --config "$DAY_EX_CFG" --gap-analysis aws_quota_gap.md
dyec aws validate all --profile "$AWS_PROFILE" --region-az "$REGION_AZ" --config "$DAY_EX_CFG" --gap-analysis aws_permissions_quotas.md
dyec --json aws validate all --profile "$AWS_PROFILE" --region-az "$REGION_AZ" --config "$DAY_EX_CFG"
```

`--profile` and `--region-az` are required; the implicit `default` profile is
rejected. Pass the exact config so config-selected headnode, DRAGEN, budget,
CUR, and optional Slurm-accounting requirements are included. The modes are:

- `permissions`: operator IAM simulation, selected headnode runtime-policy
  inspection, SSM/DRAGEN policy checks, and live budget, cost-center, CUR,
  Glue, Athena, and optional Slurm-accounting readiness
- `quotas`: rendered cluster demand, existing infrastructure headroom, and
  current cost-control/accounting count limits
- `all`: the complete permissions, readiness, and quota check set

The expanded operator action groups cover AWS Budgets and billing views;
Cost Explorer/tag reports; the two global DynamoDB cost-center tables; CUR 2.0
BCM Data Exports and its required CUR/S3 permissions; Glue catalog management;
Athena allocation queries; optional Slurm-accounting CloudFormation, EC2,
Secrets Manager, IAM/pass-role, and tagging operations; and DRAGEN secret
metadata/policy access. SNS permissions use the configured
`daylily-<cluster_name>-heartbeat` topic ARN rather than a generic topic, and
EC2 quota reads include `ec2:DescribeSpotInstanceRequests` so open Spot demand
is not omitted. `iam.runtime_cost_policy` separately inspects the exact
managed policy selected by `iam_policy_arn` for the headnode. It requires
`budgets:ViewBudget`, `billing:GetBillingViewData`, and `dynamodb:GetItem` on
both named cost-center tables. `iam.dragen_license_secret_policy` requires an
exact-secret policy containing only `secretsmanager:DescribeSecret` and
`secretsmanager:GetSecretValue`; validation never reads the secret value.
Slurm and DRAGEN operator permissions are intentionally covered by the shared
service action groups; their config-specific results are
`slurm_accounting.readiness`, `quota.slurm_accounting_shape`, and
`iam.dragen_license_secret_policy`, not separate simulation-group IDs.
IAM cannot simulate an account-root ARN. Root-profile simulation rows are
`WARN`/`UNKNOWN` and name the unverified SCP, RCP, and resource-policy
boundaries; use the actual non-root operator role or user for simulated
PASS/FAIL decisions.

Read-only live readiness checks are reported independently:

- `budget.readiness` for global/cluster existence, configured limits, actual
  spend, monthly/USD shape, exact cluster-tag filters, thresholds, and the
  configured subscriber
- `cost_centers.registry_readiness` for table/idle contracts plus fresh usage
  below every active cost center's cap
- `cost_control.cur_export_readiness` for the exact bucket policy and export
  destination/configuration, `HEALTHY` state, latest `DELIVERY_SUCCESS`, and
  required schema
- `cost_control.cur_catalog_readiness` for the exact managed table schema and
  table/current-month-partition S3 locations
- `cost_control.athena_readiness`
- `slurm_accounting.readiness`, which records accounting as disabled or checks
  the explicit baseline-VPC/stack contract, running EC2 host, client security
  group, and secret metadata when enabled

The explicit target AZ selects the cluster region. Current cost-center checks
use the fixed `us-west-2` home-region contract, while CUR 2.0, the CUR S3
bucket, Glue, and Athena use the fixed `us-east-1` billing-region contract; no
alternate-region discovery or substitution is performed.

The quota report evaluates current use plus incremental demand for network,
gp3, FSx, and EC2 capacity. Rendered vCPUs are separated into Standard, X, F,
G/VT, P, Inf, Trn, DL, HPC, and High Memory quota families; mixed compute
resources must fit every family they permit. Current Spot consumption includes
both running instances and open, unfulfilled requests. FSx checks use the exact
Scratch, Persistent_1, Persistent_2, or Intelligent-Tiering quota names; the
Intelligent-Tiering path also checks SSD read-cache and throughput capacity. It
also adds:

- `quota.budget_count`: current budgets plus any missing global/cluster budgets
- `quota.dynamodb_table_count`: table quota plus missing registry/usage tables
- `quota.s3_bucket_count`: general-purpose bucket quota plus the CUR bucket
- `quota.cur2_export_count`: current CUR 2.0 exports plus the named DayEC export
- `quota.athena_active_dml`: current queued/running workgroup queries plus one
  allocation query against the regional applied quota; all workgroups are
  enumerated and active DDL is excluded
- `quota.cloudformation_stack_count`: accounting-stack headroom, conditional on
  `slurm_accounting_enabled`
- `quota.slurm_accounting_shape`: optional accounting instance demand; when
  enabled its On-Demand vCPUs and 20 GiB gp3 volume are added to quota math,
  and the report records two security groups, one network interface, one
  secret, one IAM role/profile pair, and one CloudFormation stack as
  incremental accounting demand
- `quota.slurm_accounting.*`: current-use-plus-demand headroom for accounting
  security groups, network interfaces, Secrets Manager secrets, IAM roles, and
  IAM instance profiles; IAM counts/ceilings use `iam:GetAccountSummary`

Validation is read-only. It can simulate create/update/delete permissions, but
it performs no AWS mutation and starts no Athena query, SSM command/session, or
cluster operation. `--gap-analysis` only writes the requested local Markdown
report. The report is complete rather than gap-only: it starts with overall
`SATISFIED` or `NOT SATISFIED`, maps PASS to `SATISFIED`, unverifiable WARN to
`UNKNOWN`, and known missing/stale/drifted FAIL to `NOT SATISFIED`, then
includes every check in a results matrix, admin
follow-up with exact details, and the full set of passing checks. Any WARN or
FAIL makes the overall result `NOT SATISFIED` and returns a validation-failure
exit status. JSON mode emits the same checks and PASS/WARN/FAIL summary.

## Runtime, Environment, State, And Pricing

```bash
dyec runtime status
dyec runtime check
dyec runtime explain
dyec env status
dyec resources-dir
dyec --json state list
dyec state show --cluster "$CLUSTER_NAME"
dyec pricing snapshot --profile "$AWS_PROFILE" --region "$REGION"
```
