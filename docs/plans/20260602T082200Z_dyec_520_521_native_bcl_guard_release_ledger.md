# DYEC 5.1.20 / 5.1.21 Native BCL Guard Release Ledger

## Objective

Release the DYEC-side native BCL Convert guard used for the Lane003 sharding
experiment, without changing the already-published DayOA `2.0.34` pin.

## Gate 0 Inventory

| Item | Evidence |
| --- | --- |
| DYEC checkout | `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster` |
| DYEC branch | `codex/dyec515-full-catalog-20260531` |
| Baseline HEAD | `a7432c406b6e3f328e97eba6e758b02cc13eeeb7`, after DYEC `5.1.19` publication record |
| Latest DYEC tag | `5.1.19`, annotated and present on origin |
| DayOA release | `2.0.34`, annotated tag resolving to `317c1ee567b9ed80592455e955d2b06aba63c25e` |
| DayOA tile-shard commit | `f8a24c1` is an ancestor of DayOA `2.0.34` |
| Included DYEC change | `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` validates required native DayOA lane-split files as well as rule markers and fails hard when they are absent |
| Next releases | `5.1.20` for the DYEC code change, then `5.1.21` for the final DYEC self-pin |

## Ledger

| ID | Step | Status | Evidence |
| --- | --- | --- | --- |
| DYEC520-001 | Confirm DayOA `2.0.34` is already published and includes the tile-shard commit. | SUCCESS | `git cat-file -t 2.0.34` returned `tag`; `git rev-list -n 1 2.0.34` returned `317c1ee567b9ed80592455e955d2b06aba63c25e`; `git merge-base --is-ancestor f8a24c1 2.0.34` returned `0`. |
| DYEC520-002 | Commit the DYEC native BCL guard and release ledger. | IN_PROGRESS | Validation before commit: `python -m pytest -q tests/test_script_entrypoints.py` passed `32 passed in 0.19s`; `python -m pytest -q tests/test_workflow.py::TestConfigureHeadnode::test_repo_checkout_uses_published_detached_tag` passed `1 passed in 0.26s`. |
| DYEC520-003 | Push branch, create annotated tag `5.1.20`, verify and push tag. | OPEN |  |
| DYEC520-004 | Build and upload DYEC `5.1.20` from the `TWINE` conda environment using `twup`. | OPEN |  |
| DYEC521-001 | Update DYEC self-pins from `5.1.19` to `5.1.21`. | OPEN |  |
| DYEC521-002 | Validate final self-pin behavior. | OPEN |  |
| DYEC521-003 | Commit, push branch, create annotated tag `5.1.21`, verify and push tag. | OPEN |  |
| DYEC521-004 | Build and upload DYEC `5.1.21` from the `TWINE` conda environment using `twup`. | OPEN |  |

## Final Status

Working ledger. Terminal status will be recorded after the double DYEC release
train finishes.
