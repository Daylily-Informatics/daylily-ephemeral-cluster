# DAY-EC DayOA Command Catalog Validation Results

Generated: 2026-05-24T04:45:00Z

## Summary

This report covers the `fork-fixer` low-coverage DayOA command catalog validation run. The detailed execution ledger is `docs/plans/20260523T135957Z_fork_fixer_dayoa_catalog_recipe_validation_ledger.md`.

Five catalog recipes completed successfully end-to-end, one live recipe failed, and seven recipes were blocked or failed during dry-run/preflight before live compute was launched.

| Outcome | Count | Command IDs |
|---|---:|---|
| Success | 5 | `illumina_snv_alignstats`, `illumina_snv_alignstats_relatedness_vep_multiqc`, `ultima_snv_alignstats`, `ont_snv_alignstats`, `pacbio_snv_alignstats` |
| Live failure | 1 | `hybrid_ilmn_ont_snv` |
| Dry-run failed / live not run | 5 | `roche_snv_alignstats`, `illumina_run_qc`, `illumina_bclconvert`, `ont_run_qc`, `ultima_run_qc` |
| Blocked before live | 2 | `hybrid_ultima_ont_snv`, `complete_genomics_mgi_snv_concordance` |

The `hybrid_ilmn_ont_snv` failure was against the deprecated `sentdhiom` family. After the run, the DAY-EC catalog was corrected to use the production `sentdhiomr` family:

```bash
bin/day_run produce_snv_concordances produce_sentdhiomr_sv produce_sentdhiomr_snv_vcf --config 'dedupers=["dmd"]' -p -j 100 -k
```

That catalog correction was not part of the original fork-fixer validation run and does not change the historical run evidence below.

## Environment

| Field | Value |
|---|---|
| DAY-EC repo | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| DAY-EC branch | `codex/analysis-id-export-catalog-validation` |
| Base commit at run/report time | `6531a53070e8087a23f368b69e4b8c93cfd2dc53` |
| Local DAY-EC version | `4.1.3.dev0+g6531a5307.d20260523` |
| Headnode DAY-EC version | `4.1.2` |
| DayOA tag used for validation runs | `1.0.21` |
| DayOA commit in workflow clones | `c2ffe93` |
| AWS profile | `lsmc` |
| Region / AZ | `us-west-2` / `us-west-2d` |
| Cluster | `fork-fixer` |
| ParallelCluster version | `3.13.2` |
| Cluster status at final validation check | `CREATE_COMPLETE`; compute fleet `RUNNING` |
| Headnode | `i-031d99598446e6d56`, `r7i.2xlarge`, private IP `10.0.0.86`, public IP `44.227.78.165` |
| FSx file system | `fs-0b734921119395885`, 9600 GiB, DNS `fs-0b734921119395885.fsx.us-west-2.amazonaws.com`, mount name `kwiz7b4v` |
| FSx free space at final check | About `8.6T` free under `/fsx` |

## Result And Data Locations

All validation workflow result directories live under:

```text
/fsx/analysis_results/johnm
```

`/fsx/analysis_results/ubuntu` exists but was empty when inspected on 2026-05-24. The requested export source `/fsx/anaylsis_results/ubuntu` contains a spelling error and does not match where these validation outputs were written.

For a DRA export of these validation results, the corrected per-analysis destination pattern should be:

```text
s3://lsmc-ssf-sequencing-data/derived/fork-fixer/analysis_results/johnm/<analysis-id>/
```

The requested destination `s3://lsmc-ssf-sequencing-data/derived/<cluster-name>/analysis_results/ubnutu/**` also contains an entity spelling mismatch. No DRA export was run from the empty `ubuntu` source, and the S3 prefix `s3://lsmc-ssf-sequencing-data/derived/fork-fixer/analysis_results/` had `Total Objects: 0` at inspection time.

`dyec export` operates on one completed analysis directory at a time, for example:

```bash
dyec export \
  --cluster-name fork-fixer \
  --source-path /fsx/analysis_results/johnm/ff_illumina_fullqc_5x_1021 \
  --destination-s3-uri s3://lsmc-ssf-sequencing-data/derived/fork-fixer/analysis_results/johnm/ff_illumina_fullqc_5x_1021/ \
  --region us-west-2 \
  --profile lsmc \
  --output-dir tmp/fork-fixer-exports/ff_illumina_fullqc_5x_1021
```

