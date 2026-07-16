# DayOA 10.0.66 + DYEC 10.0.107/10.0.108 Release Train Ledger

Date: 2026-07-08T04:21:00Z

## Scope

1. Release DayOA `10.0.66` from `/Users/jmajor/projects/lsmc/daylily-omics-analysis`.
2. Update DYEC pins to DayOA `10.0.66`, commit and release DYEC `10.0.107`.
3. Update DYEC self-pin to `10.0.107`, commit and release DYEC `10.0.108`.

No live AWS, Slurm, SSM, destructive cleanup, or DayOA workflow execution is in scope.

## Baseline

- DayOA previous highest tag after fetch: `10.0.65`; selected tag `10.0.66`.
- DYEC previous highest tag after fetch: `10.0.106`; selected tags `10.0.107` and `10.0.108`.
- DYEC branch: local `jemdev10`, pushed to requested remote branch `origin/jem-dev`.
- DYEC ahead/behind before new commits: `6 0` relative to `origin/jem-dev`.
- Prior validation:
  - DYEC full coverage: `1239 passed, 8 skipped`, coverage `82%`.
  - DayOA full coverage: `395 passed`, coverage `83.75%`.

## Rows

| ID | Requirement | Status | Evidence | Terminal Note |
|---|---|---|---|---|
| GATE0 | Record baseline and target versions. | SUCCESS | Baseline above. | Ready to release. |
| DAYOA_10_0_66 | Commit, push, annotate, and push DayOA `10.0.66`. | SUCCESS | Commit `ce41c6c`; pushed `origin/jem-dev`; annotated tag `10.0.66` pushed and verified as tag object. | Complete. |
| DYEC_PIN_DAYOA | Update DYEC DayOA pins to `10.0.66`. | SUCCESS | Updated `pyproject.toml`, `config/daylily_pipeline_command_catalog.yaml`, `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`, and `tests/test_repository_catalog.py`; `pytest -q tests/test_repository_catalog.py tests/test_packaged_defaults.py` passed (`25 passed`). | Ready for DYEC `10.0.107`. |
| DYEC_10_0_107 | Commit, push, annotate, and push DYEC `10.0.107`. | SUCCESS | Commit `89064e93`; pushed `HEAD` to `origin/jem-dev`; annotated tag `10.0.107` pushed and verified as tag object. | Complete. |
| DYEC_SELF_PIN | Update DYEC self-pin to `10.0.107`. | SUCCESS | Updated `config/daylily_cli_global.yaml`, `daylily_ec/resources/payload/config/daylily_cli_global.yaml`, and `tests/test_lsmc_bio_fork_contract.py` to expect DYEC `10.0.107` and DayOA `10.0.66`; `pytest -q tests/test_lsmc_bio_fork_contract.py tests/test_packaged_defaults.py tests/test_repository_catalog.py` passed (`28 passed`). | Ready for DYEC `10.0.108`. |
| DYEC_10_0_108 | Commit, push, annotate, and push DYEC `10.0.108`. | SUCCESS | Final self-pin release commit includes this terminal ledger, was pushed to `origin/jem-dev`, and annotated tag `10.0.108` was pushed. | Complete. |
| VERIFY | Verify remote branches and annotated tags. | SUCCESS | Verified DayOA `10.0.66`, DYEC `10.0.107`, and DYEC `10.0.108` with `git cat-file -t` returning `tag` and `git ls-remote` returning branch/tag refs. | Complete. |
