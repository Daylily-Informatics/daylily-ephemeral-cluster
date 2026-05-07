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
- `cluster`
- `export`
- `delete`
- `resources-dir`
- `env`
- `runtime`
- `pricing`
- `aws`
- `headnode`
- `samples`
- `workflow`
- `state`

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

Lists clusters in a region and their basic status. Prefer `daylily-ec cluster list` for new operator usage.

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

## `daylily-ec cluster`

ParallelCluster inspection helpers. `cluster list` describes each cluster so the
default operator table includes cluster name, region, and public IP. Add
`--verbose` to include status, create time, last update time, headnode launch
time, and whether the Daylily headnode configuration check passes. Repeat
`--region` once per requested region to combine clusters into one table.

Subcommands:

- `list`
- `describe`
- `wait`

Examples:

```bash
daylily-ec cluster list \
  --profile "$AWS_PROFILE" \
  --region "$REGION"

daylily-ec cluster list \
  --profile "$AWS_PROFILE" \
  --region us-west-2 \
  --region us-east-1 \
  --verbose

daylily-ec cluster list \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --details

daylily-ec --json cluster describe \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"

daylily-ec cluster wait \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --status CREATE_COMPLETE
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
- `--dry-run`

For supported automation, pass the cluster and region explicitly instead of relying on prompts:

```bash
daylily-ec delete --dry-run \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster-name "$CLUSTER_NAME"

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

## `daylily-ec aws validate`

Read-only AWS readiness validation for the selected profile and AZ.

Subcommands:

- `permissions`
- `quotas`
- `all`

Required:

- `--profile`
- `--region-az`

Optional:

- `--config`
- `--gap-analysis`

Examples:

```bash
daylily-ec aws validate permissions \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --gap-analysis aws_permissions_gap.md

daylily-ec aws validate quotas \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG" \
  --gap-analysis aws_quota_gap.md

daylily-ec --json aws validate all \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG"
```

The command rejects `--profile default` and does not use implicit profile or
region discovery. It never creates, updates, deletes, sends SSM commands, starts
SSM sessions, or runs `pcluster create`. `--gap-analysis PATH` writes a Markdown
report for AWS admins with every passing permission/quota check, denied actions,
quota codes, rendered cluster demand, and WARN/FAIL remediation guidance.
ParallelCluster UI is not part of current validation; the repo uses the
`pcluster` CLI directly.

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

This command is about shell/bootstrap state. To configure a live cluster headnode over Session Manager from the operator machine, use `daylily-ec headnode configure`.

```bash
daylily-ec headnode configure --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
```

## `daylily-ec headnode connect`

Opens a Session Manager shell on the cluster headnode. The shell must land as
`ubuntu` in `/home/ubuntu` in a bash login shell.

Important options:

- `--profile`
- `--region`
- `--cluster` / `--cluster-name`
- `--dry-run`

Example:

```bash
daylily-ec headnode connect \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

## `daylily-ec headnode info`

Returns the full `pcluster describe-cluster` payload for one cluster. Use global `--json` for machine-readable output.

Important options:

- `--profile`
- `--region`
- `--cluster` / `--cluster-name`

Example:

```bash
daylily-ec --json headnode info \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

## `daylily-ec headnode jobs`

Runs a read-only Slurm queue check on the headnode using the same format as the headnode `sq` alias.

Important options:

- `--profile`
- `--region`
- `--cluster` / `--cluster-name`

Example:

```bash
daylily-ec headnode jobs \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

## `daylily-ec headnode configure`

Re-runs the supported Daylily headnode bootstrap over SSM.

Important options:

- `--profile`
- `--region`
- `--cluster` / `--cluster-name`
- `--repo-overrides`

Example:

```bash
daylily-ec headnode configure \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

## `daylily-ec samples stage`

Stages local `analysis_samples.tsv` inputs into the FSx-backed data repository and writes workflow-ready manifests.

Important inputs:

- positional `analysis_samples`
- `--reference-bucket`
- `--config-dir`
- `--stage-target`
- `--profile`
- `--region`
- `--debug`

Manifest notes:

