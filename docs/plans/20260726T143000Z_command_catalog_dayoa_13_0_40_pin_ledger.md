# Command catalog DayOA 13.0.40 pin ledger

Controlling request: ensure every DYEC command-catalog launch selects the
highest released DayOA version.

## Gate 0 — inventory

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` on
  `jem-candidate-260725`; pre-existing changes are outside this task.
- Authoritative DayOA checkout: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`.
- Both local and `origin` numeric tags establish `13.0.40` as the highest
  released numeric DayOA tag at inspection time.
- Catalog baseline: 19 command `git_tag` values were `10.0.97`, one was
  `13.0.39`, and five were already `13.0.40`.
- `git_tag` is the actual launch pin. `validated_version` and `validation_runs`
  record prior validation evidence and are deliberately not rewritten to avoid
  claiming validation that has not occurred on 13.0.40.

| ID | Area | Requirement | Status | Category | Gate | Evidence | Terminal note |
|---|---|---|---|---|---|---|---|
| G0 | Inventory | Establish highest available DayOA tag and catalog pin baseline | SUCCESS | feature_implementation | Gate 0 | `git tag` and `git ls-remote --tags origin`; catalog count sweep | `13.0.40` is the target. |
| P1 | Catalog | Advance every command launch `git_tag` to `13.0.40` | SUCCESS | feature_implementation | Gate 1 | Post-change sweep found no non-`13.0.40` command `git_tag`; packaged catalog is byte-identical to source | Historical validation fields remain truthful. |
| T1 | Tests | Update catalog pin assertions and run focused tests | SUCCESS | contract_test | Gate 5 | `pytest -q tests/test_repository_catalog.py tests/test_cli_registry_v2.py tests/test_tests_runner.py` -> `259 passed` | Parsed catalog, launch argv, and runner expectations all use `13.0.40`. |
