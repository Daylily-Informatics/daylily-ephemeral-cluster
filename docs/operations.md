# Operations

This doc covers the supported day-2 operator tasks after a cluster exists.

## Connect To The Head Node

```bash
bin/daylily-ssh-into-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

The supported path uses Session Manager and must land directly in the `ubuntu` login shell.

## Reapply Headnode Configuration

If you update the local checkout after the cluster already exists, reapply the supported headnode configuration before running new helpers:

```bash
bin/daylily-cfg-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

## Validate The Shell Context

On the head node:

```bash
whoami
echo "$CONDA_DEFAULT_ENV"
command -v daylily-ec
command -v day-clone
day-clone --list
```

If the managed login hook has not been applied yet:

```bash
cd ~/projects/daylily-ephemeral-cluster
source ./activate
eval "$(daylily-ec headnode init --emit-shell --non-interactive --skip-project-check)"
```

## Stage From The Operator Machine

```bash
bin/daylily-stage-samples-from-local-to-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --reference-bucket "$REF_BUCKET" \
  --config-dir ./generated-config \
  ./analysis_samples.tsv
```

Important details:

- the staging helper writes through the S3-backed FSx data repository
- the default visible remote staging base is `/fsx/data/staged_sample_data`
- the command prints the exact remote stage directory to pass into the launcher

## Launch The Workflow

```bash
bin/daylily-run-omics-analysis-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --stage-dir /fsx/data/staged_sample_data/remote_stage_<timestamp>
```

The supported launcher:

- clones the configured workflow repo through `day-clone`
- writes `config/samples.tsv` and `config/units.tsv`
- records durable run state in `/home/ubuntu/daylily-runs/<session>/`
- starts the workflow inside tmux

If you want the launcher to enforce the upstream workflow repo’s own project validation, add `--strict-project-check`. The supported default skips that upstream check so the Daylily flow does not fall back to a global project implicitly.

## Inspect Runtime State

On the head node:

```bash
sinfo
squeue -o "%.18i %.8u %.8T %.10M %.30N %.50j"
tmux ls
tmux attach -t <session-name>
```

For durable launcher state from the operator machine:

```bash
python -m daylily_ec.ssh_to_ssm_e2e_runner \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster-name "$CLUSTER_NAME" \
  --reuse-existing-cluster \
  --reference-bucket "$REF_BUCKET" \
  --analysis-samples ./analysis_samples.tsv \
  --workflow-live
```

That runner reuses the cluster, restages data, launches the workflow, waits for `status.json` completion, and exports results unless `--skip-export` is set.

## Export Results

```bash
daylily-ec export \
  --cluster-name "$CLUSTER_NAME" \
  --region "$REGION" \
  --target-uri analysis_results/ubuntu \
  --output-dir .
```

`fsx_export.yaml` is the local artifact to keep.

## Delete The Cluster

```bash
daylily-ec delete \
  --cluster-name "$CLUSTER_NAME" \
  --region "$REGION"
```

Delete is destructive. Export and verify the results first.
