# tstVer4-1-1b DayOA Command Catalog Validation Results

Generated: 2026-05-25T20:04:39Z

## Summary

This report covers the `tstVer4-1-1b` low-coverage DayOA command catalog validation run. The execution ledger is `docs/plans/20260525T063158Z_tstver411b_dayoa_catalog_recipe_validation_ledger.md`.

The cluster was created successfully and the command matrix was executed serially where live execution was allowed. Six recipes completed end-to-end, six failed either during dry-run or live execution, and one recipe was blocked before execution because the input contract could not be verified.

| Outcome | Count | Command IDs |
|---|---:|---|
| `SUCCESS` | 6 | `illumina_snv_alignstats`, `illumina_snv_alignstats_relatedness_vep_multiqc`, `ultima_snv_alignstats`, `ont_snv_alignstats`, `pacbio_snv_alignstats`, `hybrid_ilmn_ont_snv` |
| `FAILED` | 6 | `roche_snv_alignstats`, `hybrid_ultima_ont_snv`, `illumina_run_qc`, `illumina_bclconvert`, `ont_run_qc`, `ultima_run_qc` |
| `BLOCKED` | 1 | `complete_genomics_mgi_snv_concordance` |

No retired non-`r` hybrid target was executed. `hybrid_ilmn_ont_snv` used `sentdhiomr` and succeeded. `hybrid_ultima_ont_snv` used the explicit `sentdhuomr` override, passed dry-run, launched live, and failed in `sentdhuomr_hybrid_select` because `python -c "from importlib.resources import files; ... files('sentieon_cli.scripts') ..."` resolved to base Python and raised `ModuleNotFoundError: No module named 'sentieon_cli'`.

## Environment

| Field | Value |
|---|---|
| DAY-EC repo | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| DAY-EC branch | `codex/analysis-id-export-catalog-validation` |
| DAY-EC HEAD | `012a3b5b30d2e69a07aa80dd4c224ad1ee26d3a4` |
| DAY-EC tag | `4.1.3` |
| Local DAY-EC version | `daylily-ephemeral-cluster 4.1.3.dev0+g6531a5307.d20260523` |
| Headnode DAY-EC version | `4.1.3` |
| DayOA tag | `1.0.21` |
| DayOA commit in workflow clones | `c2ffe93f246ff19c346f0a99e04fddc9e2712ff3` |
| AWS profile | `lsmc` |
| Region / AZ | `us-west-2` / `us-west-2d` |
| Cluster | `tstVer4-1-1b` |
| ParallelCluster version | `3.13.2` |
| Cluster status at final check | `CREATE_COMPLETE`; compute fleet `RUNNING` |
| Headnode | `i-0e08d1087dcce4d0a` |
| FSx | `fs-0445f465f1a8d6b48`, `12000` GiB requested, `/fsx` mounted with about `11T` available at final check |
| DRA | `/data/` DRA `dra-02c0d074383f04c9c`, `AVAILABLE` |
| Slurm final check | Queue empty; partitions `i8`, `i128`, `i192`, `i192mem`, `i192bigmem` present |
| Destructive actions | None. No teardown, export, deletion, or cleanup was performed. |

## Source Inputs And Local Manifests

Generated manifests and run contexts live under:

```text
docs/plans/20260525T063158Z_tstver411b_inputs/
```

