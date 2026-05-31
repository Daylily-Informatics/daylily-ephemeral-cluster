# Catalog Mount Contract And Release Cleanup Ledger

Created: 2026-05-31T10:11:14Z

## Objective

Make the command catalog explicit about whether source data is default-mounted,
requires a run-directory DRA, or has no external source data; sync source and
packaged catalogs; remove stale DYEC Hybrid Ultima/ONT runtime repair; and assess
the remaining DYEC release-train checklist.

## Rows

| ID | Requirement | Status | Evidence | Terminal note |
|---|---|---|---|---|
| CAT-001 | Add structured source mount contract fields. | SUCCESS | `daylily_ec/repositories.py` requires `test_data_profile.source_mount_mode` with `none`, `default_mounted`, or `run_dra_required`; profiles also expose `source_s3_uri_template`, `source_fsx_prefix`, and run-context `SOURCE_S3_URI` / `MOUNT_ID` columns where applicable. The schema rejects run-analysis commands that do not use a `run_dra_required` profile or whose input contract omits those run-context columns. | Catalog callers can now distinguish default-mounted sources from run DRAs without parsing prose. |
| CAT-002 | Add full S3 prefixes where the catalog knows them. | SUCCESS | `config/daylily_available_repositories.yaml` and packaged copy include exact run prefixes for Illumina, ONT, and Ultima run-analysis profiles; default sample profile records the primary reference-read S3 prefix. | Exact per-run launch identity still belongs in `runs.tsv`; catalog states the required shape and validation roots. |
| CAT-003 | Sync packaged catalog. | SUCCESS | `cmp -s config/daylily_available_repositories.yaml daylily_ec/resources/payload/config/daylily_available_repositories.yaml` returned 0. | Packaged `load_repository_catalog()` no longer sees stale schema/content. |
| RUN-001 | Remove stale Hybrid Ultima/ONT DYEC runtime repair. | SUCCESS | Removed `hybrid_ultima_ont_stage1_runtime_repair_requested` and `patch_hybrid_ultima_ont_stage1_assertion`; focused test asserts the repair strings remain absent. | DayOA owns the fix path now; DYEC no longer blocks before Snakemake on the old target path. |
| DOC-001 | Document mount-mode interpretation. | SUCCESS | README, `docs/dra_fsx_strategy.md`, and `docs/operations.md` describe `source_mount_mode`, default mounts, and run-DRA-required behavior. | Active docs no longer require operators to infer mount behavior from notes. |
| LEDGER-001 | Patch stale DYEC ledgers. | SUCCESS | Updated the command-catalog validation ledger, catalog metadata ledger, and 5.1.4 release ledger with current source/package sync, focused validation, and remaining release state. | DYEC release remains open for commit/tag/push/build/publish. |
| TEST-001 | Run focused tests. | SUCCESS | `python -m pytest tests/test_repository_catalog.py tests/test_cli_registry_v2.py tests/test_script_entrypoints.py tests/test_export.py tests/test_headnode_init.py tests/test_workflow.py::TestClusterBootConfigPublish tests/test_headnode_readiness.py tests/test_run_mounts.py -q` -> 212 passed. | Catalog/package, export/Dewey registration, script-entrypoint, headnode/bootstrap, readiness, and run-mount coverage passed. |
| TEST-002 | Run syntax/package checks. | SUCCESS | `py_compile` passed for touched Python modules; `python -m ruff check daylily_ec/repositories.py daylily_ec/scripts/daylily_run_omics_analysis_headnode.py tests/test_repository_catalog.py tests/test_script_entrypoints.py` passed; YAML/TOML parse passed; `git diff --check` passed; `python -m pip install -e . --dry-run` resolved DayOA `2.0.26`. | No install, build, tag, push, or publish side effects were performed. |
| REL-001 | Finish DYEC 5.1.4 release train. | OPEN | Commit is prepared separately; tag `5.1.4`, push, build from `TWINE`, and publish with `twup` were not performed in this cleanup pass. | Requires explicit release execution after reviewing the committed diff. |

## Assessment Of Prior Checklist

| Checklist item | Current state |
|---|---|
| Sync DYEC packaged catalog | Complete. Source and packaged catalogs match byte-for-byte. |
| Commit DYEC metadata work | Ready after this ledger; commit should include catalog metadata, 2.0.26 pins, stale repair removal, docs, tests, and ledger updates. |
| Remove stale Hybrid Ultima/ONT runtime repair | Complete locally. |
| Patch stale docs/ledgers | DYEC active docs and ledgers patched. DayOA release ledger/docs are outside this DYEC worktree. No active DYEC docs contain the stale "merges outputs locally" wording. |
| Rerun focused DYEC tests | Complete; 212 focused tests passed plus ruff, py_compile, parse checks, diff check, and pip dry-run. |
| Finish DYEC release train | Still open: commit, annotated tag `5.1.4`, tag verification, push, build, and `twup` publish remain. |
