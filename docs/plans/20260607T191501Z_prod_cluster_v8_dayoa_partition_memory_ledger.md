# DAY-EC v8 Cluster + DayOA Partition/Memory Ledger

UTC start: 20260607T191501Z

## Boundary

No AWS-mutating command was run. In particular, no `pcluster create-cluster`, `pcluster update-cluster`, `pcluster delete-cluster`, or `pcluster create-cluster --dryrun true` command was run.

## Gate 0

- DYEC branch: `jem-dev...origin/jem-dev`
- DYEC HEAD/tag before release work: `e7ccfe9a`, latest tag `8.0.1`
- DayOA branch: `jem-dev...origin/jem-dev`
- DayOA HEAD/tag before release work: `a6382d8`, latest tag `8.0.0`
- DYEC Python/pip: Python `3.11.15`, pip `26.1.2` in `/Users/jmajor/miniconda3/envs/DAY-EC`
- DayOA Python/pip: Python `3.12.12`, pip `25.3`
- ParallelCluster: `{"version": "3.15.0"}`
- AWS discovery profile/region/AZ: `lsmc`, `us-west-2`, `us-west-2d`

## Rows

| Row | Owner | Status | Evidence |
| --- | --- | --- | --- |
| `G0-001` | Agent 1 | SUCCESS | Recorded branch, dirty state, versions, pcluster version, AWS profile/region/AZ, and no-mutation boundary. |
| `DYEC-001` | Agent 2 | SUCCESS | Added source `config/day_cluster/prod_cluster_v8.yaml` and packaged copy; preserved old `prod_cluster.yaml`. |
| `DYEC-002` | Agent 2 | SUCCESS | v8 default template cutover complete; active queues are `i8`, `i128`, `i128nvme`, `i192`, `i192nvme`, `i384nvme`, `i192hugenvme`; memory scheduling enabled; granular max-count substitutions added. |
| `AWS-RO-001` | Agent 3 | SUCCESS | Read-only EC2 offering/spec discovery used `describe-instance-type-offerings` and `describe-instance-types`; `r8in.48xlarge`/`r8ib.48xlarge` excluded as unavailable in `us-west-2d`; AMD `*a` excluded by criteria. |
| `SPOT-001` | Agent 3 | SUCCESS | Added `scripts/pcluster_spot_baseline.sh`; generated `docs/spot-baselines/pcluster-spot-baseline-us-west-2d.csv` and `.md` with 37 instance rows. |
| `DAYOA-001` | Agent 4 | SUCCESS | DayOA active Slurm config moved from legacy partitions to v8 partitions; static check found no legacy partition values and no missing `mem_mb` on partitioned entries. |
| `DAYOA-002` | Agent 5 | SUCCESS | BCL Convert scratch defaults moved from `/dev/shm` to `/scratch`; Slurm profile binds `/scratch:/scratch`. |
| `BWA-001` | Agent 6 | SUCCESS | Added `daylily_omics_analysis.slurm.spot_partition_order` and `bin/day_run` hook for `bwa_mem2a_aln_sort.partition_strategy: spot_price_runtime`; helper fails hard on missing AWS price/spec data. |
| `TEST-001` | Agent 7 | SUCCESS | DYEC full suite: `1065 passed, 7 skipped`. Focused DYEC v8 tests also passed. |
| `TEST-002` | Agent 8 | SUCCESS | DayOA v8-focused tests pass; full DayOA suite now passes: `281 passed`. Benchmark directives were added instead of xfail/skip markers. |
| `VALID-001` | Agent 9 | BLOCKED | Rendered placeholder v8 config parses and has expected queues; `pcluster validate-cluster-configuration --cluster-configuration docs/plans/20260607T191501Z_prod_cluster_v8_rendered_placeholder.yaml --region us-west-2` exits rc=2 because ParallelCluster 3.15.0 does not expose `validate-cluster-configuration`. |
| `REL-001` | Agent 10 | SUCCESS | DayOA `9.0.0` annotated tag pushed; DYEC active DayOA pins and self-pins advanced to `9.0.0`; DYEC full suite passes and release commit/tag is the final local gate for this row. |
| `REPORT-001` | Agent 10 | SUCCESS | This ledger records terminal row states, command outcomes, blockers, and next gate. |

## Validation Evidence

Rendered placeholder file:

`docs/plans/20260607T191501Z_prod_cluster_v8_rendered_placeholder.yaml`

Render summary:

- queues: `['i8', 'i128', 'i128nvme', 'i192', 'i192nvme', 'i384nvme', 'i192hugenvme']`
- `Scheduling.SlurmSettings.EnableMemoryBasedScheduling`: `True`

ParallelCluster validation blocker:

```text
pcluster: error: argument operation: invalid choice: 'validate-cluster-configuration'
```

No `create-cluster --dryrun true` substitute was used.

## Test Evidence

DYEC:

```text
source ./activate && python -m pytest -q
1065 passed, 7 skipped
```

DayOA:

```text
python -m pytest -q
281 passed
```

## Next Safe Gate

The remaining validation limitation is external to repo code: ParallelCluster `3.15.0` does not expose `validate-cluster-configuration`. The next manual cluster gate remains an explicitly approved `pcluster create-cluster` test; no create/update/delete command was run in this pass.
