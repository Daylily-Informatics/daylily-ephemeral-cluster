# testbudgetblock Budget Failure Probe Ledger

Date: 2026-07-04T23:36:18Z

## Objective

Run a standard DayOA Slurm test workflow on DYEC cluster `testbudgetblock`
using AWS profile `lsmc`, and capture evidence that submission fails at the
budget-enforcement check.

No destructive AWS or Slurm action is approved or needed. This probe may create
a new analysis checkout and attempt Slurm submission through the installed
`sbatch` wrapper, but it must stop once the expected budget-check failure is
captured.

## Gate 0: Inventory Freeze

- Controlling ledger: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260704T233618Z_testbudgetblock_budget_failure_probe_ledger.md`
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
  - `git status --short --branch` -> `## jemdev10`
  - branch: `jemdev10`
  - HEAD: `bb75ce01e4a8b42560d667b14e7785c14f2e08d7`
  - exact tag: `10.0.99`
- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
  - `git status --short --branch` -> `## jem-dev...origin/jem-dev`
  - branch: `jem-dev`
  - HEAD: `9c8c014bcc25beb6f6045027f8386695d039af0e`
  - exact tag: `10.0.62`
- Instructions read:
  - `/Users/jmajor/.codex/AGENTS-HOW-TO-RUN-DAYOA.md`
  - `/Users/jmajor/projects/lsmc/AGENTS.md`
  - `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/AGENTS.md`
  - `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`
- Operating contract:
  - Use activated local DYEC checkout for cluster/headnode commands.
  - Use profile `lsmc`.
  - Start with region `us-west-2` unless cluster inspection proves otherwise.
  - Run DayOA work through an interactive `ubuntu` tmux/login shell and `dy-r`.
  - Never invoke raw `snakemake`.
  - Do not cancel, requeue, drain, resume, delete, or mutate cluster state beyond the requested workflow submission attempt.
- Known expectation:
  - `testbudgetblock` is intended to be budget-enforced and the standard Slurm submission should fail before real job admission when the project budget is blocked.

## Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| TBB-001 | Gate 0 | Record repo state, instructions, assumptions, and live-system limits before headnode actions. | SUCCESS | contract_test | Gate 0 | orchestrator | This ledger Gate 0 section. |  | Baseline recorded before headnode workflow action. |
| TBB-002 | Cluster inspection | Confirm `testbudgetblock` is reachable under profile `lsmc` and capture basic headnode/queue state. | SUCCESS | contract_test | Gate 0 | orchestrator | `dyec cluster describe --profile lsmc --region us-west-2 --cluster testbudgetblock` -> `clusterStatus=CREATE_COMPLETE`, `computeFleetStatus=RUNNING`, headnode `i-03dadb54f182e1dbe`; tags include `aws-parallelcluster-enforce-budget=true`, `aws-parallelcluster-project=testbudgetblock`; `dyec headnode jobs ...` -> header only. |  | Cluster is reachable and queue was empty before launch. |
| TBB-003 | Workflow launch | Start a pinned DayOA standard Slurm test in an interactive `ubuntu` tmux/login shell. | SUCCESS | contract_test | Gate 1 | orchestrator | Attempt 1 `tbb_budget_probe_20260704t233618z` cloned DayOA `10.0.62`, but `dy-r help -p -k -j 1` failed before Slurm because current DayOA requires a valid aligner/deduper config. Attempt 2 `tbb_budget_probe2_20260704t2344z` cloned DayOA `10.0.62` and ran `dy-r help -p -k -j 1 --config aligners=[bwa2a] dedupers=[dmd] snv_callers=[deep]` under Slurm activation. |  | Second attempt reached the one-job Slurm DAG and invoked submission. |
| TBB-004 | Budget failure evidence | Capture the expected budget-check failure stderr and confirm whether a Slurm job was admitted. | SUCCESS | contract_test | Gate 1 | orchestrator | `dyec workflow status --session tbb_budget_probe2_20260704t2344z` -> `exit_code=1`, `completed_at=2026-07-04T23:44:32Z`; log showed `Budget enforcement: project 'testbudgetblock' in region 'us-west-2': total=5.0 USD, used=67.479 USD, percent=1349.58%.` and `ERROR: AWS Budget 'testbudgetblock' is exhausted: 1349.58% used (67.479/5.0 USD)` plus `Budget monitor: https://ursa.day.lsmc.bio/ursa-actions#budgets?budget=testbudgetblock`; final `dyec headnode jobs ...` -> header only. |  | Budget wrapper blocked Slurm submission as expected; no job was admitted to the queue. |
| TBB-005 | Final report | Summarize terminal row counts, command evidence, and any blockers. | SUCCESS | contract_test | Gate 5 | orchestrator | Final response will report the two attempts, terminal status, queue state, and ledger path. |  | Ledger rows are terminal and objective evidence is captured. |

