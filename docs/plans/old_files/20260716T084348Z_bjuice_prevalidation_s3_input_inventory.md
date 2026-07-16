# BJuice Prevalidation S3 Input Inventory

Timestamp: `2026-07-16T08:43:48Z`

Scope: source-backed input locations for the full-instrument Illumina Betelgeuse prevalidation data used by `HG001`-`HG007` and the three SMN12-positive controls `NA19235`, `NA20775`, and `NA23687`, plus the matching ONT flow cells. This is an inventory only. No S3 object, DRA, mount, FSx path, or workflow state was created, copied, changed, or deleted.

Coverage boundary: **full Illumina** means all eight BCLConvert lane pairs (`L001`-`L008`, R1 and R2) from the run below. The raw ONT flow-cell prefixes below are the full source cells. Later Gate C BJuice manifests for `HG001`-`HG003` intentionally select terminal-hour suffixes `0..23` and therefore must not be described as full-ONT manifests.

## Canonical Illumina source

- Run: `20260618_LH01106_0011_A23MFMCLT3`
- Experiment recorded by the controlling manifests: `20260618_ILMN_Betelgeuse_Preval`
- Run URI: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/`
- BCLConvert FASTQ URI: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/Analysis/1/Data/BCLConvert/fastq/`
- Instrument/run sample sheet: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/SampleSheet.csv`
- BCLConvert sample-sheet copy: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/Analysis/1/Data/BCLConvert/SampleSheet.csv`
- Intermediate analysis copy: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/Analysis/1/Data/SampleSheet.csv`

Read-only `head-object` evidence shows all three `SampleSheet.csv` objects are `3197` bytes with ETag `069d349a1d1480a9389a561ce811ae15`; the root copy was last modified `2026-06-19T01:01:47Z`, and both analysis copies were last modified `2026-06-19T18:33:05Z`.

Every row below has exactly eight R1 and eight R2 objects under the BCLConvert FASTQ URI. The verified object-name form is `<sample>_S<index>_L001..L008_R1|R2_001.fastq.gz`.

| Sample | Role | BCLConvert identifier | Full Illumina lane pairs |
|---|---|---|---:|
| `HG001` | GIAB | `HG001_S14` | 8 |
| `HG002` | GIAB | `HG002_S15` | 8 |
| `HG003` | GIAB | `HG003_S16` | 8 |
| `HG004` | GIAB | `HG004_S17` | 8 |
| `HG005` | GIAB | `HG005_S18` | 8 |
| `HG006` | GIAB | `HG006_S19` | 8 |
| `HG007` | GIAB | `HG007_S20` | 8 |
| `NA19235` | SMN12 positive; expected SMN1/SMN2 `4/0` | `NA19235_S11` | 8 |
| `NA20775` | SMN12 positive; expected SMN1/SMN2 `3/1` | `NA20775_S12` | 8 |
| `NA23687` | SMN12 positive; expected SMN1/SMN2 `1/2` | `NA23687_S13` | 8 |

## Matching ONT flow cells

The exact raw cell URIs below were direct-listed with AWS profile `lsmc` on `2026-07-16`. Sample membership is the barcode selection recorded in the full-coverage source manifests and the successful five-sample SMN12 hybrid analysis.

| ONT set/cell | Exact S3 URI | Matching samples and barcodes |
|---|---|---|
| Set3 FC1 | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set3-FC1/` | `NA19235=barcode11`; `NA20775=barcode12` |
| Set3 FC2 | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set3-FC2/` | `NA19235=barcode11`; `NA20775=barcode12` |
| Set3 FC3 | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set3-FC3/` | `NA19235=barcode11`; `NA20775=barcode12` |
| Set4 FC1 | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set4-FC1/` | `NA23687=barcode13`; `HG001=barcode14`; `HG002=barcode15`; `HG003=barcode16` |
| Set4 FC2 | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set4-FC2/` | `NA23687=barcode13`; `HG001=barcode14`; `HG002=barcode15`; `HG003=barcode16` |
| Set4 FC3 | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set4-FC3/` | `NA23687=barcode13`; `HG001=barcode14`; `HG002=barcode15`; `HG003=barcode16` |
| Set5 FC1 | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set5-FC1/` | `HG004=barcode17`; `HG005=barcode18`; `HG006=barcode19`; `HG007=barcode20` |
| Set5 FC2 | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set5-FC2/` | `HG004=barcode17`; `HG005=barcode18`; `HG006=barcode19`; `HG007=barcode20` |
| Set5 FC3 | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set5-FC3/` | `HG004=barcode17`; `HG005=barcode18`; `HG006=barcode19`; `HG007=barcode20` |

