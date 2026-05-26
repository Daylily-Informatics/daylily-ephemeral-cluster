# hyb-hg003 HG003 Altair3 HIOMR Experiment Report

Generated: 2026-05-26T15:33:26Z

## Executive Summary

This report covers the HG003 Altair Run 3 Illumina + ONT solo and hybrid `sentdhiomr` experiment on cluster `hyb-hg003` in `lsmc/us-west-2`.

The completed FSx-to-S3 export for the remaining on-FSx run directories succeeded. Because `hyb-hg003` already had FSx DRA `dra-0b1de8c1eeed5bf1a` mapping `/analysis_results/ubuntu/` to `s3://lsmc-ssf-sequencing-data/derived/hyb-hg003/analysis_results/`, the exported S3 prefixes do not include an extra `ubuntu/` path component.

Export task:

- FSx file system: `fs-04fb08a9a0d8a6752`
- DRA: `dra-0b1de8c1eeed5bf1a`
- Export task: `task-066ca115e7646531d`
- Status: `SUCCEEDED`
- Files: `29852` total, `29852` succeeded, `0` failed
- Export report path: `s3://lsmc-ssf-sequencing-data/derived/hyb-hg003/analysis_results/_daylily_monitor/fsx-export/20260526T150944Z/export-report/`

Cluster deletion was not executed. Deleting `hyb-hg003` is destructive and still requires a separate explicit confirmation.

## Versions And Runtime

| Component | Version / Commit | Evidence |
|---|---|---|
| Cluster | `hyb-hg003` | Existing DAY-EC cluster, profile `lsmc`, region `us-west-2` |
| DAY-EC worktree used for export/report | `4.1.15-2-g22fb2780-dirty`, commit `22fb2780a25c0777678692aadcfb26b49e97a766` | Local `git describe` / `git rev-parse` |
| DayOA for 2026-05-26 HIOMR matrix runs | tag family `1.0.24`, checked-out commit `fb4f0340b2c841053bba10fa79c345e84e683721` | Exported run `.git/HEAD`; tag `1.0.24` object present |
| Genome | `hg38_broad` | Run output path and `day_cmd.log` |
| Hybrid rule family | `sentdhiomr` | Run commands used `produce_sentdhiomr_snv_vcf`; retired `sentdhiom` was not used for the matrix runs |

Earlier solo and first hybrid attempts from 2026-05-23 were launched under the then-active DayOA tag sequence recorded in `docs/plans/20260523T004101Z_hyb_hg003_hg003_dayoa_1018_validation_ledger.md`; the final exported 2026-05-26 matrix clones are DayOA `1.0.24` checkouts.

## Input Data Provenance

Full staged data was created from HG003-a Illumina Altair Run 3 plus an existing HG003 ONT 30x CRAM.

