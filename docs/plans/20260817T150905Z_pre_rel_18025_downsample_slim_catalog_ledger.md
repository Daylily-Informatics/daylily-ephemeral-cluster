# pre-rel-18025 downsample slim-data catalog execution ledger

Created: `2026-08-17T15:09:05Z`

## Objective and execution boundary

Launch the user-requested current-DYEC catalog-controlled downsample/slim-data
analyses on `pre-rel-18025` in `us-west-2`, using profile `lsmc`, remote user
`ubuntu`, project `pre-rel-18025`, and active cost center
`pre-rel-18025-ccenter`:

1. Solo kitchen-sink lanes: ILMN, ONT, Ultima, and CG.
2. `hiomr2_slim_kitchensink_mega` for the packaged HG002 5x+5x fixture.
3. The requested Bjuice v0.9 HG002 5x-by-5x lane.

Each eligible lane must use the current catalog with explicit DayOA `15.0.15`,
render and run a fresh catalog dry controller first, require attributable
terminal `rc=0` with zero submitted Slurm jobs, and only then continue the
same controller analysis root without `-n`.  DYEC owns the persistent Ubuntu
tmux controller, analysis-root visit/lock lifecycle, `dyoainit`, `dy-a`, and
`dy-r`; raw Snakemake is prohibited.

No budget change, Slurm intervention, source modification, export, or FSx
cleanup is included in this operation.  Existing sequence-QC jobs are read-only
context and must not be altered.

## Gate 0 baseline

- Activated local CLI: `Daylily Ephemeral Cluster 18.0.26`.
- Current catalog view: `current`; every requested visible catalog entry is
  pinned to DayOA `15.0.15`.
- Cluster inspection at `2026-08-17T15:08Z`: `pre-rel-18025` is
  `UPDATE_COMPLETE`, its compute fleet is `RUNNING`, and its headnode is
  `i-021f1c67509abb6c3`.
- Cost center inspection: `pre-rel-18025-ccenter` is active and permits
  `ubuntu`; no limit was changed.
- The three Bjuice-preval DRA associations remain read-only mounted and are
  reserved for the existing QC controller context.
- The user asked for parallelism only where contracts and current capacity
  permit it.  Do not silently substitute a historical fixture, cluster class,
  or full-coverage data for a declared slim-data contract.

## Catalog contract inventory

| ID | Requested lane | Current catalog command | Declared data profile | Manifest/status gate |
| --- | --- | --- | --- | --- |
| SOLO-ILMN | Solo ILMN | `illumina_hg002_kitchensink_multiqc` | `default_reads_slim` | Requires explicit six-manifest input; current command has no packaged manifest template. |
| SOLO-ONT | Solo ONT | `ont_snv_alignstats_kitchensink` | `default_reads_slim` | Requires explicit six-manifest input; current command has no packaged manifest template. |
| SOLO-ULT | Solo Ultima | `ultima_snv_alignstats_kitchensink` | `default_reads_slim` | Requires explicit six-manifest input; current command has no packaged manifest template. |
| SOLO-CG | Solo CG | `complete_genomics_cg_snv_concordance` | `default_reads_slim` | Packaged six-manifest fixture exists and requires a materialized staging receipt. |
| HIOMR2 | HG002 5x+5x | `hiomr2_slim_kitchensink_mega` | `hg002_bjuice_verified_5x5x_fastq` | Packaged receipt-bound fixture is available; full coverage must not be substituted. |
| BJUICE | Requested v0.9 HG002 5x-by-5x | `inflection-bjuice-product-v0.9` | `hg002_bjuice_v2_full_preval_run_mounts` | Requires mounted full-prevalence inputs and a direct-ILMN coverage receipt; it is not the packaged 5x+5x fixture. Exact one-AU 5x-by-5x manifest and matching v0.9 routing must be resolved before launch. |

## Control rows

