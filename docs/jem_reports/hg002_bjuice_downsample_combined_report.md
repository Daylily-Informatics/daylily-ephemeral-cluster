# HG002 Bjuice native-SR × LR measured-coverage matrix report

## Measured-coverage sanity table

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
| E4:N01 | 0.5× | 0.56× | 0.11× | 0.5× | 0.57× |
| E4:N02 | 0.5× | 0.56× | 0.18× | 4× | 4.63× |
| E4:N03 | 0.5× | 0.56× | 0.20× | 12× | 11.43× |
| E4:N04 | 0.5× | 0.56× | 0.20× | 30× | 18.77× |
| E4:N05 | 10× | 10.97× | 2.18× | 0.5× | 0.57× |
| E4:N06 | 10× | 10.97× | 3.43× | 4× | 4.63× |
| E4:N07 | 10× | 10.97× | 3.82× | 12× | 11.43× |
| E4:N08 | 10× | 10.97× | 3.90× | 30× | 18.77× |
| E4:N09 | 30× | 31.12× | 10.64× | 30× | 18.77× |
| E4:N10 | 43.73× | 43.73× | 14.66× | 30× | 18.77× |
| E4:N11 | 2× | 2.25× | 0.45× | 0.5× | 0.57× |
| E4:N12 | 2× | 2.25× | 0.73× | 4× | 4.63× |
| E4:N13 | 2× | 2.25× | 0.80× | 12× | 11.43× |
| E4:N14 | 2× | 2.25× | 0.81× | 30× | 18.77× |
| E4:N15 | 20× | 21.33× | 4.09× | 0.5× | 0.57× |
| E4:N16 | 20× | 21.33× | 6.18× | 4× | 4.63× |
| E4:N17 | 20× | 21.33× | 7.18× | 12× | 11.43× |
| E4:N18 | 20× | 21.33× | 7.43× | 30× | 18.77× |
| E4:N19 | 5× | 5.57× | 1.99× | 30× | 18.77× |
| E4:N20 | 15× | 16.22× | 5.71× | 30× | 18.77× |

This is the only report table that presents requested coverage targets. E1/E3/P1 values were re-read from three completed S3 exports; E4 values were retained from the checksum-bound snapshot and are now provenance-linked to its successful no-delete S3 clone export. Every source path and SHA-256 is retained in [direct_s3_coverage_regather.tsv](hg002_bjuice_downsample_combined_report_assets/tables/direct_s3_coverage_regather.tsv) and [source_inventory.tsv](hg002_bjuice_downsample_combined_report_assets/tables/source_inventory.tsv).

## Technical summary

This report contains **32 observations**: all **12 prior E1/E3/P1 observations** plus **20 E4 controlled-matrix AUs** captured at **2026-08-18T17:55:26Z**. The E4 snapshot was captured while the workflow state was **running** with no terminal controller, `day_run`, or Snakemake return code; the full clone was subsequently preserved by a successful no-delete export (task `task-08e04406a00b92553`), so E4 benchmark accounting remains explicitly partial.

Every coverage-positioned figure uses **measured native SR×** on its vertical axis and **measured LR×** on its horizontal axis, with equal numeric scale. RSR× is audit-only. The strongest retained tagged-TrussSV global F-score is **0.7611** at **E4:N04**. Captured successful benchmark rows sum to **$201.27** for E1, **$108.52** for E3, **$31.46** for P1, **$256.59** for E4 (preserved interrupted-export snapshot).

E1 is **not a valid two-axis Illumina downsampling series**: every direct-S3 native-SR summary is exactly 43.73× (and has the same SHA-256), despite the AU-specific declared fractions. It is retained as a full-SR / variable-LR experiment. E3 supplies four variable-native-SR observations, P1 is a distinct full-input observation, and E4 supplies the intended 20-cell controlled matrix.

RSR is not a conventional random Illumina downsample. The E1 Sentieon hybrid log shows stage 3 running on a generated `hybrid_stage2.bed` interval set, followed by `hybrid_transfer` from the full SR alignment into `g_sr_realigned.cram`. Its retained-record fraction and Mosdepth therefore vary with the hybrid-selected regions and LR input. The 8.54–14.01× E1 RSR range is expected to differ from the uniform 43.73× native-SR evidence and must not form a coverage-matrix axis.