Cluster deletion is destructive. It must remain blocked until after successful export verification and a separate explicit deletion confirmation.

## Source Inputs And Manifests

Generated local report/manifests are under:

```text
docs/plans/20260523T135957Z_fork_fixer_inputs/
```

| Mode | Input source | Manifest / context |
|---|---|---|
| Illumina HG003 5x | `s3://lsmc-dayoa-references-usw2/genomic_data/organism_reads_slim/H_sapiens/giab/NovaSeqX_WHGS_TruSeqPF_HG002-007/downsampled/HG003_5x_R1.fastq.gz` and `_R2.fastq.gz` | `illumina_hg003_5x.tsv` |
| ONT HG003 5x | `s3://lsmc-dayoa-references-usw2/genomic_data/organism_reads_slim/H_sapiens/giab/agbt_2026/ont/HG003_5x.cleaned.cram` plus `.crai` | `ont_hg003_5x.tsv` |
| Ultima HG003 5x | `s3://lsmc-dayoa-references-usw2/genomic_data/organism_reads_slim/H_sapiens/giab/agbt_2026/ug/HG003_5x.cleaned.cram` plus `.crai` | `ultima_hg003_5x.tsv` |
| PacBio HG003 5x | `s3://lsmc-dayoa-references-usw2/genomic_data/organism_reads_slim/H_sapiens/giab/agbt_2026/pacbio/HG003/R0-HG003-D0-0-D0/5p0x/HG003_5p0x.bam` plus `.bai` | `pacbio_hg003_5x.tsv` |
| Roche HG003 | Roche HG003 BAM/BAI, downsample requested with `ROCHE_DOWNSAMPLE_RATIO=0.086` | `roche_hg003_5x.tsv` |
| Hybrid ILMN+ONT | Illumina HG003 5x FASTQ plus ONT HG003 5x CRAM/CRAI | `hybrid_ilmn_ont_hg003_5x5x.tsv` |
| Hybrid Ultima+ONT | Ultima HG003 5x CRAM/CRAI plus ONT HG003 5x CRAM/CRAI | `hybrid_ultima_ont_hg003_5x5x.tsv` |
| CG/MGI candidate | `ML150002521_L01_UDB-386_1.fq.gz` and `_386_2.fq.gz` | `complete_genomics_mgi_hg003_candidate_blocked.tsv` |
| Illumina run context | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/` | `illumina_run_context.tsv`; DRA `dra-0a592634650dd2f5c` mounted at `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/` |
| ONT run context | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260513_ONT_HG003/` | `ont_run_context.tsv`; DRA `dra-08f17b5dc6c296b25` mounted at `/fsx/run_dir_mounts/20260513_ONT_HG003/` |
| Ultima run context | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/RUN602221/2026/602221-20260417_2346/` | `ultima_run_context_candidate.tsv`; DRA `dra-0d9808292112c9ed6` mounted at `/fsx/run_dir_mounts/602221-20260417_2346/` |

## Recipe Matrix

| Command ID | Catalog command run | Status | Stage / run context | Result directory or evidence |
|---|---|---|---|---|
| `illumina_snv_alignstats` | `bin/day_run produce_sent_align produce_dmd_dedup_cram produce_sentd_snv_vcf produce_snv_concordances produce_alignstats -p -k -j 20` | `SUCCESS` | `/fsx/staging/staged_sample_data/remote_stage_20260523T145944Z` | Success live result: `/fsx/analysis_results/johnm/ff_illumina_snv_alignstats_5x_1021_retry1`; first live attempt `/fsx/analysis_results/johnm/ff_illumina_snv_alignstats_5x_1021` failed during shared conda creation; dry-run result `/fsx/analysis_results/johnm/ff_illumina_snv_alignstats_5x_1021_dryrun` |
| `illumina_snv_alignstats_relatedness_vep_multiqc` | `bin/day_run produce_sent_align produce_dmd_dedup_cram produce_sentd_snv_vcf produce_alignstats produce_snv_concordances produce_relatedness produce_vep produce_multiqc_all --config 'multiqc_qc={"enable_tools":["vep"]}' -p -j 100 -k` | `SUCCESS` | `/fsx/staging/staged_sample_data/remote_stage_20260523T150351Z` | Live result: `/fsx/analysis_results/johnm/ff_illumina_fullqc_5x_1021`; dry-run result `/fsx/analysis_results/johnm/ff_illumina_fullqc_5x_1021_dryrun` |
| `ultima_snv_alignstats` | `bin/day_run produce_alignstats produce_na_dedup_cram produce_sentdug_snv_vcf produce_snv_concordances -p -j 20 -k` | `SUCCESS` | `/fsx/staging/staged_sample_data/remote_stage_20260523T151313Z` | Success live result: `/fsx/analysis_results/johnm/ff_ultima_snv_alignstats_5x_1021_retry1`; first live attempt `/fsx/analysis_results/johnm/ff_ultima_snv_alignstats_5x_1021` failed during shared conda creation; dry-run result `/fsx/analysis_results/johnm/ff_ultima_snv_alignstats_5x_1021_dryrun` |
| `ont_snv_alignstats` | `bin/day_run produce_alignstats produce_sentdont_snv_vcf produce_snv_concordances -p -j 5 -k` | `SUCCESS` | `/fsx/staging/staged_sample_data/remote_stage_20260523T150612Z` | Success live result: `/fsx/analysis_results/johnm/ff_ont_snv_alignstats_5x_1021_retry1`; first live attempt `/fsx/analysis_results/johnm/ff_ont_snv_alignstats_5x_1021` failed during shared conda creation; dry-run result `/fsx/analysis_results/johnm/ff_ont_snv_alignstats_5x_1021_dryrun` |
| `pacbio_snv_alignstats` | `bin/day_run produce_sentmm2_align produce_na_dedup_cram produce_sentdpb_snv_vcf produce_alignstats produce_snv_concordances -p -j 2 -k -T 1` | `SUCCESS` | `/fsx/staging/staged_sample_data/remote_stage_20260523T151638Z` | Success live result: `/fsx/analysis_results/johnm/ff_pacbio_snv_alignstats_5x_1021_retry1`; first live attempt `/fsx/analysis_results/johnm/ff_pacbio_snv_alignstats_5x_1021` failed during shared conda creation; dry-run result `/fsx/analysis_results/johnm/ff_pacbio_snv_alignstats_5x_1021_dryrun` |
| `roche_snv_alignstats` | `bin/day_run produce_alignstats produce_na_dedup_cram produce_rochehc_snv_vcf -p -j 5 -k` | `DRY_RUN_FAILED_LIVE_NOT_RUN` | `/fsx/staging/staged_sample_data/remote_stage_20260523T151947Z` | Dry-run result: `/fsx/analysis_results/johnm/ff_roche_snv_alignstats_5x_1021_dryrun`; live not launched |
| `hybrid_ilmn_ont_snv` | `bin/day_run produce_snv_concordances produce_sentdhiom_sv produce_sentdhiom_snv_vcf --config 'dedupers=["dmd"]' -p -j 100 -k` | `FAILED` | `/fsx/staging/staged_sample_data/remote_stage_20260523T152627Z` | Failed live result: `/fsx/analysis_results/johnm/ff_hybrid_ilmn_ont_snv_5x5x_1021_retry1`; first live attempt `/fsx/analysis_results/johnm/ff_hybrid_ilmn_ont_snv_5x5x_1021` failed during shared conda creation; dry-run result `/fsx/analysis_results/johnm/ff_hybrid_ilmn_ont_snv_5x5x_1021_dryrun` |
| `hybrid_ultima_ont_snv` | `bin/day_run produce_sentdhuom_snv_vcf produce_alignstats produce_snv_concordances -p -j 100 -k` | `BLOCKED` | `/fsx/staging/staged_sample_data/remote_stage_20260523T153033Z` | Live not launched; stage output collapsed distinct Ultima and ONT CRAM inputs to the same destination basename |
| `complete_genomics_mgi_snv_concordance` | `bin/day_run produce_sentcg_align produce_dmd_dedup_cram produce_cgt7p_snv_vcf produce_alignstats produce_snv_concordances -p -j 20 -k -T 1 --retries 0 --rerun-incomplete --keep-incomplete` | `BLOCKED` | `docs/plans/20260523T135957Z_fork_fixer_inputs/complete_genomics_mgi_hg003_candidate_blocked.tsv` | Live not launched; candidate mate pair was suspicious and no substitution was authorized |
| `illumina_run_qc` | `bin/day_run produce_illumina_run_qc -p -j 5 -k --config run_context_file=config/runs.tsv` | `DRY_RUN_FAILED_LIVE_NOT_RUN` | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/` | Dry-run result: `/fsx/analysis_results/johnm/ff_illumina_run_qc_1021_dryrun`; live not launched |
| `illumina_bclconvert` | `bin/day_run produce_bclconvert_fastqs_and_metrics -p -j 20 -k --config run_context_file=config/runs.tsv` | `DRY_RUN_FAILED_LIVE_NOT_RUN` | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/` | Dry-run result: `/fsx/analysis_results/johnm/ff_illumina_bclconvert_1021_dryrun`; live not launched |
| `ont_run_qc` | `bin/day_run produce_ont_run_qc -p -j 5 -k --config run_context_file=config/runs.tsv` | `DRY_RUN_FAILED_LIVE_NOT_RUN` | `/fsx/run_dir_mounts/20260513_ONT_HG003/` | Dry-run result: `/fsx/analysis_results/johnm/ff_ont_run_qc_1021_dryrun`; live not launched |
| `ultima_run_qc` | `bin/day_run produce_ultima_run_qc -p -j 5 -k --config run_context_file=config/runs.tsv` | `DRY_RUN_FAILED_LIVE_NOT_RUN` | `/fsx/run_dir_mounts/602221-20260417_2346/` | Dry-run result: `/fsx/analysis_results/johnm/ff_ultima_run_qc_1021_dryrun`; live not launched |

## Success Evidence

The five successful recipes all had `status.json exit_code=0`, no remaining Slurm jobs, and expected output files under `results/day/hg38_broad/` or `results/day/hg38/` inside the DayOA clone.

| Command ID | Completed session | Completed at | Key observed outputs |
|---|---|---|---|
| `illumina_snv_alignstats` | `ff_illumina_snv_alignstats_5x_1021_retry1` | `2026-05-23T16:17:24Z` | dmd CRAM/CRAI, sentd SNV VCF/TBI, alignstats JSON, concordance marker/log/report files |
| `illumina_snv_alignstats_relatedness_vep_multiqc` | `ff_illumina_fullqc_5x_1021` | `2026-05-23T16:33:40Z` | dmd CRAM/CRAI, sentd VCF/TBI, alignstats JSON, VEP VCF/TBI and summaries, relatedness reports, final `DAY_final_multiqc.html` and data |
| `ultima_snv_alignstats` | `ff_ultima_snv_alignstats_5x_1021_retry1` | `2026-05-23T16:11:32Z` | sentdug VCF/TBI, alignstats JSON, concordance marker/log/report files |
| `ont_snv_alignstats` | `ff_ont_snv_alignstats_5x_1021_retry1` | `2026-05-23T16:14:57Z` | sentdont SNV VCF/TBI, sentdont SV VCF/TBI, alignstats JSON, concordance marker/log/report files |
| `pacbio_snv_alignstats` | `ff_pacbio_snv_alignstats_5x_1021_retry1` | `2026-05-23T16:36:02Z` | sentmm2 CRAM/CRAI, alignstats JSON, sentdpb SNV VCF/TBI, sentdpb SV VCF/TBI, concordance marker/log/report files |

Several successful rows produced a `concordance.done.SKIPPED` sentinel because no ROI footprints were expanded from the staged truth directory. The workflow still completed successfully, but this is not evidence of populated ROI concordance content.

## Failures And Blockers

### `hybrid_ilmn_ont_snv`

This was the only true live workflow failure after a successful dry-run. It used the deprecated `sentdhiom` family:

```bash
bin/day_run produce_snv_concordances produce_sentdhiom_sv produce_sentdhiom_snv_vcf --config 'dedupers=["dmd"]' -p -j 100 -k
```

The retry session `ff_hybrid_ilmn_ont_snv_5x5x_1021_retry1` failed with `status.json exit_code=1` at `2026-05-23T16:12:13Z`. The failing rule was `sentdhiom_hybrid_select`. The log showed that `PATH` resolved `python` to base `/home/ubuntu/miniconda3/bin/python` (`Python 3.13.13`) instead of the active conda env Python under `/fsx/resources/environments/conda/.../820d63e.../bin/python`; importing `sentieon_cli.scripts` failed with `ModuleNotFoundError: No module named 'sentieon_cli'`.

Because `sentdhiom` is retired, this result should be treated as an invalid/deprecated-catalog test, not a production HIOMR failure. The DAY-EC catalog now points the ILMN+ONT hybrid command at:

```bash
bin/day_run produce_snv_concordances produce_sentdhiomr_sv produce_sentdhiomr_snv_vcf --config 'dedupers=["dmd"]' -p -j 100 -k
```

### `roche_snv_alignstats`

The Roche recipe staged and imported data, but dry-run failed before live execution. The dry-run attempted to pull or use:

- `docker://broadinstitute/gatk-nightly:2025-08-19-4.6.2.0-17-g2a1f41bf3-NIGHTLY-SNAPSHOT`
- `docker://roche/sbxd-small-variant-caller:latest`

