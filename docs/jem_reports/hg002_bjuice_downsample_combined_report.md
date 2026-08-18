# HG002 Bjuice native-SR × LR measured-coverage matrix report

## Direct-S3 coverage sanity table

| ID | target ILMNx | SR ILMNx | RSR ILMNx | target ONTx | LRONTx |
| --- | ---: | ---: | ---: | ---: | ---: |
| E1:p5xp5 | 0.5× | 43.73× | 8.54× | 0.5× | 0.57× |
| E1:1x1 | 1× | 43.73× | 9.85× | 1× | 1.16× |
| E1:3x3 | 3× | 43.73× | 11.93× | 3× | 4.09× |
| E1:5x5 | 5× | 43.73× | 12.71× | 5× | 6.20× |
| E1:10x5 | 10× | 43.73× | 13.65× | 5× | 9.67× |
| E1:15x5 | 15× | 43.73× | 14.01× | 5× | 11.43× |
| E1:15x10 | 15× | 43.73× | 13.65× | 10× | 9.67× |
| E3:10xby10x | 9.85× | 10.81× | 3.72× | 9.67× | 9.67× |
| E3:12xby12x | 12.71× | 13.83× | 4.77× | 11.43× | 11.43× |
| E3:20xby15x | 20× | 21.33× | 7.36× | 15× | 14.71× |
| E3:30xby15x | 30× | 31.12× | 10.50× | 15× | 14.71× |
| P1:fullcov | NA | 43.73× | 14.01× | NA | 11.43× |

This is the only report table that presents requested coverage targets. All values were re-read from the three completed analysis exports on S3 at the summary-file level; the full paths and SHA-256 values are available in [direct_s3_coverage_regather.tsv](hg002_bjuice_downsample_combined_report_assets/tables/direct_s3_coverage_regather.tsv).

## Technical summary

This report contains **12 direct-S3-audited observations**: E1 (seven AUs), E3 (four AUs), and P1 (one full-input AU).

Every coverage-positioned figure uses **measured native SR×** on its vertical axis and **measured LR×** on its horizontal axis, with equal numeric scale. RSR× is audit-only. The strongest retained tagged-TrussSV global F-score is **0.7382** at **E3:20xby15x**. Successful benchmark task rows sum to **$201.27** for E1, **$108.52** for E3, **$31.46** for P1.

E1 is **not a valid two-axis Illumina downsampling series**: every direct-S3 native-SR summary is exactly 43.73× (and has the same SHA-256), despite the AU-specific declared fractions. It is retained as a full-SR / variable-LR experiment. E3 supplies the actual variable-native-SR observations; P1 is a distinct full-input observation.

RSR is not a conventional random Illumina downsample. The E1 Sentieon hybrid log shows stage 3 running on a generated `hybrid_stage2.bed` interval set, followed by `hybrid_transfer` from the full SR alignment into `g_sr_realigned.cram`. Its retained-record fraction and Mosdepth therefore vary with the hybrid-selected regions and LR input. The 8.54–14.01× E1 RSR range is expected to differ from the uniform 43.73× native-SR evidence and must not form a coverage-matrix axis.

## Source S3 URIs

