# HG002 Bjuice E4 partial matrix report rebuild ledger

UTC opened: 2026-08-18T17:46:03Z

State: COMPLETE

## Objective

Rebuild the existing HG002 Bjuice measured-coverage matrix report from its
current 12 E1/E3/P1 observations plus every independently usable result already
produced by the live 20-AU E4 experiment. Every coverage-coordinate plot must
use measured native Illumina SR coverage from `sentdhiomr2sr/smd` and measured
ONT LR coverage from `sentdhiomr2lr/na`; RSR remains audit-only.

## Gate 0 baseline and boundaries

- Worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-hg002-bjuice-native-sr-matrix`
- Branch: `codex/hg002-bjuice-native-sr-matrix-report`
- Baseline commit: `dcda34993300e19a26e814f52e37bb08ab6a1a8d`
- Baseline worktree: clean.
- Existing report: `docs/jem_reports/hg002_bjuice_downsample_combined_report.md`.
- Existing retained evidence: 12 observations (E1 seven, E3 four, P1 one), 22
  figures, and 12 supporting tables. These observations must remain present.
- E4 analysis root:
  `/fsx/analysis_results/pre-rel-18025/prerel18025-bjuice-v2-hg002-20au-18042-20260818t1255z-live`.
- E4 is a live, nonterminal workflow. This work is read-only against the
  analysis root and produces a timestamped partial report snapshot; it does not
  stop, resume, mutate, export, or represent E4 as complete.
- A required read visit was recorded through DYEC before inspecting E4.
- No Slack post, Git commit/push/tag, workflow change, Slurm intervention, FSx
  deletion, or full-analysis export is authorized by this task.

## Tracked rows

| ID | Work | Status | Gate | Evidence / terminal note |
|---|---|---|---|---|
| BASE-001 | Preserve the clean baseline, prior 12 observations, E4 live-state boundary, and native-SR/LR axis contract. | SUCCESS | Gate 0 | Baseline `dcda34993300e19a26e814f52e37bb08ab6a1a8d` was clean. The final validation compared every common provenance field for the 12 prior rows against `HEAD`; all were unchanged except regenerated display IDs. |
| E4-001 | Inventory the exact E4 AU manifest and map source/runtime AU identities to the 20 planned cells. | SUCCESS | Gate 0 | Exact source-AU/runtime-AU mappings for planned cells N01 through N20 are retained in `e4_snapshot_completeness.tsv` and `retained_observations.tsv`. |
| E4-002 | Audit E4 output completeness per AU and per metric; accept only parseable source artifacts and expose missing/in-progress cells. | SUCCESS | Gate 0 | All 20 AUs had parseable native-SR, RSR-audit, LR, three-class hard-VCF GIAB-HC, four Truvari callers, 15 SegDup VCFs, and one SMN12 summary. E4 also had 4,539 usable successful benchmark rows; 242 failed attempts and 18 success-labelled rows with `s=NA` remain excluded and auditable. |
| E4-003 | Harvest a bounded, checksum-bound evidence snapshot through DYEC without copying large primary callsets or changing E4. | SUCCESS | Gate 1 | `compact_evidence.json`, 5,303,092 bytes, SHA-256 `a49254c836f6507f5ce5910ba6f3f0b1099e72f6e7063245478eb48a05204f0c`; capture 2026-08-18T17:54:41Z through 17:55:26Z. Its 5,161-entry source inventory and receipt are under `evidence/raw/E4/`. E4 was running at both boundaries with no controller, `day_run`, or Snakemake RC. |
| COV-001 | Validate one native-SR and one LR Mosdepth total mean for every plotted E4 observation; retain RSR only as an explicitly named audit field when available. | SUCCESS | Gate 1 | All 32 retained rows passed strict source-path checks: vertical coordinates come from `sentdhiomr2sr/smd`, horizontal coordinates from `sentdhiomr2lr/na`, and RSR only from the separately named `sentdhiomr2rsr/na` audit field. E4 native-SR range is 0.56x to 43.73x and LR range is 0.57x to 18.77x. |
| BUILD-001 | Extend the report generator for partial E4 metric availability while preserving all E1/E3/P1 rows and existing report sections. | SUCCESS | Gate 1 | `build_report.py` now parses the compact E4 contract, rejects incomplete core cardinalities, preserves the previous experiment sections, and labels E4 benchmark accounting as partial. |
| BUILD-002 | Rebuild the Markdown report, tables, figures, provenance inventory, and E4 completeness table from the bounded snapshot. | SUCCESS | Gate 1 | Rebuild produced 32 retained observations (12 prior plus 20 E4), 22 figures, 13 tables, and a refreshed 575-file SHA-256 manifest. |
| QA-001 | Run one combined validation pass for row preservation, source hashes, SR/LR axes, missing-data semantics, links, table schemas, and report generation. | SUCCESS | Gate 5 | Combined validation PASS at 2026-08-18T18:07:45Z: 12 prior rows preserved; 32 native-SR paths; 96 hard-VCF rows; 128 Truvari rows; 480 AU/gene SegDup pairs; 32 SMN rows; 5,161 inventory entries; 22 figures; 13 tables; zero missing local report links; both Python sources compile; `git diff --check` clean; all 575 output checksums verify. |
| QA-002 | Inspect representative regenerated figures for label, coordinate, and missing-cell legibility. | SUCCESS | Gate 5 | Visually inspected the measured-coverage grid, hard-VCF SNP F-score heatmap, and SMN copy-number heatmap after regenerating all figures. Numeric native-SR/LR axes and near-neighbor label offsets are legible; point centers remain at exact measured coordinates. |
| DOC-001 | Finalize the ledger with artifact paths, snapshot time, evidence counts, limitations, and terminal status for every row. | SUCCESS | Gate 5 | Ledger finalized 2026-08-18T18:07:45Z. No E4 workflow/Slurm action, FSx mutation, export/delete, Slack post, or Git commit/push/tag occurred. |

## Acceptance

- The 12 prior observations remain present and unchanged in provenance.
- Each E4 result enters only the metric table(s) whose source artifacts exist,
  parse, and pass their expected schema; missing files are not synthesized.
- No E4 result is plotted unless both measured native-SR and measured LR
  coverage are available. RSR never supplies the Illumina plot coordinate.
- The report states E4 snapshot time, per-metric usable counts, and that E4 was
  nonterminal at capture.
- All ledger rows reach a terminal status and the rebuilt report passes a
  single combined validation/visual-QA cycle.

## Final artifacts and boundary

- Rebuilt report:
  `docs/jem_reports/hg002_bjuice_downsample_combined_report.md`.
- Bounded E4 evidence and receipt:
  `docs/jem_reports/hg002_bjuice_downsample_combined_report_assets/evidence/raw/E4/`.
- E4 completeness matrix:
  `docs/jem_reports/hg002_bjuice_downsample_combined_report_assets/tables/e4_snapshot_completeness.tsv`.
- Regenerator and collector:
  `reports/hg002_bjuice_combined_report/build_report.py` and
  `reports/hg002_bjuice_combined_report/collect_compact_e4_evidence.py`.
- Output checksum manifest:
  `reports/hg002_bjuice_combined_report/output_checksums.sha256`.

This artifact is a valid partial-result snapshot, not a declaration that the
E4 workflow finished. Core per-AU report inputs were complete for all 20 AUs at
capture, while benchmark cost and runtime values remain lower bounds until a
terminal E4 snapshot is harvested and the report is regenerated.
