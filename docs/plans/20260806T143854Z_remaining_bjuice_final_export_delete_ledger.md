# Remaining-BJuice final DRA export and delete-on-success ledger

Created: 2026-08-06T14:38:54Z
Human requestor: John Major
Cluster: `preval-hiomr2` (`lsmc`, `us-west-2`)
Source: `/fsx/analysis_results/preval-hiomr2/remaining-bjuice-1345`
Destination: `s3://lsmc-ssf-sequencing-data/derived/remaining-bjuice-1345-final-delete-20260806T143854Z/preval-hiomr2/remaining-bjuice-1345/`
Status: terminal incident; export failed, unsafe detach deleted FSx source, data coverage reconciled across preserved S3 exports, and code repair tested

## Approval and safety boundary

- First destructive request: 2026-08-06, delete the root if fully exported.
- The agent reported that the previous full-root export predated 275 files and
  56,502,900 bytes outside the separately exported SeqOne-v2 package.
- Second explicit approval: 2026-08-06, re-export this exact root using DRA
  delete-on-success semantics.
- Deletion is limited to the exact source path above. S3 deletion is forbidden.
- FSx deletion is permitted only after the new export task reaches `SUCCEEDED`.

## Gate 0 baseline

- The source exists, is owned by `ubuntu:ubuntu`, and has apparent size
  4,382,348,331,409 bytes.
- No matching controller process, Slurm job, or analysis-root write lock was
  observed immediately before authorization.
- Prior exports remain preserved and are not destinations for this operation.
- DYEC's explicit `export` command supports
  `--delete-data-in-file-system`; its implementation performs deletion only
  while detaching after a successful export task and writes an immutable
  `fsx_export.yaml` receipt.

## Control ledger

| ID | Requirement | Status | Category | Gate | Evidence / terminal note |
|---|---|---|---|---|---|
| RBD-001 | Verify exact source, inactivity, lock state, current size, and second approval | SUCCESS | legitimate_safety_handling | Gate 0 | Exact root and 4,382,348,331,409-byte baseline verified; no controller, matching Slurm job, or write lock; second approval recorded. |
| RBD-002 | Verify the fresh S3 destination is empty | SUCCESS | legitimate_safety_handling | Gate 0 | Authoritative `list-objects-v2` returned no contents for the exact new prefix before DRA creation. |
| RBD-003 | Record export visit and acquire the analysis-root write lock normally | SUCCESS | legitimate_safety_handling | Gate 0 | Export visit recorded with the exact S3 URI; root was unlocked and `codex-remaining-bjuice-final-export-delete-20260806` acquired the write lock normally. |
| RBD-004 | Run the exact DRA export with delete-on-success and wait through its terminal boundary | FAIL | feature_implementation | Gate 5 | Guarded command started at 2026-08-06T14:41:26Z in one-pane tmux `remaining_bjuice_1345_final_export_delete_20260806`. Task `task-087f0a4c3e4b5f010` failed with 1,078 succeeded and 2,878 failed files. This row moved through `ATTEMPTING_BUGFIX` during the failure audit and code repair; the source no longer exists for a live retry. |
| RBD-005 | Require task `SUCCEEDED`, zero failed files, detached DRA, and `delete_data_in_file_system: true` receipt | FAIL | contract_test | Gate 5 | The task was `FAILED`, not `SUCCEEDED`. DYEC nevertheless detached DRA `dra-094192bdac9b58697` with `DeleteDataInFileSystem=true`; receipt status is `error`, phase `detach`, RC 1. Root cause: `run_export_workflow` forwarded the requested delete flag unconditionally from its `finally` block instead of gating it on task success. |
| RBD-006 | Verify the FSx source is absent and S3 objects remain present | SUCCESS | contract_test | Gate 5 | The exact FSx root is absent. Original full export remains 42,641 objects / 4,209,560,050,285 bytes; separate SeqOne-v2 package remains 3,630 objects / 232,120,467,710 bytes; fresh partial prefix contains 1,080 objects / 57,298,713 bytes. All 2,878 failed paths are covered by the union: 2,847 are in the separately reconciled package, and the 31 remaining paths are in the original full export; uncovered path count is zero. |
| RBD-007 | Release the analysis-root lock and preserve the ledger/receipt | SUCCESS | legitimate_safety_handling | Gate 5 | The lock directory was removed with the exact source root, so no live lock remains to release. The immutable failure report remains at the task report S3 URI; the exact receipt is preserved beside this ledger. |
| RBD-008 | Repair DYEC so a failed export can never request FSx deletion during detach | SUCCESS | legitimate_safety_handling | Gate 5 | `run_export_workflow` now computes deletion from both the requested flag and proven `rc == 0` / `task_lifecycle == SUCCEEDED`. Regression test asserts a failed task detaches with `DeleteDataInFileSystem=false`; focused suite passes 19 tests. |

## Terminal incident evidence

- Failed task: `task-087f0a4c3e4b5f010`, lifecycle `FAILED`, total 3,956,
  succeeded 1,078, failed 2,878.
- Failed DRA: `dra-094192bdac9b58697`; it reached `DELETED` and the exact
  FSx source is absent.
- Fresh partial prefix:
  `s3://lsmc-ssf-sequencing-data/derived/remaining-bjuice-1345-final-delete-20260806T143854Z/preval-hiomr2/remaining-bjuice-1345/`.
- Failure report:
  `s3://lsmc-ssf-sequencing-data/derived/remaining-bjuice-1345-final-delete-20260806T143854Z/preval-hiomr2/remaining-bjuice-1345/_daylily_monitor/fsx-export/20260806T144358Z/export-report/task-087f0a4c3e4b5f010/failures.csv`.
- Original full-root preservation:
  `s3://lsmc-ssf-sequencing-data/derived/remaining-bjuice-1345-final-20260805T184259Z/preval-hiomr2/remaining-bjuice-1345/`.
- Separate SeqOne-v2 package preservation:
  `s3://lsmc-ssf-sequencing-data/derived/remaining-bjuice-1345-seqone-v2-prejasmine-20260806T015946Z/preval-hiomr2/remaining-bjuice-1345-seqone-v2-prejasmine-export-20260806T015946Z/remaining-bjuice-1345-seqone-v2-prejasmine-20260805/`.
- Coverage audit: all 2,878 failed relative paths exist in at least one of the
  original full-root, separate package, or fresh partial prefixes; zero paths
  are uncovered.
- The requested single-prefix successful export was not achieved. Data remains
  recoverable only from the explicit union above; no synthetic fallback copy
  was created.
