# HG002 Bjuice native-SR measured-coverage matrix refresh ledger

UTC opened: 2026-08-18T08:03:25Z
Owner: Codex
Controlling request: recreate the complete HG002 Bjuice downsample matrix
report so that the plotted Illumina coordinate is native short-read (SR)
Mosdepth coverage rather than realigned short-read (RSR) coverage. Add a
top-of-report per-experiment/per-AU sanity table containing LR×, native SR×,
realigned SR×, requested Illumina target, and requested ONT target.

## Scope and safety boundary

- Worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-hg002-bjuice-native-sr-matrix`
  on `codex/hg002-bjuice-native-sr-matrix-report`, clean from
  `origin/main` commit `ec1589f5b4d127ae1ae5a505d37dc30f73ae6d30`.
- No workflow execution, raw Snakemake invocation, Slurm intervention, DRA
  mutation, export, deletion, or source-analysis rewrite is authorized.
- Read-only collection of the exact Mosdepth summaries from the known completed
  analysis roots/S3 exports is authorized by the request. Every missing or
  ambiguous source must fail closed rather than be substituted.
- The canonical axis contract is native SR
  `align/sentdhiomr2sr/smd/alignqc/mosdepth/*.summary.txt`, LR
  `align/sentdhiomr2lr/na/alignqc/mosdepth/*.summary.txt`, each using
  Mosdepth `chrom=total` mean. RSR is retained only as the explicit audit
  value from `align/sentdhiomr2rsr/na/alignqc/mosdepth/*.summary.txt`.

## Gate 0 baseline

- Current report: `docs/jem_reports/hg002_bjuice_downsample_combined_report.md`.
- Current renderer: `reports/hg002_bjuice_combined_report/build_report.py`.
- Current retained observations: 19 total—E1=7, E2=7, E3=4, P1=1.
- Diagnosis: the renderer currently globbed RSR at
  `build_report.py:382`; the retained table has 18 RSR ILMN sources and only
  P1 native SR. Direct inspection confirms each of the seven E1 ILMN sources
  is `align/sentdhiomr2rsr/na/alignqc/mosdepth/*.summary.txt`, so E1's
  rendered "SR" coordinate is realigned SR, not native SR. P1 already
  validates native SR explicitly.
- Existing evidence has 18 RSR Mosdepth summaries and one native-SR P1 summary;
  it cannot reproduce a native-SR matrix without fresh bounded source capture.
- Known source roots:
  - E1 `/fsx/analysis_results/prod-cand-1703/prod-cand-1703-hg002-bjuice-v2-multiau-20260814T114522Z`
  - E2 `/fsx/analysis_results/prod-cand-1703/prod-cand-1703-hg002-bjuice-v2-seqkitfix-20260815T080300Z`
  - E3 `/fsx/analysis_results/prod-cand-1703/prod-cand-1703-hg002-bjuice-4au-kitchensink-20260817T025004Z`, exported under
    `s3://lsmc-dayoa-analysis-results-usw2/derived/bjuice-v2-multi-analysis-unit/prod-cand-1703/prod-cand-1703-hg002-bjuice-4au-kitchensink-20260817T025004Z/`
  - P1 `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022-bjuice-preval6-15014-dry-20260817t112900z/daylily-omics-analysis/`
- P1 has no requested target; both target cells must remain `NA`.

## Tracked rows

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence / terminal note |
|---|---|---|---|---|---|---|---|
| G0 | Baseline | Record the native-SR correction contract, source roots, counts, clean worktree, and non-destructive boundary | SUCCESS | plan_amendment | Gate 0 | Codex | Baseline above records the original RSR-axis diagnosis before edits. |
| SCOPE-1 | Revised scope | Produce the report only from direct-S3-audited E1/E3/P1 data; consume no E2 result or metric | SUCCESS | scope_amendment | Gate 0 | Codex | User explicitly narrowed the regenerated report to E1 (7), E3 (4), and P1 (1). E2 is not present in the report, tables, figures, source capture, or remaining asset bundle; 535 tracked raw-E2 files and `E2.tar.gz` were removed from this report bundle. |
| SRC-1 | E1 source evidence | Capture exactly one native-SR, one RSR, and one LR Mosdepth summary for each of seven E1 runtime AUs, with source path and SHA-256 | SUCCESS | active_product_contract | Gate 0 | Codex | Direct S3 capture at `2026-08-18T10:03:39Z` recorded seven triples in `assets/evidence/direct_s3_coverage_regather.tsv`; all native-SR means are 43.73× and share SHA-256 `5db712bdee30b383422f5729ea73497896aca01fd2db749b39a1b829c6484f80`. |
| SRC-2 | E2 source evidence | Do not substitute E2 data into the revised E1/E3/P1 report | SUCCESS | scope_amendment | Gate 0 | Codex | Historical investigation remains above, but E2 is intentionally excluded from this deliverable and its unavailable native-SR summaries are not inferred. |
| SRC-3 | E3 source evidence | Capture exactly one native-SR, one RSR, and one LR Mosdepth summary for each of four E3 runtime AUs, with source path and SHA-256 | SUCCESS | active_product_contract | Gate 0 | Codex | Direct S3 capture at `2026-08-18T10:03:39Z` recorded four triples from the completed E3 export. |
| SRC-4 | P1 source evidence | Revalidate native-SR, RSR, and LR Mosdepth summaries for the P1 full-input AU, with source path and SHA-256 | SUCCESS | active_product_contract | Gate 0 | Codex | Direct S3 capture at `2026-08-18T10:03:39Z` recorded the P1 triple; target cells remain `NA`. |
| MOD-1 | Evidence collector | Use an explicit three-coverage direct-S3 capture contract and reject missing/duplicate summary files | SUCCESS | feature_implementation | Gate 1 | Codex | Added `reports/hg002_bjuice_combined_report/collect_direct_s3_coverage.py`; it reads exactly 36 summaries, hashes each payload, requires E1/E3/P1 exact values, and writes the audit TSV. |
| MOD-2 | Renderer | Position every coverage-coordinate chart using native SR× and LR×; retain RSR× only as provenance/audit data | SUCCESS | feature_implementation | Gate 1 | Codex | Renderer asserts native `sentdhiomr2sr/smd` and LR `sentdhiomr2lr/na` source paths; RSR is retained under its own field. Ten occupied measured coordinates use equal numeric x/y coverage scales. |
| MOD-3 | Report | Add the requested six-column top sanity table and direct-S3 diagnosis | SUCCESS | feature_implementation | Gate 1 | Codex | Report begins with `ID,target ILMNx, SR ILMNx, RSR ILMNx,target ONTx,LRONTx`; targets appear only there and P1 retains `NA`. |
| REP-1 | Regeneration | Recreate the Markdown report, figures, tables, source inventory, and direct-S3 receipt from the new contract | SUCCESS | feature_implementation | Gate 1 | Codex | Regenerated report, 22 figures, 12 tables, direct-S3 evidence, and reproducible collector. E1’s actual full-SR/variable-LR geometry and selective-RSR explanation are documented. |
| QA-1 | Contract checks | Prove 12 E1/E3/P1 rows, one of each coverage source per AU, native-SR axis sources, RSR audit values, coordinate mapping, and valid links | SUCCESS | contract_test | Gate 5 | Codex | Final focused local validator passed at `2026-08-18T10:25:14Z`: `direct_s3_rows=12 retained=12 coordinates=10 charts=22 links=complete`; visual QA confirmed no coordinate-label overlap and numeric equal-scale placement. |
| GIT-1 | Delivery | Commit and push the regenerated report and supporting evidence on request | SUCCESS | delivery | Gate 5 | Codex | User authorized publication on 2026-08-18. The containing feature-branch commit publishes the corrected report, regenerated figures/tables, direct-S3 receipt, collector, renderer, and this ledger. Inventory found no separate duplicate Markdown/HTML report drafts to delete: the corrected report replaces the sole tracked report in place. The scoped E2 raw-evidence bundle is removed as part of the requested E1/E3/P1-only deliverable; Git history is not rewritten. |
| VIS-1 | Metric-circle labels and density | Remove opaque C## coordinate codes from every report figure; print the plotted metric within a fill-only circle whose area is 25% larger, with a clearly non-metric 2D coordinate-density overlay | SUCCESS | report_correction | Gate 5 | Codex | User-directed correction on 2026-08-18. All coordinate figures now use actual metric text: occupancy for availability, F-score/FN/FP or GT concordance for concordance, call count for SegDup, and copy number/NA for SMN. `CIRCLE_MARKER_AREA=600` is 25% above the former 480 pt² marker area; circles have no colored edge. Dashed density contours reflect only retained-AU coordinate density and explicitly do not interpolate metric values into blank space. |
| PLAN-1 | Compact AU matrix proposal | Preserve the original 81-cell factorial as a deferred ideal, but select a presentation-first subset that reuses all current E1/E3/P1 evidence without launching workflows | SUCCESS | planning | Gate 0 | Codex | The proposal was amended on 2026-08-18 to 20 new controlled AUs (N01–N20) plus all 12 current direct-S3-audited outcomes. It fully crosses 0.5×, 2×, 10×, and 20× ILMN targets at ONT `[0,1)`, `[0,8)`, `[0,24)`, and `[0,72)` windows, then adds the 5×/15×/30×/full long-LR ladder. Its compact matrix plot, proposed-cell TSV, and full current-observation reuse TSV are under the proposal asset directory. It remains explicitly non-executing. |
| CONFIG-1 | 20-AU Bjuice execution capsule | Generate a supported catalog-input six-manifest set from the exact reviewed source inputs, terminal direct-ILMN receipt, and explicit custom AU plan | SUCCESS | configuration | Gate 1 | Codex | `dyec 18.0.41` ran `catalog config-bjuice-v2-hg002-multi-au` locally with profile `lsmc`/region `us-west-2`, producing `bjuice_hg002_20new_execution_config/manifests/` and receipt `bjuice_v2_hg002_multi_au_manifest_receipt.json`. The receipt records 20 AUs, the 43.73× direct-ILMN denominator, six manifest SHA-256 values, and explicit-custom-matrix mode. Focused validation matched all 20 labels, fractions rounded down to 12 decimal places, and ONT intervals; no render or launch occurred. |

## Read-only evidence log

- AWS CLI read at the 72-hour cut-off `2026-08-15T08:29:55Z`:
  `aws fsx describe-data-repository-tasks --profile lsmc --region us-west-2`
  filtered to `EXPORT_TO_REPOSITORY` returned twelve successful tasks. Each
  source path was under `/analysis_results/pre-rel-18025/`; none was either
  E1 `prod-cand-1703-hg002-bjuice-v2-multiau-20260814T114522Z` or E2
  `prod-cand-1703-hg002-bjuice-v2-seqkitfix-20260815T080300Z`. The same
  result held when cross-checked from the calendar start
  `2026-08-15T00:00:00Z`. This establishes only that no matching export task
  exists in the requested three-day window.
- Renderer/evidence read: `build_report.py:382` chooses
  `align/sentdhiomr2rsr/na/alignqc/mosdepth/*.summary.txt` for E1/E2/E3;
  `retained_observations.tsv` records all seven E1 plotted ILMN paths under
  that same RSR directory. Consequently, the existing E1 matrix is not an
  acceptable native-SR matrix and must not be relabelled as one.
- Current-headnode presence read as `ubuntu` through `dyec headnode run`:
  both E1 and E2 analysis roots returned `Analysis root does not exist` and
  have no clone on `pre-rel-18025`. No file was changed and no workflow or
  Slurm action was taken.
- E1 S3 read using AWS CLI: the canonical completed-output prefix
  `s3://lsmc-dayoa-analysis-results-usw2/derived/bjuice-v2-multi-analysis-unit/prod-cand-1703/prod-cand-1703-hg002-bjuice-v2-multiau-20260814T114522Z/daylily-omics-analysis/`
  lists seven native-SR, seven RSR, and seven LR Mosdepth `*.summary.txt`
  files under `results/day/hg38/`. This source was not declared in the
  current report's `source_s3_uris.tsv`, but is a valid bounded source for
  SRC-1 capture.
- Prefix inventory read using AWS CLI: under
  `s3://lsmc-dayoa-analysis-results-usw2/derived/bjuice-v2-multi-analysis-unit/`,
  the only top-level prefixes are `_report_evidence/` and `prod-cand-1703/`.
  The latter has exactly two completed-output children: E1
  `prod-cand-1703-hg002-bjuice-v2-multiau-20260814T114522Z/` and later E3
  `prod-cand-1703-hg002-bjuice-4au-kitchensink-20260817T025004Z/`. Exact
  AWS CLI searches for E2's `seqkitfix-20260815T080300Z` identifier returned
  no key under this Bjuice parent or under the matching
  `s3://lsmc-ssf-sequencing-data/derived/prod-cand-1703/` candidate root.
- Exact-commit Git provenance read at `a339091e`: E2's
  `collection_receipt.tsv` records the original FSx analysis root and only 14
  captured coverage summaries. The embedded `dayoa_evidence_manifest.json`
  records all seven missing native-SR Mosdepth relative paths, byte sizes, and
  SHA-256 values. The asset bundle has no E2 export receipt, DRA/task ID, S3
  destination, FSx ID, or copy of those seven files; its final MultiQC data
  was not included either.
- CloudTrail read for 2026-08-14 through 2026-08-18: former FSx
  `fs-0d3d8cd3df85ab151` has DRA/export events for E1 and E3 but none for E2.
  `DeleteFileSystem` at `2026-08-17T08:42:57Z` used
  `skipFinalBackup=true`. `fsx describe-backups` and AWS Backup both return
  zero surviving recovery points for that filesystem.
- Namespace cross-check: `lsmc-dayoa-analysis-results-usw2` has no
  `derived/pc*` or `derived/prod*` keys. The actual
  `s3://lsmc-ssf-sequencing-data/derived/prod-cand-1703/` namespace contains
  six sibling exports, but exact searches find neither E2's analysis ID nor
  the unique native-SR filename
  `HG002-5r2pnnjbw114ye.sentdhiomr2sr.smd.mosdepth.summary.txt`.

## Acceptance

- The top sanity table covers the 12 retained E1/E3/P1 experiment/AU
  observations and exposes the three independent measured coverages plus the
  requested targets. No E2 row or metric is present.
- Every plotted Illumina coverage coordinate originates from native SR
  Mosdepth; every realigned-SR coordinate remains audit-only and cannot drive
  a chart position.
- All 12 observations are provenance- and hash-auditable to the completed S3
  exports; P1 has no invented target.
- All report outputs are regenerated from the corrected data model. The
  collector, renderer, evidence, Markdown, tables, and figures are ready for
  review in the feature worktree; commit/push remains explicitly out of scope.

## Completion evidence

- Direct S3 re-gather: `assets/evidence/direct_s3_coverage_regather.tsv` and
  the report-linked copy under `assets/tables/`; 36 Mosdepth payloads across
  12 AUs are recorded with full S3 URI and SHA-256 evidence.
- Regeneration: `python reports/hg002_bjuice_combined_report/build_report.py`
  produced 12 retained observations, 11 concordance heatmaps, 14 heatmaps in
  total, 22 figures, and 12 tables.
- Focused validation: `python /tmp/validate_hg002_native_sr_report.py` passed
  at `2026-08-18T10:25:14Z` with
  `direct_s3_rows=12 retained=12 coordinates=10 charts=22 links=complete`.
- Visual QA: inspected the measured-coverage grid, a Hard-VCF F-score
  heatmap, the SegDup facet grid, and the SMN facet grid. The original C##
  labels are removed; each displayed coordinate now prints its actual plotted
  value or retained-observation count.
- Visual correction regeneration at 2026-08-18T11:25:20Z: the renderer emitted
  12 retained observations, 11 concordance heatmaps, 14 heatmaps total, 22
  figures, and 12 tables. Static validation found no `C##`,
  `coordinate_id`, square-marker, or colored-edge implementation remaining
  in the public report renderer/tables. The density contour is computed only
  from the twelve retained AU coordinates using a fixed 1.25× by 1.25×
  coverage-unit kernel and is labelled as non-metric in the report/figures.
