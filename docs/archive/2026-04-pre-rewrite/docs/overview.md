# Overview

Daylily is an operator-focused control plane for AWS ParallelCluster environments that are meant to be created for a run, used heavily, exported, and removed. The durable assets are the reference bucket, staged manifests, workflow repositories, and exported results, not the running cluster itself.

## System Model

The current codebase has three practical layers:

1. Control plane: `daylily-ec` validates prerequisites, renders cluster config, creates the cluster, configures the head node, exports results, and deletes the cluster.
2. Data plane: a region-scoped S3 bucket is mounted through FSx for Lustre so `/fsx/data`, `/fsx/resources`, and `/fsx/analysis_results` are shared across nodes and exportable back to S3.
3. Workflow plane: repository metadata in `config/daylily_available_repositories.yaml` drives `day-clone` and the workflow launcher on the head node.

## Supported Operator Lifecycle

The supported flow in the current repo is:

1. Build or activate `DAY-EC` with `source ./activate`.
2. Run `daylily-ec preflight` with an explicit config file and target AZ.
3. Run `daylily-ec create` and wait for it to return only after the post-ParallelCluster headnode configuration finishes.
4. Connect through Session Manager using `bin/daylily-ssh-into-headnode`.
5. Stage sample manifests and inputs from the operator machine with `bin/daylily-stage-samples-from-local-to-headnode`.
6. Launch the workflow on the head node with `bin/daylily-run-omics-analysis-headnode`.
7. Export `/fsx/analysis_results/ubuntu` with `daylily-ec export`.
8. Delete the cluster with `daylily-ec delete` when the run is complete.

## Filesystem Layout

The code and current headnode helpers assume these paths:

- `/fsx/data`: staged inputs and shared data
- `/fsx/resources`: cached references and tool assets
- `/fsx/analysis_results/ubuntu`: workflow clones, run directories, and results owned by `ubuntu`
- `/home/ubuntu/daylily-runs/<session>`: durable launcher state for the tmux-based workflow helper

## Runtime Expectations

- The supported operator identity on the head node is `ubuntu`.
- Session Manager must be configured with `SSM-SessionManagerRunShell` so shells land in the `ubuntu` login shell.
- The login shell should source `~/projects/daylily-ephemeral-cluster/activate` and evaluate `daylily-ec headnode init --emit-shell --non-interactive --skip-project-check`.

## Related Docs

- [quickest_start.md](quickest_start.md)
- [operations.md](operations.md)
- [DAY_EC_ENVIRONMENT.md](DAY_EC_ENVIRONMENT.md)
