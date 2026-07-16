# DYEC 10.0.65 Release Evidence

Generated: in progress, opened 2026-06-20T03:05Z.

## Scope

This report tracks the DYEC `10.0.65` release validation on `tstpartition` in `us-west-2` using AWS profile `lsmc`. The DayOA catalog pin under evidence is `10.0.35`.

Controlling ledger: `docs/plans/20260619T203509Z_dyec_10_0_55_release_evidence_ledger.md`.

Command execution contract:
- DayOA workflow commands run as `ubuntu` on the headnode inside persistent tmux/login shells.
- Workflow setup uses separate `source dyoainit`, `dy-a ...`, then `dy-r ...` commands.
- No raw `snakemake` invocation is used for workflow execution.
- Run-directory catalog rows are executed one at a time, with no more than two active run DRAs.

Cleanup boundary:
- The eight slim analysis directories exported at Gate 0 were deleted only after explicit approval of the exact path set.
- No other `/fsx/analysis_results/**` cleanup is approved or claimed in this report until a separately recorded approval and verification exists.

## Release State

| Repo | Final tag | Commit | Evidence |
|---|---:|---|---|
| `daylily-omics-analysis` | `10.0.35` | `01cf556` | Annotated release tag on `jem-dev`; ONT run-QC pycoQC/nanoq wrapper fix. |
| `daylily-ephemeral-cluster` | `10.0.65` | `9f09d41e` | Annotated release tag on `jem-dev`; DYEC CLI reports `10.0.65` and self-pin points to `10.0.64`. |

## Command Catalog Matrix

| Command catalog command | Disposition | Evidence analysis ID | S3 evidence URI | Evidence details |
|---|---|---|---|---|
| `simple-test` | PASS | `catalog_slim_utility_20260619_10028` | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_utility_20260619_10028/` | 1,809 objects; 591,128,030 bytes. |
| `illumina_snv_alignstats` | PASS | `catalog_slim_ilmn_20260619_10028` | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_ilmn_20260619_10028/` | 1,812 objects; 591,890,671 bytes. |
| `illumina_snv_alignstats_relatedness_vep_multiqc` | PASS | `catalog_slim_ilmn_20260619_10028` | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_ilmn_20260619_10028/` | Shared slim Illumina evidence root; 1,812 objects; 591,890,671 bytes. |
| `illumina_hg002_kitchensink_multiqc` | PASS | `catalog_slim_ilmn_20260619_10028` | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_ilmn_20260619_10028/` | Shared slim Illumina evidence root; 1,812 objects; 591,890,671 bytes. |
| `illumina_pangenome_snv` | PASS | `catalog_slim_ilmn_20260619_10028` | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_ilmn_20260619_10028/` | Shared slim Illumina evidence root; 1,812 objects; 591,890,671 bytes. |
| `ultima_snv_alignstats` | PASS | `catalog_slim_ultima_20260619_10028` | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_ultima_20260619_10028/` | 1,794 objects; 591,042,796 bytes. |
| `ultima_snv_alignstats_kitchensink` | PASS | `catalog_slim_ultima_20260619_10028` | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_ultima_20260619_10028/` | Shared slim Ultima evidence root; 1,794 objects; 591,042,796 bytes. |
| `ultima_pangenome_snv` | PASS | `catalog_slim_ultima_20260619_10028` | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_ultima_20260619_10028/` | Shared slim Ultima evidence root; 1,794 objects; 591,042,796 bytes. |
| `ont_snv_alignstats` | PASS | `catalog_slim_ont_20260619_10028` | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_ont_20260619_10028/` | 1,792 objects; 591,030,651 bytes. |
| `ont_snv_alignstats_kitchensink` | PASS | `catalog_slim_ont_20260619_10028` | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_ont_20260619_10028/` | Shared slim ONT evidence root; 1,792 objects; 591,030,651 bytes. |
| `pacbio_snv_alignstats` | PASS | `catalog_slim_pacbio_20260619_10028` | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_pacbio_20260619_10028/` | 1,790 objects; 590,423,422 bytes. |
| `roche_snv_alignstats` | PASS | `catalog_slim_roche_20260619_10028` | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_roche_20260619_10028/` | 1,790 objects; 590,349,524 bytes. |
| `hybrid_ilmn_ont_snv` | PASS | `catalog_slim_hybrid_20260619_10028` | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_hybrid_20260619_10028/` | 1,799 objects; 608,970,129 bytes. |
| `hybrid_ilmn_ont_snv_kitchensink` | PASS | `catalog_slim_hybrid_20260619_10028` | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_hybrid_20260619_10028/` | Shared slim hybrid evidence root; 1,799 objects; 608,970,129 bytes. |
| `inflection-bjuice-product-v0.1` | PASS | `catalog_slim_hybrid_20260619_10028` | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_hybrid_20260619_10028/` | Shared slim hybrid evidence root; 1,799 objects; 608,970,129 bytes. |
| `complete_genomics_mgi_snv_concordance` | PASS | `catalog_slim_cg_20260619_10028` | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_cg_20260619_10028/` | 1,786 objects; 590,446,901 bytes. |
| `illumina_run_qc` | PASS | `catalog_illumina_run_qc_20260619_10051` | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_illumina_run_qc_20260619_10051/` | `dy-r produce_illumina_run_qc ...` returned `rc=0`; 1,869 objects; 593,196,094 bytes. |
| `illumina_bclconvert` | PASS | `catalog_illumina_bclconvert_l003_lane_20260620_10057` | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_illumina_bclconvert_l003_lane_20260620_10057/` | `dy-r produce_bclconvert_fastqs_and_metrics ...` returned `rc=0`; 82/82 demux FastQC zips; 2,456 exported objects; 602,068,300,470 bytes. |
| `illumina_run_qc_bclconvert` | PASS | `catalog_illumina_bclconvert_l003_lane_20260620_10057` | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_illumina_bclconvert_l003_lane_20260620_10057/` | `dy-r produce_illumina_run_qc_and_bclconvert ...` returned `rc=0` after bootstrap-config `dy-r --unlock`; shared BCL/run-QC evidence root; 2,456 exported objects; 602,068,300,470 bytes. |
| `ont_run_qc` | PASS | `catalog_ont_run_qc_20260620_10065` | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_ont_run_qc_20260620_10065/` | `dy-r produce_ont_run_qc ...` returned `rc=0` on DayOA `10.0.35`; summary, ONT MultiQC, demux MultiQC, and benchmark verified; 2,666 exported objects; 651,316,855 bytes. |
| `ultima_run_qc` | PENDING | pending | pending export | Requires Ultima run DRA after active run-DRA count remains within the max-two constraint. |

## Open Items

- Run `ultima_run_qc` with at most two active run DRAs.
- Refresh this report and the controlling ledger to terminal pass/fail dispositions for every row.
