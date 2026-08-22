# HG002 Bjuice combined downsampling heatmap report ledger

Created: 2026-08-16T09:56:34Z

Controlling request: combine the two completed HG002 Bjuice downsampling experiments into one provenance-aware retained-observation dataset and render one technical Markdown report with a unified measured-coverage grid, eleven concordance heatmaps, supporting plots, complete tables, and source-to-chart evidence.

Ledger path: `docs/plans/20260816T095634Z_hg002_bjuice_combined_heatmap_report_ledger.md`

## Gate 0 baseline

- Clean worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-hg002-combined-report-20260816`
- Branch: `codex/hg002-bjuice-combined-report-20260816`
- Base: `origin/main` at `bbb0f861`
- Shared checkout: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` is detached and dirty with unrelated user work; it will not be edited.
- Operations boundary: profile `lsmc`, region `us-west-2`, cluster `prod-cand-1703`, remote user `ubuntu`; activate DYEC with `source ./activate`.
- E1 root: `/fsx/analysis_results/prod-cand-1703/prod-cand-1703-hg002-bjuice-v2-multiau-20260814T114522Z`
- E2 root: `/fsx/analysis_results/prod-cand-1703/prod-cand-1703-hg002-bjuice-v2-seqkitfix-20260815T080300Z`
- Report: `/Users/jmajor/Downloads/hg002_bjuice_downsample_combined_report.md`
- Assets: `/Users/jmajor/Downloads/hg002_bjuice_downsample_combined_report_assets/`
- Excluded roots: the failed retargeted, `srfix`, and `directdenom` attempts are not eligible sources.
- No workflow execution, analysis-data edit, export, deletion, release, PR, or tag is authorized by this ledger.

## Control rows

| ID | Area | Requirement | Status | Category | Gate | Evidence | Root cause / terminal note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| G0-001 | Source | Record clean repo state, exact roots, cluster contract, outputs, and exclusions. | SUCCESS | plan_amendment | Gate 0 | Baseline above. | Scope frozen. |
| G0-002 | Source | Record DYEC read visits and prove both exact roots, terminal state, and seven-AU identity mappings. | SUCCESS | active_product_contract | Gate 0 | DYEC visits under each root; E1 release visit `20260814.jsonl`, E2 release visit `20260816.jsonl`; both notes report `dy-r write operation exited rc=0`. | Exact roots and seven runtime-AU mappings confirmed without source mutation. |
| SRC-001 | Evidence | Build bounded hashed source inventories for coverage, manifests, hard-VCF, raw Truvari, SegDup, SMN12, and canonical benchmarks. | SUCCESS | active_product_contract | E1 archive SHA-256 `269e25c6b8be5f0be5cbdf5962b309e9ebabbf6dac407e6199a9c9aab84468c8`; E2 `9ad12ce209ed5aaba0a424c283f8160863c5169731e9df43d0d302400a51b4d8`; 1,058 inventory rows reconcile. | Bounded collector found 7 AUs, 14 coverage summaries, 7 hard-VCF files, 28 raw Truvari summaries, 7 SMN12 summaries, and 105 SegDup VCFs per experiment. |
| OBS-001 | Model | Build the fourteen-source-observation table and apply exact `(AU, measured ILMN, measured ONT)` E2-preferred deduplication. | SUCCESS | feature_implementation | `retained_observations.tsv`, `duplicate_resolution.tsv`, `duplicate_metric_audit.tsv`. | Fourteen retained rows; zero exact three-field duplicates; shared coordinates retain all AUs. |
| COV-001 | Coverage | Render the top combined coverage-grid table and heatmap with explicit occupied cells and gaps. | SUCCESS | feature_implementation | `coverage_grid.tsv`, `combined_measured_coverage_grid.png`, and the Markdown grid. | Thirteen unique ILMN rows by nine ONT columns; axes are numeric ascending left/right and bottom/top. |
| HVCF-001 | Hard VCF | Render nine combined GIAB-HC heatmaps and three combined precision-recall plots for crude SNP, INS_50, and DEL_50. | SUCCESS | feature_implementation | Nine `hard_vcf_giabhc_*_heatmap.png` files, three precision-recall figures, and `hard_vcf_giabhc_metrics.tsv`. | Crude SNP recomputed from `SNPts + SNPtv/2` for TP, FN, and FP. |
| TRU-001 | Truvari | Render two combined TrussSV heatmaps and one combined all-caller precision-recall plot from raw summaries. | SUCCESS | feature_implementation | `truvari_trussv_*_heatmap.png`, faceted `truvari_all_callers_precision_recall.png`, and `truvari_metrics.tsv`. | Raw undefined rates remain `NA`; one figure facets four callers while retaining both experiments. |
| CALL-001 | Calls | Render one combined SegDup call heatmap and one combined SMN12 heatmap with explicit `NA` no-call state. | SUCCESS | feature_implementation | `segdup_call_heatmap.png`, `smn12_copy_number_heatmap.png`, `segdup_calls.tsv`, and `smn12_calls.tsv`. | Descriptive call states remain separate from concordance; undefined SMN calls are `NA`. |
| BENCH-001 | Benchmarks | Render combined per-task walltime, task cost, and AU aggregate figures with complete supporting tables. | SUCCESS | feature_implementation | Three benchmark figures plus `benchmark_task_groups.tsv` and `benchmark_au_totals.tsv`. | Nine E2 records lacking source cost remain explicitly unpriced; numeric cost totals are a lower bound. |
| TAB-001 | Tables | Write every requested combined TSV plus duplicate and source audits. | SUCCESS | feature_implementation | Twelve TSVs under the report assets directory. | Every required table exists; empty duplicate tables retain headers because the exact duplicate count is zero. |
| REP-001 | Report | Write the single answer-first technical Markdown report with both experiment provenance and one figure of each type. | SUCCESS | feature_implementation | `/Users/jmajor/Downloads/hg002_bjuice_downsample_combined_report.md`. | One combined report links 23 figures and 12 tables; it does not duplicate figures by experiment. |
| QA-001 | Validation | Assert source cardinality, deduplication coverage, 11 concordance plus one coverage heatmap, table/chart reconciliation, and valid links. | SUCCESS | contract_test | Generator terminal JSON: 14 source, 14 retained, 0 exact duplicates, 11 concordance heatmaps, 23 figures, 12 tables; 34 Markdown links resolve; zero hash mismatches. | All machine-verifiable acceptance checks passed. |
| QA-002 | Visual QA | Inspect every figure family in final report context and correct clipping, illegibility, orientation, or provenance ambiguity. | SUCCESS | contract_test | Three contact-sheet passes plus focused precision-recall inspection. | Dense labels were repaired with deterministic callouts; Truvari remains one figure with caller facets. |
| GIT-001 | Delivery | Commit generator, ledger, checksums, and chart manifest on the clean report branch. | SUCCESS | active_product_contract | Enclosing branch commit contains `build_report.py`, `collect_evidence.sh`, this ledger, `chart_map.tsv`, and `output_checksums.sha256`. | No push, PR, tag, release, workflow execution, export, or deletion performed. |

