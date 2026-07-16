# DayOA/DYEC Partition Release Ledger

Created: 2026-07-09T05:15:54Z

## Objective

Release the DayOA Intel partition-string changes, then advance DYEC to consume that DayOA tag, then advance the DYEC self pin.

## Gate 0 Inventory

| Surface | Evidence |
|---|---|
| DayOA repo | `/Users/jmajor/projects/lsmc/daylily-omics-analysis` |
| DYEC repo | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` |
| Branches | Both repos on `jem-dev`; both in sync with `origin/jem-dev` before release commits (`git rev-list --left-right --count HEAD...origin/jem-dev -> 0 0`). |
| DayOA latest tag | `10.0.74` from `git tag --list '10.*'`; planned release tag `10.0.74`. |
| DYEC latest tag | `10.0.124` from `git tag --list '10.*'`; planned DayOA-pin release tag `10.0.125`; planned self-pin release tag `10.0.126`. |
| DayOA dirty baseline | Partition/profile/resource changes across Slurm profiles, rule config YAML, workflow rules, and focused tests. |
| DYEC dirty baseline | Intel cluster config and packaged payload config changes, `tests/test_packaged_defaults.py`, plus this release ledger and pre-existing untracked `docs/plans/20260709T033739Z_intel_memory_partition_queues_ledger.md`. |
| Pin surfaces | DayOA dependency in `pyproject.toml`; command catalog DayOA tags in `config/daylily_pipeline_command_catalog.yaml` and packaged copy; DYEC self pins in `config/daylily_cli_global.yaml` and packaged copy; tests with blessed tags. |
| Safety boundary | No DayOA workflow execution, no Slurm admin action, no AWS destructive action. Git commits, annotated tags, and pushes only. |

## Tracking Rows

| ID | Repo | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | DayOA | Commit, push, annotated-tag, and push DayOA partition-string release `10.0.74` on `jem-dev`. | SUCCESS | feature_implementation | Gate 5 | Codex | `python -m pytest tests/test_slurm_profile.py tests/test_dynamic_resource_helpers.py tests/test_multiqc_qc_targets.py tests/test_htd_callers_contract.py tests/test_slurm_caller_partitions.py -q -> 96 passed`; commit `67a3c82`; pushed `jem-dev`; pushed annotated tag `10.0.74`. |  | DayOA partition release is available on `origin/jem-dev` and tag `10.0.74`. |
| REL-002 | DYEC | Update DayOA pin surfaces to `10.0.74`, commit/push dirty DYEC state, annotated-tag/push `10.0.125`. | SUCCESS | config_or_startup_contract | Gate 5 | Codex | `source ./activate && python -m pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py tests/test_tests_runner.py tests/test_cli_registry_v2.py tests/test_packaged_defaults.py -q -> 203 passed`; commit `c6309a3c`; pushed `jem-dev`; pushed annotated tag `10.0.125`. |  | DYEC now pins DayOA `10.0.74` in dependency, catalog, packaged catalog, repo override, and tests. |
| REL-003 | DYEC | Update DYEC self pin to `10.0.125`, commit/push, annotated-tag/push `10.0.126`. | SUCCESS | config_or_startup_contract | Gate 5 | Codex | `config/daylily_cli_global.yaml`, packaged copy, `config/dragen_fix5_repo_overrides.txt`, and `tests/test_lsmc_bio_fork_contract.py` set DYEC self pin to `10.0.125`; focused tests passed again with `203 passed`; final release tag is `10.0.126`. |  | DYEC self pin advances to the just-pushed `10.0.125` release, and the self-pin commit is released as `10.0.126`. |
| REL-004 | Both | Verify focused tests and tag types; report final tag state. | SUCCESS | contract_test | Gate 5 | Codex | DayOA focused tests `96 passed`; DYEC focused tests `203 passed` before both DYEC releases; `git diff --check` passed in both repos before release commits; annotated tag type verification performed after tag creation. |  | No working rows remain; final release train is DayOA `10.0.74`, DYEC DayOA-pin release `10.0.125`, and DYEC self-pin release `10.0.126`. |
