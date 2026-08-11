# DYEC 16.1.72 catalog result-export ledger

Updated: 2026-08-11T04:59:01Z

## Objective

Publish the scoped ONT RunQC repair and make the DYEC command catalog describe
and enforce the supported result-export sequence, including the required
analysis export visit `--intent`, automatic on-success export, receipt checks,
S3 result verification, and the default no-delete boundary.

## Gate 0 baseline

- DYEC branch: `codex/seqqc-16.1.66-retry`
- Previous DYEC release: `16.1.71`
- Previous ONT catalog pin: DayOA `13.4.21`
- DayOA repair release: annotated tag `13.4.22` at
  `b6c1ff99b3ac7e487bd2a1205f6aaf21fd6fb5ef`
- Existing unrelated workspace changes are excluded from this release commit.
- Full ONT catalog execution remains pre-compute blocked by the existing AWS
  Budget state (`$438.249/$200`); no budget or Slurm state was changed.

## Execution ledger

| ID | State | Evidence |
| --- | --- | --- |
| EXP-001 | SUCCESS | Catalog schema v3 requires a validated `result_export` contract. |
| EXP-002 | SUCCESS | `catalog list`, `show`, and `render` expose the export recipe, including `analysis visit --mode export --intent`. |
| EXP-003 | SUCCESS | Automatic controller export records an export visit and stops if that visit cannot be recorded. |
| EXP-004 | SUCCESS | Recipe uses `--export-trigger on-success`, verifies receipt lifecycle plus expected S3 objects, and omits filesystem deletion. |
| EXP-005 | SUCCESS | Source and packaged catalog/global-config mirrors are byte-identical. |
| EXP-006 | SUCCESS | Focused release suite: 320 tests passed. Python compile and targeted Ruff fatal-error checks passed; `git diff --check` passed. Full suite: 2441 passed, 11 skipped, 45 unrelated failures from existing shared-worktree/environment drift; isolated catalog/provider tests confirm the failures are stale DayOA-pin expectations and a pre-existing provider token, not this result-export change. |
| EXP-007 | PENDING | Commit and push DYEC release changes. |
| EXP-008 | PENDING | Create, push, and verify annotated non-v tag `16.1.72`. |

## Headnode evidence boundary

The DayOA `13.4.22` repair was exercised in the exact pycoQC and ToulligQC
containers on the `prod-cand-260809` headnode, and the absolute-destination FSx
publisher smoke succeeded. The full catalog controller submitted zero Slurm
jobs because the cluster budget guard rejected submission. Therefore this
release has exact-container and FSx publisher evidence, but not a newly
completed full ONT MultiQC plus FSx-to-S3 export under `13.4.22`.
