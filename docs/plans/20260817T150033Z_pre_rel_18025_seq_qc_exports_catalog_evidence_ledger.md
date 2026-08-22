# pre-rel-18025 sequencing-QC export and catalog-evidence follow-up

Created: 2026-08-17T15:00:33Z

## Objective and boundary

After each of the three rerun sequencing-QC controllers reaches attributable
terminal `rc=0`, export its complete FSx analysis root through DYEC's supported
FSx DRA export path to an explicit S3 prefix, verify the immutable export
receipt and expected QC evidence, and update the three current DYEC command
catalog records with the resulting evidence S3 URI prefixes.

The target scope is AWS profile `lsmc`, region `us-west-2`, cluster/project
`pre-rel-18025`, active cost center `pre-rel-18025-ccenter`, and remote user
`ubuntu`. The source roots are:

- ILMN: `/fsx/analysis_results/pre-rel-18025/prerel18025_ilm_seq_qc_18026_15015_20260817T1427Z`
- ONT: `/fsx/analysis_results/pre-rel-18025/prerel18025_ont_seq_qc_18026_15015_20260817T1427Z`
- Ultima: `/fsx/analysis_results/pre-rel-18025/prerel18025_ultima_seq_qc_18026_15015_20260817T1427Z`

No export, S3 write, catalog-source edit, or FSx deletion has occurred in this
follow-up. `dyec export --delete-data-in-file-system` would delete each entire
source root after a successful DRA export. That irreversible cleanup requires
a separate explicit confirmation naming these exact roots, after the user has
been told the effect. The S3 destination prefixes are also not yet specified,
so no prefix is inferred.

## Gate 0 baseline

- Controlling launch ledger:
  `docs/plans/20260817T142701Z_pre_rel_18025_seq_qc_rerun_18026_15015_ledger.md`.
- Activated local CLI: DYEC `18.0.26`; all rerun controllers use explicit
  DayOA tag `15.0.15`.
- Current status at 2026-08-17T15:00Z: all three live controllers are
  attributable and `RUNNING`; none has terminal `rc=0` yet. Submitted Slurm
  work is ILMN `20`, ONT `21` and `22`, and Ultima `23`, presently
  `CONFIGURING`.
- `dyec export` supports an immutable receipt and optional
  `--delete-data-in-file-system`; its required destination S3 URI and output
  receipt directory must be explicit.
- `dyec catalog` exposes no mutable update subcommand. The source catalog
  records use `validation_evidence_s3_uri_prefix` in
  `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`;
  the precise active records must be verified before any later source edit.

| ID | Area | Requirement | Status | Approval gate | Evidence / terminal note |
|---|---|---|---|---|---|
| G0-001 | Baseline | Record active live sessions, exact source roots, export mechanism, and catalog mechanism. | SUCCESS | Gate 0 | Baseline above. |
| DEST-001 | Destination | Obtain explicit S3 prefix for each analysis-root export. | BLOCKED | User input | No S3 prefixes were supplied; no default is inferred. |
| DEL-001 | Cleanup | Obtain second explicit approval to delete the three exact FSx roots only after each matching export receipt succeeds. | BLOCKED | Destructive approval | Initial cleanup request is not the required second approval. |
| EXP-ILMN | Export | Wait for terminal ILMN `rc=0`, export/verify it, then clean up only if DEL-001 is approved. | BLOCKED | Gates DEST-001, DEL-001 | Current-DYEC ILMN rerun is terminal `rc=0`, but no destination was supplied and no export task exists. |
| EXP-ONT | Export | Wait for terminal ONT `rc=0`, export/verify it, then clean up only if DEL-001 is approved. | BLOCKED | Gates DEST-001, DEL-001 | Current-DYEC ONT rerun is terminal `rc=0`, but no destination was supplied and no export task exists. |
| EXP-ULT | Export | Wait for terminal Ultima `rc=0`, export/verify it, then clean up only if DEL-001 is approved. | BLOCKED | Gates DEST-001, DEL-001 | Current-DYEC Ultima rerun is terminal `rc=0`, but no destination was supplied and no export task exists. |
| CAT-001 | Catalog evidence | Update the three exact active catalog evidence prefixes only after verified S3 receipts exist. | BLOCKED | Gates EXP-* | No evidence S3 URI exists, so no catalog source edit is authorized. |
| FIN-001 | Acceptance | Record per-lane export receipts, evidence URIs, cleanup results, and catalog update evidence. | BLOCKED | All gates | Pending explicit destinations and a separate destructive-cleanup confirmation. |

## Export audit: `2026-08-17T17:44:14Z`

- The current-DYEC rerun sessions for ILMN, ONT, and Ultima are each terminal
  `SUCCEEDED` with attributable `exit_code=0` and no failure markers.
- The original DayOA `15.0.14` QC live sessions are also terminal `rc=0`, as
  are the three Solo slim-data results (ILMN, ONT, Ultima).
- Required read visits were recorded for the nine completed in-scope analysis
  checkouts before inspection.
- Read-only AWS evidence from
  `aws --profile lsmc --region us-west-2 fsx describe-data-repository-tasks
  --filters Name=file-system-id,Values=fs-0b1dadc673c44817f` filtered to
  `EXPORT_TO_REPOSITORY` returned `[]`. Therefore this FSx filesystem has no
  export task for any of those result roots; no S3 write, DRA export receipt,
  catalog evidence URI, or FSx cleanup occurred.

- Rechecked at `2026-08-17T18:54:44Z`: the same exact read-only FSx task query
  again returned `[]`; no export began while the BJUICE workflow remains live.

- Rechecked at `2026-08-17T20:56:07Z` after BJUICE became terminal `rc=0`:
  the same query still returned `[]`. The completed HIOMR2 and BJUICE roots are
  present on FSx. No catalog evidence URI has been added.

## Current status counts

- SUCCESS: 1
- OPEN: 0
- BLOCKED: 7
- IN_PROGRESS: 0
- FAIL: 0