## E4 exported snapshot completeness

All 20 E4 AUs supplied parseable native-SR, RSR-audit, LR, hard-VCF GIAB-HC, four-caller Truvari, SMN12, and 15-gene SegDup artifacts. Their measured native-SR range is **0.56×–43.73×** and measured LR range is **0.57×–18.77×**.

| E4 AU | source AU | native SR | LR | hard VCF | Truvari | SegDup | SMN12 | usable benchmark rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| E4:N01 | HG002-ilmn0p5x-ont0p5x-h01 | 0.56× | 0.57× | complete | 4/4 | 15/15 | complete | 231 |
| E4:N02 | HG002-ilmn0p5x-ont4x-h08 | 0.56× | 4.63× | complete | 4/4 | 15/15 | complete | 231 |
| E4:N03 | HG002-ilmn0p5x-ont12x-h24 | 0.56× | 11.43× | complete | 4/4 | 15/15 | complete | 231 |
| E4:N04 | HG002-ilmn0p5x-ont30x-h72 | 0.56× | 18.77× | complete | 4/4 | 15/15 | complete | 209 |
| E4:N05 | HG002-ilmn10x-ont0p5x-h01 | 10.97× | 0.57× | complete | 4/4 | 15/15 | complete | 230 |
| E4:N06 | HG002-ilmn10x-ont4x-h08 | 10.97× | 4.63× | complete | 4/4 | 15/15 | complete | 230 |
| E4:N07 | HG002-ilmn10x-ont12x-h24 | 10.97× | 11.43× | complete | 4/4 | 15/15 | complete | 229 |
| E4:N08 | HG002-ilmn10x-ont30x-h72 | 10.97× | 18.77× | complete | 4/4 | 15/15 | complete | 231 |
| E4:N09 | HG002-ilmn30x-ont30x-h72 | 31.12× | 18.77× | complete | 4/4 | 15/15 | complete | 229 |
| E4:N10 | HG002-ilmn43p73x-ont30x-h72 | 43.73× | 18.77× | complete | 4/4 | 15/15 | complete | 231 |
| E4:N11 | HG002-ilmn2x-ont0p5x-h01 | 2.25× | 0.57× | complete | 4/4 | 15/15 | complete | 231 |
| E4:N12 | HG002-ilmn2x-ont4x-h08 | 2.25× | 4.63× | complete | 4/4 | 15/15 | complete | 231 |
| E4:N13 | HG002-ilmn2x-ont12x-h24 | 2.25× | 11.43× | complete | 4/4 | 15/15 | complete | 230 |
| E4:N14 | HG002-ilmn2x-ont30x-h72 | 2.25× | 18.77× | complete | 4/4 | 15/15 | complete | 231 |
| E4:N15 | HG002-ilmn20x-ont0p5x-h01 | 21.33× | 0.57× | complete | 4/4 | 15/15 | complete | 230 |
| E4:N16 | HG002-ilmn20x-ont4x-h08 | 21.33× | 4.63× | complete | 4/4 | 15/15 | complete | 230 |
| E4:N17 | HG002-ilmn20x-ont12x-h24 | 21.33× | 11.43× | complete | 4/4 | 15/15 | complete | 230 |
| E4:N18 | HG002-ilmn20x-ont30x-h72 | 21.33× | 18.77× | complete | 4/4 | 15/15 | complete | 229 |
| E4:N19 | HG002-ilmn5x-ont30x-h72 | 5.57× | 18.77× | complete | 4/4 | 15/15 | complete | 208 |
| E4:N20 | HG002-ilmn15x-ont30x-h72 | 16.22× | 18.77× | complete | 4/4 | 15/15 | complete | 207 |

The exported E4 clone preserves **4,539 usable successful raw benchmark rows** from the snapshot. Because the workflow was nonterminal when captured, these are not final cost or runtime totals. The collector also retained an audit of **242 failed-attempt rows** and excluded **18 rows labelled successful whose walltime was `NA`**. Exact per-AU counts are in [e4_snapshot_completeness.tsv](hg002_bjuice_downsample_combined_report_assets/tables/e4_snapshot_completeness.tsv). The export receipt and retained status-v2 history are linked in the audit section below.

