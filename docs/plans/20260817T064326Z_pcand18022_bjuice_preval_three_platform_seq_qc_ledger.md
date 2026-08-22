# pcand-18022 Bjuice-preval input DRA and three-platform sequencing QC ledger

Created: 2026-08-17T06:43:26Z

Controlling request: attach read-only DRA mounts for the full Bjuice-preval
Illumina run and canonical ONT-parent tree, attach one recent complete Ultima
run, then run the catalog Illumina (without BCL Convert), ONT (without
basecalling), and Ultima (without basecalling) RunQC commands to terminal
`rc=0`. Notify the user when the Bjuice ILMN and ONT mounts are both ready so
the explicit prevalence test-run scope can be queued separately.

## Gate 0: inventory and baseline

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`; pre-existing
  modified and untracked worktree paths are user-owned and untouched.
- Activated CLI: `Daylily Ephemeral Cluster 18.0.22` after `source ./activate`.
- Target: `pcand-18022`, `us-west-2`, AWS profile `lsmc`, stack
  `UPDATE_COMPLETE`, compute fleet `RUNNING`, Ubuntu headnode
  `i-07c38ac3548d7f4c4`. DYEC reports zero Slurm jobs and zero managed run mounts.
  The other live cluster, `prod-cand-1703`, has 33 running jobs and already owns
  the same three input associations; it is not reused or duplicated.
- Active target cost center: `pcand-18022-ccenter`, status `active`, allowed user
  `ubuntu`, monthly cap USD 1234. This task does not change the cap or cost-center
  record.
- Exact read-only source scope:
  - ILMN: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/`.
    Read-only S3 checks confirm `RunInfo.xml` (79,277 bytes) and
    `SampleSheet.csv` (3,197 bytes).
  - ONT: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/`, mounted
    once as `pca100-2026`. The prefix contains exactly the 15 reviewed
    `20260615_ONT_Set{1..5}-FC{1..3}` child directories. The RunQC context is
    explicitly scoped to `20260615_ONT_Set4-FC1`; it is not discovered at launch.
  - Ultima: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/RUN604834/2026/604834-20260717_2309/`.
    Read-only S3 checks confirm `UploadCompleted.json`, `604834_LibraryInfo.xml`,
    and `604834_SequencingInfo.json`.
- Catalog pin: current `illumina_run_qc`, `ont_run_qc`, `ultima_run_qc`, and the
  full Bjuice v2 command all resolve to the maximum current pinned DayOA version
  `15.0.11`. Historical validation tags are evidence only and must not be used for
  this work.
- Mount contract: `dyec mounts create` only, read-only, metadata import enabled,
  auto-import `NEW,CHANGED`, no auto-export, and a 5,400-second readiness budget.
- Initial explicit exclusions: BCL Convert, ONT/Ultima basecalling, raw
  Snakemake, Slurm intervention, DRA deletion/detach, FSx/S3 cleanup or
  export, budget mutation, and automatic Bjuice test-run launch. The user later
  supplied three exact output prefixes and a second explicit authorization to
  delete only the corresponding three completed FSx analysis roots after each
  DYEC export succeeded; that limited cleanup is recorded below.
- Durable command record: `docs/runbooks/18.0.22/runbooka1.md` is the new,
  task-owned Bjuice-preval DRA-to-QC-to-conditional-export runbook authorized
  by the user at 2026-08-17T07:17:08Z. The unrelated concurrent
  `runbooka.md` remains untouched. The task-owned runbook now records the
  approved three-root export and cleanup receipts.