| Data | Original / staged source |
|---|---|
| Illumina run | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/` |
| Illumina sample | `HG003-a`, `20260514_ILMN_Altair_Run_3`, 8 BCLConvert R1/R2 lane pairs |
| Staged full Illumina data | `/fsx/staging/staged_external_sequencing_data/remote_stage_20260522T203135Z/20260514-LH01106-0009-B23TVLGLT4_HG003-a-NOVASEQ-PF-gdna-20260514-ILMN-Altair-Run-3_HG003-a_0/lane1..lane8/` |
| ONT full CRAM | `/fsx/staging/staged_external_sequencing_data/remote_stage_20260522T203135Z/20260514-LH01106-0009-B23TVLGLT4_HG003-a-NOVASEQ-PF-gdna-20260514-ILMN-Altair-Run-3_HG003-a_0/HG003_30x.cleaned.cram` |
| Downsampled ILMN / ONT matrix root | `/fsx/analysis_results/johnm/staged_sample_data/hg003_altair_ont_hiomr_matrix_20260523T141028Z/downsampled/` |
| Matrix manifests | `/fsx/analysis_results/johnm/staged_manifests/hg003_altair_ont_hiomr_matrix_20260523T141028Z/` |
| Truth / concordance data | `/fsx/staging/staged_external_sequencing_data/remote_stage_20260522T203135Z/20260514-LH01106-0009-B23TVLGLT4_HG003-a-NOVASEQ-PF-gdna-20260514-ILMN-Altair-Run-3_HG003-a_0/concordance_data` |

For hybrid matrix rows, `config/units.tsv` points to downsampled ILMN FASTQs such as `.../downsampled/ilmn/HG003-a/20x/HG003-a_Altair_Run3_20x_R1.fastq.gz` and downsampled ONT CRAMs such as `.../downsampled/ont/HG003-a/10x/HG003-a_ONT_10x.cram`.

The hybrid alignstats emitted ONT `na` and `dmd` coverage JSONs. The short-read coverage reported below is therefore the intended downsample target encoded in `units.tsv`; actual short-read-only hybrid alignstats were not emitted as a separate JSON in these runs.

## Results Matrix

GIAB HC metrics are `Precision / Sensitivity / F-measure` from `_giabHC/summary.txt` when present.

| Run | Short | Long | Status | GIAB HC P/S/F | Top-level final VCFs | S3 prefix |
|---|---:|---:|---|---|---:|---|
| `hg003a_altair3_ilmn_full_1021` | full | n/a | SUCCESS | `0.9993 / 0.9788 / 0.9889` | 1 VCF + index | `s3://lsmc-ssf-sequencing-data/derived/hyb-hg003/analysis_results/hg003a_altair3_ilmn_full_1021/` |
| `hg003a_altair3_ont_full_1021` | n/a | full | SUCCESS | `0.9861 / 0.7279 / 0.8375` | SNV VCF + SV VCF + indexes | `s3://lsmc-ssf-sequencing-data/derived/hyb-hg003/analysis_results/hg003a_altair3_ont_full_1021/` |
| `hg003a_altair3_hiomr_full_1021` | full | full | SUCCESS | `0.9990 / 0.9943 / 0.9966` | 1 HIOMR SNV VCF + index | `s3://lsmc-ssf-sequencing-data/derived/hyb-hg003/analysis_results/hg003a_altair3_hiomr_full_1021/` |
| `hg003a_altair3_hiomr_full_1022` | full | full | SUCCESS | `0.9990 / 0.9942 / 0.9966` | 1 HIOMR SNV VCF + index | `s3://lsmc-ssf-sequencing-data/derived/hyb-hg003/analysis_results/hg003a_altair3_hiomr_full_1022/` |
| `hg003a_altair3_hiomr_ilmn20x_ont10x_1022` | 20x | 10x | SUCCESS | `0.9984 / 0.9927 / 0.9956` | 1 HIOMR SNV VCF + index | `s3://lsmc-ssf-sequencing-data/derived/hyb-hg003/analysis_results/hg003a_altair3_hiomr_ilmn20x_ont10x_1022/` |
| `hg003a_altair3_hiomr_ilmn20x_ont7x_1022` | 20x | 7x | SUCCESS | `0.9986 / 0.9917 / 0.9951` | 1 HIOMR SNV VCF + index | `s3://lsmc-ssf-sequencing-data/derived/hyb-hg003/analysis_results/hg003a_altair3_hiomr_ilmn20x_ont7x_1022/` |
| `hg003a_altair3_hiomr_ilmn20x_ont5x_1022` | 20x | 5x | SUCCESS | `0.9985 / 0.9904 / 0.9944` | 1 HIOMR SNV VCF + index | `s3://lsmc-ssf-sequencing-data/derived/hyb-hg003/analysis_results/hg003a_altair3_hiomr_ilmn20x_ont5x_1022/` |
| `hg003a_altair3_hiomr_ilmn15x_ont10x_1022` | 15x | 10x | SUCCESS | `0.9980 / 0.9927 / 0.9953` | 1 HIOMR SNV VCF + index | `s3://lsmc-ssf-sequencing-data/derived/hyb-hg003/analysis_results/hg003a_altair3_hiomr_ilmn15x_ont10x_1022/` |
| `hg003a_altair3_hiomr_ilmn15x_ont7x_1022` | 15x | 7x | SUCCESS | `0.9981 / 0.9917 / 0.9949` | 1 HIOMR SNV VCF + index | `s3://lsmc-ssf-sequencing-data/derived/hyb-hg003/analysis_results/hg003a_altair3_hiomr_ilmn15x_ont7x_1022/` |
| `hg003a_altair3_hiomr_ilmn15x_ont5x_1022` | 15x | 5x | CANCELLED | n/a | none final; intermediate shard/tmp VCFs exported | `s3://lsmc-ssf-sequencing-data/derived/hyb-hg003/analysis_results/hg003a_altair3_hiomr_ilmn15x_ont5x_1022/` |
| `hg003a_altair3_hiomr_ilmn10x_ont10x_1022` | 10x | 10x | FAILED | n/a | final HIOMR SNV VCF existed before concordance failure | `s3://lsmc-ssf-sequencing-data/derived/hyb-hg003/analysis_results/hg003a_altair3_hiomr_ilmn10x_ont10x_1022/` |
| `hg003a_altair3_hiomr_ilmn7x_ont7x_1022` | 7x | 7x | FAILED | `0.9946 / 0.9891 / 0.9918` | final HIOMR SNV VCF existed before later ROI failure | `s3://lsmc-ssf-sequencing-data/derived/hyb-hg003/analysis_results/hg003a_altair3_hiomr_ilmn7x_ont7x_1022/` |
| `hg003a_altair3_hiomr_ilmn7x_ont5x_1022` | 7x | 5x | CANCELLED | n/a | none final; intermediate shard/tmp VCFs exported | `s3://lsmc-ssf-sequencing-data/derived/hyb-hg003/analysis_results/hg003a_altair3_hiomr_ilmn7x_ont5x_1022/` |
| `hg003a_altair3_hiomr_ilmn5x_ont5x_1022` | 5x | 5x | CANCELLED | n/a | none final; intermediate shard/tmp VCFs exported | `s3://lsmc-ssf-sequencing-data/derived/hyb-hg003/analysis_results/hg003a_altair3_hiomr_ilmn5x_ont5x_1022/` |

