# DYEC AWS Budget set-limit 18.0.11 release ledger

Created: 2026-08-15T23:39:57Z

## Objective

Restore pushed commit `60eff1f6ffcb575c2c5b8eebb0bef84e57c106bb`, make the
AWS Budget limit-update command release-grade, and publish the next immutable
DYEC patch release without changing any live AWS Budget.

## Gate 0 baseline

- Controlling ledger:
  `docs/plans/20260815T233957Z_budget_set_limit_18011_release_ledger.md`.
- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`.
- Branch: `codex/aws-budget-set-limit-20260815`, restored at pushed commit
  `60eff1f6ffcb575c2c5b8eebb0bef84e57c106bb`.
- Base release: annotated tag `18.0.10`, peeled commit
  `6e91ecf313e14145193d0d69bb97989ea2156f07`.
- Next unused patch inferred from the numeric tag sequence: `18.0.11`.
- Pre-existing unowned paths: `TrusSV/` and
  `tmp/dayoa-ont-headnode-proof/`; neither will be staged or changed.
- Restored diff baseline: 115 inserted lines in `daylily_ec/aws/budgets.py`
  and `daylily_ec/cli.py`; no tests or operator documentation accompanied the
  original commit.
- Focused baseline:
  `python -m pytest -q tests/test_budgets.py tests/test_cli_registry_v2.py tests/test_cli_docs_contract.py`
  -> `280 passed, 2 failed`. The expected gaps are the unregistered test-tree
  expectation for `aws budget set-limit` and the unreleased `18.0.11` docs
  baseline.
- Live safety boundary: this release work will not call `UpdateBudget`, change
  an AWS Budget or cost center, or treat release authorization as approval for
  a live budget-cap increase.
- Publication boundary: Git commit, PR, annotated tag, and GitHub release are
  in scope. PyPI publication is not requested.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval gate | Owner | Evidence | Root cause | Terminal note |
|---|---|---|---|---|---|---|---|---|---|
| RESTORE-001 | Git | Restore the pushed budget branch at exact commit `60eff1f6` without losing other work | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | Local and `origin/codex/aws-budget-set-limit-20260815` both resolve to `60eff1f6`; unowned paths remain untouched |  | Restored branch is the implementation base. |
| API-001 | AWS Budgets | Preserve the existing fixed-budget contract while changing only the explicit monthly USD limit | SUCCESS | feature_implementation | Gate 4 | orchestrator | The updater preserves exactly one complete legacy or expression filter contract, omits read-only fields, and verifies the post-update cap |  | Fixed COST/MONTHLY/USD budgets are the only supported shape. |
| SAFE-001 | CLI | Require explicit target/current/new cap evidence and provide non-mutating planning before a live update | SUCCESS | legitimate_safety_handling | Gate 4 | orchestrator | Required `--expected-current-monthly-cap-usd`, non-mutating `--dry-run`, stale-cap rejection, and equal-cap no-op implemented |  | No AWS write was made during release validation. |
| TEST-001 | Tests | Add unit, CLI, JSON, no-op, mismatch, invalid-budget, and registry-policy coverage | SUCCESS | contract_test | Gate 5 | orchestrator | Focused suite: `305 passed` in 25.80 seconds |  | Tests use mocked AWS clients only. |
| DOC-001 | Docs | Document the command, safety boundary, and current release as `18.0.11` | SUCCESS | active_product_contract | Gate 5 | orchestrator | README, CLI reference, operations runbook, environment/testing/start docs, and docs contract now identify `18.0.11` |  | Live increases still require the separate approval process. |
| GATE-001 | Validation | Pass focused behavioral and proportional static repository gates | SUCCESS | contract_test | Gate 5 | orchestrator | `305 passed`; `python -m compileall -q daylily_ec`; fatal Ruff selectors passed; `git diff --check` passed |  | Full suite intentionally omitted at the user's request because this is a small, focused change. |
| RELEASE-001 | Release | Commit, push the restored branch, and publish annotated tag `18.0.11` | SUCCESS | feature_implementation | Gate 5 | orchestrator | Release transaction commits and pushes the guarded restoration, then creates and pushes immutable annotated tag `18.0.11` |  | User explicitly narrowed publication to commit, push, and tag; no PR or GitHub release object. |

## Final report

All rows terminal: yes

Objective complete: yes

Status counts:

- SUCCESS: 7
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
- IN_PROGRESS: 0
- OPEN: 0

Validation:

- Focused baseline: `280 passed, 2 failed` for the expected unreleased command
  and documentation contracts.
- Focused release gate: `305 passed` in 25.80 seconds.
- Static release gate: package compile, fatal Ruff selectors, and
  `git diff --check` passed.
- The full suite was not run, per the user's explicit request to keep
  validation proportional to this small change.

Residual risks:

- AWS documents that updating a budget temporarily resets calculated spend to
  zero until usage data is refreshed; this release performs no live update.
