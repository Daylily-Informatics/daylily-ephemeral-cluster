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
- `pcluster version` reports `3.15.0`
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
export EXPORT_S3_ROOT="$ANALYSIS_RESULTS_S3_URI/"
export EXPORT_S3_URI="$EXPORT_S3_ROOT$CLUSTER_NAME/$ANALYSIS_ID/"
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

For a pcluster-only schema check, validate only a rendered cluster YAML:

```bash
pcluster validate-cluster-configuration --cluster-configuration <rendered-cluster.yaml> --region "$REGION"
```

Do not run `pcluster create-cluster`, `pcluster update-cluster`, or `pcluster delete-cluster` while only validating the pinned CLI upgrade.

## 4. Create

```bash
dyec create \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG" \
  --global-spot-max-cost 9.99 \
  --spot-cost-limit-pct 1.7 \
  --write-spot-pricing-warn-threshold 6.00
```

Wait for the CLI to return successfully. The cluster is not DayEC-ready just because ParallelCluster reports that infrastructure exists.
`dyec create` writes `config/<cluster>_spot_price_summary_<run_id>.json` and
runtime compute nodes append high-price JSONL exceptions to
`spot_price_warn_exception_messages.log` beside the normal spot logs.

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
day-clone --list
day-clone --check-auth --repository daylily-omics-analysis --git-tag <dayoa_version>
command -v tmux
command -v squeue
exit
```

Expected user is `ubuntu` and the login shell starts in `/home/ubuntu`. `day-clone --list` must print the repository rows and clone syntax from the headnode catalog. The authentication check must resolve the requested private DayOA ref before any analysis checkout is created.

For any new DayOA analysis, resolve the intended DayOA release tag before launch and pass it explicitly. Manual launches use `day-clone -t <dayoa_version> -d <analysis_id>`; DYEC launches use `--git-tag <dayoa_version>`. Do not rely on default refs.

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
  --export-destination-s3-uri "$EXPORT_S3_ROOT" \
  --export-trigger on-success \
  --dry-run
```

Remove `--dry-run` only after the rendered command, staging paths, export destination, and cluster state are correct.

For `dyec samples run` and `dyec workflow launch`, `--export-destination-s3-uri`
can be a full destination or an export root. Export roots are expanded to
`<root>/<cluster>/<analysis-id>/`.

## 6. Run-Folder Analysis

Use this path when raw run directories should stay in S3 and be read through an ephemeral run DRA. Run mounts can legitimately spend more than 40 minutes in `CREATING`, especially for large run directories; use a timeout comfortably above that window when the CLI supports one.

```bash
dyec --json mounts create "s3://<sequencing-run-bucket>/<run-prefix>/" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --platform ILMN \
  --read-only \
  --wait \
  --timeout-seconds 5400

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
  --git-tag 10.0.69 \
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
  --stream snakemake \
  --lines 50
```

The status `state` is `RUNNING`, `SUCCEEDED`, `FAILED`, or `UNKNOWN`. Check
`controller`, `snakemake_log`, `last_progress_at`, `jobs`, `slurm`, and
`terminal` together. Queue emptiness and the status command's own RC are never
workflow success. For a manual recovery run, use explicit `--repo-path` plus
`--controller-pid`; add the exact `--snakemake-log` only when PID/open-file
correlation is unavailable. DYEC never guesses the newest master log.

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
- `destination_s3_uri` ending in `<cluster>/<analysis_id>/` for launch auto-export, or `<executing_entity>/<analysis_id>/` for explicit direct export
- `fsx_root: /fsx/analysis_results/<executing_entity>/<analysis_id>/`
- `s3_root: s3://.../<cluster>/<analysis_id>/` for launch auto-export, or `s3://.../<executing_entity>/<analysis_id>/` for explicit direct export
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
