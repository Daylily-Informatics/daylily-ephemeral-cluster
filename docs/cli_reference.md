# CLI Reference

This reference is grounded in the current `dyec` / `daylily-ec` command surface. Both executable names use the same entrypoint.

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
  --config "$DAY_EX_CFG"
```

`create` runs preflight, renders the ParallelCluster YAML, creates the cluster, waits for the headnode, configures DayEC on the headnode over SSM, and validates the supported `ubuntu` login shell. In non-interactive automation, storage URIs and identity values must be explicit in config or flags.

Important options:

- `--region-az`
- `--profile`
- `--config`
- `--pass-on-warn`
- `--debug`
- `--non-interactive`
- `--create-slurm-accounting-db`
- `--scan-slurm-accounting-db`

## Cluster

```bash
dyec cluster list --profile "$AWS_PROFILE" --region "$REGION" --verbose
dyec --json cluster describe --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec cluster wait --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
```

`cluster-info` remains available, but `cluster list` and `cluster describe` are the preferred current inspection surfaces.

## Headnode

```bash
dyec headnode connect --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec headnode configure --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec headnode info --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec headnode jobs --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
```

Supported headnode command payloads run as `ubuntu`. Interactive sessions use AWS Session Manager and must land in `/home/ubuntu` in a bash login shell.

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
  --export-destination-s3-uri "$EXPORT_S3_URI" \
  --export-trigger on-success \
  --dry-run
```

Important options include `--command-id`, `--analysis-id`, `--executing-entity`, `--export-destination-s3-uri`, `--export-trigger`, `--artifact-registration-command-id`, `--dewey-url`, `--dewey-token-env`, and `--git-tag`.

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
  --timeout-seconds 3600

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

Do not treat run-mount creation as failed only because it has been in `CREATING` for a few minutes. Large dynamic FSx associations can legitimately take around 30 minutes; use an explicit timeout comfortably above that when waiting.

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
  --git-tag 2.0.41 \
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
  --git-tag 2.0.41 \
  --genome hg38_broad \
  --jobs 5 \
  --target produce_illumina_run_qc \
  --snakemake-extra "--config run_context_file=config/runs.tsv"
```

`workflow launch` requires `--analysis-id`; `--executing-entity` should be a stable safe path segment. The headnode checkout root is `/fsx/analysis_results/<executing_entity>/<analysis_id>/`, and the repository checkout sits below it.

Auto-export options:

- `--export-destination-s3-uri`: full S3 destination prefix ending in `<executing_entity>/<analysis_id>/`
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

The catalog is version 2. The current DayOA repository default and DayOA command pins are `2.0.41`; `daylily-sarek` is present as a Nextflow/nf-core Sarek repository entry.

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

The source path must be `/fsx/analysis_results/<executing_entity>/<analysis_id>` or `/analysis_results/<executing_entity>/<analysis_id>`. The destination must be an explicit S3 URI ending in `<executing_entity>/<analysis_id>/`. Run mounts, reference data, nested paths, old export staging paths, unsafe path segments, and non-empty destination prefixes are rejected.

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
