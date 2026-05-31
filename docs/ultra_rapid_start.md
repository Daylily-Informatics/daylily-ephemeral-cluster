# Ultra Rapid Start

Use this only when AWS setup, quotas, Session Manager, the DayEC config, and the reference S3 URI are already known-good.

```bash
source ./activate

export AWS_PROFILE=daylily-service-lsmc
export REGION=us-west-2
export REGION_AZ=us-west-2d
export CLUSTER_NAME=day-demo-$(date +%Y%m%d%H%M%S)
export DAY_EX_CFG="$HOME/.config/daylily/daylily_ephemeral_cluster.yaml"
export REF_S3_URI=s3://lsmc-dayoa-references-usw2
export CONTROL_DATA_S3_URI=s3://lsmc-dayoa-control-data-usw2
export STAGE_S3_URI=s3://lsmc-ssf-sequencing-data/staged_external_data
export ANALYSIS_RESULTS_S3_URI=s3://lsmc-dayoa-analysis-results-usw2
export EXECUTING_ENTITY="${USER:-ubuntu}"
export ANALYSIS_ID=dayoa
export ANALYSIS_SAMPLES=etc/analysis_samples_template.tsv
export STAGE_CFG_DIR="$PWD/tmp-stage-config/$CLUSTER_NAME"
export EXPORT_DIR="$PWD/tmp-export/$ANALYSIS_ID"
export EXPORT_S3_URI="$ANALYSIS_RESULTS_S3_URI/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID/"

dyec preflight --profile "$AWS_PROFILE" --region-az "$REGION_AZ" --config "$DAY_EX_CFG"
dyec create --profile "$AWS_PROFILE" --region-az "$REGION_AZ" --config "$DAY_EX_CFG"

dyec samples stage "$ANALYSIS_SAMPLES" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --reference-s3-uri "$REF_S3_URI" \
  --control-data-s3-uri "$CONTROL_DATA_S3_URI" \
  --stage-s3-uri "$STAGE_S3_URI" \
  --config-dir "$STAGE_CFG_DIR"

dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --stage-dir "/fsx/staging/staged_external_sequencing_data/remote_stage_<timestamp>" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$EXECUTING_ENTITY" \
  --git-tag 2.0.25

dyec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --source-path "/fsx/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID" \
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