| Mode | Input source | Local manifest / context |
|---|---|---|
| Illumina HG003 5x | `s3://lsmc-dayoa-omics-analysis-us-west-2/data/genomic_data/organism_reads/H_sapiens/giab/NovaSeqX_WHGS_TruSeqPF_HG002-007/downsampled/HG003_5x_R1.fastq.gz` and `_R2.fastq.gz` | `illumina_hg003_5x.tsv` |
| ONT HG003 5x | `s3://lsmc-dayoa-omics-analysis-us-west-2/data/genomic_data/organism_reads/H_sapiens/giab/agbt_2026/ont/HG003_5x.cleaned.cram` plus `.crai` | `ont_hg003_5x.tsv` |
| Ultima HG003 5x | `s3://lsmc-dayoa-omics-analysis-us-west-2/data/genomic_data/organism_reads/H_sapiens/giab/agbt_2026/ug/HG003_5x.cleaned.cram` plus `.crai` | `ultima_hg003_5x.tsv` |
| PacBio HG003 5x | `s3://lsmc-dayoa-omics-analysis-us-west-2/data/genomic_data/organism_reads/H_sapiens/giab/agbt_2026/pacbio/HG003/R0-HG003-D0-0-D0/5p0x/HG003_5p0x.bam` plus `.bai` | `pacbio_hg003_5x.tsv` |
| Roche HG003 | Roche HG003 BAM/BAI with `ROCHE_DOWNSAMPLE_RATIO=0.086` | `roche_hg003_5x.tsv` |
| Hybrid ILMN+ONT | Illumina HG003 5x FASTQ plus ONT HG003 5x CRAM/CRAI | `hybrid_ilmn_ont_hg003_5x5x.tsv` |
| Hybrid Ultima+ONT | Ultima HG003 5x CRAM/CRAI plus ONT HG003 5x CRAM/CRAI, with `STAGE_DIRECTIVE=pass_through` | `hybrid_ultima_ont_hg003_5x5x.tsv` |
| CG/MGI candidate | `ML150002521_L01_UDB-386_1.fq.gz` and `_386_2.fq.gz` candidate pair | `complete_genomics_mgi_hg003_candidate_blocked.tsv` |
| Illumina run context | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/` | `illumina_run_context.tsv`; DRA `dra-073d8c1fbda87df4d`, mounted at `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/` |
| ONT run context | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260513_ONT_HG003/` | `ont_run_context.tsv`; DRA `dra-062bb9457a8117d57`, mounted at `/fsx/run_dir_mounts/20260513_ONT_HG003/` |
| Ultima run context | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/RUN602221/2026/602221-20260417_2346/` | `ultima_run_context_candidate.tsv`; DRA `dra-0a246cd72f629eeef`, mounted at `/fsx/run_dir_mounts/602221-20260417_2346/` |

Hybrid Ultima+ONT input validation passed the no-collision gate before dry-run: the generated TSVs preserved distinct paths and sizes for UG `/fsx/references/.../ug/HG003_5x.cleaned.cram` at `8,356,213,863` bytes and ONT `/fsx/references/.../ont/HG003_5x.cleaned.cram` at `5,260,585,144` bytes.

CG/MGI remained blocked because the candidate mate-pair contract was not trustworthy: `_386_1` was `90,600,002,744` bytes, `_386_2` was `10,794,018,984` bytes, and nearby `_388_2` was `97,844,317,264` bytes. No substitution was authorized.

## Recipe Matrix

| Command ID | Exact command run | Input manifest/context | Stage/run context | Dry-run result | Live result | Evidence | Fork-fixer comparison |
|---|---|---|---|---|---|---|---|
| `illumina_snv_alignstats` | `bin/day_run produce_sent_align produce_dmd_dedup_cram produce_sentd_snv_vcf produce_snv_concordances produce_alignstats -p -k -j 20` | `illumina_hg003_5x.tsv` | `/fsx/staging/staged_sample_data/remote_stage_20260525T071517Z` | `SUCCESS`, `tvb_illumina_snv_alignstats_5x_1021_dryrun`, `exit_code=0` | `SUCCESS`, `tvb_illumina_snv_alignstats_5x_1021`, completed `2026-05-25T09:20:32Z`, `exit_code=0` | `/fsx/analysis_results/johnm/tvb_illumina_snv_alignstats_5x_1021/daylily-omics-analysis/results/day/hg38_broad/`; 2 CRAM, 1 VCF, 15 alignstats matches, 7 concordance matches | Reproduced success |
| `illumina_snv_alignstats_relatedness_vep_multiqc` | `bin/day_run produce_sent_align produce_dmd_dedup_cram produce_sentd_snv_vcf produce_alignstats produce_snv_concordances produce_relatedness produce_vep produce_multiqc_all --config 'multiqc_qc={"enable_tools":["vep"]}' -p -j 100 -k` | `illumina_hg003_5x.tsv` | `/fsx/staging/staged_sample_data/remote_stage_20260525T072540Z` | `SUCCESS`, `tvb_illumina_related_vep_multiqc_5x_1021_dryrun`, `exit_code=0` | `SUCCESS`, `tvb_illumina_related_vep_multiqc_5x_1021`, completed `2026-05-25T10:10:02Z`, `exit_code=0` | `/fsx/analysis_results/johnm/tvb_illumina_related_vep_multiqc_5x_1021/daylily-omics-analysis/results/day/hg38_broad/`; 2 CRAM, 52 VCF, 17 alignstats, 8 concordance, 36 MultiQC, 7 relatedness matches | Reproduced success |
| `ultima_snv_alignstats` | `bin/day_run produce_alignstats produce_na_dedup_cram produce_sentdug_snv_vcf produce_snv_concordances -p -j 20 -k` | `ultima_hg003_5x.tsv` | `/fsx/staging/staged_sample_data/remote_stage_20260525T072907Z` | `SUCCESS`, `tvb_ultima_snv_alignstats_5x_1021_dryrun`, `exit_code=0` | `SUCCESS`, `tvb_ultima_snv_alignstats_5x_1021`, completed `2026-05-25T10:18:07Z`, `exit_code=0` | `/fsx/analysis_results/johnm/tvb_ultima_snv_alignstats_5x_1021/daylily-omics-analysis/results/day/hg38_broad/`; 1 VCF, 11 alignstats matches, 7 concordance matches | Reproduced success |
| `ont_snv_alignstats` | `bin/day_run produce_alignstats produce_sentdont_snv_vcf produce_snv_concordances -p -j 5 -k` | `ont_hg003_5x.tsv` | `/fsx/staging/staged_sample_data/remote_stage_20260525T073112Z` | `SUCCESS`, `tvb_ont_snv_alignstats_5x_1021_dryrun`, `exit_code=0` | `SUCCESS`, `tvb_ont_snv_alignstats_5x_1021`, completed `2026-05-25T10:34:37Z`, `exit_code=0` | `/fsx/analysis_results/johnm/tvb_ont_snv_alignstats_5x_1021/daylily-omics-analysis/results/day/hg38_broad/`; 2 VCF, 11 alignstats matches, 7 concordance matches | Reproduced success |
| `pacbio_snv_alignstats` | `bin/day_run produce_sentmm2_align produce_na_dedup_cram produce_sentdpb_snv_vcf produce_alignstats produce_snv_concordances -p -j 2 -k -T 1` | `pacbio_hg003_5x.tsv` | `/fsx/staging/staged_sample_data/remote_stage_20260525T073306Z` | `SUCCESS`, `tvb_pacbio_snv_alignstats_5x_1021_dryrun`, `exit_code=0` | `SUCCESS`, `tvb_pacbio_snv_alignstats_5x_1021`, completed `2026-05-25T11:12:49Z`, `exit_code=0` | `/fsx/analysis_results/johnm/tvb_pacbio_snv_alignstats_5x_1021/daylily-omics-analysis/results/day/hg38_broad/`; 1 CRAM, 2 VCF, 11 alignstats matches, 7 concordance matches | Reproduced success |
| `roche_snv_alignstats` | `bin/day_run produce_alignstats produce_na_dedup_cram produce_rochehc_snv_vcf -p -j 5 -k` | `roche_hg003_5x.tsv` | `/fsx/staging/staged_sample_data/remote_stage_20260525T073504Z` | `FAILED`, `tvb_roche_snv_alignstats_5x_1021_dryrun`, completed `2026-05-25T07:39:43Z`, `exit_code=1` | Live not launched | Missing Singularity image `/fsx/resources/environments/containers/ubuntu/ip-10-0-0-103/7a424a40c6fd659f4d052893dd3554fa.simg` while preparing containerized Roche/GATK environment | Reproduced dry-run failure |
| `hybrid_ilmn_ont_snv` | `bin/day_run produce_snv_concordances produce_sentdhiomr_sv produce_sentdhiomr_snv_vcf --config 'dedupers=["dmd"]' -p -j 100 -k` | `hybrid_ilmn_ont_hg003_5x5x.tsv` | `/fsx/staging/staged_sample_data/remote_stage_20260525T074001Z` | `SUCCESS`, `tvb_hybrid_ilmn_ont_snv_5x5x_1021_dryrun`, `exit_code=0` | `SUCCESS`, `tvb_hybrid_ilmn_ont_snv_5x5x_1021`, completed `2026-05-25T19:32:57Z`, `exit_code=0` | `/fsx/analysis_results/johnm/tvb_hybrid_ilmn_ont_snv_5x5x_1021/daylily-omics-analysis/results/day/hg38_broad/`; final `sentdhiomr.snv.sort.vcf.gz` and `.tbi`, `sentdhiomr.sv.vcf.gz` and `.tbi`, 7 concordance matches | Resolved by `r`-suffix hybrid use; fork-fixer old `sentdhiom` live failure no longer applies |
| `hybrid_ultima_ont_snv` | `bin/day_run produce_sentdhuomr_snv_vcf produce_alignstats produce_snv_concordances -p -j 100 -k` | `hybrid_ultima_ont_hg003_5x5x.tsv` | `/fsx/staging/staged_sample_data/remote_stage_20260525T074404Z` | `SUCCESS`, `tvb_hybrid_ultima_ont_snv_5x5x_1021_dryrun`, `exit_code=0` | `FAILED`, `tvb_hybrid_ultima_ont_snv_5x5x_1021`, completed `2026-05-25T19:59:00Z`, `exit_code=1` | Failure rule `sentdhuomr_hybrid_select`; Slurm jobs `878`/`879`; stderr: `ModuleNotFoundError: No module named 'sentieon_cli'` during `files('sentieon_cli.scripts').joinpath('hybrid_select.py')`; rule log only had the start marker and no benchmark was written | New/uncovered after `r`-suffix plus pass-through staging; fork-fixer was blocked before live by staging basename collision |
| `complete_genomics_mgi_snv_concordance` | `bin/day_run produce_sentcg_align produce_dmd_dedup_cram produce_cgt7p_snv_vcf produce_alignstats produce_snv_concordances -p -j 20 -k -T 1 --retries 0 --rerun-incomplete --keep-incomplete` | `complete_genomics_mgi_hg003_candidate_blocked.tsv` | Not staged | `BLOCKED` before dry-run | Live not launched | Candidate mate pair not verified: `_386_1` `90,600,002,744` bytes, `_386_2` `10,794,018,984` bytes, nearby `_388_2` `97,844,317,264` bytes | Reproduced blocker |
| `illumina_run_qc` | `bin/day_run produce_illumina_run_qc -p -j 5 -k --config run_context_file=config/runs.tsv` | `illumina_run_context.tsv` | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/` | `FAILED`, `tvb_illumina_run_qc_1021_dryrun`, completed `2026-05-25T08:50:20Z`, `exit_code=1` | Live not launched | `WorkflowError ... The units table was not found at .../config/units.tsv. Create config/units.tsv or set --config units_table=/path/to/units.tsv.` | Reproduced run-context config-contract failure |
| `illumina_bclconvert` | `bin/day_run produce_bclconvert_fastqs_and_metrics -p -j 20 -k --config run_context_file=config/runs.tsv` | `illumina_run_context.tsv` | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/` | `FAILED`, `tvb_illumina_bclconvert_1021_dryrun`, completed `2026-05-25T08:51:13Z`, `exit_code=1` | Live not launched | `WorkflowError ... No read pairs specified for analysis unit 20260514_LH01106_0009_B23TVLGLT4.` | Reproduced run-context config-contract failure |
| `ont_run_qc` | `bin/day_run produce_ont_run_qc -p -j 5 -k --config run_context_file=config/runs.tsv` | `ont_run_context.tsv` | `/fsx/run_dir_mounts/20260513_ONT_HG003/` | `FAILED`, `tvb_ont_run_qc_1021_dryrun`, completed `2026-05-25T08:52:05Z`, `exit_code=1` | Live not launched | `WorkflowError ... The units table was not found at .../config/units.tsv. Create config/units.tsv or set --config units_table=/path/to/units.tsv.` | Reproduced run-context config-contract failure |
| `ultima_run_qc` | `bin/day_run produce_ultima_run_qc -p -j 5 -k --config run_context_file=config/runs.tsv` | `ultima_run_context_candidate.tsv` | `/fsx/run_dir_mounts/602221-20260417_2346/` | `FAILED`, `tvb_ultima_run_qc_1021_dryrun`, completed `2026-05-25T08:52:58Z`, `exit_code=1` | Live not launched | `WorkflowError ... The units table was not found at .../config/units.tsv. Create config/units.tsv or set --config units_table=/path/to/units.tsv.` | Reproduced run-context config-contract failure |

## Success Evidence

All six successful recipes had a dry-run `exit_code=0`, live `status.json exit_code=0`, no remaining Slurm jobs after completion, and expected outputs under `/fsx/analysis_results/johnm/<analysis-id>/daylily-omics-analysis/results/day/hg38_broad/`.

| Command ID | Live analysis ID | Completed at | Key observed outputs |
|---|---|---|---|
| `illumina_snv_alignstats` | `tvb_illumina_snv_alignstats_5x_1021` | `2026-05-25T09:20:32Z` | CRAM/CRAI, sentd SNV VCF/TBI, alignstats files, concordance files |
| `illumina_snv_alignstats_relatedness_vep_multiqc` | `tvb_illumina_related_vep_multiqc_5x_1021` | `2026-05-25T10:10:02Z` | CRAM/CRAI, sentd VCF/TBI, VEP outputs, alignstats, concordance, MultiQC, relatedness |
| `ultima_snv_alignstats` | `tvb_ultima_snv_alignstats_5x_1021` | `2026-05-25T10:18:07Z` | sentdug VCF/TBI, alignstats, concordance |
| `ont_snv_alignstats` | `tvb_ont_snv_alignstats_5x_1021` | `2026-05-25T10:34:37Z` | sentdont SNV/SV VCF/TBI, alignstats, concordance |
| `pacbio_snv_alignstats` | `tvb_pacbio_snv_alignstats_5x_1021` | `2026-05-25T11:12:49Z` | sentmm2 CRAM/CRAI, sentdpb SNV/SV VCF/TBI, alignstats, concordance |
| `hybrid_ilmn_ont_snv` | `tvb_hybrid_ilmn_ont_snv_5x5x_1021` | `2026-05-25T19:32:57Z` | `sentdhiomr` SNV VCF/TBI, `sentdhiomr` SV VCF/TBI, concordance |

## Failures And Blockers

### `hybrid_ultima_ont_snv`

This row used the intended `sentdhuomr` rule family and did not run retired `sentdhuom`.

```bash
bin/day_run produce_sentdhuomr_snv_vcf produce_alignstats produce_snv_concordances -p -j 100 -k
```

The dry-run passed and live execution started from `/fsx/staging/staged_sample_data/remote_stage_20260525T074404Z`. The live session `tvb_hybrid_ultima_ont_snv_5x5x_1021` failed with `status.json exit_code=1` at `2026-05-25T19:59:00Z`.

The failing rule was `sentdhuomr_hybrid_select` for chromosome shard `1-24`. It requested `threads=8`, `mem_mb=16000`, and partition `i192mem,i192bigmem`. Slurm external jobs `878` and `879` failed. The rule log itself only contained:

```text
Starting hybrid_select pipeline at Mon May 25 19:58:48 UTC 2026
```

The Slurm stderr contained the actual Python import failure:

```text
HYBRID_SELECT=$(python -c "from importlib.resources import files; print(files('sentieon_cli.scripts').joinpath('hybrid_select.py'))")
...
File "/home/ubuntu/miniconda3/lib/python3.13/importlib/resources/_common.py", line 82, in _
  return importlib.import_module(cand)
