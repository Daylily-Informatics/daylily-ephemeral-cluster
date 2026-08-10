# majors-cluster delete ledger

Control ledger for the requested `majors-cluster` Slurm cleanup and cluster delete.

Controlling plan: this ledger.
Ledger path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260719T215939Z_majors_cluster_delete_ledger.md`

## Gate 0 Baseline

- Timestamp: `2026-07-19T21:59:39Z`.
- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`.
- Repo state: `git status --short --branch` -> `## main...origin/main [behind 45]` plus existing untracked plan artifacts under `docs/plans/`.
- Safety note: Slurm job `1131` was cancelled immediately after the explicit user request. No AWS resource delete was performed before this Gate 0 record.
- Active cluster: `majors-cluster`, region `us-west-2`, profile `lsmc`.
- ParallelCluster status: `UPDATE_COMPLETE`; compute fleet `RUNNING`.
- Headnode: `i-0b8817aa1ded68964`, `r7i.2xlarge`, private IP `10.0.0.42`, public IP `44.244.17.193`, state `running`.
- Compute node before cancel: `i-04ab33f074ab049cb`, `r8i.2xlarge`, private IP `10.0.1.98`, state `running`.
- Slurm baseline before cancel: job `1131`, partition `i8`, state `RUNNING`, node `i8-dy-price8-1`, name `wrap`, user `ubuntu`, submit line `/opt/slurm/sbin/sbatch --comment=RnD --export=ALL --partition i8 --wrap=sleep 10000`.
- Slurm post-cancel verification: `dyec headnode jobs --profile lsmc --region us-west-2 --cluster majors-cluster` returned only the header, no queued or running jobs.
- FSx: `fs-0c3980010a92252b1`, lifecycle `AVAILABLE`, storage `4800 GiB`, cluster-bound.
- DRA associations:
  - `dra-0793ae787f061be4d` `/run_dir_mounts/20260618_LH01106_0011_A23MFMCLT3/` -> `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/`, lifecycle `AVAILABLE`.
  - `dra-04ddc72645adc61a4` `/run_dir_mounts/pca100-2026/` -> `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/`, lifecycle `AVAILABLE`.
  - `dra-06a58d32ab234e73d` `/references/` -> `s3://lsmc-dayoa-references-usw2`, lifecycle `AVAILABLE`.
- Active FSx data repository tasks: none in `PENDING` or `EXECUTING`.
- Dry-run: `dyec delete --dry-run --profile lsmc --region us-west-2 --cluster-name majors-cluster` reported no AWS resources changed and warned that cluster-bound FSx `fs-0c3980010a92252b1` and the three active DRA associations above are in the delete scope.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| MCDEL-001 | Slurm | Cancel requested job `1131`. | SUCCESS | active_product_contract | User explicit scheduler approval | Codex | `scancel 1131` via supported SSM helper as `ubuntu`; immediate state `COMPLETING`; later `dyec headnode jobs` returned only the header. |  | Job is no longer present in `squeue`. |
| MCDEL-002 | AWS | Delete `majors-cluster` after dry-run and second approval. | SUCCESS | active_product_contract | Destructive AWS second approval | Codex | User supplied exact approved command; `dyec delete --yes --profile lsmc --region us-west-2 --cluster-name majors-cluster` started at `2026-07-19T22:01:06Z`; later `pcluster list-clusters --region us-west-2` omitted `majors-cluster`; `pcluster describe-cluster --cluster-name majors-cluster` returned cluster does not exist. |  | ParallelCluster `majors-cluster` is deleted. FSx post-delete cleanup was intentionally stopped by later user instruction. |
| MCDEL-003 | Verification | After live delete, verify ParallelCluster, EC2, FSx, and DRA state. | SUCCESS | contract_test | After live delete | Codex | Final verification at `2026-07-19T22:09:18Z`: no non-terminated EC2 instances with `parallelcluster:cluster-name=majors-cluster`; FSx `fs-0c3980010a92252b1` `AVAILABLE`; DRAs `dra-0793ae787f061be4d`, `dra-04ddc72645adc61a4`, and `dra-06a58d32ab234e73d` `AVAILABLE`; no active FSx repository tasks. |  | Cluster resources are absent; requested FSx and DRA preservation is confirmed. |
| MCDEL-004 | FSx | Stop FSx deletion requested after cluster delete had started. | SUCCESS | active_product_contract | User requested preservation | Codex | Sent `Ctrl-C` to local DYEC delete process; no local `dyec delete`/`pcluster delete` process remained; code inspection showed DYEC post-delete cleanup matches only `dyec:fsx-lifecycle=CLUSTER_BOUND`; retagged FSx `fs-0c3980010a92252b1` to `dyec:fsx-lifecycle=PRESERVED_AFTER_CLUSTER_DELETE`; FSx remained `AVAILABLE`. |  | Local post-delete FSx cleanup path was stopped, and the tag no longer matches DYEC's cluster-bound FSx deletion selector. |

