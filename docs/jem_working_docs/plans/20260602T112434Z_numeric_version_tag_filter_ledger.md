# Numeric Version Tag Filter Ledger

Date: 2026-06-02T11:24:34Z

## Objective

Apply a packaging/version-resolution fix in both DYEC and DayOA so non-version
marker tags are ignored. Accepted package version tags are numeric-only
`N.N.N` or `N.N.N.N`.

## Gate 0 Inventory

| Item | Evidence |
|---|---|
| Controlling ledger | `docs/plans/20260602T112434Z_numeric_version_tag_filter_ledger.md` |
| DYEC repo | `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster` |
| DYEC branch/status | `codex/dyec515-full-catalog-20260531`; dirty with pre-existing BCL benchmark and script changes |
| DYEC failure signal | plain `git describe --tags --long --always` returned `lsmc-back-fork-cnd2-0-gdf0fe629` |
| DYEC filtered describe baseline | `git describe --dirty --tags --long --match '[0-9]*.[0-9]*.[0-9]*' --match '[0-9]*.[0-9]*.[0-9]*.[0-9]*' --exclude '*[!0-9.]*' --exclude '*.*.*.*.*' --always` returned `5.1.23-0-gdf0fe629-dirty` |
| DayOA repo | `/Users/jmajor/projects/daylily/daylily-omics-analysis` |
| DayOA branch/status | `codex/dayoa-bclconvert-tile-shards-20260601`; clean before this fix |
| DayOA filtered describe baseline | same filtered describe command returned `2.0.36-0-ge700207` |
| Existing DayOA packaging | `pyproject.toml` already had a broad `tag_regex` that allowed suffixes after `N.N.N` |
| Existing DYEC packaging | `pyproject.toml` had no `tag_regex` and no constrained `git_describe_command` |

## Rows

| ID | Repo | Requirement | Status | Category | Gate | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|
| TVF-001 | DYEC | Ignore non-`N.N.N`/`N.N.N.N` tags during SCM version inference | SUCCESS | config_or_startup_contract | Gate 2 | Updated `pyproject.toml` with numeric-only `tag_regex` and numeric-tag-only `git_describe_command` excluding marker tags and 5+ component dotted tags. | Plain `git describe` can choose annotated marker tags before `setuptools_scm` parses a version. | DYEC packaging now filters both tag selection and parsed tag shape. |
| TVF-002 | DayOA | Ignore non-`N.N.N`/`N.N.N.N` tags during SCM version inference | SUCCESS | config_or_startup_contract | Gate 2 | Updated `/Users/jmajor/projects/daylily/daylily-omics-analysis/pyproject.toml` with narrowed numeric-only `tag_regex` and numeric-tag-only `git_describe_command` excluding marker tags and 5+ component dotted tags. | Existing regex did not constrain Git's initial describe selection and permitted suffixes. | DayOA packaging now filters both tag selection and parsed tag shape. |
| TVF-003 | Both | Verify editable metadata/install no longer fails with marker tags present | SUCCESS | contract_test | Gate 5 | DYEC: `source ./activate && python -m pip install --no-deps -e .` built and installed `5.1.24.dev0+gdf0fe629.d20260602`; DayOA: `/Users/jmajor/miniconda3/envs/DAY-EC/bin/python -m pip install --no-deps -e .` built and installed `2.0.37.dev0`; env restored to DayOA `2.0.35`, `pip check` passed. |  | Both editable metadata paths pass; shared local env has no broken requirements after restoring the DYEC-pinned DayOA package. |

## Final State

All rows are terminal. The objective is complete: both repositories now ignore
non-numeric marker tags for SCM version inference.
