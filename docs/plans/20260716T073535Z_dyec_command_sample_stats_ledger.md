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

## Contract decisions

- The CLI name is a required argument and is the sole top-level JSON key.
- `ANALYSIS_UNIT_UID` in `config/units.tsv` is authoritative for each DayOA analysis-unit row. DYEC does not reconstruct, rewrite, hash, or normalize DayOA identifiers.
- Completed milestone cells report the artifact modification timestamp to whole-second UTC precision. Running cells report elapsed runtime from exact-root Slurm evidence. Unresolved terminal failure evidence reports `failed`; otherwise the state is `pending`.
- Mito remains a requested per-analysis-unit VCF milestone. Current DayOA `11.0.12` does not include a mitochondrial artifact in `HIOMRS_FINAL_OUTPUT_PATTERNS` or `produce_hiomrs`, so this DYEC release reports `not_configured`, does not include Mito in the unit completion denominator, and never claims a call exists. A later DayOA contract may replace this state only after its exact output path is released.
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
| PA1 | Mito amendment | Reconcile requested Mito column with current released DayOA source. | NO_LONGER_NEEDED | plan_amendment | Gate 4 | Codex | DayOA `11.0.12` has no native HIOMRS mito final artifact. DYEC reports `not_configured`; implementing a caller belongs to a future DayOA release and is not fabricated here. |
| S3 | Tests/docs | Add focused regression tests and an exact README invocation/field contract. | SUCCESS | contract_test | Gate 5 | Codex | `tests/test_command_sample_stats.py`, registry/pin tests, and `README.md`. |
| S4 | Validation | Run formatting/lint, type checks, focused tests, source/payload parity, full suite, and package build. | SUCCESS | contract_test | Gate 5 | Codex | `ruff check` and `git diff --check` passed; focused suite `222 passed`; full suite `2215 passed, 11 skipped` in 71.61s; focused mypy found no issues (environment warns its configured Python 3.9 target is older than this mypy supports); isolated pip wheel build succeeded and contains the collector plus both packaged configs. |
| R1 | Pins | Pin both catalog copies to DayOA `11.0.12` and both global defaults to DYEC `10.3.22`. | SUCCESS | config_or_startup_contract | Gate 2 | Codex | Source and packaged files match; fork/payload/catalog tests pass. |
| R2 | Release | Commit, push, open PR, wait for green checks, and merge to `main`. | IN_PROGRESS | feature_implementation | Gate 5 | Codex | Awaiting release workflow. |
| R3 | Tag | Create and push an annotated `10.3.22` tag from the clean merged `main` commit and verify it. | OPEN | feature_implementation | Gate 5 | Codex | Must not move a pushed tag; remote tag availability will be rechecked immediately before creation. |
| S5 | Closeout | Record terminal release evidence and ensure no working rows remain. | OPEN | contract_test | Gate 5 | Codex | Awaiting R2-R3. |

## Completion gate

The objective is complete only when every row above is terminal, focused tests prove JSON/table/state/DAG behavior, CLI registry tests include the command, documentation gives an exact invocation, `main` contains the release commit, annotated tag `10.3.22` points to that commit, and the release worktree has no unexplained changes.
