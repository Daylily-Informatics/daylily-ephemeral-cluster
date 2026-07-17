# DayOA to DYEC current-branch release-train ledger

Created: 2026-07-17T08:20:16Z
Amended: 2026-07-17 after the user explicitly required publication from
whatever branch is currently checked out.

## Objective

Publish all current DayOA dirty work as annotated release `11.0.25`, advance
DYEC's active, packaged, and tested DayOA pins to `11.0.25` and publish
annotated release `10.3.29`, then advance the DYEC self-pin and publish
annotated release `10.3.30`. Preserve the checked-out branches and report exact
commits, remote refs, tests, and tag objects.

## Ordered contract

1. On DayOA branch `codex/feat-multiqc-integrity-release-11.0.24`, validate and
   commit all tracked and untracked work, push that branch, then create and push
   annotated tag `11.0.25` on the clean release commit.
2. On DYEC branch `main`, retain and commit the complete existing dirty set
   together with all active, packaged, and tested DayOA pin updates to
   `11.0.25`; push `main`, then create and push annotated tag `10.3.29`.
3. Advance both DYEC self-pin configuration copies and their contract test from
   `10.3.28` to `10.3.30`; validate, commit, push `main`, then create and push
   annotated tag `10.3.30`.

Tags are non-`v`, annotated, created only after clean commits, and must not be
moved or overwritten. No force-push, PR, branch switch, or admin merge is
authorized. Historical ledger references are not rewritten as active pins.

## Gate 0 inventory freeze

- Controlling ledger:
  `daylily-ephemeral-cluster/docs/plans/20260717T082016Z_inflection_dayoa_dyec_release_train_ledger.md`.
- DayOA repository: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`.
  Branch `codex/feat-multiqc-integrity-release-11.0.24`; base
  `18296a2e4cba487f80957e8a159224567e971300`; upstream divergence `0 0`;
  newest annotated release `11.0.24`; requested `11.0.25` absent locally and
  remotely.
- DayOA dirty scope: three tracked ExpansionHunter biological-identity fix
  files plus three untracked dated ledgers. The focused fix has live proof for
  a completed ExpansionHunter job and `165` focused source tests recorded in
  its dedicated ledger; the original controller's full downstream report was
  still in progress at that ledger's latest snapshot.
- DYEC repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`.
  Branch `main`; base `32a50e723ff113b18f5e2aa08e5ab6dd03ef4028`; upstream
  divergence `0 0`; base is annotated release `10.3.28`; requested `10.3.29`
  and `10.3.30` are absent locally and remotely.
- DYEC dirty scope: Slurm-accounting PrivateLink implementation/config/tests,
  Betelgeuser HIOMR production command-catalog copy, repository/CLI contract
  tests, and eight untracked dated ledgers including this controlling ledger.
- Pin sweep: active non-ledger `11.0.15` references occur in the source and
  packaged command catalogs, README, sample-stat diagnostics, and their tests.
  Active `10.3.28` self-pins occur in the source and packaged CLI-global config
  and the fork-contract test.
- Release validation will use the repositories' existing pytest suites plus
  `git diff --check`, source/payload byte-parity checks, branch ancestry, tag
  object type, and peeled remote-tag checks. No live workflow, cluster,
  scheduler, budget, or AWS mutation is part of this release request.

## Control ledger

| ID | Repo | Requirement | Status | Category | Approval gate | Owner | Evidence | Root cause | Terminal note |
|---|---|---|---|---|---|---|---|---|---|
| GATE0-001 | both | Freeze exact branches, dirty scope, ancestry, pin surfaces, and free tags | SUCCESS | plan_amendment | Gate 0 | orchestrator | Fetched upstreams; both divergence counts `0 0`; requested local/remote tags absent |  | Stale different-branch premise amended to the user's actual current-branch instruction. |
| DAYOA-001 | DayOA | Validate complete dirty scope | SUCCESS | contract_test | Gate 1 | orchestrator | `pytest -q` -> `858 passed in 38.10s`; `git diff --check` passed |  | Complete six-file dirty set validated. |
| DAYOA-002 | DayOA | Commit/push current branch and annotate/push `11.0.25` | SUCCESS | feature_implementation | Gate 1 | orchestrator | Commit `d0b2aa2fe811accfa84106bd67c9bef1b643fb13`; branch pushed; local annotated tag type `tag`; remote tag pushed |  | Exact clean DayOA release commit published. |
| DYEC-PIN-001 | DYEC | Update all active/payload/test DayOA pins to `11.0.25` and validate full dirty scope | SUCCESS | feature_implementation | Gate 1 | orchestrator | Source/payload catalog byte parity; no active non-ledger `11.0.15`; focused `258 passed`; full `2249 passed, 11 skipped`; `git diff --check` passed |  | Complete pre-existing DYEC dirty set and pin changes are green. |
| DYEC-PIN-002 | DYEC | Commit/push `main` and annotate/push `10.3.29` | IN_PROGRESS | feature_implementation | Gate 1 | orchestrator | Clean commit, branch push, and annotated tag are next |  |  |
| DYEC-SELF-001 | DYEC | Update source/payload/test self-pin to `10.3.30` and validate | OPEN | feature_implementation | Gate 1 | orchestrator | Current self-pin `10.3.28` |  |  |
| DYEC-SELF-002 | DYEC | Commit/push `main` and annotate/push `10.3.30` | OPEN | feature_implementation | Gate 1 | orchestrator |  |  |  |
| FINAL-001 | both | Verify remote branch tips, annotated tag objects and peeled commits, clean worktrees, and exact pins | OPEN | contract_test | Gate 5 | orchestrator |  |  |  |

## Completion contract

Completion requires every row terminal, remote branches at the reported
commits, all three tags present as annotated tag objects, source/payload pin
parity, no stale active pin values, and clean worktrees. The report must state
that no workflow, cluster, scheduler, budget, or AWS mutation occurred.
