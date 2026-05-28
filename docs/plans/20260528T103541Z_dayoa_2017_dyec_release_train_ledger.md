# DayOA 2.0.17 To DYEC Release Train Ledger

## Objective

Publish the DayOA HTD disable fixes as `2.0.17`, update DYEC's pinned DayOA repository catalog version to `2.0.17`, publish a DYEC release, then update DYEC's self pin to that release and publish the follow-up DYEC release.

## Gate 0 Inventory

- DayOA checkout: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
- DayOA branch: `codex/dayoa-local-evidence-dewey-refactor-20260528`
- DayOA release commit: `276bf6e44ae18978efafd93eff0262e772fe3c60`
- DayOA release tag: `2.0.17`
- DYEC checkout: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
- DYEC branch: `codex/dyec-dewey-registration-refactor-20260528`
- Previous DYEC release tag: `5.0.18`
- Planned DYEC DayOA-pin release tag: `5.0.19`
- Planned DYEC self-pin release tag: `5.0.20`

## Ledger

| Row | Step | Status | Evidence |
| --- | --- | --- | --- |
| REL-001 | Publish DayOA `2.0.17` tag. | COMPLETE | `git push origin 2.0.17` created remote tag `2.0.17` from DayOA commit `276bf6e44ae18978efafd93eff0262e772fe3c60`. |
| REL-002 | Build and upload DayOA `2.0.17`. | COMPLETE | `python -m build` produced `daylily_omics_analysis-2.0.17-py3-none-any.whl` and `.tar.gz`; `twup` uploaded to PyPI and a retry probe downloaded `daylily-omics-analysis==2.0.17`. |
| REL-003 | Update DYEC DayOA catalog and tests to `2.0.17`. | COMPLETE | Updated both repository catalog copies plus catalog/CLI tests from `2.0.16` to `2.0.17`; `cmp -s config/daylily_available_repositories.yaml daylily_ec/resources/payload/config/daylily_available_repositories.yaml` passed; `python -m pytest -q tests/test_repository_catalog.py tests/test_cli_registry_v2.py` returned `102 passed`. |
| REL-004 | Commit, push, tag, build, and upload DYEC `5.0.19`. | PENDING |  |
| REL-005 | Update DYEC self pin to `5.0.19`. | PENDING |  |
| REL-006 | Commit, push, tag, build, and upload DYEC `5.0.20`. | PENDING |  |
