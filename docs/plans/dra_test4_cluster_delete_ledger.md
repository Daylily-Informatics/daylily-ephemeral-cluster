# dra-test4 Cluster Delete Ledger

Date: 2026-05-18

## Objective

Delete the AWS ParallelCluster cluster `dra-test4` in `us-west-2` after recording live inventory and receiving the required second explicit approval for the destructive action.

## Gate 0: Inventory Freeze

| Item | Evidence |
|---|---|
| Controlling SOP | `/Users/jmajor/.codex/docs/plan-ledger-workflow.md` |
| Ledger path | `docs/plans/dra_test4_cluster_delete_ledger.md` |
| Repo path | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| Local git baseline | `git status --short --branch` -> `## main...origin/main`; dirty DayOA pin/docs/test files, prior export ledger update, untracked GIAB validation ledger, and untracked export receipt directory were present before this delete ledger. |
| Current time | `date -u +%Y-%m-%dT%H:%M:%SZ -> 2026-05-18T14:04:04Z` |
| Cluster state | `AWS_PROFILE=lsmc pcluster describe-cluster --cluster-name dra-test4 --region us-west-2` -> `clusterStatus=CREATE_COMPLETE`, `computeFleetStatus=RUNNING`, headnode `i-0d85f5c6569c7e475`, headnode state `running`, headnode type `r7i.2xlarge`, private IP `10.0.0.56`. |
| FSx state | FSx tagged to `dra-test4`: `fs-0bcf5a60d9b48f03e`, lifecycle `AVAILABLE`, deployment `SCRATCH_2`, storage capacity `2400` GiB, mount name `vbnz3b4v`. |
| Headnode state | SSM as `ubuntu`: host `ip-10-0-0-56`, load average `0.16, 0.12, 0.12`, `/fsx` usage `419G` used of `2.2T` (`19%`). |
| Jobs/session state | `dyec headnode jobs --profile lsmc --region us-west-2 --cluster dra-test4` returned only the header; SSM `tmux ls` returned no sessions. |
| Active DRA inventory | `dyec delete --dry-run` and FSx association listing showed active DRAs: `dra-03b5c7431ba062ae0` at `/run_dir_mounts/20260424_ONT_100ul/`, `dra-05ced18cd0aa0f3db` at `/run_dir_mounts/20260427_ONT_300ul/`, `dra-0c5f310f558ca6946` at `/run_dir_mounts/20260513_ONT_HG003/`, `dra-0bffcc0b7979c4e19` at `/analysis_results/ubuntu/run_qc_illumina_all/`, `dra-0464a323ae90abaf9` at `/analysis_results/ubuntu/illumina_run_qc/` with lifecycle `MISCONFIGURED`, and `dra-088ced7bcccf07336` at `/data/`. |
| Active export tasks | `aws fsx describe-data-repository-tasks` for `fs-0bcf5a60d9b48f03e` filtered to `PENDING`, `EXECUTING`, or `FAILED` returned `[]`. |
| Recent export proof | Fresh ONT QC export task `task-092aab06bcc1b24d5` previously completed `SUCCEEDED` with `TotalCount=3611`, `SucceededCount=3611`, `FailedCount=0`, and temporary DRA `dra-0a1d444f47e53de71` detached/deleted. |
| Delete dry-run | `dyec delete --profile lsmc --region us-west-2 --cluster-name dra-test4 --dry-run` -> no AWS resources changed; warned about FSx `fs-0bcf5a60d9b48f03e` and active DRAs above. |
| Destructive command prepared, not run | `dyec delete --profile lsmc --region us-west-2 --cluster-name dra-test4 --yes` |
| Live-system limit | Cluster deletion is destructive and has not been approved with the required second explicit confirmation yet. Do not run the live delete until the user confirms after this warning. |

## Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Baseline | Record repo, cluster, FSx, DRA, export-task, job, and headnode inventory before destructive delete. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | Gate 0 table above. |  | Baseline recorded before live deletion. |
| DRY-001 | Dry run | Run a supported delete dry-run and capture affected resources. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | `dyec delete --profile lsmc --region us-west-2 --cluster-name dra-test4 --dry-run` reported no AWS changes and listed the active FSx/DRA inventory. |  | Dry-run complete; no AWS resources were changed. |
| PRE-001 | Safety | Verify no active Slurm jobs, tmux sessions, or active export tasks are running. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | `dyec headnode jobs` header only; SSM `tmux ls` no sessions; active export task query returned `[]`. |  | No live workload or active export task found. |
| DEL-001 | Delete | Execute destructive cluster deletion only after second explicit approval. | BLOCKED | legitimate_safety_handling | Gate 5 | orchestrator | Prepared command: `dyec delete --profile lsmc --region us-west-2 --cluster-name dra-test4 --yes`. | Destructive AWS approval required after warning. | Blocked until user replies with explicit confirmation for live cluster deletion. |
| REP-001 | Reporting | Report current terminal state and confirmation string. | SUCCESS | plan_amendment | Gate 5 | orchestrator | Final status counts below. |  | Reported that live deletion is blocked pending explicit confirmation. |

## Current Status Counts

| Status | Count |
|---|---:|
| SUCCESS | 4 |
| BLOCKED | 1 |
| OPEN | 0 |
| IN_PROGRESS | 0 |
| ATTEMPTING_BUGFIX | 0 |
| FAIL | 0 |
| DUPLICATE | 0 |
| NO_LONGER_NEEDED | 0 |

