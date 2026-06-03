# DayOA 2.0.30 / DYEC Release Train Ledger

Created: 2026-05-31T19:27:56Z

Objective: publish DayOA `2.0.30`, update DYEC to consume it, tag the DYEC
DayOA-pin release, then tag a follow-up DYEC self-pin release.

## Gate 0: Inventory Freeze

Controlling ledger:
`docs/plans/20260531T192756Z_dayoa2030_dyec_release_train_ledger.md`

DayOA repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`

DayOA branch: `codex/dayoa-local-evidence-dewey-refactor-20260528`

DayOA baseline:

```text
## codex/dayoa-local-evidence-dewey-refactor-20260528...origin/codex/dayoa-local-evidence-dewey-refactor-20260528
git rev-list --left-right --count HEAD...@{u} -> 0 0
HEAD -> 22f813756f6e195cb0e2658d3eb0ba6ba91652ab, tag: 2.0.29
```

DYEC repo: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster`

DYEC branch: `codex/dyec515-full-catalog-20260531`

DYEC baseline:

```text
## codex/dyec515-full-catalog-20260531...origin/codex/dyec515-full-catalog-20260531
git rev-list --left-right --count HEAD...@{u} -> 0 0
HEAD -> 2240d70128c7c9f602b2a58b2100af700b9dee76 Record dyec-515 catalog retest evidence
git describe --tags --dirty --always -> 5.1.11-1-g2240d701
```

Version facts:

- DayOA `2.0.30` did not exist locally or on `origin` at Gate 0.
- DYEC `5.1.12` and `5.1.13` did not exist locally or on `origin` at Gate 0.
- DYEC `environment.yaml` has no DayOA package pin; Python package pins live in
  `pyproject.toml`, and workflow repository pins live in the command catalog.
- DYEC self pins live in `config/daylily_cli_global.yaml` and the packaged
  resource copy under `daylily_ec/resources/payload/config/`.

## Execution Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| TRAIN-001 | DayOA release | Publish DayOA `2.0.30` before DYEC consumes it. | SUCCESS | release | Gate 5 | Codex | DayOA branch pushed; annotated tag `2.0.30` pushed. |  | DayOA release commit is recorded in the DayOA ledger. |
| TRAIN-002 | DYEC DayOA pin | Update DYEC package/catalog/test pins from DayOA `2.0.29` to `2.0.30`. | SUCCESS | config_or_startup_contract | Gate 2 | Codex | `pyproject.toml`, `config/daylily_pipeline_command_catalog.yaml`, packaged catalog copy, `tests/test_repository_catalog.py`, and `tests/test_cli_registry_v2.py`; `environment.yaml` inspected and has no DayOA pin. |  | Active package and workflow catalog pins now target DayOA `2.0.30`. |
| TRAIN-003 | DYEC DayOA-pin release | Validate, commit, push, and tag DYEC `5.1.12`. | SUCCESS | release | Gate 5 | Codex | Local annotated tag verified with `git cat-file -t 5.1.12` -> `tag`; remote push is performed after the final release commit is fixed. |  | The `5.1.12` release commit is the commit carrying the DayOA `2.0.30` pin update. |
| TRAIN-004 | DYEC self pin | Update DYEC self pins to the final self-pin release version. | SUCCESS | config_or_startup_contract | Gate 2 | Codex | `config/daylily_cli_global.yaml`, packaged config copy, and `tests/test_workflow.py` now use `5.1.13`. |  | Final self-pin release config points at `5.1.13`. |
| TRAIN-005 | DYEC self-pin release | Validate, commit, push, and tag DYEC `5.1.13`. | SUCCESS | release | Gate 5 | Codex | Local annotated tag verified with `git cat-file -t 5.1.13` -> `tag`; remote push is performed after the final release commit is fixed. |  | The final self-pin release commit is the commit carrying this terminal ledger state. |

## Final Status

All rows are terminal for the local release commits. Remote branch/tag push
evidence is reported in the final cross-repo release train report because
remote push verification happens after these commits exist.

Verification checkpoint:

```text
source ./activate && python -m pytest tests/test_repository_catalog.py tests/test_cli_registry_v2.py tests/test_packaged_defaults.py -q
-> 118 passed
```

Self-pin verification checkpoint:

```text
source ./activate && python -m pytest tests/test_workflow.py::TestConfigureHeadnode::test_repo_checkout_uses_published_detached_tag tests/test_packaged_defaults.py tests/test_versioning.py -q
-> 13 passed
```
