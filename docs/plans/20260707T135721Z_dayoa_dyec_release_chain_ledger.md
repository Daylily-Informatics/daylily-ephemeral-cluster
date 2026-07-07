# DayOA And DYEC Release Chain Ledger

Created: 2026-07-07T13:57:21Z
Control repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`

## Objective

Release the current DayOA state to a new version tag, update DYEC DayOA pins, release DYEC, then update DYEC self-pins to that new DYEC tag and release DYEC again.

## Gate 0 Baseline

| Item | Evidence |
|---|---|
| DayOA branch | `jem-dev`; `origin/jem-dev...HEAD` -> `0 0`; working tree clean. |
| DayOA current HEAD | `9c8c014 Fix SMN12 caller prep and scratch staging`; tags on HEAD include `10.0.62` and `10.0.63`. |
| DayOA next tag | `10.0.64`; no DayOA commit expected because the tree is clean. |
| DYEC branch | `jemdev10`; `origin/jem-dev...HEAD` -> `0 0`. |
| DYEC current HEAD | `7e612191 Pin DYEC self release 10.0.100`; tag on HEAD `10.0.101`. |
| DYEC dirty state | Untracked `docs/plans/20260707T115024Z_illumina94_export_delete_ledger.md`; this ledger was created after Gate 0 and is in scope for the DYEC dirty commit. |
| DYEC next tags | First release `10.0.102`; final self-pin release `10.0.103`. |
| Release rules | Use non-`v` semver annotated tags; commit first when there are changes; do not move existing tags. |

## Tracking Rows

| ID | Area | Requirement | Status | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|
| GATE0 | Baseline | Record repo state, dirty files, and planned tags. | SUCCESS | Orchestrator | Gate 0 table above. |  | Ready to release. |
| DAYOA-RELEASE | DayOA | Commit dirty DayOA changes if present, push `jem-dev`, create and push new DayOA tag. | SUCCESS | Agent 1 | DayOA was clean, so no commit was created. `git push origin jem-dev` -> up to date; `git tag -a 10.0.64 -m 'Release 10.0.64'`; `git push origin 10.0.64`; `git cat-file -t 10.0.64` -> `tag`; tag resolves to `9c8c014`. |  | DayOA release tag `10.0.64` is pushed. |
| DYEC-DAYOA-PIN | DYEC | Update DYEC DayOA pins in `pyproject.toml` and `config/**` to new DayOA tag. | SUCCESS | Agent 2 | Updated DayOA pins from `10.0.63` to `10.0.64` in `pyproject.toml`, `config/daylily_pipeline_command_catalog.yaml`, `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`, and blessed-tag tests. Full DYEC `pytest -q` -> `1211 passed, 8 skipped`. |  | DYEC now pins DayOA `10.0.64`. |
| DYEC-RELEASE-1 | DYEC | Commit/push dirty DYEC state and DayOA pin update, then create/push first DYEC tag. | SUCCESS | Agent 2 | Commit `62fe32d7 Release DYEC 10.0.102 with DayOA 10.0.64`; included DayOA pin updates plus dirty ledger files; `git push origin HEAD:jem-dev`; `git tag -a 10.0.102 -m 'Release 10.0.102'`; `git push origin 10.0.102`; `git cat-file -t 10.0.102` -> `tag`. |  | DYEC first release tag `10.0.102` is pushed. |
| DYEC-SELF-PIN | DYEC | Update DYEC self-pinned version to the first new DYEC tag. | SUCCESS | Agent 3 | Updated `config/daylily_cli_global.yaml`, `daylily_ec/resources/payload/config/daylily_cli_global.yaml`, and `tests/test_lsmc_bio_fork_contract.py` from `10.0.100` to `10.0.102`. Full DYEC `pytest -q` -> `1211 passed, 8 skipped`. |  | DYEC self-pins now target `10.0.102`. |
| DYEC-RELEASE-2 | DYEC | Commit/push self-pin update, then create/push final DYEC tag. | SUCCESS | Agent 3 | Commit `bf659392 Pin DYEC self release 10.0.102`; `git push origin HEAD:jem-dev`; `git tag -a 10.0.103 -m 'Release 10.0.103'`; `git push origin 10.0.103`; `git cat-file -t 10.0.103` -> `tag`. |  | DYEC final release tag `10.0.103` is pushed. |
| FINAL | Closeout | Report pushed tags, commits, tests, and final versions. | SUCCESS | Orchestrator | DayOA tag `10.0.64` pushed; DYEC tag `10.0.102` pushed for DayOA pin update; DYEC tag `10.0.103` pushed for self-pin update. DYEC full test suite passed twice: `1211 passed, 8 skipped`. |  | Release chain complete. |

## Progress Log

- 2026-07-07T13:57Z: Ledger created. DayOA is clean; DYEC has one pre-existing untracked ledger file plus this new release-chain ledger.
- 2026-07-07T14:00Z: DayOA tag `10.0.64` created and pushed on clean `jem-dev` commit `9c8c014`.
- 2026-07-07T14:03Z: DYEC DayOA pins updated to `10.0.64`; full DYEC tests passed: `1211 passed, 8 skipped`.
- 2026-07-07T14:04Z: DYEC commit `62fe32d7` pushed to `origin/jem-dev`; annotated tag `10.0.102` pushed.
- 2026-07-07T14:06Z: DYEC self-pins updated to `10.0.102`; full DYEC tests passed again: `1211 passed, 8 skipped`.
- 2026-07-07T14:07Z: DYEC commit `bf659392` pushed to `origin/jem-dev`; annotated tag `10.0.103` pushed.

## Final Status Counts

| Status | Count | Rows |
|---|---:|---|
| SUCCESS | 7 | `GATE0`, `DAYOA-RELEASE`, `DYEC-DAYOA-PIN`, `DYEC-RELEASE-1`, `DYEC-SELF-PIN`, `DYEC-RELEASE-2`, `FINAL` |
| BLOCKED | 0 |  |
