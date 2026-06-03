# DYEC5128 Command Catalog Success Cleanup

Updated: 2026-06-03T13:35:38Z

## Scope

Only analysis directories for catalog workflow sessions that had terminal `SUCCESS`
status are eligible for cleanup here. Failed live workflow directories are left in
place for debugging. Running workflow directories are left in place.

## Successful Catalog Results

| Command | Phase | Analysis ID | Status | FSx state | Notes |
|---|---|---|---|---|---|
| `simple-test` | live | `ccv5128_20260603T122558Z_01_simple-test` | `SUCCESS` | absent | Export/delete-on-success already removed the live analysis directory. |
| `simple-test` | dry-run | `ccv5128_20260603T122558Z_01_simple-test_dryrun` | `SUCCESS` | present | Eligible for deletion. |
| `illumina_snv_alignstats` | dry-run | `ccv5128_20260603T122558Z_02_illumina_snv_alignstats_dryrun` | `SUCCESS` | present | Eligible for deletion; live run failed and is not deleted. |
| `illumina_snv_alignstats_relatedness_vep_multiqc` | dry-run | `ccv5128_20260603T122558Z_03_illumina_snv_alignstats_relatedness_vep_multiqc_dryrun` | `SUCCESS` | present | Eligible for deletion; live run failed and is not deleted. |
| `illumina_hg002_kitchensink_multiqc` | dry-run | `ccv5128_20260603T122558Z_04_illumina_hg002_kitchensink_multiqc_dryrun` | `SUCCESS` | present | Eligible for deletion; live run failed and is not deleted. |
| `ultima_snv_alignstats` | dry-run | `ccv5128_20260603T122558Z_05_ultima_snv_alignstats_dryrun` | `SUCCESS` | deleted | Deleted; live run later completed with `exit_code=1` and was left in place. |

## Delete Manifest

```text
/fsx/analysis_results/dyec5128/ccv5128_20260603T122558Z_01_simple-test_dryrun
/fsx/analysis_results/dyec5128/ccv5128_20260603T122558Z_02_illumina_snv_alignstats_dryrun
/fsx/analysis_results/dyec5128/ccv5128_20260603T122558Z_03_illumina_snv_alignstats_relatedness_vep_multiqc_dryrun
/fsx/analysis_results/dyec5128/ccv5128_20260603T122558Z_04_illumina_hg002_kitchensink_multiqc_dryrun
/fsx/analysis_results/dyec5128/ccv5128_20260603T122558Z_05_ultima_snv_alignstats_dryrun
```

## Pre-Deletion Sizes

| Analysis ID | Size | Bytes |
|---|---:|---:|
| `ccv5128_20260603T122558Z_01_simple-test_dryrun` | `615M` | `621816703` |
| `ccv5128_20260603T122558Z_02_illumina_snv_alignstats_dryrun` | `614M` | `621252376` |
| `ccv5128_20260603T122558Z_03_illumina_snv_alignstats_relatedness_vep_multiqc_dryrun` | `615M` | `621478347` |
| `ccv5128_20260603T122558Z_04_illumina_hg002_kitchensink_multiqc_dryrun` | `615M` | `621481769` |
| `ccv5128_20260603T122558Z_05_ultima_snv_alignstats_dryrun` | `614M` | `621344250` |

## Deletion Result

Completed: 2026-06-03T13:35:38Z

Deleted and verified absent:

```text
/fsx/analysis_results/dyec5128/ccv5128_20260603T122558Z_01_simple-test_dryrun
/fsx/analysis_results/dyec5128/ccv5128_20260603T122558Z_02_illumina_snv_alignstats_dryrun
/fsx/analysis_results/dyec5128/ccv5128_20260603T122558Z_03_illumina_snv_alignstats_relatedness_vep_multiqc_dryrun
/fsx/analysis_results/dyec5128/ccv5128_20260603T122558Z_04_illumina_hg002_kitchensink_multiqc_dryrun
/fsx/analysis_results/dyec5128/ccv5128_20260603T122558Z_05_ultima_snv_alignstats_dryrun
```

Remaining command-catalog analysis directories after cleanup:

```text
/fsx/analysis_results/dyec5128/ccv5128_20260603T122558Z_02_illumina_snv_alignstats
/fsx/analysis_results/dyec5128/ccv5128_20260603T122558Z_03_illumina_snv_alignstats_relatedness_vep_multiqc
/fsx/analysis_results/dyec5128/ccv5128_20260603T122558Z_04_illumina_hg002_kitchensink_multiqc
/fsx/analysis_results/dyec5128/ccv5128_20260603T122558Z_05_ultima_snv_alignstats
```

Those remaining directories are failed live runs and were not deleted by this
success-only cleanup.

## Code/Driver Changes Needed

| Area | Change Needed | Status |
|---|---|---|
| Validation driver | Force catalog `bin/day_run` commands through `source dyoainit; dy-a ...; dy-r ...` so DayOA is invoked through the required wrapper. | Implemented in this validation driver. |
| Validation driver | Run command batches with `--max-active 3` to reduce concurrent FSx pressure. | Implemented in this validation driver invocation. |
| DayOA tag | Retry failed live commands with catalog tag `2.0.41` once FSx pressure is acceptable. | Prepared but not launched because the user requested no more catalog jobs. |
| DayOA workflow | Fix/verify `produce_snv_concordances` benchmark failure: `AttributeError: 'NoneType' object has no attribute 'snakemake_threads'`. | Needed for failed Illumina live commands. |
| Environment cache | Promote newly built cache-miss envs/containers back to `/fsx/references/runtime_assets/cached_envs/{conda,containers}` if they should seed future clusters. | Needed to avoid repeated rebuilds; current boot script only symlinks existing cached assets forward. |
| Cyrius env | Resolve `cyrius_v0.1` conda/pip build failure or seed its env into cached runtime assets. | Needed for `illumina_hg002_kitchensink_multiqc`. |
