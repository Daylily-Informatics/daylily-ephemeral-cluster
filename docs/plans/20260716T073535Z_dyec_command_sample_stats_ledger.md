# DYEC command sample-stats execution ledger

## Objective

Add a strict, read-only `dyec command sample-stats` interface for the HIOMRS kitchensink pipeline. The command must emit a stable JSON document and a human table covering execution provenance, budgets, overall job progress (including retry count), per-analysis-unit milestone state and QC values, and an optional verified DAG PNG download to an explicitly named local path.

## Gate 0 inventory

- Source repository: `git@github.com:lsmc-bio/daylily-ephemeral-cluster.git`
- Clean worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-command-sample-stats-20260716`
- Branch: `codex/dyec-command-sample-stats`
- Baseline: `origin/main` at `b67497cbd1a2df52453a3e9c988f628471006682`, annotated tag `10.3.21`
- Baseline worktree state: clean
- Baseline focused validation: `python -m pytest -q tests/test_analysis_status.py tests/test_cli_registry_v2.py -q` -> `182 passed`.
- Inventory sweeps: `rg` over CLI registration, analysis status, command catalog, source/payload pins, HIOMRS artifact definitions, alignstats, SegDup, ExpansionHunter, GIAB, contamination, and gender surfaces.
- Preserved unrelated checkout: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` remains on its existing dirty branch and is not edited by this work.
- Supported initial pipeline selector: `hiomrs-kitchensink`, mapped exactly to catalog command `hybrid_ilmn_ont_hiomrs_kitchensink`. `bjuice-v1` is deliberately not accepted until its artifact contract is implemented.
- Execution is read-only except for required analysis visit records and the explicitly requested local DAG destination.
- Gate 0 also found a completed Intel Spot/On-Demand template split in the preserved dirty checkout. Its feature files and terminal execution ledger are being transplanted onto this clean current-`main` release branch; unrelated runtime-cache reports, inventories, stale pin edits, and ledgers remain excluded.

## Contract decisions

- The CLI name is a required argument and is the sole top-level JSON key.
- `ANALYSIS_UNIT_UID` in `config/units.tsv` is authoritative for each DayOA analysis-unit row. DYEC does not reconstruct, rewrite, hash, or normalize DayOA identifiers.
- Completed milestone cells report the artifact modification timestamp to whole-second UTC precision. Running cells report elapsed runtime from exact-root Slurm evidence. Unresolved terminal failure evidence reports `failed`; otherwise the state is `pending`.
- Mito is a configured per-analysis-unit VCF milestone in released DayOA `11.0.13`. DYEC resolves the exact native HIOMRS `<analysis-unit>.mito.vcf.gz` path, reports its artifact/running/failure state, and includes it in the unit completion denominator.
- The per-library-unit table additionally reports specimen type, sample use, order type (`positive_control`, `rns`, or `clinical` when explicitly sourced), final QC disposition, final data package ready, final data package delivered, and optional F-score versus truth. Missing metadata remains `null` with source/state evidence and is never inferred from identifiers.
- The top-level retry count is evidence-derived from Snakemake retry/restart records, not inferred from completed artifacts.
- Missing required provenance, manifests, catalog entries, active profile configuration, or ambiguous DAG selection fail clearly. Metrics that are legitimately not yet produced remain `null` with source/state evidence; they are not converted to zero.
- Remote DAG transfer uses bounded SSM chunks and SHA-256 verification. It does not use SSH/SCP, a mutable S3 staging object, or an unverified partial copy.

