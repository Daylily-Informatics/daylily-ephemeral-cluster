# DayOA and DYEC Release Train Ledger

Controlling plan: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260615T025936Z_dayoa_dyec_release_train_ledger.md`
Ledger path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260615T025936Z_dayoa_dyec_release_train_ledger.md`
Started: `2026-06-15T02:59:36Z`

## Gate 0 Baseline

- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DayOA branch: `jem-dev`, tracking `origin/jem-dev`
- DayOA starting status: 12 modified files plus untracked `docs/plans/20260614T214848Z_hg003_ilmn30x_pangenome_1004/`
- DayOA latest remote SemVer tag before release: `10.0.16`
- Planned DayOA release tag: `10.0.17`
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DYEC branch: `jem-dev`, tracking `origin/jem-dev`
- DYEC starting status: untracked AWS cost docs/assets and 4NA SMN12 docs/plans artifacts
- DYEC latest remote SemVer tag before release: `10.0.25`
- Planned DYEC release tags: `10.0.26` after DayOA pin update, then `10.0.27` after self-pin update
- Pin surfaces found:
  - `pyproject.toml`: DayOA dependency pinned to `10.0.16`
  - `config/daylily_pipeline_command_catalog.yaml`: DayOA `default_ref`, `validated_version`, and `git_tag` pinned to `10.0.16`
  - `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`: packaged copy pinned to `10.0.16`
  - `config/daylily_cli_global.yaml`: DYEC self pins set to `10.0.25`
  - `daylily_ec/resources/payload/config/daylily_cli_global.yaml`: packaged copy self pins set to `10.0.25`
- Live workflow execution not requested; no DayOA `dy-r` command will be launched in this release train.

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | DayOA | Commit dirty DayOA work, push `jem-dev`, tag and push `10.0.17` | SUCCESS | feature_implementation | Gate 5 | Codex | `python -m pytest tests/test_multiqc_qc_targets.py tests/test_multiqc_sample_identifiers.py tests/test_ont_fastq_contracts.py tests/test_sentieon_model_bundle_config.py -q` -> 67 passed; commit `3d824071`; pushed `origin/jem-dev`; annotated tag `10.0.17` pushed |  | DayOA dirty work released as `10.0.17`. |
| REL-002 | DYEC | Update DayOA pins to `10.0.17`, commit dirty DYEC work, push `jem-dev`, tag and push `10.0.26` | SUCCESS | config_or_startup_contract | Gate 5 | Codex | Updated `pyproject.toml`, root catalog, packaged catalog, and blessed-tag tests; `python -m pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py tests/test_packaged_defaults.py -q` -> 23 passed; commit `490314e1`; pushed `origin/jem-dev`; annotated tag `10.0.26` pushed |  | DYEC dirty work plus DayOA `10.0.17` pins released as `10.0.26`. |
| REL-003 | DYEC | Update DYEC self pins to `10.0.26`, commit, push `jem-dev`, tag and push `10.0.27` | IN_PROGRESS | config_or_startup_contract | Gate 5 | Codex | Updated `config/daylily_cli_global.yaml`, packaged `daylily_cli_global.yaml`, and `DYEC_BLESSED_TAG` to `10.0.26`; `python -m pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py tests/test_packaged_defaults.py -q` -> 23 passed |  |  |
| REL-004 | Verification | Verify local checks and remote branch/tag state after pushes | OPEN | contract_test | Gate 5 | Codex | Pending |  |  |
