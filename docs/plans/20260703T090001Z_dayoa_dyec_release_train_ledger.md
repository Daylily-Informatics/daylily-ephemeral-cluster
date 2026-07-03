# DayOA / DYEC Release Train Ledger

Controlling request: commit dirty DayOA on `jem-dev`, push and tag a new version; update DYEC DayOA pins in `pyproject.toml` and `config/**`, commit dirty DYEC on `jem-dev`, push and tag a new version; update DYEC self-pins to that new version, commit/push/tag again, and report final versions.

Ledger path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260703T090001Z_dayoa_dyec_release_train_ledger.md`

## Gate 0: Inventory Freeze

- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DayOA branch baseline: `jem-dev...origin/jem-dev`
- DayOA dirty baseline:
  - `workflow/rules/sentieon_markdups.smk`
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DYEC branch baseline: `jem-dev...origin/jem-dev`
- DYEC dirty baseline:
  - `config/day_cluster/post_install_rhel8_dragen.sh`
  - `daylily_ec/cli.py`
  - `daylily_ec/resources/payload/config/day_cluster/post_install_rhel8_dragen.sh`
  - `docs/cli_reference.md`
  - `docs/operations.md`
  - `tests/test_cli_registry_v2.py`
  - `config/day_cluster/prod_cluster_dragen_native_ami_rhel8_nofsx.yaml`
  - `config/daylily_ephemeral_cluster_dragen_native_ami_rhel8_2c_nofsx.yaml`
  - `daylily_ec/aws/cluster_tags.py`
  - `docs/plans/20260703T084957Z_dyec_cluster_tags_cli_ledger.md`
  - `tests/test_cluster_tags.py`
- Current local max tags after fetch:
  - DayOA: `10.0.53`
  - DYEC: `10.0.82`
- Candidate release tags:
  - DayOA: `10.0.54`
  - DYEC DayOA-pin release: `10.0.83`
  - DYEC self-pin release: `10.0.84`
- Remote tag check:
  - DayOA `10.0.54` not present on origin.
  - DYEC `10.0.83` and `10.0.84` not present on origin.
- Live-system boundary:
  - No live cluster, Slurm, SSM, headnode, workflow, or destructive AWS action is approved or required.

## Control Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | DayOA | Validate, commit, push `jem-dev`, create annotated tag, and push DayOA release. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `pytest tests/test_slurm_profile.py -q -> 14 passed`; commit `8e81ad5`; pushed `jem-dev`; annotated tag `10.0.54` pushed and `git cat-file -t 10.0.54 -> tag`. |  | DayOA release `10.0.54` is pushed on `jem-dev`. |
| REL-002 | DYEC pins | Update DayOA pins in DYEC `pyproject.toml`, `config/**`, packaged config, and pin tests to the new DayOA tag. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `pyproject.toml`, `config/daylily_pipeline_command_catalog.yaml`, `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`, `tests/test_repository_catalog.py`, `tests/test_cli_registry_v2.py`, and `tests/test_lsmc_bio_fork_contract.py` now reference `10.0.54`; `pytest tests/test_cluster_tags.py tests/test_cluster_info.py tests/test_cli_registry_v2.py tests/test_repository_catalog.py tests/test_lsmc_bio_fork_contract.py tests/test_packaged_defaults.py -q -> 175 passed`. |  | DYEC DayOA pin surfaces now target DayOA `10.0.54`. |
| REL-003 | DYEC first release | Commit dirty DYEC release content, push `jem-dev`, create annotated tag, and push DYEC intermediate release. | OPEN | feature_implementation | Gate 1 | orchestrator | Pending |  |  |
| REL-004 | DYEC self-pin | Update DYEC self-pins to the intermediate DYEC tag. | OPEN | feature_implementation | Gate 1 | orchestrator | Pending |  |  |
| REL-005 | DYEC final release | Commit self-pin update, push `jem-dev`, create annotated tag, and push final DYEC release. | OPEN | feature_implementation | Gate 1 | orchestrator | Pending |  |  |
| REL-006 | Final verification | Verify tag types, final pin surfaces, clean owned status, and report final versions. | OPEN | contract_test | Gate 5 | orchestrator | Pending |  |  |
