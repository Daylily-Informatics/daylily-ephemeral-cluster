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
| REL-001 | DayOA | Commit dirty DayOA changes, push `jem-dev`, create and push annotated tag `10.0.61`. | OPEN |  |  |
| REL-002 | DYEC DayOA pin | Update DayOA pins in DYEC `pyproject.toml`, `config/**`, and packaged payload config, commit, push `jem-dev`, create and push annotated tag `10.0.94`. | OPEN |  |  |
| REL-003 | DYEC self pin | Update DYEC self pin to `10.0.94`, commit, push `jem-dev`, create and push annotated tag `10.0.95`. | OPEN |  |  |
| REL-004 | Verification | Verify focused tests and annotated tag types. | OPEN |  |  |