ModuleNotFoundError: No module named 'sentieon_cli'
```

That means the live failure is no longer the previous staging basename collision. The `r`-suffix command reached a real `sentdhuomr` execution point and then failed because the Python used by the rule could not import `sentieon_cli`.

### `roche_snv_alignstats`

Roche failed in dry-run before live execution. The exact missing image path was:

```text
/fsx/resources/environments/containers/ubuntu/ip-10-0-0-103/7a424a40c6fd659f4d052893dd3554fa.simg
```

This reproduces the fork-fixer Roche dry-run failure pattern and points at container/Singularity materialization rather than sample staging or Slurm capacity.

### Run-context Commands

The run-context DRAs mounted and were `AVAILABLE`, but all run-context recipes failed during dry-run before live execution.

| Command ID | Failure |
|---|---|
| `illumina_run_qc` | `WorkflowError ... The units table was not found at .../config/units.tsv. Create config/units.tsv or set --config units_table=/path/to/units.tsv.` |
| `illumina_bclconvert` | `WorkflowError ... No read pairs specified for analysis unit 20260514_LH01106_0009_B23TVLGLT4.` |
| `ont_run_qc` | `WorkflowError ... The units table was not found at .../config/units.tsv. Create config/units.tsv or set --config units_table=/path/to/units.tsv.` |
| `ultima_run_qc` | `WorkflowError ... The units table was not found at .../config/units.tsv. Create config/units.tsv or set --config units_table=/path/to/units.tsv.` |

These are reproduced DayOA run-analysis config-contract failures, not cluster creation or DRA availability failures.

### `complete_genomics_mgi_snv_concordance`

This row was not run. The candidate mate-pair sizes were inconsistent enough that executing would have been a silent substitution risk:

```text
ML150002521_L01_UDB-386_1.fq.gz  90,600,002,744 bytes
ML150002521_L01_UDB-386_2.fq.gz  10,794,018,984 bytes
nearby _388_2 candidate          97,844,317,264 bytes
```

Because the exact valid mate pair was not verified, the row remained `BLOCKED`.

## Cluster And Data Location Notes

All validation workflow outputs were written under:

```text
/fsx/analysis_results/johnm/
```

No DRA export or S3 export was in scope for this plan and none was performed. The cluster was intentionally left running:

```text
clusterStatus: CREATE_COMPLETE
computeFleetStatus: RUNNING
headNode: i-0e08d1087dcce4d0a
```

Final read-only check at `2026-05-25T20:04:08Z` showed `/fsx` mounted, about `11T` available, and an empty Slurm queue.
