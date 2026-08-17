# pcand-usw2d Three-Platform Run Mount Ledger

Created: 2026-08-17T09:24:32Z
Completed: 2026-08-17T10:25:33Z

## Objective and scope

After Slurm accounting was enabled and the cluster returned to
`UPDATE_COMPLETE` with a `RUNNING` compute fleet, create and verify three
read-only FSx data repository associations on `pcand-usw2d` in parallel:

- the Bjuice-preval ILMN run;
- the reviewed Bjuice-preval ONT parent containing the 15 run directories;
- recent Ultima run `604834-20260717_2309`.

No export/writeback, delete, duplicate retry, source mutation, workflow launch,
Slurm intervention, source-code test, commit, push, reset, stash, clean, or
checkout was performed by this operation.

## Gate 0: inventory freeze

- Target: AWS profile `lsmc`, region `us-west-2`, cluster `pcand-usw2d`.
- Initial and closing cluster state: `clusterStatus=UPDATE_COMPLETE`,
  `cloudFormationStackStatus=UPDATE_COMPLETE`,
  `computeFleetStatus=RUNNING`; headnode `i-01421a467936317f7` was `running`.
- Target FSx: `fs-09dbcea48d90844c4`, `LUSTRE`, `AVAILABLE`, 4800 GiB.
- Pre-create raw DRA inventory: one active static reference association,
  `dra-09d4459fb084335a5` at `/references/`; no run-mount association existed.
  Three creates resulted in four active DRAs, below DYEC 18.0.22's hard limit
  of eight.
- All three exact S3 prefixes were proven readable with one-object
  `aws s3api list-objects-v2` probes. No path was inferred or substituted.
- Execution binary: clean detached release worktree
  `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster-dyec-18.0.22-20260817T075000Z`,
  commit `f9adda5268129242013a44bf6e684836aed84e25`, exact tag `18.0.22`.
- Source contract: `docs/runbooks/18.0.22/runbooka1.md`, section
  `Submitted read-only DRA mounts`.
- Each create used `--wait --timeout-seconds 5400`; no slow association was
  retried or replaced.
- At Gate 0 the active checkout was dirty on
  `codex/dyec-18.0.22-dayoa-15.0.11`; those modified and untracked files were
  treated as user-owned and not touched. During the AWS wait, that checkout
  was changed externally to detached tag `18.0.25` at
  `03cf995572b3516433fd8fc6d28b7622a774bc44`. This operation performed no Git
  state transition. The initially-created untracked ledger disappeared during
  that transition, so this terminal ledger was recreated without overwriting
  any existing file.

## Terminal rows

| ID | Platform | Mount/run | Association | Source and headnode path | Terminal evidence | Status |
|---|---|---|---|---|---|---|
| MNT-ILMN | ILMN | `20260618_LH01106_0011_A23MFMCLT3` | `dra-0a4fbff420ab78ff1` | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/` -> `/fsx/run_dir_mounts/20260618_LH01106_0011_A23MFMCLT3` | `AVAILABLE`, read-only, `NEW,CHANGED`, no auto-export, no failure details | `SUCCESS` |
| VERIFY-ILMN | ILMN | same | same | same | SSM command `0aaf1f87-58c2-41a3-ab43-56c884695c1e`: `usable=true` | `SUCCESS` |
| MNT-ONT | ONT | mount/run `pca100-2026` | `dra-05050fd1574597dca` | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/` -> `/fsx/run_dir_mounts/pca100-2026` | `AVAILABLE`, read-only, `NEW,CHANGED`, no auto-export, no failure details | `SUCCESS` |
| VERIFY-ONT | ONT | same | same | same | SSM command `a00a2b3c-25ba-4833-a43b-b3496894914d`: `usable=true` | `SUCCESS` |
| MNT-ULTIMA | ULTIMA | mount `ultima-604834-20260717`; run `604834-20260717_2309` | `dra-04db4d859984093ee` | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/RUN604834/2026/604834-20260717_2309/` -> `/fsx/run_dir_mounts/ultima-604834-20260717` | `AVAILABLE`, read-only, `NEW,CHANGED`, no auto-export, no failure details | `SUCCESS` |
| VERIFY-ULTIMA | ULTIMA | same | same | same | SSM command `c4b31a4b-146d-4a2b-8638-86a69c910de1`: `usable=true` | `SUCCESS` |

## Timeline

- 2026-08-17T09:25:38Z: all three associations were created within the same
  second, proving concurrent submission.
- 2026-08-17T09:45:17Z: Ultima reached `AVAILABLE`; verification completed at
  09:45:53Z.
- 2026-08-17T10:05:14Z: ONT reached `AVAILABLE`; verification completed at
  10:05:35Z.
- 2026-08-17T10:24:55Z: ILMN reached `AVAILABLE`; verification completed at
  10:25:03Z.
- 2026-08-17T10:25:33Z: final DYEC, raw FSx, and ParallelCluster reads agreed
  on all mount and cluster acceptance conditions.

## Final acceptance

Complete: six `SUCCESS`, zero `OPEN`, zero `IN_PROGRESS`, zero
`ATTEMPTING_BUGFIX`, zero `BLOCKED`, and zero `FAIL`. All three exact sources
are available and usable on the headnode. No Git tests were run, per user
direction.