## Failed And Cancelled Attempts

`hg003a_altair3_hiomr_ilmn10x_ont10x_1022` failed in `rtg_vcfeval_roi` for the `_giabHC` concordance ROI after the top-level `sentdhiomr` SNV VCF and index had been produced. The rule log contains:

```text
Reference sequence chrX is used in calls but not in baseline.
rtg: line 299: ... Killed "$RTG_JAVA" ...
```

`hg003a_altair3_hiomr_ilmn7x_ont7x_1022` failed in `rtg_vcfeval_roi` for `_clinvar_genes`. GIAB HC concordance had already completed, and the same RTG/Java kill signature was present:

```text
Reference sequence chrX is used in calls but not in baseline.
rtg: line 299: ... Killed "$RTG_JAVA" ...
```

The 15x/5x, 7x/5x, and 5x/5x matrix rows were cancelled when the user asked to kill all active runs at 2026-05-26T15:06Z. They were exported for forensics, but they did not complete final merge/concordance and do not have top-level final `sentdhiomr.snv.sort.vcf.gz` outputs.

## Variant Call Files

Top-level final VCFs are under each run's S3 prefix at:

```text
daylily-omics-analysis/results/day/hg38_broad/<sample>/align/<aligner>/<deduper>/snv/<caller>/
```

Key final file patterns:

- Illumina solo: `*.sent.na.sentd.snv.sort.vcf.gz` and `.tbi`
- ONT solo: `*.ont.na.sentdont.snv.sort.vcf.gz`, `*.ont.na.sentdont.sv.vcf.gz`, and indexes
- Hybrid HIOMR: `*.ont.dmd.sentdhiomr.snv.sort.vcf.gz` and `.tbi`

