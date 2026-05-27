# jem-bucktst3 DayOA 2.0.7 0.1x Ledger

Created: 2026-05-27T05:25:45Z

## Objective

Run a 0.1x DayOA test workflow on cluster `jem-bucktst3` in `us-west-2` using `day-clone -t 2.0.7`, with the 0.1x inputs discovered from the cloned DayOA repository's `.test_data/data` tree.

## Gate 0 Inventory Freeze

| Item | Evidence |
|---|---|
| Ledger path | `docs/plans/20260527T052545Z_jem_bucktst3_dayoa_207_0p1x_ledger.md` |
| Repo | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| Branch / commit | `main`, `1f834ea2` |
| Git state | `git status --short --branch` showed dirty pre-existing `docs/plans` changes and untracked artifacts; this ledger is the only intended local repo write for this task. |
| User request | Run a 0.1x test from `day-clone -t 2.0.7` and use data from actual DayOA `.test_data/data`. |
| Assumption | "this cluster" means `jem-bucktst3`, from the immediately preceding cluster-delete discussion. |
| Cluster baseline | `pcluster describe-cluster --cluster-name jem-bucktst3 --region us-west-2` returned `clusterStatus=CREATE_COMPLETE`, `computeFleetStatus=RUNNING`, headnode `i-084e068e2e8413877`, headnode state `running`, ParallelCluster `3.13.2`. |
| Local DYEC | `dyec version` returned `Daylily Ephemeral Cluster 5.0.7.dev0+g104fadf31.d20260527`. |
| Safety boundary | No destructive AWS action requested or authorized. All headnode commands must use `daylily_ec.aws.ssm.run_shell` as `ubuntu`. |
| Initial known queue state | Earlier live check at 2026-05-27T05:18:06Z found Slurm job `308`, state `CONFIGURING`, name `kahlo-compute-Q0QEFs.sh`. |

## Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Baseline | Record repo, cluster, local DYEC, assumptions, and safety boundary before live launch. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | Gate 0 table above. |  | Baseline recorded before live clone/launch. |
| HN-001 | Headnode | Verify `jem-bucktst3` headnode readiness, `day-clone`, Slurm, `/fsx`, and current queue/process state. | SUCCESS | contract_test | Gate 2 | orchestrator | SSM as `ubuntu` at 2026-05-27T05:26:57Z: `day-clone=/home/ubuntu/.local/bin/day-clone`, headnode DYEC `5.0.0`, `/fsx` mounted with 4.3T available, Slurm partitions up, `squeue` empty, no Snakemake processes. |  | Headnode is ready for clone and launch. |
| CLONE-001 | DayOA | Run `day-clone -t 2.0.7` into a unique `/fsx/analysis_results/ubuntu/<analysis-id>` destination and verify exact tag. | SUCCESS | feature_implementation | Gate 2 | orchestrator | SSM at 2026-05-27T05:27:34Z: `day-clone -t 2.0.7 -d jem-bucktst3-dyoa207-0p1x-20260527t052745z`; checkout `/fsx/analysis_results/ubuntu/jem-bucktst3-dyoa207-0p1x-20260527t052745z/daylily-omics-analysis`; `git describe --tags --always --dirty -> 2.0.7`; HEAD `0701566c1b5047c14e2b96c566895caa4b7d9d49`. |  | DayOA tag `2.0.7` is cloned and verified. |
| DATA-001 | DayOA test data | Locate the 0.1x input data under cloned repo `.test_data/data` and fail hard if absent or ambiguous. | BLOCKED | contract_test | Gate 2 | orchestrator | Found manifests in the cloned repo: `.test_data/data/agbt_2026/downsample_series/HG003.samples.tsv` and `.test_data/data/agbt_2026/downsample_series/ilmn-solo/HG003_0.1x.units.tsv`. The units row points to `/fsx/control_data/genomic_data/organism_reads/H_sapiens/giab/NovaSeqX_WHGS_TruSeqPF_HG002-007/downsampled/HG003_0.1x_R1.fastq.gz` and `_R2.fastq.gz`; both paths returned `exists=false`. Exact search under cloned `.test_data/data` found no `0.1x` FASTQs; exact search under `/fsx` found no `HG003_0.1x_R1/R2.fastq.gz`. | The requested 0.1x manifests exist, but the actual input FASTQs are not present on the cluster at the manifest paths or in `.test_data/data`. | Blocked rather than substituting a different fixture or coverage level. |
| RUN-001 | DayOA workflow | Launch the smallest appropriate 0.1x workflow from the cloned DayOA checkout using the discovered `.test_data/data` inputs. | BLOCKED | feature_implementation | Gate 2 | orchestrator | No live Snakemake launch performed. | Blocked by `DATA-001`: required 0.1x FASTQs are absent. | Requires the exact `HG003_0.1x_R1.fastq.gz` and `HG003_0.1x_R2.fastq.gz` inputs to be made visible at the manifest paths, or an explicit user-approved replacement input contract. |
| MON-001 | Monitoring | Report live Snakemake/Slurm state and terminal result or blocker. | BLOCKED | legitimate_safety_handling | Gate 5 | orchestrator | Headnode baseline had empty `squeue` and no Snakemake controllers before clone; no workflow was launched after data validation failed. | Blocked by missing requested input data. | Objective is not complete; nothing is running for this 0.1x attempt. |

## Notes

- Do not use fallback input locations. The requested input source is the cloned DayOA `.test_data/data` tree.
- Do not delete or modify existing unrelated cluster/worktree artifacts.

## Terminal Status

As of 2026-05-27T05:34Z, all rows are terminal, but the objective is `BLOCKED`: DayOA `2.0.7` was cloned and the 0.1x manifests were found under `.test_data/data`, but the manifest-referenced 0.1x FASTQs are absent on `jem-bucktst3`. No workflow was launched.