| ID | Area | Requirement | Status | Category | Approval gate | Evidence / terminal note |
|---|---|---|---|---|---|---|
| INV-001 | Baseline | Record target, source scope, mount capacity, catalog pin, and ownership boundary. | SUCCESS | legitimate_safety_handling | Gate 0 | The inventory above is current before any DRA mutation. |
| MNT-ILMN | DRA | Attach and verify the full Bjuice-preval ILMN source read-only. | SUCCESS | feature_implementation | Gate 1 | `dra-0cc3051c7e460429e`, FSx `fs-09eb220d064d55d92`: `AVAILABLE` and headnode-verified usable at `/fsx/run_dir_mounts/20260618_LH01106_0011_A23MFMCLT3` (verify command `ecc8eb22-db83-4d57-a9bf-fae0451e9734`). |
| MNT-ONT | DRA | Attach and verify the canonical Bjuice ONT parent read-only. | SUCCESS | feature_implementation | Gate 1 | `dra-0a739dd6aa2d433a0`, FSx `fs-09eb220d064d55d92`: `AVAILABLE` and headnode-verified usable at `/fsx/run_dir_mounts/pca100-2026` (verify command `c6118e13-5d9a-4e2f-aacd-faf570bc085e`). The single parent satisfies all 15 reviewed directories. |
| MNT-ULT | DRA | Attach and verify the recent complete Ultima source read-only. | SUCCESS | feature_implementation | Gate 1 | `dra-080f12613e5deb4e8`, FSx `fs-09eb220d064d55d92`: `AVAILABLE` and headnode-verified usable at `/fsx/run_dir_mounts/ultima-604834-20260717` (verify command `3da5b363-fb3a-4030-9feb-39e9eec9ffe6`). |
| CTX-001 | Run context | Preserve three exact, explicit catalog run-context TSVs. | SUCCESS | contract_test | Gate 0 | Contexts reside beside this ledger and use no source discovery. `dyec --json catalog render illumina_run_qc` accepted the ILMN context, explicit cluster/cost center, and explicit DayOA `15.0.11`; rendering created no analysis root or controller. |
| QC-ILMN | Catalog | Run DayOA 15.0.11 `illumina_run_qc`, excluding BCL Convert, after verified ILMN readiness. | SUCCESS | feature_implementation | Gate 2 | Catalog showed `git_tag=15.0.11` before each render/launch. Dry `pcand18022_ilmn_seq_qc_15011_dry_20260817T0709Z` terminal `rc=0`, attributable, with zero Slurm submissions. Distinct live `pcand18022_ilmn_seq_qc_15011_live_20260817T0712Z` submitted Slurm job `6` and then reached attributable terminal `rc=0` with no failure markers. |
| QC-ONT | Catalog | Run DayOA 15.0.11 `ont_run_qc`, excluding basecalling, after verified ONT readiness. | SUCCESS | feature_implementation | Gate 2 | Catalog showed `git_tag=15.0.11` before every render/launch. Explicit Set4-FC1 dry `pcand18022_ont_seq_qc_15011_dry_20260817T0750Z` terminal `rc=0` with zero Slurm submissions. Distinct live `pcand18022_ont_seq_qc_15011_live_20260817T0752Z` submitted eight Slurm jobs and then reached attributable terminal `rc=0` with no failure markers. |
| QC-ULT | Catalog | Run DayOA 15.0.11 `ultima_run_qc`, excluding basecalling, after verified Ultima readiness. | SUCCESS | feature_implementation | Gate 2 | Catalog showed `git_tag=15.0.11` before every render/launch. Dry `pcand18022_ultima_seq_qc_15011_dry_20260817T0732Z` and live `pcand18022_ultima_seq_qc_15011_live_20260817T0734Z` each reached attributable terminal `rc=0` with no failure markers. |
| ATTN-001 | Handoff | Notify the user when both full Bjuice ILMN and ONT parent mounts are verified. | SUCCESS | coordination | Gate 1 | Alerted the user at the verified ONT transition: full Bjuice ILMN + ONT input pair is ready to queue prevalence test runs; no Bjuice manifest/run was generated. |
| MON-001 | Monitoring | Run exactly one 15-minute heartbeat until all requested QC controllers are terminal or a fail-closed blocker occurs. | SUCCESS | legitimate_safety_handling | Gate 1-2 | The single heartbeat `monitor-pcand-18022-bjuice-preval-mounts-and-runqc` changed from 10 to 15 minutes at 2026-08-17T08:10:40Z under the user's explicit condition, then was deleted at 2026-08-17T08:37:18Z after all three live RunQC controllers had attributable terminal `rc=0`. |
| EXP-ILMN | Export + cleanup | Export the completed ILMN root to the user-approved URI, then delete only that root after DYEC success. | SUCCESS | feature_implementation | Second explicit delete approval | Receipt `exports/illumina/fsx_export.yaml`: DRA `dra-0eccda2383d501558`, task `task-04314e6ad167c3da3` `SUCCEEDED`, phase `complete`, detached `true`, `delete_data_in_file_system: true`; root confirmed absent. |
| EXP-ONT | Export + cleanup | Export the completed ONT root to the user-approved URI, then delete only that root after DYEC success. | SUCCESS | feature_implementation | Second explicit delete approval | Receipt `exports/ont/fsx_export.yaml`: DRA `dra-07a7629ad6d148601`, task `task-0ab635bdaf6de0351` `SUCCEEDED`, phase `complete`, detached `true`, `delete_data_in_file_system: true`; root confirmed absent. |
| EXP-ULT | Export + cleanup | Export the completed Ultima root to the user-approved URI, then delete only that root after DYEC success. | SUCCESS | feature_implementation | Second explicit delete approval | Receipt `exports/ultima/fsx_export.yaml`: DRA `dra-0392265fb9f0f8aa9`, task `task-0764f6ed0d480690c` `SUCCEEDED`, phase `complete`, detached `true`, `delete_data_in_file_system: true`; root confirmed absent. |
| CAT-EVID-001 | Catalog evidence | Record the three DayOA 15.0.11 RunQC results with their exported S3 evidence prefixes. | SUCCESS | documentation | Gate 2 + export success | Active `illumina_run_qc`, `ont_run_qc`, and `ultima_run_qc` records point to the three exported `pcand-18022` result prefixes and retain `git_tag: 15.0.12` / `validated_version: 15.0.9`; the new records are historical DayOA 15.0.11 evidence, not a claim that 15.0.12 was validated. |

