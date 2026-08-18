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

For the DRA/docs, local-context, and DayOA-pin surfaces:

```bash
python -m pytest \
  tests/test_repository_catalog.py \
  tests/test_cli_registry_v2.py \
  tests/test_packaged_defaults.py \
  tests/test_run_mounts.py \
  tests/test_export.py \
  tests/test_cli_context.py \
  tests/test_cli_docs_contract.py \
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

The active DayOA pin is `15.0.26`. Inspect it through the public surface and
verify both checked-in catalog copies before relying on launch examples:

```bash
dyec --json catalog show hybrid_ilmn_ont_hiomr_kitchensink
dyec --json catalog show illumina_run_qc

rg -n 'default_ref: "15\.0\.5"|git_tag: "?15\.0\.5"?' \
  config/daylily_pipeline_command_catalog.yaml \
  daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml
```

`validation_pending: true` in catalog output is expected when a command's
target tag differs from its historical `validated_version`; it is not a failed
catalog validation or permission to relabel old receipts.

## Docs Sweeps

The supported operator docs must match the `18.0.44` root help, current `15.0.26`
catalog target, project-local context contract, and provider-neutral export
surface. `tests/test_cli_docs_contract.py` checks those durable claims. Keep
old evidence in `docs/archive/**`, dated reports, or historical ledgers rather
than rewriting it as current guidance.

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
