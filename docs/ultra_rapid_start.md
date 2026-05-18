# Ultra Rapid Start

Use this only when AWS setup, quotas, Session Manager, the DayEC config, and the reference bucket are already known-good.

```bash
source ./activate

export AWS_PROFILE=daylily-service-lsmc
export REGION=us-west-2
export REGION_AZ=us-west-2d
export CLUSTER_NAME=day-demo-$(date +%Y%m%d%H%M%S)
export DAY_EX_CFG="$HOME/.config/daylily/daylily_ephemeral_cluster.yaml"
export REF_BUCKET=s3://lsmc-dayoa-omics-analysis-us-west-2
export ANALYSIS_BUCKET=s3://lsmc-dayoa-analysis-results-us-west-2
export ANALYSIS_DIR=dayoa
export ANALYSIS_SAMPLES=etc/analysis_samples_template.tsv
export STAGE_CFG_DIR="$PWD/tmp-stage-config/$CLUSTER_NAME"
export EXPORT_DIR="$PWD/tmp-export/$ANALYSIS_DIR"
export EXPORT_S3_URI="$ANALYSIS_BUCKET/analysis_results/ubuntu/$ANALYSIS_DIR/"

dyec preflight --profile "$AWS_PROFILE" --region-az "$REGION_AZ" --config "$DAY_EX_CFG"
dyec create --profile "$AWS_PROFILE" --region-az "$REGION_AZ" --config "$DAY_EX_CFG"

dyec samples stage "$ANALYSIS_SAMPLES" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --reference-bucket "$REF_BUCKET" \
  --config-dir "$STAGE_CFG_DIR"

dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --stage-dir "/fsx/data/staged_sample_data/remote_stage_<timestamp>" \
  --destination "$ANALYSIS_DIR" \
  --git-tag 1.0.9

dyec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --source-path "/fsx/analysis_results/ubuntu/$ANALYSIS_DIR" \
  --destination-s3-uri "$EXPORT_S3_URI" \
  --output-dir "$EXPORT_DIR"

cat "$EXPORT_DIR/fsx_export.yaml"
```

Fast checks:

```bash
dyec info
dyec runtime status
dyec cluster list --profile "$AWS_PROFILE" --region "$REGION" --verbose
```

Delete only after `fsx_export.yaml` shows `status: success` and `detached: true`.

```bash
dyec delete --dry-run --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec delete --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
```
