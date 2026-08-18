# pre-rel-18025 completed-analysis FSx export and catalog evidence ledger

Created: `2026-08-17T21:02:39Z`

## Objective and boundary

Export every completed `rc=0` analysis in the current `pre-rel-18025` scope to
the user-specified standard derived-data layout:

`s3://lsmc-ssf-sequencing-data/derived/pre-rel-18025/<analysis-job-name>/daylily-omics-analysis/`

Each export is a supported DYEC DRA export of the exact DayOA checkout and all
its subdirectories. The source is retained on FSx: no
`--delete-data-in-file-system`, detach deletion, filesystem cleanup, or other
destructive action is authorized in this ledger. After a receipt proves export
success, update only the current catalog records that directly correspond to a
current-DYEC `15.0.15` result with that result's evidence URI. A Slack post is
not attempted until the user supplies an exact channel or channel ID.

## Gate 0 baseline

- Active local CLI: DYEC `18.0.26`; profile `lsmc`, region `us-west-2`, cluster
  `pre-rel-18025`, project/cost center `pre-rel-18025` /
  `pre-rel-18025-ccenter`, remote user `ubuntu`.
- The fresh terminal-status sweep found ten sessions `SUCCEEDED` with
  attributable `exit_code=0` and no failure markers. The Bjuice terminal
  receipt was already recorded immediately before this Gate 0 sweep; its
  detailed status query is slow but no subsequent controller or failure state
  exists.
- FSx `fs-0b1dadc673c44817f` had zero `EXPORT_TO_REPOSITORY` tasks at the last
  audit. The filesystem currently has four associations (one references DRA
  and three read-only run mounts), leaving only four temporary DRA slots;
  exports must run serially and detach cleanly before the next attach.
- Existing user-owned untracked paths are preserved: `TrusSV/`,
  `tmp/dayoa-ont-headnode-proof/`, and the pre-existing plan/artifact paths
  shown by `git status --short --branch`. No test suite is authorized.
- Catalog evidence fields before this work point to prior `pcand-*` exports;
  no `pre-rel-18025` evidence URI is present.
- A 16-hour CloudTrail audit on `2026-08-17T21:55Z` found ten successful-export
  submissions for similarly named but distinct `pcand-18022` roots on FSx
  `fs-09eb220d064d55d92`. It found only the completed EXP-QC15-ILMN task for
  this cluster's FSx `fs-0b1dadc673c44817f`; those prior `pcand` exports cannot
  evidence or substitute for the requested `pre-rel-18025` standard layout.

## Export rows

