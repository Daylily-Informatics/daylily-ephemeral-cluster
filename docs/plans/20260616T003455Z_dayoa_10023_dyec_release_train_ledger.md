# DayOA 10.0.23 DYEC Release Train Ledger

## Gate 0 Baseline

- Created UTC: `2026-06-16T00:34:55Z`
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DYEC baseline branch/status before edits: `jem-dev...origin/jem-dev`, clean except untracked dyecX4 manifest artifacts created during this task.
- DayOA baseline branch/status before this DYEC train: `jem-dev...origin/jem-dev`, clean after commit `28ecd7da17f7ed6bee64f4d5b56a0088320d048d` and annotated tag `10.0.23`.
- Existing DYEC release head before edits: `10.0.36` at `679f4a86`.
- No export or delete operation was run; dyecX4 inventory is read-only pre-teardown evidence.

## Control Ledger

| ID | Area | Requirement | Status | Category | Gate | Evidence | Terminal Note |
|---|---|---|---|---|---|---|---|
| REL-001 | DayOA | Confirm DayOA closeout is committed, pushed, and tagged before updating DYEC pins | SUCCESS | release_train | Gate 0 | DayOA commit `28ecd7da17f7ed6bee64f4d5b56a0088320d048d`; tag `10.0.23`; branch `jem-dev` pushed | DayOA release baseline complete. |
| REL-002 | DYEC DayOA pin | Update active DYEC DayOA pins from `10.0.22` to `10.0.23` in `pyproject.toml`, `config/**`, packaged config, and contract tests | SUCCESS | release_train | Gate 1 | `pyproject.toml`; `config/daylily_pipeline_command_catalog.yaml`; `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`; `tests/test_repository_catalog.py`; `tests/test_lsmc_bio_fork_contract.py`; `pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py -q` -> 15 passed | DayOA pins updated and tested. |
| REL-003 | dyecX4 manifest | Produce a pre-teardown manifest of `/fsx/analysis_results` directories that are not exported to S3 | SUCCESS | pre_teardown_inventory | Gate 1 | `docs/plans/20260616T001451Z_dyecx4_unexported_export_manifest.{json,tsv,md}`; cluster `dyecX4`; headnode `i-05815cdeec4a6dad8`; 106 dirs inspected; 82 need export review; active workflow process lines `0` | Manifest created for user export selection. |
| REL-004 | DYEC first release | Commit, push, and annotated-tag DYEC after DayOA `10.0.23` pin and manifest | SUCCESS | release_train | Gate 2 | Commit `3604eaf1`; annotated tag `10.0.37`; pushed `jem-dev` and tag `10.0.37` | First DYEC release complete. |
| REL-005 | DYEC self pin | Update DYEC self pins after first DYEC release | SUCCESS | release_train | Gate 3 | `config/daylily_cli_global.yaml`; `daylily_ec/resources/payload/config/daylily_cli_global.yaml`; `tests/test_lsmc_bio_fork_contract.py`; `pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py -q` -> 15 passed; final tag `10.0.39` | `10.0.38` was pushed, then superseded by `10.0.39` so the latest DYEC release self-pins to its current release tag instead of the prior tag. |
| REL-006 | Final verification | Verify tests, clean git state, annotated tags, pushed branch/tags, and manifest summary | SUCCESS | acceptance | Gate 5 | Tests passed; manifest shows 106 dirs inspected, 82 need export review, active workflow process lines `0`; final push/tag verification recorded in chat final report | All ledger rows terminal. |

## dyecX4 Manifest Summary

- Manifest Markdown: `docs/plans/20260616T001451Z_dyecx4_unexported_export_manifest.md`
- Manifest TSV: `docs/plans/20260616T001451Z_dyecx4_unexported_export_manifest.tsv`
- Manifest JSON: `docs/plans/20260616T001451Z_dyecx4_unexported_export_manifest.json`
- Analysis directories inspected: `106`
- Needs export review: `82`
- Exported candidates: `24`
- Active workflow process lines: `0`
- Slurm status command rc: `0`
- Tmux sessions present: `58`
