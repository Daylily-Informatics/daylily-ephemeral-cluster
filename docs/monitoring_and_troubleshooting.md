# Monitoring And Troubleshooting

Use this when a current DayEC cluster exists but behavior is unclear or failing.

## 1. Local Runtime

```bash
source ./activate
dyec runtime status
dyec runtime check
dyec runtime explain
dyec info
```

If the local runtime points at the wrong editable checkout, refresh it:

```bash
python -m pip install -e .
```

## 2. Cluster State

```bash
dyec cluster list --profile "$AWS_PROFILE" --region "$REGION" --verbose
pcluster describe-cluster --region "$REGION" --cluster-name "$CLUSTER_NAME"
```

Infrastructure existence is not the final readiness point. DayEC readiness is when `dyec create` has returned after headnode configuration and validation.

## 3. Headnode Access

```bash
dyec headnode connect \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

Expected:

```bash
whoami
pwd
command -v day-clone
```

`whoami` must be `ubuntu`.

If the shell is incomplete:

```bash
dyec headnode configure \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

## 4. Reference DRA

The cluster template creates `/fsx/data` from the reference bucket `data/` prefix. If reference files are missing, check:

```bash
dyec headnode connect --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
ls -lah /fsx/data
```

Bootstrap waits for required reference entries and hard-fails if the DRA never becomes visible.

## 5. Run DRA Mounts

List and verify run mounts:

```bash
dyec --json mounts list --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec --json mounts verify --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME" --mount-id RUN123
```

Common failures:

- source S3 prefix overlaps an active DRA
- FSx path overlaps an active DRA
- filesystem was created with incompatible repository configuration
- headnode path under `/fsx/run_dir_mounts/<mount_id>` is not usable

## 6. Workflow State

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

On the headnode:

```bash
tmux ls
tmux attach -t <session>
squeue
sacct | tail -n 20
```

Run-state files live under `/home/ubuntu/daylily-runs/<session>/`.

## 7. Export Failures

Export reads from `/exports/<export_id>/...` and writes through an explicit temporary output DRA.

```bash
dyec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --export-id "$EXPORT_ID" \
  --source-path "/exports/$EXPORT_ID/analysis_results/ubuntu/" \
  --destination-s3-uri "$EXPORT_S3_URI" \
  --output-dir "$EXPORT_DIR"

cat "$EXPORT_DIR/fsx_export.yaml"
```

If the export failed, `fsx_export.yaml` records the phase, failure message, source path, destination S3 URI, task id when available, and detach state.

## 8. Delete Checks

Before deletion:

- run mounts that are no longer needed should be detached
- selected results should be exported
- `fsx_export.yaml` should show `status: success` and `detached: true`

```bash
dyec delete --dry-run --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec delete --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
```

## 9. Escalation Order

1. local runtime checks
2. `dyec preflight --debug`
3. `dyec cluster list` and `pcluster describe-cluster`
4. Session Manager document verification
5. run mount list/verify
6. workflow `status.json` and `tmux.log`
7. `fsx_export.yaml`