| ID | Analysis job name | Source / destination | Status | Category | Gate | Evidence / terminal note |
| --- | --- | --- | --- | --- | --- | --- |
| EXP-QC14-ILMN | `prerel18025_ilm_seq_qc_15014_live_20260817T1247Z` | `.../prerel18025_ilm_seq_qc_15014_live_20260817T1247Z/daylily-omics-analysis` -> `derived/pre-rel-18025/prerel18025_ilm_seq_qc_15014_live_20260817T1247Z/daylily-omics-analysis/` | SUCCEEDED | feature_implementation | Gate 1 | Receipt `EXP-QC14-ILMN/fsx_export.yaml`: `status=success`, task `task-0d939f018dd9ed2d2` `SUCCEEDED`, DRA `dra-08485f43532a33026` detached, and `delete_data_in_file_system=false`. |
| EXP-QC14-ONT | `prerel18025_ont_seq_qc_15014_live_20260817T1241Z` | `.../prerel18025_ont_seq_qc_15014_live_20260817T1241Z/daylily-omics-analysis` -> `derived/pre-rel-18025/prerel18025_ont_seq_qc_15014_live_20260817T1241Z/daylily-omics-analysis/` | SUCCEEDED | feature_implementation | Gate 1 | Receipt `EXP-QC14-ONT/fsx_export.yaml`: `status=success`, task `task-003e25cfd6ce656be` `SUCCEEDED`, DRA `dra-00e2e69e487f52dac` detached, and `delete_data_in_file_system=false`. |
| EXP-QC14-ULT | `prerel18025_ultima_seq_qc_15014_live_20260817T1308Z` | `.../prerel18025_ultima_seq_qc_15014_live_20260817T1308Z/daylily-omics-analysis` -> `derived/pre-rel-18025/prerel18025_ultima_seq_qc_15014_live_20260817T1308Z/daylily-omics-analysis/` | SUCCEEDED | feature_implementation | Gate 1 | Receipt `EXP-QC14-ULT/fsx_export.yaml`: `status=success`, task `task-083a8cb5715b182bb` `SUCCEEDED`, DRA `dra-0c6bb70c485215b9b` detached, and `delete_data_in_file_system=false`. |
| EXP-QC15-ILMN | `prerel18025_ilm_seq_qc_18026_15015_20260817T1427Z` | `.../prerel18025_ilm_seq_qc_18026_15015_20260817T1427Z/daylily-omics-analysis` -> `derived/pre-rel-18025/prerel18025_ilm_seq_qc_18026_15015_20260817T1427Z/daylily-omics-analysis/` | SUCCEEDED | feature_implementation | Gate 1 | Export visit recorded. Receipt `EXP-QC15-ILMN/fsx_export.yaml`: `status=success`, task `task-0806ae7883a4e4338` `SUCCEEDED`, association `dra-0b1eb30e8a1fe1932` detached (`DELETED`), and `delete_data_in_file_system=false`. S3 objects verified and exact FSx checkout remains `PRESENT`. |
| EXP-QC15-ONT | `prerel18025_ont_seq_qc_18026_15015_20260817T1427Z` | `.../prerel18025_ont_seq_qc_18026_15015_20260817T1427Z/daylily-omics-analysis` -> `derived/pre-rel-18025/prerel18025_ont_seq_qc_18026_15015_20260817T1427Z/daylily-omics-analysis/` | SUCCEEDED | feature_implementation | Gate 1 | Receipt `EXP-QC15-ONT/fsx_export.yaml`: `status=success`, task `task-07c7a97867d25cd22` `SUCCEEDED`, DRA `dra-0097478f859cf4679` detached, and `delete_data_in_file_system=false`. |
| EXP-QC15-ULT | `prerel18025_ultima_seq_qc_18026_15015_20260817T1427Z` | `.../prerel18025_ultima_seq_qc_18026_15015_20260817T1427Z/daylily-omics-analysis` -> `derived/pre-rel-18025/prerel18025_ultima_seq_qc_18026_15015_20260817T1427Z/daylily-omics-analysis/` | SUCCEEDED | feature_implementation | Gate 1 | Receipt `EXP-QC15-ULT/fsx_export.yaml`: `status=success`, task `task-0c4d76cfd76461291` `SUCCEEDED`, DRA `dra-0f5b9e9f2545c6ae8` detached, and `delete_data_in_file_system=false`. |
| EXP-SOLO-ILMN | `prerel18025_solo_ilmn_slim_15015_20260817t1512z` | `.../prerel18025_solo_ilmn_slim_15015_20260817t1512z/daylily-omics-analysis` -> `derived/pre-rel-18025/prerel18025_solo_ilmn_slim_15015_20260817t1512z/daylily-omics-analysis/` | SUCCEEDED | feature_implementation | Gate 1 | Receipt `EXP-SOLO-ILMN/fsx_export.yaml`: `status=success`, task `task-00099a6b0e2c47cb0` `SUCCEEDED`, DRA `dra-01b5f8037bfe74f2b` detached, and `delete_data_in_file_system=false`. |
| EXP-SOLO-ONT | `prerel18025_solo_ont_slim_15015_20260817t1512z` | `.../prerel18025_solo_ont_slim_15015_20260817t1512z/daylily-omics-analysis` -> `derived/pre-rel-18025/prerel18025_solo_ont_slim_15015_20260817t1512z/daylily-omics-analysis/` | SUCCEEDED | feature_implementation | Gate 1 | Receipt `EXP-SOLO-ONT/fsx_export.yaml`: `status=success`, task `task-04378b580ece8d276` `SUCCEEDED`, DRA `dra-0f37fe0d0c72a5792` detached, and `delete_data_in_file_system=false`. |
| EXP-SOLO-ULT | `prerel18025_solo_ultima_slim_15015_20260817t1512z` | `.../prerel18025_solo_ultima_slim_15015_20260817t1512z/daylily-omics-analysis` -> `derived/pre-rel-18025/prerel18025_solo_ultima_slim_15015_20260817t1512z/daylily-omics-analysis/` | SUCCEEDED | feature_implementation | Gate 1 | Receipt `EXP-SOLO-ULT/fsx_export.yaml`: `status=success`, task `task-07069beeace11dcb2` `SUCCEEDED`, DRA `dra-0bd412cc4a893d352` detached, and `delete_data_in_file_system=false`. |
| EXP-HIOMR2 | `prerel18025_hg002_hiomr2_5x5x_15015_20260817t1512z` | `.../prerel18025_hg002_hiomr2_5x5x_15015_20260817t1512z/daylily-omics-analysis` -> `derived/pre-rel-18025/prerel18025_hg002_hiomr2_5x5x_15015_20260817t1512z/daylily-omics-analysis/` | SUCCEEDED | feature_implementation | Gate 1 | Receipt `EXP-HIOMR2/fsx_export.yaml`: `status=success`, task `task-0ed3bd29ec49bf8e7` `SUCCEEDED`, DRA `dra-05686c7f7f962adc7` detached, and `delete_data_in_file_system=false`. |
| EXP-BJUICE | `prerel18025_bjuice_v09_hg002_5x5x_15015_20260817t1516z` | `.../prerel18025_bjuice_v09_hg002_5x5x_15015_20260817t1516z/daylily-omics-analysis` -> `derived/pre-rel-18025/prerel18025_bjuice_v09_hg002_5x5x_15015_20260817t1516z/daylily-omics-analysis/` | SUCCEEDED | feature_implementation | Gate 1 | Receipt `EXP-BJUICE/fsx_export.yaml`: `status=success`, task `task-052a8830ab584be33` `SUCCEEDED`, DRA `dra-07b35a13361158572` detached, and `delete_data_in_file_system=false`. |

