# DYEC Headnode Force Conda Clean Release Ledger

Date: 2026-08-20

## Scope

Make `dyec headnode configure --force` run a non-interactive `conda clean --all` after removing the named `DAYOA` and `DAY-EC` environments and before rebuilding them. Publish the minimal patch as annotated tag `19.0.2` without creating a GitHub Release or package distribution.

## Gate 0: Inventory Freeze

- Controlling request: add Conda cache cleanup to the existing `--force` reset path, commit, push the feature branch, create a new version tag, and push the tag.
- Worktree: `/Users/jmajor/.codex-worktrees/dyec-headnode-force-conda-clean-19.0.2`.
- Branch: `codex/headnode-force-conda-clean`.
- Base: maximum fetched `19.0.*` annotated tag `19.0.1`, commit `4303fdded2d4d21322d10ce04791a52da1384c00`.
- Candidate: `19.0.2`; absent from local and `origin` tag refs at Gate 0.
- Baseline state: clean feature worktree created directly from `19.0.1`.
- Source inventory: `_build_headnode_conda_environment_reset_command()` removes `DAYOA` and `DAY-EC` and deletes the bootstrap receipt, but contains no `conda clean` command.
- Triggering evidence: two `pclu-18045` forced rebuild commands failed with `CondaError: Prefix record 'rclone' already exists`; Conda explicitly recommended `conda clean --all`.
- Implementation boundary: run `conda clean --all --yes` only in the existing explicit `force=True` reset step, after the environment-removal loop. Non-force configuration remains unchanged.
- Catalog boundary: no command eligibility, DayOA pin, target, or `current` catalog change is required for this headnode-only patch.
- Validation boundary: per user instruction, do not run pytest or repository test suites. Review the exact diff and use Git whitespace validation only.
- Publication boundary: commit, push branch, create and push annotated tag; do not open/merge a PR, create a GitHub Release, build distributions, or publish packages.

## Control Ledger

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| HC-001 | DYEC headnode force reset | Add non-interactive full Conda cleanup after both named environments are removed | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | `_build_headnode_conda_environment_reset_command()` now emits `conda clean --all --yes` after the environment-removal loop and before bootstrap-receipt removal; both CLI help surfaces disclose the behavior. |  | Non-force configuration remains unchanged. |
| HC-002 | DYEC tests | Add a focused contract assertion for cleanup presence and ordering | SUCCESS | contract_test | Gate 5 | orchestrator | `tests/test_workflow.py` asserts exactly one cleanup command and its ordering after `done` and before receipt removal. Test execution intentionally omitted by user instruction. |  | Contract coverage added without executing a test suite. |
| HC-003 | DYEC release | Review exact scope, commit, push branch, annotate `19.0.2`, and push tag | OPEN | feature_implementation | Gate 5 | orchestrator | Candidate tag and branch were unoccupied at Gate 0 |  |  |
| HC-004 | Publication boundary | Do not run test suites or create a GitHub Release/package publication | SUCCESS | plan_amendment | Gate 5 | orchestrator | No pytest or repository test command was run; no PR, GitHub Release, distribution build, or package publication was performed. `git diff --check` returned `rc=0`. |  | Requested publication boundary preserved. |

## Final Report

All rows terminal: no

Objective complete: no

Status counts:

- SUCCESS: 3
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
- IN_PROGRESS: 0
- OPEN: 1

Validation: exact diff review and `git diff --check -> rc=0`; test suites intentionally not run.

Publication: pending commit, branch push, annotated tag creation, and tag push.
