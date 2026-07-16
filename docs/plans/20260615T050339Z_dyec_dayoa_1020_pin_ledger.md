# DYEC DayOA 10.0.20 Pin Ledger

Created: 2026-06-15T05:03:39Z

## Objective

Move DYEC `jem-dev` to the DayOA `10.0.20` release so reruns clone the current
HiOMR recovery-safe DayOA code, including the raised Slurm default memory commit
and corrected active Sentieon hybrid model bundle pins.

## Gate 0

| Check | Evidence |
| --- | --- |
| DayOA source branch | `origin/jem-dev` at `8de2bd3` |
| DayOA release tag | annotated tag `10.0.20` pushed to `origin` |
| DYEC starting point | `jem-dev` at `11006c3f`, tag `10.0.32` |
| Existing untracked DYEC files | `docs/plans/20260615T045051Z_sentieon_20250303_runtime_cutover_ledger.md`, `docs/plans/20260615T045051Z_sentieon_20250303_runtime_cutover_ssm.py` |

## Ledger

| ID | Scope | Status | Evidence |
| --- | --- | --- | --- |
| PIN-001 | Update active and packaged DYEC command catalogs plus pyproject/test contracts from DayOA `10.0.19` to `10.0.20`. | DONE | Updated `pyproject.toml`, active/packaged command catalogs, and catalog/fork tests. |
| TEST-001 | Run focused DYEC catalog/fork tests and diff check. | DONE | `python -m pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py -q` -> `15 passed`; `git diff --check` passed. |
| RELEASE-001 | Commit, push, and tag the DayOA pin commit. | DONE | Commit `467525b9` pushed to `origin/jem-dev`; annotated tag `10.0.33` pushed. |
| SELF-001 | Update DYEC self-pin to the new pin release tag and create the final release tag. | DONE | Active and packaged `daylily_cli_global.yaml` now point at DYEC `10.0.33`; `python -m pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py -q` -> `15 passed`; `git diff --check` passed; this commit is released as `10.0.34`. |