## Acceptance rules

- All rows must reach a terminal state; no `OPEN`, `IN_PROGRESS`, or `ATTEMPTING_BUGFIX` rows may remain.
- Missing artifacts fail explicitly. Existing no-call artifacts are retained as `NA`; an older experiment is never substituted for an E2 `NA`.
- The primary retained-observation key uses exact source-reported numeric tokens. Near values are never rounded into duplicates.
- One combined retained dataset powers every chart and table.
- Objective completion requires the Markdown report and all linked assets to exist and pass source, formula, link, and visual QA.

## Terminal evidence summary

- DYEC headnode: `i-0a19cb6b471874d56` (`10.0.0.22`) on `prod-cand-1703` in `us-west-2`.
- E1 final controller evidence: lock-release note `dy-r write operation exited rc=0` at `2026-08-14T20:32:36.040464Z`.
- E2 retained final-target evidence: lock-release note `dy-r write operation exited rc=0` at `2026-08-16T04:49:37.712475Z`.
- Source hash audit: all 1,058 bounded inventory rows match their headnode SHA-256 values after local extraction.
- Output audit: `reports/hg002_bjuice_combined_report/output_checksums.sha256` records the report, all 23 figures, and all 12 tables.
- Heatmap accounting: 11 concordance heatmaps plus one coverage-layout heatmap; SegDup and SMN12 add two descriptive call heatmaps, for 14 heatmap files total.
- Retained observations: seven E1 plus seven E2. No exact `(AU, measured ILMN, measured ONT)` duplicate existed, so both experiments contribute all seven observations.
- Critical coverage finding: E2 improved mean absolute ILMN target error from `5.65x` to `4.62x`, but all seven E2 measured ILMN depths remained below nominal.

All control rows are terminal and the report objective is complete.
