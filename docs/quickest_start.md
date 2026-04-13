# Quickest Start

This doc assumes:

- the AWS account already has the operator identity and permissions needed for ParallelCluster, FSx, S3, and Session Manager
- a region-scoped reference bucket already exists
- you are working from a repo checkout of `daylily-ephemeral-cluster`

## 1. Activate DAY-EC

```bash
source ./activate

daylily-ec info
daylily-ec version
```

## 2. Prepare Operator Variables

```bash
export AWS_PROFILE=daylily-service-lsmc
export REGION=us-west-2
export REGION_AZ=us-west-2d
export CLUSTER_NAME=daylily-demo-cluster
export REF_BUCKET=s3://lsmc-dayoa-omics-analysis-us-west-2
export DAY_EX_CFG="$HOME/.config/daylily/daylily_ephemeral_cluster.yaml"
```

Create the config file from the template if you do not already have one:

```bash
mkdir -p "$(dirname "$DAY_EX_CFG")"
cp config/daylily_ephemeral_cluster_template.yaml "$DAY_EX_CFG"
```

Fill in the cluster-specific values in `"$DAY_EX_CFG"` before create. The most important fields are `cluster_name`, `s3_bucket_name`, `budget_email`, and `heartbeat_email`.

## 3. Run Preflight

```bash
daylily-ec preflight \
  --region-az "$REGION_AZ" \
  --profile "$AWS_PROFILE" \
  --config "$DAY_EX_CFG"
```

Review warnings before using `--pass-on-warn`.

## 4. Create The Cluster

```bash
daylily-ec create \
  --region-az "$REGION_AZ" \
  --profile "$AWS_PROFILE" \
  --config "$DAY_EX_CFG"
```

Success means the CLI has already finished the post-create headnode configuration step.

## 5. Connect And Verify

```bash
bin/daylily-ssh-into-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

On the head node, `whoami` should report `ubuntu`. If you need to reapply the shell context manually:

```bash
cd ~/projects/daylily-ephemeral-cluster
source ./activate
eval "$(daylily-ec headnode init --emit-shell --non-interactive --skip-project-check)"
```

## 6. Stage Sample Input From The Operator Machine

```bash
bin/daylily-stage-samples-from-local-to-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --reference-bucket "$REF_BUCKET" \
  --config-dir ./generated-config \
  ./analysis_samples.tsv
```

The command prints the exact remote FSx staging directory. Keep that path for the workflow launch step.

## 7. Launch The Workflow

```bash
bin/daylily-run-omics-analysis-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --stage-dir /fsx/data/staged_sample_data/remote_stage_<timestamp>
```

The launcher prints:

- the tmux session name
- the durable run directory under `/home/ubuntu/daylily-runs/<session>`
- the workflow repo path under `/fsx/analysis_results/ubuntu/...`

## 8. Export Results

```bash
daylily-ec export \
  --cluster-name "$CLUSTER_NAME" \
  --region "$REGION" \
  --target-uri analysis_results/ubuntu \
  --output-dir .
```

This writes `fsx_export.yaml` locally.

## 9. Delete The Cluster

```bash
daylily-ec delete \
  --cluster-name "$CLUSTER_NAME" \
  --region "$REGION"
```

Delete only after confirming the export completed successfully.
