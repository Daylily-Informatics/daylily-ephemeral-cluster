# Ultima and ONT RunQC mainline integration ledger

Created: 2026-07-27T03:00:00Z  
Scope: publish the non-regressive standalone Ultima RunQC implementation and
the durable ONT/Ultima RunQC execution records, using separate DayOA and DYEC
pull requests to GitHub `main`. Do not stage unrelated local records, logs, or
worktrees.

## Gate 0: inventory freeze

- DayOA source: `/Users/jmajor/projects/lsmc/daylily-omics-analysis-ultima-runqc`,
  branch `codex/ultima-run-qc-standalone`, commits `3b1780f9..00153c2e`.
  It differs from current GitHub `main` in the standalone Ultima controller,
  native report producer, rule wiring, and focused tests.
- DayOA integration branch:
  `codex/ultima-runqc-main-20260727`, created from current GitHub `main`
  `41863cb4`.
- DYEC integration branch:
  `codex/ont-ultima-ledgers-main-20260727`, created from current GitHub
  `main` `18846431`.
- DYEC source code for the ONT environment contract is already on GitHub main
  through the merged RunQC environment PR. The only DYEC work selected here is
  the explicit ONT run context and the durable Ultima controller/export
  receipts listed below.
- Explicit DYEC paths selected for staging:
  `docs/plans/20260726T225400Z_preval_ont_set4_fc1_runs.tsv`,
  `docs/plans/20260726T231553Z_ursa_ultima_604395_seq_qc_ledger.md`,
  `docs/plans/20260726T231553Z_ursa_ultima_604395_seq_qc_runs.tsv`, and the
  four matching `20260726T231553Z_ursa_ultima_604395_seq_qc_*` receipt
  directories. No other untracked repository content is in scope.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DAY-001 | DayOA | Rebase the five standalone Ultima RunQC commits on current GitHub main without losing current main behavior. | SUCCESS | feature_implementation | Gate 1 | Codex | Cherry-picks retained the current ONT/Illumina side of conflicts and isolated the scratch NVMe additions to Ultima rules. |  | Current ONT/Illumina rule behavior remains the merge authority. |
| DAY-002 | DayOA | Run focused tests and a merge/diff check on the rebased implementation. | SUCCESS | contract_test | Gate 5 | Codex | `PYTHONPATH=$PWD pytest -q tests/test_analysis_artifacts.py tests/test_run_qc_reports.py tests/test_ultima_run_qc_to_multiqc.py` -> 32 passed; `git diff --check origin/main...HEAD` passed. |  | Rebased implementation is focused-test clean. |
| DYE-001 | DYEC | Commit only the scoped ONT run context and durable Ultima execution/export records. | SUCCESS | feature_implementation | Gate 1 | Codex | Exact content parity against source records passed for all nine selected records; `git diff --check` passed. |  | No unrelated dirty files were staged. |
| PUB-001 | GitHub | Push both scoped branches, open PRs to main, and merge only after validation. | IN_PROGRESS | feature_implementation | Gate 5 | Codex | User explicitly authorized commit, push, PR, and merge. |  |  |

## Final report

All rows terminal: pending.  
Objective complete: pending.