## Source locations

| Source | S3 URI |
| --- | ---: |
| Shared full-prevalence Illumina FASTQs | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/Analysis/1/Data/BCLConvert/fastq/` |
| Shared HG002 ONT FC1 source | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set4-FC1/20260615_ONT_Set4-FC1/20260616_0048_3A_PBM08268_14b096e3/` |
| Shared HG002 ONT FC2 source | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set4-FC2/20260615_ONT_Set4-FC2/20260616_0040_3B_PBK89197_822a87b5/` |
| Shared HG002 ONT FC3 source | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set4-FC3/20260615_ONT_Set4-FC3/20260616_0041_3C_PBK89101_bd86eaac/` |
| E1 completed output export | `s3://lsmc-dayoa-analysis-results-usw2/derived/bjuice-v2-multi-analysis-unit/prod-cand-1703/prod-cand-1703-hg002-bjuice-v2-multiau-20260814T114522Z/daylily-omics-analysis/` |
| E3 completed output export | `s3://lsmc-dayoa-analysis-results-usw2/derived/bjuice-v2-multi-analysis-unit/prod-cand-1703/prod-cand-1703-hg002-bjuice-4au-kitchensink-20260817T025004Z/daylily-omics-analysis/` |
| P1 completed output export | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022-bjuice-preval6-15014-dry-20260817t112900z/daylily-omics-analysis/` |
| E4 exported interrupted clone | `s3://lsmc-ssf-sequencing-data/derived/pre-rel-18025/prerel18025-bjuice-v2-hg002-20au-18042-20260818t1255z-live/daylily-omics-analysis/` |

E4 snapshot source: `/fsx/analysis_results/pre-rel-18025/prerel18025-bjuice-v2-hg002-20au-18042-20260818t1255z-live` (DayOA 15.0.24 at `9cd4e43fded97ea57f11f19c164ab1fbe3fa77d4`); the complete clone was subsequently preserved at `s3://lsmc-ssf-sequencing-data/derived/pre-rel-18025/prerel18025-bjuice-v2-hg002-20au-18042-20260818t1255z-live/`. The exact S3 roots and direct summary-file URIs are recorded in [source_s3_uris.tsv](hg002_bjuice_downsample_combined_report_assets/tables/source_s3_uris.tsv) and [direct_s3_coverage_regather.tsv](hg002_bjuice_downsample_combined_report_assets/tables/direct_s3_coverage_regather.tsv); E4 file hashes and paths are in [source_inventory.tsv](hg002_bjuice_downsample_combined_report_assets/tables/source_inventory.tsv).

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
| E4:N01 | 0.56× | 0.11× | 0.57× | [0,1) | HG002-ehyq1gkgctd5sk |
| E4:N02 | 0.56× | 0.18× | 4.63× | [0,8) | HG002-chjze1q0erq9s3 |
| E4:N03 | 0.56× | 0.20× | 11.43× | [0,24) | HG002-3am5mqch4e741r |
| E4:N04 | 0.56× | 0.20× | 18.77× | [0,72) | HG002-yjk6fdaa4kbmwx |
| E4:N05 | 10.97× | 2.18× | 0.57× | [0,1) | HG002-q72eaw08wpkf3v |
| E4:N06 | 10.97× | 3.43× | 4.63× | [0,8) | HG002-atx653x1j8ynp0 |
| E4:N07 | 10.97× | 3.82× | 11.43× | [0,24) | HG002-pcqc0c5xzp2s1k |
| E4:N08 | 10.97× | 3.90× | 18.77× | [0,72) | HG002-1yxqt33e4ha4wz |
| E4:N09 | 31.12× | 10.64× | 18.77× | [0,72) | HG002-e2mfe9p53bbdx1 |
| E4:N10 | 43.73× | 14.66× | 18.77× | [0,72) | HG002-rawrmex4zyxxd5 |
| E4:N11 | 2.25× | 0.45× | 0.57× | [0,1) | HG002-1w3583n0mxzmxk |
| E4:N12 | 2.25× | 0.73× | 4.63× | [0,8) | HG002-69qtwf5v9wjrh3 |
| E4:N13 | 2.25× | 0.80× | 11.43× | [0,24) | HG002-afd318m6ttcxqg |
| E4:N14 | 2.25× | 0.81× | 18.77× | [0,72) | HG002-bkvtsgeczn2ycw |
| E4:N15 | 21.33× | 4.09× | 0.57× | [0,1) | HG002-f5tq2g3fwym1wt |
| E4:N16 | 21.33× | 6.18× | 4.63× | [0,8) | HG002-h18bnth6fp1ybq |
| E4:N17 | 21.33× | 7.18× | 11.43× | [0,24) | HG002-ds948px1gsb06w |
| E4:N18 | 21.33× | 7.43× | 18.77× | [0,72) | HG002-bkms86vs8ep25w |
| E4:N19 | 5.57× | 1.99× | 18.77× | [0,72) | HG002-nk7tnqw08n0e91 |
| E4:N20 | 16.22× | 5.71× | 18.77× | [0,72) | HG002-7ge6tbnr426h4f |