| Source | S3 URI |
| --- | ---: |
| Shared full-prevalence Illumina FASTQs | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/Analysis/1/Data/BCLConvert/fastq/` |
| Shared HG002 ONT FC1 source | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set4-FC1/20260615_ONT_Set4-FC1/20260616_0048_3A_PBM08268_14b096e3/` |
| Shared HG002 ONT FC2 source | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set4-FC2/20260615_ONT_Set4-FC2/20260616_0040_3B_PBK89197_822a87b5/` |
| Shared HG002 ONT FC3 source | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set4-FC3/20260615_ONT_Set4-FC3/20260616_0041_3C_PBK89101_bd86eaac/` |
| E1 completed output export | `s3://lsmc-dayoa-analysis-results-usw2/derived/bjuice-v2-multi-analysis-unit/prod-cand-1703/prod-cand-1703-hg002-bjuice-v2-multiau-20260814T114522Z/daylily-omics-analysis/` |
| E3 completed output export | `s3://lsmc-dayoa-analysis-results-usw2/derived/bjuice-v2-multi-analysis-unit/prod-cand-1703/prod-cand-1703-hg002-bjuice-4au-kitchensink-20260817T025004Z/daylily-omics-analysis/` |
| P1 completed output export | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022-bjuice-preval6-15014-dry-20260817t112900z/daylily-omics-analysis/` |

The exact S3 roots and every direct summary-file URI are recorded in [source_s3_uris.tsv](hg002_bjuice_downsample_combined_report_assets/tables/source_s3_uris.tsv) and [direct_s3_coverage_regather.tsv](hg002_bjuice_downsample_combined_report_assets/tables/direct_s3_coverage_regather.tsv).

## Measured native-SR × LR availability

The circle centers below are placed at their actual numeric native-SR× and LR× values; x and y use the same coverage-unit scale. The in-circle value is the retained-observation count, and [coverage_grid.tsv](hg002_bjuice_downsample_combined_report_assets/tables/coverage_grid.tsv) lists the corresponding AU(s). Dashed contours show two-dimensional density of retained AU coordinates only; they do not interpolate any coverage or metric into blank space. This exposes E1 as a vertical full-SR series instead of falsely spreading it across nominal Illumina positions.

![combined_measured_coverage_grid.png](hg002_bjuice_downsample_combined_report_assets/figures/combined_measured_coverage_grid.png)

### Retained observation provenance

| Observation | measured SR ILMNx | measured RSR ILMNx (audit only) | measured LRONTx | ONT hours | Runtime AU |
| --- | ---: | ---: | ---: | ---: | ---: |
| E1:p5xp5 | 43.73× | 8.54× | 0.57× | [0,1) | HG002-082hc3dnbehb1c |
| E1:1x1 | 43.73× | 9.85× | 1.16× | [0,2) | HG002-98xq4xrqz7dwy9 |
| E1:3x3 | 43.73× | 11.93× | 4.09× | [0,7) | HG002-871vyxbnp4n81v |
| E1:5x5 | 43.73× | 12.71× | 6.20× | [0,11) | HG002-vqs89p8gahfwf9 |
| E1:10x5 | 43.73× | 13.65× | 9.67× | [0,19) | HG002-fjg1n22920ymw4 |
| E1:15x5 | 43.73× | 14.01× | 11.43× | [0,24) | HG002-bq765db79mczvn |
| E1:15x10 | 43.73× | 13.65× | 9.67× | [0,19) | HG002-f277f1cckvy1xb |
| E3:10xby10x | 10.81× | 3.72× | 9.67× | [0,19) | HG002-nxw0jbvh1h5mqx |
| E3:12xby12x | 13.83× | 4.77× | 11.43× | [0,24) | HG002-nfjdv62wjc8dwr |
| E3:20xby15x | 21.33× | 7.36× | 14.71× | [0,36) | HG002-wesenyqd5xz29g |
| E3:30xby15x | 31.12× | 10.50× | 14.71× | [0,36) | HG002-q73e7s390m0hjt |
| P1:fullcov | 43.73× | 14.01× | 11.43× | [0,24) | HG002-qvmjccyp5fr1y3 |

The retained-observation table has native-SR, RSR, LR, source paths, and selection provenance without repeating the requested targets: [retained_observations.tsv](hg002_bjuice_downsample_combined_report_assets/tables/retained_observations.tsv).

## Measured ONT coverage and runtime

This is descriptive aligned LR yield versus cumulative input runtime. It uses measured LR× only; the lines connect experiment-specific hour means and are not a fitted yield model.

![ont_coverage_vs_runtime.png](hg002_bjuice_downsample_combined_report_assets/figures/ont_coverage_vs_runtime.png)


## Hard-VCF GIAB high-confidence concordance

Crude SNP uses `SNPts + SNPtv/2` independently for TP, FN, and FP; precision, recall, and F-score are recalculated from those composite counts. Each color map uses the same equal-scale numeric native-SR×/LR× plane. Every 25%-larger circle prints its own plotted metric and has no colored edge. Dashed contours show retained-AU coordinate density only, not interpolated metric values. When multiple observations share a measured coordinate, both the circle color and printed value are their arithmetic mean; the metric TSV keeps unaggregated values.

### SNP (SNPts + SNPtv/2)

F-score, false-negative, false-positive, and precision–recall views below all use the direct-S3 measured coverage contract; no RSR or nominal coverage is used to position an observation.

![hard_vcf_giabhc_snp_fscore_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_snp_fscore_heatmap.png)

![hard_vcf_giabhc_snp_fn_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_snp_fn_heatmap.png)

![hard_vcf_giabhc_snp_fp_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_snp_fp_heatmap.png)

![hard_vcf_giabhc_snp_precision_recall.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_snp_precision_recall.png)

### INS_50

F-score, false-negative, false-positive, and precision–recall views below all use the direct-S3 measured coverage contract; no RSR or nominal coverage is used to position an observation.

![hard_vcf_giabhc_ins_50_fscore_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_ins_50_fscore_heatmap.png)

![hard_vcf_giabhc_ins_50_fn_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_ins_50_fn_heatmap.png)

![hard_vcf_giabhc_ins_50_fp_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_ins_50_fp_heatmap.png)

![hard_vcf_giabhc_ins_50_precision_recall.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_ins_50_precision_recall.png)

### DEL_50

F-score, false-negative, false-positive, and precision–recall views below all use the direct-S3 measured coverage contract; no RSR or nominal coverage is used to position an observation.

![hard_vcf_giabhc_del_50_fscore_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_del_50_fscore_heatmap.png)

![hard_vcf_giabhc_del_50_fn_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_del_50_fn_heatmap.png)

![hard_vcf_giabhc_del_50_fp_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_del_50_fp_heatmap.png)

![hard_vcf_giabhc_del_50_precision_recall.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_del_50_precision_recall.png)

Exact hard-VCF values: [hard_vcf_giabhc_metrics.tsv](hg002_bjuice_downsample_combined_report_assets/tables/hard_vcf_giabhc_metrics.tsv).

## Truvari structural-variant concordance

The two coverage-coordinate maps use tagged TrussSV values. The precision–recall facets retain the same E1/E3/P1 observations and label each point directly; raw summary metrics remain available for audit.

![truvari_trussv_global_fscore_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/truvari_trussv_global_fscore_heatmap.png)

![truvari_trussv_gt_concordance_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/truvari_trussv_gt_concordance_heatmap.png)

![truvari_all_callers_precision_recall.png](hg002_bjuice_downsample_combined_report_assets/figures/truvari_all_callers_precision_recall.png)

Caller color and marker shape encode the caller (TIDDIT, LongReadSV, Sniffles2, or tagged TrussSV); experiment is encoded by marker fill. Every plotted point is labelled with experiment, AU, and F-score. Points with undefined raw precision or recall remain in the table as `NA` and are not plotted. Exact raw-summary values: [truvari_metrics.tsv](hg002_bjuice_downsample_combined_report_assets/tables/truvari_metrics.tsv).

## SegDup and SMN1/2 calls

These callset summaries are descriptive, not truth/query concordance. Their coordinate facets use the same measured native-SR×/LR× plane, so a vertical E1 arrangement represents the actual full-SR result rather than a nominal SR ladder. Each 25%-larger circle prints the displayed call count or copy number and has no colored edge; dashed contours represent retained-AU coordinate density only. Colors and values are coordinate-level arithmetic means when observations co-locate.

![segdup_call_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/segdup_call_heatmap.png)

Exact SegDup records, including PASS/non-PASS state, are available in [segdup_calls.tsv](hg002_bjuice_downsample_combined_report_assets/tables/segdup_calls.tsv).

![smn12_copy_number_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/smn12_copy_number_heatmap.png)

Undefined low-coverage SMN copy-number calls remain `NA`; they are not coerced to zero. Complete SMN fields: [smn12_calls.tsv](hg002_bjuice_downsample_combined_report_assets/tables/smn12_calls.tsv).

## Benchmark cost and parallel-aware runtime

The per-task panels retain individual-AU task groups; the summary uses the exact retained observations. Neither view uses requested coverage values.

![benchmark_per_task_walltime.png](hg002_bjuice_downsample_combined_report_assets/figures/benchmark_per_task_walltime.png)

![benchmark_per_task_cost.png](hg002_bjuice_downsample_combined_report_assets/figures/benchmark_per_task_cost.png)

![benchmark_au_totals.png](hg002_bjuice_downsample_combined_report_assets/figures/benchmark_au_totals.png)

The task plots show the top 12 groups per retained observation; the TSV retains every successful task group. Observed makespan spans the first through last benchmark timestamp. Active-interval union merges overlapping task intervals. Longest task is a lower bound, not a DAG-derived critical path.

Supporting benchmark tables: [benchmark_task_groups.tsv](hg002_bjuice_downsample_combined_report_assets/tables/benchmark_task_groups.tsv) and [benchmark_au_totals.tsv](hg002_bjuice_downsample_combined_report_assets/tables/benchmark_au_totals.tsv).

## Scope, methods, and limitations

- Native SR× is the exact `chrom=total` Mosdepth mean from `sentdhiomr2sr/smd`; LR× is from `sentdhiomr2lr/na`. RSR× from `sentdhiomr2rsr/na` is retained only as a separately named audit result.
- The S3 collection rejects a missing or duplicate native-SR, RSR, or LR summary and fails if a re-read direct value differs from the recorded contract.
- E1’s seven identical native-SR summaries establish a data-generation limitation, not a charting transformation. This report does not claim that its declared SR fractions were applied.
- Hard-VCF metrics are restricted to `ROI=giabHC`; the crude SNP construction is intentionally not a standard variant-class aggregation.
- Truvari metrics come from raw `summary.json`. Undefined no-call rates are `NA`, even where a downstream report-oriented artifact normalized them to zero.
- SegDup is descriptive callset output, not truth/query concordance. A no-call state is not evidence of reference genotype truth.
- E1, E3, and P1 reuse the same HG002 source material; input subsets are nested and P1 is a full-input production observation. Results are descriptive and no causal or inferential claim is made.
- The executions may have different runtime software provenance. The report uses produced artifacts and does not relabel a later execution as a pristine re-execution of an earlier release.

## Audit and reproducibility

- Direct S3 native-SR, RSR, and LR values with exact source paths and SHA-256 values: [direct_s3_coverage_regather.tsv](hg002_bjuice_downsample_combined_report_assets/tables/direct_s3_coverage_regather.tsv).
- Existing bounded evidence inventory for detailed call/benchmark inputs: [source_inventory.tsv](hg002_bjuice_downsample_combined_report_assets/tables/source_inventory.tsv).
- Figure-to-table mapping: [chart_map.tsv](hg002_bjuice_downsample_combined_report_assets/tables/chart_map.tsv).

Generated from bounded E1/E3/P1 evidence snapshots plus direct S3 reads of all 36 Mosdepth summaries on 2026-08-18.
