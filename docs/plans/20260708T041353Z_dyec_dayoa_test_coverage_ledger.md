# DYEC + DayOA Test Coverage Expansion Ledger

Date: 2026-07-08T04:13:53Z

## Scope

Improve local test completeness and coverage quality for:

- DYEC: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DayOA: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`

No live AWS, Slurm, SSM, or DayOA workflow execution is in scope. DayOA workflow commands must not be launched directly from this ledger.

## Gate 0 Baseline

- DYEC branch/status: `jemdev10`, dirty with existing tracked/untracked changes before this ledger.
- DayOA branch/status: `jem-dev...origin/jem-dev`, dirty with existing tracked changes before this ledger.
- DYEC collection: `source ./activate && pytest --collect-only -q` -> `1241 tests collected`.
- DYEC full coverage baseline: `1231 passed, 8 skipped, 2 failed`, total coverage `82.38%`; failures in `tests/test_renderer.py` for missing `REGSUB_SPOT_PRICE_WARN_THRESHOLD` expectation.
- DayOA collection with explicit interpreter: `/Users/jmajor/miniconda3/envs/DAY-EC/bin/python -m pytest --collect-only -q` -> `392 tests collected`.
- DayOA full coverage baseline: `389 passed, 3 failed`, total package coverage `83.75%`; failures in `workflow/rules/parascopy.smk` log/benchmark contract and README tool-catalog docs contract.
- DayOA coverage boundary: `pyproject.toml` only covers `daylily_omics_analysis`, not active Snakemake rule files or workflow scripts.
- Safety boundary: no live cluster mutation, no raw DayOA workflow run, no destructive actions.

## Rows

| ID | Repo | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| GATE0 | Both | Record baseline, dirty state, collection, and failing test evidence. | SUCCESS | contract_test | Gate 0 | orchestrator | Baseline above. |  | Baseline captured before edits. |
| DYEC-FAIL-001 | DYEC | Repair renderer substitution-key contract tests for current template token set. | SUCCESS | contract_test | Gate 1 | orchestrator | `tests/test_renderer.py` now expects 53 keys and includes `REGSUB_SPOT_PRICE_WARN_THRESHOLD`; focused suite `pytest -q tests/test_renderer.py tests/test_tests_runner.py tests/test_spot_pricing.py` -> `70 passed`. |  | Renderer contract now matches the current token set. |
| DAYOA-FAIL-001 | DayOA | Repair current DayOA rule/docs contract failures. | SUCCESS | contract_test | Gate 1 | orchestrator | `workflow/rules/parascopy.smk` aggregate target now has log+benchmark directives; `tests/test_tool_catalog_docs.py` asserts current `dyec headnode connect` contract; focused DayOA suite -> `13 passed`. |  | Current DayOA failures are repaired without launching workflows. |
| DYEC-COV-001 | DYEC | Add meaningful tests around coverage runner behavior so `dyec tests pytest --coverage` remains a real gate. | SUCCESS | contract_test | Gate 1 | orchestrator | `daylily_ec/tests_runner.py` rejects `--no-cov` and `--cov-fail-under*` when `--coverage` owns the gate; `tests/test_tests_runner.py` covers default quiet command, current interpreter use, and CLI rejection. |  | Coverage gate cannot be weakened through forwarded pytest args. |
| DYEC-COV-002 | DYEC | Add meaningful spot warning/summary coverage beyond token presence. | SUCCESS | contract_test | Gate 1 | orchestrator | `tests/test_spot_pricing.py` now verifies partition raw min/max costs, uncapped bid, final bid, and warn-threshold behavior separately. |  | Spot summary tests now validate Ursa-facing numeric fields, not only presence. |
| DAYOA-COV-001 | DayOA | Expand coverage of rule-level log/benchmark and shell-test harness contracts. | SUCCESS | contract_test | Gate 1 | orchestrator | `tests/README.md` documents shell, rule, parser, and wrapper contract gates; `README.md` includes shell test commands. |  | Shell and rule contract gates are named in test docs and enforced by a new coverage-boundary test. |
| DAYOA-COV-002 | DayOA | Add a coverage guard documenting that workflow scripts/rules are outside package coverage and must stay under explicit contract tests. | SUCCESS | contract_test | Gate 1 | orchestrator | New `tests/test_coverage_contracts.py` asserts package coverage source/threshold, required workflow contract gates, and that rule/script surface materially exceeds package coverage scope. |  | Coverage report boundary is now executable and explicit. |
| VERIFY | Both | Run focused tests and coverage checks, record terminal state. | SUCCESS | contract_test | Gate 5 | orchestrator | DYEC focused `70 passed`; DYEC full coverage `1239 passed, 8 skipped`, total `82%`; DayOA focused `13 passed`; DayOA full coverage `395 passed`, total `83.75%`; `ruff check` on changed DYEC Python passed; `py_compile` on new DayOA tests passed; `git diff --check` passed in both repos. |  | All ledger rows terminal; no live workflow/AWS actions were performed. |

## Final Report

- DYEC local coverage is green after the changes: `1239 passed, 8 skipped`, total package coverage `82%`.
- DayOA local coverage is green after the changes: `395 passed`, total package coverage `83.75%`.
- DayOA package coverage remains intentionally scoped to `daylily_omics_analysis`; the new test documents and enforces that workflow rules/scripts require separate contract gates.
- No raw DayOA workflow execution, live AWS action, Slurm action, or destructive operation was performed.
