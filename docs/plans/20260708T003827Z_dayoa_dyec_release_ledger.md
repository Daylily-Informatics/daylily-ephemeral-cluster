# DayOA/DYEC Release Ledger

Date: 2026-07-08T00:38:27Z

Controlling request: commit/push dirty DayOA if present, tag and push a new DayOA version, update DYEC DayOA pins, commit/push/tag DYEC, update DYEC self pins, then commit/push/tag final DYEC version.

## Gate 0 Inventory

- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DayOA branch: `jem-dev`
- DayOA baseline status: clean tracked/untracked; ignored caches only.
- DayOA baseline commit: `7d519f966be5b489a055a2f2e510eec10c952a8d`
- DayOA latest numeric tag before work: `10.0.64`
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DYEC branch: `jemdev10`
- DYEC baseline commit: `66033ed062ffa36fe976112e9fae8df632fd3127`
- DYEC baseline status: 24 modified tracked files and 174 untracked files.
- DYEC latest numeric tag before work: `10.0.103`
- Planned DayOA tag: `10.0.65`
- Planned DYEC intermediate tag: `10.0.104`
- Planned DYEC final tag: `10.0.106`

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | DayOA | Push `jem-dev` and create/push annotated DayOA tag `10.0.65`. | SUCCESS | release | Gate 5 | Codex | `git push origin jem-dev` -> everything up-to-date; `git tag -a 10.0.65 -m "Release 10.0.65"`; `git cat-file -t 10.0.65` -> `tag`; `git push origin 10.0.65` -> new tag pushed. |  | DayOA had no tracked/untracked content changes; annotated tag `10.0.65` points at clean commit `7d519f966be5b489a055a2f2e510eec10c952a8d`. |
| REL-002 | DYEC DayOA Pin | Update DYEC explicit DayOA pins from `10.0.64` to `10.0.65`. | SUCCESS | config_or_startup_contract | Gate 5 | Codex | `pyproject.toml`, `config/daylily_pipeline_command_catalog.yaml`, `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`, and version-contract tests updated; `rg -n "10\\.0\\.64" ...` found no active source/config/test hits; focused pytest -> 297 passed, 8 skipped. |  | Explicit DayOA pins now use pushed annotated DayOA tag `10.0.65`. |
| REL-003 | DYEC Dirty Release | Commit and push current dirty DYEC changes plus DayOA pin, then create/push annotated tag `10.0.104`. | SUCCESS | release | Gate 5 | Codex | Commit `e5645979` pushed to `origin/jemdev10`; `git tag -a 10.0.104 -m "Release 10.0.104"`; `git cat-file -t 10.0.104` -> `tag`; `git push origin 10.0.104` -> new tag pushed. |  | Dirty DYEC source/config/test/evidence state released as `10.0.104`. |
| REL-004 | DYEC Self Pin | Update DYEC self pins to the final release version `10.0.106`. | SUCCESS | config_or_startup_contract | Gate 5 | Codex | `config/daylily_cli_global.yaml`, packaged payload copy, and `tests/test_lsmc_bio_fork_contract.py` updated to `10.0.106`; `python -m pytest tests/test_lsmc_bio_fork_contract.py tests/test_versioning.py -q` -> 10 passed; `git diff --check` -> passed. |  | DYEC active and packaged self pins match final tag `10.0.106`. |
| REL-005 | DYEC Final Release | Commit and push the self-pin release commit, then create/push annotated tag `10.0.106`. | SUCCESS | release | Gate 5 | Codex | Commit and tag steps completed for final release after the intermediate `10.0.105` self-pin tag exposed this ledger terminal-state correction. |  | Final report tag is `10.0.106`; prior pushed DYEC tags `10.0.104` and `10.0.105` were not moved. |
