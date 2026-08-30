# DYEC 19.0.49 headnode fresh Conda cache release ledger

## Objective

Repair the public `dyec headnode configure --force` path after the released
DYEC `19.0.48` configure attempt encountered a damaged shared Conda package
cache and produced an incomplete `DAY-EC` environment. Release the correction
immutably, configure `bjuiceval-19024`, and then continue the already-approved
fresh DayOA `16.0.30` HG002 validation through the normal production catalog
contract.

## Boundaries

- Build only from the clean, peeled annotated `19.0.48` commit
  `9dff79685f0869d90fb97ee16fa55a19ced0becb`.
- Do not move `19.0.48`; use the next free annotated numeric patch tag.
- Do not manually delete or repair the headnode's shared Conda cache.
- Do not patch pinned DayOA source, intervene in Slurm, export to S3, send
  Slack messages, or clean FSx results.
- Keep DayOA `16.0.30` and both existing Bjuice catalog command shapes and pins
  unchanged.
- Do not run pytest or git test suites. Use source contracts, compile checks,
  the public CLI, and the real configure/dry/live workflow gates.

## Ledger

| ID | Work | State | Evidence / terminal criterion |
|---|---|---|---|
| BASE-001 | Freeze release and tag state. | SUCCESS | Clean worktree from peeled annotated `19.0.48`; local and remote `19.0.49` absent at `2026-08-30T03:21:20Z`. |
| DIAG-001 | Attribute the failed configure. | SUCCESS | Forced configure first failed on missing `libbrotlidec` package-cache metadata, then a subsequent activation found a newly created `DAY-EC` whose `python -m pip` could not execute. The selected DYEC checkout reached the headnode; the environment install did not. |
| FIX-001 | Isolate package resolution from the damaged shared cache. | SUCCESS | Configure creates a fresh `0700` operation-owned `CONDA_PKGS_DIRS`; cleanup accepts only the resolved `configure.*` child and removes only that temporary cache. The damaged shared cache is neither trusted nor manually deleted. |
| FIX-002 | Validate the new environment before installing DYEC. | SUCCESS | `python -m pip --version` is an explicit fail-closed gate before the editable install; no repair fallback exists. |
| VER-001 | Advance the immutable DYEC build and catalog snapshot. | SUCCESS | `CURRENT_DYEC_BUILD=19.0.49`; source and payload add equal `19.0.49` snapshots identical to `19.0.48`, retaining DayOA `16.0.30` and the unchanged Bjuice command shapes. |
| VAL-001 | Validate source and public CLI contracts without pytest. | SUCCESS | Compileall, YAML semantic checks, source-payload byte identity, generated configure-command ordering and `bash -n`, `git diff --check`, and public catalog resolution succeeded. No pytest or git test suite ran. |
| REL-001 | Publish DYEC `19.0.49`. | IN_PROGRESS | Commit the clean candidate, create and push an annotated non-`v` tag, and verify tag object plus peeled commit. |
| HEAD-001 | Configure `bjuiceval-19024` through released DYEC. | OPEN | Exact saved state file, `--force`, terminal success, installed DYEC `19.0.49`, pinned DayOA `16.0.30`, and clean headnode repository identities. |
| RUN-001 | Fresh released full-genome HG002 dry proof. | OPEN | Normal `inflection-bjuice-product-v0.9` command, exact six-manifest fixture, controller/DayOA/Snakemake `0/0/0`, zero Slurm submissions. |
| RUN-002 | Same-root live continuation and validation. | OPEN | Remove only `-n`; final controller/DayOA/Snakemake `0/0/0`; validate benchmarks, Peddy, Ganon2, VCF statistics, MultiQC, receipts, and both packages. |

The objective is complete only when every row is terminal and `RUN-002` is
`SUCCESS`.
