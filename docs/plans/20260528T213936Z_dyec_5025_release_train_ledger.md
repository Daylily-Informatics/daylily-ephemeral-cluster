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
| REL-001 | No-Dewey bootstrap | Commit source, packaged, tests, runbook, and no-Dewey ledger. | OPEN |  |  |
| REL-002 | Carry forward `5.0.24` | Merge or otherwise include `5.0.24^{}` so `5.0.25` does not regress the run-mount DRA fix. | OPEN |  |  |
| REL-003 | Self pins | Update source and packaged DYEC self-pins to `5.0.25`. | OPEN |  |  |
| REL-004 | Validation | Run focused release validation after integration. | OPEN |  |  |
| REL-005 | Commit and tag | Commit clean release state and create annotated tag `5.0.25` on that exact commit. | OPEN |  |  |

