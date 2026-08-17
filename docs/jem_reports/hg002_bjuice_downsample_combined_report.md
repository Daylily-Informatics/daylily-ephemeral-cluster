# HG002 Bjuice combined downsampling heatmap report

## Technical summary

This report combines **14 retained measured-coverage observations** from two completed HG002 HIOMR2 kitchensink-mega downsampling experiments. Exact duplicate identity is `(AU, measured ILMN, measured ONT)`; **0 older E1 observation(s)** were superseded by E2. Experiment provenance remains visible as `E1:<AU>` or `E2:<AU>` in every chart and table.

E2 reduced mean absolute Illumina target error to **4.62x**, versus **5.65x** in E1, but measured Illumina coverage remained below nominal in **7/7 E2 AUs**. ONT mean absolute target error was **0.12x** in E2 and **1.99x** in E1. The strongest retained TrussSV global F-score was **0.7190** at **E1:15x5**. Successful benchmark task rows sum to **$201.27** for retained E1 observations and **$113.16** for retained E2 observations.

E1 completed its live rerun at `rc=0` on 2026-08-14; E2 completed the retained kitchensink-mega/final-MultiQC closure at `rc=0` on 2026-08-16. E1's manifest fractions were present, but its Illumina rule did not apply them as intended; E1 coverage is therefore used only as measured observational evidence. E2 is the corrected re-downsampling experiment. Analytical packaging is not part of the E2 completion claim.

## Where data exist: unified measured-coverage grid

Rows are measured Illumina coverage and columns are measured ONT coverage. The Markdown grid is shown from largest ILMN value at the top to smallest at the bottom, matching the plotted heatmap's smallest-at-bottom orientation. `—` is a true grid gap.

| ILMN \ ONT | 0.57x | 1.16x | 2.96x | 4.09x | 5.17x | 6.20x | 9.67x | 10.05x | 11.43x |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 14.01x | — | — | — | — | — | — | — | — | E1:15x5 |
| 13.65x | — | — | — | — | — | — | E1:10x5; E1:15x10 | — | — |
| 12.71x | — | — | — | — | — | E1:5x5 | — | — | — |
| 11.93x | — | — | — | E1:3x3 | — | — | — | — | — |
| 9.85x | — | E1:1x1 | — | — | — | — | — | — | — |
| 8.54x | E1:p5xp5 | — | — | — | — | — | — | — | — |
| 5.47x | — | — | — | — | — | — | — | E2:15x10 | — |
| 4.96x | — | — | — | — | E2:15x5 | — | — | — | — |
| 3.50x | — | — | — | — | E2:10x5 | — | — | — | — |
| 1.82x | — | — | — | — | E2:5x5 | — | — | — | — |
| 1.01x | — | — | E2:3x3 | — | — | — | — | — | — |
| 0.27x | — | E2:1x1 | — | — | — | — | — | — | — |
| 0.11x | E2:p5xp5 | — | — | — | — | — | — | — | — |

![combined_measured_coverage_grid.png](hg002_bjuice_downsample_combined_report_assets/figures/combined_measured_coverage_grid.png)

### Retained observation provenance