## Live Update 2026-07-19T22:06Z

- The live delete command was started after explicit approval.
- The user then asked to stop the FSx delete while ParallelCluster was still deleting.
- The local DYEC process was interrupted with `Ctrl-C` before it reported cluster deletion complete or started the external P2 FSx cleanup section.
- Current cluster state after interrupt: `majors-cluster` CloudFormation stack `DELETE_IN_PROGRESS`, deletion time `2026-07-19T22:01:06.341Z`.
- Current FSx state after interrupt and retag: `fs-0c3980010a92252b1` lifecycle `AVAILABLE`, tag `dyec:fsx-lifecycle=PRESERVED_AFTER_CLUSTER_DELETE`, tag `ursa-preserve=true`.
- Current DRA state: `dra-0793ae787f061be4d`, `dra-04ddc72645adc61a4`, and `dra-06a58d32ab234e73d` lifecycle `AVAILABLE`.

## Final State 2026-07-19T22:09:18Z

- `majors-cluster` is no longer listed by `pcluster list-clusters --region us-west-2`.
- `pcluster describe-cluster --region us-west-2 --cluster-name majors-cluster` returns that the cluster does not exist.
- EC2 query for non-terminated instances tagged `parallelcluster:cluster-name=majors-cluster` returns `[]`.
- FSx `fs-0c3980010a92252b1` remains `AVAILABLE`, DNS `fs-0c3980010a92252b1.fsx.us-west-2.amazonaws.com`, storage `4800 GiB`.
- FSx preservation tags include `dyec:fsx-lifecycle=PRESERVED_AFTER_CLUSTER_DELETE` and `ursa-preserve=true`.
- DRAs remain `AVAILABLE`:
  - `dra-0793ae787f061be4d`
  - `dra-04ddc72645adc61a4`
  - `dra-06a58d32ab234e73d`
- Active FSx data repository tasks for `fs-0c3980010a92252b1`: none.
- Ledger rows: `4 SUCCESS / 0 BLOCKED / 0 IN_PROGRESS`.

## Exact Delete Scope Pending Approval

The proposed live command is:

```bash
dyec delete --yes --profile lsmc --region us-west-2 --cluster-name majors-cluster
```

Expected destructive effects:

- Delete ParallelCluster `majors-cluster`.
- Terminate the headnode `i-0b8817aa1ded68964`.
- Terminate cluster compute capacity, including the observed compute node `i-04ab33f074ab049cb` if still present.
- Delete cluster-bound FSx filesystem `fs-0c3980010a92252b1`, which deletes cached/local FSx contents.
- Remove the attached FSx data repository associations `dra-0793ae787f061be4d`, `dra-04ddc72645adc61a4`, and `dra-06a58d32ab234e73d`.
- Do not delete source S3 objects at the DRA repository paths listed above.
