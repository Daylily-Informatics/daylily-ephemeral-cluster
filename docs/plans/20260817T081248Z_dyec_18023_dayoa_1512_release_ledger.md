# DYEC 18.0.23 release ledger: DayOA 15.0.12

Created: 2026-08-17T08:12:48Z

## Objective

Cut a DYEC release from the highest released DYEC tag, `18.0.22`, with every
current DayOA command-catalog selector advanced to the published DayOA
`15.0.12` release.

## Gate 0

- Baseline DYEC tag and commit: annotated `18.0.22` at `f9adda5268129242013a44bf6e684836aed84e25`.
- Release branch: `codex/release-18.0.23-dayoa-15.0.12`.
- DayOA `15.0.12` is already an annotated, published LSMC Bio release:
  `https://github.com/lsmc-bio/daylily-omics-analysis/releases/tag/15.0.12`.
- No active controller, Slurm job, headnode session, FSx root, mount, export,
  or cleanup action is in scope for this release.

## Release changes

| Row | Change | Status | Evidence |
| --- | --- | --- | --- |
| REL-01 | Advance both current command-catalog copies from DayOA `15.0.11` to `15.0.12`. | COMPLETE | Each byte-identical copy has 62 `15.0.12` selectors and no `15.0.11` selector. |
| REL-02 | Advance current operator docs and test contracts to the same active pin. | COMPLETE | Historical ledgers and retained receipts remain unchanged. |
| REL-03 | Carry the explicit, dry-run-only pinned-source test override. | COMPLETE | It requires an exact reused local commit, prohibits reset/checkout/export/delete, and preserves before/after source evidence. |
| REL-04 | Verify static release integrity, commit, push branch/tag, and publish a GitHub release. | READY | Static checks are complete; no test suite will run, per user instruction. |

## Version-pin audit

- `pyproject.toml` uses dynamic `setuptools_scm` versioning and contains no
  DayOA version pin.
- `environment.yaml` and the packaged environment YAML contain no DayOA version
  pin.
- The DYEC release version is supplied by the exact annotated git tag
  `18.0.23`; no in-file package version should be added.

## Verification boundary

- No tests are run by explicit instruction.
- Static checks are limited to `git diff --check`, byte identity of the two
  catalog copies, exact active-pin searches, and remote branch/tag/release
  verification.
