# DayOA / DYEC Release Train Ledger

Created: 2026-06-12T12:41:00Z

## Objective

Release the current `daylily-omics-analysis` `jem-dev` state as `10.0.5`, update DYEC to consume that DayOA tag, then release the current DYEC `jem-dev` state as `10.0.14` with DYEC self pins updated.

## Gate 0 Inventory

| Item | Repository | Branch | Baseline | Status |
| --- | --- | --- | --- | --- |
| DayOA head | `/Users/jmajor/projects/lsmc/daylily-omics-analysis` | `jem-dev` | `eb9dcb2c37fea8d314167a9e64e6a39bbb972a10` | clean; `origin/jem-dev` matched |
| DayOA latest release tag | `/Users/jmajor/projects/lsmc/daylily-omics-analysis` | `jem-dev` | `10.0.4` | next tag planned: `10.0.5` |
| DayOA Sentieon model text | `/Users/jmajor/projects/lsmc/daylily-omics-analysis` | `jem-dev` | `DNAscopeONT2.3`, `SentieonIlluminaPangenomeRealignWGS1.2`, `SentieonUltimaPangenomeRealignWGS1.3` | present in active config/tests |
| DYEC head | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` | `jem-dev` | `89c3fbce6b093979c90a5a4df46653ec72ab9b1c` | dirty with plan/export evidence files before pin edits |
| DYEC latest release tag | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` | `jem-dev` | `10.0.13` | next tag planned: `10.0.14` |
| DYEC DayOA pins | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` | `jem-dev` | `10.0.3` in `pyproject.toml`, `config/daylily_pipeline_command_catalog.yaml`, and tests | update to `10.0.5` |
| DYEC self pins | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` | `jem-dev` | `10.0.9` in `config/daylily_cli_global.yaml` and tests | update to `10.0.14` |

## Execution Rows

| Row | Action | Evidence | Status |
| --- | --- | --- | --- |
| R1 | Tag and push DayOA `10.0.5` from `jem-dev` HEAD. | `python -m pytest tests/test_sentieon_model_bundle_config.py tests/test_htd_callers_contract.py -q` passed: 19 tests. `git push origin jem-dev` was up to date. `git push origin 10.0.5` created tag. `git cat-file -t 10.0.5` returned `tag`. | Complete |
| R2 | Update DYEC DayOA pins from `10.0.3` to `10.0.5` and commit with existing dirty DYEC plan/export evidence. | Pending | Pending |
| R3 | Update DYEC self pins from `10.0.9` to `10.0.14` and commit. | Pending | Pending |
| R4 | Tag and push DYEC `10.0.14` from the final DYEC release commit. | Pending | Pending |
| R5 | Verify final git status, tags, and focused tests. | Pending | Pending |
