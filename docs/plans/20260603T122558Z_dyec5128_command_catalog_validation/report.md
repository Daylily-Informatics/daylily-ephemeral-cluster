# DYEC5128 Command Catalog Validation Report

Updated: 2026-06-03T13:35:38Z

## Gate 0

- Status: `SUCCESS`
- Reason: ``
- Headnode: `i-092ed82f571bfbc2f`

## Commands

| Command | Status | Dry-run analysis | Live analysis | Export URI |
|---|---:|---|---|---|
| `simple-test` | `SUCCESS` | `ccv5128_20260603T122558Z_01_simple-test_dryrun` | `ccv5128_20260603T122558Z_01_simple-test` | `s3://lsmc-ssf-sequencing-data/derived/validation/dyec5128/dyec5128/ccv5128_20260603T122558Z_01_simple-test/` |
| `illumina_snv_alignstats` | `FAILED` | `ccv5128_20260603T122558Z_02_illumina_snv_alignstats_dryrun` | `ccv5128_20260603T122558Z_02_illumina_snv_alignstats` | `s3://lsmc-ssf-sequencing-data/derived/validation/dyec5128/dyec5128/ccv5128_20260603T122558Z_02_illumina_snv_alignstats/` |
| `illumina_snv_alignstats_relatedness_vep_multiqc` | `FAILED` | `ccv5128_20260603T122558Z_03_illumina_snv_alignstats_relatedness_vep_multiqc_dryrun` | `ccv5128_20260603T122558Z_03_illumina_snv_alignstats_relatedness_vep_multiqc` | `s3://lsmc-ssf-sequencing-data/derived/validation/dyec5128/dyec5128/ccv5128_20260603T122558Z_03_illumina_snv_alignstats_relatedness_vep_multiqc/` |
| `illumina_hg002_kitchensink_multiqc` | `FAILED` | `ccv5128_20260603T122558Z_04_illumina_hg002_kitchensink_multiqc_dryrun` | `ccv5128_20260603T122558Z_04_illumina_hg002_kitchensink_multiqc` | `s3://lsmc-ssf-sequencing-data/derived/validation/dyec5128/dyec5128/ccv5128_20260603T122558Z_04_illumina_hg002_kitchensink_multiqc/` |
| `ultima_snv_alignstats` | `FAILED` | `ccv5128_20260603T122558Z_05_ultima_snv_alignstats_dryrun` | `ccv5128_20260603T122558Z_05_ultima_snv_alignstats` | `s3://lsmc-ssf-sequencing-data/derived/validation/dyec5128/dyec5128/ccv5128_20260603T122558Z_05_ultima_snv_alignstats/` |
| `ultima_snv_alignstats_kitchensink` | `PENDING` | `` | `` | `` |
| `ont_snv_alignstats` | `PENDING` | `` | `` | `` |
| `ont_snv_alignstats_kitchensink` | `PENDING` | `` | `` | `` |
| `pacbio_snv_alignstats` | `PENDING` | `` | `` | `` |
| `roche_snv_alignstats` | `PENDING` | `` | `` | `` |
| `hybrid_ilmn_ont_snv` | `PENDING` | `` | `` | `` |
| `hybrid_ilmn_ont_snv_kitchensink` | `PENDING` | `` | `` | `` |
| `inflection-bjuice-product-v0.1` | `PENDING` | `` | `` | `` |
| `hybrid_ultima_ont_snv` | `PENDING` | `` | `` | `` |
| `complete_genomics_mgi_snv_concordance` | `PENDING` | `` | `` | `` |
| `illumina_run_qc` | `PENDING` | `` | `` | `` |
| `illumina_bclconvert` | `PENDING` | `` | `` | `` |
| `illumina_run_qc_bclconvert` | `PENDING` | `` | `` | `` |
| `ont_run_qc` | `PENDING` | `` | `` | `` |
| `ultima_run_qc` | `PENDING` | `` | `` | `` |

## Artifact Paths

- Events: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster/docs/plans/20260603T122558Z_dyec5128_command_catalog_validation/events.jsonl`
- Logs: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster/docs/plans/20260603T122558Z_dyec5128_command_catalog_validation/logs`
- Generated sample configs: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster/docs/plans/20260603T122558Z_dyec5128_command_catalog_validation/generated_sample_configs`
- Run contexts: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster/docs/plans/20260603T122558Z_dyec5128_command_catalog_validation/run_contexts`

## Event Counts

- Total events: `27`

## Cleanup

- Success cleanup manifest: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster/docs/plans/20260603T122558Z_dyec5128_command_catalog_validation/success_cleanup_manifest.md`
- Deleted successful dry-run analysis directories for `simple-test`, `illumina_snv_alignstats`, `illumina_snv_alignstats_relatedness_vep_multiqc`, `illumina_hg002_kitchensink_multiqc`, and `ultima_snv_alignstats`.
- `simple-test` live analysis directory was already absent after export/delete-on-success.
- Failed live analysis directories were left in place for debugging.
