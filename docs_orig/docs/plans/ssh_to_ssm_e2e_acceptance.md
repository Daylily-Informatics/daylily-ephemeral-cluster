# SSH-to-SSM End-to-End Runner

The accepted operator flow is implemented by [`bin/daylily-ssh-to-ssm-e2e`](../../bin/daylily-ssh-to-ssm-e2e), which executes [`daylily_ec.ssh_to_ssm_e2e_runner`](../../daylily_ec/ssh_to_ssm_e2e_runner.py).

## What It Covers

The runner exercises the supported lifecycle against a real AWS sandbox account:

1. prepare a temporary config with a unique cluster name
2. run `daylily-ec preflight`
3. run `daylily-ec create` and wait for the CLI to return only after the post-`pcluster` headnode configuration finishes
4. resolve the headnode instance ID and wait for SSM readiness
5. validate that `SSM-SessionManagerRunShell` is configured to land in the `ubuntu` login shell
6. optionally smoke a live Session Manager open/exit through a PTY-capable local shell
7. validate headnode bootstrap over SSM as `ubuntu`
8. stage sample data from the laptop through the S3/FSx-backed path
9. launch the workflow from the laptop against the exact remote stage directory returned by the staging step
10. inspect tmux and Slurm state over SSM
11. export results back to S3
12. optionally delete the cluster

Each stage is recorded in a machine-readable JSON summary.

## Required Inputs

- `--profile`
- `--region`
- `--region-az`
- `--reference-bucket`
- `--analysis-samples`

Useful optional flags:

- `--config` to point at the base Daylily config to copy and override
- `--cluster-name` to force a specific cluster name instead of the generated timestamped name
- `--workflow-live` to run the workflow without `--dry-run`
- `--interactive-session-smoke` to attempt a live open/exit probe of `daylily-ssh-into-headnode`
- `--skip-export` to skip the export step
- `--delete-cluster --allow-destroy` to opt into destructive teardown
- `--output-json` to choose the summary file path

## Example

```bash
bin/daylily-ssh-to-ssm-e2e \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG" \
  --reference-bucket "$REF_BUCKET" \
  --analysis-samples /path/to/analysis_samples.tsv \
  --interactive-session-smoke
```

The default output summary is written to:

```text
tmp-e2e-results/<cluster-name>.json
```

## Safety Defaults

- The runner is non-destructive by default.
- Cluster deletion is skipped unless both `--delete-cluster` and `--allow-destroy` are supplied.
- Workflow launch defaults to `--dry-run`; pass `--workflow-live` for a real launch.

## Session Manager Contract

Interactive access now depends on the session document contract, not PEMs and not manual `sudo` repair steps.

The runner expects `SSM-SessionManagerRunShell` to be configured with:

- `runAsEnabled: true`
- `runAsDefaultUser: ubuntu`
- `shellProfile.linux` that lands in the `ubuntu` login shell, for example by using `exec bash -l` or sourcing the managed Daylily bootstrap

If that contract is missing, the runner fails before attempting interactive access.