| ID | Requirement | Status | Evidence / next gate |
| --- | --- | --- | --- |
| DOC-001 | Record Gate 0, exact pins, and user scope. | SUCCESS | This ledger; repo and DayOA execution instructions were reviewed before work. |
| CAT-001 | Verify all requested catalog commands and their exact targets/pins. | SUCCESS | Active DYEC 18.0.26 catalog `show` returned DayOA `15.0.15` for all six command IDs. |
| CLUSTER-001 | Verify selected cluster/cost center and preserve active QC work. | SUCCESS | `UPDATE_COMPLETE`, fleet `RUNNING`, active cost center; no job or budget action taken. |
| INPUT-001 | Resolve immutable ILMN/ONT/Ultima solo slim-data manifests. | SUCCESS | The three existing six-manifest sets were materialized/readable on the headnode: ILMN HG002 R1/R2, ONT HG003 cleaned CRAM, and Ultima HG003 cleaned CRAM. |
| INPUT-002 | Validate CG fixture and its `staging_receipt.json`. | BLOCKED | The historical receipt says materialized, but both required `TVBCG5X/HG003/5x/lane-1/D0` mate paths are currently absent on `pre-rel-18025`; no restage, remount, replacement, or retry is authorized. |
| INPUT-003 | Validate receipt-bound HG002 5x+5x fixture. | SUCCESS | The package identity receipt and three exact HG002 Bjuice-preval files were readable: ILMN R1/R2 and ONT FASTQ, with declared `5.862704556x`/`4.794169766x` coverage. |
| INPUT-004 | Resolve Bjuice v0.9 HG002 5x-by-5x semantics and generate/validate one authoritative manifest if the v0.9 contract supports it. | SUCCESS | Read-only ILMN and ONT DRA mounts verify `usable=true`; the supported v2 generator produced a one-AU `5x5` manifest set from the direct `43.73x` HG002 ILMN coverage receipt with ONT window `[0,11)`, and the v0.9 render uses `ont_fastq_hour_window_mode=per_analysis_unit`. |
| DRY-001 | Render and launch every unblocked dry controller in parallel. | SUCCESS | Five dry controllers reached attributable terminal `rc=0` with `submitted_count=0`; detailed receipts below. CG was blocked before render by INPUT-002. |
| LIVE-001 | Continue each successful dry controller in its same analysis root with only `-n` removed. | SUCCESS | All five eligible live lanes are terminal `rc=0` in their reused clean DayOA `15.0.15` roots. |

## Input and render evidence

- Solo manifests were the exact sets under
  `docs/plans/20260811T071607Z_solo_kitchensink_catalog_launch_ledger/manifests/{ilmn,ont,ultima}`.
- The unavailable CG mates are expected at
  `/fsx/staging/staged_external_sequencing_data/complete-genomics-solo-six-manifest-v1/TVBCG5X/HG003/5x/lane-1/D0/`
  and were both `MISSING` during the headnode check. This is a terminal
  fail-closed blocker for this request, not a workflow failure.
- The Bjuice manifest plan is
  `docs/plans/20260817T150905Z_pre_rel_18025_downsample_slim_catalog_artifacts/bjuice_v09_hg002_5x5x_plan.json`;
  its generated manifests and receipt are in the sibling
  `bjuice_v09_hg002_5x5x_manifests/` directory.
- The Bjuice DRA associations used only for read verification were
  `dra-0cf840190ff9a46f1` (ILMN) and `dra-0a150204884212f34` (ONT). Both
  remain read-only, no-auto-export mounts.

## Dry proof and live-controller receipts

All five roots are clean clones of DayOA tag `15.0.15` at
`6ac26d834b5492bd4dfced7fe67f22a02c09c0eb`. Each dry receipt is terminal
`SUCCEEDED`, attributable `exit_code=0`, and reports zero submitted Slurm
jobs. The live command is the exact rendered command against the same root,
with only `-n` removed.

| Lane | Analysis ID | Dry session | Live session | Current state |
| --- | --- | --- | --- | --- |
| SOLO-ILMN | `prerel18025_solo_ilmn_slim_15015_20260817t1512z` | `prerel18025-solo-ilmn-slim-15015-20260817t1512z-dry` | `prerel18025-solo-ilmn-slim-15015-20260817t1512z-live` | SUCCEEDED; attributable terminal `rc=0`. |
| SOLO-ONT | `prerel18025_solo_ont_slim_15015_20260817t1512z` | `prerel18025-solo-ont-slim-15015-20260817t1512z-dry` | `prerel18025-solo-ont-slim-15015-20260817t1512z-live` | SUCCEEDED; attributable terminal `rc=0`. |
| SOLO-ULT | `prerel18025_solo_ultima_slim_15015_20260817t1512z` | `prerel18025-solo-ultima-slim-15015-20260817t1512z-dry` | `prerel18025-solo-ultima-slim-15015-20260817t1512z-live` | SUCCEEDED; attributable terminal `rc=0`. |
| HIOMR2 | `prerel18025_hg002_hiomr2_5x5x_15015_20260817t1512z` | `prerel18025-hg002-hiomr2-5x5x-15015-20260817t1512z-dry` | `prerel18025-hg002-hiomr2-5x5x-15015-20260817t1512z-live` | SUCCEEDED; attributable terminal `rc=0`. |
| BJUICE | `prerel18025_bjuice_v09_hg002_5x5x_15015_20260817t1516z` | `prerel18025-bjuice-v09-hg002-5x5x-15015-20260817t1516z-dry` | `prerel18025-bjuice-v09-hg002-5x5x-15015-20260817t1516z-live` | SUCCEEDED; attributable terminal `rc=0`. |

