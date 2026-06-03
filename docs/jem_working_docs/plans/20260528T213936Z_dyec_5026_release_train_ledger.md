# DYEC 5.0.26 Release Train Ledger

Created: 2026-05-28T21:39:36Z

## Objective

Commit the no-Dewey bootstrap change, carry forward the existing DYEC `5.0.24` run-mount DRA fix and `5.0.25` retry replacement fix, update DYEC self-pins, and tag the resulting clean commit as annotated `5.0.26`.

## Gate 0 Inventory

| Field | Evidence |
|---|---|
| Repo | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| Branch | `codex/dyec-dewey-registration-refactor-20260528...origin/codex/dyec-dewey-registration-refactor-20260528` |
| Remote | `git@github.com:Daylily-Informatics/daylily-ephemeral-cluster.git` |
| Initial HEAD | `2517224b` (`Record DYEC 5.0.23 publish evidence`) |
| Initial dirty state | Modified `config/day_cluster/post_install_ubuntu_combined.sh`, packaged boot script, and `tests/test_headnode_init.py`; untracked `docs/end_to_end_5.0.22.md` and `docs/plans/20260528T205245Z_remove_boot_dewey_probe_ledger.md`. |
| Current reachable release | `5.0.23` is reachable from this branch head. |
| Newer remote release to carry forward | Annotated tag `5.0.24` points to `abc88cf9` on `codex/dyec-run-mount-data-dra-fix-20260528`; `git rev-list --left-right --count HEAD...5.0.24^{}` -> `0 1`, so current branch lacked that fix before this release train. |
| Initial planned tag | `5.0.25`; remote `refs/tags/5.0.25` absent at inventory. |
| Release amendment | `5.0.25` existed by tag-creation time and points to `b108404f` (`Allow explicit retry analysis directory replacement`), so this release train advanced to `5.0.26` without moving the published tag. |
| Final planned tag | `5.0.26`; remote `refs/tags/5.0.26` and local tag `5.0.26` absent before final release commit. |
| Release tag policy | Use non-`v` annotated tag; do not move existing tags. |

## Tracking Rows

| ID | Area | Requirement | Status | Evidence | Terminal Note |
|---|---|---|---|---|---|
| REL-001 | No-Dewey bootstrap | Commit source, packaged, tests, runbook, and no-Dewey ledger. | SUCCESS | Commit `98955292` (`Remove Dewey bootstrap probe`) includes the source/packaged boot script change, focused test update, `docs/end_to_end_5.0.22.md`, and the no-Dewey ledger. | No-Dewey bootstrap change is committed before release integration. |
| REL-002 | Carry forward `5.0.24` | Merge or otherwise include `5.0.24^{}` so `5.0.26` does not regress the run-mount DRA fix. | SUCCESS | Merge commit includes `5.0.24^{}` (`abc88cf9`) with `daylily_ec/run_mounts.py`, `tests/test_run_mounts.py`, self-pin source/package files, and `docs/plans/20260528T205800Z_dyec_5024_run_mount_data_dra_ledger.md`. | The release line now contains the run-mount DRA fix from `5.0.24`. |
| REL-003 | Carry forward `5.0.25` | Merge or otherwise include `5.0.25^{}` so `5.0.26` does not regress the retry replacement fix. | SUCCESS | Merge commit includes `5.0.25^{}` (`b108404f`) with `daylily_ec/cli.py`, `daylily_ec/repositories.py`, headnode script entrypoint updates, and related tests. | The release line now contains the retry replacement fix from the already-published `5.0.25`. |
| REL-004 | Self pins | Update source and packaged DYEC self-pins to `5.0.26`. | SUCCESS | Updated `config/daylily_cli_global.yaml` and `daylily_ec/resources/payload/config/daylily_cli_global.yaml` to `git_ephemeral_cluster_repo_tag: 5.0.26` and `git_ephemeral_cluster_repo_release_tag: 5.0.26`. | Self-pins point at the final planned release tag. |
| REL-005 | Validation | Run focused release validation after final integration. | SUCCESS | Final checks: `bash -n` for both boot scripts; `python -m pytest -q tests/test_headnode_init.py tests/test_packaged_defaults.py tests/test_workflow.py::TestClusterBootConfigPublish tests/test_run_mounts.py tests/test_versioning.py tests/test_cli_registry_v2.py tests/test_repository_catalog.py tests/test_script_entrypoints.py` -> `172 passed`; `python -m pytest -q` -> `925 passed, 7 skipped`; `python -m ruff check .` passed; `python -m ruff format --check` on the touched release Python files passed; `git diff --check` passed. | Release validation passed after integrating `5.0.24`, `5.0.25`, and applying `5.0.26` self-pin updates. |
| REL-006 | Commit and tag | Commit clean release state and create annotated tag `5.0.26` on that exact commit. | SUCCESS | Final release state is committed with message `Release DYEC 5.0.26 no-Dewey bootstrap`; annotated tag command: `git tag -a 5.0.26 -m "Release 5.0.26"`. | The exact commit and tag object are verified after tag creation and reported in the final release response. |

## Terminal Report

- Terminal rows: `SUCCESS=6`.
- Target tag: `5.0.26`.
- The release line includes `5.0.24^{}` and `5.0.25^{}` so both the run-mount DRA fix and retry replacement fix are retained.
- Full-repo `ruff format --check .` reports broad pre-existing formatting drift outside this release slice, so final formatter validation was scoped to release-touched Python files after formatting that set.
