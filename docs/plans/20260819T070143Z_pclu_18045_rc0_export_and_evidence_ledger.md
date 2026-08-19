# `pclu-18045` RC0 export, cleanup, and catalog-evidence ledger

Created: `2026-08-19T07:01:43Z`  
Controlling request: export the eleven fresh `rc=0` production command-catalog analysis roots from FSx to S3, capture delivery evidence in the catalog, and only then remove the verified FSx roots after a separate destructive confirmation.  
Execution branch: `codex/pclu-18045-rc0-exports-18.0.57`, based on annotated DYEC `18.0.56` (`b3129397d1ba74906e30044ef4293b7113e27205`).

## Invariants

- The current 18.0.56 command catalog pins every command to the maximum released DayOA tag, `15.0.37` (`a31c9ca8c2ca5c9281face0e0716d9241b8fca86`).  The forward evidence release must retain that pin.
- A validation receipt must preserve its actual execution tag.  Several already-accepted RC0 runs predate 15.0.37; their provenance must not be relabeled as a 15.0.37 execution merely because the current catalog is now pinned there.
- Each export uses the full analysis root, a unique empty destination `s3://lsmc-ssf-sequencing-data/derived/pclu-18045/<analysis-id>/`, a pre-export `analysis visit --mode export`, and `dyec export --wait --timeout-seconds 5400` with FSx deletion disabled.
- `dyec exports cleanup --confirm-fsx-delete` is destructive.  It is blocked until every delivery receipt succeeds and the user gives a second explicit confirmation naming the eleven exact FSx roots.
- No workflow controller, raw Snakemake command, Slurm intervention, or source-pin mutation is in scope.

## Gate 0 baseline

| Check | Status | Evidence |
|---|---|---|
| Cluster identity and controller safety | SUCCESS | `pclu-18045`, `us-west-2`, stack `UPDATE_COMPLETE`, compute fleet `RUNNING`; `dyec --json headnode dayoa-controllers` at `2026-08-19T07:00:55Z` reported zero live controllers and zero Slurm jobs.  Historical tmux panes are stale and are not active controllers. |
| Release authority | SUCCESS | Annotated DYEC `18.0.56` and DayOA `15.0.37` tags were verified; current catalog lists all eleven `type: prod` commands at `git_tag: 15.0.37`. |
| Analysis-root inventory | SUCCESS | All eleven accepted same-root dry/live controller status objects were read; every recorded dry and live controller/day-run receipt is `rc=0`, and every live Snakemake receipt is `rc=0`. |
| Destination safety | SUCCESS | Each newly exported S3 destination was empty immediately before DRA creation; every no-delete export receipt is `success`, `complete`, `SUCCEEDED`, detached, and clone-status-v2 verified.  The three already-delivered Run-QC roots were re-HEADed rather than overwritten. |
| Deletion authority | BLOCKED | A second explicit user confirmation is required before any cleanup command can delete FSx data. |

## Export rows

