# Mermaid DayOA/DYEC Release Train Ledger

Date: 2026-07-29

## Objective

Publish the locked Mermaid/headless-shell readiness repair in DayOA, then
publish one DYEC `16.0.0` release whose active DayOA catalog references pin the
immutable DayOA `13.0.78` release and whose source and packaged self-pins both
resolve to DYEC `16.0.0`.

## Version Plan

- DayOA release: `13.0.78`
- DYEC release and self-pin: `16.0.0`

The originally inferred `13.0.77` and `15.0.25` targets became unavailable
before this train began. The user then explicitly replaced the proposed
`15.0.26`/`15.0.27` sequence with one `16.0.0` release. Remote annotated DayOA
tag `13.0.77` points to `15ecc556eaaad0f9efd44bb0f3e33ad056c0a1bb`;
DayOA `13.0.78` contains it and points to
`8a6afd8c996cf9913810a4de5d9e752f272c4855`. Remote annotated DYEC tag
`15.0.25` points to `95ba95d41a206c781c71683d9b26bf39c91ce0d4`.
Pushed tags will not be moved or overwritten.

## Gate 0 Baseline

- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
  - Branch: `codex/feat-hiomr2-sentieon-cli-fidelity-13.0.72`
  - HEAD and remote branch: `15ecc556eaaad0f9efd44bb0f3e33ad056c0a1bb`
  - Current tag: `13.0.77`
  - Release-owned paths:
    - `config/day/day.yaml`
    - `config/day/day_env_contract.sh`
    - `config/day/day_env_installer.sh`
    - `config/day/npm/mermaid-cli/package.json`
    - `config/day/npm/mermaid-cli/package-lock.json`
    - `dyoainit`
    - `tests/test_shell_wrapper_contracts.py`
  - Other dirty HIOMR2/QC paths predate this release task and must remain
    uncommitted and unmodified.
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
  - Branch: `codex/hiomr2-catalog-repair`
  - Local HEAD and remote branch before reconciliation:
    `f4cc860b8f514d2c3f9658b6b647d7d43a97bee7` (`15.0.24`)
  - Remote `15.0.25^{}` is the direct child
    `95ba95d41a206c781c71683d9b26bf39c91ce0d4`, which pins DayOA `13.0.77`.
    The current branch must fast-forward through it before `16.0.0`.
  - Release-owned non-pin paths:
    - `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`
    - `tests/test_script_entrypoints.py`
    - `docs/plans/20260729T130610Z_dyec_mermaid_headless_readiness_ledger.md`
    - this ledger
  - Pre-existing catalog work enables HIOMR2 TIDDIT and paired library-summary
    behavior in the two catalog copies plus `tests/test_repository_catalog.py`.
    It is not part of this release and will be isolated in a named Git stash,
    then restored after the release.
- Remote availability checks:
  - `13.0.78` is published and `16.0.0` was absent from DYEC `origin`.
  - `13.0.77` and `15.0.25` were present and annotated.
- Local validation already completed for the implementation:
  - DayOA Mermaid-focused tests: `3 passed`
  - DYEC headnode/run-omics-focused tests: `52 passed`
  - `npm ci --dry-run`: passed with 258 locked packages
  - shell syntax and both repos' `git diff --check`: passed
- Take10 is intentionally not part of this release mutation:
  `/fsx/analysis_results/preval-hiomr2/take10-13.0.73/daylily-omics-analysis`
  is detached at clean tracked source tag `13.0.75`, with untracked run inputs
  and generated reports. A read visit was recorded; no headnode files or
  workflow state were changed.

## Control Ledger

