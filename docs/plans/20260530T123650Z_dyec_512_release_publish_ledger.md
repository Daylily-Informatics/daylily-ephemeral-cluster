# DYEC 5.1.2 Release Publish Ledger

Created: 2026-05-30T12:36:50Z

## Objective

Update DYEC self-pins to `5.1.2`, commit all current dirty/new non-ignored work, push the feature branch, create and push annotated tag `5.1.2`, rebuild the distribution from that tag, and publish with `twup` from the `TWINE` Conda environment.

## Gate 0 Inventory

| Field | Evidence |
|---|---|
| Repo | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| Branch | `codex/dyec-dewey-registration-refactor-20260528...origin/codex/dyec-dewey-registration-refactor-20260528` |
| Remote | `git@github.com:Daylily-Informatics/daylily-ephemeral-cluster.git` |
| Initial HEAD | `ce89faef5b72` (`5.1.0`) |
| Initial describe | `5.1.0-dirty` |
| Existing exact tag | `5.1.0` points at `ce89faef5b72`; `git cat-file -t 5.1.0` returned `commit`, so it is lightweight. |
| Target tag availability | Local and remote `refs/tags/5.1.2` were absent at inventory. |
| Initial modified files | `config/daylily_available_repositories.yaml`, `daylily_ec/cli.py`, `daylily_ec/repositories.py`, `daylily_ec/resources/payload/config/daylily_available_repositories.yaml`, `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`, `daylily_ec/stage_samples.py`, `tests/test_repository_catalog.py`. |
| Initial untracked work | `6146` non-ignored untracked paths: mostly `docs/plans/20260529T194248Z_dyec_test_command_catalog_validation_logs` (`6044` files) plus `docs/plans/20260526T224018Z_blahab44_inputs` and `docs/plans/20260526T223700Z_goodole3_inputs` (`170` files). |
| Ignored build artifacts | Existing `dist/`, `build/`, `*.egg-info/`, `__pycache__/`, and root `*.vcf.gz` are ignored by `.gitignore` and are not part of the commit set. |
| Release tag policy | Use non-`v` annotated tag; commit first; do not move existing pushed tags. |

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | Inventory | Record Gate 0 baseline before release edits. | SUCCESS | plan_amendment | Gate 0 | orchestrator | This ledger records repo, branch, tag availability, dirty state, and release policy. |  | Gate 0 is complete. |
| REL-002 | Self pins | Update source and packaged DYEC self-pins to `5.1.2`. | SUCCESS | feature_implementation | Gate 5 | orchestrator | `config/daylily_cli_global.yaml` and `daylily_ec/resources/payload/config/daylily_cli_global.yaml` now set `git_ephemeral_cluster_repo_tag: 5.1.2` and `git_ephemeral_cluster_repo_release_tag: 5.1.2`; `rg` found no remaining `5.0.31` in those self-pin files. |  | Self-pins point at the requested release tag. |
| REL-003 | Validation | Run focused release validation before commit/tag. | SUCCESS | contract_test | Gate 5 | orchestrator | `source ./activate && python -m pytest -q tests/test_repository_catalog.py tests/test_packaged_defaults.py tests/test_versioning.py` -> `20 passed`; `python -m ruff check` on touched Python files passed; `python -m ruff format --check` on touched Python files passed after formatting; `git diff --check` passed. |  | Focused pre-commit release validation passed. |
| REL-004 | Commit and push | Commit all current dirty/new non-ignored work and push the feature branch. | OPEN | feature_implementation | Gate 5 | orchestrator | Pending. |  |  |
| REL-005 | Tag | Create and push annotated tag `5.1.2` on the clean release commit. | OPEN | feature_implementation | Gate 5 | orchestrator | Pending. |  |  |
| REL-006 | Build and publish | Remove old `dist/*`, activate `TWINE`, run `python -m build`, then run `.zsh twup`. | OPEN | feature_implementation | Gate 5 | orchestrator | Pending. |  |  |

## Terminal Report

Pending.
