# HG002 Bjuice four-AU export and combined-report update ledger

Controlling request: export the completed four-AU HIOMR2 kitchensink-mega analysis to S3, then extend the checked-in combined downsampling report with those measured-coverage observations and all source S3 URIs.

Source analysis root:

`/fsx/analysis_results/prod-cand-1703/prod-cand-1703-hg002-bjuice-4au-kitchensink-20260817T025004Z`

Planned destination (must be fresh and DYEC-validated before transfer):

`s3://lsmc-dayoa-analysis-results-usw2/derived/bjuice-v2-multi-analysis-unit/prod-cand-1703-hg002-bjuice-4au-kitchensink-20260817T025004Z/`

## Gate 0 baseline

- Clean report worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-bjuice-4au-export-report-20260817` on `codex/bjuice-4au-export-report-20260817`, from `origin/main` at `b961cf93`.
- The user-authorized export is explicitly no-delete. FSx must remain preserved.
- The existing checked-in report is `docs/jem_reports/hg002_bjuice_downsample_combined_report.md`; its prior source tables/figures are the preservation baseline.
- A direct local `dyec analysis visit` cannot resolve remote `/fsx` paths from this Mac. Remote artifact reads and the export will therefore use supported cluster-aware DYEC paths. This is recorded as a tooling limitation, not evidence that the source root is absent.
- Existing generator source is present on historical branch `codex/hg002-bjuice-combined-report-20260816` but was not merged with the published report assets. This update will restore that reproducible generator to the report branch rather than hand-editing plotted tables or figures.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| EXP-001 | DYEC export | Validate the exact FSx source and a fresh non-overlapping S3 destination through DYEC. | COMPLETE | legitimate_safety_handling | Gate 0 | orchestrator | DYEC accepted the exact source and destination before association. |  | Destination was fresh and did not overlap an active association. |
| EXP-002 | DYEC export | Run no-delete FSx DRA export and retain immutable receipt. | COMPLETE | feature_implementation | Gate 0 | orchestrator | `reports/fsx_exports/prod-cand-1703-hg002-bjuice-4au-kitchensink-20260817T025004Z/fsx_export.yaml`; DRA `dra-00a90f9d2839678c6`; task `task-0086514fbf61dae5e`. |  | Task `SUCCEEDED`; association detached; `delete_data_in_file_system: false`. |
| EVD-001 | Report evidence | Collect bounded evidence for the four new AUs using DYEC and record source hashes. | COMPLETE | feature_implementation | Gate 0 | orchestrator | `docs/jem_reports/hg002_bjuice_downsample_combined_report_assets/evidence/raw/E3/compact_evidence.json`. |  | DYEC headnode read-only compact extract includes 4 runtime AUs and 99 source-hash rows. |
| REP-001 | Report generator | Restore the prior checked-in reproducible generator, extend it to E3, and preserve prior E1/E2 observations. | COMPLETE | feature_implementation | Gate 1 | orchestrator | `reports/hg002_bjuice_combined_report/build_report.py`; historical source `374529c0`. |  | Rebuild contains E1 7, E2 7, and E3 4 observations. |
| REP-002 | Plot contract | Use measured ILMN and measured ONT only for coverage coordinates; remove target-coverage plots. | COMPLETE | feature_implementation | Gate 1 | orchestrator | Report technical summary and chart manifest; obsolete `planned_vs_measured_coverage.png` removed from Git. |  | All coverage axes and grid labels are measured Mosdepth totals. |
| REP-003 | Precision-recall | Plot hard-VCF crude SNP, INS_50, DEL_50 P/R for all retained AUs with F-score labels; plot SV P/R for all AUs with caller color and shape. | COMPLETE | feature_implementation | Gate 1 | orchestrator | `hard_vcf_giabhc_{snp,ins_50,del_50}_precision_recall.png`; `truvari_all_callers_precision_recall.png`. |  | All 18 retained observations included; visual inspection completed. |
| REP-004 | Provenance | Add every analysis source S3 URI to the Markdown report and supporting source inventory. | COMPLETE | feature_implementation | Gate 1 | orchestrator | Markdown `Source S3 URIs` section and `tables/source_s3_uris.tsv`. |  | Includes shared ILMN and three ONT source prefixes plus completed E3 output export URI. |
| VER-001 | Verification | Rebuild figures/tables, visually inspect affected charts, verify Markdown links, and reconcile rows/coordinates/source hashes. | COMPLETE | contract_test | Gate 5 | orchestrator | Generator: 18 source/retained, 0 duplicate, 11 concordance heatmaps, 14 heatmaps total, 22 figures, 13 tables; Markdown link check `missing_links []`. |  | Coverage grid, SNP P/R, and Truvari P/R visually inspected. |
| GIT-001 | Git | Commit and push generator, ledger, report, assets, tables, and export receipt on the clean branch. | COMPLETE | feature_implementation | Gate 5 | orchestrator | Clean staged change set on `codex/bjuice-4au-export-report-20260817`; commit and push recorded below. |  | No unrelated main-worktree changes included. |

## Final report

All rows terminal: yes

Objective complete: yes

## Git evidence

- Branch: `codex/bjuice-4au-export-report-20260817`
- Commit: `c11cedc5c57651aecaa80a3764e1cd9ead3ea0cb` (`Update HG002 Bjuice combined report with four-AU results`).
- Export guarantee: DRA task `task-0086514fbf61dae5e` succeeded; the association was detached and FSx preservation was explicitly recorded as `delete_data_in_file_system: false`.