Cancelled rows also exported intermediate per-chromosome and temporary files under `.../snv/sentdhiomr/vcfs/*/tmp/`, but those are not final callsets.

## Export Evidence

Primary export receipt files:

- `reports/fsx_exports/hyb-hg003_hiomr_matrix_20260526T150944Z/existing_dra_bulk/fsx_existing_dra_export.yaml`
- `reports/fsx_exports/hyb-hg003_hiomr_matrix_20260526T150944Z/existing_dra_bulk/latest_task.json`
- `reports/hyb_hg003_hiomr_matrix_20260526T150944Z_s3_inventory.final.json`
- `reports/hyb_hg003_hiomr_matrix_20260526T150944Z_parsed_summary.tsv`

The initial per-directory `dyec export` attempt was blocked before creating an export task because the requested source path overlapped the existing DRA at `/analysis_results/ubuntu/`. The successful export used `aws fsx create-data-repository-task` directly against the existing association.

## Commands

### Staging Full HG003 Inputs

The exact staging command recorded in the staging ledger was:

```bash
dyec samples stage tmp/hg003_hybrid_30x_staging/analysis_samples_hg003a_ilmn30x_ont30x_hybrid.tsv \
  --reference-s3-uri s3://lsmc-dayoa-references-usw2 \
  --profile lsmc \
  --region us-west-2 \
  --config-dir tmp/hg003_hybrid_30x_staging/staged_config
```

The resulting staged prefix was:

```text
s3://lsmc-ssf-sequencing-data/staged_external_data/remote_stage_20260522T203135Z/
```

### Create Matrix Downsamples

The exported artifacts preserve the downsampled products and generated TSVs, but not a single original shell script for the matrix downsampling step. The reproducible command pattern is:

```bash
STAGE_ROOT=/fsx/staging/staged_external_sequencing_data/remote_stage_20260522T203135Z/20260514-LH01106-0009-B23TVLGLT4_HG003-a-NOVASEQ-PF-gdna-20260514-ILMN-Altair-Run-3_HG003-a_0
MATRIX_ROOT=/fsx/analysis_results/johnm/staged_sample_data/hg003_altair_ont_hiomr_matrix_20260523T141028Z

mkdir -p "$MATRIX_ROOT/downsampled/ilmn/HG003-a/{5x,7x,10x,15x,20x}"
mkdir -p "$MATRIX_ROOT/downsampled/ont/HG003-a/{5x,7x,10x}"

# ILMN: subsample lane-concatenated R1/R2 streams to target coverage.
# Use the same random seed for each mate at a given target.
zcat "$STAGE_ROOT"/lane*/HG003-a_*_R1_001.fastq.gz | seqtk sample -s 23 - <fraction> | gzip -c > "$MATRIX_ROOT/downsampled/ilmn/HG003-a/<target>/HG003-a_Altair_Run3_<target>_R1.fastq.gz"
zcat "$STAGE_ROOT"/lane*/HG003-a_*_R2_001.fastq.gz | seqtk sample -s 23 - <fraction> | gzip -c > "$MATRIX_ROOT/downsampled/ilmn/HG003-a/<target>/HG003-a_Altair_Run3_<target>_R2.fastq.gz"

# ONT: subsample CRAM to target coverage and index.
samtools view -@ 16 -T /fsx/references/genomic_data/organism_references/H_sapiens/hg38_broad/Homo_sapiens_assembly38.fasta \
  -bs <fraction> "$STAGE_ROOT/HG003_30x.cleaned.cram" |
  samtools sort -@ 16 -O cram -T /fsx/tmp/HG003_ONT_<target> \
  -o "$MATRIX_ROOT/downsampled/ont/HG003-a/<target>/HG003-a_ONT_<target>.cram"
samtools index "$MATRIX_ROOT/downsampled/ont/HG003-a/<target>/HG003-a_ONT_<target>.cram"
```

### Create `samples.tsv` And `units.tsv`

The matrix TSVs were written under:

```text
/fsx/analysis_results/johnm/staged_manifests/hg003_altair_ont_hiomr_matrix_20260523T141028Z/
```

