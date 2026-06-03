# DYEC 5.1.15 / DayOA 2.0.32 Release Ledger

Created: 2026-05-31T20:45:00Z

Objective: supersede the already-pushed DYEC `5.1.14` release, which carried
the dynamic DRA no-wait behavior but still depended on unavailable DayOA
`2.0.30`, with a new DYEC release pinned to published DayOA `2.0.32`.

## Gate 0: Inventory Freeze

DYEC repo: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster`

DYEC branch: `codex/dyec515-full-catalog-20260531`

Baseline:

```text
HEAD -> bd29cb9e, tag: 5.1.14, origin/codex/dyec515-full-catalog-20260531
```

DayOA release fact:

```text
pip index versions daylily-omics-analysis -> latest 2.0.32
```

Release boundary:

- Do not move `5.1.14`; it is already pushed.
- Cut `5.1.15` as the corrective DYEC release.

## Execution Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DYEC-001 | DayOA package pin | Update the DYEC Python dependency and command catalog from DayOA `2.0.30` to `2.0.32`. | SUCCESS | config_or_startup_contract | Gate 5 | Codex | `pyproject.toml`, `config/daylily_pipeline_command_catalog.yaml`, and the packaged catalog copy point at `2.0.32`. | DayOA `2.0.30` was not available on the package index; `2.0.32` is available. | DYEC now installs against a published DayOA package. |
| DYEC-002 | DYEC self pin | Update release self pins from `5.1.14` to `5.1.15`. | SUCCESS | config_or_startup_contract | Gate 5 | Codex | `config/daylily_cli_global.yaml`, packaged config copy, and workflow checkout tests point at `5.1.15`. | `5.1.14` is already pushed and must not be moved. | Next release tag will be `5.1.15`. |
| DYEC-003 | Validation | Validate package install and focused catalog/version behavior before release. | SUCCESS | contract_test | Gate 5 | Codex | `python -m pip install -e .` installed `daylily-omics-analysis==2.0.32`; focused pytest command covering catalog, registry, packaged defaults, versioning, workflow checkout, no-wait mount paths, and staged sample mounts returned `197 passed in 3.89s`. | DYEC `5.1.14` still pointed at unavailable DayOA `2.0.30`. | Corrective release scope is validated locally before commit/tag. |
| DYEC-004 | Publication | Commit, annotate tag `5.1.15`, push branch, and push tag. | SUCCESS | release | Gate 6 | Codex | Release will be published from the commit containing this ledger with annotated tag `5.1.15`; remote ref verification is reported after push because embedding the post-push ref output in the tagged commit would require changing the tag target. | `5.1.14` is already pushed and cannot be moved. | Cut `5.1.15` as the durable DYEC release for the DayOA `2.0.32` pin. |

## Final Status

All rows terminal for the local release commit. Remote branch/tag verification is reported in the final release handoff after push.