### Controller-admission observation

At the latest read-only headnode inspection, all five controllers had a live,
attributable PID in the expected analysis root and no submitted Slurm jobs.
This is explained by DayOA `bin/day_run`'s built-in concurrent-controller
safeguard: it retains a single pre-Slurm admission lease while the admitted
controller creates/validates its environment and waits for a first matching
Slurm WorkDir. The behavior was observed directly in the running process tree:
HIOMR2 has an active `snakemake` child and `conda env create`; the other four
are in the safeguard's 60-second scan/wait loop. No budget change, scheduler
intervention, source change, Slurm action, export, or cleanup was performed.

An initial live-continuation invocation that included `--json` was rejected
locally before dispatch because `dyec workflow launch` does not support JSON
mode. The corrected invocations omitted that unsupported flag; no duplicate
controller or Slurm submission resulted from the rejected attempts.

At `2026-08-17T15:32:39Z`, the five live controller PIDs were still present:
ILMN `237833`, ONT `237838`, Ultima `237843`, HIOMR2 `237848`, and Bjuice
`248103`. HIOMR2's active Snakemake child still had no submitted job receipt
because it was actively running a pinned `conda env create`; no terminal
failure marker, budget denial, or scheduler error was observed.

### Progress snapshot: `2026-08-17T16:18Z`

All five controllers have crossed DayOA's pre-Slurm admission gate, remain
attributable and `RUNNING`, and report no terminal failure markers:

| Lane | Progress | Submitted / finished | Current Slurm observation |
| --- | --- | --- | --- |
| SOLO-ILMN | `123 of 155 steps (79%) done` | `98` / `123` | `19 RUNNING` |
| SOLO-ONT | last progress: submitted Snakemake job `7` as Slurm `353` | `16` / `32` | no attributable row at this exact snapshot |
| SOLO-ULT | `109 of 134 steps (81%) done` | `84` / `109` | `1 RUNNING` |
| HIOMR2 | `98 of 292 steps (34%) done` | `81` / `98` | `1 RUNNING` |
| BJUICE | last progress: submitted Snakemake job `72` as Slurm `357` | `40` / `40` | `12 RUNNING` |

The controller status timestamps fall between `16:18:46Z` and `16:18:59Z`.
The counts are DYEC workflow-observability values (not a claim that every
completed workflow step was a separate Slurm submission). No user-visible
failure, budget denial, source mutation, or Slurm intervention is recorded.

### Latest terminal/running snapshot

- SOLO-ILMN, SOLO-ONT, and SOLO-ULT now each report `SUCCEEDED` with an
  attributable terminal `exit_code=0` and no failure markers.
- HIOMR2 remains attributable and `RUNNING` at `98 of 292 steps (34%)`; its
  sole observed active job is
  `sentdhiomr2_hybrid_cli172i_core-HG002-Z-HG002-ANALYSIS-UNIT-5X5X` (Slurm
  `68`).
- BJUICE remains attributable and `RUNNING` at `98 of 294 steps (33%)`; its
  sole observed active job is
  `sentdhiomr2_hybrid_cli172i_core-HG002-qp0pfqh42zyaqs` (Slurm `269`).

### Direct controller/Slurm snapshot: `2026-08-17T17:34:54Z`

The three solo controllers remain terminal `SUCCEEDED rc=0`. The two remaining
controller PIDs are still live and attributable: HIOMR2 `237848` and BJUICE
`248103`. Direct `squeue` evidence shows their core jobs are genuinely
`RUNNING`, not pending or failed:

| Lane | Slurm job | Elapsed | Allocated node |
| --- | --- | --- | --- |
| HIOMR2 | `68` (`sentdhiomr2_hybrid_cli172i_core`) | `1:33:14` | `i384nvme-dy-mem384nvme-4` |
| BJUICE | `269` (`sentdhiomr2_hybrid_cli172i_core`) | `1:19:39` | `i384nvme-dy-mem384nvme-8` |