Representative generation pattern:

```bash
MANIFEST_DIR=/fsx/analysis_results/johnm/staged_manifests/hg003_altair_ont_hiomr_matrix_20260523T141028Z
MATRIX_ROOT=/fsx/analysis_results/johnm/staged_sample_data/hg003_altair_ont_hiomr_matrix_20260523T141028Z
TRUTH_DIR=/fsx/staging/staged_external_sequencing_data/remote_stage_20260522T203135Z/20260514-LH01106-0009-B23TVLGLT4_HG003-a-NOVASEQ-PF-gdna-20260514-ILMN-Altair-Run-3_HG003-a_0/concordance_data

mkdir -p "$MANIFEST_DIR"

cat > "$MANIFEST_DIR/hiomr_ilmn20x_ont10x_samples.tsv" <<'EOF'
SAMPLEID	SAMPLESOURCE	SAMPLECLASS	BIOLOGICAL_SEX	CONCORDANCE_CONTROL_PATH	IS_POSITIVE_CONTROL	IS_NEGATIVE_CONTROL	SAMPLE_TYPE	TUM_NRM_SAMPLEID_MATCH	EXTERNAL_SAMPLE_ID	N_X	N_Y	TRUTH_DATA_DIR
HG003-a	blood	research	male	TRUTH_DIR	true	false	gdna	na	HG003	1	1	TRUTH_DIR
EOF

cat > "$MANIFEST_DIR/hiomr_ilmn20x_ont10x_units.tsv" <<'EOF'
RUNID	SAMPLEID	EXPERIMENTID	LANEID	BARCODEID	LIBPREP	SEQ_VENDOR	SEQ_PLATFORM	ILMN_R1_PATH	ILMN_R2_PATH	PACBIO_R1_PATH	PACBIO_R2_PATH	ONT_R1_PATH	ONT_R2_PATH	UG_R1_PATH	UG_R2_PATH	SUBSAMPLE_PCT	ILMN_TRIM_READ_LENGTH	SAMPLEUSE	BWA_KMER	DEEP_MODEL	ULTIMA_CRAM	ULTIMA_CRAM_ALIGNER	ULTIMA_CRAM_SNV_CALLER	ONT_CRAM	ONT_CRAM_ALIGNER	ONT_CRAM_SNV_CALLER	PB_BAM	PB_BAM_ALIGNER	PB_BAM_SNV_CALLER	ROCHE_BAM	ROCHE_BAM_ALIGNER	ROCHE_BAM_SNV_CALLER	ROCHE_DOWNSAMPLE_RATIO	LONGREADTRIM_READ_LENGTH	LONGREADTRIM_MODE	ULTIMA_SUBSAMPLE_PCT	ONT_SUBSAMPLE_PCT	ONT_BAM	ONT_BAM_ALIGNER	ONT_BAM_SNV_CALLER
20260514-LH01106-0009-B23TVLGLT4-HIOMR-ILMN20X-ONT10X	HG003-a	20260514-Altair3-ONT-HIOMR-ILMN20x-ONT10x	0	HG003-a	PF	ILMN	NOVASEQ	/fsx/analysis_results/johnm/staged_sample_data/hg003_altair_ont_hiomr_matrix_20260523T141028Z/downsampled/ilmn/HG003-a/20x/HG003-a_Altair_Run3_20x_R1.fastq.gz	/fsx/analysis_results/johnm/staged_sample_data/hg003_altair_ont_hiomr_matrix_20260523T141028Z/downsampled/ilmn/HG003-a/20x/HG003-a_Altair_Run3_20x_R2.fastq.gz							na		posControl	19	WGS				/fsx/analysis_results/johnm/staged_sample_data/hg003_altair_ont_hiomr_matrix_20260523T141028Z/downsampled/ont/HG003-a/10x/HG003-a_ONT_10x.cram	ont	sentdont											na			
EOF
```

Replace `20x` / `10x` path and `RUNID` fields for the other matrix cells.

### Launch Analyses

Common launch pattern:

