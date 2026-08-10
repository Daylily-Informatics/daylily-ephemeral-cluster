# Bulk FSx Export With DRA Delete Ledger

Created: 2026-07-23T18:21:03Z

Cluster: `ifx-p2-1000-120-0715`
Region/profile: `us-west-2` / `lsmc`
FSx state at start: `/fsx` 12T, 12T used, 74G available, 100% used.

## Scope

Export requested 20-sample plus earlier Set1/Set2 analysis roots with `dyec export`.
Use explicit DRA delete-on-detach mode added locally as `--delete-data-in-file-system`.
Do not use raw `rm -rf`; data deletion must occur only after a successful export task through the CLI DRA detach path.

## CLI Patch Evidence

- `dyec export --help` exposes `--delete-data-in-file-system`.
- `dyec exports detach --help` exposes `--delete-data-in-file-system`.
- Focused tests: `python -m pytest -q tests/test_export.py tests/test_export_data_behavioral_coverage.py tests/test_cli_registry_v2.py::test_export_command_passes_workflow_options` -> 16 passed.

## Export Rows

| ID | Analysis root | Size | S3 destination | Status | Evidence |
|---|---:|---:|---|---|---|
| EXP-20 | `/fsx/analysis_results/ifx-p2-1000-120-0715/bjuiceprevalanalysis-complete` | 5.9T | `s3://lsmc-ssf-sequencing-data/derived/mike_k/fsx_exports/ifx-p2-1000-120-0715/bjuiceprevalanalysis-complete/` | IN_PROGRESS | Initial start blocked by stale overlapping DRA `dra-0ece96cd32b97edba`; detaching stale DRA without delete, then retrying intended CLI export with delete flag. |
| EXP-SET1-PKG | `/fsx/analysis_results/ifx-p2-1000-120-0715/set1-inflection-pkg-19a3220-20260717` | 161G | `s3://lsmc-ssf-sequencing-data/derived/mike_k/fsx_exports/ifx-p2-1000-120-0715/set1-inflection-pkg-19a3220-20260717/` | OPEN | Pending. |
| EXP-SET1-FULLCOV | `/fsx/analysis_results/ifx-p2-1000-120-0715/inflection-batch1-fullcov-18296a2-20260717` | 634M | `s3://lsmc-ssf-sequencing-data/derived/mike_k/fsx_exports/ifx-p2-1000-120-0715/inflection-batch1-fullcov-18296a2-20260717/` | OPEN | Pending. |
| EXP-SET2 | `/fsx/analysis_results/ifx-p2-1000-120-0715/second-half-preval` | 782G | `s3://lsmc-ssf-sequencing-data/derived/mike_k/fsx_exports/ifx-p2-1000-120-0715/second-half-preval/` | SUCCESS | `fsx_export.yaml`: status success, task `task-0c6c719faad4c6fbd`, DRA `dra-01c4244792e16b808`, `delete_data_in_file_system: true`, detach lifecycle DELETED. S3: 23,195 objects / 838,628,955,670 bytes. FSx source absent; `/fsx` free 856G. |
| EXP-SET2-EARLY | `/fsx/analysis_results/ifx-p2-1000-120-0715/second-half-bjuice-preval` | 624M | `s3://lsmc-ssf-sequencing-data/derived/mike_k/fsx_exports/ifx-p2-1000-120-0715/second-half-bjuice-preval/` | OPEN | Pending. |

## Acceptance

- Each row has a `fsx_export.yaml` receipt.
- Receipt status is `success`.
- Receipt records `delete_data_in_file_system: true`.
- Source root is absent or demonstrably reduced by the DRA delete-on-detach operation.
- S3 destination contains exported objects.
