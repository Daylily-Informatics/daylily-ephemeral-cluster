# CLI Reference

This reference is grounded in the current `daylily-ec --help` surface and the supported helper scripts that still belong to the operator workflow.

## Root Command

```bash
daylily-ec --help
```

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
- `headnode`

## `daylily-ec version`

Show the CLI version:

```bash
daylily-ec version
```

## `daylily-ec info`

Show the current runtime and Daylily paths:

```bash
daylily-ec info
```

Use this when you need to confirm:

- config directory
- state directory
- cache directory
- project root
- runtime backend

## `daylily-ec preflight`

Runs validation only. No cluster mutation happens here.

Required:

- `--region-az`

Important options:

- `--profile`
- `--config`
- `--pass-on-warn`
- `--debug`
- `--non-interactive`

Example:

```bash
daylily-ec preflight \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG"
```

## `daylily-ec create`

Runs the full create workflow:

- preflight
- config rendering
- ParallelCluster create
- Daylily headnode configuration
- bootstrap validation

Required:

- `--region-az`

Important options:

- `--profile`
- `--config`
- `--pass-on-warn`
- `--debug`
- `--repo-override <repo-key>:<git-ref>`
- `--non-interactive`

Example:

```bash
daylily-ec create \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG"
```

## `daylily-ec cluster-info`

Lists clusters in a region and their basic status.

Required:

- `--region`

Optional:

- `--profile`

Example:

```bash
daylily-ec cluster-info \
  --profile "$AWS_PROFILE" \
  --region "$REGION"
```

## `daylily-ec export`

Exports FSx content back to the attached S3 repository and writes `fsx_export.yaml`.

Required:

- `--cluster-name` or `--cluster`
- `--target-uri`
- `--region`
- `--output-dir`

Optional:

- `--profile`
- `--verbose`

Example:

```bash
daylily-ec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster-name "$CLUSTER_NAME" \
  --target-uri analysis_results/ubuntu \
  --output-dir "$EXPORT_DIR"
```

## `daylily-ec delete`

Deletes a cluster and monitors teardown.

Optional inputs:

- `--cluster-name`
- `--region`
- `--profile`
- `--state-file`
- `--yes`

For supported automation, pass the cluster and region explicitly instead of relying on prompts:

```bash
daylily-ec delete \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster-name "$CLUSTER_NAME"
```

Use `--yes` only when the delete has already been intentionally approved.

## `daylily-ec drift`

Runs a drift check against a previous state file.

Required:

- `--state-file`

Optional:

- `--profile`
- `--debug`

Example:

```bash
daylily-ec drift \
  --profile "$AWS_PROFILE" \
  --state-file ~/.config/daylily/state/<state-file>.json
```

## `daylily-ec resources-dir`

Print the extracted resource directory used by the installed package:

```bash
daylily-ec resources-dir
```

Useful when debugging packaged resource resolution.

## `daylily-ec env`

Subcommands:

- `status`
- `activate`
- `deactivate`
- `reset`

Examples:

```bash
daylily-ec env status
daylily-ec env activate
daylily-ec env deactivate
daylily-ec env reset
```

These commands print guidance and environment state. They do not replace `source ./activate` for the supported checkout flow.

## `daylily-ec runtime`

Subcommands:

- `status`
- `check`
- `explain`

Examples:

```bash
daylily-ec runtime status
daylily-ec runtime check
daylily-ec runtime explain
```

Use them to confirm:

- the active backend
- runtime prerequisites
- the expected activation command

## `daylily-ec pricing snapshot`

Current pricing-related subcommand:

- `snapshot`

Important options:

- `--region` (repeatable)
- `--partition` (repeatable)
- `--config`
- `--profile`

Example:

```bash
daylily-ec pricing snapshot \
  --profile "$AWS_PROFILE" \
  --region us-west-2 \
  --partition all_clusters
```

## `daylily-ec headnode init`

Initializes headnode shell state and can emit shell code for bootstrap flows.

Important options:

- `--project`
- `--profile`
- `--skip-project-check`
- `--non-interactive`
- `--emit-shell`

Examples:

```bash
daylily-ec headnode init --project dayoa --skip-project-check
daylily-ec headnode init --emit-shell
```

This command is about shell/bootstrap state. To configure a live cluster headnode over Session Manager from the operator machine, use:

```bash
bin/daylily-cfg-headnode --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
```

## Supported Helper Scripts

These helpers remain part of the supported path:

### `bin/daylily-ssh-into-headnode`

```bash
bin/daylily-ssh-into-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

### `bin/daylily-stage-samples-from-local-to-headnode`

```bash
bin/daylily-stage-samples-from-local-to-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --reference-bucket "$REF_BUCKET" \
  --config-dir "$STAGE_CFG_DIR" \
  "$ANALYSIS_SAMPLES"
```

### `bin/daylily-run-omics-analysis-headnode`

```bash
bin/daylily-run-omics-analysis-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --stage-dir "/fsx/data/staged_sample_data/remote_stage_<timestamp>" \
  --destination dayoa
```

### `bin/daylily-cfg-headnode`

```bash
bin/daylily-cfg-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

For end-to-end live validation, see [testing_and_debugging.md](testing_and_debugging.md).
