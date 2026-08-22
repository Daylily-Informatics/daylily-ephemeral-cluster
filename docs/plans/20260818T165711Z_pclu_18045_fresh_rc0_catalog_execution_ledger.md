# `pclu-18045` fresh-RC0 catalog execution ledger

Created: 2026-08-18T16:57:11Z
Controlling request: Run the eleven fresh production catalog lanes on `pclu-18045` using DYEC `18.0.47`, pinned to DayOA `15.0.27`.
Ledger owner: Codex / `codex/pclu-18045-rc0-catalog-execution`

## Scope and acceptance

This ledger covers the eleven lanes expressly requested in the preceding
fresh-RC0 plan. It deliberately excludes historical, development, research,
and the two additional Bjuice product catalog entries. It does **not** use
historical results or concordance values as validation.

Each eligible lane must use a unique analysis ID, an immutable `18.0.47` /
`15.0.27` pin, an explicit input contract, a catalog dry controller with
`rc=0` and no submitted workflow work, and a same-root live continuation that
differs only by removal of `-n`. A live lane passes only when its controller
returns `rc=0`. Export and catalog-evidence rows remain independent gates.

No raw Snakemake, manual controller, Slurm administration, implicit input
discovery, source patching, deletion, or export cleanup is authorized.

## Gate 0 baseline

- Local repo is on `codex/pclu-18045-rc0-catalog-execution`, created from
  annotated DYEC tag `18.0.47` at `6c034972727769ddc376791d15ddd1a76f84f019`.
- Unrelated user-owned untracked paths preserved in the checkout: `TrusSV/`,
  `docs/plans/20260818T133210Z_workflow_status_chunked_transport_ledger.md`,
  `docs/plans/20260818T133927Z_shared_github_policy_validation_ledger.md`, and
  `tmp/dayoa-ont-headnode-proof/`.
- Local and headnode DYEC report `18.0.47`; headnode reports pinned DayOA
  `15.0.27` from `/home/ubuntu/projects/daylily-ephemeral-cluster`.
- Target cluster is `lsmc/us-west-2/pclu-18045`, headnode
  `i-005c458734f5d4800`, status `UPDATE_COMPLETE`, compute fleet `RUNNING`.
- 2026-08-18T16:56:27Z controller inventory was authoritative and empty:
  zero DYEC controllers, Slurm jobs, tmux panes, and stale receipts.
- 2026-08-18T16:56Z `dyec mounts list` returned an empty array. No previous
  cluster's mount or staged data is treated as present on this new FSx system.
- The following read-only input associations were independently revalidated
  from current S3 visibility and the still-available prior association shape:
  ILMN `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/`
  to mount `20260618_LH01106_0011_A23MFMCLT3`; ONT parent
  `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/` to mount
  `pca100-2026`; Ultima
  `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/RUN604834/2026/604834-20260717_2309/`
  to mount `ultima-604834-20260717`. The ONT QC run remains the explicit child
  `20260615_ONT_Set4-FC1` beneath the mounted parent.
- No workflow, mount, DRA, export, data, or Slurm state has been changed for
  this ledger as of creation.
- Live controllers begun after dry proof use DayOA's built-in pre-Slurm
  admission lease. At 2026-08-18T17:26Z `SOLO Ultima` held that lease while the
  other same-root continuations waited; this serialization is an expected
  controller safeguard and will not be bypassed.
- The ledger's explicit, no-delete read-only run-mount associations are ILMN
  `dra-095e58578ecac6b3d`, ONT `dra-07f63b6c26f23a545`, and Ultima
  `dra-07fa4748941bd7d5d`. ONT became `AVAILABLE` and passed `dyec mounts
  verify` at 2026-08-18T17:42Z. ILMN became `AVAILABLE` and passed `dyec
  mounts verify` at 2026-08-18T18:03Z. Ultima became `AVAILABLE` and passed
  `dyec mounts verify` at 2026-08-18T18:25Z.
- `ultima_sentieon_pangenome_kitchensink` completed its fresh dry proof but
  its same-root live controller failed terminally at 2026-08-18T17:53Z with
  controller/day-run/Snakemake `rc=1`. The graph caller rejected HLA contigs in
  the explicit UG CRAM that are absent from the pinned hg38 reference. No
  input substitution, source patch, retry, export, or cleanup is authorized.
