# DayOA DYEC Release Train Ledger

## Objective

Commit and release the current DayOA dirty state on `jem-dev`, update DYEC DayOA pins to that new DayOA release, commit and release the current DYEC dirty state, then update DYEC self-pins and cut a final DYEC self-pin release.

## Gate 0 Baseline

- Timestamp: `20260616T122118Z`.
- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`.
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`.
- Branches: both repos are on `jem-dev` tracking `origin/jem-dev`.
- DayOA remote: `git@github.com:lsmc-bio/daylily-omics-analysis.git`.
- DYEC remote: `git@github.com:lsmc-bio/daylily-ephemeral-cluster.git`.
- DayOA latest local/remote release tag: `10.0.23`; next planned tag: `10.0.24`.
- DYEC latest local/remote release tag: `10.0.39`; current `jem-dev` head already has one untagged commit `f8c879a5`; next planned DYEC tags are `10.0.40` for the DayOA-pin/max-count release and `10.0.41` for the DYEC self-pin catch-up.
- DayOA dirty baseline: modified workflow/config/test/docs files plus untracked Ultima specialty rule/tests and HG003/ultimarerun plan artifacts.
- DYEC dirty baseline: max node-count repair files plus `docs/plans/20260616T083056Z_dyec_max_count_repair_ledger.md`.
- Release convention: non-`v` semver annotated tags only; do not move existing tags.

## Ledger

| Row | Owner | Requirement | Acceptance | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| G0-001 | Agent 1 | Record release train baseline. | Branches, remotes, latest tags, dirty state, and planned next tags are recorded before staging. | DONE | Gate 0 baseline above. |
| DAYOA-TEST-001 | Agent 2 | Run focused DayOA tests before release. | Relevant tests for Ultima specialty callers, target aliases, mosdepth wrapper, and MultiQC pass. | DONE | Initial run exposed a memory-floor regression where higher Slurm memory values had been lowered; restored `alignstats=250000`, `legacy_cram_compat_bam=64000`, `mosdepth=64000`, `rtg_vcfeval=650000/128000`, and `gatk_contam=80000/64000`. Rerun: `python -m pytest tests/test_sentdug_specialty_callers.py tests/test_multiqc_qc_targets.py tests/test_workflow_target_aliases.py tests/test_mosdepth_contracts.py -q` -> `45 passed in 0.40s`. |
| DAYOA-REL-001 | Agent 3 | Commit DayOA dirty state, push `jem-dev`, tag `10.0.24`, and push the tag. | `origin/jem-dev` contains the release commit and annotated tag `10.0.24` points to that commit. | DONE | DayOA commit `cb6ca4c212896b6d563e0c085922b09158657820` (`Add Ultima expanded caller validation targets`) pushed to `origin/jem-dev`; annotated tag `10.0.24` pushed; `git cat-file -t 10.0.24` -> `tag`; `git describe --tags --exact-match HEAD` -> `10.0.24`. |
| DYEC-PIN-001 | Agent 4 | Update DYEC DayOA pins to `10.0.24` in `pyproject.toml`, `config/**`, packaged `config/**`, and tests. | Pin sweep finds active DayOA pins at `10.0.24`; old active `10.0.23` pins are gone except historical evidence text. | DONE | Updated `pyproject.toml`, `config/daylily_pipeline_command_catalog.yaml`, `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`, `tests/test_repository_catalog.py`, and `tests/test_lsmc_bio_fork_contract.py`. `rg -n "10\\.0\\.23" ...` across those active surfaces returned no matches. |
| DYEC-TEST-001 | Agent 5 | Run focused DYEC tests for max-count repair and pin/catalog contracts. | Relevant tests pass after DayOA pin update. | DONE | `python -m pytest tests/test_triplets.py tests/test_workflow.py tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py -q` -> `146 passed in 1.15s`. |
| DYEC-REL-001 | Agent 6 | Commit DYEC dirty state, push `jem-dev`, tag `10.0.40`, and push the tag. | `origin/jem-dev` contains the release commit and annotated tag `10.0.40` points to that commit. | OPEN | Pending. |
| DYEC-SELF-001 | Agent 7 | Update DYEC self-pins to `10.0.40` in config surfaces and tests. | Self-pin sweep finds active DYEC self-pins at `10.0.40`. | OPEN | Pending. |
| DYEC-SELF-TEST-001 | Agent 8 | Run focused DYEC tests after self-pin update. | Pin/catalog contract tests pass after self-pin update. | OPEN | Pending. |
| DYEC-SELF-REL-001 | Agent 9 | Commit DYEC self-pin update, push `jem-dev`, tag `10.0.41`, and push the tag. | `origin/jem-dev` contains the self-pin commit and annotated tag `10.0.41` points to that commit. | OPEN | Pending. |
| FINAL-001 | Agent 1 | Verify final release state and report. | No rows remain `OPEN`, `IN_PROGRESS`, or `ATTEMPTING_BUGFIX`; final branch/tag/type evidence is recorded. | OPEN | Pending. |

## Notes

- DayOA workflow execution was not part of this release step; no raw Snakemake commands are used.
- Existing tags must not be moved. If a planned tag exists remotely before creation, cut the next patch tag instead and record the amendment.