The retained-observation table has native-SR, RSR, LR, source paths, and selection provenance without repeating the requested targets: [retained_observations.tsv](hg002_bjuice_downsample_combined_report_assets/tables/retained_observations.tsv).

## Measured ONT coverage and runtime

This is descriptive aligned LR yield versus cumulative input runtime. It uses measured LR× only; the lines connect experiment-specific hour means and are not a fitted yield model.

![ont_coverage_vs_runtime.png](hg002_bjuice_downsample_combined_report_assets/figures/ont_coverage_vs_runtime.png)


## Hard-VCF GIAB high-confidence concordance

Crude SNP uses `SNPts + SNPtv/2` independently for TP, FN, and FP; precision, recall, and F-score are recalculated from those composite counts. Each color map uses the same equal-scale numeric native-SR×/LR× plane. Every 25%-larger circle prints its own plotted metric and has no colored edge. Dashed contours show retained-AU coordinate density only, not interpolated metric values. When multiple observations share a measured coordinate, both the circle color and printed value are their arithmetic mean; the metric TSV keeps unaggregated values.

### SNP (SNPts + SNPtv/2)

F-score, false-negative, false-positive, and precision–recall views below all use the measured native-SR/LR coverage contract; no RSR or nominal coverage is used to position an observation.

![hard_vcf_giabhc_snp_fscore_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_snp_fscore_heatmap.png)

![hard_vcf_giabhc_snp_fn_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_snp_fn_heatmap.png)

![hard_vcf_giabhc_snp_fp_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_snp_fp_heatmap.png)

![hard_vcf_giabhc_snp_precision_recall.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_snp_precision_recall.png)

### INS_50

F-score, false-negative, false-positive, and precision–recall views below all use the measured native-SR/LR coverage contract; no RSR or nominal coverage is used to position an observation.

![hard_vcf_giabhc_ins_50_fscore_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_ins_50_fscore_heatmap.png)

![hard_vcf_giabhc_ins_50_fn_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_ins_50_fn_heatmap.png)

![hard_vcf_giabhc_ins_50_fp_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_ins_50_fp_heatmap.png)

![hard_vcf_giabhc_ins_50_precision_recall.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_ins_50_precision_recall.png)

### DEL_50

F-score, false-negative, false-positive, and precision–recall views below all use the measured native-SR/LR coverage contract; no RSR or nominal coverage is used to position an observation.

![hard_vcf_giabhc_del_50_fscore_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_del_50_fscore_heatmap.png)

![hard_vcf_giabhc_del_50_fn_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_del_50_fn_heatmap.png)

![hard_vcf_giabhc_del_50_fp_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_del_50_fp_heatmap.png)

![hard_vcf_giabhc_del_50_precision_recall.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_del_50_precision_recall.png)

Exact hard-VCF values: [hard_vcf_giabhc_metrics.tsv](hg002_bjuice_downsample_combined_report_assets/tables/hard_vcf_giabhc_metrics.tsv).

## Truvari structural-variant concordance

The two coverage-coordinate maps use tagged TrussSV values. The precision–recall facets retain all E1/E3/P1/E4 observations and label each point directly; raw summary metrics remain available for audit.

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

