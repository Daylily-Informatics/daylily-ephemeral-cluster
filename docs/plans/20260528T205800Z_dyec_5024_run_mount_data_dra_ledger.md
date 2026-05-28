# DYEC 5.0.24 Run Mount Data DRA Ledger

Control ledger path: `/Users/jmajor/projects/mega_dayhoff/repos_work/release_worktrees/daylily-ec-5-0-24-run-mount-fix-20260528/docs/plans/20260528T205800Z_dyec_5024_run_mount_data_dra_ledger.md`

## Summary

Release DYEC `5.0.24` to fix run-directory DRA inspection on clusters that also have a custom `/data/` DRA. Production Ursa `4.0.20` hit this during OWY replay for run `20260520_LH01121_0001_A23WW7FLT4`: the explicit run DRA became `AVAILABLE`, but `mounts list` / `mounts describe --mount-id` failed with `mount_id is required` while processing the existing `/data/` association.

No destructive AWS action is included.

## Gate 0 Inventory

- Source worktree: `/Users/jmajor/projects/mega_dayhoff/repos_work/release_worktrees/daylily-ec-5-0-24-run-mount-fix-20260528`
- Branch: `codex/dyec-run-mount-data-dra-fix-20260528`
- Base: `origin/main` at `2517224b` (`Record DYEC 5.0.23 publish evidence`)
- Latest release tag before this work: `5.0.23`
- Live evidence:
  - Cluster `xfer-cluster`, region `us-west-2`, FSx `fs-0e2c4e0540a459b1d`.
  - Existing custom DRA: `/data/` -> `s3://lsmc-dayoa-omics-analysis-us-west-2/data/`.
  - OWY run DRA: `/run_dir_mounts/20260520_LH01121_0001_A23WW7FLT4/`, association `dra-08847d14e08478c49`, lifecycle `AVAILABLE`.
  - Failure reproduced on production host: `python -m daylily_ec.cli --json mounts describe --mount-id 20260520_LH01121_0001_A23WW7FLT4 --cluster xfer-cluster --region us-west-2 --profile lsmc` -> `mount_id is required`.
  - Stack trace points to `daylily_ec.run_mounts.headnode_path_from_file_system_path("/data/")`.

## Gates

| Gate | Purpose | Status | Evidence |
|---|---|---|---|
| 0 | Inventory freeze | SUCCESS | Baseline and production failure evidence above. |
| 1 | Fix path normalization | SUCCESS | `/data/` now maps to `/fsx/data/`; run mount paths still validate the mount id below `/run_dir_mounts/`. |
| 2 | Focused validation | SUCCESS | `python -m pytest -q tests/test_run_mounts.py tests/test_packaged_defaults.py tests/test_versioning.py` -> `30 passed`; `ruff check daylily_ec/run_mounts.py tests/test_run_mounts.py`; `git diff --check`. |
| 3 | Release and publish | SUCCESS | Commit `abc88cf9`; annotated tag `5.0.24`; branch, main, and tag pushed; `python -m build` produced `5.0.24` wheel/sdist; `twup` uploaded to PyPI; `python -m pip index versions daylily-ephemeral-cluster` reports latest `5.0.24`. |

## Ledger Rows

| ID | Owner | Requirement | Status | Gate | Evidence | Terminal Note |
|---|---|---|---|---|---|---|
| DYEC24-001 | Orchestrator | Create release ledger with production failure evidence. | SUCCESS | 0 | This file. | Ledger initialized before release. |
| DYEC24-002 | Orchestrator | Fix `/data/` headnode path handling without weakening run mount validation. | SUCCESS | 1 | `daylily_ec/run_mounts.py`; `tests/test_run_mounts.py`. | `/data/` is a valid one-segment custom DRA path; run DRA validation remains explicit. |
| DYEC24-003 | Orchestrator | Update source and packaged self-pins to `5.0.24`. | SUCCESS | 1 | `config/daylily_cli_global.yaml`; `daylily_ec/resources/payload/config/daylily_cli_global.yaml`. | Self-pins point at the intended release tag. |
| DYEC24-004 | Orchestrator | Run focused tests and diff checks. | SUCCESS | 2 | `python -m pytest -q tests/test_run_mounts.py tests/test_packaged_defaults.py tests/test_versioning.py` -> `30 passed`; `ruff check daylily_ec/run_mounts.py tests/test_run_mounts.py`; `git diff --check`. | Focused validation passed. |
| DYEC24-005 | Orchestrator | Commit, push branch/main, annotated-tag `5.0.24`, build, publish via `twup`, and verify PyPI availability. | SUCCESS | 3 | Commit `abc88cf9`; annotated tag `5.0.24`; pushed branch `codex/dyec-run-mount-data-dra-fix-20260528`, `main`, and tag `5.0.24`; `twup` uploaded artifacts; PyPI reports latest `5.0.24`. | Release published. |

## Terminal Report

- Status counts: `SUCCESS=5`, `OPEN=0`, `IN_PROGRESS=0`, `ATTEMPTING_BUGFIX=0`, `BLOCKED=0`.
- Published ref: `5.0.24`.
- Focused validation: `30 passed`; ruff and diff checks passed.
- Remaining work is in Ursa: update exact `daylily-ephemeral-cluster==5.0.24`, restart production Ursa, and replay the queued OWY run-directory trigger.
