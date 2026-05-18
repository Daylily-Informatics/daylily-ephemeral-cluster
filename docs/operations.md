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

Use this after a cluster exists but the DayEC headnode tools, catalog, or login shell need repair.

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
  --reference-bucket "$REF_BUCKET" \
  --config-dir "$STAGE_CFG_DIR"
```

The helper writes local staged config files and prints a remote stage directory under `/fsx/data/staged_sample_data/...`.

For catalog-driven sample launches:

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

The catalog pin for DayOA commands is `1.0.7`.

## Attach Run Folders

Use run DRAs for raw run folders that should stay in S3 until read by the workflow:

```bash
dyec --json mounts create \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --s3-uri "s3://sequencer-run-bucket/runs/RUN123/" \
  --mount-id RUN123 \
  --run-id RUN123 \
  --platform ILMN \
  --read-only \
  --batch-import-metadata-on-create \
  --auto-import NEW,CHANGED \
  --wait
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
  --wait
```

Deletion detaches the DRA with `DeleteDataInFileSystem=False`; it does not delete S3 objects.

## Launch Workflows

Sample-manifest workflow:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --stage-dir "/fsx/data/staged_sample_data/remote_stage_<timestamp>" \
  --destination dayoa \
  --git-tag 1.0.7
```

Run-folder workflow:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --run-context-file ./runs.tsv \
  --destination run-qc \
  --git-tag 1.0.7 \
  --dy-command "bin/day_run produce_illumina_run_qc --config run_context_file=config/runs.tsv -p -j 5 -k"
```

The launcher creates `/home/ubuntu/daylily-runs/<session>/` with `launch.sh`, `tmux.log`, and `status.json`.

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
  --source-path "/fsx/analysis_results/ubuntu/$ANALYSIS_DIR" \
  --destination-s3-uri "$EXPORT_S3_URI" \
  --output-dir "$EXPORT_DIR"
```

Verify:

```bash
cat "$EXPORT_DIR/fsx_export.yaml"
```

Success means `status: success`, `task_lifecycle: SUCCEEDED`, `detached: true`, `delete_data_in_file_system: false`, and a completed FSx export task id. The destination must be an explicit S3 URI ending in `analysis_results/ubuntu/<analysis_dir>/`.

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
