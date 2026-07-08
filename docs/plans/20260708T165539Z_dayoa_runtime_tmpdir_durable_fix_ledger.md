# DayOA Runtime TMPDIR Durable Fix Ledger

Date: 2026-07-08T16:55:39Z

## Gate 0 Inventory

- Controlling request: make the live workaround durable so future DYEC/DayOA runs do not use `/dev/shm/tmp*` for controller-side conda/runtime temp creation.
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch `jem-dev`.
- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`, branch `jem-dev`.
- Pre-existing dirty state: both repos already had unrelated dirty files from the active jul8itelx4 catalog and run-QC work; this ledger only covers the runtime temp-root fix.

## Rows

| ID | Repo | Requirement | Status | Category | Evidence | Terminal Note |
|---|---|---|---|---|---|---|
| TMP-001 | DayOA | `bin/day_run` must honor an explicit `DAYOA_RUNTIME_TMPDIR` and export matching `TMPDIR`, `TMP`, and `TEMP`. | SUCCESS | feature_implementation | `bin/day_run`; `pytest tests/test_shell_wrapper_contracts.py -q -> 25 passed`; `bash -n bin/day_run -> passed` | Future `dy-r` launches with `DAYOA_RUNTIME_TMPDIR` no longer reset controller temp back to the configured Sentieon tmpdir. |
| TMP-002 | DayOA | `bin/day_activate` must preserve the same runtime temp-root contract during profile activation. | SUCCESS | feature_implementation | `bin/day_activate`; `pytest tests/test_shell_wrapper_contracts.py -q -> 25 passed`; `bash -n bin/day_activate -> passed` | Activation keeps Sentieon config intact but routes process temp vars to the explicit runtime temp root. |
| TMP-003 | DYEC | Generated headnode workflow launches must create and export a per-session `/tmp/dayoa-conda-tmp-*` runtime temp root before DayOA activation and `dy-r`. | SUCCESS | feature_implementation | `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`; `pytest tests/test_script_entrypoints.py -q -> 33 passed`; `python -m py_compile daylily_ec/scripts/daylily_run_omics_analysis_headnode.py -> passed` | Future DYEC `workflow launch` sessions default to a session-scoped temp root outside `/dev/shm`, including `TMPDIR`, `TMP`, `TEMP`, and pip/cache envs. |
| TMP-004 | DYEC | DYEC must protect immediate future launches that still clone an older DayOA tag whose wrappers do not yet honor `DAYOA_RUNTIME_TMPDIR`. | SUCCESS | feature_implementation | `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`; `tests/test_script_entrypoints.py` checks `patch_dayoa_runtime_tmpdir_wrappers` runs before conda/day activation; `pytest tests/test_script_entrypoints.py -q -> 33 passed` | The generated launch script patches known old `bin/day_run` and `bin/day_activate` wrapper shapes after clone and before activation; fixed wrappers are detected as already present and unknown shapes fail hard. |

## Final State

All rows are terminal `SUCCESS`. No live cluster mutation, Slurm action, job cancellation, DRA mutation, commit, tag, or push was performed for this fix.
