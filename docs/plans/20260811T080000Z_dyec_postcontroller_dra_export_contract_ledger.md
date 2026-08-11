# DYEC post-controller DRA export contract ledger

Controlling request: make ONT use the same separate DYEC DRA export contract as successful ILMN and Ultima exports, and remove catalog guidance that advertises controller-embedded export.

## Gate 0 baseline

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch `codex/seqqc-16.1.66-retry`; pre-existing dirty/untracked work is preserved.
- Sweep: `rg -n -i 'export_trigger|export_destination_s3_uri|automatic_launch_options|dyec export' daylily_ec tests config docs README.md`.
- Live evidence: ILMN and Ultima receipts show standalone DYEC DRA exports of `/analysis_results/ubuntu/<analysis-id>/`, followed by successful task completion and no-delete detach. ONT automatic export entered `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`, wrote an S3 visit, and supplied nested `$clone_root` to `dyec export`, which is not a valid export source.
- Live limit: active ONT recovery DRA `dra-0126a4d61163319f8` is not cancelled or detached by this source-contract work.

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| EXP-001 | DYEC controller | Do not execute export from the DayOA controller process. | SUCCESS | active_product_contract | Gate 3 | Codex | `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` no longer emits an export visit, `dyec export`, or export cleanup block. | Export lifecycle had been coupled to the workflow controller. | Workflow script now records only DayOA controller state; DYEC export is a separate operation. |
| EXP-002 | DYEC command catalog | Remove automatic-export guidance; retain explicit DYEC post-controller visit/DRA receipt instructions. | SUCCESS | active_product_contract | Gate 3 | Codex | Source and packaged command catalogs now expose `post_controller_protocol`, explicit DYEC visit/export commands, and matching active operator docs. | Catalog advertised the incorrect controller-embedded protocol. | No command-specific catalog row carries export ownership; all inherit the corrected shared result-export contract. |
| EXP-003 | DYEC tests | Add regression checks that reject controller-embedded automatic export and retain correct root-level DRA instructions. | SUCCESS | contract_test | Gate 1 | Codex | `pytest -q tests/test_repository_catalog.py tests/test_cli_registry_v2.py tests/test_script_entrypoints.py` -> `284 passed`; source/payload catalog byte parity passed. | Existing tests codified the incorrect boundary. | Regression suite rejects embedded launch export and verifies controller script contains no export block. |
| EXP-004 | ONT recovery | Keep current no-delete ONT DRA recovery separate from DayOA and verify its terminal receipt. | SUCCESS | feature_implementation | Gate 1 | Codex | Receipt `/home/ubuntu/daylily-runs/prodcand_ont_seqqc_13422_r3/export-retry-20260811-root2/fsx_export.yaml`: task `task-0f786441dbda1fc49` `SUCCEEDED`, `detached: true`, `delete_data_in_file_system: false`. S3 head checks passed for `multiqc_report.html` (2,845,207 bytes) and `ont_demux_fastq.multiqc.html` (3,406,587 bytes). | Previous automatic path lacked required role configuration and passed a nested source path. | ONT now has the same post-controller, no-delete DRA receipt contract as ILMN and Ultima. |

## Final report

All rows terminal: yes
Objective complete: yes

Status counts:
- SUCCESS: 4
