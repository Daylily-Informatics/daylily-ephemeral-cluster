# DYEC Local Context and DayOA 15.0.3 Control Ledger

Controlling request: DYEC local context from DYEC `18.0.8` with active DayOA targets at `15.0.3`.

## Gate 0: Inventory Freeze

- DYEC worktree: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster-dyec-context-18008`
- Branch: `codex/dyec-context-dayoa-1503-18008`
- Baseline: annotated DYEC tag `18.0.8` at `67717bbaf4f994d3ce39bf4369af568ca12a645b`.
- DayOA input: annotated tag `15.0.3` at `78f41e6265dd2a8eb795cabdab7b65dfa6c66653`; its existing checkout is dirty and is out of scope.
- Original detached DYEC `18.0.6` checkout and its untracked `TrusSV/` and `tmp/dayoa-ont-headnode-proof/` directories are out of scope and untouched.
- Initial target-worktree status: clean on `codex/dyec-context-dayoa-1503-18008`.
- Catalog sweep: `rg -n 'default_ref: "15\\.0\\.1"|dayoa_git_tags:|git_tag: 15\\.0\\.1|git_tag: "15\\.0\\.1"' config/daylily_pipeline_command_catalog.yaml | wc -l` returned `88` candidate lines.
- No DayOA workflow, AWS, cluster, Slurm, or live validation action is authorized or planned for this implementation.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Baseline | Record tags, worktree state, catalog sweep, and live-system boundary. | SUCCESS | plan_amendment | Gate 0 | codex | Gate 0 section above. |  | Baseline frozen before source changes. |
| CTX-001 | Local context | Add strict `$PWD/.dyec.config.yaml` loader, writer, and validation contract. | SUCCESS | feature_implementation | Gate 2 | codex | `daylily_ec/cli_context.py`; `tests/test_cli_context.py`; malformed YAML, unknown keys, non-string/null values, blank clearing, atomic lifecycle, and ignored `DYEC_*` coverage. |  | CWD-only config accepts only the four string keys and deletes the file only when empty. |
| CTX-002 | CLI surface | Add `set-vars`, `unset-vars`, root `--verbose`/`-v`, and create `--admin-email`. | SUCCESS | feature_implementation | Gate 2 | codex | `daylily_ec/cli.py`, CLI-context tests, and final full suite. |  | `--admin-email` applies only to AWS Budget email precedence; heartbeat email fallback remains unchanged. |
| CTX-003 | Resolution | Apply explicit flag, local context, then existing behavior to all relevant CLI options; defer required checks. | SUCCESS | feature_implementation | Gate 2 | codex | All registered target options are wrapped; explicit/local/no-context, repeatable-region, required-missing, AWS fallback, and JSON-safe verbose tests pass. |  | Required checks occur after local resolution; no region/AZ inference or `DYEC_*` environment shim exists. |
| CAT-001 | Catalog | Promote source and packaged active DayOA target pins to `15.0.3`, preserving historical blocks. | SUCCESS | config_or_startup_contract | Gate 2 | codex | Source/package byte parity; 30 active and 29 current-direct commands all resolve to `15.0.3`; historical build blocks compare unchanged to tag `18.0.8`. |  | `dyec_builds.current.dayoa_git_tags` is only `15.0.3`; numeric releases remain immutable. |
| CAT-002 | Catalog API | Surface target validation pending state without relabeling validation provenance. | SUCCESS | feature_implementation | Gate 2 | codex | `AnalysisCommand.to_public_payload`, `catalog list/show/render`, and repository-catalog tests. |  | Derived `validation_pending` is true only when launch tag differs from retained `validated_version`; launches remain non-blocking. |
| DOC-001 | Operator docs | Document local context, precedence, diagnostics, DayOA pinning, and validation-pending meaning. | SUCCESS | feature_implementation | Gate 2 | codex | `README.md`, `docs/cli_reference.md`, `docs/quickest_start.md`, and `docs/pip_install.md`. |  | Documents CWD-only context, explicit override examples, stderr verbose behavior, DayOA `15.0.3`, and retained validation provenance. |
| TEST-001 | Tests | Add focused regression coverage and run source, catalog, lint, YAML, and diff checks. | SUCCESS_WITH_BASELINE_FAILURES | contract_test | Gate 5 | codex | Focused suite: `448 passed`. Final default suite: `2,585 passed, 11 skipped, 2 failed`; final suite excluding the two tag-proven baseline nodes: `2,585 passed, 11 skipped, 2 deselected`. Scoped Ruff E9/F, new-file Ruff/format, YAML parsing/yamllint, source/package parity, and `git diff --check` pass. | Two unchanged `18.0.8` test/data inconsistencies: an absent `exclusive=""` script literal and a tracked staging example omitted from an expected list. | No live AWS, cluster, Slurm, or DayOA workflow action ran. |

## Baseline Failure Proof

- `git show 18.0.8:tests/test_packaged_defaults.py` contains the stale
  `exclusive=""` expectation, while `git grep -n exclusive 18.0.8 --
  daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` returns no match.
- `git show 18.0.8:tests/test_staging_examples.py` omits
  `complete_genomics_solo_slim_mounted_reference_v1` from its expected listing,
  while `git ls-tree -r --name-only 18.0.8 --
  examples/staging/complete_genomics_solo_slim_mounted_reference_v1` proves
  that the file was already tracked at the baseline tag.

These failures are not in the changed surfaces and were left unmodified.

## Final Report

All rows terminal: yes

Objective complete: yes
