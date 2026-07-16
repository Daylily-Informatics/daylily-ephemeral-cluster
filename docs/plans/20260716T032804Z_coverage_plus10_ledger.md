# DYEC statement coverage plus 10 percentage points ledger

Created: `2026-07-16T03:28:04Z`

## Objective

Increase `daylily_ec` statement coverage by at least 10.00 absolute percentage
points using executable behavioral tests. Do not change the denominator,
exclude source, omit files, add pragma-based suppression, or weaken test
collection to manufacture the increase.

## Gate 0 inventory

- Clean worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-coverage-plus10-20260716`
- Branch: `codex/coverage-plus10-20260716`
- Baseline ref: `origin/main` at `2329bccb6a443490cde3b11423623b3b1fc0ab56`
- Preserved active checkout: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
  on `codex/dyec-self-pin-10317`, with 51 tracked and 75 untracked status
  entries. It is outside this ledger's write scope.
- Measurement command:
  `pytest -q --cov=daylily_ec --cov-report=term --cov-report=json:<path>`
- Baseline: 19,327 statements; 15,589 covered; 3,738 missed; 80.66% exact.
- Test result: 1,693 passed, 11 skipped, one dependency warning.
- Baseline exact coverage: `80.6591814559942%`.
- The MaxCount product repair added three executable statements, so final
  acceptance uses the legitimate 19,330-statement denominator rather than
  manufacturing an unchanged denominator. A 10.00-point gain requires at
  least 17,525 covered statements (`90.66218313502328%`).
- No AWS, cluster, Slurm, workflow, budget, deployment, release, or destructive
  action is in scope.

## Control ledger

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| COV-DYEC-001 | Baseline | Freeze exact denominator, clean ref, dirty-checkout boundary, and baseline result. | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 above; coverage JSON `/tmp/dyec_coverage_plus10_baseline.json`. |  | Baseline and acceptance arithmetic are fixed. |
| COV-DYEC-002 | Coverage inventory | Rank missed executable behavior and select high-value test surfaces without exclusions or denominator changes. | SUCCESS | contract_test | Gate 1 | orchestrator | Baseline and authoritative intermediate JSON inventories drove non-overlapping gap tests across CLI, validation, create/accounting, staging, storage, repositories, export, cost, headnode, locks, Dewey, and Sentieon. |  | Final gap tests intersected only lines missing from the full-run JSON. |
| COV-DYEC-003 | Tests | Add behavioral tests sufficient to gain at least 10.00 absolute statement-coverage points. | SUCCESS | contract_test | Gate 2 | orchestrator | 504 new behavioral tests; final 17,634 covered versus 15,589 baseline, a net +2,045 covered statements while product source grew by three statements. |  | No exclusions, omitted files, pragma suppression, or coverage-config changes. |
| COV-DYEC-004 | Verification | Run focused tests, complete suite with identical coverage command, Ruff, Black check, and diff check. | SUCCESS | contract_test | Gate 3 | orchestrator | `2,197 passed, 11 skipped`; 19,330 statements, 17,634 covered, 1,696 missed, `91.22607346094154%`; Ruff, Black, template parity, and diff checks pass. Mypy reports the exact same 10 pre-existing `create_cluster.py` findings at base and current. |  | Exact gain is `10.56689200494734` points. |
| COV-DYEC-005 | Integration | Preserve unrelated work, commit intentionally, publish normal PR, and record terminal evidence. | IN_PROGRESS | feature_implementation | Gate 4 | orchestrator | Final fetch remained a no-op at `origin/main=2329bccb6a443490cde3b11423623b3b1fc0ab56`; commit/push/PR pending. |  |  |

## Final report

All rows terminal: `no`

Objective complete: `no`
