# DayOA `12.0.2` To DYEC Release Ledger

Controlling request: update DAY-EC from current DYEC `main` so its source and packaged catalogs pin DayOA `12.0.2`, prove that DayOA release pins the forked Snakemake `7.25.0b113` release, publish the DYEC pin release and its follow-up self-pin release, and update the cross-repository Snakemake release ledger.

Ledger path: `docs/plans/20260718T072200Z_dayoa_12_0_2_dyec_release_ledger.md`

Cross-repository ledger: `/Users/jmajor/projects/lsmc-snakemake-7.25.0b113-20260718/daylily-omics-analysis-7.25.0b113/docs/plans/20260718T063659Z_snakemake_7_25_0b113_release_ledger.md`

## Scope And Release Contract

- Work only in the isolated fork clone `/Users/jmajor/projects/lsmc-snakemake-7.25.0b113-20260718/daylily-ephemeral-cluster-12.0.2`; the original DAY-EC checkout is user-dirty and remains untouched.
- DYEC source and packaged repository catalogs must pin the annotated DayOA `12.0.2` tag.
- The release chain must be proved end to end: DYEC catalog -> DayOA `12.0.2` -> `config/day/day.yaml` -> `Daylily-Informatics/snakemake@7.25.0b113`.
- Source and packaged catalog/config copies must remain byte-identical.
- Follow the established two-release promotion order: first publish DYEC `11.0.3` carrying the DayOA pin, then update both DYEC self-pin copies to `11.0.3` and publish final DYEC `11.0.4`.
- Use normal PR merges to `main`, wait for checks, and create annotated non-`v` tags. Do not move prior tags, force-push, admin-merge, publish PyPI/Docker artifacts, or modify the `Daylily-Informatics` upstream.

## Gate 0 Baseline

- DYEC `origin/main`: `c72302fa5a9a101d3cbde4dbd38125374f088bed`.
- Latest numeric DYEC tag reachable from `main`: annotated `11.0.2`; proposed collision-free next tags are `11.0.3` and `11.0.4`.
- Current source and packaged DayOA default plus active HIOMRS/Inflection pins: `12.0.1`.
- Current source and packaged DYEC bootstrap self-pin: `11.0.1`.
- DayOA tag `12.0.2` is annotated at `46d51469b7962a6bec7b4ff5c3765ddd6303a2fe`; its `config/day/day.yaml` pins `git+https://github.com/Daylily-Informatics/snakemake.git@7.25.0b113`.
- The original `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` checkout has two unrelated untracked ledgers and was behind remote `main`; it is excluded from writes.

## Control Ledger

| ID | Area | Requirement | Status | Category | Gate | Evidence | Terminal Note |
|---|---|---|---|---|---|---|---|
| DYEC-001 | Baseline | Prove current fork `main`, existing pins, available next tags, and the DayOA -> Snakemake lineage. | SUCCESS | inventory | Gate 0 | Exact commits/tags and both pin hops recorded above; remote `11.0.3` and `11.0.4` were absent. | Isolated fork-only branch starts from current `origin/main`. |
| DYEC-002 | Catalog | Update source and packaged DayOA defaults plus active HIOMRS/Inflection command pins to `12.0.2`. | SUCCESS | config_or_startup_contract | Gate 2 | Both catalog copies now use `12.0.2` for the default plus HIOMRS, kitchen-sink, Betelgeuser, and Inflection `git_tag`/`validated_version` fields; `cmp` proves byte identity. | Old active `12.0.1` pins are absent. |
| DYEC-003 | Tests | Update exact pin tests and pass focused plus full DYEC validation. | SUCCESS | contract_test | Gate 5 | Exact pin contracts: `32 passed`; complete DYEC suite in `DAY-EC`: `2264 passed, 11 skipped` in 65.63s; Ruff, YAML parsing, catalog byte identity, and `git diff --check` passed. | Three touched test files are already non-Black on `origin/main`; no unrelated bulk reformat was introduced. |
| DYEC-004 | Release | Commit, push, PR-merge, and annotate the first DYEC pin release as `11.0.3`. | OPEN | feature_implementation | Gate 5 | Pending. |  |
| DYEC-005 | Self-pin | Update both shipped DYEC self-pin copies and their exact test to `11.0.3`. | OPEN | config_or_startup_contract | Gate 4 | Pending publication of `11.0.3`. |  |
| DYEC-006 | Release | Commit, push, PR-merge, and annotate the final self-pinned DYEC release as `11.0.4`. | OPEN | feature_implementation | Gate 5 | Pending. |  |
| DYEC-007 | Ledgers | Close this ledger and append the DYEC promotion receipts to the cross-repository Snakemake release ledger. | OPEN | durable_evidence | Gate 5 | Pending final tags. |  |
| DYEC-008 | Verification | Verify clean/synced fork state, annotated tag objects and peeled commits, exact pin chain, and non-success rows. | OPEN | contract_test | Gate 5 | Pending. |  |

## Final Report

All rows terminal: **no**

Objective complete: **no**

Status counts:

- SUCCESS: 3
- IN_PROGRESS: 0
- OPEN: 5
- BLOCKED: 0
- FAIL: 0
