# Quickest Start

This is the guided current operator path. It includes checks after each stage and uses the DRA-backed FSx model.

## 1. Activate The Checkout

```bash
cd /path/to/daylily-ephemeral-cluster
source ./activate
dyec version
dyec runtime status
dyec info
aws --version
pcluster version
session-manager-plugin
```

Expected:

- `dyec` and `daylily-ec` resolve to the same CLI
- runtime backend is `day-ec-conda`
- `aws`, `pcluster`, and `session-manager-plugin` are available

## 2. Set Variables

```bash
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
```

Sanity checks:

```bash
aws sts get-caller-identity --profile "$AWS_PROFILE"
aws s3 ls "$REF_BUCKET" --profile "$AWS_PROFILE" --region "$REGION"
```

## 3. Preflight

```bash
dyec preflight \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG"
```

Preflight checks identity, IAM, quotas, repository catalog validity, bucket access, network resources, and rendered cluster demand.

## 4. Create

```bash
dyec create \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG"
```

Wait for the CLI to return successfully. The cluster is not DayEC-ready just because ParallelCluster reports that infrastructure exists.

Sanity checks:

```bash
dyec cluster list --profile "$AWS_PROFILE" --region "$REGION" --verbose

dyec headnode connect \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

On the headnode:

```bash
whoami
pwd
command -v day-clone
command -v tmux
exit
```

Expected user is `ubuntu` and working directory is `/home/ubuntu`.

## 5. Sample-Manifold Analysis

Use this path when inputs are represented by `analysis_samples.tsv`.

```bash
dyec samples stage "$ANALYSIS_SAMPLES" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --reference-bucket "$REF_BUCKET" \
  --config-dir "$STAGE_CFG_DIR"
```

Use the exact remote stage directory printed by the staging helper:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --stage-dir "/fsx/data/staged_sample_data/remote_stage_<timestamp>" \
  --destination "$ANALYSIS_DIR" \
  --git-tag 1.0.16
```

## 6. Run-Folder Analysis

Use this path when raw run directories should stay in S3 and be read through an ephemeral run DRA.

```bash
dyec --json mounts create "s3://sequencer-run-bucket/runs/RUN123/" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --platform ILMN \
  --read-only \
  --wait

dyec --json mounts verify \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --mount-id RUN123
```

Create a local `runs.tsv` for DayOA run-analysis commands, then launch:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --run-context-file ./runs.tsv \
  --destination run-qc \
  --git-tag 1.0.16 \
  --dy-command "bin/day_run produce_illumina_run_qc --config run_context_file=config/runs.tsv -p -j 5 -k"
```

## 7. Monitor

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
  --lines 50
```

## 8. Export Completed Analysis Directory

Export directly from the completed analysis directory on FSx:

```bash
dyec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --source-path "/fsx/analysis_results/ubuntu/$ANALYSIS_DIR" \
  --destination-s3-uri "$EXPORT_S3_URI" \
  --output-dir "$EXPORT_DIR"

cat "$EXPORT_DIR/fsx_export.yaml"
```

Expected receipt values:

- `status: success`
- `detached: true`
- `delete_data_in_file_system: false`
- `source_path: /analysis_results/ubuntu/<analysis_dir>/`
- `destination_s3_uri` matching `s3://bucket/analysis_results/ubuntu/<analysis_dir>/`

## 9. Delete

Delete only after export verification:

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