## Execution rows

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence / terminal note |
|---|---|---|---|---|---|---|---|
| G0 | Inventory | Freeze clean baseline, instructions, current CLI/status implementation, pins, and DayOA HIOMRS artifact contract. | SUCCESS | contract_test | Gate 0 | Codex | Baseline, preserved dirty checkout, sweeps, and `182 passed` baseline recorded above. |
| S1 | Collector | Implement strict source-backed HIOMRS sample-stat collector without identifier rewriting or inferred metadata. | SUCCESS | feature_implementation | Gate 4 | Codex | `daylily_ec/command_sample_stats.py`; tests prove authoritative unique `ANALYSIS_UNIT_UID`, timestamps/running/failed/pending state, configured denominator, QC and metadata sources. |
| S2 | CLI | Add `dyec command sample-stats` JSON/table interface with one required report-name key. | SUCCESS | feature_implementation | Gate 3 | Codex | Explicit `command/sample-stats` registry entry, JSON and human rendering tests, exact `hiomrs-kitchensink` selector; `bjuice-v1` fails clearly. |
| S2A | Table | Add requested disposition, package, truth, specimen/use/order, relatives, sex, contamination, coverage, read length, and insert-size fields. | SUCCESS | feature_implementation | Gate 3 | Codex | Source-backed nullable fields and table columns are covered by `tests/test_command_sample_stats.py`. |
| S2B | Provenance/cost | Report cluster/AZ, runtime/tmux, versions/catalog/env/commands/retries, AWS cluster budget, project cost-center budget, and completed benchmark cost. | SUCCESS | feature_implementation | Gate 4 | Codex | Local evidence plus read-only AWS enrichment; test proves AZ, cluster limit/spend/forecast, and project usage. Secret-like environment names are excluded. |
| S2C | DAG | Download one explicitly named DAG using verified local copy or bounded SSM chunks. | SUCCESS | legitimate_safety_handling | Gate 4 | Codex | SHA-256/size verification, 20 MiB remote bound, collision refusal, partial cleanup, and transfer tests. No SCP or mutable S3 staging. |
| PA1 | Mito amendment | Reconcile requested Mito column with the released DayOA artifact contract. | SUCCESS | plan_amendment | Gate 4 | Codex | Annotated DayOA tag `11.0.13` adds the native HIOMRS mito VCF/TBI/done contract. DYEC now reports that exact artifact and includes it in progress. |
| S3 | Tests/docs | Add focused regression tests and an exact README invocation/field contract. | SUCCESS | contract_test | Gate 5 | Codex | `tests/test_command_sample_stats.py`, registry/pin tests, and `README.md`. |
| I1 | Intel templates | Carry the completed explicit Intel Spot/On-Demand template split onto current `main` without importing unrelated dirty-tree work. | SUCCESS | feature_implementation | Gate 4 | Codex | Imported only the split templates, exact consumer/test edits, and `20260716T025545Z_intel_spot_ondemand_template_split_ledger.md`; preserved newer max-count and Slurm-accounting tests while resolving overlaps. |
| S4 | Validation | Run formatting/lint, type checks, focused tests, source/payload parity, full suite, and package build. | SUCCESS | contract_test | Gate 5 | Codex | Combined candidate: Ruff and diff check passed; focused sample-status/catalog/Intel suite `481 passed`; full suite `2219 passed, 11 skipped` in 72.47s; wheel build succeeded and contains the collector, pinned catalog, and all 15 Spot plus 15 On-Demand packaged templates. Initial focused mypy also found no issues. |
| R1 | Pins | Pin both catalog copies to DayOA `11.0.13` and keep source/package defaults in the two-step DYEC release train. | SUCCESS | config_or_startup_contract | Gate 2 | Codex | DayOA annotated tag `11.0.13` peels to `c1494347249d66b22d3a9252784277d05bd9c1c6`; source/package catalogs match and all catalog/fork/package tests pass. |
| R2 | Feature release | Commit and push the combined candidate on `codex/dyec-command-sample-stats`, then create and verify annotated tag `10.3.22` without merging to `main`. | SUCCESS | feature_implementation | Gate 5 | Codex | Commit `ff83ea8b13ebf8aeb0b2c40967e4f4b00bfa2a1f` pushed; annotated tag object `291d5466d1ad03465400d08bd078b747c6b9120e` peels to that commit. |
| R3 | Self-pin release | Advance both source/package DYEC defaults to `10.3.23`, commit, push, and create a second verified annotated tag. | IN_PROGRESS | config_or_startup_contract | Gate 5 | Codex | Source/package self-pins and the fork contract now target the final `10.3.23` tag; focused validation and release remain. |
| S5 | Closeout | Record terminal release evidence and ensure no working rows remain. | OPEN | contract_test | Gate 5 | Codex | Awaiting R2-R3. |

## Completion gate

The release objective is complete only when every release row above is terminal,
focused tests prove JSON/table/state/DAG behavior, CLI registry tests include the
command, documentation gives an exact invocation, annotated tags `10.3.22` and
`10.3.23` point to the intended feature-branch commits, final tag `10.3.23`
self-pins `10.3.23` and DayOA `11.0.13`, and the release worktree has no
unexplained changes. No merge to `main` is part of this user-requested release.
