# `us-west-2` ParallelCluster Runtime Inventory

- Inventory time: `2026-07-14T22:54:53Z` through `2026-07-14T22:55:24Z`
- AWS account: `108782052779`
- AWS profile: `lsmc`
- Region: `us-west-2`
- Scope: read-only ParallelCluster, CloudFormation, EC2, SSM headnode, Slurm queue, tmux, and `sinfo` checks.
- Mutation boundary: no cluster, Slurm, workflow, tag, or AWS resource changes were made.

## Regional summary

| Cluster | Cluster/stack state | Created UTC | Created PDT | Headnode | Headnode workload | Slurm queue | Explicit sweep-protection tag | CFN termination protection | `aws-parallelcluster-enforce-budget` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `sent-hg003-5x-0712` | `UPDATE_COMPLETE` | `2026-07-12T12:34:19.887Z` | `2026-07-12 05:34:19 PDT` | `i-04059f0d8c4f701d2` running | Two live DayOA tmux shells at prompts; one failed controller acquired a write lock for planned recovery; one controller completed successfully. One additional login shell and a `sleep 900` process were present. No active Snakemake/`dy-r` process. | Empty | None found | `false` | `true` |
| `ursa-m-rgx-br75` | `CREATE_COMPLETE` | `2026-07-14T01:40:08.082Z` | `2026-07-13 18:40:08 PDT` | `i-0eb29aeecd07951c5` running | No user workload, tmux session, workflow controller, or compute instance; only the inspection login shell was present. | Empty | None found | `false` | `skip` |
| `ifx-20260719g` | cluster `CREATE_FAILED`; stack `ROLLBACK_FAILED` | `2026-07-14T15:14:24.927Z` | `2026-07-14 08:14:24 PDT` | None | No headnode exists, so no headnode/Slurm inspection was possible. | Unavailable | None found | `false` | `true` |
| `ifx-20260719h` | `CREATE_COMPLETE` | `2026-07-14T16:29:40.329Z` | `2026-07-14 09:29:40 PDT` | `i-04ac6c1a5f7cebe92` running | No user workload, tmux session, workflow controller, or compute instance; only the inspection login shell was present. | Empty | None found | `false` | `true` |
| `ifx-sacctoff-1037` | `CREATE_COMPLETE` | `2026-07-14T18:24:29.927Z` | `2026-07-14 11:24:29 PDT` | `i-026a3f1a8fb421d2f` running | No user workload, tmux session, workflow controller, or compute instance; only the inspection login shell was present. | Empty | None found | `false` | `true` |

## Sweep-protection interpretation

No top-level cluster stack has a tag whose key or value contains `sweep`, `protect`, `retain`, `keep`, or `save`. CloudFormation termination protection is also disabled for all five stacks. Therefore, none is explicitly protected from a cluster sweep by the live AWS evidence inspected here.

`aws-parallelcluster-enforce-budget=skip` on `ursa-m-rgx-br75` is not a sweep-protection tag. The current DYEC source uses it to skip submission-time cluster budget enforcement in the `sbatch` wrapper. The other four entries use `true`.

Operationally, `sent-hg003-5x-0712` should not be treated as safe to sweep merely because `squeue` is empty: tmux session `bjuice-hg002-hiomrs-1102-20260714` is at a prompt after a failed LongReadSV controller (`RETURN CODE: 1`) and then acquired the analysis-root write lock for a planned corrected patch/rerun. Session `hiomrs-hg003-1x-1104-20260714` is at a prompt after `173/173`, `WORKFLOW SUCCESS`, `RETURN CODE: 0`.

## Slurm and `sinfo`

All four reachable headnodes returned only the header from:

```text
squeue -o '%i  %P  %C  %t  %N  %c  %T  %m  %M  %D  %j'
```

Thus no Slurm jobs were queued, running, configuring, completing, or pending at the inspection time.

### `ifx-sacctoff-1037`

All configured nodes reported `idle~` (powered down/power-save, available to scale):

```text
i8=1; i96nvme=1; i128=3; i128mem=1; i128bigmem=1; i128nvme=1;
i192=3; i192mem=1; i192bigmem=1; i192nvme=3; i384nvme=3; i192hugenvme=1
```

### `ifx-20260719h`

All configured nodes reported `idle~`:

```text
i8=1; i96nvme=1; i128=48; i128mem=16; i128bigmem=16; i128nvme=16;
i192=48; i192mem=16; i192bigmem=16; i192nvme=48; i384nvme=48; i192hugenvme=16
```

### `ursa-m-rgx-br75`

All configured nodes reported `idle~`:

```text
i8=1; i128=3; i128mem=1; i128bigmem=1; i128nvme=1;
i192=3; i192mem=1; i192bigmem=1; i192nvme=3; i384nvme=3; i192hugenvme=1
```

### `sent-hg003-5x-0712`

`sinfo` reported one powered-on but idle `i128nvme` compute node; all other configured nodes were `idle~`:

```text
i96nvme=12 idle~
i128nvme=11 idle~ + 1 idle
i192nvme=12 idle~
i384nvme=12 idle~
```

EC2 independently confirmed the powered-on node as compute instance `i-0dd749b145f6d3b21`, launched `2026-07-14T19:26:51Z`.

### `ifx-20260719g`

No headnode exists because cluster creation failed and the stack is `ROLLBACK_FAILED`; `squeue` and `sinfo` are unavailable.

## Conclusion

- ParallelCluster lists five entries in `us-west-2`: four usable stacks and one failed residual stack.
- Every reachable Slurm queue is empty.
- Three reachable headnodes are user-workload idle.
- `sent-hg003-5x-0712` has no active Slurm jobs or active workflow process, but it retains live tmux context, a powered-on idle compute node, and a recovery write-lock boundary.
- No cluster has an explicit sweep-protection tag or CloudFormation termination protection.