The per-task panels retain individual-AU task groups; the summary uses the exact retained observations. Neither view uses requested coverage values. E4 bars are explicitly a preserved nonterminal snapshot and must not be interpreted as final AU cost or duration.

![benchmark_per_task_walltime.png](hg002_bjuice_downsample_combined_report_assets/figures/benchmark_per_task_walltime.png)

![benchmark_per_task_cost.png](hg002_bjuice_downsample_combined_report_assets/figures/benchmark_per_task_cost.png)

![benchmark_au_totals.png](hg002_bjuice_downsample_combined_report_assets/figures/benchmark_au_totals.png)

The task plots show the top 12 groups per retained observation; the TSV retains every usable successful task group. Observed makespan spans the first through last benchmark timestamp. Active-interval union merges overlapping task intervals. Longest task is a lower bound, not a DAG-derived critical path. E4 values stop at the captured snapshot timestamp because the controller was interrupted before a terminal workflow receipt.

Supporting benchmark tables: [benchmark_task_groups.tsv](hg002_bjuice_downsample_combined_report_assets/tables/benchmark_task_groups.tsv) and [benchmark_au_totals.tsv](hg002_bjuice_downsample_combined_report_assets/tables/benchmark_au_totals.tsv).

## Scope, methods, and limitations

- Native SR× is the exact `chrom=total` Mosdepth mean from `sentdhiomr2sr/smd`; LR× is from `sentdhiomr2lr/na`. RSR× from `sentdhiomr2rsr/na` is retained only as a separately named audit result.
- The completed-export S3 collection rejects a missing or duplicate native-SR, RSR, or LR summary and fails if a re-read direct value differs from the recorded contract. The E4 collector applies the same exact-cardinality and schema checks against its live FSx snapshot.
- E1’s seven identical native-SR summaries establish a data-generation limitation, not a charting transformation. This report does not claim that its declared SR fractions were applied.
- Hard-VCF metrics are restricted to `ROI=giabHC`; the crude SNP construction is intentionally not a standard variant-class aggregation.
- Truvari metrics come from raw `summary.json`. Undefined no-call rates are `NA`, even where a downstream report-oriented artifact normalized them to zero.
- SegDup is descriptive callset output, not truth/query concordance. A no-call state is not evidence of reference genotype truth.
- E1, E3, P1, and E4 reuse the same HG002 source material; input subsets are nested and P1 is a full-input production observation. Results are descriptive and no causal or inferential claim is made.
- E4 was nonterminal at 2026-08-18T17:55:26Z; the complete clone was later preserved by export task `task-08e04406a00b92553`. Its 20 core metric sets were complete and parseable, but its 4,539 benchmark rows are a lower-bound snapshot, not final workflow accounting.
- The executions may have different runtime software provenance. The report uses produced artifacts and does not relabel a later execution as a pristine re-execution of an earlier release.

## Audit and reproducibility

- Direct S3 native-SR, RSR, and LR values with exact source paths and SHA-256 values: [direct_s3_coverage_regather.tsv](hg002_bjuice_downsample_combined_report_assets/tables/direct_s3_coverage_regather.tsv).
- E4 per-AU metric and benchmark completeness at capture: [e4_snapshot_completeness.tsv](hg002_bjuice_downsample_combined_report_assets/tables/e4_snapshot_completeness.tsv).
- E4 export receipt: [e4_export_evidence.tsv](hg002_bjuice_downsample_combined_report_assets/tables/e4_export_evidence.tsv); retained clone status-v2 history: [status_v2.json](hg002_bjuice_downsample_combined_report_assets/evidence/raw/E4/status_v2.json).
- Existing bounded evidence inventory for detailed call/benchmark inputs: [source_inventory.tsv](hg002_bjuice_downsample_combined_report_assets/tables/source_inventory.tsv).
- Figure-to-table mapping: [chart_map.tsv](hg002_bjuice_downsample_combined_report_assets/tables/chart_map.tsv).

Generated from bounded E1/E3/P1 evidence, direct S3 reads of their 36 Mosdepth summaries, and the checksum-bound E4 snapshot captured 2026-08-18T17:54:41Z through 2026-08-18T17:55:26Z, with the full E4 clone preserved by the recorded no-delete S3 export.
