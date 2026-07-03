# Operations

This is the day-2 runbook for current DayEC clusters.

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

The supported user is `ubuntu` and the supported working directory is `/home/ubuntu`.

## Re-run Headnode Configuration

```bash
dyec headnode configure \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

Use this after a cluster exists but the DayEC headnode tools, catalog, analysis guard surface, or login shell need repair. In particular, if a DayOA run reports `No such command 'analysis'`, rerun this command from an activated local checkout and then verify `dyec analysis --help` on the headnode before workflow writes.

## Inspect Cluster And Jobs

```bash
dyec cluster list --profile "$AWS_PROFILE" --region "$REGION" --verbose
dyec --json cluster describe --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec headnode jobs --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
```

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
  --executing-entity "${EXECUTING_ENTITY:-ubuntu}" \
  --dry-run
```

The catalog pin for DayOA commands is `9.0.0`.

Use `--project <project>` on `dyec samples run` or `dyec workflow launch` when
the budget/comment string should differ from the cluster name. DYEC passes that
value to `dyoainit`, DayOA exports it as `DAY_PROJECT`, and Slurm receives it as
`sbatch --comment "$DAY_PROJECT"`.

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

DYEC runs the collector on the headnode as `ubuntu`, from
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

Sample-manifest workflow:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --stage-dir "/fsx/staging/staged_external_sequencing_data/remote_stage_<timestamp>" \
  --analysis-id dayoa \
  --executing-entity "${EXECUTING_ENTITY:-ubuntu}" \
  --git-tag 9.0.0 \
  --genome hg38_broad \
  --target produce_alignstats
```

Run-folder workflow:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --run-context-file ./runs.tsv \
  --analysis-id run-qc \
  --executing-entity "${EXECUTING_ENTITY:-ubuntu}" \
  --git-tag 9.0.0 \
  --genome hg38_broad \
  --jobs 5 \
  --target produce_illumina_run_qc \
  --snakemake-extra "--config run_context_file=config/runs.tsv"
```

The launcher creates `/home/ubuntu/daylily-runs/<session>/` with `launch.sh`, `tmux.log`, and `status.json`.

## Budget Enforcement

New clusters enforce budgets by default. `dyec create` uses the cluster name as
the default budget project, or `--budget-project <project>` when supplied, and
renders that value into the `aws-parallelcluster-project` tag. It renders
`aws-parallelcluster-enforce-budget=true` unless `--disable-budget-enforcement`
is explicitly set.

The staged Slurm wrapper always requires `sbatch --comment <project>`. With
enforcement enabled, the exact `RnD` project bypasses AWS Budget lookup; every
other project must be present in the S3-backed user allow-list, match an AWS
Budget exactly, and be under 100% spend. When a job is blocked, the wrapper
prints the Ursa budget monitor URL:
`https://ursa.day.lsmc.bio/ursa-actions#budgets?budget=<project>`.

Disabling budget enforcement skips the S3 allow-list and AWS Budget checks, but
does not remove the `--comment <project>` requirement.

For repo-native work that is not a catalog workflow command, clone the pinned repository on the headnode and then follow that repository's documented launch path:

```bash
day-clone --list
day-clone --repository daylily-omics-analysis --destination "$ANALYSIS_ID" --git-tag 9.0.0 --executing-entity "$EXECUTING_ENTITY"
day-clone -d "$ANALYSIS_ID" -t 9.0.0
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
  --lines 100
```

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

For DayOA commands with catalog `artifact_registration` enabled, pass
`--artifact-registration-command-id`, `--dewey-url`, and `--dewey-token-env`.
DYEC then loads the exported DayOA evidence manifest, maps selected relative
paths to S3 URIs through `fsx_export.yaml`, posts to Dewey, and writes
`dewey_registration_receipt.json`. Missing policy, manifest, Dewey URL, token,
or invalid Dewey response is a hard failure.

Use the command catalog's `test_data_profile.source_mount_mode` before launch:
`default_mounted` data should already be visible through the cluster's default
reference/control-data DRAs; `run_dra_required` data must have a `runs.tsv`
`SOURCE_S3_URI` and `MOUNT_ID` and a verified `/fsx/run_dir_mounts/<MOUNT_ID>/`
projection; `none` commands should not receive sample or run-source inputs.

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
