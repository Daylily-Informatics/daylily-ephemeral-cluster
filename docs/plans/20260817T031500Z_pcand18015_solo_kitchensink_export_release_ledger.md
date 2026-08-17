# pcand-18015 solo kitchensink export and catalog-evidence release ledger

Controlling request: Export the completed `pcand-18015` solo slim-data `hg38` ILMN, ONT, and ULTIMA kitchensink analysis roots from FSx to S3; record their exact S3 prefixes as DYEC command-catalog confirmation evidence; release the updated DYEC catalog; then notify Mike K and John M in Slack.

## Gate 0 — inventory and execution boundary

- Release worktree: `codex/dyec-18019-pcand18015-solo-evidence` from `origin/main` at `6516e106`; clean before this work.
- Execution provenance: all controllers used DYEC `18.0.18` commit `7f6f8ea82b2bd6a7fb1efae20870949b29b13887`, DayOA `15.0.10` commit `3a501d3f927a9573dc52adb978af31b5b64c85f3`, cluster `pcand-18015`, region `us-west-2`, and active cost center `pcand-18015-ccenter`.
- Each live controller was terminal `rc=0` before export: ILMN `155/155`, ONT `126/126`, ULTIMA `134/134`.
- The configured DYEC export root is `s3://lsmc-ssf-sequencing-data/derived/`; each exact destination below is a distinct empty child prefix.
- Every analysis root received a DYEC `analysis visit --mode export` before export. Exports use `dyec export --wait --timeout-seconds 5400` with `delete_data_in_file_system=false`; no cleanup is in scope.

## Control rows

| ID | Area | Requirement | Status | Category | Approval Gate | Evidence | Terminal note |
|---|---|---|---|---|---|---|---|
| EXP-001 | ILMN no-delete DRA export | Export completed ILMN root and retain FSx source. | SUCCESS | contract_test | Gate 4 | `task-0cba5482e91a16c8a` `SUCCEEDED`; `dra-044cb9ffb45f00362` detached; receipt `exports/ilmn/fsx_export.yaml`; destination `s3://lsmc-ssf-sequencing-data/derived/pcand-18015/pcand18015_ilmn_solo_slim_1510_ccenter_20260817t020600z_live/`; final MultiQC HTML verified at 8,548,561 bytes. | FSx retained. |
| EXP-002 | ONT no-delete DRA export | Export completed ONT root and retain FSx source. | SUCCESS | contract_test | Gate 4 | `task-002eacd7a1405af78` `SUCCEEDED`; `dra-03db1877decce2e50` detached; receipt `exports/ont/fsx_export.yaml`; destination `s3://lsmc-ssf-sequencing-data/derived/pcand-18015/pcand18015_ont_solo_slim_1510_ccenter_20260817t020900z_live/`; final MultiQC HTML verified at 6,941,320 bytes. | FSx retained. |
| EXP-003 | ULTIMA no-delete DRA export | Export completed ULTIMA root and retain FSx source. | SUCCESS | contract_test | Gate 4 | `task-03aef1ba4e80efa95` `SUCCEEDED`; `dra-08d22e4432145f447` detached; receipt `exports/ultima/fsx_export.yaml`; destination `s3://lsmc-ssf-sequencing-data/derived/pcand-18015/pcand18015_ultima_solo_slim_1510_ccenter_20260817t021200z_live/`; final MultiQC HTML verified at 7,642,590 bytes. | FSx retained. |
| CAT-001 | Catalog evidence | Record exact exported ILMN/ONT/ULTIMA prefixes and receipt-backed validation runs in the source and packaged current catalog. | SUCCESS | feature_implementation | Gate 5 | `config/daylily_pipeline_command_catalog.yaml` and packaged mirror contain matching prefixes and validation run receipts. | Evidence describes the actual `18.0.18`/`15.0.10` execution rather than a future release. |
| REL-001 | DYEC release | Commit, push, merge, tag, and publish the resulting DYEC release. | SUCCESS | feature_implementation | Gate 5 | Commit `16058ace9b7df7793ddcf95eaa83ae1aa3c89b66` merged through [PR #123](https://github.com/lsmc-bio/daylily-ephemeral-cluster/pull/123) as `5d0d8d0a2f08c609ec4b21e140eb6f5439cff408`; annotated tag `18.0.19` is pushed and dereferences to that exact merge commit. | Tagged release complete; the follow-on ledger closeout does not move the tag. |
| COMMS-001 | Slack handoff | Send final state to Mike K and John M. | SUCCESS | feature_implementation | Gate 5 | Delivered in the Mike K + John M DM: [Slack message](https://lsmchq.slack.com/archives/D0AQK8RB3D5/p1786938603101139). | Includes rc=0 completion, exact S3 roots, no-delete preservation, PR, and tag. |

## Current-state report

- All six control rows are terminal `SUCCESS`; no FSx data was deleted.
- Catalog evidence, receipts, and the source/package catalog mirror are merged on `main` in release `18.0.19`.
- Final Slack handoff is delivered. The requested objective is complete.
