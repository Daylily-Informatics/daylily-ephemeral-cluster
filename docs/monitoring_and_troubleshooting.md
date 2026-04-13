# Monitoring And Troubleshooting

Use this runbook when the cluster exists but something in the supported lifecycle is failing or unclear.

## 1. Confirm Local Runtime Health

Start locally:

```bash
source ./activate
daylily-ec runtime status
daylily-ec runtime check
daylily-ec runtime explain
daylily-ec info
```

If the local runtime is broken, fix that first.

## 2. Confirm Cluster State

Use both the Daylily view and the ParallelCluster view:

```bash
daylily-ec cluster-info --profile "$AWS_PROFILE" --region "$REGION"
pcluster describe-cluster --region "$REGION" -n "$CLUSTER_NAME"
```

Key point: infrastructure existence does not prove Daylily readiness. `daylily-ec create` still has post-create bootstrap work to finish after the underlying cluster first appears.

## 3. Session Manager Readiness

If connect fails, check the document:

```bash
aws ssm get-document \
  --name SSM-SessionManagerRunShell \
  --document-format JSON \
  --query Content \
  --output text \
  --region "$REGION" \
  --profile "$AWS_PROFILE"
```

Check the local plugin:

```bash
session-manager-plugin
```

If the shell opens but the environment feels wrong, reconnect and verify:

```bash
whoami
command -v day-clone
```

Expected:

- `ubuntu`
- `day-clone` on `PATH`

## 4. Headnode Shell Bootstrap Problems

When the login shell is incomplete:

```bash
bin/daylily-cfg-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

Then reconnect and check again:

```bash
whoami
command -v day-clone
command -v tmux
```

The supported path does not continue from another user context.

## 5. Workflow Monitoring

The current launcher creates a durable run directory on the headnode:

```text
/home/ubuntu/daylily-runs/<session>/
```

Inspect it:

```bash
cat /home/ubuntu/daylily-runs/<session>/status.json
tail -n 100 /home/ubuntu/daylily-runs/<session>/tmux.log
```

Attach if needed:

```bash
tmux ls
tmux attach -t <session>
```

Slurm checks:

```bash
squeue
sacct | tail -n 20
```

## 6. Staging Issues

If workflow launch cannot find manifests or staged data, rerun staging and pay attention to the printed remote stage directory:

```bash
bin/daylily-stage-samples-from-local-to-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --reference-bucket "$REF_BUCKET" \
  --config-dir "$STAGE_CFG_DIR" \
  "$ANALYSIS_SAMPLES"
```

Local manifest checks:

```bash
ls -lh "$STAGE_CFG_DIR"
head -n 5 "$STAGE_CFG_DIR"/*_samples.tsv
head -n 5 "$STAGE_CFG_DIR"/*_units.tsv
```

Then relaunch using the exact printed `--stage-dir`.

## 7. Export Verification

Run export:

```bash
daylily-ec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster-name "$CLUSTER_NAME" \
  --target-uri analysis_results/ubuntu \
  --output-dir "$EXPORT_DIR"
```

Then inspect:

```bash
cat "$EXPORT_DIR/fsx_export.yaml"
```

If export failed, that file should tell you whether the problem was path normalization, FSx task startup, or task completion.

## 8. Teardown Checks

Before delete:

- verify export succeeded
- verify the destination S3 URI looks correct

Delete:

```bash
daylily-ec delete \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster-name "$CLUSTER_NAME"
```

After delete, confirm:

```bash
daylily-ec cluster-info --profile "$AWS_PROFILE" --region "$REGION"
```

If the cluster is still present, inspect the ParallelCluster side directly:

```bash
pcluster describe-cluster --region "$REGION" -n "$CLUSTER_NAME"
```

## 9. When To Stop Guessing

Use the following escalation order:

1. local runtime checks
2. preflight with `--debug`
3. cluster-info plus `pcluster describe-cluster`
4. Session Manager document verification
5. headnode run-state inspection under `/home/ubuntu/daylily-runs/`
6. export receipt inspection

That path stays aligned with the actual code rather than drifting into folklore.