## Catalog-evidence rows

| ID | Current catalog command | Status | Gate | Evidence / terminal note |
| --- | --- | --- | --- | --- |
| CAT-QC-ILMN | `illumina_run_qc` | OPEN | Gate 2 | Update only after EXP-QC15-ILMN receipt succeeds. |
| CAT-QC-ONT | `ont_run_qc` | OPEN | Gate 2 | Update only after EXP-QC15-ONT receipt succeeds. |
| CAT-QC-ULT | `ultima_run_qc` | OPEN | Gate 2 | Update only after EXP-QC15-ULT receipt succeeds. |
| CAT-SOLO-ILMN | `illumina_hg002_kitchensink_multiqc` | OPEN | Gate 2 | Update only after EXP-SOLO-ILMN receipt succeeds. |
| CAT-SOLO-ONT | `ont_snv_alignstats_kitchensink` | OPEN | Gate 2 | Update only after EXP-SOLO-ONT receipt succeeds. |
| CAT-SOLO-ULT | `ultima_snv_alignstats_kitchensink` | OPEN | Gate 2 | Update only after EXP-SOLO-ULT receipt succeeds. |
| CAT-HIOMR2 | `hiomr2_slim_kitchensink_mega` | OPEN | Gate 2 | Update only after EXP-HIOMR2 receipt succeeds. |
| CAT-BJUICE | `inflection-bjuice-product-v0.9` | OPEN | Gate 2 | Update only after EXP-BJUICE receipt succeeds. |

## Completion boundary

The export objective is complete only when every export row has a DYEC receipt
with `status: success`, `task_lifecycle: SUCCEEDED`, and
`delete_data_in_file_system: false`; every current-catalog row has the matching
standard-layout evidence URI; and each export source is still present on FSx.
Slack remains blocked on the missing channel destination.
