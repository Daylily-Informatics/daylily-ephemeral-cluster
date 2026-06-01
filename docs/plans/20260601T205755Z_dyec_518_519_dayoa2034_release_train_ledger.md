# DYEC 5.1.18 / 5.1.19 DayOA 2.0.34 Release Train Ledger

Created: 2026-06-01T20:57:55Z

## Objective

Publish a DYEC double release train after DayOA `2.0.34`: first release
`5.1.18` carries the DayOA `2.0.34` dependency/catalog pin; second release
`5.1.19` updates DYEC internal self-pins to the final tag and is the package
train endpoint.

## Gate 0 Inventory

| Item | Evidence |
|---|---|
| Repo | `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster` |
| Branch | `codex/dyec515-full-catalog-20260531` tracking `origin/codex/dyec515-full-catalog-20260531` |
| Baseline HEAD | `f8196b0dea16d0f00d45e47287fd477e6fcfaa4f`, annotated tag `5.1.17` |
| DayOA release input | `2.0.34` tagged on commit `317c1ee567b9ed80592455e955d2b06aba63c25e`; package index reports latest `2.0.34` |
| Package index before release | `python -m pip index versions --no-cache-dir daylily-ephemeral-cluster` reported latest `5.1.17` |
| Next releases | `5.1.18` then `5.1.19`; no local or remote tags existed at Gate 0 |
| Pre-existing dirty files not owned by this release | `AGENTS.md`, `docs/plans/20260601T144201Z_dyec_516_517_release_train_ledger.md`, and untracked HG003 catalog / dyec5117 mount ledger artifacts were present before this release train and will not be staged unless explicitly part of this release. |

## Execution Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DYEC518-001 | DayOA pin | Pin DYEC dependency, command catalog, packaged catalog, and tests to DayOA `2.0.34`. | SUCCESS | config_or_startup_contract | Gate 1 | Codex | `rg -n "2\.0\.33|5\.1\.17" pyproject.toml config/daylily_cli_global.yaml daylily_ec/resources/payload/config/daylily_cli_global.yaml config/daylily_pipeline_command_catalog.yaml daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml tests -S` returned no matches after the pin update. |  | DayOA dependency/catalog/test pins now reference `2.0.34`; DYEC self-pin files now stage `5.1.18`. |
| DYEC518-002 | First validation | Install against DayOA `2.0.34` and run focused DYEC validation before `5.1.18`. | SUCCESS | contract_test | Gate 5 | Codex | Initial focused validation installed `daylily-omics-analysis` `2.0.34`, then failed `tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_rejects_dewey_options_without_artifact_registration` before reaching the intended validation. Bugfixes: added explicit `--region us-west-2`, moved Dewey/export option validation before external AWS/ParallelCluster discovery, and removed invalid `--output json` from `pcluster list-clusters`. Final rerun: `python -m pip show daylily-omics-analysis` reported `Version: 2.0.34`; `python -m pytest -q tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_rejects_dewey_options_without_artifact_registration tests/test_repository_catalog.py tests/test_cli_registry_v2.py tests/test_workflow.py tests/test_day_clone.py tests/test_script_entrypoints.py` passed `231 passed in 3.56s`. | Validation order reached external discovery before local Dewey option checks; shared `resolve_cluster()` also passed an AWS CLI-only output flag to `pcluster`. | Release gate is green for `5.1.18`. |
| DYEC518-003 | First DYEC release | Commit, push branch, create annotated tag `5.1.18`, verify tag type and target, and push tag. | OPEN | release | Gate 6 | Codex |  |  |  |
| DYEC519-001 | Final self-pin | After `5.1.18`, update DYEC internal self-pins from `5.1.18` to `5.1.19`. | OPEN | config_or_startup_contract | Gate 6 | Codex |  |  |  |
| DYEC519-002 | Final validation | Re-run focused validation for final self-pin and package metadata. | OPEN | contract_test | Gate 6 | Codex |  |  |  |
| DYEC519-003 | Final DYEC release | Commit, push branch, create annotated tag `5.1.19`, verify tag type, push tag, build in `TWINE`, upload with `twup`, and verify package-index visibility. | OPEN | release | Gate 6 | Codex |  |  |  |

## Final Status

Working ledger. Terminal status will be recorded after the double release train.
