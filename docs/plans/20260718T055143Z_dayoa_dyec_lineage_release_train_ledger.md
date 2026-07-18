# DayOA/DYEC Three-Manifest Lineage Release Train Ledger

Created: 2026-07-18T05:51:43Z

## Objective

Publish the already-merged DayOA three-manifest lineage, persisted-EUID, delivery-ID,
and Inflection packaging implementation as a current DayOA patch release. Then update
DYEC's source and packaged DayOA pins, publish the corresponding DYEC release, advance
DYEC's source and packaged self-pins, and publish the follow-up DYEC release.

## Gate 0 Inventory

- DayOA release worktree:
  `/Users/jmajor/projects/lsmc/.codex-worktrees/dayoa-release-d12-20260717`
- DYEC release worktree:
  `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-release-11-20260717`
- Unrelated dirty primary checkouts and the interrupted Set 1 ExpansionHunter repair
  worktree are excluded from this release train.
- The three-manifest/EUID/delivery-ID feature was already committed and merged in
  DayOA `12.0.0` and DYEC `11.0.0`; there was no uncommitted feature source to recover.
- DayOA `main` had untagged Inflection packaging implementation and example commits
  after `12.0.0`; exact release candidate `c82e0cbe3cff81f2125128f3dc4abe30f3fc258a`.
- Existing pushed tags are immutable. New releases use the next patch versions.

## Control Ledger

| ID | Repo | Requirement | Status | Category | Gate | Evidence | Terminal note |
|---|---|---|---|---|---|---|---|
| DAYOA-001 | DayOA | Verify the exact current merged lineage/package candidate | SUCCESS | contract_test | Gate 0 | `PYTHONPATH=. pytest -q` -> `948 passed`; focused Ruff and `git diff --check` clean | Candidate is exact `origin/main` commit `c82e0cb`. |
| DAYOA-002 | DayOA | Publish an annotated patch tag without moving prior tags | SUCCESS | feature_implementation | Gate 1 | Annotated `12.0.1` points to `c82e0cb` and is visible on origin | DayOA release is published. |
| DYEC-001 | DYEC | Pin source and packaged catalogs to DayOA `12.0.1` | SUCCESS | config_or_startup_contract | Gate 2 | Source and packaged catalogs plus fork/catalog/status tests contain `12.0.1`; source/payload files match | Active default and validated HIOMRS/Inflection pins advance together. |
| DYEC-002 | DYEC | Test, commit, push, and publish first DYEC release | SUCCESS | contract_test | Gate 3 | Commit `d026acbe`; PR #30 merged as `bc01aa1f`; annotated `11.0.1` pushed | First DYEC release carries the DayOA pin. |
| DYEC-003 | DYEC | Advance both DYEC self-pin copies to the first DYEC release | SUCCESS | config_or_startup_contract | Gate 4 | Source and packaged global configs plus fork-contract expectation use `11.0.1`; focused gate -> `45 passed` | Both shipped self-pin copies advance together. |
| DYEC-004 | DYEC | Test, commit, push, and publish follow-up DYEC release | SUCCESS | contract_test | Gate 5 | Self-pin commit `bada24e3`; PR #31 merged as `89c056a1`; annotated `11.0.2` pushed. All 99 test files passed in nine isolated batches; 11 tests skipped; Ruff and diff checks clean | Monolithic local pytest was resource-killed at 15% with no failed assertion, so the same inventory was completed in bounded processes; `test_export.py` required the normal import-order anchor used by the monolithic suite. |
| VERIFY-001 | Both | Verify clean trees, annotated local/remote tags, and exact peeled commits | SUCCESS | contract_test | Gate 5 | DayOA `12.0.1` -> `c82e0cb`; DYEC `11.0.1` -> `bc01aa1f`; DYEC `11.0.2` -> `89c056a1`; all local tag objects are annotated and origin exposes matching peeled commits; source/payload configs compare byte-identical | All requested release artifacts are published without moving prior tags. |

## Release Sequence

1. DayOA `12.0.1` — current merged DayOA candidate.
2. DYEC `11.0.1` — DayOA pin advanced to `12.0.1`.
3. DYEC `11.0.2` — DYEC self-pin advanced to `11.0.1`.

Tags are non-`v`, annotated, and never moved.

## Closeout

All control-ledger rows are terminal and successful. DayOA `12.0.1` contains
the already-merged strict `specimens.tsv` / `samples.tsv` / `libraries.tsv`
lineage contract, persisted-EUID and delivery-ID enforcement, and the current
Inflection packaging implementation/example. DYEC `11.0.1` pins DayOA
`12.0.1`; DYEC `11.0.2` is the follow-up release whose source and packaged
self-pins both point to `11.0.1`.
