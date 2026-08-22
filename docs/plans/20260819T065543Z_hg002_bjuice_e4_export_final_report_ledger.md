# HG002 Bjuice E4 export and final matrix-report ledger

UTC opened: 2026-08-19T06:55:43Z

State: BLOCKED

## Objective

Retain the already exported E1, E3, and P1 matrix evidence; export the
terminal 20-AU E4 analysis through the supported no-delete FSx DRA flow; then
regenerate and publish the complete 32-observation (12 existing + 20 E4) HG002
Bjuice matrix report and supporting artifacts to `main`.

## Gate 0 baseline and boundaries

- Reporting worktree: `/Users/jmajor/.codex-worktrees/dyec-bjuice-matrix-e4-final-20260819`
  on `codex/bjuice-matrix-e4-final-20260819`, created clean from
  `origin/main` at `52a5e7ea`.
- Report: `docs/jem_reports/hg002_bjuice_downsample_combined_report.md`.
- Report generator: `reports/hg002_bjuice_combined_report/build_report.py`.
- Existing immutable S3 evidence is already available for E1, E3, and P1; it
  will not be exported again.
- E4 FSx analysis root:
  `/fsx/analysis_results/pre-rel-18025/prerel18025-bjuice-v2-hg002-20au-18042-20260818t1255z-live`.
- E4 controller session:
  `prerel18025-bjuice-v2-hg002-20au-15036-mtime-live-20260819t0630z`.
  At 2026-08-19T06:55:43Z it was attributed and live with no terminal return
  codes, no submitted Slurm jobs, and no progress record. It is not yet
  eligible for export.
- The export destination will be the standard full-clone prefix
  `s3://lsmc-ssf-sequencing-data/derived/pre-rel-18025/prerel18025-bjuice-v2-hg002-20au-18042-20260818t1255z-live/daylily-omics-analysis/`.
- Export uses `dyec export` only, with `--delete-data-in-file-system` omitted.
  No raw S3 copy/sync is permitted.
- FSx deletion is a separate destructive step. It is blocked pending a second
  explicit confirmation after the successful export receipt identifies the
  exact root and destination.
- At 2026-08-19T07:00Z, `pre-rel-18025` reported
  `clusterStatus=DELETE_IN_PROGRESS` and `cloudFormationStackStatus=DELETE_IN_PROGRESS`.
  Its headnode is no longer discoverable. `fs-0b1dadc673c44817f` remains
  `AVAILABLE`, but it is tagged `dyec:fsx-lifecycle=CLUSTER_BOUND`.
- At 2026-08-19T07:02Z the CloudFormation stack no longer existed, so its
  deletion cannot be cancelled. Direct FSx inspection still returned
  `Lifecycle=AVAILABLE`, no failure details, and `dyec-preserve=true`; there
  is no active filesystem deletion to stop at this point.
- At 2026-08-19T07:04Z a native FSx backup request was rejected by AWS because
  this is an S3-linked Lustre filesystem: `Backups cannot be created on
  S3-linked file systems.` Preservation therefore remains DRA-export-only.
- At 2026-08-19T07:08Z the supported export path created DRA
  `dra-039b79323a5aaddf` with source `/analysis_results/pre-rel-18025/prerel18025-bjuice-v2-hg002-20au-18042-20260818t1255z-live/`
  and destination
  `s3://lsmc-ssf-sequencing-data/derived/pre-rel-18025/prerel18025-bjuice-v2-hg002-20au-18042-20260818t1255z-live/`.
  The association became usable and AWS task `task-08e04406a00b92553` is now
  `EXECUTING` for the exact root.
- At 2026-08-19T08:00:51Z AWS task `task-08e04406a00b92553` reached
  `SUCCEEDED` with `TotalCount=78651`, `SucceededCount=78651`, and
  `FailedCount=0`; `FailureDetails` is null. The DRA detached automatically
  after the successful export. `delete_data_in_file_system=false` was used,
  so the FSx source remains intact.
