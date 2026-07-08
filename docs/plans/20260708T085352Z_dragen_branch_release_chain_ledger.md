# DRAGEN Branch Review And Release Chain Ledger

Created: 2026-07-08T08:53:52Z

Objective: review the DRAGEN feature changes on `jem-dev-dragen` in DayOA and DYEC, merge those changes into `jem-dev`, then run the chained release process: DayOA release, DYEC DayOA-pin release, and DYEC self-pin release.

## Gate 0 Inventory

Repos:

- DayOA: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DYEC: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`

Branch review commands:

- DayOA: `git diff --stat $(git merge-base origin/jem-dev origin/jem-dev-dragen)..origin/jem-dev-dragen`
- DYEC: `git diff --stat $(git merge-base origin/jem-dev origin/jem-dev-dragen)..origin/jem-dev-dragen`
- Tag availability: DayOA `git ls-remote --tags origin '10.0.67'`; DYEC `git ls-remote --tags origin '10.0.111' '10.0.112'`

Baseline:

- DayOA `jem-dev`: `ce41c6c`, annotated tag `10.0.66`
- DayOA `jem-dev-dragen`: `104fa2d`
- DayOA merge base: `7d519f9`
- DayOA branch-owned changes: 20 files, 2109 insertions, 43 deletions
- DYEC `jem-dev`: `efec655f`, one commit past annotated tag `10.0.110`
- DYEC `jem-dev-dragen`: `67ae16e2`
- DYEC merge base: `b640ce4d`
- DYEC branch-owned changes: 26 files, 672 insertions, 37 deletions
- Available next tags: DayOA `10.0.67`, DYEC `10.0.111`, DYEC `10.0.112`

Reviewed branch-owned surfaces:

- DayOA:
  - RHEL Slurm profile under `config/day_profiles/slurm_rhel/`
  - explicit workflow partition override handling
  - DRAGEN pangenome/sentpg concordance and RHEL rule resources
  - `dragen_snv_concordance` target alias
  - focused profile/rule/alias tests
- DYEC:
  - DRAGEN RHEL headnode launch/config environment fixes
  - `install-daylily-headnode-tools` payload updates
  - RHEL DRAGEN post-install IMDS/user environment changes
  - DRAGEN command catalog entries and repository override handling
  - focused CLI/catalog/headnode/script tests

Version plan:

- DayOA DRAGEN release: `10.0.67`
- DYEC DayOA-pin DRAGEN release: `10.0.111`
- DYEC self-pin follow-up release: `10.0.112`

## Tracking Rows

| ID | Repo | Requirement | Status | Evidence | Terminal Note |
|---|---|---|---|---|---|
| DRG-001 | DayOA | Review `jem-dev-dragen` branch-owned changes before merge. | SUCCESS | Branch-owned diff from merge-base `7d519f9` to `104fa2d`: 20 files, RHEL profile, DRAGEN concordance rules, alias/tests. | Review found scoped DRAGEN/RHEL Slurm feature work, no broad unrelated file removals in branch-owned diff. |
| DRG-002 | DayOA | Merge `origin/jem-dev-dragen` into `jem-dev`, test, push, and tag `10.0.67`. | SUCCESS | Merge commit `c0acb42`; `pytest tests/test_slurm_profile.py tests/test_workflow_target_aliases.py tests/test_pangenome_kitchensink_contracts.py tests/test_sentieon_model_bundle_config.py tests/test_slurm_caller_partitions.py -q -> 35 passed`; pushed `jem-dev`; annotated tag `10.0.67` pushed; `git cat-file -t 10.0.67 -> tag`. | DayOA DRAGEN/RHEL profile changes are released as `10.0.67`. |
| DRG-003 | DYEC | Review `jem-dev-dragen` branch-owned changes before merge. | SUCCESS | Branch-owned diff from merge-base `b640ce4d` to `67ae16e2`: 26 files, DRAGEN headnode launch/config fixes, catalog entries, payload/script/tests. | Review found scoped DRAGEN RHEL headnode and catalog feature work, with merge expected to reconcile newer `jem-dev` release/pin files. |
| DRG-004 | DYEC | Merge `origin/jem-dev-dragen` into `jem-dev`, update DayOA pins to `10.0.67`, test, push, and tag `10.0.111`. | SUCCESS | Merge produced conflicts in `tests/test_cli_registry_v2.py` and `tests/test_repository_catalog.py`; resolved by preserving current `jem-dev` runtime/cost/export assertions and adding DRAGEN catalog assertions. Active DayOA pin surfaces updated to `10.0.67`: `pyproject.toml`, both command catalog copies, `config/dragen_fix5_repo_overrides.txt`, `tests/test_lsmc_bio_fork_contract.py`, `tests/test_repository_catalog.py`, `tests/test_cli_registry_v2.py`, and `tests/test_tests_runner.py`. `pytest tests/test_cli_registry_v2.py tests/test_headnode_init.py tests/test_repository_catalog.py tests/test_script_entrypoints.py tests/test_tests_runner.py tests/test_lsmc_bio_fork_contract.py tests/test_packaged_defaults.py -q -> 246 passed`; `bash -n` passed for DRAGEN post-install and headnode-tool scripts plus packaged copies; commit `81b7e76d`; annotated tag `10.0.111` pushed. | DYEC DRAGEN branch changes and DayOA `10.0.67` pins are released as `10.0.111`. |
| DRG-005 | DYEC | Update DYEC self-pin to `10.0.111`, test, push, and tag `10.0.112`. | SUCCESS | Edited `config/daylily_cli_global.yaml`, `daylily_ec/resources/payload/config/daylily_cli_global.yaml`, and `tests/test_lsmc_bio_fork_contract.py` to point at `10.0.111`; `pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py tests/test_cli_registry_v2.py tests/test_packaged_defaults.py -q -> 171 passed`; commit `335e6a7e`; annotated tag `10.0.112` pushed. | DYEC self-pin release is complete as `10.0.112`; this ledger closure intentionally follows the tag so the tag is not moved. |
| DRG-006 | Both | Final verification: clean local repos, annotated tags, pushed refs, and exact final version report. | IN_PROGRESS | Final verification pending after this ledger closure commit. |  |

## Final Notes

- DayOA DRAGEN branch was merged into `jem-dev` and released as annotated tag `10.0.67`.
- DYEC DRAGEN branch was merged into `jem-dev` with DayOA pins updated to `10.0.67`, then released as annotated tag `10.0.111`.
- DYEC self-pin now points to `10.0.111`, and the follow-up release was pushed as annotated tag `10.0.112`.
- Historical `config/command_catalog_performance_history.json` entries still mention older DayOA tags because they are recorded performance history, not active pin surfaces.
