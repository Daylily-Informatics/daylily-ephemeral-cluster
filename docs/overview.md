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
- `daylily-ec cluster list`
- `daylily-ec cluster describe`
- `daylily-ec cluster wait`
- `daylily-ec headnode connect`
- `daylily-ec headnode info`
- `daylily-ec headnode jobs`
- `daylily-ec headnode configure`
- `daylily-ec samples stage`
- `daylily-ec samples run`
- `daylily-ec workflow launch`
- `daylily-ec workflow status`
- `daylily-ec workflow logs`
- `daylily-ec state list`
- `daylily-ec state show`
- `python -m daylily_ec.ssh_to_ssm_e2e_runner`
- `bin/utils/ilmn/extract_undetermined_indexes`

`daylily-ec` is the main CLI. It owns:

- environment/runtime introspection
- preflight
- cluster create
- cluster listing/info/wait
- headnode connect/configure/jobs/info
- sample staging and catalog-driven stage+run
- workflow launch/status/logs
- export
- delete
- state inspection
- pricing snapshots

The `bin/` helpers remain callable during the transition, but new operator workflows should use `daylily-ec ...` commands.

## Data Plane

The data model is simple on purpose:

- the cluster is temporary
- the reference bucket is durable
- FSx for Lustre is the performance layer mounted into the cluster

The staging helper reads a local `analysis_samples.tsv`, validates the referenced sources, uploads or references them in the bucket-backed namespace, and writes workflow manifests that the headnode launcher can consume:

- `<timestamp>_samples.tsv`
- `<timestamp>_units.tsv`

The manifest is additive and multi-modality. Legacy Illumina rows can still use
`R1_FQ` / `R2_FQ`, while newer rows can describe ONT, Ultima, PacBio, Roche,
and explicit hybrid units with the modality-specific columns in the bundled
template.

Run-level metric files can travel with the staged manifests by passing
repeatable `--run-metric-staging RUN_UID:PLATFORM:FOFN` options to
`daylily-ec samples stage` or `daylily-ec samples run`. Each FOFN lists one
metric file per line. Relative FOFN entries keep their relative path under
`runs/<RUN_UID>/`; absolute, S3, and FSx entries copy by basename.

The helper prints the remote FSx stage directory. The launcher uses that path through `--stage-dir` so the workflow starts from the exact staged manifest set you just generated.

For Illumina run triage before staging, `bin/utils/ilmn/extract_undetermined_indexes`
streams Undetermined or Unclassified FASTQs from local paths, S3 URIs, or
presigned URLs and emits ranked index-pair TSVs. With `--split-fastqs`, it can
also write one R1/R2 FASTQ pair per selected tag pair.

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
- start in `/home/ubuntu`
- source a login shell for `ubuntu`

## Workflow Launch Model

`daylily-ec workflow launch` is the supported launcher. It:

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
3. `daylily-ec headnode connect` is Session Manager into the `ubuntu` login shell.
4. Export is the handoff from ephemeral compute back to durable storage.
