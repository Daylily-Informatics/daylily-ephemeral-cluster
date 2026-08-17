# pre-rel-18025 Bjuice-preval DRA mounts and sequencing-QC ledger

Created: 2026-08-17T11:59:33Z

## Objective and execution boundary

Create three read-only run-directory DRAs on the newly created `pre-rel-18025`
cluster in `us-west-2` for the Bjuice-preval Illumina run, the canonical
Bjuice-preval ONT parent (all 15 reviewed child directories), and one recent
complete Ultima run. Submit the three creates concurrently. As each association
becomes `AVAILABLE` and headnode-verifiable, run the corresponding supported
catalog dry controller and then a distinct live sequencing-QC controller only
after the dry receipt proves `rc=0` and zero Slurm submissions.

The user explicitly authorized one 15-minute heartbeat monitor once all three
associations are `CREATING`. It stops after every lane has reached a terminal
mount/QC-launch outcome or at six hours, when continuation must be reconfirmed.

No auto-export, writeback, BCL Convert, ONT/Ultima basecalling, source mutation,
Slurm intervention, DRA deletion, export, FSx cleanup, or budget mutation is in
scope.

## Gate 0 baseline

- Target selection: `pre-rel-18025` is the newest live `us-west-2` cluster
  (`creationTime=2026-08-17T11:29:39Z`), with `UPDATE_COMPLETE`, a running
  Ubuntu headnode `i-021f1c67509abb6c3`, and a `RUNNING` compute fleet.
- Profile and runtime: `lsmc`; activated local DYEC is `18.0.25`. The target
  cost center `pre-rel-18025-ccenter` is active, allows `ubuntu`, and has a
  USD 1100 monthly cap. This task does not alter it.
- Headnode baseline: no Slurm jobs, no live DayOA controllers, no tmux panes;
  `/fsx` is mounted and has 12,016,302,080 KiB free.
- FSx: `fs-0b1dadc673c44817f`, `LUSTRE`, `AVAILABLE`, 12,000 GiB. Its only
  pre-existing DRA is the non-overlapping `/references/` association
  `dra-008ba0f9c70294220`; three requested run associations will leave four
  total, below the eight-association limit.
