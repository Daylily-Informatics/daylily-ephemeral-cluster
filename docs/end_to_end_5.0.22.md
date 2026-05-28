# DayEC End-To-End Runbook (5.0.22)

Status: starter operator document.

Version proof:

- `git describe --tags --dirty --always` -> `5.0.22`
- `source ./activate && dyec --json version` -> `{"version": "5.0.22"}`

This runbook covers the current DRA-first DayEC path: create a disposable
ParallelCluster, validate supported headnode access, attach or stage inputs,
launch DayOA, export one completed analysis directory to S3, verify the export
receipt, and only then prepare cluster deletion.

## Safety Boundary

Cluster creation is live AWS work and will create billable resources.

Cluster deletion is destructive. Treat delete requests as approval to inspect or
dry-run only until the operator gives a separate explicit confirmation for the
exact cluster. Do not answer destructive prompts or pass `--yes` before that
confirmation.

Do not rely on defaults for profile, region, cluster name, input buckets,
analysis identity, DayOA tag, export destination, Dewey URL, or Dewey token.
Missing values should stop the run.

## 1. Activate And Verify

```bash
cd /Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster
source ./activate
dyec --json version
dyec runtime status
dyec info
aws --version
pcluster version
session-manager-plugin
```

Expected:

- `dyec` reports `5.0.22`
- runtime backend is the DayEC conda environment
- AWS CLI, ParallelCluster CLI, and Session Manager plugin are available

## 2. Set Explicit Run Values

Fill these before creating or launching anything.

```bash
export AWS_PROFILE=lsmc
export REGION=us-west-2
export REGION_AZ=us-west-2d
export CLUSTER_NAME=<cluster-name>
export DAY_EX_CFG=<absolute-path-to-cluster-request-yaml>

export REF_S3_URI=s3://lsmc-dayoa-references-usw2
export CONTROL_DATA_S3_URI=s3://lsmc-dayoa-control-data-usw2
export STAGE_S3_URI=s3://lsmc-ssf-sequencing-data/staged_external_data
export ANALYSIS_RESULTS_S3_URI=s3://lsmc-dayoa-analysis-results-usw2

export EXECUTING_ENTITY=<operator-or-project>
export ANALYSIS_ID=<analysis-id>
export DAYOA_GIT_TAG=<explicit-dayoa-tag>
export ANALYSIS_SAMPLES=<analysis_samples.tsv>
export STAGE_CFG_DIR="$PWD/tmp-stage-config/$CLUSTER_NAME"
export EXPORT_DIR="$PWD/tmp-export/$ANALYSIS_ID"
export EXPORT_S3_URI="$ANALYSIS_RESULTS_S3_URI/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID/"
```

Sanity checks:

```bash
aws sts get-caller-identity --profile "$AWS_PROFILE"
aws s3 ls "$REF_S3_URI" --profile "$AWS_PROFILE" --region "$REGION"
aws s3 ls "$CONTROL_DATA_S3_URI" --profile "$AWS_PROFILE" --region "$REGION"
aws s3 ls "$STAGE_S3_URI" --profile "$AWS_PROFILE" --region "$REGION"
aws s3 ls "$EXPORT_S3_URI" --profile "$AWS_PROFILE" --region "$REGION"
```

The export destination must be empty or intentionally unused for this analysis
ID before export.

## 3. Preflight

```bash
dyec preflight \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG" \
  --non-interactive
```

Preflight must pass before create. It checks AWS identity, IAM, quota,
repository catalog validity, S3 role access, network resources, and rendered
cluster demand.

## 4. Create Cluster

```bash
dyec create \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG" \
  --non-interactive
```

Wait for `dyec create` to return successfully. ParallelCluster infrastructure
existing is not enough; DayEC readiness means headnode configuration and
readiness validation also completed.

Confirm cluster state:

```bash
dyec cluster list --profile "$AWS_PROFILE" --region "$REGION" --verbose
dyec --json cluster describe --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec headnode info --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
```

