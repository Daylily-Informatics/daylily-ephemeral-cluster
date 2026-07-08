# DayOA/DYEC Docs Release Train Ledger

Controlling request: refresh active DayOA markdown docs against current code, then refresh active DYEC markdown docs against current code, then release DayOA, pin that release in DYEC and release DYEC, then update the DYEC self-pin and release DYEC again.

Ledger path: `docs/plans/20260708T133425Z_dayoa_dyec_docs_release_train_ledger.md`

## Gate 0 Baseline

- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DayOA branch: `jem-dev`, tracking `origin/jem-dev`
- DayOA remote: `git@github.com:lsmc-bio/daylily-omics-analysis.git`
- DayOA baseline commit: `c0acb423d95beebf9d31006dbad941ef672c5c5d`
- DayOA Gate 0 status: clean
- DayOA latest local and remote semver tag: `10.0.68`
- DayOA planned release tag: `10.0.69`
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DYEC branch: `jem-dev`, tracking `origin/jem-dev`
- DYEC remote: `git@github.com:lsmc-bio/daylily-ephemeral-cluster.git`
- DYEC baseline commit: `abb87510d4b9a8080f758cabb767907996a84ebb`
- DYEC latest local and remote semver tag: `10.0.114`
- DYEC planned tags: `10.0.115` for the DayOA-pin/docs release, then `10.0.116` for the self-pin release
- DYEC Gate 0 dirty files from prior requested command-catalog work: `daylily_ec/cli.py`, `daylily_ec/tests_runner.py`, `tests/test_cli_registry_v2.py`, `tests/test_lsmc_bio_fork_contract.py`, `tests/test_repository_catalog.py`, `tests/test_tests_runner.py`
- Scope boundary: release actions target lsmc-bio `origin` remotes only. No `upstream`/Daylily-Informatics pushes are in scope.
- Tag contract: non-`v` annotated semver tags, commit first, then tag the clean release commit, then push the tag.

## Execution Rows

| ID | Repo | Requirement | Status | Evidence |
|---|---|---|---|---|
| G0 | Both | Inventory repo state, remotes, dirty files, latest tags, and release plan | SUCCESS | Gate 0 baseline above. |
| DAYOA-DOCS | DayOA | Refresh active markdown docs so README and docs index describe current feature surface | SUCCESS | Updated `README.md`, `docs/README.md`, `docs/ops/results_directory_structure.md`; active docs inspected: `README.md`, `docs/README.md`, `docs/catalog_of_tools.md`, `docs/ops/results_directory_structure.md`, `docs/workflows/*.md`; quarantine docs excluded. |
| DAYOA-VERIFY | DayOA | Run focused docs/code validation before release | SUCCESS | `python -m pytest -q tests/test_tool_catalog_docs.py tests/test_multiqc_qc_targets.py tests/test_multiqc_staging_contracts.py tests/test_multiqc_sample_identifiers.py tests/test_evidence_manifest.py` -> 83 passed; `git diff --check` clean. |
| DAYOA-RELEASE | DayOA | Commit docs, push `jem-dev`, create and push annotated `10.0.69` | SUCCESS | Commit `e2d7793`; pushed `origin/jem-dev`; `git cat-file -t 10.0.69 -> tag`; pushed tag `10.0.69`; remote tag dereferences to `e2d7793f6faf8d30524548ac693bf66c82e723e4`. |
| DYEC-DOCS | DYEC | Refresh active markdown docs for current CLI, command-catalog phasing, run-DRA waits, and defaults | SUCCESS | Updated `README.md`, `docs/quickest_start.md`, `docs/cli_reference.md`, `docs/dra_fsx_strategy.md`, `docs/testing_and_debugging.md`, and historical spec timeout note; active doc sweep no longer finds stale `3600`, `9.0.0`, `8.0.0`, or `10.0.56` in those files. |
| DYEC-DAYOA-PIN | DYEC | Update DayOA pin surfaces to `10.0.69` | SUCCESS | Updated `pyproject.toml`, `config/daylily_pipeline_command_catalog.yaml`, packaged catalog, and DayOA pin tests; `config/daylily_available_repositories.yaml` and packaged copy remain symlinks to the catalog. |
| DYEC-VERIFY-1 | DYEC | Run focused validation for command-catalog docs and DayOA pin release | SUCCESS | `pytest tests/test_tests_runner.py tests/test_cli_registry_v2.py tests/test_repository_catalog.py tests/test_lsmc_bio_fork_contract.py tests/test_packaged_defaults.py -q` -> 202 passed; `ruff check ...` -> all checks passed; `git diff --check` clean; source and packaged catalogs compare equal. Rendered default `dyec800` and `all` non-research command-catalog commands all use `-j 150` with default `--jobs 150`. |
| DYEC-RELEASE-1 | DYEC | Commit dirty DYEC work plus docs and DayOA pins, push `jem-dev`, create and push annotated `10.0.115` | OPEN | Pending. |
| DYEC-SELF-PIN | DYEC | Update DYEC self-pin surfaces to `10.0.115` | OPEN | Expected surfaces: `config/daylily_cli_global.yaml`, `daylily_ec/resources/payload/config/daylily_cli_global.yaml`, self-pin tests. |
| DYEC-VERIFY-2 | DYEC | Run focused validation for self-pin release | OPEN | Pending. |
| DYEC-RELEASE-2 | DYEC | Commit self-pin, push `jem-dev`, create and push annotated `10.0.116` | OPEN | Pending. |
| FINAL | Both | Verify local tag types and remote tag presence for all releases | OPEN | Pending. |
