# DYEC 5.1.16 / 5.1.17 Release Train Ledger

Created: 2026-06-01T14:42:01Z

## Objective

Publish a DYEC double release train after DayOA `2.0.33`: first release
`5.1.16` carries the DayOA `2.0.33` pin and the `day-clone --executing-entity`
bootstrap fix; second release `5.1.17` updates DYEC internal self-pins to the
final tag and is the package train endpoint.

## Gate 0 Inventory

| Item | Evidence |
|---|---|
| Repo | `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster` |
| Branch | `codex/dyec515-full-catalog-20260531` |
| Baseline HEAD | `3b6cc5cc2f01862158138214296737d385f89a94`, annotated tag `5.1.15`, `origin/codex/dyec515-full-catalog-20260531` |
| Package index before release | `python -m pip index versions daylily-ephemeral-cluster` reported latest `5.1.15`; DayOA index reported latest `2.0.33` after the DayOA release train |
| Next releases | `5.1.16` then `5.1.17`; neither tag existed locally or on `origin` at Gate 0 |
| Included local fix | `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` generates `day-clone --executing-entity "$EXECUTING_ENTITY"`; helper copies no longer expose the `-u` alias |
| Pre-existing dirty file | `AGENTS.md` has Slurm service-boundary instruction edits and is intentionally not part of this release train |

## Execution Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DYEC516-001 | DayOA pin | Pin DYEC dependency, command catalog, packaged catalog, and tests to DayOA `2.0.33`. | SUCCESS | config_or_startup_contract | Gate 1 | Codex | `pyproject.toml`, `config/daylily_pipeline_command_catalog.yaml`, payload catalog, and catalog tests edited from `2.0.32` to `2.0.33`; `rg "2.0.32" pyproject.toml config daylily_ec/resources tests` returned no matches. | DayOA `2.0.33` is the newly published package release. | Ready for `5.1.16`. |
| DYEC516-002 | Bootstrap fix | Include the stable long-form `day-clone --executing-entity` workflow bootstrap fix. | SUCCESS | feature_implementation | Gate 1 | Codex | `docs/plans/20260601T130854Z_day_clone_executing_entity_flag_ledger.md` records the local fix and focused validation. | Generated workflow script had used `-u`, which is not accepted by older observed `day-clone` contracts. | Included in first DYEC release commit. |
| DYEC516-003 | Validation | Install against DayOA `2.0.33` and run focused DYEC validation before `5.1.16`. | SUCCESS | contract_test | Gate 5 | Codex | `source ./activate && python -m pip install -e .` installed local DYEC metadata with `daylily-omics-analysis 2.0.33`; focused pytest command passed `39 passed in 0.75s`. | Release must prove the dependency pin is installable before tagging. | Ready for `5.1.16`. |
| DYEC516-004 | First DYEC release | Commit, push branch, create annotated tag `5.1.16`, verify tag type, and push tag. | SUCCESS | release | Gate 6 | Codex | Commit `329dea63e266e719b5e8e0c37ad877468a436b7a`; `git cat-file -t 5.1.16` returned `tag`; `git rev-list -n 1 5.1.16` matched the release commit; `git push origin 5.1.16` succeeded. | First release boundary must exist before final self-pin points at the next tag. | `5.1.16` tag is on `origin`. |
| DYEC517-001 | Final self-pin | After `5.1.16`, update DYEC internal self-pins from `5.1.16` to `5.1.17`. | SUCCESS | config_or_startup_contract | Gate 6 | Codex | `config/daylily_cli_global.yaml`, packaged payload config, and workflow tag-detach test now reference `5.1.17`. | Final package should bootstrap to the final DYEC tag, not the intermediate tag. | Ready for final validation. |
| DYEC517-002 | Final validation | Re-run focused validation for final self-pin and package metadata. | SUCCESS | contract_test | Gate 6 | Codex | Focused pytest command passed `39 passed in 0.63s` after the `5.1.17` self-pin update. | Final tag should only be cut after the bootstrap tag contract is revalidated. | Ready for `5.1.17` release. |
| DYEC517-003 | Final DYEC release | Commit, push branch, create annotated tag `5.1.17`, verify tag type, push tag, build in `TWINE`, upload with `twup`, and verify package-index visibility. | OPEN | release | Gate 6 | Codex |  |  |  |

## Final Status

Working ledger. Terminal status will be recorded after the double release train.
