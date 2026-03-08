# Operations

This doc covers the supported operator workflows after the local environment is ready and a cluster exists.

## Connect To A Cluster

List clusters in a region:

```bash
pcluster list-clusters --region "$REGION"
```

SSH to the head node with the helper script:

```bash
./bin/daylily-ssh-into-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --pem ~/.ssh/<your-key>.pem
```

When flags are omitted the helper falls back to interactive selection.

## Validate The Head Node

Daylily bootstraps the head node automatically after cluster creation. Validate that bootstrap before staging data or launching a workflow.

From your laptop, re-run the head-node bootstrap if needed:

```bash
./bin/daylily-cfg-headnode \
  --pem ~/.ssh/<your-key>.pem \
  --region "$REGION" \
  --profile "$AWS_PROFILE" \
  --cluster "$CLUSTER_NAME"
```

Once connected to the head node:

```bash
cd ~/projects/daylily-ephemeral-cluster
conda activate DAY-EC

python -m daylily_ec info
day-clone --list
```

Optional remote validation workflow from your laptop:

```bash
./bin/daylily-run-ephemeral-cluster-remote-tests \
  ~/.ssh/<your-key>.pem \
  "$REGION" \
  "$AWS_PROFILE" \
  --cluster "$CLUSTER_NAME" \
  --yes
```

That helper clones the default workflow repository and launches a tmux-backed test run on the head node.

## Stage Sample Data On The Head Node

Use the head-node helper when the input TSV and sample sources are already accessible from the cluster environment.

```bash
cd ~/projects/daylily-ephemeral-cluster
./bin/daylily-stage-analysis-samples-headnode /path/to/analysis_samples.tsv

# Optional custom target
./bin/daylily-stage-analysis-samples-headnode \
  /path/to/analysis_samples.tsv \
  /fsx/custom_stage_dir
```

This flow stages data under the target directory and writes `samples.tsv` and `units.tsv` there. The bundled template lives at [`../etc/analysis_samples_template.tsv`](../etc/analysis_samples_template.tsv).

## Stage Sample Data From A Laptop

Use the laptop-side helper when you want to validate sources locally, upload to the FSx-backed S3 repository, and generate config files without an interactive SSH session.

```bash
./bin/daylily-stage-samples-from-local-to-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --reference-bucket "s3://myorg-daylily-omics-analysis-${REGION}" \
  --config-dir ./generated-config \
  ./analysis_samples.tsv
```

Important details:

- The script stages through the S3-backed FSx data repository, not by copying files over SSH.
- Its default staging base is `/data/staged_sample_data`, which appears on the cluster as `/fsx/data/staged_sample_data/remote_stage_<timestamp>/`.
- It writes local `samples.tsv` and `units.tsv` copies into `--config-dir` or next to the source TSV if `--config-dir` is omitted.

## Launch A Workflow From A Laptop

Use the launcher after staging files and validating the head node.

For data staged with the laptop-side helper above, point the launcher at the matching stage base:

```bash
./bin/daylily-run-omics-analysis-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --pem ~/.ssh/<your-key>.pem \
  --stage-base /fsx/data/staged_sample_data
```

For data staged directly on the head node into `/fsx/staged_sample_data`, the default `--stage-base` is already correct:

```bash
./bin/daylily-run-omics-analysis-headnode \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --pem ~/.ssh/<your-key>.pem
```

Useful launch flags:

- `--stage-dir` for an explicit staging directory
- `--repository` to choose a different workflow key from [`../config/daylily_available_repositories.yaml`](../config/daylily_available_repositories.yaml)
- `--project` to pass a budget/project into `dyoainit`
- `--target`, `--jobs`, `--aligners`, `--dedupers`, `--snv-callers` to shape the run
- `--dry-run` to emit the `dy-r` command without executing the full workload

The launcher clones the workflow repository via `day-clone`, copies the staged config files into the repo, and starts the run inside a tmux session on the head node.

## Monitor Cluster And Workload State

Infrastructure status:

```bash
pcluster describe-cluster -n "$CLUSTER_NAME" --region "$REGION"
python -m daylily_ec drift --state-file ~/.config/daylily/state_<cluster>_<timestamp>.json --profile "$AWS_PROFILE"
```

Scheduler and tmux status on the head node:

```bash
sinfo
squeue -o "%.18i %.8u %.8T %.10M %.30N %.50j"
tmux ls
tmux attach -t <session-name>
```

## Export Results Back To S3

Launch an FSx export task from your laptop and store the task outcome locally:

```bash
./bin/daylily-export-fsx-to-s3-from-local \
  --cluster "$CLUSTER_NAME" \
  --target-uri analysis_results/ubuntu/<run-or-project> \
  --region "$REGION" \
  --profile "$AWS_PROFILE" \
  --output-dir ./fsx-export-status
```

`--target-uri` accepts an FSx-relative path or an S3 URI under the filesystem export root. The helper writes `fsx_export.yaml` into `--output-dir`.

## Delete A Cluster

When the workload is complete and results have been exported:

```bash
./bin/daylily-delete-ephemeral-cluster \
  --region "$REGION" \
  --cluster-name "$CLUSTER_NAME" \
  --profile "$AWS_PROFILE"
```

Add `--yes` to skip the FSx deletion confirmation prompt.

## Related Docs

- [quickest_start.md](quickest_start.md)
- [overview.md](overview.md)
- [DAY_EC_ENVIRONMENT.md](DAY_EC_ENVIRONMENT.md)
