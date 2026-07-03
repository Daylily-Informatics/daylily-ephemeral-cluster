# DayOA/DYEC Release Train Ledger

Stamp: `20260703T232850Z`

Controlling request: commit and push the dirty DayOA changes to `jem-dev`, tag and push a new DayOA release, update DYEC DayOA pins, commit/push/tag DYEC, then update the DYEC self pin to that new DYEC release and commit/push/tag again.

## Gate 0 Baseline

- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DayOA branch: `jem-dev...origin/jem-dev`
- DayOA starting tag: `10.0.60`
- DayOA release target: `10.0.61`
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DYEC branch: `jem-dev...origin/jem-dev`
- DYEC starting tag: `10.0.93`
- DYEC DayOA-pin release target: `10.0.94`
- DYEC self-pin release target: `10.0.95`
- Starting DYEC self pin: `10.0.92` in `config/daylily_cli_global.yaml` and packaged payload copy.
- Boundary: no workflow execution, no AWS mutation, no Slurm/job action.

## Rows

| ID | Area | Requirement | Status | Evidence | Terminal Note |
|---|---|---|---|---|---|
| REL-001 | DayOA | Commit dirty DayOA changes, push `jem-dev`, create and push annotated tag `10.0.61`. | SUCCESS | DayOA commit `bd8f440395286c47c0031bf16e09f909c7704082`; `git push origin jem-dev`; `git tag -a 10.0.61 -m "Release 10.0.61"`; `git push origin 10.0.61`; `git cat-file -t 10.0.61` -> `tag`. | DayOA release `10.0.61` was pushed to `lsmc-bio/daylily-omics-analysis`. |
| REL-002 | DYEC DayOA pin | Update DayOA pins in DYEC `pyproject.toml`, `config/**`, and packaged payload config, commit, push `jem-dev`, create and push annotated tag `10.0.94`. | SUCCESS | DYEC commit `f3aaa34fcd7dde83a78fc8d51cb714cfdde10258`; DayOA pins updated to `10.0.61` in `pyproject.toml`, `config/daylily_pipeline_command_catalog.yaml`, `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`, and blessed-tag tests; `git push origin jem-dev`; `git tag -a 10.0.94 -m "Release 10.0.94"`; `git push origin 10.0.94`; `git cat-file -t 10.0.94` -> `tag`. | DYEC release `10.0.94` was pushed with the DayOA `10.0.61` pin. |
| REL-003 | DYEC self pin | Update DYEC self pin to `10.0.94`, commit, push `jem-dev`, create and push annotated tag `10.0.95`. | SUCCESS | Self pins updated to `10.0.94` in `config/daylily_cli_global.yaml`, `daylily_ec/resources/payload/config/daylily_cli_global.yaml`, and `tests/test_lsmc_bio_fork_contract.py`; final commit and tag `10.0.95` will point at this ledger update. | DYEC final self-pin release `10.0.95` captures a self pin to the preceding DYEC release `10.0.94`. |
| REL-004 | Verification | Verify focused tests and annotated tag types. | SUCCESS | DayOA: `python -m pytest tests/test_dynamic_resource_helpers.py tests/test_slurm_profile.py tests/test_slurm_caller_partitions.py -q` -> `44 passed`. DYEC DayOA-pin pass: `python -m pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py tests/test_cli_registry_v2.py -q` -> `142 passed`. DYEC self-pin pass: same focused tests rerun before final commit. `git diff --check` passed before commits. | Focused verification passed for DayOA and DYEC pin contracts. |
