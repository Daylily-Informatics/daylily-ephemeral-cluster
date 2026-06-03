# Delete `dyec0602bcl` Ledger

## Objective

Prepare deletion of AWS ParallelCluster cluster `dyec0602bcl` in `us-west-2` using profile `lsmc`.

No live destructive delete has been run in this ledger yet.

## Gate 0 Inventory

| Item | Value |
| --- | --- |
| Cluster | `dyec0602bcl` |
| Region | `us-west-2` |
| Profile | `lsmc` |
| Account | `108782052779` from cluster stack ARN |
| ParallelCluster status | `CREATE_COMPLETE` |
| Compute fleet | `RUNNING` |
| Headnode | `i-0c36c39770c533c8e` |
| Headnode state | `running` |
| Headnode private IP | `10.0.0.235` |
| Headnode public IP | `44.255.242.91` |
| Headnode type | `r7i.8xlarge` |
| FSx | `fs-05f90a39933f9b539` |
| `/fsx` usage | `6.6T` size, `1.8T` used, `4.8T` available, `27%` |

## Delete Dry Run

Command:

```bash
daylily-ec delete --cluster-name dyec0602bcl --region us-west-2 --profile lsmc --dry-run
```

Result:

| Check | Evidence |
| --- | --- |
| AWS mutation | none |
| Cluster status | `CREATE_COMPLETE` |
| FSx attached | `fs-05f90a39933f9b539` |
| Run DRA | `dra-04d1f5b3dd1cc75a4`, `/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/`, `AVAILABLE`, `AutoExport=['NEW', 'CHANGED']` |
| Run DRA source | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/` |
| References DRA | `dra-08b3132d486abddea`, `/references/`, `AVAILABLE` |
| References source | `s3://lsmc-dayoa-references-usw2` |

## Headnode Runtime Snapshot

Read-only SSM command against `i-0c36c39770c533c8e` showed:

| Check | Evidence |
| --- | --- |
| Active Slurm queue | `63|bcl2fq|run_bclconvert_tile_shard-run_bclconvert_L003_0001_tiles0001-0008|PENDING|0:00|1|(BeginTime)` |
| tmux sessions | `bcl2fq_scratch_dra_20260603T011121Z`, `dayoa_bcl_alllanes_16shard_48devshm_20260603`, `dayoa_bcl_l001_16shard_48devshm_20260603`, multiple `dayoa_bcl_l003_*` sessions |
| Mounted run dir | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4` |

## Proposed Live Delete

Exact live command, pending separate explicit confirmation:

```bash
daylily-ec delete --cluster-name dyec0602bcl --region us-west-2 --profile lsmc --yes
```

Expected effect:

- Delete ParallelCluster `dyec0602bcl`.
- Tear down cluster CloudFormation resources.
- Delete the cluster FSx filesystem `fs-05f90a39933f9b539`.
- Remove active FSx data repository associations on that FSx, including the run DRA and references DRA.
- Terminate the headnode and compute nodes.
- Stop all tmux sessions and any remaining Slurm jobs on this cluster.
- Keep S3 objects intact; dry-run did not indicate any S3 object deletion.

## Approval Gate

Live deletion requires a second explicit approval after this dry-run summary.

Required confirmation:

```text
CONFIRM DELETE CLUSTER dyec0602bcl
```