## Current-state report

- All rows terminal: yes.
- Objective complete: yes for the requested read-only DRA mounts, three catalog
  RunQC controllers, three user-approved DYEC exports, and deletion of only the
  three corresponding FSx analysis roots after their individual export tasks
  reached `SUCCEEDED`. Bjuice prevalence test runs remain intentionally
  unqueued.
- Export roots: ILMN `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022_ilmn_seq_qc_15011_live_20260817T0712Z/`; ONT `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022_ont_seq_qc_15011_live_20260817T0752Z/`; Ultima `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022_ultima_seq_qc_15011_live_20260817T0734Z/`.
- The original Ultima input association `dra-080f12613e5deb4e8` is absent in
  the post-export mount list because the user states it was unmounted in a
  separate thread. This task did not recreate, detach, or otherwise modify that
  source association; the source S3 prefix was not independently re-inspected.
- No further monitor action is scheduled: the sole heartbeat was deleted when
  the final ONT controller reached attributable `rc=0`.

## Mount-submission receipt

- A first local shell parse attempt was rejected before DYEC started; it created
  no association. The corrected parallel submission then created exactly the
  three association IDs above.
- Every submitted association is read-only, has metadata import enabled,
  auto-import `NEW,CHANGED`, and has an empty auto-export event list.
- Headnode baseline is Ubuntu 22.04.5 on `ip-10-0-0-68`; it reports DYEC
  `18.0.22`, `day-clone` available, no live DayOA controllers, no tmux panes,
  and no Slurm jobs at the baseline observation.

## Heartbeat observations

- 2026-08-17T07:00:00Z: `source ./activate && dyec --json mounts list --profile
  lsmc --region us-west-2 --cluster pcand-18022` reports ILMN
  `dra-0cc3051c7e460429e`, ONT `dra-0a739dd6aa2d433a0`, and Ultima
  `dra-080f12613e5deb4e8` all `CREATING` (each DYEC `updated_at` at this
  observation). Each remains read-only with auto-import `NEW,CHANGED` and an
  empty auto-export event list. No verification, controller launch, retry,
  replacement, deletion, detach, or export was performed.