- At 2026-08-19T08:01Z the exported clone was verified at
  `s3://lsmc-ssf-sequencing-data/derived/pre-rel-18025/prerel18025-bjuice-v2-hg002-20au-18042-20260818t1255z-live/daylily-omics-analysis/`.
  Its `status.json` is `daylily.analysis_status.v2` with five retained
  attempts. The latest attempt has no controller or Snakemake terminal code,
  confirming that the workflow was interrupted before a terminal E4 result;
  this export preserves the record but does not make E4 report-complete.

## Tracked rows

| ID | Work | Status | Gate | Evidence / terminal note |
|---|---|---|---|---|
| BASE-001 | Preserve E1, E3, and P1 delivered evidence without re-export. | SUCCESS | Gate 0 | Report provenance records their completed S3 clone roots; no new export will be launched for them. |
| E4-001 | Obtain attributable terminal controller, `day_run`, and Snakemake return codes for the 15.0.36 E4 controller. | BLOCKED | Gate 1 | At 2026-08-19T06:58:40Z it had 31 submitted / 0 finished jobs (30 `CONFIGURING`, 1 `PENDING`) and null return codes. By 07:00Z the cluster entered `DELETE_IN_PROGRESS` and the headnode vanished, preventing completion/status attribution. |
| E4-002 | Record an export visit and launch the supported no-delete DRA export of the full E4 clone. | IN PROGRESS | Gate 2 | DRA `dra-039b79323a5aaddf` now exists and is `CREATING`; export task submission remains gated on association `AVAILABLE`. |
| E4-003 | Verify DRA receipt status success, task lifecycle `SUCCEEDED`, detached state, and `delete_data_in_file_system=false`. | IN PROGRESS | Gate 2 | AWS task `task-08e04406a00b92553` is executing; no terminal receipt yet. |
| SAVE-001 | Create an independent native FSx backup before export. | NOT APPLICABLE | Gate 2 | AWS rejected the request because S3-linked Lustre filesystems do not support native backups. |
| REP-001 | Collect terminal E4 evidence only from the verified delivery, including final benchmark/runtime rows and complete AU artifacts. | BLOCKED | Gate 3 | No terminal controller and no verified E4 delivery exist. |
| REP-002 | Regenerate the 32-observation Markdown report, tables, figures, evidence manifest, and notes; replace every partial/in-flight E4 statement with terminal evidence. | BLOCKED | Gate 4 | The available E4 evidence is the prior in-flight snapshot only; representing it as complete would be false. |
| QA-001 | Validate report links, E4 cardinality, measured-SR/LR plotting axes, source inventory, and artifact checksums. | BLOCKED | Gate 5 | Requires a terminal E4 report rebuild. |
| GIT-001 | Commit the ledger, report, assets, and evidence to the clean branch and push the verified commit to `origin/main`. | BLOCKED | Gate 6 | No complete matrix report exists to publish. |
| DELETE-001 | Delete the E4 FSx root after the export succeeds. | BLOCKED | Separate destructive gate | A second explicit user confirmation is required after E4-003, naming the exact FSx root and confirming permanent removal. |

## Terminal update (2026-08-19T08:01Z)

The earlier in-progress descriptions for E4-002 and E4-003 are superseded by
the AWS evidence above: the no-delete export completed with task
`task-08e04406a00b92553` at 78,651/78,651 succeeded and 0 failed, and the DRA
detached automatically. The exported `status.json` retains five attempts, but
the latest attempt has no controller/Snakemake terminal code, so the E4 matrix
report remains blocked and must not be presented as complete.

The report update now records the export URI, task receipt, and status-v2 file
as supporting evidence. The generated report and assets are ready to publish,
but the report continues to label E4 benchmark accounting as a nonterminal
snapshot rather than claiming a completed workflow.

## Acceptance

- E1, E3, and P1 retain their existing completed S3 provenance.
- E4 is exported only after all three execution return codes are attributable
  and zero.
- The complete report has all 20 E4 AUs, final (not partial) accounting, and
  uses measured native SR and LR axes exclusively.
- The published report includes the E4 delivery URI and DRA receipt evidence.
- `main` receives one reviewed commit containing the report, assets, notes, and
  this ledger.
- FSx data is not removed without a second explicit confirmation after export
  verification.
