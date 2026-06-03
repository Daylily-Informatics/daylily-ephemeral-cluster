# Quickest Start

This is the current public-safe operator path. It uses the DRA-backed FSx model, explicit config, SSM headnode access as `ubuntu`, catalog-backed DayOA commands, and explicit export receipts.

## 1. Activate The Checkout

```bash
cd /path/to/daylily-ephemeral-cluster
source ./activate
dyec --json version
dyec --help
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
- missing dependencies fail clearly instead of being guessed

## 2. Set Variables

```bash
export AWS_PROFILE=<non-default-profile>
export REGION=us-west-2
export REGION_AZ=us-west-2d
export CLUSTER_NAME=<cluster-name>
export DAY_EX_CFG="$HOME/.config/daylily/daylily_ephemeral_cluster.yaml"
export REF_S3_URI=s3://<reference-bucket>
export CONTROL_DATA_S3_URI=s3://<control-data-bucket>
export STAGE_S3_URI=s3://<staging-bucket>/<prefix>
export ANALYSIS_RESULTS_S3_URI=s3://<analysis-results-bucket>/<prefix>
export EXECUTING_ENTITY=ubuntu
export ANALYSIS_ID=<analysis-id>
export ANALYSIS_SAMPLES=./analysis_samples.tsv
export STAGE_CFG_DIR="$PWD/tmp-stage-config/$CLUSTER_NAME"
export EXPORT_DIR="$PWD/tmp-export/$ANALYSIS_ID"
export EXPORT_S3_URI="$ANALYSIS_RESULTS_S3_URI/$EXECUTING_ENTITY/$ANALYSIS_ID/"
```

Sanity checks:

```bash
aws sts get-caller-identity --profile "$AWS_PROFILE"
aws s3 ls "$REF_S3_URI" --profile "$AWS_PROFILE" --region "$REGION"
dyec --json repositories commands
```

## 3. Preflight

```bash
dyec preflight \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG"
```

Preflight checks identity, IAM, quotas, repository catalog validity, bucket access, network resources, and rendered cluster demand. Treat failures as contract gaps to fix explicitly.

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
exec bash -l
whoami
pwd
command -v day-clone
command -v tmux
command -v squeue
exit
```

Expected user is `ubuntu` and the login shell starts in `/home/ubuntu`.

## 5. Sample-Manifest Analysis

Use this path when inputs are represented by `analysis_samples.tsv`. `dyec samples run` is the preferred command because it stages manifests, validates the catalog command, launches the workflow, and can trigger export.

```bash
dyec samples run "$ANALYSIS_SAMPLES" \
  --command-id illumina_snv_alignstats \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --reference-s3-uri "$REF_S3_URI" \
  --control-data-s3-uri "$CONTROL_DATA_S3_URI" \
  --stage-s3-uri "$STAGE_S3_URI" \
  --config-dir "$STAGE_CFG_DIR" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$EXECUTING_ENTITY" \
  --export-destination-s3-uri "$EXPORT_S3_URI" \
  --export-trigger on-success \
  --dry-run
```

Remove `--dry-run` only after the rendered command, staging paths, export destination, and cluster state are correct.

## 6. Run-Folder Analysis

Use this path when raw run directories should stay in S3 and be read through an ephemeral run DRA. Run mounts can legitimately spend many minutes in `CREATING`, especially for large run directories; use a timeout comfortably above 30 minutes when the CLI supports one.

```bash
dyec --json mounts create "s3://<sequencing-run-bucket>/<run-prefix>/" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --platform ILMN \
  --read-only \
  --wait \
  --timeout-seconds 3600

dyec --json mounts verify \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --mount-id <mount_id>
```

Create a local `runs.tsv` with explicit `SOURCE_S3_URI`, `MOUNT_ID`, and platform values, then launch a catalog run-analysis command:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --repository daylily-omics-analysis \
  --git-tag 2.0.41 \
  --run-context-file ./runs.tsv \
  --analysis-id run-qc \
  --executing-entity "$EXECUTING_ENTITY" \
  --genome hg38_broad \
  --jobs 5 \
  --target produce_illumina_run_qc \
  --snakemake-extra "--config run_context_file=config/runs.tsv"
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

Read-only headnode checks are acceptable:

```bash
dyec headnode jobs --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
```

Do not cancel, requeue, drain, resume, or restart Slurm components without separate approval for that exact action.

## 8. Export Completed Analysis Directory

Export directly from the completed analysis directory on FSx:

```bash
dyec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --source-path "/fsx/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID" \
  --destination-s3-uri "$EXPORT_S3_URI" \
  --output-dir "$EXPORT_DIR"

cat "$EXPORT_DIR/fsx_export.yaml"
```

Expected receipt values:

- `status: success`
- `detached: true`
- `delete_data_in_file_system: false`
- `source_path: /analysis_results/<executing_entity>/<analysis_id>/`
- `destination_s3_uri` ending in `<executing_entity>/<analysis_id>/`
- `fsx_root: /fsx/analysis_results/<executing_entity>/<analysis_id>/`
- `s3_root: s3://.../<executing_entity>/<analysis_id>/`
- `dayoa_analysis_root` under `fsx_root` when exporting DayOA
- `dayoa_s3_root` under `s3_root` when exporting DayOA

For catalog commands with an explicit `artifact_registration` policy, Dewey registration is a DYEC export concern. Pass `--artifact-registration-command-id`, `--dewey-url`, and `--dewey-token-env` with the export or auto-export launch. DayOA does not receive Dewey or QEO configuration.

## 9. Delete

Delete only after export verification. The live delete is destructive:

```bash
dyec delete --dry-run \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

Run the non-dry-run delete only after a separate explicit approval for that exact cluster deletion.
