# DYEC 17.0.18 merged ONT RunQC release ledger

Created: 2026-08-14T10:15:00Z

## Objective

Merge the annotated DYEC `17.0.16` ONT RunQC repair release into annotated
DYEC `17.0.17`, preserve both release histories, pin the merged active catalog
to merged DayOA release `14.0.16`, and publish the result as annotated DYEC
release `17.0.18`.

## Gate 0

- First parent: DYEC `17.0.17`, commit
  `5d7542579e8321d69604735a60aed647da92e7af`.
- Merged parent: DYEC `17.0.16`, commit
  `1d86200b68d2c2b8a26a2720382a2160c7dcfaea`.
- DayOA `14.0.16` is the merged DayOA line containing the `14.0.15` BJuice
  work and the immutable ONT RunQC environment v0.5 repair.
- Catalog snapshots `17.0.16` and `17.0.17` are retained exactly from their
  owning release tags. Active repository rows and `current` are repinned to
  DayOA `14.0.16`; `17.0.18` is appended as the new immutable snapshot.
- Tests remain source/unit contract tests and do not build a workflow Conda
  environment. Runtime acceptance belongs to the catalog execution.

## Control ledger

| ID | Requirement | Status | Evidence | Terminal note |
|---|---|---|---|---|
| MERGE-001 | Merge DYEC `17.0.16` into `17.0.17` with both commits as parents | SUCCESS | Release merge commit has first parent `17.0.17` and second parent `17.0.16` | No tag is moved. |
| DAYOA-001 | Pin merged active catalog to DayOA `14.0.16` | SUCCESS | Annotated DayOA tag resolves to `ab8a66afa65a62b4d447ce583c9e44855b6be6dc`; `14.0.15` is its ancestor; all active pins are `14.0.16` | Historical pins remain release-owned. |
| CAT-001 | Preserve `17.0.16` and `17.0.17` snapshots and append `17.0.18` | SUCCESS | Source/payload byte mirror passed; both parent snapshot blocks match their owning tags exactly; `current == 17.0.18` | Parent snapshots are immutable. |
| TEST-001 | Run focused merged release suite without Conda environment builds | SUCCESS | `376 passed in 142.40s`; `git diff --check` passed | Runtime acceptance is not simulated in tests. |
| REL-001 | Commit, push branch, and publish annotated tag `17.0.18` | SUCCESS | Annotated release tag and branch are published by this release transaction | Existing tags remain immutable. |

## Final report

All rows terminal: yes

Objective complete: yes
