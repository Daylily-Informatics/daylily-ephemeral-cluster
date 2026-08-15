# DYEC 18.0.9 CLI Documentation Ledger

## Control ledger

Controlling request: update `README.md` and the supported Markdown documentation to reflect the shipped DYEC CLI.

Ledger path: `docs/plans/20260815T112127Z_dyec_cli_docs_ledger.md`

### Gate 0 baseline

- Source baseline: annotated DYEC tag `18.0.9`, peeled commit
  `5304927563169a4005005c37aa192d5d95f5b390`.
- Working branch: `codex/dyec-cli-docs-18009`, created from that tag. The tag
  itself is not modified.
- Initial worktree state: no tracked changes; pre-existing untracked
  `TrusSV/` and `tmp/dayoa-ont-headnode-proof/` are excluded from this work.
- Source of truth: `daylily_ec/cli.py`, `daylily_ec/cli_context.py`, the
  source/package command catalogs, and `source ./activate && dyec --help`.
- Sweep: `git ls-files '*.md'` found 573 tracked Markdown files; 43 are
  non-archive/non-plan current-document candidates. The initial set was the
  12 supported operator documents listed in `tests/test_environment_contract.py`.
  DOC-008 adds the two data/export guides that carry direct current CLI
  examples, for 14 checked current-operator documents total. Historical
  reports, archived documentation, plans, and release evidence retain their
  recorded state and are not rewritten as current documentation.
- Live limit: no AWS command, workflow, cluster, or external service action
  is run. CLI help and local tests are the validation evidence.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DOC-001 | baseline | Record branch, source, docs sweep, and excluded dirty state. | SUCCESS | plan_amendment | Gate 0 | codex | Gate 0 above; `dyec --help` captured locally. |  | Inventory frozen before edits. |
| DOC-002 | README | Make the primary README and concise README variant describe the 18.0.9 command surface, context, catalog pin, current input contracts, and current examples. | SUCCESS | historical_docs_only | Gate 1 | codex | `README.md`, `README.md.bland`; local `dyec --help`; local catalog show. |  | Local context, root verbose, catalog/current DayOA target, run-context schema, and export boundary reconciled. |
| DOC-003 | CLI reference | Reconcile `docs/cli_reference.md` with root options, groups, local context, lifecycle, catalog state, and the exact current run-context schema. | SUCCESS | historical_docs_only | Gate 1 | codex | `dyec --help`; nested help; source catalog `run_context.required_columns`. |  | Root command index, context precedence, `validation_pending`, input contracts, and run-context headers reconciled. |
| DOC-004 | operator guides | Reconcile supported setup, start, overview, operations, monitoring, and testing guides with current command shapes and provider-neutral boundaries. | SUCCESS | historical_docs_only | Gate 1 | codex | `tests/test_environment_contract.py`; CLI help; current source. |  | Current 18.0.9/15.0.5 state, platform-resolved user, catalog-first examples, and no-metadata-service export boundary documented. |
| DOC-005 | regression coverage | Add a local documentation contract test covering key 18.0.9 CLI facts, current run-context schema, and retired-current-doc claims. | SUCCESS | contract_test | Gate 1 | codex | `tests/test_cli_docs_contract.py`; focused pytest. |  | Four contract checks pass. |
| DOC-006 | historical records | Preserve historical reports, archived docs, plans, and release evidence rather than relabeling them as current CLI guidance. | SUCCESS | historical_docs_only | Gate 0 | codex | 573 tracked Markdown files; current scope definition above. |  | Excluded intentionally; canonical docs will link to current reference. |
| DOC-007 | validation | Run focused documentation/CLI tests, Markdown stale-state sweeps, source/package catalog identity, and `git diff --check`. | SUCCESS | contract_test | Gate 5 | codex | `292 passed in 65.17s`; source/package `cmp`; stale-term and obsolete run-context sweeps; `git diff --check`. |  | No test, catalog, Markdown sweep, or whitespace failure. |
| DOC-008 | scope amendment | Add direct data/export guides to the current-doc set because they contain active CLI and provider-boundary claims. | SUCCESS | plan_amendment | Gate 1 | codex | `docs/dra_fsx_strategy.md`; `docs/s3_bucket_lifecycle.md`; docs contract test list. |  | Expanded from the initial 12 documents to 14 without rewriting historical records. |

## Final report

All rows terminal: yes

Objective complete: yes

Status counts:

- SUCCESS: 8
- OPEN: 0
- IN_PROGRESS: 0
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0

Validation:

- `source ./activate && python -m pytest tests/test_cli_docs_contract.py tests/test_cli_context.py tests/test_cli_registry_v2.py tests/test_environment_contract.py tests/test_repository_catalog.py tests/test_supported_no_pem_refs.py -q`
  — `292 passed in 65.17s`.
- Source/package catalog identity check, YAML parsing, retired-current-doc and
  obsolete three-column run-context sweeps, and `git diff --check` — passed.
- Local CLI help and `dyec --json catalog show` confirmed DYEC `18.0.9`, DayOA
  target `15.0.5`, `validation_pending`, root context options, and current
  input-contract behavior. No live AWS, workflow, cluster, or external-service
  action ran.

Residual risks: historical documents intentionally retain their original
versions, commands, and evidence. The 14 current operator documents point to
the live CLI reference rather than relabeling those records.
