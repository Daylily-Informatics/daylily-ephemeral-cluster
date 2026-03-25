# Operations

This doc covers the supported operator workflows after the local environment is ready and a cluster exists.

## Connect To A Cluster

List clusters in a region:

```bash
daylily-ec cluster-info --region "$REGION" --profile "$AWS_PROFILE"
```

SSH to the head node:

```bash
ssh -i ~/.ssh/<your-key>.pem ubuntu@<headnode-ip>
```

Use `daylily-ec cluster-info` to find the public IP for the cluster you want to connect to.

## Validate The Head Node

Daylily bootstraps the head node automatically after cluster creation. Validate that bootstrap before staging data or launching a workflow.

Once connected to the head node:

```bash
cd ~/projects/daylily-ephemeral-cluster
conda activate DAY-EC

daylily-ec info
day-clone --list
```

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
daylily-ec drift --state-file ~/.config/daylily/state_<cluster>_<timestamp>.json --profile "$AWS_PROFILE"
```

Scheduler and tmux status on the head node:

```bash
sinfo
squeue -o "%.18i %.8u %.8T %.10M %.30N %.50j"
tmux ls
tmux attach -t <session-name>
```

## Export Results Back To S3

Use `daylily-ec export`:

```bash
daylily-ec export \
  --cluster-name "$CLUSTER_NAME" \
  --region "$REGION" \
  --target-uri analysis_results \
  --output-dir .
```

This waits for the FSx data-repository task to finish and writes `fsx_export.yaml` locally. The older export helpers in `bin/` remain available as wrappers around this same command.

## Delete A Cluster

When the workload is complete and results have been exported, delete the cluster with `daylily-ec delete`:

```bash
daylily-ec delete --cluster-name "$CLUSTER_NAME" --region "$REGION"
```

If you have the create-time state JSON, prefer:

```bash
daylily-ec delete --state-file "$STATE_FILE"
```

The CLI keeps the existing FSx safety confirmation and performs the supported heartbeat teardown before monitoring cluster deletion to completion. The legacy delete helper remains as a thin wrapper for compatibility.

## Related Docs

- [quickest_start.md](quickest_start.md)
- [overview.md](overview.md)
- [DAY_EC_ENVIRONMENT.md](DAY_EC_ENVIRONMENT.md)
