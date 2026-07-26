# DYEC Cost-Center Creation, Launch Propagation, and HIOMR2 Recovery Ledger

Date: 2026-07-26

## Control Ledger

Controlling plan: user request in this task to create the `bjuice` cost center, make `dyec create` provision a valid cost center when Slurm accounting is enabled, expose an explicit cost-center workflow-launch input, and rerun the blocked HG003 HIOMR2 workflow.

Ledger path: `docs/plans/20260726T095455Z_dyec_cost_center_create_and_launch_ledger.md`

### Gate 0 baseline

- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` at `jem-candidate-260725`; the DayOA-command pin work advanced the shared branch to `c65c9dca` / `14.0.14` during this task. The worktree has numerous pre-existing untracked ledgers, artifacts, recordings, and temporary directories; this work owns only this ledger and the source/tests subsequently named here.
- Source sweep: `rg -n -C 3 "budget_monitor_url|cost_center_monitor_url|_PostCreateInputs|_resolve_post_create_inputs|def workflow_launch|def build_parser|--project|cost-center|cost_center" daylily_ec config/day_cluster/sbatch tests`.
- Wrapper baseline: `config/day_cluster/sbatch` calls undefined `budget_monitor_url` and `cost_center_monitor_url` at its reporting lines. The deployed `preval-hiomr2` wrapper has the same defect.
- Create baseline: `daylily_ec/workflow/create_cluster.py` currently collects cluster/global budget inputs but does not collect, validate, or create a cost-center registry record.
- Launch baseline: `dyec workflow launch` accepts `--project` but not `--cost-center`; its headnode controller passes the project into `dyoainit`, which becomes Slurm `--comment` through DayOA's submit helper.
- Live baseline: `preval-hiomr2` is up in `us-west-2`; `bjuice` is absent from `dayec-cost-centers`; the prior HIOMR2 controller exited before the first Slurm job was accepted. Cluster AWS Budget is `$200`, usage `$0` at inspection.
- Approval record: the user first requested a `$500` increase, was shown the cluster `$200 -> $700` proposal, then directed “fix the budget and then please run the hiomr2 run... fix whatever is blocking this.” This is the second approval for the `$700` cluster and `bjuice` caps plus the supported wrapper refresh. No job, service, partition, or node intervention is authorized.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| CC-001 | DYEC create | Collect explicit cost-center name, monthly cap, and allowed submitters at the start of the budget/accounting inputs; validate and create the registry plus current usage record when Slurm accounting/enforcement is enabled. | IN_PROGRESS | feature_implementation | Gate 2 | Codex | `daylily_ec/workflow/create_cluster.py`; `daylily_ec/aws/cost_centers.py`; `tests/test_workflow.py` |  | Awaiting final suite and publication. |
| CC-002 | DYEC workflow launch | Expose explicit `--cost-center`, validate it, preserve the value in the controller receipt, and export it as `DAY_PROJECT` before `dy-r` so Slurm submission uses the chosen cost center. | IN_PROGRESS | feature_implementation | Gate 3 | Codex | `daylily_ec/cli.py`; `daylily_ec/repositories.py`; `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` |  | Awaiting final suite and publication. |
| CC-003 | DYEC sbatch wrapper | Define the monitor URL helper functions used by the wrapper so budget/cost-center reporting does not fail before registry validation. | IN_PROGRESS | feature_implementation | Gate 2 | Codex | source/payload wrapper mirrors; `tests/test_sbatch_wrapper.py` | Missing helper definitions caused `budget_monitor_url: command not found`. | User explicitly rejected direct `/opt/slurm/bin/sbatch` installation; future cluster bootstrap remains the only wrapper delivery path. |
| CC-004 | DYEC tests/docs | Add focused contract tests for create, launch propagation, and wrapper behavior; document the explicit no-default cost-center contract. | IN_PROGRESS | contract_test | Gate 5 | Codex | focused suite passed before final script-level coverage addition; README updated |  | Full focused rerun pending. |
| CC-005 | Live `preval-hiomr2` | Create active `bjuice` registry and current-month usage entries using the approved cap and permitted submitters. | SUCCESS | config_or_startup_contract | Gate 2 | User + Codex | `aws budgets describe-budget` confirms `$700`; `dyec cost-centers show bjuice` confirms active `$700`, allowed user `ubuntu`, created `2026-07-26T10:15:38Z` |  | Registry and initial usage record were created. |
| CC-006 | Live `preval-hiomr2` | Do not make any further direct `/opt/slurm/bin/sbatch` changes; submit only through the DYEC workflow CLI. | SUCCESS | config_or_startup_contract | Gate 2 | User + Codex | User explicitly directed “you should not be hackinh sbatch”; cancellation was requested after the already-completed managed refresh. | The source-level direct-install attempt was removed immediately. | No further wrapper or Slurm-service action will be taken. |
| CC-007 | Live HIOMR2 workflow | Relaunch the existing five-shard HG003 HIOMR2 request through `dyec workflow launch --cost-center bjuice`; monitor only. | OPEN | active_product_contract | Gate 3 | User + Codex | prior live controller exited before first job acceptance | Depends on CC-006; workflow writes require existing analysis-root lock/visit contract. | Launch a fresh analysis id after the wrapper is verified. |
