# Ultra Rapid Start

Use this only when AWS setup, quotas, Session Manager, the DYEC config, and the
selected DayOA command/input contract are already known-good. This is the
`18.0.46` catalog-first path; it performs real cloud operations when `--dry-run`
is removed.

```bash
source ./activate

export AWS_PROFILE=<named-profile>
export REGION=us-west-2
export REGION_AZ=us-west-2d
export CLUSTER=<cluster-name>
export DAY_EX_CFG="$HOME/.config/daylily/daylily_ephemeral_cluster.yaml"
export ANALYSIS_ID=<analysis-id>
export EXECUTING_ENTITY="$CLUSTER"
export MANIFEST_DIR=./config
export STAGING_S3_URI=s3://<bucket>/<temporary-dyec-relay-prefix>/
export EXPORT_DIR="$PWD/export-receipts/$ANALYSIS_ID"
export EXPORT_S3_URI=s3://<analysis-results-bucket>/<prefix>/$EXECUTING_ENTITY/$ANALYSIS_ID/

dyec --json version
dyec preflight --profile "$AWS_PROFILE" --region-az "$REGION_AZ" --config "$DAY_EX_CFG"
dyec create --profile "$AWS_PROFILE" --region-az "$REGION_AZ" --config "$DAY_EX_CFG"
```

For repeated work, these three values can instead be saved locally with
`dyec set-vars --profile ... --region ... --region-az ...`; explicit flags still
win and direct `aws`/`pcluster` calls still use their normal environment setup.

## Render first

Inspect the exact catalog contract. The active catalog targets DayOA `15.0.27`.
For a six-manifest command, the directory must contain the complete validated
manifest set; a legacy `--stage-dir` is not interchangeable with
`--manifest-dir`.

```bash
dyec --json catalog show <command-id>

dyec --json catalog render <command-id> \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$EXECUTING_ENTITY" \
  --manifest-dir "$MANIFEST_DIR" \
  --payload-staging-s3-uri "$STAGING_S3_URI" \
  --dry-run
```

For a `run_context` command, replace the manifest options with the verified
`--run-context-file ./runs.tsv` required by that catalog row. For a
`sample_manifest` or `sample_manifest_v12` row, use the explicit staged input
shape from `dyec catalog show` or `dyec samples run`.

## Launch, monitor, export

After the rendered command is reviewed, run the same catalog command with
`launch` rather than `render` and remove `--dry-run`. Then monitor and export
the exact analysis root:

```bash
dyec --json workflow status \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --session "$ANALYSIS_ID"

dyec analysis visit \
  --analysis-root "/fsx/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID" \
  --mode export \
  --intent "export completed analysis results" \
  --s3-visit-uri "$EXPORT_S3_URI"

dyec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --source-path "/fsx/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID" \
  --destination-s3-uri "$EXPORT_S3_URI" \
  --output-dir "$EXPORT_DIR"
```

Verify `fsx_export.yaml` reports `status: success`, `task_lifecycle:
SUCCEEDED`, and `detached: true`. A live `dyec delete` is destructive and needs
separate approval for the exact cluster; start with `dyec delete --dry-run`.