- 2026-08-17T07:08:34Z: the same mount-list command reports ILMN
  `dra-0cc3051c7e460429e` `AVAILABLE`; ONT `dra-0a739dd6aa2d433a0` and Ultima
  `dra-080f12613e5deb4e8` remain `CREATING` (all three DYEC `updated_at` values
  are 2026-08-17T07:08:34Z).
- 2026-08-17T07:08:47Z: `dyec --json mounts verify --profile lsmc --region
  us-west-2 --cluster pcand-18022 --association-id dra-0cc3051c7e460429e`
  returned `verified: true`, `usable: true`, lifecycle `AVAILABLE`, command ID
  `ecc8eb22-db83-4d57-a9bf-fae0451e9734`, and the exact headnode path
  `/fsx/run_dir_mounts/20260618_LH01106_0011_A23MFMCLT3`.
- ILMN catalog evidence: `dyec --json catalog show illumina_run_qc` reported
  `git_tag: 15.0.11` before the dry render, dry launch, live render, and live
  launch. Both renders used `--strict-project-check`, the explicit ILMN context
  TSV, remote user `ubuntu`, project `pcand-18022`, cost center
  `pcand-18022-ccenter`, and explicit `--git-tag 15.0.11`; the rendered target
  is only `produce_illumina_run_qc` / `bin/day_run produce_illumina_run_qc`, not
  BCL Convert.
- ILMN dry controller `pcand18022_ilmn_seq_qc_15011_dry_20260817T0709Z`:
  `dyec --json workflow status` reports terminal `SUCCEEDED`, attributable
  `exit_code: 0`, zero submitted/finished Slurm jobs, no failure markers, and
  exact Snakemake log
  `.snakemake/log/2026-08-17T071131.047721.snakemake.log` under its isolated
  analysis root.
- ILMN live controller `pcand18022_ilmn_seq_qc_15011_live_20260817T0712Z`:
  `dyec --json workflow status` reports `RUNNING`, attributable controller PID
  `103156`, tmux correlation, expected/observed immutable DayOA checkout
  `/fsx/analysis_results/pcand-18022/pcand18022_ilmn_seq_qc_15011_live_20260817T0712Z/daylily-omics-analysis`, no submitted Slurm jobs yet, and no terminal
  failure marker. No direct Slurm or remote workflow action was performed.
- 2026-08-17T07:19:36Z: mount list remains ILMN `AVAILABLE`; ONT
  `dra-0a739dd6aa2d433a0` and Ultima `dra-080f12613e5deb4e8` remain
  `CREATING`. All three remain read-only with auto-import `NEW,CHANGED` and no
  auto-export event.
- 2026-08-17T07:19:36Z: ILMN live workflow status remains attributable and
  tmux-correlated (`PID 103156`), state `RUNNING`, with zero submitted/finished
  Slurm jobs, no attributable terminal exit code, and no failure markers.
- 2026-08-17T07:22:17Z: repeat `dyec --json workflow status` for the ILMN live
  session still reports an attributable/tmux-correlated live controller (`PID
  103156`) and state `RUNNING`, but `submitted_count: 0`, no exact attributable
  Snakemake log, no progress line, and no terminal error or failure marker. A
  `dyec workflow logs --stream controller --lines 80` observation returned no
  controller content. This is recorded as controller-startup state only; no
  Slurm, controller, DRA, or retry action was taken.
- 2026-08-17T07:25:31Z: exact mount list remains ILMN `AVAILABLE`; ONT
  `dra-0a739dd6aa2d433a0` and Ultima `dra-080f12613e5deb4e8` remain
  `CREATING`. The ILMN live status remains attributable/tmux-correlated and
  `RUNNING` with zero submitted/finished Slurm jobs, no progress or exact
  Snakemake log, no terminal exit, and no failure marker. A fresh controller-log
  tail again returned no controller content. No intervention was taken.
