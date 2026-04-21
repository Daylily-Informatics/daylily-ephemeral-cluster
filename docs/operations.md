# Operations

This is the day-2 operator runbook for the supported path: connect, validate, restage, run, monitor, export, and delete.

## Connect To The Headnode

Use the supported CLI command:

```bash
daylily-ec headnode connect \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

What this does:

- resolves the headnode instance ID
- checks Session Manager plugin availability
- validates `SSM-SessionManagerRunShell`
- opens the interactive shell

Once connected, the shell should already be correct:

```bash
whoami
pwd
command -v day-clone
command -v tmux
```

Expected:

- `whoami` prints `ubuntu`
- `day-clone` resolves on `PATH`

If that is not true, stop and fix the bootstrap. Do not continue a supported workflow from the wrong user context.

`day-clone` uses HTTPS by default for workflow clones. For editable development clones
where you need to push back to GitHub, select SSH explicitly:

```bash
day-clone -d dayoa-dev --repository daylily-omics-analysis -w ssh
```

Useful headnode status commands:

```bash
daylily-ec headnode info \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"

daylily-ec headnode jobs \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

## Re-run Headnode Configuration

If cluster creation succeeded but you need to re-apply the supported headnode configuration:

```bash
daylily-ec headnode configure \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

This is the supported repair path when the headnode needs to be brought back to the expected Daylily state.

## Restage Inputs From The Laptop

```bash
daylily-ec samples stage "$ANALYSIS_SAMPLES" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --reference-bucket "$REF_BUCKET" \
  --config-dir "$STAGE_CFG_DIR"
```

Operational notes:

- the input file is `analysis_samples.tsv`
- the helper writes workflow manifests into `--config-dir`
- the helper prints the remote stage directory under `/fsx/data/staged_sample_data/...`
- use that exact printed directory for the next step

Useful local checks:

```bash
ls -lh "$STAGE_CFG_DIR"
head -n 5 "$STAGE_CFG_DIR"/*_samples.tsv
head -n 5 "$STAGE_CFG_DIR"/*_units.tsv
```

## Launch A Workflow

```bash
daylily-ec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --stage-dir "/fsx/data/staged_sample_data/remote_stage_<timestamp>" \
  --destination dayoa
```

Useful launch options:

- `--destination`: controls the target workspace under `/fsx/analysis_results/ubuntu`
- `--aligners`
- `--dedupers`
- `--snv-callers`
- `--jobs`
- `--dy-command`: full override if you need a specific workflow command
- `--dry-run`: useful for launch smoke tests

The launcher writes the run-state directory:

```text
/home/ubuntu/daylily-runs/<session>/
```

Expected files:

- `launch.sh`
- `tmux.log`
- `status.json`

## Inspect Tmux And Runtime State

Reconnect if needed:

```bash
daylily-ec headnode connect \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

Then inspect:

```bash
tmux ls
tmux attach -t <session>
squeue
```

Useful local CLI checks:

```bash
daylily-ec runtime status
daylily-ec runtime check
daylily-ec runtime explain
daylily-ec info
daylily-ec cluster list --profile "$AWS_PROFILE" --region "$REGION"
daylily-ec --json workflow status --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME" --session <session>
daylily-ec workflow logs --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME" --session <session> --lines 100
```

## Export Results

The supported export scope is `analysis_results/ubuntu` unless you have a deliberate reason to choose a narrower or different path.

```bash
daylily-ec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster-name "$CLUSTER_NAME" \
  --target-uri analysis_results/ubuntu \
  --output-dir "$EXPORT_DIR"
```

Then verify the receipt:

```bash
cat "$EXPORT_DIR/fsx_export.yaml"
```

Success means:

- `status: success`
- `s3_uri:` points to the expected path under the filesystem export root

## Delete The Cluster

Deletion is destructive. The supported flow is:

1. export first
2. verify `fsx_export.yaml`
3. then delete

Command:

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

For scripted teardown, `--yes` skips the final FSx deletion confirmation prompt. Use that only when the delete has already been intentionally approved.

## A Useful Read-Only Loop

When you are watching a live run from the operator machine:

```bash
watch -n 30 "daylily-ec cluster list --profile $AWS_PROFILE --region $REGION"
```

When you are watching from the headnode:

```bash
watch -n 30 "squeue && echo && tail -n 40 /home/ubuntu/daylily-runs/<session>/tmux.log"
```

If things go sideways, continue with [monitoring_and_troubleshooting.md](monitoring_and_troubleshooting.md).
