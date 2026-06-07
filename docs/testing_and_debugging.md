# Testing And Debugging

This repo has four validation layers:

1. local environment checks
2. unit and contract tests
3. static sweeps for stale docs/config
4. optional AWS-backed end-to-end validation

## Activate

```bash
source ./activate
dyec --json version
dyec runtime status
aws --version
pcluster version
session-manager-plugin
```

The active ParallelCluster target is exactly `aws-parallelcluster==3.15.0`; `pcluster version` should report `3.15.0`.

If the active editable install is stale, refresh it:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

## Focused Tests

For the DRA docs and DayOA pin cutover:

```bash
python -m pytest \
  tests/test_repository_catalog.py \
  tests/test_cli_registry_v2.py \
  tests/test_packaged_defaults.py \
  tests/test_run_mounts.py \
  tests/test_export.py \
  tests/test_environment_contract.py \
  -q
```

Other useful focused runs:

```bash
python -m pytest tests/test_ssm.py -q
python -m pytest tests/test_script_entrypoints.py -q
python -m pytest tests/test_ssm_e2e_runner.py -q
python -m pytest tests/test_stage_samples_from_local_to_headnode.py -q
```

## Catalog Checks

The source and packaged catalogs must match:

```bash
cmp -s config/daylily_pipeline_command_catalog.yaml daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml
```

The current DayOA pin should be `8.0.0` everywhere in the catalog:

```bash
rg -n "2\\.0\\.29|0\\.7\\.758|\\b1\\.0\\.[0-9]\\b" \
  config/daylily_pipeline_command_catalog.yaml \
  daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml \
  tests
```

That command should return no stale runtime pin hits after the cutover.

## Docs Sweeps

Active docs should not carry retired export/template options or stale run-mount flags. Use the stale-term sweep recorded in the execution ledger, and keep any old evidence in `docs/archive/**` or historical ledgers rather than active operator docs.

## AWS-Backed E2E Runner

The E2E runner exercises the supported lifecycle through the CLI:

```bash
python -m daylily_ec.ssh_to_ssm_e2e_runner --help
```

Reuse an existing cluster:

```bash
AWS_PROFILE="$AWS_PROFILE" python -m daylily_ec.ssh_to_ssm_e2e_runner \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster-name "$CLUSTER_NAME" \
  --reuse-existing-cluster \
  --reference-s3-uri "$REF_S3_URI" \
  --control-data-s3-uri "$CONTROL_DATA_S3_URI" \
  --stage-s3-uri "$STAGE_S3_URI" \
  --analysis-samples "$ANALYSIS_SAMPLES" \
  --workflow-live \
  --output-json "$PWD/tmp-e2e-results/$CLUSTER_NAME.json"
```

Cluster deletion from the runner requires explicit delete flags.

## Failure Triage

Use this order:

1. `source ./activate`
2. `dyec runtime status`
3. `dyec preflight --debug ...`
4. `dyec cluster list ...`
5. `dyec headnode connect ...`
6. `dyec --json mounts list ...`
7. `dyec --json workflow status ...`
8. inspect `fsx_export.yaml`
