# DYEC Headnode Cache Config Release Ledger

Created: 2026-06-03T12:58:51Z

## Objective

Make the Sarek/Nextflow container-cache fix durable in DYEC headnode setup, correct stale packaged DayOA runtime config, test the affected surfaces, publish the next DYEC release, and copy the updated headnode bootstrap assets to the LSMC and Daylily us-west-2 reference buckets.

## Gate 0 Inventory

- DYEC repo: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster`
- DYEC branch: `codex/dyec515-full-catalog-20260531`
- DYEC latest numeric semver tag at inventory: `5.1.29`
- DYEC branch state at inventory: `HEAD=90aa0523`, one commit past `5.1.29`
- Dirty files before this change: `docs/plans/20260603T122155Z_hg003_dayoa_sarek_relaunch_ledger.md` and `docs/plans/20260603T122558Z_dyec5128_command_catalog_validation/events.jsonl`
- DayOA repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
- DayOA branch state: clean, synced, `HEAD=54d53b9`, exact tag `2.0.41`, `2.0.41...HEAD` count `0 0`
- AWS identity probes: `lsmc` us-west-2 account `108782052779`; `daylily` us-west-2 account `670484050738`
- Assumption: no DayOA retag is needed because current DayOA is already exactly at the published `2.0.41` release tag.

## Rows

| ID | Repo | Requirement | Status | Category | Gate | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|
| HC-001 | DYEC | Provision `/fsx/work`, `/fsx/run_dir_mounts`, headnode-owned Sarek/Nextflow/cache roots, and a cache-profile script in post-install source and payload. | SUCCESS | config_or_startup_contract | Gate 5 | `config/day_cluster/post_install_ubuntu_combined.sh`; `daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh`; focused tests passed. |  | New clusters install the per-user cache/work root contract instead of relying on a shared writable container cache. |
| HC-002 | DYEC | Correct packaged global config self pins and Sentieon runtime paths. | SUCCESS | config_or_startup_contract | Gate 5 | `config/daylily_cli_global.yaml`; `daylily_ec/resources/payload/config/daylily_cli_global.yaml`; focused tests passed. |  | Global config now points at DYEC `5.1.30`, the real Sentieon license asset, and Sentieon `202503.02`. |
| HC-003 | DYEC | Update readiness/tests to enforce the new headnode cache contract and packaged parity. | SUCCESS | contract_test | Gate 5 | `daylily_ec/headnode_readiness.py`; `tests/test_headnode_init.py`; `tests/test_headnode_readiness.py`; `tests/test_workflow.py`; focused tests passed. |  | Readiness checks fail if `/fsx/work/ubuntu/...`, `/fsx/run_dir_mounts`, or `/etc/profile.d/daylily-runtime-cache.sh` are absent. |
| HC-004 | DayOA | Verify whether a DayOA release is needed for this train. | SUCCESS | release_publish | Gate 5 | `git status --short --branch` clean; `git describe --tags --dirty --always --match '[0-9]*.[0-9]*.[0-9]*'` -> `2.0.41`; `git rev-list --left-right --count 2.0.41...HEAD` -> `0 0`. |  | DayOA is already at the current release tag; no empty retag or package re-upload needed. |
| HC-005 | DYEC | Run focused tests and checks. | SUCCESS | contract_test | Gate 5 | `source ./activate && bash -n config/day_cluster/post_install_ubuntu_combined.sh && python -m pytest -q tests/test_packaged_defaults.py tests/test_headnode_init.py tests/test_headnode_readiness.py tests/test_resources_extraction.py tests/test_workflow.py::TestConfigureHeadnode::test_repo_checkout_uses_published_detached_tag tests/test_versioning.py` -> 34 passed; `source ./activate && python -m pytest -q tests/test_repository_catalog.py tests/test_cli_registry_v2.py tests/test_s3.py tests/test_workflow.py` -> 232 passed; rerun focused pytest -> 34 passed; `source ./activate && ruff check daylily_ec/headnode_readiness.py tests/test_headnode_readiness.py tests/test_headnode_init.py tests/test_workflow.py` -> all checks passed; `git diff --check` clean. |  | Focused local validation passed before commit. |
| HC-006 | DYEC | Commit, push, tag, build, publish, and verify next DYEC release. | OPEN | release_publish | Gate 5 | Pending. |  |  |
| HC-007 | S3 | Publish updated headnode config assets to LSMC us-west-2 and Daylily public us-west-2 reference buckets with readback hash verification. | OPEN | release_publish | Gate 5 | Pending. |  |  |
| HC-008 | Cross-repo | Verify final DayOA/DYEC release train state. | OPEN | final_acceptance | Gate 5 | Pending. |  |  |

## Evidence Log

- 2026-06-03T12:58:51Z: Gate 0 recorded before tests, commit, tags, package upload, or S3 publication.
- 2026-06-03T13:02Z: Focused and broader local validation passed; dirty live-run ledger files were left unstaged for release commit scoping.