| ID | Catalog command | Accepted analysis root | Export status | Receipt directory | S3 destination | Acceptance evidence |
|---|---|---|---|---|---|---|
| EXP-01 | `illumina_run_qc` | `/fsx/analysis_results/pclu-18045/pclu18045_ilmn_runqc_18047_15027_20260818t1803z` | SUCCESS | Prior tracked receipt `docs/plans/20260818T165711Z_pclu_18045_fresh_rc0_catalog_execution_ledger_artifacts/exports/pclu18045_ilmn_runqc_18047_15027_20260818t1803z/fsx_export.yaml` | `s3://lsmc-ssf-sequencing-data/derived/pclu-18045/pclu18045_ilmn_runqc_18047_15027_20260818t1803z/` | `task-0bb6871b1e2d50c35`, complete, detached, preserved FSx, clone-status-v2 verified; exported status object re-HEADed. |
| EXP-02 | `ont_run_qc` | `/fsx/analysis_results/pclu-18045/pclu18045_ont_runqc_18047_15027_20260818t1743z` | SUCCESS | Prior tracked receipt `docs/plans/20260818T165711Z_pclu_18045_fresh_rc0_catalog_execution_ledger_artifacts/exports/pclu18045_ont_runqc_18047_15027_20260818t1743z/fsx_export.yaml` | `s3://lsmc-ssf-sequencing-data/derived/pclu-18045/pclu18045_ont_runqc_18047_15027_20260818t1743z/` | `task-04c2d9004a10fe4d9`, complete, detached, preserved FSx, clone-status-v2 verified; exported status object re-HEADed. |
| EXP-03 | `ultima_run_qc` | `/fsx/analysis_results/pclu-18045/pclu18045_ultima_runqc_18047_15027_20260818t1825z` | SUCCESS | Prior tracked receipt `docs/plans/20260818T165711Z_pclu_18045_fresh_rc0_catalog_execution_ledger_artifacts/exports/pclu18045_ultima_runqc_18047_15027_20260818t1825z/fsx_export.yaml` | `s3://lsmc-ssf-sequencing-data/derived/pclu-18045/pclu18045_ultima_runqc_18047_15027_20260818t1825z/` | `task-0cc1b2ddc22746cf5`, complete, detached, preserved FSx, clone-status-v2 verified; exported status object re-HEADed. |
| EXP-04 | `hiomr2_slim_kitchensink_mega` | `/fsx/analysis_results/pclu-18045/pclu18045_rc0_18052_hiomr2_20260819T004600Z` | SUCCESS | `..._artifacts/EXP-04-hiomr2/fsx_export.yaml` | `s3://lsmc-ssf-sequencing-data/derived/pclu-18045/pclu18045_rc0_18052_hiomr2_20260819T004600Z/` | `dra-096d62f568ab913df`, task `task-05709df38186d168a`: success, complete, detached, preserved FSx, clone-status-v2 verified; exported status object re-HEADed. |
| EXP-05 | `inflection-bjuice-product-v0.9` | `/fsx/analysis_results/pclu-18045/pclu18045_rc0_18052_bjuice_20260819T004600Z` | SUCCESS | `..._artifacts/EXP-05-bjuice/fsx_export.yaml` | `s3://lsmc-ssf-sequencing-data/derived/pclu-18045/pclu18045_rc0_18052_bjuice_20260819T004600Z/` | `dra-08f8548757bfb61f5`, task `task-06be83f0601a7e82a`: success, complete, detached, preserved FSx, clone-status-v2 verified; exported status object re-HEADed. |
| EXP-06 | `illumina_hg002_kitchensink_multiqc` | `/fsx/analysis_results/pclu-18045/pclu18045_rc0_18052_soloilmn_20260819T004600Z` | SUCCESS | `..._artifacts/EXP-06-solo-ilmn/fsx_export.yaml` | `s3://lsmc-ssf-sequencing-data/derived/pclu-18045/pclu18045_rc0_18052_soloilmn_20260819T004600Z/` | `dra-02fed7c06c975ae16`, task `task-0bd1d9ee8fe48137c`: success, complete, detached, preserved FSx, clone-status-v2 verified; exported status object re-HEADed. |
| EXP-07 | `ont_snv_alignstats_kitchensink` | `/fsx/analysis_results/pclu-18045/pclu18045_rc0_18052_soloont_20260819T004600Z` | SUCCESS | `..._artifacts/EXP-07-solo-ont/fsx_export.yaml` | `s3://lsmc-ssf-sequencing-data/derived/pclu-18045/pclu18045_rc0_18052_soloont_20260819T004600Z/` | `dra-0706b4324d3e946b0`, task `task-022cb6e9cf3140dff`: success, complete, detached, preserved FSx, clone-status-v2 verified; exported status object re-HEADed. |
| EXP-08 | `ultima_snv_alignstats_kitchensink` | `/fsx/analysis_results/pclu-18045/pclu18045_rc0_18052_soloultima_20260819T004600Z` | SUCCESS | `..._artifacts/EXP-08-solo-ultima/fsx_export.yaml` | `s3://lsmc-ssf-sequencing-data/derived/pclu-18045/pclu18045_rc0_18052_soloultima_20260819T004600Z/` | `dra-07b88b4df6d0232a6`, task `task-005ba3c2b1186e132`: success, complete, detached, preserved FSx, clone-status-v2 verified; exported status object re-HEADed. |
| EXP-09 | `complete_genomics_cg_snv_concordance` | `/fsx/analysis_results/pclu-18045/pclu18045_rc0_18052_solocg_20260819T004600Z` | SUCCESS | `..._artifacts/EXP-09-solo-cg/fsx_export.yaml` | `s3://lsmc-ssf-sequencing-data/derived/pclu-18045/pclu18045_rc0_18052_solocg_20260819T004600Z/` | `dra-0068679f14941e110`, task `task-0328db6d15f94b0bd`: success, complete, detached, preserved FSx, clone-status-v2 verified; exported status object re-HEADed. |
| EXP-10 | `illumina_sentieon_pangenome_kitchensink` | `/fsx/analysis_results/pclu-18045/pclu18045_rc0_18053_pangenomeilmn_20260819T033638Z` | SUCCESS | `..._artifacts/EXP-10-pangenome-ilmn/fsx_export.yaml` | `s3://lsmc-ssf-sequencing-data/derived/pclu-18045/pclu18045_rc0_18053_pangenomeilmn_20260819T033638Z/` | `dra-0399a694ff79bf48a`, task `task-0a564cfaa7a78831b`: success, complete, detached, preserved FSx, clone-status-v2 verified; exported status object re-HEADed. |
| EXP-11 | `ultima_sentieon_pangenome_kitchensink` | `/fsx/analysis_results/pclu-18045/pclu18045_rc0_18055_pangenomeultima_20260819T051914Z` | SUCCESS | `..._artifacts/EXP-11-pangenome-ultima/fsx_export.yaml` | `s3://lsmc-ssf-sequencing-data/derived/pclu-18045/pclu18045_rc0_18055_pangenomeultima_20260819T051914Z/` | `dra-05be422bf08c53c66`, task `task-078777327e77d1b96`: success, complete, detached, preserved FSx, clone-status-v2 verified; exported status object re-HEADed. |