Both corresponding Snakemake controller processes remain present. This is a
read-only status observation; no job, node, scheduler, budget, or workflow
intervention was performed.

### Latest snapshot: `2026-08-17T18:54:44Z`

- HIOMR2 is now terminal `SUCCEEDED` with attributable `exit_code=0` and no
  failure markers.
- BJUICE remains attributable and `RUNNING` at `98 of 294 steps (33%)`, with
  no failure markers. Its controller PID `248103` and Snakemake PID `337279`
  are live. Direct `squeue` shows its core job `269`
  (`sentdhiomr2_hybrid_cli172i_core`) `RUNNING` for `1:09:18` on
  `i192nvme-dy-bigmem192nvme-5`.
- The running job is below the three-hour investigation threshold. This is
  monitoring only; no Slurm or workflow action was taken.

### Latest BJUICE monitor: `2026-08-17T19:42:12Z`

BJUICE is still attributable and `RUNNING` at `98 of 294 steps (33%)`; its
controller PID `248103` exists and it reports no failure markers. Direct
`squeue` shows job `269` remains `RUNNING` on
`i192nvme-dy-bigmem192nvme-5` with elapsed time `1:56:46`. It remains below the
three-hour investigation threshold; no intervention was performed.

### Latest BJUICE monitor: `2026-08-17T19:57:23Z`

BJUICE advanced to `170 of 294 steps (58%) done` at `19:54:36Z`, with `135`
submitted and `170` finished workflow-observability counts. It remains
attributable and `RUNNING` with no failure markers. Its current core gather job
is Slurm `2723` (`sentdhiomr2_hybrid_cli172i_gather`), `RUNNING` for `3:45` on
`i192nvme-dy-mem192nvme-9`. No intervention was performed.

### Latest BJUICE monitor: `2026-08-17T20:23:39Z`

BJUICE advanced to `263 of 294 steps (89%) done`, with `227` submitted and
`263` finished workflow-observability counts. The controller remains
attributable and `RUNNING` with no failure markers. Eleven Slurm jobs are
currently running, including the requested
`package_sentdhiomr2_inflection_analytical` job `3415`; the remaining active
jobs are `rtg_vcfeval_hiomr2_cli_gvcf_roi` tasks. No export, catalog update,
or workflow/Slurm intervention has occurred.

### One-time BJUICE monitor: `2026-08-17T20:26:12Z`

BJUICE is attributable and `RUNNING` at `265 of 294 steps (90%) done`, with
`227` submitted and `265` finished workflow-observability counts. It has no
failure markers and its controller PID `248103` exists. Ten active Slurm jobs
are all `rtg_vcfeval_hiomr2_cli_gvcf_roi` tasks, running for `23:36` to
`27:14` across the allocated `i192nvme-dy-{bigmem,mem}192nvme` nodes. The
Inflection packaging job has completed its active stage. This was monitoring
only; no export, catalog update, workflow retry, Slurm action, or cleanup was
performed.

### Latest BJUICE monitor: `2026-08-17T20:36:06Z`

BJUICE is attributable and `RUNNING` at `269 of 294 steps (91%) done`, with
`229` submitted and `269` finished workflow-observability counts. Its
controller PID `248103` exists, it has no failure markers, and DYEC attributes
eight active Slurm jobs. No export or intervention was performed.

### BJUICE terminal receipt

The live session `prerel18025-bjuice-v09-hg002-5x5x-15015-20260817t1516z-live`
is now `SUCCEEDED` with attributable `exit_code=0`, no failure markers, no
active attributed Slurm jobs, and no live controller. The user-requested
workflow-launch objective is terminal: the five eligible lanes succeeded and
the CG lane remains an evidence-backed missing-input blocker. Export, S3
delivery, Slack notification, and FSx cleanup are separate operations and have
not occurred.

### Export/FSx audit: `2026-08-17T20:56:07Z`

Required read visits were recorded for the now-completed HIOMR2 and BJUICE
analysis checkouts. Both exact DayOA checkout paths remain `PRESENT` on FSx.
The read-only FSx task query for filesystem `fs-0b1dadc673c44817f`, filtered to
`EXPORT_TO_REPOSITORY`, returned `[]`. There is therefore no export receipt,
S3 evidence URI, FSx deletion after export, or catalog evidence update for any
of these downsample results.

## Completion boundary

This objective is complete only when every requested lane has either a
catalog-controlled live launch receipt after successful dry proof, or an
evidence-backed fail-closed blocker recorded in this ledger.  A request to
change cost controls, export results, or delete FSx data is outside this
ledger's authority.