- 2026-08-17T07:30:52Z: mount list reports Ultima
  `dra-080f12613e5deb4e8` `AVAILABLE`; ILMN remains `AVAILABLE`; ONT
  `dra-0a739dd6aa2d433a0` remains `CREATING`. ILMN live status now reports one
  submitted job: DYEC job `3`, external Slurm job `6`, with progress
  `Submitted job 3 with external jobid '6'.`; Slurm reports the named
  `illumina_run_qc_fetch_metric_subset-20260618_LH01106_0011_A23MFMCLT3` job
  `CONFIGURING` on requested resource `i192nvme-dy-bigmem192nvme-1`. The exact
  attributable Snakemake log is
  `.snakemake/log/2026-08-17T072916.336921.snakemake.log`. No action was taken
  on the scheduler.
- 2026-08-17T07:31:15Z: `dyec --json mounts verify --profile lsmc --region
  us-west-2 --cluster pcand-18022 --association-id dra-080f12613e5deb4e8`
  returned lifecycle `AVAILABLE`, `verified: true`, `usable: true`, exact path
  `/fsx/run_dir_mounts/ultima-604834-20260717`, and command ID
  `3da5b363-fb3a-4030-9feb-39e9eec9ffe6`.
- Ultima catalog evidence: `dyec --json catalog show ultima_run_qc` reported
  `git_tag: 15.0.11` before dry render, dry launch, live render, and live
  launch. Both renders used `--strict-project-check`, the explicit Ultima TSV,
  remote user `ubuntu`, project `pcand-18022`, cost center
  `pcand-18022-ccenter`, and explicit `--git-tag 15.0.11`; rendered commands
  are only `produce_ultima_run_qc`, not basecalling.
- Ultima dry controller `pcand18022_ultima_seq_qc_15011_dry_20260817T0732Z`:
  terminal `SUCCEEDED`, attributable `exit_code: 0`, zero submitted/finished
  Slurm jobs, no failure markers, and exact Snakemake log
  `.snakemake/log/2026-08-17T073338.077183.snakemake.log`.
- Ultima live `pcand18022_ultima_seq_qc_15011_live_20260817T0734Z` was
  catalog-launched after that dry receipt. Its first workflow status at
  2026-08-17T07:35:40Z has tmux session/controller PID `159673` present but no
  attributable controller receipt, no submitted job, no exact Snakemake log,
  and no terminal failure. It is monitored without intervention.
- 2026-08-17T07:37:57Z: ILMN live
  `pcand18022_ilmn_seq_qc_15011_live_20260817T0712Z` reached attributable
  terminal `SUCCEEDED`, `exit_code: 0`, no failure marker. Its previously
  submitted Slurm job is no longer live; the terminal receipt—not queue
  emptiness—is the success evidence.
- 2026-08-17T07:37:57Z: Ultima live
  `pcand18022_ultima_seq_qc_15011_live_20260817T0734Z` is attributable and
  tmux-correlated (`PID 159673`), state `RUNNING`, zero submitted/finished
  Slurm jobs, no failure marker, with exact active Snakemake log
  `.snakemake/log/2026-08-17T073606.697766.snakemake.log`. It is not yet a
  submitted-job lane. The approved cadence change to 15 minutes is therefore
  not yet eligible: ONT has not mounted/launched and Ultima has not submitted a
  job.
- 2026-08-17T07:39:32Z: mount list remains ILMN and Ultima `AVAILABLE`; ONT
  `dra-0a739dd6aa2d433a0` remains `CREATING`. Ultima live remains
  attributable/tmux-correlated and `RUNNING`, zero submitted/finished jobs, no
  progress line, no terminal exit, and no failure marker; its exact open
  Snakemake log is unchanged. A controller-log tail returned no content. No
  intervention and no cadence change were made.
