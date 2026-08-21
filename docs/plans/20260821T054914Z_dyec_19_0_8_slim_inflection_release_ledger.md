# DYEC 19.0.8 slim Inflection catalog release ledger

Created: 2026-08-21T05:49:14Z

## Scope

Release the existing HG002 5x Illumina plus 5x ONT Inflection v0.9
shape-validation catalog clone, its focused assertion, and the approved catalog
live-sweep protocol from annotated DYEC 19.0.7. This release uses numeric
catalog keys only: it adds immutable 19.0.8 and does not restore a `current`
key.

## Gate 0

| Item | Evidence |
| --- | --- |
| Base release | Annotated 19.0.7; tag object `563cbda69a8a3338041ac051fd025341d5dd3cf3`; peeled commit `6d08ebf72f8ad6b5173e3aab31e783325396b573` |
| Release branch | `codex/release-19.0.8-inflection-slim` |
| Source feature | Dirty dclu1904 worktree; only the requested slim command, assertion, and protocol were selected |
| DayOA pin | `16.0.4`, retained from 19.0.7 |
| Catalog model | Exact numeric snapshot key `19.0.8`; no `current` key or implicit selection |

## Release record

| Step | Status | Evidence |
| --- | --- | --- |
| Slim catalog row | complete | Added `inflection-bjuice-product-v0.9-slim-5x5x-validation` to active repository commands and the immutable `19.0.8` snapshot. |
| Assertions | complete | Added focused clone parity assertions. |
| Operator protocol | complete | Added the catalog render/same-root continuation/export-before-cleanup protocol to `AGENTS.md`. |
| Publish | complete | The exact clean release commit is tagged `19.0.8` and branch/tag are pushed to lsmc-bio origin. |

## Verification boundary

By explicit instruction, no pytest invocation, Git test command, or Git diff
check is run. No cluster, workflow, export, cleanup, or DayOA source change is
part of this release.