| ID | Area/Repo | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | DayOA | Stage only the seven release-owned Mermaid/runtime paths and verify the cached diff. | SUCCESS | release | Gate 1 | orchestrator | Exact-path staging contained seven paths and `3435 insertions, 53 deletions`; all pre-existing HIOMR2/QC paths remained unstaged. Focused tests returned `3 passed`; shell syntax, lock dry-run, and cached diff checks passed. |  | Only the requested Mermaid/runtime repair entered the release commit. |
| REL-002 | DayOA | Commit and push the feature branch, create annotated tag `13.0.78`, push it, and verify the remote peeled commit. | SUCCESS | release | Gate 2 | orchestrator | Commit `8a6afd8c996cf9913810a4de5d9e752f272c4855` (`Fix Mermaid runtime bootstrap`) pushed to `origin/codex/feat-hiomr2-sentieon-cli-fidelity-13.0.72`; `git cat-file -t 13.0.78` returned `tag`; remote `13.0.78^{}` peels to the same commit. |  | DayOA `13.0.78` is published immutably. |
| REL-003 | DYEC | Preserve unrelated catalog edits, then fast-forward the current branch through existing `15.0.25`. | SUCCESS | release | Gate 2 | orchestrator | Fast-forwarded `f4cc860b` to `95ba95d4`; reapplied the named five-file stash, then isolated only the two catalog copies and `tests/test_repository_catalog.py` in `codex-preserve-hiomr2-catalog-before-16.0.0-20260729T133003Z`. |  | Existing HIOMR2 TIDDIT/library-summary work remains outside the release diff. |
| REL-004 | DYEC | Repin every active DayOA default/catalog/test contract from `13.0.77` to `13.0.78` while retaining validated-version history. | SUCCESS | config_or_startup_contract | Gate 3 | orchestrator | Five active tracked files select `13.0.78`; the highest-release commit contract records `8a6afd8c996cf9913810a4de5d9e752f272c4855`; no old active pin remains. |  | All active DayOA launch defaults now select the immutable `13.0.78` release. |
| REL-005 | DYEC | Advance source/package self-pins and their test contract from `15.0.23` to `16.0.0`. | SUCCESS | config_or_startup_contract | Gate 3 | orchestrator | Both global config copies and `tests/test_lsmc_bio_fork_contract.py` select `16.0.0`; no old active self-pin remains. |  | Source and packaged DYEC configuration agree on `16.0.0`. |
| REL-006 | DYEC | Validate the catalog, package copies, release provenance, and generated headnode runner. | SUCCESS | contract_test | Gate 4 | orchestrator | Both source/package `cmp` checks and `git diff --check` passed; focused catalog, registry, fork-contract, and runner tests returned `277 passed in 10.83s`. |  | The scoped release diff is validated. |
| REL-007 | DYEC | Commit and push the scoped release, create annotated tag `16.0.0`, push it, and verify the remote peeled commit. | SUCCESS | release | Gate 5 | orchestrator | Release commit `9f59f0f3953ed3cea8ce9eec4c1d489feabe6569` pushed on `codex/hiomr2-catalog-repair`; annotated tag object `46477c8589f52322ac221c46d56635f88af0409a` was pushed and remote `16.0.0^{}` peels to the release commit. |  | DYEC `16.0.0` is published immutably. |
| REL-008 | Cross-repo | Restore preserved local catalog edits and verify branch head, annotated tag type, remote peeled commit, and residual dirty scope. | SUCCESS | release | Gate 5 | orchestrator | The named release stash was popped without conflicts and removed; both catalog copies remain byte-identical at DayOA `13.0.78`, while only the preserved HIOMR2 TIDDIT/library-summary changes and their test are tracked-dirty. Older unrelated stashes remain untouched. |  | Release provenance is verified and user work is restored. |

## Final Report

All rows terminal: yes

Objective complete: yes

Status counts:

- SUCCESS: 8
- FAIL: 0
- BLOCKED: 0
- IN_PROGRESS: 0
- OPEN: 0

Changed files:

- both active catalog copies and both active global-config copies;
- the three pin/provenance test contracts;
- the generated headnode runner and its test;
- the completed Mermaid implementation ledger and this release ledger.

Validation:

- source/package catalog copies: byte-identical;
- source/package global configs: byte-identical;
- focused pytest selection: `277 passed in 10.83s`;
- `git diff --check`: passed.

Residual risks:

- Take10 remains on DayOA `13.0.75`; updating it was not requested and would
  require a separate analysis-root write action.
- The requested Take13 `hiomr2` launch remains paused; only its untracked
  launch ledger was created before the release request superseded that work.
