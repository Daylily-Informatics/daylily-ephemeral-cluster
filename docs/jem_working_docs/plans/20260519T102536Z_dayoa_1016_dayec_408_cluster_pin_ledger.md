# DayOA 1.0.16 / DayEC 4.0.8 Pin Ledger

Date: 2026-05-19T10:25:36Z

## Gate 0: Inventory Freeze

- Controlling ledger: `docs/plans/20260519T102536Z_dayoa_1016_dayec_408_cluster_pin_ledger.md`
- Repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
- Baseline branch: `main...origin/main`
- Baseline commit: `4aec6300 Merge pull request #254 from Daylily-Informatics/codex/docs-plans-ledgers`
- Baseline DayEC tags: latest local/remote `4.0.7`; next requested release pin `4.0.8`
- Baseline DayEC bootstrap config: `config/daylily_cli_global.yaml` and packaged copy pin `4.0.7`
- Baseline DayOA catalog config: source and packaged catalogs pin `1.0.15`
- Baseline DayOA docs/tests: active docs and `tests/test_cli_registry_v2.py` still contain `1.0.12`; catalog tests contain `1.0.15`
- DayOA target tag evidence: `git ls-remote --tags ... '1.0.16*'` returned tag `8b14cc3` peeling to commit `e02f86d`
- Initial repo dirty state: clean before this ledger was created
- Live cluster inventory: `dyec cluster list --profile lsmc --region us-west-2 --verbose` returned two configured `CREATE_COMPLETE` clusters, `XL-pilot` and `dra-enabled`; the user's singular "only running cluster" target is therefore ambiguous until resolved or explicitly broadened.

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | DayOA tag | Verify DayOA `1.0.16` exists before pinning. | SUCCESS | config_or_startup_contract | Gate 0 | orchestrator | `git ls-remote --tags` found `1.0.16` tag `8b14cc3` peeling to `e02f86d`. |  | Tag exists upstream. |
| REL-002 | DayEC catalog | Update DayOA source catalog, packaged catalog, docs, and tests to `1.0.16`. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Updated active pin surfaces; `repo_catalog_cmp=0`, no stale active `1.0.12` or `1.0.15` refs, `pytest tests/test_packaged_defaults.py tests/test_repository_catalog.py tests/test_cli_registry_v2.py -q -> 101 passed`. |  | Source/package catalog, docs, and tests now agree on DayOA `1.0.16`. |
| REL-003 | DayEC release | Bump DayEC bootstrap config to `4.0.8`, then commit, tag, and push that version. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Updated `config/daylily_cli_global.yaml` and packaged copy to `4.0.8`; `cli_global_cmp=0`; remote tag lookup for `4.0.8` returned no existing tag before tag creation. |  | This ledger commit carries the `4.0.8` release pin; tag/push verification is reported after publication. |
| CLUSTER-001 | Headnode config | Update cluster-side day-clone default DayOA version to `1.0.16` on the running `lsmc` `us-west-2` cluster. | BLOCKED | config_or_startup_contract | Gate 2 | orchestrator | `dyec cluster list --profile lsmc --region us-west-2 --verbose` returned `XL-pilot` and `dra-enabled`, both `CREATE_COMPLETE` and configured. | Live inventory has two running/configured clusters, but the request names a singular target. | Needs target clarification or explicit approval to update both clusters. |
