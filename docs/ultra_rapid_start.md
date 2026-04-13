# Ultra Rapid Start

This is the shortest supported path for operators who already have:

- a working AWS profile
- the required IAM/bootstrap in the target account
- a known-good Daylily config file
- a reference bucket in the target region
- `SSM-SessionManagerRunShell` configured correctly

If any of that is not already true, stop here and read [aws_setup.md](aws_setup.md) first.

## Short Path

```bash
source ./activate

export AWS_PROFILE=daylily-service-lsmc
export REGION=us-west-2
export REGION_AZ=us-west-2d
export CLUSTER_NAME=day-demo-$(date +%Y%m%d%H%M%S)
export DAY_EX_CFG="$HOME/.config/daylily/daylily_ephemeral_cluster.yaml"
export REF_BUCKET=s3://lsmc-dayoa-omics-analysis-us-west-2
export ANALYSIS_SAMPLES=etc/analysis_samples_template.tsv
export STAGE_CFG_DIR="$PWD/tmp-stage-config/$CLUSTER_NAME"
export EXPORT_DIR="$PWD/tmp-export/$CLUSTER_NAME"

daylily-ec preflight \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG"

daylily-ec create \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG"

bin/daylily-ssh-into-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"

bin/daylily-stage-samples-from-local-to-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --reference-bucket "$REF_BUCKET" \
  --config-dir "$STAGE_CFG_DIR" \
  "$ANALYSIS_SAMPLES"

bin/daylily-run-omics-analysis-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --stage-dir "/fsx/data/staged_sample_data/remote_stage_<timestamp>" \
  --destination dayoa

daylily-ec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster-name "$CLUSTER_NAME" \
  --target-uri analysis_results/ubuntu \
  --output-dir "$EXPORT_DIR"
```

## Fast Checks

- `daylily-ec info`
- `daylily-ec runtime status`
- `daylily-ec cluster-info --profile "$AWS_PROFILE" --region "$REGION"`
- `cat "$EXPORT_DIR/fsx_export.yaml"`

## Delete Only After Export Verification

```bash
daylily-ec delete \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster-name "$CLUSTER_NAME"
```

That delete is destructive. Verify export first.
