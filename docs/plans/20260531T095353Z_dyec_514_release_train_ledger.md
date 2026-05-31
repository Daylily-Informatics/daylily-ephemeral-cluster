# DYEC 5.1.4 Release Train Ledger

Date: 2026-05-31

## Objective

Pin DYEC to the newly released DayOA tag, package current DYEC bootstrap/catalog/runtime fixes, publish DYEC, and make a deployed DYEC version available for a new cluster validation round.

## Gate 0

| Check | Evidence | Status |
|---|---|---|
| Repo | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` on `codex/dyec-dewey-registration-refactor-20260528` | SUCCESS |
| Latest semver tag | `5.1.3`; `git cat-file -t 5.1.3` -> `tag` | SUCCESS |
| Release target | `5.1.4`, annotated non-`v` tag | OPEN |
| DayOA target pin | `2.0.26` after DayOA release completes | OPEN |
| Boot script S3 publication | Four reference targets already backed up, uploaded, and read back with SHA `4a8d190f8185eb90dfcf3747267b7a77e82a10df9d6f611701c92de57705394a`. | SUCCESS |

## Rows

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| DYEC-001 | Update DayOA catalog pins to released DayOA `2.0.26`. | OPEN |  |
| DYEC-002 | Preserve current boot-script, S3 validation, export, Dewey registration, catalog metadata, and docs changes. | OPEN |  |
| DYEC-003 | Validate focused DYEC tests and repository checks sufficient for release. | OPEN |  |
| DYEC-004 | Commit, tag `5.1.4`, push branch/tag, build, and publish. | OPEN |  |

