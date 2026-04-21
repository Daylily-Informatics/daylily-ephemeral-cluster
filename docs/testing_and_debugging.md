# Testing And Debugging

This repo has three distinct validation layers:

1. local environment/runtime checks
2. unit and policy tests
3. AWS-backed end-to-end validation

## Build And Activate `DAY-EC`

The supported checkout entry point is:

```bash
source ./activate
```

Quick sanity checks:

```bash
daylily-ec version
daylily-ec runtime status
aws --version
pcluster version
session-manager-plugin
```

If that shell is wrong, fix the environment first. Do not debug AWS behavior from a broken local toolchain.

## Targeted Pytest Runs

Useful targeted tests:

```bash
pytest -q tests/test_supported_no_pem_refs.py
pytest -q tests/test_environment_contract.py
pytest -q tests/test_ssm.py
pytest -q tests/test_script_entrypoints.py
pytest -q tests/test_ssm_e2e_runner.py
pytest -q tests/test_workflow.py
```

When you are editing a specific module, keep the test loop narrow. Run the whole suite later.

## Broader Test Runs

Typical broader runs:

```bash
pytest -q
pytest --maxfail=1 -q
pytest -q tests/test_ssm.py tests/test_workflow.py tests/test_ssm_e2e_runner.py
```

## Policy Tests

Two repo policy tests matter for the supported doc/runtime contract:

```bash
pytest -q tests/test_supported_no_pem_refs.py
pytest -q tests/test_environment_contract.py
```

They guard:

- supported docs and scripts staying free of retired key-file guidance
- the `environment.yaml` and `pyproject.toml` contract
- legacy env files staying archived/quarantined

## AWS-Backed End-To-End Runner

The repo ships a real AWS-backed acceptance runner:

```bash
python -m daylily_ec.ssh_to_ssm_e2e_runner --help
```

It exercises the supported lifecycle through the actual CLI/helpers:

- `daylily-ec preflight`
- `daylily-ec create`
- `daylily-ec headnode connect`
- `bin/daylily-stage-samples-from-local-to-headnode`
- `bin/daylily-run-omics-analysis-headnode`
- `daylily-ec export`
- optionally `daylily-ec delete`

### Example: Reuse An Existing Cluster

```bash
AWS_PROFILE="$AWS_PROFILE" python -m daylily_ec.ssh_to_ssm_e2e_runner \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster-name "$CLUSTER_NAME" \
  --reuse-existing-cluster \
  --reference-bucket "$REF_BUCKET" \
  --analysis-samples "$ANALYSIS_SAMPLES" \
  --workflow-live \
  --output-json "$PWD/tmp-e2e-results/$CLUSTER_NAME.json"
```

### Example: Full Lifecycle Run

```bash
AWS_PROFILE="$AWS_PROFILE" python -m daylily_ec.ssh_to_ssm_e2e_runner \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG" \
  --reference-bucket "$REF_BUCKET" \
  --analysis-samples "$ANALYSIS_SAMPLES" \
  --workflow-live \
  --output-json "$PWD/tmp-e2e-results/run.json"
```

Important runner flags:

- `--reuse-existing-cluster`
- `--cluster-name`
- `--workflow-live`
- `--workflow-timeout-minutes`
- `--interactive-session-smoke`
- `--skip-export`
- `--delete-cluster`
- `--allow-destroy`

The runner is non-destructive by default. Delete requires both delete flags.

## Where To Look When Something Fails

### Create/preflight failures

Start here:

```bash
daylily-ec preflight --profile "$AWS_PROFILE" --region-az "$REGION_AZ" --config "$DAY_EX_CFG" --debug
daylily-ec info
daylily-ec runtime explain
```

Then inspect:

- the terminal output from preflight/create
- Daylily state/config directories reported by `daylily-ec info`
- `pcluster describe-cluster --region "$REGION" -n "$CLUSTER_NAME"`

### Session Manager failures

Check:

```bash
aws ssm get-document \
  --name SSM-SessionManagerRunShell \
  --document-format JSON \
  --query Content \
  --output text \
  --region "$REGION" \
  --profile "$AWS_PROFILE"
```

Also verify the local plugin:

```bash
session-manager-plugin
```

### Headnode bootstrap issues

Try:

```bash
bin/daylily-cfg-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

Then reconnect and check:

```bash
whoami
command -v day-clone
```

### Workflow launch failures

Inspect on the headnode:

```bash
tmux ls
cat /home/ubuntu/daylily-runs/<session>/status.json
tail -n 100 /home/ubuntu/daylily-runs/<session>/tmux.log
```

### Export failures

Inspect:

```bash
cat "$EXPORT_DIR/fsx_export.yaml"
```

That file is the first place to look because it records success/error and the target path.

## A Good Debugging Sequence

When the failure is ambiguous, use this order:

1. `source ./activate`
2. `daylily-ec runtime status`
3. `daylily-ec preflight --debug ...`
4. `daylily-ec cluster-info ...`
5. `daylily-ec headnode connect ...`
6. inspect `/home/ubuntu/daylily-runs/<session>/`

That sequence is usually faster than jumping directly into AWS console tabs.