Full-source manifest counts are `438` ONT FASTQs per GIAB sample across three cells. The successful full-source SMN12 hybrid manifest records `438` for `NA19235`, `436` for `NA20775`, and `438` for `NA23687`; these totals include every available matching pass/fail FASTQ selected by that manifest. The two-object shortfall for `NA20775` is recorded evidence, not an inferred replacement path.

## Controlling manifests and sample sheets

### HG001-HG007 full-source manifests

These are the combined controlling source manifests for the full-instrument Illumina plus all matching ONT source FASTQs:

- `/Users/jmajor/projects/lsmc/docs/plans/20260625T024425Z_vclu_hg001_007_hiomr_full_coverage_artifacts/samples.tsv`
- `/Users/jmajor/projects/lsmc/docs/plans/20260625T024425Z_vclu_hg001_007_hiomr_full_coverage_artifacts/units.tsv`
- `/Users/jmajor/projects/lsmc/docs/plans/20260625T024425Z_vclu_hg001_007_hiomr_full_coverage_artifacts/source_inventory.tsv`
- `/Users/jmajor/projects/lsmc/docs/plans/20260625T024425Z_vclu_hg001_007_hiomr_full_coverage_artifacts/ont_barcode_mapping.tsv`
- `/Users/jmajor/projects/lsmc/docs/plans/20260625T024425Z_vclu_hg001_007_hiomr_full_coverage_artifacts/manifest_summary.tsv`
- `/Users/jmajor/projects/lsmc/docs/plans/20260625T024425Z_vclu_hg001_007_hiomr_full_coverage_artifacts/ilmn_fastq_summary.tsv`

Later BJuice Gate C operational manifests exist for `HG001`-`HG003`; they keep all eight Illumina lane pairs but select ONT terminal-hour suffixes `0..23` (`144` ONT paths per sample). They are exact current examples for that bounded Gate C run, not replacements for the full-ONT source inventory:

- `HG001`: `/Users/jmajor/projects/lsmc/daylily-omics-analysis/docs/plans/20260713T025500Z_bjuice_hg001_hg002_full_manifests/HG001.samples.tsv` and `/Users/jmajor/projects/lsmc/daylily-omics-analysis/docs/plans/20260713T025500Z_bjuice_hg001_hg002_full_manifests/HG001.units.tsv`
- `HG002`: `/Users/jmajor/projects/lsmc/daylily-omics-analysis/docs/plans/20260713T025500Z_bjuice_hg001_hg002_full_manifests/HG002.samples.tsv` and `/Users/jmajor/projects/lsmc/daylily-omics-analysis/docs/plans/20260713T025500Z_bjuice_hg001_hg002_full_manifests/HG002.units.tsv`
- `HG003`: `/Users/jmajor/projects/lsmc/daylily-omics-analysis/docs/plans/20260711T210404Z_hg003_bjuice_fullilmn_ont24h_gate_c_artifacts/samples.tsv` and `/Users/jmajor/projects/lsmc/daylily-omics-analysis/docs/plans/20260711T210404Z_hg003_bjuice_fullilmn_ont24h_gate_c_artifacts/units.tsv`

### Three SMN12-positive controls

The latest source-backed full hybrid manifest is the successful five-sample analysis `smn12_hg38_hybrid_sentsegdup_5sample_20260704T231239Z`. Its exact exported controls are:

- `s3://lsmc-ssf-sequencing-data/derived/analysis_results/cluster_fsx_bulk_export/20260705T050809Z/jemx3/jemx3/smn12_hg38_hybrid_sentsegdup_5sample_20260704T231239Z/daylily-omics-analysis/config/samples.tsv`
- `s3://lsmc-ssf-sequencing-data/derived/analysis_results/cluster_fsx_bulk_export/20260705T050809Z/jemx3/jemx3/smn12_hg38_hybrid_sentsegdup_5sample_20260704T231239Z/daylily-omics-analysis/config/units.tsv`
- `s3://lsmc-ssf-sequencing-data/derived/analysis_results/cluster_fsx_bulk_export/20260705T050809Z/jemx3/jemx3/smn12_hg38_hybrid_sentsegdup_5sample_20260704T231239Z/daylily-omics-analysis/config/manifest_summary.tsv`

Read-only S3 listing verified these at `2563`, `392564`, and `1126` bytes respectively, all last modified `2026-07-05T05:34:42Z`. The source analysis records seven source run directories: Set3 FC1/FC2/FC3, Set4 FC1/FC2/FC3, and the Illumina run.

Local precursor/control evidence:

- `/Users/jmajor/projects/lsmc/docs/plans/20260704T231239Z_smn12_hg38_hybrid_sentieon_segdup_ledger.md`
- `/Users/jmajor/projects/lsmc/docs/plans/20260704T231239Z_smn12_hg38_hybrid_sentieon_segdup_artifacts/input_inventory_summary.tsv`
- `/Users/jmajor/projects/lsmc/docs/plans/20260702T082019Z_shortreadonly_smn12_artifacts/samples.tsv`
- `/Users/jmajor/projects/lsmc/docs/plans/20260702T082019Z_shortreadonly_smn12_artifacts/units.tsv`
- `/Users/jmajor/projects/lsmc/docs/plans/20260708T060825Z_dewey_dayoa_s3_inventory_artifacts/dewey_analysis_source_seq_run_dirs.tsv`
- `/Users/jmajor/projects/lsmc/docs/plans/20260708T060825Z_dewey_dayoa_s3_inventory_artifacts/dewey_parent_candidates.with_source_seq_run_dirs.tsv`

## Recent real Ultima example

The newest run-name date currently visible under the canonical `basecalls/lsmc/ssf-hq/RUN*/2026/` S3 roots is:

- Run URI: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/RUN602202/2026/602202-20260512_1805/`
- Run-level library/sample manifest (the Ultima sample-sheet equivalent): `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/RUN602202/2026/602202-20260512_1805/602202_LibraryInfo.xml`
- Exact sample-level metadata example: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/RUN602202/2026/602202-20260512_1805/602202-KPF011_1-Z0157-CATGGATAGCTGCAGAT/602202-KPF011_1-Z0157-CATGGATAGCTGCAGAT.json`

Live read-only evidence: the run prefix contains `9541` listed objects. `602202_LibraryInfo.xml` is `3715` bytes, content type `application/xml`, ETag `8b140061ba67be17c5a21e75696e9ade`, last modified `2026-05-15T03:22:00Z`. The sample JSON is `2554823` bytes, ETag `6c58146c4b1ffc785c0ad4b54773c2a3`, last modified `2026-05-15T01:09:38Z`.

The June 2026 Ultima candidates `604729-20260617_2146`, `605029-20260618_0043`, `602228-20260618_1513`, and `602230-20260618_1147` were recorded as transfer-failed/unresolved in `/Users/jmajor/projects/lsmc/docs/plans/20260621T230921Z_recent_seqrun_runqc_solo_hybrid_artifacts/candidate_runs.tsv`. No exact S3 URI is asserted for them here. Their current canonical S3 location remains **unknown** rather than guessed.

## Read-only verification record

Commands used were limited to local `rg`, `find`, TSV parsing, `git status`, and AWS read APIs with `--profile lsmc`:

- `aws s3api list-objects-v2` for the Betelgeuse run, nine ONT flow-cell roots, the SMN12 exported config, and canonical Ultima `RUN*/2026/` roots.
- `aws s3api head-object` for the three Illumina sample-sheet objects, the Ultima `602202_LibraryInfo.xml`, and the sample-level Ultima JSON example.
- `aws sts get-caller-identity --profile lsmc` confirmed account `108782052779` before the read-only checks.

No `aws s3 cp`, `sync`, `mv`, or `rm`; no `put-object`, multipart upload, delete API, DRA/mount command, FSx access, or workflow command was run.
