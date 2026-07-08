# Command Catalog Performance Profiles Ledger

- Created: `20260708T023632Z`
- Scope: DYEC-only evidence/profile generation for command-catalog benchmark metrics.
- Boundary: Do not modify DayOA or DayOA workflow code without explicit permission.
- Source benchmark capture: `docs/plans/20260707T144453Z_benchmark_resource_review/`

| Row | Owner | Status | Evidence |
|---|---|---:|---|
| GATE0_BASELINE | Orchestrator | PASS | Repo `daylily-ephemeral-cluster`; branch `jemdev10`; existing command-catalog benchmark TSVs found under `docs/plans/20260707T144453Z_benchmark_resource_review/`; requested baseline is DYEC `10.0.103` with 18 prod + 3 dev/research evidence cohorts. |
| CATALOG_MODEL_REVIEW | Agent 1 | PASS | DYEC catalog commands expose `command_id`, `type`, `git_tag`, `display_name`, and `genome`; command-catalog runner writes registry/summary/evidence prefix but had no stable performance profile output. |
| PROFILE_GENERATOR | Agent 2 | PASS | Added `daylily_ec/command_catalog_performance.py` and `dyec tests command-catalog-performance`; generator writes command summary TSV, full per-rule profile JSON, and version-keyed history JSON. |
| BASELINE_SEED_10_0_103 | Agent 3 | PASS | Seeded `docs/plans/20260707T144453Z_benchmark_resource_review/command_catalog_performance_profile.json`, `command_catalog_performance_summary.tsv`, and `config/command_catalog_performance_history.json` for DYEC `10.0.103`; counts: 21 commands, 18 prod cohort, 3 dev cohort, 20 benchmarked, 1 no benchmark evidence. |
| DOCS_AND_TESTS | Agent 1 | PASS | Added `tests/test_command_catalog_performance.py`, CLI registry coverage, and `docs/cli_reference.md` usage. Verified with `source ./activate; pytest -q tests/test_command_catalog_performance.py tests/test_tests_runner.py::test_command_catalog_cli_emits_json tests/test_cli_registry_v2.py` and `source ./activate; ruff check daylily_ec/command_catalog_performance.py tests/test_command_catalog_performance.py tests/test_cli_registry_v2.py`. |
| FINAL_REPORT | Orchestrator | PASS | All rows terminal. Generated files are `docs/plans/20260707T144453Z_benchmark_resource_review/command_catalog_performance_profile.json`, `docs/plans/20260707T144453Z_benchmark_resource_review/command_catalog_performance_summary.tsv`, and `config/command_catalog_performance_history.json`. Only `simple-test` has no benchmark evidence. |
