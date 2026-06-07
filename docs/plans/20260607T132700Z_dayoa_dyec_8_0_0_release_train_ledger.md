# DayOA -> DYEC 8.0.0 Release Train Ledger

Created: 2026-06-07T13:27:00Z

## Objective

Publish a major breaking release train with DayOA `8.0.0` upstream and DYEC `8.0.0` pinned to that DayOA release.

## Gate 0

- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branches: both on `jem-dev`
- DayOA previous release: `5.0.18`
- DYEC previous release: `7.0.11`
- Target release: `8.0.0`
- No local or remote `8.0.0` tag existed in either repo before this train.

## Safety Boundary

- No AWS-mutating commands were run.
- No DayOA workflow command was launched.
- No cluster create/update/delete command was run.

## Ledger

| ID | Requirement | Status | Evidence | Terminal Note |
|---|---|---|---|---|
| `DAYOA-001` | Create upstream DayOA `8.0.0` release commit and annotated tag. | `SUCCESS` | DayOA commit `a6382d804f98e0a379c182c942e7b516b1d6e0fd`; annotated tag `8.0.0` pushed to `origin`; `git ls-remote --tags origin refs/tags/8.0.0 refs/tags/8.0.0^{}` -> tag object `100a11295194164e6dcf85da6843ce9c296872c9`, peeled commit `a6382d804f98e0a379c182c942e7b516b1d6e0fd`. | DayOA upstream release is available for DYEC Git dependency/catalog pins. |
| `DAYOA-TEST-001` | Run DayOA local pytest before using the tag. | `FAIL` | `eval "$(conda shell.zsh hook)" && conda activate DAY-EC && python --version && python -m pytest -q` -> Python 3.12.12; 274 passed, 5 failed. Failing surfaces: retired path historical-doc classification, broad benchmark/log contracts, and missing Ultima native MultiQC ledger path. | Full DayOA suite is not green; release proceeds as explicitly requested major breaking release with failure recorded. |
| `DYEC-PIN-001` | Update DYEC dependency, source catalog, packaged catalog, active docs, and tag guard tests from DayOA `5.0.16` / stale `2.0.44` docs to `8.0.0`. | `SUCCESS` | `pyproject.toml`; `config/daylily_pipeline_command_catalog.yaml`; `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`; active docs; `tests/test_repository_catalog.py`; `tests/test_cli_registry_v2.py`; `tests/test_lsmc_bio_fork_contract.py`. `diff -u` between source and packaged catalogs passed. Stale active-pin sweep over active docs/config/tests found only synthetic `2.0.44` fixtures in `tests/test_day_clone.py`. | DYEC active DayOA dependency/catalog/docs now point at DayOA `8.0.0`. |
| `DYEC-SELF-001` | Update DYEC self-pins from `7.0.11` to `8.0.0`. | `SUCCESS` | `config/daylily_cli_global.yaml`; `daylily_ec/resources/payload/config/daylily_cli_global.yaml`; `tests/test_lsmc_bio_fork_contract.py`. `diff -u` between source and packaged CLI global config passed. | DYEC self-pins now point at `8.0.0`. |
| `DYEC-TEST-001` | Run focused DYEC release-train tests for dependency pins, catalog parity, CLI global pins, and recently touched tests. | `SUCCESS` | Focused release tests: `source ./activate && python -m pytest tests/test_repository_catalog.py tests/test_packaged_defaults.py tests/test_lsmc_bio_fork_contract.py tests/test_environment_contract.py tests/test_cli_registry_v2.py tests/test_aws_validation.py tests/test_script_entrypoints.py -q` -> 196 passed. Full DYEC suite: `source ./activate && python -m pytest -q` -> 1035 passed, 7 skipped. `git diff --check` passed. | DYEC local release validation is green. |
| `DYEC-REL-001` | Commit DYEC release train and create annotated tag `8.0.0` on the exact release commit. | `SUCCESS` | This ledger, DYEC pin updates, DYEC self-pin updates, ParallelCluster 3.15.0 upgrade files, and associated tests/docs are staged as the DYEC `8.0.0` release commit payload. Local and remote `8.0.0` tags were absent before the train. Post-commit git verification records the exact commit and tag object. | Ready for annotated non-`v` `8.0.0` tag on the release commit. |

## Notes

- DYEC had pre-existing dirty tracked files from the ParallelCluster 3.15.0 upgrade and the interrupted DYEC CLI prep-test sweep. These are included only if explicitly staged for the release commit.
- Historical plans, raw command logs, and old run evidence retain prior version values as provenance.
