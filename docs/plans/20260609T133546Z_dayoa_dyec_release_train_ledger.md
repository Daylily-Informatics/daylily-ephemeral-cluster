# DayOA/DYEC Release Train Ledger

Date: 2026-06-09T13:35:46Z

## Gate 0 Baseline

- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`, branch `jem-dev`, clean against `origin/jem-dev`, HEAD `cf2afcb`, describe `10.0.1-9-gcf2afcb`.
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch `jem-dev`, dirty with `AGENTS.md` and pangenome evidence/log artifacts, HEAD `667af537`, describe `10.0.8-5-g667af537-dirty`.
- Live validation runner remains active separately for pangenome catalog rows on cluster `dyecX4`; release work must not manipulate Slurm jobs or services.
- Version policy: non-`v` semver annotated tags, commit first, then tag the exact clean commit, and do not move pushed tags.

## Rows

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | DayOA | Tag clean pushed DayOA `jem-dev` HEAD as next patch release. | SUCCESS | feature_implementation | Gate 5 | orchestrator | `git tag -a 10.0.2 -m "Release 10.0.2"` and `git push origin 10.0.2`; `git cat-file -t 10.0.2` -> `tag`; tag target `cf2afcb`. |  | DayOA `10.0.2` is published as an annotated tag on the clean/pushed `jem-dev` HEAD. |
| REL-002 | DYEC | Pin DYEC to DayOA `10.0.2` in package dependency, command catalog, packaged catalog, and catalog tests. | SUCCESS | config_or_startup_contract | Gate 5 | orchestrator | Updated `pyproject.toml`, both command catalog copies, and catalog/runner/CLI tests; `python -m pytest tests/test_repository_catalog.py tests/test_tests_runner.py tests/test_cli_registry_v2.py -q` -> `138 passed`. |  | DYEC now pins command catalog/default ref and package dependency to current DayOA `10.0.2`. |
| REL-003 | DYEC | Commit and tag first DYEC release carrying the DayOA pin/catalog updates. | IN_PROGRESS | feature_implementation | Gate 5 | orchestrator | Planned next DYEC patch from `10.0.8` to `10.0.9`; focused tests passed before commit. |  |  |
| REL-004 | DYEC | Update DYEC self-reference to first new DYEC tag and tag second DYEC release. | OPEN | feature_implementation | Gate 5 | orchestrator | Planned final DYEC patch after `10.0.9`. |  |  |
| REL-005 | Live pangenome | Continue read-only monitoring of active ILMN/ULTIMA pangenome live sessions. | OPEN | legitimate_safety_handling | Gate 5 | orchestrator | Sessions `ccv_live_illumina_pangenome_snv_20260609T130830Z` and `ccv_live_ultima_pangenome_snv_20260609T130830Z`. |  |  |