- the shipped template is `etc/analysis_samples_template.tsv`
- legacy Illumina rows can still use `R1_FQ` / `R2_FQ`
- multi-modality rows can also populate `ILMN_*`, `CG_*`, `ONT_*`, `UG_*`, `ULTIMA_CRAM*`, `ONT_CRAM*`, `PB_BAM*`, `ONT_BAM*`, and `ROCHE_BAM*`
- ONT FASTQ rows can populate `ONT_FASTQ_PREFIX` with an S3 prefix ending in `fastq_pass/<tag>/`; the helper parses the ONT shard filenames, selects one run plus flowcell plus tag, concatenates the shards into one `ONT_R1_PATH`, and writes `ONT_R2_PATH=na`
- populate `ONT_FLOWCELL_ID` when the ONT FASTQ prefix contains shards from more than one flowcell
- raw reads are staged into the remote stage; aligned artifacts remain pass-through unless `STAGE_DIRECTIVE=stage_data`
- one manifest row normally maps to one `units.tsv` row; multi-lane Illumina rows with the same unit identity are merged

Example:

```bash
daylily-ec samples stage "$ANALYSIS_SAMPLES" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --reference-bucket "$REF_BUCKET" \
  --config-dir "$STAGE_CFG_DIR"
```

## `daylily-ec samples run`

Stages a manifest, validates it against a repository catalog command, and
launches the compatible workflow with the staged manifests.

Important inputs:

- positional `analysis_samples`
- `--command-id`
- `--destination`
- `--reference-bucket`
- `--config-dir`
- `--profile`
- `--region`
- `--cluster`
- `--git-tag`
- `--dry-run`

The command writes a timestamped `*_samples_run_receipt.json` next to the
generated `samples.tsv` and `units.tsv`. Complete Genomics/MGI inputs use
`CG_R1_FQ` / `CG_R2_FQ` in the staging manifest; generated `units.tsv` rows
still point DayOA at `ILMN_R1_PATH` / `ILMN_R2_PATH` with
`SEQ_VENDOR=CG` and `SEQ_PLATFORM=DNBSEQ`.

Example:

```bash
daylily-ec samples run "$ANALYSIS_SAMPLES" \
  --command-id complete_genomics_mgi_snv_concordance \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --reference-bucket "$REF_BUCKET" \
  --destination "$ANALYSIS_RUN_ID" \
  --dry-run
```

## `daylily-ec workflow`

Headnode workflow launch and inspection helpers.

Subcommands:

- `launch`
- `status`
- `logs`

Examples:

```bash
daylily-ec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --stage-dir "/fsx/data/staged_sample_data/remote_stage_<timestamp>" \
  --destination dayoa

daylily-ec --json workflow status \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --session daylily-omics-analysis

daylily-ec workflow logs \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --session daylily-omics-analysis \
  --lines 100
```

## `daylily-ec state`

Local state-file inspection helpers.

Subcommands:

- `list`
- `show`

Examples:

```bash
daylily-ec --json state list
daylily-ec state show --cluster-name "$CLUSTER_NAME"
daylily-ec --json state show --state-file ~/.config/daylily/state_<cluster>_<run>.json
```

## Helper Scripts

These helpers remain callable, but the preferred operator surface is now `daylily-ec`.

### `bin/daylily-ssh-into-headnode`

Prefer `daylily-ec headnode connect` for operator use.

```bash
bin/daylily-ssh-into-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

### `bin/daylily-stage-samples-from-local-to-headnode`

Prefer `daylily-ec samples stage` for operator use.

```bash
bin/daylily-stage-samples-from-local-to-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --reference-bucket "$REF_BUCKET" \
  --config-dir "$STAGE_CFG_DIR" \
  "$ANALYSIS_SAMPLES"
```

### `bin/daylily-run-omics-analysis-headnode`

Prefer `daylily-ec workflow launch` for operator use.

```bash
bin/daylily-run-omics-analysis-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --stage-dir "/fsx/data/staged_sample_data/remote_stage_<timestamp>" \
  --destination dayoa
```

### `bin/daylily-cfg-headnode`

Prefer `daylily-ec headnode configure` for operator use.

```bash
bin/daylily-cfg-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

For end-to-end live validation, see [testing_and_debugging.md](testing_and_debugging.md).
