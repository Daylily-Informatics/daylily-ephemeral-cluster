# Overview

This repo is an operator-facing control plane for disposable AWS ParallelCluster environments used to run Daylily bioinformatics workflows. The current supported path is repo-driven and Session-Manager-first:

1. validate the local environment and AWS prerequisites
2. create the cluster
3. finish headnode bootstrap over Session Manager as `ubuntu`
4. stage local inputs into the bucket-backed FSx namespace
5. launch the workflow in tmux on the headnode
6. monitor runtime state until the run is complete
7. export `/fsx/analysis_results/ubuntu` back to S3
8. tear the cluster down

## Control Plane

The supported control-plane surfaces are:

- `daylily-ec`
- `activate`
- `bin/daylily-ssh-into-headnode`
- `bin/daylily-stage-samples-from-local-to-headnode`
- `bin/daylily-run-omics-analysis-headnode`
- `bin/daylily-cfg-headnode`
- `python -m daylily_ec.ssh_to_ssm_e2e_runner`

`daylily-ec` is the main CLI. It owns:

- environment/runtime introspection
- preflight
- cluster create
- cluster listing/info
- export
- delete
- pricing snapshots
- headnode init helpers

The `bin/` helpers are thin supported wrappers around the staged-input, headnode-config, interactive-connect, and workflow-launch flows.

## Data Plane

The data model is simple on purpose:

- the cluster is temporary
- the reference bucket is durable
- FSx for Lustre is the performance layer mounted into the cluster

The staging helper reads a local `analysis_samples.tsv`, validates the referenced sources, uploads or references them in the bucket-backed namespace, and writes workflow manifests that the headnode launcher can consume:

- `<timestamp>_samples.tsv`
- `<timestamp>_units.tsv`

The helper prints the remote FSx stage directory. The launcher uses that path through `--stage-dir` so the workflow starts from the exact staged manifest set you just generated.

## Headnode Bootstrap Model

The cluster create flow does more than call `pcluster create-cluster`.

After infrastructure creation, Daylily:

- resolves the headnode instance
- waits for Systems Manager readiness
- configures the headnode over Session Manager
- installs and validates the user-scoped Daylily bootstrap under `/home/ubuntu`
- verifies a fresh `ubuntu` login shell

That last point matters. The supported shell must already be correct when the operator connects. The repo does not treat manual user switching as part of the supported workflow.

Session Manager is only considered valid when the regional document `SSM-SessionManagerRunShell` is configured to:

- run shell sessions as `ubuntu`
- source a login shell for `ubuntu`

## Workflow Launch Model

`bin/daylily-run-omics-analysis-headnode` is the supported launcher. It:

1. discovers the staged config files from `--stage-dir`
2. ensures the target repo exists under `/fsx/analysis_results/ubuntu/<destination>/...`
3. copies staged `samples.tsv` and `units.tsv` into the workflow repo
4. creates `/home/ubuntu/daylily-runs/<session>/`
5. writes `launch.sh`, `tmux.log`, and `status.json`
6. starts the tmux session

`status.json` is the durable machine-readable run receipt for the launcher. It records:

- `session_name`
- `repo_path`
- `started_at`
- `completed_at`
- `exit_code`
- `command`

## Create, Export, And E2E Artifacts

The current codebase writes several operator-useful artifacts:

### Create

- preflight report JSON under the Daylily XDG state/config tree
- state record JSON for create/delete workflows
- rendered cluster config and related local workflow state

### Workflow launch

- stage manifest files in the chosen local `--config-dir`
- remote workflow run directory under `/home/ubuntu/daylily-runs/<session>/`

### Export

- `fsx_export.yaml` in the chosen `--output-dir`

### E2E runner

- generated config copy for the run
- per-stage JSON summary, defaulting to `tmp-e2e-results/<cluster>.json`
- stage config directory and export output directory when not overridden

## Mental Model

If you remember only four things, remember these:

1. `source ./activate` is the supported way into the local toolchain.
2. `daylily-ec create` is not done until the Daylily post-create headnode steps succeed.
3. `bin/daylily-ssh-into-headnode` is Session Manager into the `ubuntu` login shell.
4. Export is the handoff from ephemeral compute back to durable storage.
