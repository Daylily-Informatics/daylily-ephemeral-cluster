# Overview

DayEC is an operator-facing control plane for disposable AWS ParallelCluster environments. It creates the cluster, configures the headnode over Session Manager as `ubuntu`, launches Daylily workflows, and exports selected FSx results back to S3 before teardown.

## Current Model

The current codebase is DRA-first:

1. `dyec create` renders a ParallelCluster template with FSx for Lustre mounted at `/fsx`.
2. Cluster creation adds a `reference-data` DRA from the reference bucket `data/` prefix to FSx API path `/data/`, visible as `/fsx/data`.
3. `dyec mounts create` can attach selected S3 run prefixes as ephemeral run DRAs under `/run_dir_mounts/<mount_id>`, visible as `/fsx/run_dir_mounts/<mount_id>`.
4. `dyec workflow launch` starts DayOA work in tmux on the headnode and writes outputs under `/fsx/analysis_results/...`.
5. Operators copy selected outputs to `/fsx/exports/<export_id>/...`.
6. `dyec export` creates a temporary output DRA, runs an FSx `EXPORT_TO_REPOSITORY` task, writes `fsx_export.yaml`, and detaches the DRA.
7. `dyec delete` tears down the cluster after export verification.

## Control Plane

The supported operator surface is the CLI:

- `dyec preflight`
- `dyec create`
- `dyec cluster list|describe|wait`
- `dyec headnode connect|configure|info|jobs`
- `dyec samples stage|run`
- `dyec mounts create|list|describe|verify|delete`
- `dyec mount rundir`
- `dyec workflow launch|status|logs`
- `dyec repositories commands`
- `dyec export`
- `dyec exports attach|run|detach`
- `dyec state list|show`
- `dyec delete`

Historical helper scripts may still exist for packaging or compatibility tests, but current operator docs should use the CLI surface above.

## Data Plane

The namespace is intentionally explicit:

| Path | Role |
|---|---|
| `/fsx/data` | Reference data from the cluster-created reference DRA |
| `/fsx/run_dir_mounts/<mount_id>` | Read-oriented run-folder input DRA |
| `/fsx/analysis_results/...` | Workflow checkout and result workspace |
| `/fsx/exports/<export_id>` | Temporary export staging namespace |

Run-directory mounts are inputs. They do not define the export destination and are rejected as export sources. Export is a separate output DRA task from `/exports/<export_id>/...` to the requested S3 URI.

## Workflow Plane

`config/daylily_available_repositories.yaml` is the source of truth for workflow repositories and blessed command profiles. The packaged copy under `daylily_ec/resources/payload/config/` must match it.

Catalog v2 splits commands by input contract:

- `sample_analysis` commands use `analysis_samples.tsv`; `dyec samples stage` writes `samples.tsv` and `units.tsv`.
- `run_analysis` commands use `runs.tsv`; run input must be mounted under `/fsx/run_dir_mounts/<mount_id>`.

The current DayOA catalog pin is `1.0.7` for the repository default and all DayOA command `git_tag` values.

## Headnode Model

Headnode work is Session-Manager-first:

- interactive sessions use `dyec headnode connect`
- command payloads run as `ubuntu`
- the supported shell is a login bash shell in `/home/ubuntu`
- `day-clone` clones configured repositories under the FSx analysis root

Manual root sessions or user switching are not part of the supported path.

## Receipts

DayEC writes operational artifacts that should be kept with the run record:

- preflight and state files in the DayEC config/state directory
- local staged `*_samples.tsv` and `*_units.tsv`
- headnode `/home/ubuntu/daylily-runs/<session>/status.json`
- headnode `/home/ubuntu/daylily-runs/<session>/tmux.log`
- local `fsx_export.yaml`

`fsx_export.yaml` is the proof that the explicit export task completed and the temporary export DRA was detached.

## Further Reading

- [dra_fsx_strategy.md](dra_fsx_strategy.md)
- [quickest_start.md](quickest_start.md)
- [operations.md](operations.md)
- [cli_reference.md](cli_reference.md)
- [monitoring_and_troubleshooting.md](monitoring_and_troubleshooting.md)
