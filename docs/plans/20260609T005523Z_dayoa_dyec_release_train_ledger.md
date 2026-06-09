# DayOA/DYEC Release Train Ledger - 20260609T005523Z

Objective: publish a DayOA patch tag, update DYEC DayOA pins in `pyproject.toml` and `config/daylily_pipeline_command_catalog.yaml`, then perform the two-step DYEC release/tag flow.

## Gate 0 - Baseline

- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch: `jem-dev`
- DayOA baseline tag/commit: `10.0.0` at `4ee3be6`
- DYEC baseline latest tag: `10.0.4`
- DYEC baseline HEAD: `1f4b7533` (`Record dyec8c catalog dry-run results`)
- DYEC pre-existing unrelated dirty files: cluster template/config files plus existing docs/plans artifacts; they are intentionally out of scope.

## Ledger

| Row | Scope | Action | Status | Evidence |
| --- | --- | --- | --- | --- |
| REL-001 | DayOA | Create empty release commit and annotated `10.0.1` tag | COMPLETE | Commit `d69c5a82e017e4c40ac5ac84979930230b58fd1d`; tag type `tag` |
| REL-002 | DayOA | Push `jem-dev` and tag `10.0.1` | COMPLETE | `git push origin jem-dev`; `git push origin 10.0.1` |
| REL-003 | DYEC | Update DayOA pins to `10.0.1` in package metadata, catalog, payload catalog, and tests | COMPLETE | No remaining selected-surface `10.0.0` DayOA refs; focused validation passed |
| REL-004 | DYEC | Include FSx DRA empty-tags bugfix found during dyec8c catalog mount creation | COMPLETE | `pytest tests/test_run_mounts.py tests/test_repository_catalog.py tests/test_lsmc_bio_fork_contract.py tests/test_cli_registry_v2.py -q`: `152 passed` |
| REL-005 | DYEC | Commit/push/tag first DYEC release | PENDING | Target version: `10.0.5` |
| REL-006 | DYEC | Update DYEC self-pins and commit/push/tag second DYEC release | PENDING | Target version: `10.0.6` |