## Live Command Log

Commands and observations will be appended here as the probe runs.

- `source ./activate && dyec cluster describe --profile lsmc --region us-west-2 --cluster testbudgetblock`
  - Result: cluster reachable; `clusterStatus=CREATE_COMPLETE`, `computeFleetStatus=RUNNING`, headnode `i-03dadb54f182e1dbe`, headnode state `running`.
  - Relevant tags: `aws-parallelcluster-enforce-budget=true`, `aws-parallelcluster-project=testbudgetblock`, `aws-parallelcluster-monitor-bucket=s3://lsmc-dayoa-references-usw2/runtime_assets/cluster_boot_config`.
- `source ./activate && dyec headnode jobs --profile lsmc --region us-west-2 --cluster testbudgetblock`
  - Result before launch: queue header only, no jobs.
- Attempt 1:
  - Command: `dyec workflow launch --profile lsmc --region us-west-2 --cluster testbudgetblock --analysis-id tbb-budget-probe-20260704t233618z --session-name tbb_budget_probe_20260704t233618z --executing-entity ubuntu --repository daylily-omics-analysis --git-tag 10.0.62 --project testbudgetblock --genome hg38 --jobs 1 --dy-command 'dy-r help -p -k -j 1' --no-input-staging --bootstrap-test-config --no-containerized --export-trigger none`
  - Result: tmux session created and DayOA `10.0.62` cloned to `/fsx/analysis_results/ubuntu/tbb-budget-probe-20260704t233618z/daylily-omics-analysis`.
  - Terminal status: `exit_code=1`, `completed_at=2026-07-04T23:43:01Z`.
  - Not accepted as the budget proof because DayOA failed before Slurm submission with `WorkflowError ... SMN short-read callers require a valid short-read aligner/deduper pair`.
- Attempt 2:
  - Command: `dyec workflow launch --profile lsmc --region us-west-2 --cluster testbudgetblock --analysis-id tbb-budget-probe2-20260704t2344z --session-name tbb_budget_probe2_20260704t2344z --executing-entity ubuntu --repository daylily-omics-analysis --git-tag 10.0.62 --project testbudgetblock --genome hg38 --jobs 1 --dy-command 'dy-r help -p -k -j 1 --config aligners=[bwa2a] dedupers=[dmd] snv_callers=[deep]' --no-input-staging --bootstrap-test-config --no-containerized --export-trigger none`
  - Result: tmux session created and DayOA `10.0.62` cloned to `/fsx/analysis_results/ubuntu/tbb-budget-probe2-20260704t2344z/daylily-omics-analysis`.
  - Terminal status: `exit_code=1`, `completed_at=2026-07-04T23:44:32Z`.
  - Budget evidence:
    - `Budget enforcement: project 'testbudgetblock' in region 'us-west-2': total=5.0 USD, used=67.479 USD, percent=1349.58%.`
    - `ERROR: AWS Budget 'testbudgetblock' is exhausted: 1349.58% used (67.479/5.0 USD)`
    - `Budget monitor: https://ursa.day.lsmc.bio/ursa-actions#budgets?budget=testbudgetblock`
  - Queue result after failure: `dyec headnode jobs --profile lsmc --region us-west-2 --cluster testbudgetblock` returned only the queue header; no Slurm job was admitted.

## Terminal State

- Rows terminal: 5
- Rows in progress: 0
- Rows blocked: 0
- Rows failed: 0
- Objective status: budget enforcement failure reproduced as expected; final response pending.
