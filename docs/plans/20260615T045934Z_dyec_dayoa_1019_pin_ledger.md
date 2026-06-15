# DYEC DayOA 10.0.19 Pin Ledger

Created: 2026-06-15T04:59:34Z

## Objective

Update DYEC `jem-dev` so future workflow launches can use clean, pushed code for the successful HG003 HiOMR rerun:

- pin DayOA to `10.0.19`;
- keep bundled DayOA command catalog refs aligned to `10.0.19`;
- carry the active Sentieon runtime path cutover to `sentieon-genomics-202503.03`;
- create a normal DYEC release tag and then a self-pin release tag.

## Gate 0

| Check | Evidence |
| --- | --- |
| DYEC branch | `jem-dev` |
| Start tag | `10.0.29` |
| DayOA release to pin | `10.0.19`, commit `a391fcf`, pushed to `origin/jem-dev` |
| Pre-existing dirty tracked files | `config/daylily_cli_global.yaml`, `daylily_ec/resources/payload/config/daylily_cli_global.yaml` already pointed Sentieon install dir at `sentieon-genomics-202503.03`. |
| Untracked files left out | `docs/plans/20260615T045051Z_sentieon_20250303_runtime_cutover_ledger.md`, `docs/plans/20260615T045051Z_sentieon_20250303_runtime_cutover_ssm.py` because the helper script uses raw AWS CLI sync and is not part of the DYEC CLI-only rerun path. |

## Rows

| ID | Scope | Status | Evidence |
| --- | --- | --- |
| PIN-001 | Update `pyproject.toml` DayOA dependency to `10.0.19`. | DONE | `pyproject.toml` dependency now references `git+https://github.com/lsmc-bio/daylily-omics-analysis.git@10.0.19`. |
| PIN-002 | Update active and packaged command catalog DayOA refs to `10.0.19`. | DONE | `config/daylily_pipeline_command_catalog.yaml` and packaged payload catalog now use `10.0.19` for DayOA default refs/git tags/validated versions. |
| PIN-003 | Include active and packaged global Sentieon runtime path `sentieon-genomics-202503.03`. | DONE | `config/daylily_cli_global.yaml` and packaged payload config now use `/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.03/`. |
| REL-001 | Commit/tag/push DYEC DayOA pin release. | IN_PROGRESS | Planned tag `10.0.30`. |
| REL-002 | Commit/tag/push DYEC self-pin release. | OPEN | Planned tag `10.0.31`. |

## Validation Plan

```bash
python -m pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py -q
git diff --check
```

Validation result before `10.0.30` commit:

- `tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py`: `15 passed in 0.60s`.
- `git diff --check`: passed.
