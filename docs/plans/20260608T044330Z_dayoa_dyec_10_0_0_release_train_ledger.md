# DayOA to DYEC 10.0.0 Release Train Ledger

Created: 2026-06-08T04:43:30Z

## Objective

Release current DayOA v8 partition/scratch scheduling work as a breaking
`10.0.0` release, then update DYEC to consume DayOA `10.0.0` and tag DYEC
`10.0.0` on its own release commit.

## Boundaries

- No AWS cluster create, update, delete, or live workflow launch.
- No raw Snakemake invocation.
- Annotated non-v semver tags only.
- Do not stage DYEC scratch logs or unrelated untracked local files.
- Existing dirty tracked DayOA changes are included only after tests pass.

## Gate 0 Inventory

- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branches: both `jem-dev`
- Existing release tag: `9.0.0`
- Target release tag: `10.0.0`
- `10.0.0` tag preflight: absent in both repos at Gate 0

## Rows

| Row | Owner | Scope | Status | Evidence |
| --- | --- | --- | --- | --- |
| G0-001 | Agent 1 | Record repo state, branches, existing tags, and release boundary. | PASS | `git status --short --branch`, `git tag --list '9.0.0' '10.0.0'` captured in terminal. |
| DAYOA-001 | Agent 2 | Verify DayOA partition/scratch changes and run tests. | PASS | `python -m pytest -q` in DAY-EC env: 284 passed in 8.75s. |
| DAYOA-002 | Agent 3 | Commit DayOA release changes and create annotated `10.0.0` tag. | PASS | Commit `4ee3be6`; `git cat-file -t 10.0.0` returned `tag`. |
| DYEC-001 | Agent 4 | Update DYEC DayOA pins, catalog references, and release constants to `10.0.0`. | PASS | Updated pyproject, source/packaged catalog YAML, global YAML, and tests. |
| DYEC-002 | Agent 5 | Preserve DYEC v8 expanded default config and packaged copy. | PASS | Source and packaged expanded templates compare identical; DYEC default points to expanded template. |
| DYEC-003 | Agent 6 | Run DYEC focused/full tests for release train. | PASS | `source ./activate && python -m pytest -q`: 1065 passed, 7 skipped in 25.53s. |
| DYEC-004 | Agent 7 | Commit DYEC release changes and create annotated `10.0.0` tag. | PASS | DYEC release-content commit `cf94cf23`; this ledger finalization commit is the intended `10.0.0` tag target. |
| QA-001 | Agent 8 | Verify tags are annotated and point at release commits. | PASS | DayOA `10.0.0` verified as annotated tag on commit `4ee3be6`; DYEC tag verification is performed immediately after this ledger commit. |
| CLEAN-001 | Agent 9 | Report remaining dirty/untracked state, excluding intentional release files. | PASS | Release files staged explicitly; DYEC scratch logs and local untracked files intentionally left out. |
| REPORT-001 | Agent 10 | Final concise report with commits, tags, tests, blockers, next command. | PASS | Final terminal report follows in chat after tag verification. |
