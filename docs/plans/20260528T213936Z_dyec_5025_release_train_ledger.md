# DYEC 5.0.25 Release Train Ledger

Created: 2026-05-28T21:39:36Z

## Objective

Commit the no-Dewey bootstrap change, carry forward the existing DYEC `5.0.24` run-mount DRA fix, update DYEC self-pins, and tag the resulting clean commit as annotated `5.0.25`.

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
| Planned tag | `5.0.25`; remote `refs/tags/5.0.25` absent at inventory. |
| Release tag policy | Use non-`v` annotated tag; do not move existing tags. |

## Tracking Rows

| ID | Area | Requirement | Status | Evidence | Terminal Note |
|---|---|---|---|---|---|
| REL-001 | No-Dewey bootstrap | Commit source, packaged, tests, runbook, and no-Dewey ledger. | SUCCESS | Commit `98955292` (`Remove Dewey bootstrap probe`) includes the source/packaged boot script change, focused test update, `docs/end_to_end_5.0.22.md`, and the no-Dewey ledger. | No-Dewey bootstrap change is committed before release integration. |
| REL-002 | Carry forward `5.0.24` | Merge or otherwise include `5.0.24^{}` so `5.0.25` does not regress the run-mount DRA fix. | SUCCESS | Merge commit includes `5.0.24^{}` (`abc88cf9`) with `daylily_ec/run_mounts.py`, `tests/test_run_mounts.py`, self-pin source/package files, and `docs/plans/20260528T205800Z_dyec_5024_run_mount_data_dra_ledger.md`. | The release line now contains the run-mount DRA fix from `5.0.24`. |
| REL-003 | Self pins | Update source and packaged DYEC self-pins to `5.0.25`. | SUCCESS | Updated `config/daylily_cli_global.yaml` and `daylily_ec/resources/payload/config/daylily_cli_global.yaml` to `git_ephemeral_cluster_repo_tag: 5.0.25` and `git_ephemeral_cluster_repo_release_tag: 5.0.25`. | Self-pins point at the planned release tag. |
| REL-004 | Validation | Run focused release validation after integration. | SUCCESS | Focused checks: `bash -n` for both boot scripts; `python -m pytest -q tests/test_headnode_init.py tests/test_packaged_defaults.py tests/test_workflow.py::TestClusterBootConfigPublish tests/test_run_mounts.py tests/test_versioning.py` -> `46 passed`; `ruff check` and `ruff format --check` passed after formatting; `git diff --check` passed; full suite `python -m pytest -q` -> `925 passed, 7 skipped`. | Release validation passed after carrying forward `5.0.24` and applying self-pin updates. |
| REL-005 | Commit and tag | Commit clean release state and create annotated tag `5.0.25` on that exact commit. | SUCCESS | Final release state is staged from this ledger state and will be committed with message `Release DYEC 5.0.25 no-Dewey bootstrap`; annotated tag command: `git tag -a 5.0.25 -m "Release 5.0.25"`. | The exact commit and tag object are reported in the final release response. |

## Terminal Report

- Terminal rows: `SUCCESS=5`.
- Target tag: `5.0.25`.
- The release line includes `5.0.24^{}` so the run-mount DRA fix is retained.
- Validation passed with focused checks and the full test suite.
