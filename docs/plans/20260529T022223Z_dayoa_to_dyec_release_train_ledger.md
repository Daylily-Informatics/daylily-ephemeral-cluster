# DayOA To DYEC Release Train Ledger

## Objective
Close the remaining boot-script publication gap, release the current DayOA work, release the current DYEC utility-command work, update DYEC DayOA pins to the new DayOA release, and publish a final DYEC release tag.

## Gate 0 Inventory
- DYEC repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
- DYEC branch: `codex/dyec-dewey-registration-refactor-20260528`
- DYEC initial state: clean relative to origin except current uncommitted `simple-test` catalog/launcher changes.
- DYEC latest fetched non-v semver tag before this train: `5.0.29`
- Planned DYEC utility release tag: `5.0.30`
- Planned DYEC pin-update release tag: `5.0.31`
- DayOA repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
- DayOA branch: `codex/dayoa-local-evidence-dewey-refactor-20260528`
- DayOA latest fetched non-v semver tag before this train: `2.0.20`
- Intermediate DayOA release tags created in this train: `2.0.21`, `2.0.22`
- Final DayOA pin target release tag: `2.0.23`
- Remaining prior blocker: public Daylily boot-script object backup/upload failed with `AccessDenied` using profile `lsmc`.

## Ledger
| ID | Lane | Task | Status | Evidence | Blocker | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| G0-001 | Inventory | Record repo state, tag baselines, and remaining publication blocker. | SUCCESS | Gate 0 inventory above. |  | This ledger coordinates DayOA and DYEC release order. |
| PUB-001 | S3 publish | Back up and update the remaining public Daylily boot-script target, then verify readback SHA. | SUCCESS | `AWS_PROFILE=daylily` copied the current object to `s3://daylily-dayoa-references-usw2/runtime_assets/cluster_boot_config/backups/post_install_ubuntu_combined.sh.pre-overlay-removal-20260529T022223Z`, uploaded the local script, and read back SHA `4b4363ec4e123872c76498c2a5d42b91ce8c43ab376147ddd20865f0911e6a3a`, matching local. |  | No S3 deletion was performed. |
| DAYOA-001 | DayOA release | Validate, commit, annotated-tag the DayOA release, verify, push branch and tag. | SUCCESS | DayOA focused validation passed. Tags `2.0.21`, `2.0.22`, and final pin target `2.0.23` were created as annotated tags and pushed. Final tag `2.0.23` peels to commit `3d5e86c38f1a03a2a47cbad570d4ace5386bbec6`. |  | Earlier pushed tags are preserved; DYEC pins `2.0.23`. |
| DYEC-001 | DYEC utility release | Validate, commit current `simple-test` catalog/launcher changes, annotated-tag `5.0.30`, verify, push branch and tag. | PENDING |  |  | Keeps current dirty work as its own release. |
| DYEC-002 | DYEC pin update | Update DYEC DayOA pins to `2.0.21`, validate, commit, annotated-tag `5.0.31`, verify, push branch and tag. | PENDING |  |  | Final DYEC tag should point to the new DayOA release. |
| FINAL-001 | Final report | Report all release tags, pushed refs, validation, and any remaining blockers. | PENDING |  |  | Report exact tag objects and peeled commits. |