- The first normal kitchen-sink consumers of the new DayOA runtime exposed a
  second release-level defect: `ExpansionHunter` cannot load
  `libboost_program_options.so.1.85.0`. `SOLO Ultima` therefore failed
  terminally at 2026-08-18T18:01Z with controller/day-run/Snakemake `rc=1`.
  The same rule has also failed in the still-finalizing SOLO ILMN controller.
  This is not a reason to alter the immutable runtime in place.
- HIOMR2 failed terminally at 2026-08-18T18:10Z before any workflow job was
  submitted. Its exact pinned DayOA checkout was clean, but the required
  `hiomr2_cli172i_iamh2o_v0.1` Conda environment could not install a pip
  build dependency after repeated PyPI HTTP 502 responses. No agent retry,
  source change, environment mutation, or cleanup is authorized.
- SOLO ONT failed terminally at 2026-08-18T18:26Z with controller/day-run/
  Snakemake `rc=1`: the benchmark collector rejected a generated
  `pre_prep_ont_cram` benchmark filename containing the analysis-unit token
  twice. This source behavior is distinct from the ExpansionHunter runtime
  fault and likewise cannot be corrected inside the pinned checkout.

## Control ledger

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence / terminal note |
|---|---|---|---|---|---|---|---|
| G0 | Release / cluster | Freeze exact release, headnode, catalog scope, input contracts, mounts, cost-center, and empty export destinations. | SUCCEEDED | legitimate_safety_handling | Gate 0 | ledger owner | Baseline above; all three explicit run mounts were created read-only, verified `AVAILABLE`, and every launched lane used its declared input contract and immutable release pin. |
| RUN-01 | HIOMR2 | `hiomr2_slim_kitchensink_mega`, 5x ILMN + 5x ONT. | FAILED | active_product_contract | Gate 0 | run agent | Dry `pclu18045_hiomr2_18047_15027_20260818t1706z` SUCCEEDED at 2026-08-18T17:08Z: attributable controller/day-run/Snakemake `rc=0`, zero submitted jobs. Its same-root live controller failed terminally with `rc=1` before submission when `hiomr2_cli172i_iamh2o_v0.1` could not install pip dependency `poetry-core` after repeated PyPI HTTP 502 responses. No retry/fallback is authorized. |
| RUN-02 | Bjuice v0.9 | `inflection-bjuice-product-v0.9`, 5x ILMN + 5x ONT. | FAILED | active_product_contract | Gate 0 | run agent | ILMN and ONT mounts are verified `AVAILABLE`. Dry `pclu18045_bjuice_v09_18047_15027_20260818t1803z` SUCCEEDED: attributable controller/day-run/Snakemake `rc=0`, zero submitted jobs. Its same-root live continuation terminally returned controller/day-run/Snakemake `rc=1` after `ExpansionHunter` could not load `libboost_program_options.so.1.85.0` in the immutable 15.0.27 runtime. No retry, fallback, source change, or export is authorized. |
| RUN-03 | ILMN Run-QC | `illumina_run_qc`, no BCL Convert. | SUCCEEDED | active_product_contract | Gate 0 | run agent | ILMN mount `dra-095e58578ecac6b3d` verified `AVAILABLE`. Dry `pclu18045_ilmn_runqc_18047_15027_20260818t1803z` SUCCEEDED: attributable controller/day-run/Snakemake `rc=0`, zero submitted jobs. Same-root live continuation also SUCCEEDED at 2026-08-18T18:33Z with controller/day-run/Snakemake `rc=0`. |
| RUN-04 | ONT Run-QC | `ont_run_qc`, no basecalling. | SUCCEEDED | active_product_contract | Gate 0 | run agent | ONT mount `dra-07f63b6c26f23a545` verified `AVAILABLE`. Dry `pclu18045_ont_runqc_18047_15027_20260818t1743z` SUCCEEDED: attributable controller/day-run/Snakemake `rc=0`, zero submitted jobs. Same-root live continuation also SUCCEEDED at 2026-08-18T18:22Z with controller/day-run/Snakemake `rc=0`. |
| RUN-05 | Ultima Run-QC | `ultima_run_qc`, no basecalling. | SUCCEEDED | active_product_contract | Gate 0 | run agent | Explicit Ultima DRA `dra-07fa4748941bd7d5d` verified `AVAILABLE`. Dry `pclu18045_ultima_runqc_18047_15027_20260818t1825z` SUCCEEDED with attributable controller/day-run/Snakemake `rc=0`, zero submitted jobs; its same-root live continuation also SUCCEEDED with `rc=0`. |
| RUN-06 | SOLO ILMN | `illumina_hg002_kitchensink_multiqc`. | FAILED | active_product_contract | Gate 0 | run agent | Dry `pclu18045_solo_ilmn_18047_15027_20260818t1708z` SUCCEEDED: attributable controller/Snakemake `rc=0`, zero submitted jobs. Its same-root live continuation failed terminally with controller/day-run/Snakemake `rc=1`; `ExpansionHunter` could not load `libboost_program_options.so.1.85.0` in the immutable 15.0.27 runtime. No retry/fallback is authorized. |
| RUN-07 | SOLO ONT | `ont_snv_alignstats_kitchensink`. | FAILED | active_product_contract | Gate 0 | run agent | Dry `pclu18045_solo_ont_18047_15027_20260818t1708z` SUCCEEDED: attributable controller/Snakemake `rc=0`, zero submitted jobs. Its same-root live continuation failed terminally with `rc=1`; benchmark collection rejected a `pre_prep_ont_cram` filename containing the analysis-unit token twice. No retry/fallback is authorized. |
| RUN-08 | SOLO Ultima | `ultima_snv_alignstats_kitchensink`. | FAILED | active_product_contract | Gate 0 | run agent | Dry `pclu18045_solo_ultima_18047_15027_20260818t1708z` SUCCEEDED: attributable controller/Snakemake `rc=0`, zero submitted jobs. Its same-root live continuation failed terminally with controller/day-run/Snakemake `rc=1`; `ExpansionHunter` could not load `libboost_program_options.so.1.85.0` in the immutable 15.0.27 runtime. No retry/fallback is authorized. |
| RUN-09 | SOLO CG | `complete_genomics_cg_snv_concordance`. | FAILED | active_product_contract | Gate 0 | run agent | Fresh materialized six-manifest receipt `041f4611…6f3198`; dry `pclu18045_solo_cg_18047_15027_20260818t1708z` SUCCEEDED: attributable controller/Snakemake `rc=0`, zero submitted jobs. Its same-root live continuation failed terminally with controller/day-run/Snakemake `rc=1`; `ExpansionHunter` could not load `libboost_program_options.so.1.85.0` in the immutable 15.0.27 runtime. No retry/fallback is authorized. |
| RUN-10 | Pangenome ILMN | `illumina_sentieon_pangenome_kitchensink`. | BLOCKED | active_product_contract | Gate 0 | run agent | Dry `pclu18045_pangenome_ilmn_18047_15027_20260818t1708z` failed before Snakemake with controller/day-run `rc=2`, zero jobs. DayOA `15.0.27` requested graph `pangenome_sr/dmd` dedup artifacts and could not produce its required sorted BAM. The pinned graph lane requires fixed `spmd`; a new tested DayOA release and a newly pinned DYEC release are required. No retry/fallback is authorized. |
| RUN-11 | Pangenome Ultima | `ultima_sentieon_pangenome_kitchensink`. | FAILED | active_product_contract | Gate 0 | run agent | Dry `pclu18045_pangenome_ultima_18047_15027_20260818t1708z` SUCCEEDED: attributable controller/Snakemake `rc=0`, zero submitted jobs. Its same-root live continuation failed terminally with controller/day-run/Snakemake `rc=1`: `sentieon_pangenome_ug` rejected explicit UG-CRAM HLA contigs absent from the pinned hg38 reference. No retry/fallback is authorized. |
| EXP-01 | Export | No-delete full-root export for RUN-01 after fresh live `rc=0`. | BLOCKED | legitimate_safety_handling | Export | export owner | RUN-01 did not produce fresh live `rc=0`; its retained root is not eligible for export. |
| EXP-02 | Export | No-delete full-root export for RUN-02 after fresh live `rc=0`. | BLOCKED | legitimate_safety_handling | Export | export owner | RUN-02 did not produce fresh live `rc=0`; its retained root is not eligible for export. |
| EXP-03 | Export | No-delete full-root export for RUN-03 after fresh live `rc=0`. | SUCCEEDED | legitimate_safety_handling | Export | export owner | Export visit recorded; DRA task `task-0bb6871b1e2d50c35` SUCCEEDED. Receipt `docs/plans/20260818T165711Z_pclu_18045_fresh_rc0_catalog_execution_ledger_artifacts/exports/pclu18045_ilmn_runqc_18047_15027_20260818t1803z/fsx_export.yaml` confirms `detached: true`, `delete_data_in_file_system: false`, and clone-status-v2 evidence. S3 root: `s3://lsmc-ssf-sequencing-data/derived/pclu-18045/pclu18045_ilmn_runqc_18047_15027_20260818t1803z/`. |
| EXP-04 | Export | No-delete full-root export for RUN-04 after fresh live `rc=0`. | SUCCEEDED | legitimate_safety_handling | Export | export owner | Export visit recorded; DRA task `task-04c2d9004a10fe4d9` SUCCEEDED. Receipt `docs/plans/20260818T165711Z_pclu_18045_fresh_rc0_catalog_execution_ledger_artifacts/exports/pclu18045_ont_runqc_18047_15027_20260818t1743z/fsx_export.yaml` confirms `detached: true`, `delete_data_in_file_system: false`, and clone-status-v2 evidence. S3 root: `s3://lsmc-ssf-sequencing-data/derived/pclu-18045/pclu18045_ont_runqc_18047_15027_20260818t1743z/`. |
| EXP-05 | Export | No-delete full-root export for RUN-05 after fresh live `rc=0`. | SUCCEEDED | legitimate_safety_handling | Export | export owner | Export visit recorded; DRA task `task-0cc1b2ddc22746cf5` SUCCEEDED. Receipt `docs/plans/20260818T165711Z_pclu_18045_fresh_rc0_catalog_execution_ledger_artifacts/exports/pclu18045_ultima_runqc_18047_15027_20260818t1825z/fsx_export.yaml` confirms `detached: true`, `delete_data_in_file_system: false`, and clone-status-v2 evidence. S3 root: `s3://lsmc-ssf-sequencing-data/derived/pclu-18045/pclu18045_ultima_runqc_18047_15027_20260818t1825z/`. |
| EXP-06 | Export | No-delete full-root export for RUN-06 after fresh live `rc=0`. | BLOCKED | legitimate_safety_handling | Export | export owner | RUN-06 did not produce fresh live `rc=0`; its retained root is not eligible for export. |
| EXP-07 | Export | No-delete full-root export for RUN-07 after fresh live `rc=0`. | BLOCKED | legitimate_safety_handling | Export | export owner | RUN-07 did not produce fresh live `rc=0`; its retained root is not eligible for export. |
| EXP-08 | Export | No-delete full-root export for RUN-08 after fresh live `rc=0`. | BLOCKED | legitimate_safety_handling | Export | export owner | RUN-08 did not produce fresh live `rc=0`; its retained root is not eligible for export. |
| EXP-09 | Export | No-delete full-root export for RUN-09 after fresh live `rc=0`. | BLOCKED | legitimate_safety_handling | Export | export owner | RUN-09 did not produce fresh live `rc=0`; its retained root is not eligible for export. |
| EXP-10 | Export | No-delete full-root export for RUN-10 after fresh live `rc=0`. | BLOCKED | legitimate_safety_handling | Export | export owner | RUN-10 dry failed under the immutable release pin; no live root is eligible for export. |
| EXP-11 | Export | No-delete full-root export for RUN-11 after fresh live `rc=0`. | BLOCKED | legitimate_safety_handling | Export | export owner | RUN-11 did not produce fresh live `rc=0`; its retained root is not eligible for export. |
| EVD-01 | Catalog evidence | Fresh S3 receipt provenance for RUN-01, only after EXP-01 succeeds. | BLOCKED | active_product_contract | Evidence | ledger owner | RUN-01 has no successful fresh live/export evidence under the immutable release pin. |
| EVD-02 | Catalog evidence | Fresh S3 receipt provenance for RUN-02, only after EXP-02 succeeds. | BLOCKED | active_product_contract | Evidence | ledger owner | RUN-02 has no successful fresh live/export evidence under the immutable release pin. |
| EVD-03 | Catalog evidence | Fresh S3 receipt provenance for RUN-03, only after EXP-03 succeeds. | BLOCKED | active_product_contract | Evidence | ledger owner | Per-lane S3 provenance is complete, but the immutable all-lanes evidence-release condition cannot be met while other required lanes are terminal failed/blocked. No catalog mutation is authorized under this ledger. |
| EVD-04 | Catalog evidence | Fresh S3 receipt provenance for RUN-04, only after EXP-04 succeeds. | BLOCKED | active_product_contract | Evidence | ledger owner | Per-lane S3 provenance is complete, but the immutable all-lanes evidence-release condition cannot be met while other required lanes are terminal failed/blocked. No catalog mutation is authorized under this ledger. |
| EVD-05 | Catalog evidence | Fresh S3 receipt provenance for RUN-05, only after EXP-05 succeeds. | BLOCKED | active_product_contract | Evidence | ledger owner | Per-lane S3 provenance is complete, but the immutable all-lanes evidence-release condition cannot be met while other required lanes are terminal failed/blocked. No catalog mutation is authorized under this ledger. |
| EVD-06 | Catalog evidence | Fresh S3 receipt provenance for RUN-06, only after EXP-06 succeeds. | BLOCKED | active_product_contract | Evidence | ledger owner | RUN-06 has no successful fresh live/export evidence under the immutable release pin. |
| EVD-07 | Catalog evidence | Fresh S3 receipt provenance for RUN-07, only after EXP-07 succeeds. | BLOCKED | active_product_contract | Evidence | ledger owner | RUN-07 has no successful fresh live/export evidence under the immutable release pin. |
| EVD-08 | Catalog evidence | Fresh S3 receipt provenance for RUN-08, only after EXP-08 succeeds. | BLOCKED | active_product_contract | Evidence | ledger owner | RUN-08 has no successful fresh live/export evidence under the immutable release pin. |
| EVD-09 | Catalog evidence | Fresh S3 receipt provenance for RUN-09, only after EXP-09 succeeds. | BLOCKED | active_product_contract | Evidence | ledger owner | RUN-09 has no successful fresh live/export evidence under the immutable release pin. |
| EVD-10 | Catalog evidence | Fresh S3 receipt provenance for RUN-10, only after EXP-10 succeeds. | BLOCKED | active_product_contract | Evidence | ledger owner | RUN-10 has no successful fresh live/export evidence under the immutable release pin. |
| EVD-11 | Catalog evidence | Fresh S3 receipt provenance for RUN-11, only after EXP-11 succeeds. | BLOCKED | active_product_contract | Evidence | ledger owner | RUN-11 has no successful fresh live/export evidence under the immutable release pin. |

