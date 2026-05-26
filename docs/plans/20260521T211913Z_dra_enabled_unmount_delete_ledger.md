# DRA-Enabled Unmount And Delete Ledger

## Scope

Prepare destructive cleanup for `profile=lsmc`, `region=us-west-2`, cluster `dra-enabled`.

Requested actions:

- Delete all run-directory DRA mounts visible under the CLI run-mount path `/fsx/run_dir_mounts/*` before cluster teardown.
- Delete the `dra-enabled` AWS ParallelCluster cluster after separate explicit confirmation.

Safety boundary: this ledger does not authorize live destructive mutation. Live DRA deletion and cluster deletion require a separate explicit confirmation after the exact target set is reported.

## Gate 0 Inventory

| Item | Evidence |
| --- | --- |
| Repo | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| Cluster | `dra-enabled` |
| Region/profile | `us-west-2` / `lsmc` |
| Cluster dry-run status | `dyec delete --dry-run --profile lsmc --region us-west-2 --cluster-name dra-enabled` reported no AWS changes and current cluster status `CREATE_COMPLETE`. |
| FSx file system | `fs-017ab7a7cdbf44c54` |
| Run DRA to delete before cluster teardown | `dra-0e036df15b52f3f85`, lifecycle `AVAILABLE`, `/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/` -> `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/`, headnode path `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/`. |
| Reference DRA present | `dra-0c4d82481e4a4a417`, lifecycle `AVAILABLE`, `/data/` -> `s3://lsmc-dayoa-omics-analysis-us-west-2/data/`. This is not a run-directory mount; it is part of the cluster FSx/reference model and is expected to be removed through cluster/FSx teardown. |
| Headnode path check | Read-only SSM check at 2026-05-21T21:19:43Z found no `/fsx/rundata*` paths. `/fsx/run_dir_mounts/*` still contains cached directories for older runs, but AWS DRA inventory reports only one active run DRA: Run 3 `20260514_LH01106_0009_B23TVLGLT4`. |

## Execution Rows

| Row | Status | Target | Action | Evidence / Notes |
| --- | --- | --- | --- | --- |
| `G0-001` | `SUCCESS` | `dra-enabled` | Inventory current run DRAs and cluster delete dry-run. | `dyec --json mounts list` found one run DRA: `dra-0e036df15b52f3f85`; `dyec delete --dry-run` found FSx `fs-017ab7a7cdbf44c54`, run DRA `dra-0e036df15b52f3f85`, and reference DRA `dra-0c4d82481e4a4a417`. Read-only headnode check found no `/fsx/rundata*` paths and found stale cached directories under `/fsx/run_dir_mounts/*`; these are FSx data/cache directories, not active DRA associations according to AWS inventory. |
| `DRA-DEL-001` | `SUCCESS` | `dra-0e036df15b52f3f85` | Delete the Run 3 run-directory DRA without deleting S3 objects or cached FSx data. | User confirmed `CONFIRM DELETE DRA dra-0e036df15b52f3f85 AND DELETE CLUSTER dra-enabled`. Command `dyec --json mounts delete --profile lsmc --region us-west-2 --cluster dra-enabled --association-id dra-0e036df15b52f3f85 --wait --timeout-seconds 1800` returned the known post-delete projection/formatting error `Expected an s3:// URI, got ''`; verification immediately afterward showed `dyec --json mounts list` returned `{"mounts":[]}` and AWS FSx inventory for `fs-017ab7a7cdbf44c54` listed only the reference `/data/` DRA. |
| `CLUSTER-DEL-001` | `SUCCESS` | `dra-enabled` | Delete the AWS ParallelCluster cluster after the run DRA is detached. | Command `dyec delete --profile lsmc --region us-west-2 --cluster-name dra-enabled --yes` completed with `Cluster deleted`. The command reported the remaining reference DRA `dra-0c4d82481e4a4a417 /data/` before teardown and removed heartbeat resources where present. Post-delete verification: `AWS_PROFILE=lsmc pcluster list-clusters --region us-west-2` listed only `XL-pilot`, not `dra-enabled`; `describe_file_systems` for `fs-017ab7a7cdbf44c54` returned `FileSystemNotFound`; `describe_data_repository_associations` for that FSx id returned `ASSOC_COUNT 0`. |

## Final Status

All rows are terminal. The active run-directory DRA was removed, `dra-enabled` was deleted, and the associated FSx file system no longer exists. No S3 object deletion was requested or performed.
