## Control Ledger

Controlling request: Make the ILMN, ONT, Ultima, and CG solo kitchensink catalog commands run chromosomes `1-25`; rename the full-prevalence BJuice HIOMR2 Inflection product to `inflection-bjuice-product-v0.9`, with all supplied ONT FASTQs selected by default.

Ledger path: `docs/plans/20260817T091620Z_full_chromosomes_bjuice_v09_catalog_ledger.md`

### Gate 0 baseline

- Repository: `/tmp/dyec-release-18.0.23.3wZBhp/repo`
- Baseline ref: annotated tag `18.0.23` at `0662a215`.
- Working branch: `codex/dyec-18.0.24-full-chromosomes-bjuice-v09`.
- Baseline status: clean before this ledger was added.
- Sweep evidence:
  - Current catalog commands `illumina_hg002_kitchensink_multiqc`, `ont_snv_alignstats_kitchensink`, `ultima_snv_alignstats_kitchensink`, and `complete_genomics_cg_snv_concordance` inherit the four DayOA caller defaults currently set to `1-24`.
  - Generic `hiomr2` already uses the `1-25` HIOMR2 profile default.
  - The current long BJuice v2 command has explicit `1-25` scope but sets `ont_fastq_hour_window_mode=per_analysis_unit`.
  - Historical catalog snapshots remain unchanged; the source and packaged catalog mirrors must stay byte-identical.
- Authority and limits:
  - The user explicitly authorized the active catalog/default change and command rename.
  - Amendment 2026-08-17: the default is all supplied ONT FASTQs, but the released DayOA configuration contract must continue to accept an explicit global `ONT[n,n+n)` slice through paired hour-bound configuration keys.
  - No active controller, FSx/S3 export, or Slurm job is changed by this work.
  - The current catalog will point only to a released immutable DayOA tag; no pinned checkout is patched.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DYEC-001 | Current command catalog | Replace the current long BJuice v2 command ID with `inflection-bjuice-product-v0.9`, remove its default per-analysis-unit selector, and document the retained explicit config-based `ONT[n,n+n)` slice. | DONE | feature_implementation | Gate 3 | Codex | Active source and packaged catalog mirror both use `inflection-bjuice-product-v0.9`, the 5x+5x config, all-ONT default, and paired global slice keys. |  | Historical snapshots retained; no legacy active alias retained. |
| DYEC-002 | Current command catalog | Consume DayOA full-chromosome/all-ONT v0.9 contracts and pin the current catalog to immutable DayOA `15.0.14`. | DONE | feature_implementation | Gate 2 | Codex | Active top-level and `dyec_builds.current` pins are `15.0.14`; the tag resolves to the exact DayOA 15.0.12 source commit. |  | DayOA 15.0.13 is intentionally not selected. |
| DYEC-003 | Catalog contracts | Update source/package mirrors and add focused positive/negative contract tests; retain history unchanged. | DONE | contract_test | Gate 5 | Codex | Both YAML files parse and compare byte-for-byte; direct solo commands explicitly select 1-25. |  | No Git tests were run by user direction; prerelease command-catalog testing is the next gate. |
| DYEC-004 | DYEC release | Commit, push, annotate, and publish DYEC release `18.0.24` after the DayOA release and validation. | READY | feature_implementation | Gate 5 | Codex | Release runbook and prerelease notes included in the exact release commit. |  | Publish as prerelease only; no merge to main. |
