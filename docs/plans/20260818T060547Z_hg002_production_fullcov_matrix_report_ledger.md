# HG002 production full-coverage matrix-report refresh ledger

Created: 2026-08-18T06:05:47Z

Controlling request: locate the checked-in HG002 downsample matrix report; add the completed Bjuice v0.9 production HG002 AU with full Illumina and ONT `[0,24]` input; base its placement on measured short-read (SR) and long-read (LR) coverage rather than a requested target; regenerate the entire report; and commit/push the refreshed report to `main`.

## Gate 0 baseline

- Clean worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-hg002-production-fullcov-report-20260818`
- Branch: `codex/hg002-production-fullcov-report-20260818`
- Base: `origin/main` at `12288f5f410768e09246da116ef8c28687dd67aa` (`Merge HG002 Bjuice report update`)
- Existing report: `docs/jem_reports/hg002_bjuice_downsample_combined_report.md`
- Existing renderer: `reports/hg002_bjuice_combined_report/build_report.py`
- Existing collector: `reports/hg002_bjuice_combined_report/collect_evidence.sh`
- Production source export: `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022-bjuice-preval6-15014-dry-20260817t112900z/daylily-omics-analysis/`
- Production HG002 runtime AU: `HG002-qvmjccyp5fr1y3`
- Input contract: full Illumina and ONT `[0,24]`; no requested coverage target exists for this observation. Its measured SR coordinate is the native `sentdhiomr2sr/smd` Mosdepth `chrom=total` mean, explicitly not `rsr`.
- Original shared checkout is dirty with unrelated work and remains untouched.

## Control rows

| ID | Requirement | Status | Evidence / terminal note |
| --- | --- | --- | --- |
| G0-001 | Locate the current checked-in report and generator on `origin/main`. | SUCCESS | Report tip is `16fb6bdb69f6ac822191c356381b39b42e108a54`; current `origin/main` merge is `12288f5f410768e09246da116ef8c28687dd67aa`. |
| SRC-001 | Build a bounded, hash-audited production evidence bundle from the exported E1 HG002 AU. | SUCCESS | Read-only S3 extract captured 34 report-relevant objects, 239 successful HG002 benchmark rows, all source SHA-256 values, native-SR Mosdepth 43.73×, and LR Mosdepth 11.43×. A second extraction was byte-identical: `e5e39cac5d3d48e413cefd0a79cf0f9b50021f5ab7fd33cd42dde69426d0fa6b`. |
| MOD-001 | Extend the renderer/collector so a no-target full-coverage observation can coexist with E1/E2 downsample observations. | SUCCESS | Added P1 full-input parser/collector and a strict native-SR-not-RSR measurement contract; target and target-error values are represented as `NA`. |
| REP-001 | Regenerate Markdown, figures, tables, source inventory, and checksums from all 19 observations. | SUCCESS | Generated 22 figures and 13 tables; the report retains 19 observations and zero exact duplicates. |
| QA-001 | Verify source hashes, row counts, chart/table reconciliation, Markdown links, and no-target semantics. | SUCCESS | 1,107 asset checksums verify; all Markdown local links resolve; P1 row is 43.73× SR × 11.43× LR with `NA` target/error fields; coverage grid and GIAB heatmap visually reviewed. |
| GIT-001 | Commit only report-refresh artifacts and this ledger, then push the fast-forward update to `origin/main`. | SUCCESS | `a339091ee8681fcad7c5fe2fed8fb015955dab7a` was pushed fast-forward to `main` from reviewed base `12288f5f410768e09246da116ef8c28687dd67aa`; no force push or unrelated worktree content was included. |

## Completion criteria

- The production row is labelled as a distinct production observation, not an E1/E2 downsample observation.
- Its coverage grid coordinates are exact SR and LR Mosdepth `chrom=total` values.
- Its target-related fields are `NA`, not zero or an inferred nominal value.
- The report, all linked assets, bounded evidence, source inventory, and checksums are committed.
- All ledger rows are terminal and the pushed `main` URL resolves to the refreshed report.