- 2026-08-17T07:49:01Z: mount list reports all three associations `AVAILABLE`.
  ONT verification at 2026-08-17T07:49:25Z returned `verified: true`,
  `usable: true`, exact path `/fsx/run_dir_mounts/pca100-2026`, and command ID
  `c6118e13-5d9a-4e2f-aacd-faf570bc085e`. Both Bjuice input mounts are now
  available and verified; user was notified, with no Bjuice launch.
- 2026-08-17T07:49:01Z: Ultima live
  `pcand18022_ultima_seq_qc_15011_live_20260817T0734Z` reached attributable
  terminal `SUCCEEDED`, `exit_code: 0`, and no failure markers. It completed
  without a submitted Slurm job.
- ONT catalog evidence: `dyec --json catalog show ont_run_qc` reported
  `git_tag: 15.0.11` before dry render, dry launch, live render, and live
  launch. Both renders used `--strict-project-check`, the explicit
  `20260615_ONT_Set4-FC1` TSV, remote user `ubuntu`, project `pcand-18022`,
  cost center `pcand-18022-ccenter`, and explicit `--git-tag 15.0.11`; rendered
  command is `produce_ont_run_qc_and_demux_multiqc`, not basecalling.
- ONT dry `pcand18022_ont_seq_qc_15011_dry_20260817T0750Z` terminal
  `SUCCEEDED`, attributable `exit_code: 0`, zero submitted/finished Slurm jobs,
  no failure markers, and exact Snakemake log
  `.snakemake/log/2026-08-17T075147.035108.snakemake.log`.
- 2026-08-17T07:54:18Z: ONT live
  `pcand18022_ont_seq_qc_15011_live_20260817T0752Z` is attributable and
  tmux-correlated (`PID 230907`), state `RUNNING`, zero submitted/finished jobs,
  no exact Snakemake log yet, no terminal exit, and no failure marker. The
  cadence remains 10 minutes: ILMN did submit a job, but Ultima completed with
  no submission and ONT has not yet submitted one.
- 2026-08-17T07:58:33Z: all three read-only mounts remain `AVAILABLE`. ONT live
  remains attributable/tmux-correlated and `RUNNING` (`PID 230907`), zero
  submitted/finished jobs, no terminal exit or failure marker, with exact open
  Snakemake log `.snakemake/log/2026-08-17T075421.171162.snakemake.log`. A
  controller-log tail returned no content. No intervention or cadence change
  was made.
- 2026-08-17T08:08:33Z: all three mounts remain `AVAILABLE`. ONT live is
  attributable/tmux-correlated and `RUNNING`, with 8 submitted Slurm jobs, 7
  finished and external job `171` (DYEC job `8`) running as
  `ont_demux_fastq_qc-20260615_ONT_Set4-FC1` on
  `i192nvme-dy-bigmem192nvme-3`. The attributable controller reports `7 of 10
  steps (70%) done` at 2026-08-17T08:07:29Z and no terminal failure marker.
- 2026-08-17T08:10:40Z: the existing, sole heartbeat was updated in place from
  a 10-minute to a 15-minute interval. This applies the user's explicit
  cadence permission to the stable state: ILMN submitted Slurm work and is
  terminal `rc=0`, Ultima is terminal `rc=0` without a Slurm job, and ONT has
  submitted active Slurm work. No additional task was created.
- 2026-08-17T08:22:27Z: all mounts remain `AVAILABLE`. ONT live remains
  attributable/tmux-correlated and `RUNNING`, 8 submitted/7 finished jobs, one
  active Slurm job `171` named `ont_demux_fastq_qc-20260615_ONT_Set4-FC1` on
  `i192nvme-dy-bigmem192nvme-3`, 70% workflow progress, no terminal exit, and
  no failure marker. The exact Snakemake tail shows the final recorded progress
  at 2026-08-17T08:07:29Z after MultiQC job `250` finished; it identifies job
  `171` as the remaining demultiplexed FASTQ QC work. No intervention was
  taken.
