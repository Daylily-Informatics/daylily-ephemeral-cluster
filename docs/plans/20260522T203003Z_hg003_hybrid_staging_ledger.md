# HG003 Illumina + ONT Hybrid Staging Ledger

## Scope

Create and validate a DayEC `analysis_samples.tsv` manifest for a full-coverage HG003 Illumina run dataset from the LSMC sequencing-data bucket, and stage the data into the DayOA reference bucket for later hybrid analysis.

Buckets:

- Sequencing source: `s3://lsmc-ssf-sequencing-data/`
- Reference/staging target: `s3://lsmc-dayoa-omics-analysis-us-west-2/`

## Source Selection

| Source | Evidence |
| --- | --- |
| Illumina run | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/` |
| Run name | `20260514_ILMN_Altair_Run_3` from `SampleSheet.csv` |
| Sample selected | `HG003-a`, sample sheet index pair `TACACAGAGT` / `TACCGGGACA` |
| Illumina FASTQs | 8 ordered R1/R2 BCLConvert lane pairs under `Analysis/1/Data/BCLConvert/fastq/`, each R1 about `6.2 GiB` and R2 about `6.4 GiB`. |
| ONT hybrid source | Existing reference-bucket CRAM `/fsx/control_data/genomic_data/organism_reads/H_sapiens/giab/agbt_2026/ont/HG003_30x.cleaned.cram` with `.crai` present. Prior compatibility validation recorded this CRAM as readable against `hg38_broad`. |
| GIAB truth | `s3://lsmc-dayoa-omics-analysis-us-west-2/data/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG003/` |

## Artifacts

| Artifact | Path |
| --- | --- |
| Source analysis manifest | `tmp/hg003_hybrid_30x_staging/analysis_samples_hg003a_ilmn30x_ont30x_hybrid.tsv` |
| Generated samples TSV | `tmp/hg003_hybrid_30x_staging/staged_config/20260522T203135Z_samples.tsv` |
| Generated units TSV | `tmp/hg003_hybrid_30x_staging/staged_config/20260522T203135Z_units.tsv` |
| Remote stage prefix | `s3://lsmc-dayoa-omics-analysis-us-west-2/fsx/staging/staged_sample_data/remote_stage_20260522T203135Z/` |
| Headnode stage path for future clusters | `/fsx/staging/staged_sample_data/remote_stage_20260522T203135Z/` |

## Execution Rows

| Row | Status | Action | Evidence |
| --- | --- | --- | --- |
| `INV-001` | `SUCCESS` | Inventory candidate HG003 Illumina run and ONT hybrid source. | `SampleSheet.csv` for Run 3 confirmed `HG003-a`, `HG003-b`, and `HG003-c`; selected `HG003-a`. S3 listing confirmed 16 `HG003-a` lane FASTQs. Reference bucket listing confirmed `HG003_30x.cleaned.cram` and `.crai`. |
| `MAN-001` | `SUCCESS` | Create DayEC analysis manifest for HG003-a ILMN + ONT hybrid staging. | Manifest has 31 tab-separated columns and one data row. `ILMN_R1_FQ` and `ILMN_R2_FQ` each contain 8 comma-separated S3 URIs in lane order; `ONT_CRAM` points to the reference-bucket HG003 30x CRAM visible as `/fsx/references/...`. |
| `PRE-001` | `SUCCESS` | Validate manifest without staging. | `dyec samples stage ... --precheck-only` returned `Precheck passed: rows checked=1, samples checked=1, source objects checked=33, concordance directories checked=1.` |
| `STAGE-001` | `SUCCESS` | Stage manifest to the DayOA reference bucket. | `dyec samples stage tmp/hg003_hybrid_30x_staging/analysis_samples_hg003a_ilmn30x_ont30x_hybrid.tsv --reference-s3-uri s3://lsmc-dayoa-omics-analysis-us-west-2 --profile lsmc --region us-west-2 --config-dir tmp/hg003_hybrid_30x_staging/staged_config` completed. Remote stage prefix: `remote_stage_20260522T203135Z`. |
| `VER-001` | `SUCCESS` | Verify staged S3 prefix and generated config. | `aws s3 ls ... --recursive --summarize --human-readable` found `67` objects totaling `125.8 GiB`. Generated `samples.tsv` and `units.tsv` each have 2 lines. The generated units TSV contains one `HG003-a` row with comma-separated staged `/fsx/references/.../lane1` through `lane8` R1/R2 FASTQ paths and staged ONT CRAM path. |

## Final Status

The HG003-a Illumina + HG003 30x ONT hybrid staging set is ready in the reference bucket. A future DRA-backed cluster can use:

- stage dir: `/fsx/staging/staged_sample_data/remote_stage_20260522T203135Z/`
- samples TSV: `/fsx/staging/staged_sample_data/remote_stage_20260522T203135Z/20260522T203135Z_samples.tsv`
- units TSV: `/fsx/staging/staged_sample_data/remote_stage_20260522T203135Z/20260522T203135Z_units.tsv`