```bash
set -euo pipefail
day-clone -t 1.0.24 -d <analysis-id>
cd /fsx/analysis_results/ubuntu/<analysis-id>/daylily-omics-analysis
cp <samples.tsv> config/samples.tsv
cp <units.tsv> config/units.tsv
source dyoainit
source bin/day_activate slurm hg38_broad
```

Illumina solo:

```bash
bin/day_run produce_alignstats produce_sentd_snv_vcf produce_snv_concordances \
  --config 'aligners=["sent"]' 'dedupers=["na"]' \
  -p -j 100 -k -T 0 --rerun-triggers mtime --max-jobs-per-second 8
```

ONT solo:

```bash
bin/day_run produce_alignstats produce_sentdont_snv_vcf produce_snv_concordances \
  -p -j 5 -k -T 0 --rerun-triggers mtime --max-jobs-per-second 8
```

Hybrid HIOMR full / successful 2026-05-26 matrix rows:

```bash
bin/day_run produce_alignstats produce_sentdhiomr_snv_vcf produce_snv_concordances \
  --config 'dedupers=["dmd"]' \
  -p -j 234 -k -T 0 --rerun-triggers mtime --max-jobs-per-second 8
```

Hybrid HIOMR retry/current cancelled or failed matrix rows:

```bash
bin/day_run produce_alignstats produce_sentdhiomr_snv_vcf produce_snv_concordances \
  --config 'dedupers=["dmd"]' \
  -p -j 190 -k -T 0 --rerun-triggers mtime --max-jobs-per-second 8
```

### Monitor Analyses

```bash
dyec workflow status --profile lsmc --region us-west-2 --cluster hyb-hg003 --analysis-id <analysis-id>
dyec workflow logs --profile lsmc --region us-west-2 --cluster hyb-hg003 --analysis-id <analysis-id>
dyec headnode jobs --profile lsmc --region us-west-2 --cluster hyb-hg003
```

On the headnode:

```bash
squeue -u ubuntu
tail -n 100 /fsx/analysis_results/ubuntu/<analysis-id>/daylily-omics-analysis/daylily_run_*.log
cat /fsx/analysis_results/ubuntu/<analysis-id>/daylily-omics-analysis/day_cmd.log
```

### Export FSx To S3

The successful bulk export command shape was:

```bash
aws fsx create-data-repository-task \
  --profile lsmc \
  --region us-west-2 \
  --file-system-id fs-04fb08a9a0d8a6752 \
  --type EXPORT_TO_REPOSITORY \
  --paths \
    /analysis_results/ubuntu/hg003a_altair3_hiomr_ilmn15x_ont5x_1022/ \
    /analysis_results/ubuntu/hg003a_altair3_hiomr_ilmn10x_ont10x_1022/ \
    /analysis_results/ubuntu/hg003a_altair3_hiomr_ilmn7x_ont7x_1022/ \
    /analysis_results/ubuntu/hg003a_altair3_hiomr_ilmn7x_ont5x_1022/ \
    /analysis_results/ubuntu/hg003a_altair3_hiomr_ilmn5x_ont5x_1022/ \
  --report Enabled=true,Path=s3://lsmc-ssf-sequencing-data/derived/hyb-hg003/analysis_results/_daylily_monitor/fsx-export/20260526T150944Z/export-report/,Format=REPORT_CSV_20191124,Scope=FAILED_FILES_ONLY
```

Monitor export:

```bash
aws fsx describe-data-repository-tasks \
  --profile lsmc \
  --region us-west-2 \
  --task-ids task-066ca115e7646531d
```

Verify S3:

```bash
aws s3 ls --profile lsmc --region us-west-2 --recursive \
  s3://lsmc-ssf-sequencing-data/derived/hyb-hg003/analysis_results/<analysis-id>/ \
  --summarize --human-readable
```

### Delete Cluster

Not executed. Destructive command to run only after separate explicit confirmation:

```bash
dyec delete --profile lsmc --region us-west-2 --cluster hyb-hg003
```
