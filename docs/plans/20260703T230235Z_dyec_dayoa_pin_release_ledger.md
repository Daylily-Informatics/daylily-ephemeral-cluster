# DYEC DayOA Pin and Self-Pin Release Ledger

Stamp: `20260703T230235Z`

Controlling request: commit/push current DayOA work, tag/push a DayOA version, update DYEC DayOA pins, commit/push/tag DYEC, update DYEC self-pins to that tag, commit/push/tag DYEC again, and report final versions.

## Gate 0 Baseline

- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DayOA branch: `jem-dev...origin/jem-dev`
- DayOA state after fetch: clean; HEAD `d79beae` already tagged `10.0.60` and pushed to `origin/jem-dev`.
- DayOA release decision: no empty/no-op DayOA commit or tag will be manufactured; DYEC will pin the existing contentful DayOA tag `10.0.60`.
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DYEC branch: `jem-dev...origin/jem-dev`
- DYEC starting released HEAD: `602e4486`, tag `10.0.91`.
- Planned DYEC DayOA-pin release tag: `10.0.92`.
- Planned DYEC self-pin release tag: `10.0.93`.
- Pre-existing DYEC dirty files before this release-train turn included the spot lifecycle logging implementation and earlier unrelated DRAGEN headnode configure edits already present in the worktree.
- Release tag format: non-`v` annotated semver tags.

## Row Status

| ID | Area | Requirement | Status | Evidence | Terminal Note |
|---|---|---|---|---|---|
| REL-001 | DayOA | Inspect, commit, push, and tag dirty DayOA work if present. | CLOSED | `git status --short --branch`; `git tag --points-at HEAD`; `git log -1 --oneline --decorate` | DayOA was clean on `jem-dev`; HEAD was already tagged `10.0.60`, so no no-op commit/tag was created. |
| REL-002 | DYEC pins | Update DYEC DayOA pins to `10.0.60` in `pyproject.toml`, active config, packaged config, and tests. | CLOSED | `pyproject.toml`; `config/daylily_pipeline_command_catalog.yaml`; packaged command catalog; fork/catalog tests | DayOA pins now reference existing released DayOA tag `10.0.60`. |
| REL-003 | DYEC release 1 | Commit changed DYEC work, push `jem-dev`, create/push annotated tag `10.0.92`. | CLOSED | Commit `dc11b6fd`; annotated tag `10.0.92`; `git push origin jem-dev`; `git push origin 10.0.92`; `git cat-file -t 10.0.92 -> tag` | DYEC DayOA-pin release is pushed. |
| REL-004 | DYEC self-pin | Update DYEC self-pins to `10.0.92` in active and packaged global config/tests. | CLOSED | `config/daylily_cli_global.yaml`; packaged global config; `tests/test_lsmc_bio_fork_contract.py` | DYEC self-pins now point to release tag `10.0.92`. |
| REL-005 | DYEC release 2 | Commit self-pin update, push `jem-dev`, create/push annotated tag `10.0.93`. | CLOSED | Final self-pin release commit; annotated tag `10.0.93`; `git push origin jem-dev`; `git push origin 10.0.93` | DYEC self-pin release is pushed. |
| REL-006 | Verification | Verify tests and final pushed tags. | CLOSED | `source ./activate && pytest -q && bash -n config/day_cluster/post_install_ubuntu_combined.sh && bash -n config/day_cluster/post_install_rhel8_dragen.sh`; final `git ls-remote` tag verification | Pre-`10.0.92` and pre-`10.0.93` DYEC verification both passed: 1162 passed, 8 skipped; boot scripts passed `bash -n`; final tag verification completed after push. |
