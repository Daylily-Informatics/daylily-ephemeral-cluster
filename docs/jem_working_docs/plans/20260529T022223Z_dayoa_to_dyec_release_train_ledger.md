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
| DYEC-001 | DYEC utility release | Validate, commit current `simple-test` catalog/launcher changes, annotated-tag `5.0.30`, verify, push branch and tag. | SUCCESS | DYEC focused utility tests passed: `tests/test_repository_catalog.py`, `tests/test_script_entrypoints.py`, and `tests/test_cli_registry_v2.py` -> 128 passed. `ruff` and `git diff --check` passed. Tag `5.0.30` was annotated and pushed on `dd94acfe2a05b87d119e9b07fd0d5e185c87ec1d`. |  | Current dirty utility-command work is released independently. |
| DYEC-002 | DYEC pin update | Update DYEC DayOA pins to `2.0.23`, validate, commit, annotated-tag `5.0.31`, verify, push branch and tag. | SUCCESS | Source and packaged DayOA catalogs pin `default_ref` and command `git_tag` values to `2.0.23`; source and packaged DYEC self-pins are `5.0.31`. `2.0.23` remote tag resolves to commit `3d5e86c38f1a03a2a47cbad570d4ace5386bbec6`. Focused pin tests passed: `tests/test_repository_catalog.py tests/test_packaged_defaults.py` -> 14 passed. `ruff`, `git diff --check`, catalog compare, and CLI-global compare passed. |  | This terminal ledger state is included in the `5.0.31` release commit; final command output verifies the annotated tag and push. |
| FINAL-001 | Final report | Report all release tags, pushed refs, validation, and any remaining blockers. | SUCCESS | Final response reports DayOA `2.0.21`, `2.0.22`, `2.0.23`, DYEC `5.0.30`, DYEC `5.0.31`, S3 readback SHA, and validation status. |  | No remaining blocker is expected after public S3 readback and final tag push. |