It then failed while trying `conda info --json` inside missing image:

```text
/fsx/resources/environments/containers/ubuntu/ip-10-0-0-86/7a424a40c6fd659f4d052893dd3554fa.simg
```

Live Roche compute was not launched.

### `hybrid_ultima_ont_snv`

This row was blocked before live execution because the staged `units.tsv` collapsed distinct Ultima and ONT CRAM inputs to one destination basename:

```text
/fsx/staging/staged_sample_data/remote_stage_20260523T153033Z/FFHUO5X5X_HG003-ULTIMA-PF-gdna-UG5x-ONT5x_D0_0/HG003_5x.cleaned.cram
```

The S3 object at that destination was 5.26 GB, matching ONT, not the distinct 8.36 GB Ultima CRAM. No substitution was made.

### `complete_genomics_mgi_snv_concordance`

The candidate manifest mechanically passed DayEC precheck, but the apparent mate pair looked wrong: `_386_1` was 90.6 GB while `_386_2` was 10.8 GB, and a nearby `_388_2` object was 97.8 GB. Because the low-coverage input contract could not be trusted and no substitution was authorized, live execution was blocked.

### Run-context commands

The run-context commands all used mounted run directories and `--config run_context_file=config/runs.tsv`, but failed during dry-run before live execution:

