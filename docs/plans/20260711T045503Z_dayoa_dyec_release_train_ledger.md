# DayOA and DYEC Release Train Ledger

Date: 2026-07-11

## Objective

Release the current `jem-dev` DayOA head, update DYEC to pin that DayOA release,
release DYEC, then update the DYEC self-pin and publish the final DYEC release.
Preserve and include all existing dirty work in both repositories.

## Gate 0 Baseline

- Controlling ledger: `docs/plans/20260711T045503Z_dayoa_dyec_release_train_ledger.md`
- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Release branch: `jem-dev` in both repositories.
- DayOA: `HEAD == origin/jem-dev == 5bf112c3e4912b06a781d0b671beeb5753f33f2f`; clean worktree; highest semantic tag `10.0.95`; four commits are untagged.
- DYEC: local `82f021fb57ab30595502a01d112fdfad4226c71b`, remote `b02e9b58c28c7f82e635fec18a9dcff313bca4dc`, behind by one commit; highest semantic tag `10.0.157`.
- Existing DYEC dirty scope: `day-clone` source/package/tests, source/package command catalogs and tests, private-deploy-key ledgers, plus this release ledger.
- Remote DYEC commit to incorporate: `b02e9b58 Record DRAGAIN12 native DRAGEN checkpoint`.
- Version plan: DayOA `10.0.96`; DYEC DayOA-pin release `10.0.158`; DYEC self-pin release `10.0.159`.
- Tag contract: annotated, non-`v` semantic tags; never move an existing tag.

## Control Ledger

| ID | Repo | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | DayOA | Validate current `jem-dev`, publish branch, and tag `10.0.96` | SUCCESS | feature_implementation | Gate 5 | orchestrator | Full suite `583 passed`; commit `d0fa125`; annotated remote tag `10.0.96` |  | DayOA branch and tag are published and verified. |
| REL-002 | DYEC | Incorporate `origin/jem-dev` and preserve every existing dirty change | SUCCESS | feature_implementation | Gate 0 | orchestrator | Fast-forwarded `82f021fb..b02e9b58`; all prior dirty and untracked files remained present |  | Remote DRAGAIN12 work and local work are combined. |
| REL-003 | DYEC | Pin active DayOA surfaces to `10.0.96`, validate, commit, push, and tag `10.0.158` | IN_PROGRESS | config_or_startup_contract | Gate 2 | orchestrator | Seven active config/test files advanced from `10.0.95` to `10.0.96`; `pyproject.toml` intentionally has no DayOA dependency |  |  |
| REL-004 | DYEC | Pin active DYEC self-reference to `10.0.158`, validate, commit, push, and tag `10.0.159` | OPEN | config_or_startup_contract | Gate 2 | orchestrator | Current active self-pin is `10.0.156` |  |  |
| REL-005 | Both | Verify annotated local/remote tags, branch synchronization, and terminal ledger state | OPEN | contract_test | Gate 5 | orchestrator | Pending |  |  |

## Terminal Report

Pending.