| Observation | Nominal ILMN × ONT | Measured ILMN × ONT | ILMN fraction | ONT hours | Runtime AU | Selection |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| E1:p5xp5 | 0.5x × 0.5x | 8.54x × 0.57x | 0.011433798307 | [0,1) | HG002-082hc3dnbehb1c | retained_unique |
| E1:1x1 | 1.0x × 1.0x | 9.85x × 1.16x | 0.022867596615 | [0,2) | HG002-98xq4xrqz7dwy9 | retained_unique |
| E1:3x3 | 3.0x × 3.0x | 11.93x × 4.09x | 0.068602789846 | [0,7) | HG002-871vyxbnp4n81v | retained_unique |
| E1:5x5 | 5.0x × 5.0x | 12.71x × 6.20x | 0.114337983077 | [0,11) | HG002-vqs89p8gahfwf9 | retained_unique |
| E1:10x5 | 10.0x × 5.0x | 13.65x × 9.67x | 0.228675966155 | [0,19) | HG002-fjg1n22920ymw4 | retained_unique |
| E1:15x5 | 15.0x × 5.0x | 14.01x × 11.43x | 0.343013949233 | [0,24) | HG002-bq765db79mczvn | retained_unique |
| E1:15x10 | 15.0x × 10.0x | 13.65x × 9.67x | 0.343013949233 | [0,19) | HG002-f277f1cckvy1xb | retained_unique |
| E2:p5xp5 | 0.5x × 0.5x | 0.11x × 0.57x | 0.011433798307 | [0,1) | HG002-5r2pnnjbw114ye | retained_unique |
| E2:1x1 | 1.0x × 1.0x | 0.27x × 1.16x | 0.022867596615 | [0,2) | HG002-dhcejhqjtfa8my | retained_unique |
| E2:3x3 | 3.0x × 3.0x | 1.01x × 2.96x | 0.068602789846 | [0,5) | HG002-pw12ff0qe3akkp | retained_unique |
| E2:5x5 | 5.0x × 5.0x | 1.82x × 5.17x | 0.114337983077 | [0,9) | HG002-qp0pfqh42zyaqs | retained_unique |
| E2:10x5 | 10.0x × 5.0x | 3.50x × 5.17x | 0.228675966155 | [0,9) | HG002-tb1jdkbzdpwenh | retained_unique |
| E2:15x5 | 15.0x × 5.0x | 4.96x × 5.17x | 0.343013949233 | [0,9) | HG002-56db7xrgpanwkk | retained_unique |
| E2:15x10 | 15.0x × 10.0x | 5.47x × 10.05x | 0.343013949233 | [0,20) | HG002-p2tc9mz7wbv628 | retained_unique |

The full retained-observation table includes nominal targets, exact measured tokens, fractions, ONT windows, source paths, and selection status: [retained_observations.tsv](hg002_bjuice_downsample_combined_report_assets/tables/retained_observations.tsv).

## Coverage targeting and ONT yield

![planned_vs_measured_coverage.png](hg002_bjuice_downsample_combined_report_assets/figures/planned_vs_measured_coverage.png)

![ont_coverage_vs_runtime.png](hg002_bjuice_downsample_combined_report_assets/figures/ont_coverage_vs_runtime.png)

The ONT figure is descriptive aligned yield versus cumulative `[0,end)` input duration. Lines connect experiment-specific hour means and are not a fitted physical yield model.

## Hard-VCF GIAB high-confidence concordance

Crude SNP uses `SNPts + SNPtv/2` independently for TP, FN, and FP; precision, recall, and F-score are recalculated from those composite counts. Every heatmap uses the same unified measured-coverage grid and retains all experiment/AU labels in shared cells.

### SNP (SNPts + SNPtv/2)

![hard_vcf_giabhc_snp_fscore_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_snp_fscore_heatmap.png)

![hard_vcf_giabhc_snp_fn_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_snp_fn_heatmap.png)

![hard_vcf_giabhc_snp_fp_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_snp_fp_heatmap.png)

![hard_vcf_giabhc_snp_precision_recall.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_snp_precision_recall.png)

### INS_50

![hard_vcf_giabhc_ins_50_fscore_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_ins_50_fscore_heatmap.png)

![hard_vcf_giabhc_ins_50_fn_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_ins_50_fn_heatmap.png)

![hard_vcf_giabhc_ins_50_fp_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_ins_50_fp_heatmap.png)

![hard_vcf_giabhc_ins_50_precision_recall.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_ins_50_precision_recall.png)

### DEL_50

![hard_vcf_giabhc_del_50_fscore_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_del_50_fscore_heatmap.png)

![hard_vcf_giabhc_del_50_fn_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_del_50_fn_heatmap.png)

![hard_vcf_giabhc_del_50_fp_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_del_50_fp_heatmap.png)

![hard_vcf_giabhc_del_50_precision_recall.png](hg002_bjuice_downsample_combined_report_assets/figures/hard_vcf_giabhc_del_50_precision_recall.png)

Exact hard-VCF values: [hard_vcf_giabhc_metrics.tsv](hg002_bjuice_downsample_combined_report_assets/tables/hard_vcf_giabhc_metrics.tsv).

