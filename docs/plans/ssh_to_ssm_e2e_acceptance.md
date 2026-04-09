# End-to-End Acceptance Sketch: PEM-Free Daylily Operator Flow

## Goal

Prove that a normal Daylily operator can complete the supported lifecycle without any local PEM file:

1. create a cluster
2. connect to the headnode through SSM
3. validate headnode bootstrap
4. stage sample data from a laptop through the S3/FSx-backed path
5. launch a workflow from the laptop
6. reconnect and inspect tmux / Slurm state
7. rerun headnode bootstrap from the laptop
8. export results to S3
9. delete the cluster

This is an acceptance-test sketch, not a committed CI automation yet. It is intended to guide either:

- a manual release checklist run
- a future gated integration job in a dedicated AWS test account

## Scope

In scope:

- supported Daylily operator commands
- default config/template behavior
- Session Manager access
- SSM Run Command orchestration
- S3 plus FSx-backed laptop-side staging
- export and delete flows

Out of scope:

- legacy `bin/legacy/*`
- archived docs
- unsupported SSH escape hatches added manually in custom ParallelCluster YAML
- browser-only PCUI validation

## Environment

Use a dedicated AWS test account or sandbox with:

- AWS CLI v2
- `pcluster`
- `session-manager-plugin`
- a configured AWS profile with the Daylily operator permissions
- a region-specific Daylily reference bucket already cloned

Use a clean operator machine or disposable CI worker that confirms:

- `~/.ssh/` contains no PEM for the target region, or no PEM files at all
- `AWS_PROFILE` is set for the test run
- the repo checkout is activated with `source ./activate`

Recommended test variables:

```bash
export AWS_PROFILE=daylily-service
export REGION=us-west-2
export REGION_AZ=us-west-2d
export CLUSTER_NAME=daylily-ssm-e2e-$(date +%Y%m%d%H%M%S)
export REF_BUCKET=s3://<prefix>-daylily-omics-analysis-${REGION}
export DAY_EX_CFG="$HOME/.config/daylily/daylily_ephemeral_cluster.yaml"
```

## Data Fixture

Use a small `analysis_samples.tsv` fixture that exercises the supported laptop-side staging path without requiring a large production dataset. Prefer:

- one or two samples
- stable public or test-owned source URIs
- a fixture that produces `samples.tsv` and `units.tsv` deterministically

## Scenario

### 1. Preflight and create with no PEM present

Run:

```bash
test ! -e "$HOME/.ssh/${REGION}.pem"
daylily-ec preflight --region-az "$REGION_AZ" --profile "$AWS_PROFILE" --config "$DAY_EX_CFG"
daylily-ec create --region-az "$REGION_AZ" --profile "$AWS_PROFILE" --config "$DAY_EX_CFG"
```

Assert:

- no prompt or requirement for `ssh_key_name`
- no local PEM discovery step
- final connection hint is `daylily-ssh-into-headnode --profile ... --region ... --cluster ...`
- state file and rendered YAML artifacts are written
- cluster reaches `CREATE_COMPLETE`

Capture:

- create stdout/stderr
- state file path
- rendered cluster YAML path

### 2. Connect through Session Manager

Run:

```bash
./bin/daylily-ssh-into-headnode --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
```

Assert:

- Session Manager session opens successfully
- no PEM is requested or used
- operator can reach the correct shell context with `sudo -iu ubuntu` if needed

Capture:

- session transcript or terminal log

### 3. Validate headnode bootstrap

On the headnode:

```bash
sudo -iu ubuntu
cd ~/projects/daylily-ephemeral-cluster
source ~/projects/daylily-ephemeral-cluster/activate
eval "$(daylily-ec headnode init --emit-shell --non-interactive)"
daylily-ec info
day-clone --list
```

Assert:

- repo checkout exists
- `DAY-EC` activation succeeds
- `daylily-ec info` succeeds
- `day-clone --list` succeeds

### 4. Stage sample data from the laptop

Run:

```bash
./bin/daylily-stage-samples-from-local-to-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --reference-bucket "$REF_BUCKET" \
  --config-dir ./tmp-e2e-config \
  ./tests/fixtures/analysis_samples_small.tsv
```

Assert:

- no SSH or SCP is invoked
- local `samples.tsv` and `units.tsv` are written
- output reports an FSx-backed stage directory under `/fsx/data/staged_sample_data/remote_stage_<timestamp>/`

Capture:

- emitted remote FSx stage path
- generated local config files

### 5. Launch the workflow from the laptop

Run:

```bash
./bin/daylily-run-omics-analysis-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --stage-base /fsx/data/staged_sample_data \
  --dry-run
```

Repeat once without `--dry-run` if the fixture is approved for a live workflow launch.

Assert:

- the helper resolves the headnode by instance ID
- staging config is discovered over SSM
- a tmux session is created on the headnode
- the tool prints the reconnect helper and `tmux attach` command

Capture:

- tmux session name
- emitted reconnect command

### 6. Reconnect and inspect workload state

Run:

```bash
./bin/daylily-ssh-into-headnode --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
sudo -iu ubuntu
tmux ls
sinfo
squeue -o "%.18i %.8u %.8T %.10M %.30N %.50j"
```

Assert:

- expected tmux session exists
- Slurm commands are available
- job state is visible if the live workflow launch was executed

### 7. Rerun headnode bootstrap from the laptop

Run:

```bash
./bin/daylily-cfg-headnode --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
```

Assert:

- rerun succeeds with no PEM
- rerun is idempotent enough for an already-bootstrapped node

### 8. Export results to S3

Run:

```bash
daylily-ec export \
  --cluster-name "$CLUSTER_NAME" \
  --region "$REGION" \
  --target-uri analysis_results \
  --output-dir ./tmp-e2e-export
```

Assert:

- export completes successfully
- `fsx_export.yaml` is written locally
- export target points into the expected S3 repository path

### 9. Delete the cluster

Run:

```bash
daylily-ec delete --cluster-name "$CLUSTER_NAME" --region "$REGION"
```

Assert:

- delete flow completes successfully
- expected safety prompts remain intact
- no PEM is required anywhere in deletion

## Failure Variants

Run the same environment with controlled failure injection where practical:

- `session-manager-plugin` missing locally
- headnode never appears in SSM
- SSM Run Command times out
- SSM Run Command returns non-zero
- session opens outside the desired shell context and requires `sudo -iu ubuntu`

Expected result:

- failures are explicit and actionable
- no hidden fallback to PEM or raw SSH is attempted

## Evidence To Preserve

For each run, persist:

- create logs
- cluster state file
- rendered cluster YAML
- stage output including remote FSx path
- workflow launch output including tmux session name
- export metadata
- delete logs

Recommended location:

```text
artifacts/ssm-e2e/<timestamp>/
```

## Automation Shape

If this is automated later, split it into two layers:

1. `smoke`:
   create, connect, validate bootstrap, rerun bootstrap, delete

2. `full`:
   create, stage, launch, inspect, export, delete

The `smoke` layer is the best first candidate for a scheduled or gated integration run because it is cheaper and faster while still proving PEM-free access.

## Exit Criteria

This acceptance sketch can be considered implemented when there is a repeatable runner that:

- starts from a machine with no local PEM requirement
- completes the supported Daylily operator lifecycle
- records artifacts automatically
- fails hard on any regression back to PEM-based access
