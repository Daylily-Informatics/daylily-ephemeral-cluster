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
  --global-spot-max-cost 7.50 \
  --spot-cost-limit-pct 1.2 \
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
- `--create-slurm-accounting-db`
- `--scan-slurm-accounting-db`
- `--slurm-accounting-stack-name <name>`
- `--global-spot-max-cost <usd>`: default `7.50`; hard fails if `<= 0` or `> 10.00`
- `--spot-cost-limit-pct <multiplier>`: default `1.2`; hard fails if `< 1.0` or `> 1.4`
- `--write-spot-pricing-warn-threshold <usd>`: default `6.00`; hard fails if `<= 0`

Spot bid policy is deterministic and capped. For each compute resource, DYEC
looks up the current Linux/UNIX spot prices for the configured instance types in
the selected AZ, calculates the reference median, and writes the PCluster
`SpotPrice` as:

```text
min(reference_median_spot_price * spot_cost_limit_pct, global_spot_max_cost)
```

The old median-plus-dollar bump behavior and `--bump-price` helper flag are
removed. i384 partitions use the matching i192 reference resource median for
the bid calculation; missing i192 reference data is a hard failure before
cluster submission.

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
day-clone --repository daylily-omics-analysis --destination "$ANALYSIS_ID" --git-tag 10.0.69 --executing-entity "$EXECUTING_ENTITY"
day-clone -d "$ANALYSIS_ID" -t 10.0.69
```

`-t` is the short form of `--git-tag`; `-d` is the short form of `--destination` and is required for every clone. If `--repository` is omitted, `day-clone` uses `default_repository` from `daylily_pipeline_command_catalog.yaml`. If `--git-tag`/`-t` is omitted, it uses the selected repository row's `default_ref`. Missing catalog rows, missing URLs, missing cluster identity, unsafe path segments, or an existing destination directory are hard failures.

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
dyec create --scan-slurm-accounting-db --profile "$AWS_PROFILE" --region-az "$REGION_AZ" --config "$DAY_EX_CFG"
```

The helper manages external Slurm accounting database infrastructure when configured. On a running cluster, `sacct --version` may succeed while job-account queries fail if Slurm accounting storage is disabled. Treat that as an infrastructure/config state, not as a reason to restart Slurm or modify jobs.

## Delete

```bash
dyec delete --dry-run --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
```

Live delete is destructive. Use non-dry-run delete only after a separate explicit approval for the exact cluster.

## AWS Validation

```bash
dyec aws validate permissions --profile "$AWS_PROFILE" --region-az "$REGION_AZ" --gap-analysis aws_permissions_gap.md
dyec aws validate quotas --profile "$AWS_PROFILE" --region-az "$REGION_AZ" --config "$DAY_EX_CFG" --gap-analysis aws_quota_gap.md
dyec --json aws validate all --profile "$AWS_PROFILE" --region-az "$REGION_AZ" --config "$DAY_EX_CFG"
```

Validation is read-only.

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