- 2026-08-17T08:25:32Z: all mounts remain `AVAILABLE`. ONT live remains
  attributable/tmux-correlated and `RUNNING`, 8 submitted/7 finished jobs,
  active Slurm job `171`, 70% progress last updated at 08:07:29Z, no terminal
  exit, and no failure marker. A fresh 20-line Snakemake log tail ends at that
  same `7 of 10 steps (70%) done` event. The status read used
  `--receipt-wait-seconds 0` because the controller already has a receipt; no
  workflow action was taken.
- 2026-08-17T08:37:18Z: `source ./activate` followed by `dyec --json workflow
  status --profile lsmc --region us-west-2 --cluster pcand-18022 --remote-user
  ubuntu --session pcand18022_ont_seq_qc_15011_live_20260817T0752Z
  --receipt-wait-seconds 0` reports terminal `SUCCEEDED`, attributable
  `exit_code: 0` from the launch `status.json`, no failure markers, and no live
  Slurm state. This completes ONT after its eight submitted jobs. The ILMN and
  Ultima live controllers were rechecked in the same status pass and remain
  terminal attributable `rc=0`; the only heartbeat was deleted. No Bjuice
  prevalence manifest/run or export was generated.

## Approved result export and limited FSx cleanup

- The user supplied the exact three output prefixes, then separately confirmed
  that DYEC may delete only the matching three FSx analysis roots after their
  individual exports complete. The three roots and only those roots were:
  - `/fsx/analysis_results/pcand-18022/pcand18022_ilmn_seq_qc_15011_live_20260817T0712Z/`
    to `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022_ilmn_seq_qc_15011_live_20260817T0712Z/`.
  - `/fsx/analysis_results/pcand-18022/pcand18022_ont_seq_qc_15011_live_20260817T0752Z/`
    to `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022_ont_seq_qc_15011_live_20260817T0752Z/`.
  - `/fsx/analysis_results/pcand-18022/pcand18022_ultima_seq_qc_15011_live_20260817T0734Z/`
    to `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022_ultima_seq_qc_15011_live_20260817T0734Z/`.
- The local Mac has no `/fsx` mount, so an initial local `dyec analysis visit`
  refused the absent analysis root without making a remote mutation. Supported
  `dyec headnode run` execution as `ubuntu` then recorded an export visit and a
  clean delete lock for each root; no raw filesystem deletion, raw S3 copy, or
  direct DRA detach was used.
- ILMN receipt
  `docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/exports/illumina/fsx_export.yaml`:
  `status: success`, `phase: complete`, DRA `dra-0eccda2383d501558`, task
  `task-04314e6ad167c3da3` `SUCCEEDED`, `detached: true`,
  `delete_data_in_file_system: true`, detach lifecycle `DELETED`.
- ONT receipt
  `docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/exports/ont/fsx_export.yaml`:
  `status: success`, `phase: complete`, DRA `dra-07a7629ad6d148601`, task
  `task-0ab635bdaf6de0351` `SUCCEEDED`, `detached: true`,
  `delete_data_in_file_system: true`, detach lifecycle `DELETED`.
- Ultima receipt
  `docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/exports/ultima/fsx_export.yaml`:
  `status: success`, `phase: complete`, DRA `dra-0392265fb9f0f8aa9`, task
  `task-0764f6ed0d480690c` `SUCCEEDED`, `detached: true`,
  `delete_data_in_file_system: true`, detach lifecycle `DELETED`.
- A DYEC headnode postcheck reported `ILMN root absent`, `ONT root absent`, and
  `ULTIMA root absent`. A fresh `dyec --json mounts list` shows the temporary
  three export associations gone. It retains the original ILMN and ONT source
  mounts; the original Ultima source mount is absent because the user reports a
  separate-thread unmount. No source association was altered by this task.
- Catalog evidence was updated in both the source and packaged catalogs for
  `illumina_run_qc`, `ont_run_qc`, and `ultima_run_qc`. Each now has a
  `pcand-18022` result-report prefix and a terminal DayOA `15.0.11` validation
  record. The active definitions still report `git_tag: 15.0.12` and
  `validated_version: 15.0.9`; the historical 15.0.11 receipts do not represent
  a 15.0.12 validation claim.
