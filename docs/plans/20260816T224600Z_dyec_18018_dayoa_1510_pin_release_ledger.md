# DYEC 18.0.18 / DayOA 15.0.10 Pin Release Ledger

Created: 2026-08-16T22:46:00Z  
Objective: move every active/current DYEC command-catalog DayOA launch reference to immutable DayOA `15.0.10`, while retaining all existing DayOA `15.0.9` validation evidence unchanged.

## Gate 0: baseline

- DYEC release base: annotated `18.0.17` at `9e517e93e2d85e8c94ef31342b153647a6c89cb3` (`origin/main`).
- DayOA release dependency: annotated `15.0.10` at merge commit `3a501d3f927a9573dc52adb978af31b5b64c85f3`; GitHub release published at `https://github.com/lsmc-bio/daylily-omics-analysis/releases/tag/15.0.10`.
- DayOA `15.0.10` removes only the redundant post-install `node --version` exact-version gate. Its declared `nodejs=22.23.1` Conda constraint and Mermaid CLI/browser/readiness checks remain intact; `tests/test_shell_wrapper_contracts.py` passed `65` tests.
- The source and packaged DYEC catalogs contain current launch fields (`default_ref`, `git_tag`, and `dayoa_git_tags`) and historical evidence fields (`validated_version`, `dayoa_tag`, `dayoa_commit`, S3 prefixes, and notes). Only current launch fields may change.
- Isolated DYEC worktree: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster-18018-dayoa1510` on `codex/dyec-18018-dayoa-1510`; clean before this change.

| ID | Requirement | Status | Category | Gate | Evidence | Terminal note |
|---|---|---|---|---|---|---|
| PIN-001 | Move only active/current catalog launch references to `15.0.10`. | SUCCESS | config_or_startup_contract | Gate 2 | Both catalog copies changed only launch `default_ref`, `git_tag`, and current `dayoa_git_tags` fields; `git diff -U0` finds no changed `validated_version`, `dayoa_tag`, `dayoa_commit`, or S3 evidence field. | Existing `15.0.9` validation evidence remains unchanged. |
| DOC-001 | Advance active operator documentation and release-contract expectations to DYEC `18.0.18` / DayOA `15.0.10`. | SUCCESS | contract_test | Gate 2 | From a fresh detached `18.0.18` checkout, `tests/test_cli_docs_contract.py`, `tests/test_repository_catalog.py`, `tests/test_repository_catalog_aliases.py`, `tests/test_lsmc_bio_fork_contract.py`, and `tests/test_ont_runqc_17_0_28_release.py` collected 45 tests with no failures; source/package catalog comparison and `git diff --check` passed. | Exact tagged release documentation and contract are verified. |
| CAT-001 | Prove source and packaged catalogs remain byte-identical and parse as the current contract. | SUCCESS | contract_test | Gate 2 | `cmp -s` source versus packaged catalog passed; `tests/test_repository_catalog.py` -> `22 passed in 19.55s`. | Catalog identity and parser contract are proven. |
| TEST-002 | Correct current catalog validation-count/version assertions for already-recorded RunQC evidence. | SUCCESS | contract_test | Gate 2 | `tests/test_ont_runqc_17_0_28_release.py`, `tests/test_lsmc_bio_fork_contract.py`, and `tests/test_repository_catalog_aliases.py` passed; the immediate-baseline comparison now uses `18.0.17`. | Prior RunQC evidence is explicit and unchanged. |
| REL-001 | Commit, merge, annotated-tag, and publish GitHub release `18.0.18`. | SUCCESS | feature_implementation | Gate 5 | PR `#121` merged at `7f6f8ea82b2bd6a7fb1efae20870949b29b13887`; annotated `18.0.18` tag points to that merge and is pushed; GitHub Release `DYEC 18.0.18` is published. | Release is immutable and available for headnode configuration. |

## Validation boundary

- This pin release does not invent new validation evidence. Current commands will show `validation_pending: true` until separately rerun against `15.0.10`.
- No workflow, Slurm, S3 export, cleanup, or AWS configuration action is performed by this source release.

## Terminal-state report

- Status counts: `SUCCESS=4`; no working rows remain.
- The release objective is complete. Separate fresh catalog-run proof is still required before changing any historical `validated_version` or S3 validation evidence.
