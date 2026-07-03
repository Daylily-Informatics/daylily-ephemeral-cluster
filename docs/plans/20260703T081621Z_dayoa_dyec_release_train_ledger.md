# DayOA / DYEC Release Train Ledger

Created: 2026-07-03T08:16:21Z

## Gate 0 Inventory Freeze

- Controlling request: commit dirty DayOA work to `jem-dev`, push and tag a new DayOA version; update DYEC DayOA pins in `pyproject.toml` and `config/**`, commit dirty DYEC work to `jem-dev`, push and tag a new DYEC version; update DYEC self-pin to that DYEC version, commit/push/tag a follow-up DYEC version; report final tags.
- Primary repos:
  - DayOA: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`, branch `jem-dev`, starting head `0b5e912`, remote branch `origin/jem-dev`.
  - DYEC: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch `jem-dev`, starting head `ceee014c`, remote branch `origin/jem-dev`.
- Baseline dirty state:
  - DayOA modified: `config/day_profiles/slurm/templates/config.yaml`, `tests/test_slurm_profile.py`.
  - DYEC modified: `config/day_cluster/post_install_rhel8_dragen.sh`, `config/day_cluster/post_install_ubuntu_combined.sh`, `config/day_cluster/prod_cluster_dragen_native_ami_rhel8.yaml`, `config/day_cluster/prod_cluster_dragen_pcluster_image_rhel8.yaml`, `config/day_cluster/sbatch`, `config/imagebuilder/dragen_el8_4_5_4_pcluster315.yaml`, `daylily_ec/cli.py`, `daylily_ec/resources/payload/config/day_cluster/post_install_rhel8_dragen.sh`, `daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh`, `daylily_ec/resources/payload/config/day_cluster/sbatch`, `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`, `daylily_ec/workflow/create_cluster.py`, `docs/cli_reference.md`, `docs/operations.md`, `tests/test_cli_registry_v2.py`, `tests/test_headnode_init.py`, `tests/test_packaged_defaults.py`, `tests/test_sbatch_wrapper.py`, `tests/test_triplets.py`; untracked: `config/daylily_ephemeral_cluster_dragen_native_ami_rhel8_2c_public.yaml`, `docs/plans/20260703T075311Z_dyec_benchmark_collector_cli_ledger.md`, and this ledger.
- Tag baseline after `git fetch origin jem-dev --tags`:
  - DayOA local/remote max semver tag: `10.0.52`; candidate release tag `10.0.53` was absent locally and remotely.
  - DYEC local/remote max semver tag: `10.0.80`; candidate release tags `10.0.81` and `10.0.82` were absent locally and remotely.
- Current DYEC pin surfaces before this chain:
  - DayOA pins: `10.0.52` in `pyproject.toml`, `config/daylily_pipeline_command_catalog.yaml`, packaged payload command catalog, and blessed-tag tests.
  - DYEC self pins: `10.0.79` in `config/daylily_cli_global.yaml`, packaged payload global config, and fork contract test.
- Planned tags:
  - DayOA dirty release: `10.0.53`.
  - DYEC DayOA-pin/dirty release: `10.0.81`.
  - DYEC self-pin follow-up release: `10.0.82`.
- Version/tag rules: non-`v` numeric semver tags; annotated tags; commit before tag; do not move pushed tags.
- Live-system boundary: no live cluster creation, AWS resource mutation, Slurm job submission, workflow run, PR merge, package build, or package publication requested in this release train.

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| ORCH-001 | Ledger | Record Gate 0, selected versions, dirty baseline, and terminal row counts. | SUCCESS | feature_implementation | Gate 0 | orchestrator | This ledger records Gate 0, selected versions, dirty baseline, and final row counts. |  | 5 rows total; 5 rows terminal after final tag push. |
| DAYOA-001 | DayOA | Stage dirty DayOA work, commit to `jem-dev`, push branch, create annotated tag `10.0.53`, push tag. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `pytest tests/test_slurm_profile.py -q -> 14 passed`; `git diff --check`; commit `48396e9`; `git push origin jem-dev` succeeded; annotated tag `10.0.53` pushed; `git cat-file -t 10.0.53 -> tag`. |  | DayOA dirty release is pushed and tagged as `10.0.53`. |
| DYEC-001 | DYEC DayOA pin | Update DYEC DayOA pins to `10.0.53`, include dirty DYEC work, commit to `jem-dev`, push branch, tag `10.0.81`, push tag. | SUCCESS | feature_implementation | Gate 2 | orchestrator | DYEC DayOA pins updated from `10.0.52` to `10.0.53`; `pytest tests/test_cli_registry_v2.py tests/test_repository_catalog.py tests/test_lsmc_bio_fork_contract.py tests/test_workflow.py tests/test_sbatch_wrapper.py tests/test_headnode_init.py tests/test_packaged_defaults.py tests/test_triplets.py tests/test_cluster_request_config.py tests/test_renderer.py tests/test_script_entrypoints.py -q -> 363 passed`; `python -m py_compile daylily_ec/cli.py daylily_ec/workflow/create_cluster.py daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`; `git diff --check`; commit `32d80c4d`; branch push succeeded; annotated tag `10.0.81` pushed; `git cat-file -t 10.0.81 -> tag`. |  | DYEC DayOA-pin/dirty release is pushed and tagged as `10.0.81`. |
| DYEC-002 | DYEC self pin | Update DYEC self pins to `10.0.81`, commit to `jem-dev`, push branch, tag `10.0.82`, push tag. | SUCCESS | feature_implementation | Gate 2 | orchestrator | Self-pin config and blessed-tag test constant updated from `10.0.79` to `10.0.81`; `pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py tests/test_cli_registry_v2.py -q -> 135 passed`; `git diff --check`; release tag `10.0.82` cut from this self-pin commit. |  | DYEC self-pin follow-up release is pushed and tagged as `10.0.82`. |
| VAL-001 | Validation | Run focused local checks sufficient for the release train and verify annotated tags. | SUCCESS | contract_test | Gate 5 | orchestrator | DayOA `14 passed`; DYEC first-release suite `363 passed`; DYEC self-pin suite `135 passed`; compile and whitespace checks passed; annotated tag types verified with `git cat-file -t`. |  | No live cluster creation, AWS resource mutation, Slurm job submission, workflow run, PR merge, package build, or package publication performed. |

## Final Terminal Report

- Rows terminal: 5/5.
- DayOA: commit `48396e9`; branch `jem-dev` pushed; annotated tag `10.0.53` pushed.
- DYEC DayOA-pin/dirty release: commit `32d80c4d`; branch `jem-dev` pushed; annotated tag `10.0.81` pushed.
- DYEC self-pin follow-up: self pins updated to `10.0.81`; branch `jem-dev` pushed; annotated tag `10.0.82` pushed.
- Validation: DayOA focused suite `14 passed`; DYEC first-release suite `363 passed`; DYEC self-pin suite `135 passed`; compile and whitespace checks passed.
- Live-system boundary maintained: no cluster creation, AWS resource mutation, Slurm job submission, workflow run, PR merge, package build, or package publication.
