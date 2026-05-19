# CLI Reference

This reference is grounded in the current `dyec` / `daylily-ec` command surface. Both executable names use the same entrypoint.

## Root Commands

```bash
dyec --help
```

Current commands:

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
- `cluster`
- `headnode`
- `samples`
- `workflow`
- `repositories`
- `exports`
- `mounts`
- `mount`
- `state`

Use global `--json` for machine-readable output where supported.

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

`create` runs preflight, renders the ParallelCluster YAML, creates the cluster, waits for the headnode, configures DayEC on the headnode over SSM, and validates the supported `ubuntu` login shell.

Important options:

- `--region-az`
- `--profile`
- `--config`
- `--pass-on-warn`
- `--debug`
- `--non-interactive`

## Cluster

```bash
dyec cluster list --profile "$AWS_PROFILE" --region "$REGION" --verbose
dyec --json cluster describe --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec cluster wait --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
```

`cluster-info` remains available, but `cluster list` is the preferred current operator surface.

## Headnode

```bash
dyec headnode connect --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec headnode configure --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec headnode info --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec headnode jobs --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
```

Supported headnode command payloads run as `ubuntu`. Interactive sessions use `SSM-SessionManagerRunShell` and must land in `/home/ubuntu` in a bash login shell.

## Samples

`samples stage` translates `analysis_samples.tsv` into workflow-ready staged manifests:

```bash
dyec samples stage "$ANALYSIS_SAMPLES" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --reference-bucket "$REF_BUCKET" \
  --config-dir "$STAGE_CFG_DIR"
```

`samples run` stages the manifest, validates it against a catalog command, and launches the workflow:

```bash
dyec samples run "$ANALYSIS_SAMPLES" \
  --command-id complete_genomics_mgi_snv_concordance \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --reference-bucket "$REF_BUCKET" \
  --destination dayoa \
  --dry-run
```

Important options:

- `--reference-bucket`
- `--config-dir`
- `--stage-target`
- `--run-metric-staging RUN_UID:PLATFORM:FOFN`
- `--command-id`
- `--destination`
- `--git-tag`

## Run Mounts

Run mounts are FSx Data Repository Associations from selected S3 run prefixes to `/run_dir_mounts/<mount_id>/`, visible on the headnode as `/fsx/run_dir_mounts/<mount_id>/`. The mount id defaults to the final folder in the S3 URI.

```bash
dyec --json mounts create "s3://sequencer-run-bucket/runs/RUN123/" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --platform ILMN \
  --read-only \
  --batch-import-metadata-on-create \
  --auto-import NEW,CHANGED \
  --wait

dyec --json mounts list \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"

dyec --json mounts describe \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --mount-id RUN123

dyec --json mounts verify \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --mount-id RUN123

dyec --json mounts delete \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --mount-id RUN123 \
  --wait
```

`mounts verify` is currently headnode-only. It returns exit code `0` when the `/fsx/...` path is usable and nonzero when it is not.

`dyec mount rundir` is an alias for `dyec mounts create`.

Default behavior is read-oriented:

- no AutoExport policy
- no source S3 writeback
- no deletion of S3 objects on detach
- overlapping active FSx paths or S3 prefixes are rejected

## Workflow

Sample-manifest launch:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --stage-dir "/fsx/data/staged_sample_data/remote_stage_<timestamp>" \
  --destination dayoa \
  --git-tag 1.0.16
```

Run-context launch:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --run-context-file ./runs.tsv \
  --destination run-qc \
  --git-tag 1.0.16 \
  --dy-command "bin/day_run produce_illumina_run_qc --config run_context_file=config/runs.tsv -p -j 5 -k"
```

Inspect:

```bash
dyec --json workflow status --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME" --session <session>
dyec workflow logs --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME" --session <session> --lines 100
```

## Repository Catalog

```bash
dyec repositories commands
dyec repositories commands --config config/daylily_available_repositories.yaml
dyec repositories commands --command-id illumina_run_qc
```

The catalog is version 2. DayOA repository and command pins are `1.0.16`.

Command classes:

- `sample_analysis`: uses `analysis_samples.tsv`, staging, `samples.tsv`, and `units.tsv`
- `run_analysis`: uses `runs.tsv` and requires a run mount

## Export

Root export runs the complete explicit output-DRA workflow on one completed analysis directory:

```bash
dyec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --source-path "/fsx/analysis_results/ubuntu/$ANALYSIS_DIR" \
  --destination-s3-uri "$EXPORT_S3_URI" \
  --output-dir "$EXPORT_DIR"
```

Required:

- `--cluster` or `--fsx-file-system-id`
- `--source-path`
- `--destination-s3-uri`
- `--region`
- `--output-dir`

The source path must be `/fsx/analysis_results/ubuntu/<analysis_dir>` or `/analysis_results/ubuntu/<analysis_dir>`. The destination must be an explicit S3 URI ending in `analysis_results/ubuntu/<analysis_dir>/`. Run mounts, reference data, nested paths, and old export staging paths are rejected as export sources.

Lower-level helpers:

```bash
dyec --json exports attach --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME" --source-path "/fsx/analysis_results/ubuntu/$ANALYSIS_DIR" --destination-s3-uri "$EXPORT_S3_URI"
dyec --json exports run --profile "$AWS_PROFILE" --region "$REGION" --source-path "/fsx/analysis_results/ubuntu/$ANALYSIS_DIR" --destination-s3-uri "$EXPORT_S3_URI" --fsx-file-system-id "$FSX_FILE_SYSTEM_ID"
dyec --json exports detach --profile "$AWS_PROFILE" --region "$REGION" --association-id "$EXPORT_DRA_ID"
```

## Delete

```bash
dyec delete --dry-run --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec delete --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
```

Use `--yes` only when the destructive delete has already been approved.

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