## 5. Validate Headnode Access

Use the supported SSM path. The interactive session must land as `ubuntu`.

```bash
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

Expected:

- `whoami` -> `ubuntu`
- `pwd` -> `/home/ubuntu`
- `day-clone` and `tmux` are available

If this fails, run `dyec headnode configure` rather than using raw SSH or root:

```bash
dyec headnode configure \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

## 6. Input Path A: Sample Manifest

Use this path when inputs are represented by `analysis_samples.tsv`.

```bash
dyec samples stage "$ANALYSIS_SAMPLES" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --reference-s3-uri "$REF_S3_URI" \
  --control-data-s3-uri "$CONTROL_DATA_S3_URI" \
  --stage-s3-uri "$STAGE_S3_URI" \
  --config-dir "$STAGE_CFG_DIR"
```

Capture the exact remote stage directory printed by the staging command. It
should be under `/fsx/staging/staged_external_sequencing_data/...`.

Launch with that exact stage path:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --stage-dir "/fsx/staging/staged_external_sequencing_data/<remote-stage-dir>" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$EXECUTING_ENTITY" \
  --git-tag "$DAYOA_GIT_TAG"
```

## 7. Input Path B: Run-Folder Mount

Use this path when raw run folders should remain in S3 and be read through a
temporary read-only run DRA.

```bash
export RUN_S3_URI=s3://<sequencer-run-bucket>/<run-prefix>/
export RUN_MOUNT_ID=<run-mount-id>

dyec --json mounts create "$RUN_S3_URI" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --mount-id "$RUN_MOUNT_ID" \
  --platform ILMN \
  --read-only \
  --batch-import-metadata-on-create \
  --auto-import NEW,CHANGED \
  --wait

dyec --json mounts verify \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --mount-id "$RUN_MOUNT_ID"
```

Run mounts are input paths. They are not export sources.

Launch using an explicit run context:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --run-context-file ./runs.tsv \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$EXECUTING_ENTITY" \
  --git-tag "$DAYOA_GIT_TAG" \
  --dy-command "bin/day_run <explicit-rule-or-target> --config run_context_file=config/runs.tsv -p -j <jobs> -k"
```

## 8. Monitor Workflow

Record the `<session>` printed by `dyec workflow launch`.

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
  --lines 100

dyec headnode jobs \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

Terminal success requires the workflow status to show success and no remaining
unexpected Slurm jobs for the analysis.

## 9. Export Completed Analysis

Export only the completed analysis root:

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
- `task_lifecycle: SUCCEEDED`
- `detached: true`
- `delete_data_in_file_system: false`
- `source_path` is the exact analysis directory
- `destination_s3_uri` ends in `<executing_entity>/<analysis_id>/`
- `fsx_root` maps to `s3_root`
- `dayoa_analysis_root` maps to `dayoa_s3_root`

For command-catalog artifact registration, pass explicit Dewey values on export
or auto-export. Missing catalog policy, DayOA evidence manifest, Dewey URL,
token, or invalid Dewey response is a hard failure.

## 10. Prepare Teardown

Dry-run first:

```bash
dyec delete --dry-run \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

Before live delete, state the exact destructive effect and wait for separate
operator confirmation for this cluster:

```text
CONFIRM DELETE CLUSTER <cluster-name>
```

After confirmation:

```bash
dyec delete \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

Verify disappearance from ParallelCluster, CloudFormation, FSx, and DRA
surfaces before closing the run.

## Evidence Checklist

- Activated checkout and `dyec --json version`
- AWS identity and S3 URI checks
- Preflight result
- `dyec create` completion
- Cluster describe output
- Headnode `whoami`, `pwd`, `day-clone`, and `tmux`
- Staging output or run-mount create/verify output
- Workflow session id, status, logs, and Slurm state
- Export receipt path and `fsx_export.yaml`
- Delete dry-run
- Separate live-delete confirmation, if deletion is performed
- Final cluster/stack/FSx/DRA disappearance proof, if deletion is performed
