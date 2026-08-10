# Take inflection-package monitor ledger

Timestamp: `2026-07-30T13:52:24Z`

## Objective

Inspect the currently monitored `take*` DayOA analysis roots on
`preval-hiomr2`. For any upstream HIOMR2 workflow that is demonstrably
terminal-success, run the existing inflection analytical-package workflow
target using that root's exact initialized DayOA contract. Do not infer
completion from an empty Slurm queue, take over a foreign write lock, alter
active jobs, or invent package inputs.

## Gate 0

- Cluster: `preval-hiomr2`, region `us-west-2`, headnode
  `i-0b70541bdad454c76`, remote user `ubuntu`.
- Initial queue mapping:
  - `take20`: job `1058`, `sentdhiomr2_hybrid_cli170`, RUNNING.
  - `take21`: jobs `1102`, `1128`, `1134`, `1137`, and `1140`, RUNNING.
  - `take25`: attached tmux controller, with no job identified in the initial
    queue snapshot.
- Read-only inspection precedes any lock or package launch.
- A package launch is eligible only after terminal controller evidence, exact
  target/config recovery, absent foreign lock, and a newly owned write lock.

## Control ledger

| ID | Root | Requirement | Status | Evidence | Terminal note |
|---|---|---|---|---|---|
| INVENTORY-001 | all | Record current tmux, Slurm, root, visit, and lock/controller evidence. | SUCCESS | Read visits recorded for all three roots. Locks: `take20` owned by `codex-take20-hiomr2-20260730T110831Z`; `take21` by `codex-take21-hiomr2-20260730T120330Z`; `take25` by `codex-take25-hiomr2-13094-20260730T134459Z`. | Exact current owners preserved; no takeover requested. |
| TAKE20-001 | `take20` | Establish upstream terminal state and exact package target/config. | NOT_ELIGIBLE | Live controller command targets only `produce_sentdhiomr2 produce_snv_concordances`; job `1058` remains RUNNING. Selected overlay leads to `config/hiomr2_hg003_5x_cli_comparison.yaml`, which sets `allow_inflection_package: false`; no owner-issued package batch id is supplied. | Active and explicitly package-disabled; no package launch. |
| TAKE21-001 | `take21` | Establish upstream terminal state and exact package target/config. | ALREADY_IN_GRAPH | Live controller is at `120 of 297` steps (`40%`) with multiple jobs RUNNING. Exact command already includes `produce_sentdhiomr2_inflection_analytical_package`, `hiomr2_inflection_package_mode=analytical`, and `seqone_delivery_batch_id=take21`. | Existing controller will package after upstream dependencies; no duplicate launch. |
| TAKE25-001 | `take25` | Establish upstream terminal state and exact package target/config. | NOT_ELIGIBLE | Foreign lock-owning controller has cloned DayOA `13.0.94` at commit `9b8b13173b9cf442158de5cdb69401efcac81651` but has not initialized or launched DayOA. No Take25 Slurm job is present. | Clone-only state is not workflow completion. |
| PACKAGE-001 | eligible roots | Acquire each eligible root's write lock and run its existing inflection package target via initialized `dy-r`. | NOT_APPLICABLE | No inspected root is eligible for a new launch; Take21 already owns the target in its active graph. | No write lock acquired and no controller submitted. |
| CLOSE-001 | all | Preserve terminal evidence, release any newly acquired lock, and report exact outcomes. | SUCCESS | Current state recorded in this ledger; no lock was acquired by this monitor. | Inspection closed without mutation. |
