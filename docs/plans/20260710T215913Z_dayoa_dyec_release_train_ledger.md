# DayOA and DYEC Release Train Ledger

Created: 2026-07-10T21:59:13Z

## Objective

Release all authorized dirty DayOA work to `jem-dev`, pin that DayOA release
through DYEC's source and packaged configuration, release the current DYEC
changes, then update DYEC's self-pin and cut a final DYEC release.

## Gate 0 Baseline

- DayOA repository: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`.
- DayOA baseline: `jem-dev` and `origin/jem-dev` at `90adbd5`, annotated tag
  `10.0.84`; next unallocated tag `10.0.85`.
- DYEC release worktree:
  `/Users/jmajor/projects/lsmc/.worktrees/dyec-default-slurm-accounting`.
- DYEC remote baseline: `origin/jem-dev` at `eedd4d8b`; local commit
  `d8dccc89` enables Slurm accounting by default and is one commit ahead.
- Latest pre-existing DYEC tag: `10.0.149`; selected release tags are
  `10.0.150` for the DayOA-pin/accounting release and `10.0.151` for the
  subsequent self-pin release.
- Existing dirty state in the original shared DYEC checkout is unrelated and
  remains outside this release worktree.
- Release tags must be annotated, must follow their clean commits, and must
  never move or overwrite an existing remote tag.

## Control Ledger

| ID | Requirement | Status | Evidence | Terminal note |
|---|---|---|---|---|
| DAYOA-001 | Validate and commit all authorized dirty DayOA work | SUCCESS | Full suite: `553 passed`; Ruff, `bash -n`, and `git diff --check` pass; commit `e108d32` | All 26 dirty paths were included |
| DAYOA-002 | Push DayOA `jem-dev` and annotated `10.0.85` | SUCCESS | Remote branch and peeled tag both resolve to `e108d32fb4c1dbfc250c563aaedd26ef04f4fc78`; local tag object type is `tag` | No force push or tag movement |
| DYEC-001 | Make Slurm accounting default-on with an explicit disable option | SUCCESS | Commit `d8dccc89`; full pre-pin suite `1355 passed, 11 skipped` | Canonical source and packaged defaults agree |
| DYEC-002 | Pin DayOA `10.0.85` in dependency and active source/payload config | SUCCESS | `pyproject.toml`, repository override, both command catalogs, and four blessed-tag test contracts updated; full suite `1355 passed, 11 skipped` | Source and packaged catalogs are byte-identical |
| DYEC-003 | Commit, push, and annotate the first DYEC release as `10.0.150` | SUCCESS | Remote branch and peeled annotated tag both resolve to `bb1a54b82b96ec657aa1cc640740da9321eb262c`; local object type is `tag` | No force push or tag movement |
| DYEC-004 | Update source and packaged DYEC self-pin to `10.0.150` | SUCCESS | Both `daylily_cli_global.yaml` copies and blessed-tag contract updated; full suite `1355 passed, 11 skipped` | Source and packaged self-pins agree |
| DYEC-005 | Prepare the final DYEC self-pin release as `10.0.151` | SUCCESS | Final release tree passes the complete suite and targets the unallocated annotated tag `10.0.151` | Push and peeled-tag receipts necessarily follow the immutable commit and are reported in the final handoff |

## Scope Boundaries

This release train changes Git repositories and tags only. It does not launch,
reconfigure, or mutate a cluster, workflow, Slurm controller, AWS resource, or
budget.

## Final State

All source, pin, validation, and release-preparation rows are terminal and
successful. The final handoff must report the DayOA tag, intermediate DYEC
tag, final DYEC tag, exact remote commit receipts, and test results after the
final immutable commit and tag have been pushed.