- Exact source scope, all live-probed before create:
  - ILMN: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/`;
    `RunInfo.xml` and `SampleSheet.csv` are present.
  - ONT parent: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/`;
    it has exactly 15 reviewed `20260615_ONT_Set{1..5}-FC{1..3}` Bjuice-preval
    children. The explicit QC context uses `20260615_ONT_Set4-FC1`; it is not
    discovered dynamically at launch.
  - Ultima: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/RUN604834/2026/604834-20260717_2309/`;
    `UploadCompleted.json`, the LibraryInfo XML, and SequencingInfo JSON are
    present. This is the recent complete source selected for the one Ultima lane.
- Catalog contract: `illumina_run_qc`, `ont_run_qc`, and `ultima_run_qc` all
  require mounted `run_context` input and explicitly pin DayOA `15.0.14`.
  Their targets are respectively `produce_illumina_run_qc`,
  `produce_ont_run_qc_and_demux_multiqc`, and `produce_ultima_run_qc`.
- Existing dirty/untracked paths are user-owned and untouched. This ledger and
  its sibling context files are task-owned.

| ID | Area | Requirement | Status | Approval gate | Evidence / terminal note |
|---|---|---|---|---|---|
| G0-001 | Scope | Record target, source scope, capacity, command contract, and safety boundaries. | SUCCESS | Gate 0 | Baseline above; no live mutation occurred before this ledger. |
| CTX-001 | Run contexts | Persist exact non-discovered ILMN/ONT/Ultima run-context TSVs. | SUCCESS | Gate 0 | Three sibling TSV files, each with the required 11 run-context columns. |
| MNT-ILMN | DRA | Create and verify the Bjuice-preval Illumina source read-only. | SUCCESS | Gate 1 | `dra-0cf840190ff9a46f1` is `AVAILABLE`; exact `mounts verify --platform ILMN` command `303c8e47-4ced-4a6f-bc5b-273b54108127` returned `verified=true`, `usable=true`, at `/fsx/run_dir_mounts/20260618_LH01106_0011_A23MFMCLT3/`. |
| MNT-ONT | DRA | Create and verify the canonical Bjuice-preval ONT parent read-only. | SUCCESS | Gate 1 | `dra-0a150204884212f34` is `AVAILABLE`; exact `mounts verify --platform ONT` command `20d23023-62a7-44de-a700-b7435991f8eb` returned `verified=true`, `usable=true`, at `/fsx/run_dir_mounts/pca100-2026/`. The parent covers the 15 reviewed child directories. |
| MNT-ULT | DRA | Create and verify the selected recent complete Ultima source read-only. | SUCCESS | Gate 1 | `dra-03bb21b8e5a0a68af` is `AVAILABLE`; exact `mounts verify --platform ULTIMA` command `149c3b79-68f3-49bf-9437-f26862ef04ff` returned `verified=true`, `usable=true`, at `/fsx/run_dir_mounts/ultima-604834-20260717/`. |
| QC-ILMN | Catalog | Dry then live-launch catalog `illumina_run_qc` after verified mount readiness. | SUCCESS | Gate 2 | Catalog showed tag `15.0.14` and QC-only `produce_illumina_run_qc` (no BCL Convert). Dry `prerel18025_ilm_seq_qc_15014_dry_20260817T1245Z` reached attributable `rc=0` with zero submitted Slurm jobs; distinct live launch receipt/session is `prerel18025_ilm_seq_qc_15014_live_20260817T1247Z`. |
| QC-ONT | Catalog | Dry then live-launch catalog `ont_run_qc` after verified mount readiness. | SUCCESS | Gate 2 | Catalog showed tag `15.0.14` and QC-only `produce_ont_run_qc_and_demux_multiqc` (no basecalling). Dry `prerel18025_ont_seq_qc_15014_dry_20260817T1234Z` reached attributable `rc=0` with zero submitted Slurm jobs; distinct live launch receipt/session is `prerel18025_ont_seq_qc_15014_live_20260817T1241Z`. |
| QC-ULT | Catalog | Dry then live-launch catalog `ultima_run_qc` after verified mount readiness. | SUCCESS | Gate 2 | Catalog showed tag `15.0.14` and QC-only `produce_ultima_run_qc` (no basecalling). Dry `prerel18025_ultima_seq_qc_15014_dry_20260817T1305Z` reached attributable `rc=0` with zero submitted Slurm jobs; distinct live launch receipt/session is `prerel18025_ultima_seq_qc_15014_live_20260817T1308Z`. |
| MON-001 | Heartbeat | Check status every 15 minutes and launch only newly ready catalog lanes. | SUCCESS | User authorized | `monitor-pre-rel-18025-bjuice-preval-mounts-and-seq-qc` ran until all three lanes had terminal mount/QC-launch outcomes, then deletion returned `deleteStatus=deleted`. |

## Mount-submission receipt

- At `2026-08-17T12:02:48Z` / `12:02:49Z`, the three requested creates were
  accepted concurrently by DYEC. Each association is read-only, has metadata
  import enabled, has auto-import `NEW,CHANGED`, and has no auto-export events.
- The first follow-up `mounts list` at `2026-08-17T12:03:00Z` showed all three
  requested associations in `CREATING`. The authorized 15-minute heartbeat was
  therefore created with the exact three association IDs, exact run-context
  files, no-duplicate dry/live controller guard, and six-hour stop condition.
- A prior local shell parse error occurred before DYEC was invoked; it issued
  no AWS request and made no resource change.

## Heartbeat observations

- `2026-08-17T12:19:42Z`: ILMN `dra-0cf840190ff9a46f1`, ONT
  `dra-0a150204884212f34`, and Ultima `dra-03bb21b8e5a0a68af` all remain
  `CREATING`, read-only, metadata-import enabled, `NEW,CHANGED` auto-import,
  and no auto-export. This is only about 17 minutes after submission, below the
  40-minute lifecycle floor; no retry, replacement, verification, or catalog
  launch was attempted.
- `2026-08-17T12:19:54Z`: headnode controller inventory remains authoritative
  at zero controllers, zero tmux panes, and zero Slurm jobs. No duplicate
  catalog action exists.
- `2026-08-17T12:34Z` heartbeat: ILMN and Ultima remain `CREATING`; ONT is
  `AVAILABLE`. All three exact associations still show `read_only=true`,
  auto-import `NEW,CHANGED`, and no auto-export. The two creating lanes remain
  below the 40-minute lifecycle floor, so no retry or replacement was made.
- `2026-08-17T12:34Z`: exact ONT verification returned lifecycle `AVAILABLE`,
  `verified=true`, and `usable=true` for
  `/fsx/run_dir_mounts/pca100-2026/` (verification command id
  `20d23023-62a7-44de-a700-b7435991f8eb`). `catalog show ont_run_qc` then
  reconfirmed tag `15.0.14` and the QC-only
  `produce_ont_run_qc_and_demux_multiqc` target. The rendered dry command
  retains `-n`, uses only the exact ONT context TSV, and contains no basecalling.
- `2026-08-17T12:40:47Z`: supported `catalog launch --dry-run` created the
  attributable `prerel18025_ont_seq_qc_15014_dry_20260817T1234Z` controller in
  its own tmux session. `workflow status` is `RUNNING`; it has zero submitted
  or finished Slurm jobs and no terminal exit receipt yet. The distinct live
  controller is deliberately not rendered or launched until the dry controller
  reports attributable terminal `rc=0`.
- `2026-08-17T12:41Z`: ONT dry status became `SUCCEEDED` with attributable
  terminal `exit_code=0`, zero submitted/finished Slurm jobs, and no failure
  markers. After a no-duplicate inventory, the separately rendered live session
  `prerel18025_ont_seq_qc_15014_live_20260817T1241Z` was catalog-launched.
  Its receipt identifies the expected analysis root and its own tmux session;
  it uses the exact ONT context file and no basecalling.
- `2026-08-17T12:44Z`: ILMN `dra-0cf840190ff9a46f1` became `AVAILABLE` and
  exact verification returned `verified=true`, `usable=true` at the intended
  run-dir path (command id `303c8e47-4ced-4a6f-bc5b-273b54108127`).
  `catalog show illumina_run_qc` reconfirmed tag `15.0.14` and only
  `produce_illumina_run_qc`; its rendered command explicitly has no BCL Convert.
- `2026-08-17T12:46Z`: ILMN dry
  `prerel18025_ilm_seq_qc_15014_dry_20260817T1245Z` reached attributable
  terminal `exit_code=0`, zero submitted/finished Slurm jobs, and no failure
  markers. After the no-duplicate controller inventory, the distinct live
  `prerel18025_ilm_seq_qc_15014_live_20260817T1247Z` was rendered and
  catalog-launched with the exact ILMN context, tag `15.0.14`, and no BCL
  Convert.
- `2026-08-17T12:48:03Z`: Ultima `dra-03bb21b8e5a0a68af` remains `CREATING`
  (about 45 minutes after submission), still read-only with metadata import,
  auto-import `NEW,CHANGED`, and no auto-export. It is not yet eligible for
  verification or a QC launch; no retry, replacement, detach, or failure claim
  was made.
- `2026-08-17T12:49:37Z`: exact three-association readback remains unchanged:
  ILMN and ONT are `AVAILABLE`; Ultima `dra-03bb21b8e5a0a68af` is still
  `CREATING` (about 47 minutes after submission). All retain `read_only=true`,
  batch metadata import, auto-import `NEW,CHANGED`, and no auto-export. Ultima
  remains in lifecycle wait with no retry, replacement, verification, or catalog
  action.
- `2026-08-17T13:05Z`: Ultima `dra-03bb21b8e5a0a68af` became `AVAILABLE`.
  Its exact `--platform ULTIMA` verification returned `verified=true` and
  `usable=true` at `/fsx/run_dir_mounts/ultima-604834-20260717/` (command id
  `149c3b79-68f3-49bf-9437-f26862ef04ff`), retaining read-only metadata import,
  `NEW,CHANGED` auto-import, and no auto-export.
- `2026-08-17T13:05Z`: `catalog show ultima_run_qc` reconfirmed DayOA tag
  `15.0.14` and only `produce_ultima_run_qc`. The rendered dry command has
  `-n`, uses the exact Ultima context TSV, and contains no basecalling.
- `2026-08-17T13:07Z`: dry
  `prerel18025_ultima_seq_qc_15014_dry_20260817T1305Z` reached attributable
  terminal `exit_code=0`, zero submitted/finished Slurm jobs, and no failure
  markers. A no-duplicate controller inventory then preceded rendering and
  launching the distinct live
  `prerel18025_ultima_seq_qc_15014_live_20260817T1308Z` catalog session.
- `2026-08-17T13:09:16Z`: the Ultima live session is attributable and `RUNNING`
  in its expected tmux/analysis-root path, with zero submitted Slurm jobs at this
  point. This is a launch receipt, not a claim that sequencing QC has completed.
  All three requested lanes have now reached their terminal mount/QC-launch
  outcomes; heartbeat retirement follows.
- `2026-08-17T13:09Z`: the heartbeat automation
  `monitor-pre-rel-18025-bjuice-preval-mounts-and-seq-qc` was deleted after the
  three terminal mount/QC-launch outcomes; the app returned `deleteStatus=deleted`.

## Current status counts

- SUCCESS: 9
- IN_PROGRESS: 0
- OPEN: 0
- PENDING: 0
- BLOCKED: 0
- FAIL: 0
