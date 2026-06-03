# DayOA / DYEC Release Train Ledger

Created: 2026-06-03T12:34:38Z

## Objective

Publish current DayOA work, update DYEC pins to that DayOA release, publish DYEC, then update DYEC self pins and publish one more DYEC release.

## Gate 0 Inventory

- Control ledger: `docs/plans/20260603T123438Z_dayoa_dyec_release_train_ledger.md`
- DYEC repo: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster`
- DayOA repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
- Instruction files read: `/Users/jmajor/.agents/AGENTS.md`, `/Users/jmajor/.agents/AGENTS-HOW-TO-RUN-DAYOA.md`, `/Users/jmajor/.codex/AGENTS.md`, `/Users/jmajor/.codex/AGENTS-HOW-TO-RUN-DAYOA.md`, `./AGENTS.md`, `./AGENTS-HOW-TO-RUN-DAYOA.md`, `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`
- DayOA status: branch `codex/dayoa-bclconvert-tile-shards-20260601`, clean, synced with `origin/codex/dayoa-bclconvert-tile-shards-20260601`
- DayOA latest numeric semver tag: `2.0.40`; `HEAD...2.0.40` count `3 0`; next release target `2.0.41`
- DYEC status: branch `codex/dyec515-full-catalog-20260531`, synced with `origin/codex/dyec515-full-catalog-20260531`, 72 untracked files before this ledger
- DYEC latest numeric semver tag: `5.1.27`; `HEAD...5.1.27` count `4 0`; next release targets `5.1.28` and `5.1.29`
- DYEC untracked inventory size: `bench_expts` 2.8M, `docs/plans` 68M
- DayOA packaging instruction: after DayOA tag, clear `dist`, run `python -m build`, then run `twup` from interactive zsh.

## Rows

| ID | Repo | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | DayOA | Tag and push current DayOA work as `2.0.41` from clean synced branch. | SUCCESS | release_publish | Gate 5 | Codex | `python -m pytest -q tests/test_bclconvert_multiqc.py tests/test_workflow_catalog.py tests/test_workflow_target_aliases.py tests/test_rule_log_benchmark_contracts.py` in `DAY-EC` -> 34 passed; annotated tag `2.0.41` pushed; `git ls-remote` shows tag object `ccdec5c9...` peeling to commit `54d53b9...`. |  | DayOA branch and release tag are published. |
| REL-002 | DayOA | Build and publish DayOA package after tag using `python -m build` and `twup`. | SUCCESS | release_publish | Gate 5 | Codex | `rm -rf dist/* && python -m build && twup` in zsh/TWINE built `daylily_omics_analysis-2.0.41-py3-none-any.whl` and `.tar.gz`; upload URL `https://pypi.org/project/daylily-omics-analysis/2.0.41/`; `pip index versions` and `pip download daylily-omics-analysis==2.0.41` succeeded. |  | DayOA `2.0.41` is visible and downloadable from the package index. |
| REL-003 | DYEC | Commit dirty/untracked DYEC benchmark and ledger artifacts that belong to the current work. | OPEN | repo_state_publish | Gate 5 | Codex | Pending. |  |  |
| REL-004 | DYEC | Update DYEC DayOA pins to `2.0.41`, test, commit, push, tag `5.1.28`, and publish. | OPEN | dependency_pin_release | Gate 5 | Codex | Pending. |  |  |
| REL-005 | DYEC | Update DYEC self pins to `5.1.28`, test, commit, push, tag `5.1.29`, and publish. | OPEN | dependency_pin_release | Gate 5 | Codex | Pending. |  |  |
| REL-006 | DYEC / DayOA | Verify final branch, tag, package-index, and worktree state. | OPEN | final_acceptance | Gate 5 | Codex | Pending. |  |  |

## Evidence Log

- 2026-06-03T12:34:38Z: Gate 0 inventory recorded before edits or tags.
- 2026-06-03T12:45Z: DayOA `2.0.41` annotated tag pushed and package published.