## Execution rules

1. Bootstrap a single catalog dry controller before issuing any parallel dry
   launches. That controller must return `rc=0` with zero submitted workflow
   work.
2. Eligible dry lanes may then launch in parallel, each with a unique analysis
   ID and controller-owned write lock.
3. A live controller is a same-root continuation of its successful dry
   controller. The effective DayOA command must be identical except for `-n`.
4. Export only after fresh live controller `rc=0`, serially, from
   `/fsx/analysis_results/pclu-18045/<analysis-id>/` to
   `s3://lsmc-ssf-sequencing-data/derived/pclu-18045/<analysis-id>/`, preserving
   FSx data.
5. Any unavailable explicit input, mount, manifest, or prefix records a
   `BLOCKED` terminal state. It is never replaced by discovered or historical
   data.

## Closeout

All eleven lane rows are terminal. Ten dry controllers returned `rc=0` with
zero submitted workflow jobs; `illumina_sentieon_pangenome_kitchensink` failed
its dry closure before any submission. Of the ten eligible same-root live
continuations, ILMN, ONT, and Ultima Run-QC returned fresh `rc=0`; the other
seven returned `rc=1`. The three successful Run-QC roots were exported
serially without deletion and their DRA receipts and S3 controller/status
objects are recorded above. The other eight roots are intentionally not
exported. Because the all-lanes fresh-RC0 condition is unmet, no evidence-only
catalog release or catalog mutation is authorized by this ledger.