## Truvari structural-variant concordance

![truvari_trussv_global_fscore_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/truvari_trussv_global_fscore_heatmap.png)

![truvari_trussv_gt_concordance_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/truvari_trussv_gt_concordance_heatmap.png)

![truvari_all_callers_precision_recall.png](hg002_bjuice_downsample_combined_report_assets/figures/truvari_all_callers_precision_recall.png)

Caller color and shape are stable; E1 uses open markers and E2 filled markers. Points with undefined raw precision or recall remain in the table as `NA` and are not plotted. Exact raw-summary values: [truvari_metrics.tsv](hg002_bjuice_downsample_combined_report_assets/tables/truvari_metrics.tsv).

## SegDup and SMN1/2 calls

![segdup_call_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/segdup_call_heatmap.png)

SegDup cell codes are `P#` for PASS non-reference calls, `F#` for non-PASS calls, and `NA` for no non-reference call. Exact records: [segdup_calls.tsv](hg002_bjuice_downsample_combined_report_assets/tables/segdup_calls.tsv).

![smn12_copy_number_heatmap.png](hg002_bjuice_downsample_combined_report_assets/figures/smn12_copy_number_heatmap.png)

Undefined low-coverage SMN copy-number calls remain `NA`; they are not coerced to zero. Complete SMN fields: [smn12_calls.tsv](hg002_bjuice_downsample_combined_report_assets/tables/smn12_calls.tsv).

## Benchmark cost and parallel-aware runtime

![benchmark_per_task_walltime.png](hg002_bjuice_downsample_combined_report_assets/figures/benchmark_per_task_walltime.png)

![benchmark_per_task_cost.png](hg002_bjuice_downsample_combined_report_assets/figures/benchmark_per_task_cost.png)

![benchmark_au_totals.png](hg002_bjuice_downsample_combined_report_assets/figures/benchmark_au_totals.png)

The task plots show the top 12 groups per retained observation; the TSV retains every successful task group. Observed makespan spans the first through last benchmark timestamp. Active-interval union merges overlapping task intervals. Longest task is a lower bound, not a DAG-derived critical path.
Nine successful E2 benchmark records have no source-reported task cost. They remain counted as unpriced records; cost totals sum only numeric source values and therefore represent a documented lower bound.

Supporting benchmark tables: [benchmark_task_groups.tsv](hg002_bjuice_downsample_combined_report_assets/tables/benchmark_task_groups.tsv) and [benchmark_au_totals.tsv](hg002_bjuice_downsample_combined_report_assets/tables/benchmark_au_totals.tsv).

## Scope, methods, and limitations

- Coverage is the exact `chrom=total` Mosdepth mean from the HIOMR2 short-read and long-read alignment summaries.
- Hard-VCF metrics are restricted to `ROI=giabHC`; the crude SNP construction is intentionally not a standard variant-class aggregation.
- Truvari metrics come from raw `summary.json`. Undefined no-call rates are `NA`, even where a downstream report-oriented artifact normalized them to zero.
- SegDup is descriptive callset output, not truth/query concordance. A no-call state is not evidence of reference genotype truth.
- The two experiments reuse the same HG002 source material and their downsampled inputs are nested; observations are not statistically independent. Results are descriptive and no causal or inferential claim is made.
- E1 and E2 may contain different runtime software provenance because E2 was completed after authorized R&D reporting repairs. The report uses produced artifacts and does not relabel E2 as a pristine later release execution.

## Audit and reproducibility

- Source inventory with original and locally verified SHA-256 values: [source_inventory.tsv](hg002_bjuice_downsample_combined_report_assets/tables/source_inventory.tsv).
- Exact duplicate decisions: [duplicate_resolution.tsv](hg002_bjuice_downsample_combined_report_assets/tables/duplicate_resolution.tsv).
- Duplicate metric comparisons: [duplicate_metric_audit.tsv](hg002_bjuice_downsample_combined_report_assets/tables/duplicate_metric_audit.tsv).
- Figure-to-table mapping: [chart_map.tsv](hg002_bjuice_downsample_combined_report_assets/tables/chart_map.tsv).

Generated from bounded DYEC evidence snapshots on 2026-08-16.
