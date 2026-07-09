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
| REL-002 | DYEC | Update DayOA pin surfaces to `10.0.74`, commit/push dirty DYEC state, annotated-tag/push `10.0.125`. | IN_PROGRESS | config_or_startup_contract | Gate 5 | Codex | Pending. |  |  |
| REL-003 | DYEC | Update DYEC self pin to `10.0.125`, commit/push, annotated-tag/push `10.0.126`. | OPEN | config_or_startup_contract | Gate 5 | Codex | Pending. |  |  |
| REL-004 | Both | Verify focused tests and tag types; report final tag state. | OPEN | contract_test | Gate 5 | Codex | Pending. |  |  |