The `..._artifacts` directories are relative to this ledger's parent directory and are created only by the corresponding DYEC export receipt command.

## Catalog evidence and release rows

| ID | Requirement | Status | Terminal/evidence rule |
|---|---|---|---|
| EVD-01 through EVD-11 | Add each successful export's S3 root and direct-run receipt provenance to the matching production catalog command. | IN_PROGRESS | Source and packaged catalog copies now carry the eleven fresh `pclu-18045` S3 roots and RC0 `validation_runs`; the current view and new frozen `18.0.57` snapshot parse and both retain `git_tag: 15.0.37`.  The local evidence commit exists; push/release remains pending. |
| REL-01 | Cut a forward immutable DYEC evidence release after all eleven exports pass. | IN_PROGRESS | Source/package catalog parity and `18.0.57` frozen snapshot are present locally.  Tag/push waits for the parallel runtime-cache import/link workstream so one release can contain the verified operational contract.  No claim that earlier executions ran at 15.0.37. |
| DEL-01 through DEL-11 | Delete each corresponding FSx analysis root only after export verification. | BLOCKED | Requires a second explicit destructive confirmation, then exactly `dyec exports cleanup --confirm-fsx-delete` with matching root/S3/analysis ID and a cleanup receipt. |

## Parallel runtime-cache workstream

`runtime_cache_export` owns a separate ledger and the supported `dyec runtime-cache export` operation.  It must not use raw S3 copy/sync/move for runtime caches, and it must separately verify the region-specific post-install cache-link contract before reporting completion.
