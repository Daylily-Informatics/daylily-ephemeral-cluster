# DYEC analysis status and HIOMRS double-release ledger

## Objective

Add an exact-analysis-root `dyec analysis status slim|full` inspection command, retire the active legacy HIOMR catalog recipes in favor of HIOMRS, pin the HIOMRS recipes to DayOA 11.0.12, and complete the requested two-stage DYEC release train without absorbing unrelated dirty work.

## Gate 0 inventory

- Clean worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-analysis-status-hiomrs-20260716`
- Branch: `codex/analysis-status-hiomrs-release-20260716`
- Baseline: `origin/main` at `a2cf96b3aec8576e3f32cadbcc299fc8b1c3a106`
- Remote: `git@github.com:lsmc-bio/daylily-ephemeral-cluster.git`
- DayOA release to pin: annotated tag `11.0.12`, commit `cb1896912c9182aa95d2a84760cd3c3882d4c4c3`
- Existing DYEC self-pin: `10.3.19`
- Existing primary checkout is intentionally excluded because it contains unrelated dirty work.
- Live DayOA controllers and analysis roots are out of scope; this release train does not mutate them.

## Execution ledger

| Row | Work item | State | Evidence |
|---|---|---|---|
| 1 | Inventory clean source and release boundary | PASS | Gate 0 above |
| 2 | Implement `dyec analysis status slim|full` | PASS | Focused CLI/status/lock suite passed; local and supported SSM paths covered |
| 3 | Retire active legacy HIOMR catalog entries | PASS | Source/package catalogs omit both legacy IDs; tests select HIOMRS |
| 4 | Pin HIOMRS catalog commands to DayOA 11.0.12 | PASS | Default ref and both HIOMRS commands use 11.0.12; catalogs byte-identical |
| 5 | Validate first release candidate | PASS | 2,205 passed, 11 skipped; changed-code Ruff and `git diff --check` passed; repo-wide Ruff has 33 unrelated archived-doc-script findings |
| 6 | Merge and tag first DYEC release | PASS | PR #24 merged at `7e0c8bce`; annotated tag 10.3.20 pushed and verified |
| 7 | Update DYEC self-pin to the first release | PASS | Source/package defaults and fork contract target 10.3.20; 2,205 passed, 11 skipped |
| 8 | Validate and merge second DYEC release | PASS | 2,205 passed, 11 skipped; PR #25 merged at `91da9d19`; main pins DYEC 10.3.20 and DayOA 11.0.12 |
| 9 | Verify final main and publish immutable annotated tag | PASS | Source/package pins and catalogs match; 10.3.20 is annotated; final ledger merge is the prepared 10.3.21 tag target and is tagged immediately after merge |

## Acceptance contract

- `slim` reports exact-root workflow progress/state, exact-root Slurm summary, controller evidence, canonical final-artifact presence, and FSx capacity.
- `full` includes slim data plus scoped job details, stdout/stderr tails, current-log progress markers, benchmark/cost evidence, failure evidence, and bounded telemetry for allocated nodes.
- Missing Slurm, filesystem, benchmark, log, or telemetry evidence is explicit; it is never silently replaced or inferred.
- Success requires completed workflow progress and all canonical final artifacts, not merely an empty queue.
- Source and packaged catalogs remain byte-identical.
- Active catalog no longer exposes `hybrid_ilmn_ont_snv` or `hybrid_ilmn_ont_snv_kitchensink`.
- HIOMRS commands use exact DayOA tag 11.0.12.
- Both release tags are new, annotated, pushed tags and are never moved.
