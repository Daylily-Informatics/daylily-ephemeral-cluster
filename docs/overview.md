# DYEC Overview

This is the living overview for DYEC `18.0.33`. The command surface is defined
by `dyec --help`; [cli_reference.md](cli_reference.md) is the detailed
operator reference. Dated release reports, archived documents, and plan ledgers
retain historical evidence and are not current command guidance.

## Role and boundaries

DYEC is the operator-facing control plane for ephemeral AWS ParallelCluster
environments. It can create and inspect clusters, perform supported headnode
operations, mount explicit S3 prefixes into FSx, launch pinned workflow
repositories in tmux, observe exact analysis roots, and export finished output
through an explicit FSx DRA.

DYEC is not a workflow engine or an identity/metadata client. It consumes
explicit configuration, local manifests, S3 paths, and command-catalog entries.
It does not infer an external identity, discover a workflow revision, or replace
a missing input with a fallback. DayOA owns `dy-r` and its workflow rules; DYEC
owns the cluster/headnode and launch/export envelope.

## Root command surface

| Area | Commands |
|---|---|
| Local information | `version`, `info`, `env`, `runtime`, `resources-dir`, `state`, `set-vars`, `unset-vars`, `agent guidance` |
| Cluster lifecycle | `preflight`, `create`, `drift`, `cluster-info`, `delete` |
| Cluster and headnode | `cluster`, `headnode`, `slurm-accounting`, `cost-centers`, `pricing`, `aws` |
| Workflow and catalog | `workflow`, `repositories`, `catalog`, `samples`, `identities`, `tests` |
| FSx and analysis | `mounts`, `mount`, `export`, `exports`, `runtime-cache`, `analysis`, `command` |

Use `dyec <group> --help` for nested commands. Root `--json` is for
machine-readable output where supported; root `--verbose`/`-v` prints
project-local invocation diagnostics to stderr before the subcommand.

## Project-local context

`dyec set-vars` and `dyec unset-vars` manage only
`$PWD/.dyec.config.yaml`. It is ignored by Git and may contain only
`aws_profile`, `aws_region`, `aws_region_az`, and `cluster_admin_email` string
values. Blank values are unset; malformed YAML, unknown keys, and non-string
values fail clearly.

For every supported `--profile`, `--region`, and `--region-az` option, the
order is explicit flag, then the local context, then that command's pre-existing
behavior. No region is inferred from an AZ, or vice versa. The local file never
reads or writes `DYEC_*` environment variables. Direct `aws` and `pcluster`
commands still use their normal AWS environment/profile handling.

## Operating lifecycle

1. Activate the checkout with `source ./activate`, then inspect
   `dyec --json version` and `dyec --help`.
2. Resolve profile, region, and AZ explicitly or set local context; run
   `dyec preflight` before cluster creation.
3. Create the cluster with `dyec create`, then use `dyec cluster` and
   `dyec headnode` commands for supported inspection and access.
4. Use `dyec catalog show` and `dyec catalog render` before a catalog launch.
   For a lower-level launch, pass an explicit `--git-tag`; DYEC does not choose
   a DayOA ref for the operator.
5. Record an `analysis visit` before inspecting an analysis root. Acquire the
   documented lock before a protected write, unlock, delete, or kill operation.
6. Export one completed analysis root with `dyec export`, preserve its
   `fsx_export.yaml` receipt, and treat deletion as a separate destructive
   decision.

## Data and artifact boundaries

FSx is the active workflow namespace:

| Purpose | Path |
|---|---|
| Reference data | `/fsx/references/` |
| Runtime assets | `/fsx/references/runtime_assets/` |
| Control data | `/fsx/control_data/...` |
| Staged sample inputs | `/fsx/staging/staged_external_sequencing_data/...` |
| Run directories | `/fsx/run_dir_mounts/<mount-id>/` |
| Analysis roots | `/fsx/analysis_results/<executing-entity>/<analysis-id>/` |

Run mounts are read-oriented by default and are not export sources. `dyec
export` attaches a temporary output DRA to one completed analysis root, runs an
FSx export task, writes `fsx_export.yaml`, and detaches the DRA. FSx data is
preserved unless the explicitly destructive export cleanup option is supplied.
`dyec runtime-cache export` is the separate, DRA-only path for preserving
cluster-scoped runtime caches.

## Catalog state

The source and packaged command catalogs must remain byte-identical. The active
DayOA repository and active DayOA command targets are pinned to `15.0.23`.
Catalog output preserves older validation evidence and exposes
`validation_pending: true` when a command's current `git_tag` differs from its
recorded `validated_version`. The indicator is informational: it does not
relabel old proof or block a launch.

Catalog commands declare an explicit input contract. Inspect it with
`dyec --json catalog show <command-id>` before choosing one of:

- `six_manifest`: a validated local six-manifest directory;
- `sample_manifest` or `sample_manifest_v12`: an explicit staged manifest path
  or the applicable legacy staging helper;
- `run_context`: a local `runs.tsv` plus any required verified run mount; or
- `none`: no input file arguments.

## Further reading

- [CLI reference](cli_reference.md)
- [Quickest Start](quickest_start.md)
- [Operations](operations.md)
- [DRA and FSx strategy](dra_fsx_strategy.md)
- [Analysis-root agent locking](analysis_root_agent_locking.md)
- [Monitoring and troubleshooting](monitoring_and_troubleshooting.md)