| Command ID | Failure |
|---|---|
| `illumina_run_qc` | `WorkflowError`: `config/units.tsv` not found while loading common DayOA rules |
| `illumina_bclconvert` | `WorkflowError`: `No read pairs specified for analysis unit 20260514_LH01106_0009_B23TVLGLT4` |
| `ont_run_qc` | `WorkflowError`: `config/units.tsv` not found while loading common DayOA rules |
| `ultima_run_qc` | `WorkflowError`: `config/units.tsv` not found while loading common DayOA rules |

These look like DayOA run-analysis entrypoint/config-contract issues, not cluster or DRA mount failures.

## Code Changes Made After Validation

No production code changes were made to get the validation results. The validation was run against DayOA `1.0.21` as it existed at the time and the then-current DAY-EC catalog.

After the run, DAY-EC was updated so the catalog no longer launches retired `sentdhiom` targets for ILMN+ONT hybrid:

- `config/daylily_pipeline_command_catalog.yaml`
- `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`
- `tests/test_repository_catalog.py`
- `tests/test_staging_examples_live.py`

Focused verification:

```bash
pytest tests/test_repository_catalog.py tests/test_staging_examples_live.py
```

Result: `10 passed, 7 skipped`.

## Export And Delete Status

DRA export was not run in this pass because the requested source and destination paths do not match the actual output entity:

- Requested source: `/fsx/anaylsis_results/ubuntu`
- Correct spelling but empty source: `/fsx/analysis_results/ubuntu`
- Actual validation output root: `/fsx/analysis_results/johnm`
- Requested destination entity: `ubnutu`
- Corrected destination entity for these runs: `johnm`

The S3 prefix to use for the corrected export is:

```text
s3://lsmc-ssf-sequencing-data/derived/fork-fixer/analysis_results/johnm/<analysis-id>/
```

Because `dyec export` exports one completed analysis directory at a time, a corrected export would run once for each analysis directory that should be retained. After each export, the generated `fsx_export.yaml` receipt must show `status: success` and `detached: true`, and the matching S3 prefix should contain objects.

Cluster deletion remains blocked because it is destructive. Deleting `fork-fixer` would remove the ParallelCluster stack, headnode, compute fleet, and attached ephemeral FSx filesystem/cache. It should only proceed after corrected exports are successful and after a separate explicit confirmation.
