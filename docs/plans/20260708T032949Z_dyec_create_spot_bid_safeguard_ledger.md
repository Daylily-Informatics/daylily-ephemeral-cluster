# DYEC Create Spot Bid Safeguard + Ursa Warning Log Ledger

Created: 2026-07-08T03:29:49Z
Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
Branch: `jemdev10`

## Objective

Implement guarded DYEC create spot bid pricing for all ParallelCluster templates processed by `dyec create`, add an Ursa-readable high spot price warning log, remove old dollar-bump pricing behavior, update docs, and add regression tests.

## Gate 0 Baseline

| Item | Evidence |
|---|---|
| Controlling request | User-approved 10-agent plan in chat, implementation requested 2026-07-08. |
| Ledger path | `docs/plans/20260708T032949Z_dyec_create_spot_bid_safeguard_ledger.md` |
| Git baseline | `git status --short --branch` showed branch `jemdev10` with existing dirty files including `daylily_ec/cli.py`, cluster templates, docs, and tests before this work. |
| No-DayOA boundary | No changes to `/Users/jmajor/projects/lsmc/daylily-omics-analysis`; scope is DYEC only. |
| No destructive AWS boundary | No live AWS create/delete/teardown actions are part of this implementation. |
| Current old spot path | `daylily_ec/aws/spot_pricing.py` exported `DEFAULT_BUMP_PRICE=4.14`, `FALLBACK_SPOT_PRICE=5.55`, and `bump_price` arguments before implementation. |
| Create path | `daylily_ec/cli.py:create` calls `daylily_ec.workflow.create_cluster.run_create_workflow`, which calls `apply_spot_prices` after rendering the cluster YAML template. |
| Runtime spot logs | `config/day_cluster/post_install_ubuntu_combined.sh` and `config/day_cluster/post_install_rhel8_dragen.sh` write per-host spot logs under `/fsx/scratch` or `/var/log/daylily`. |
| Docs/test targets | `docs/cli_reference.md`, `tests/test_spot_pricing.py`, `tests/test_cli_registry_v2.py`, `tests/test_workflow.py`, `tests/test_state_store.py`, `tests/test_packaged_defaults.py`. |

## Agent Assignments

| Agent | Scope |
|---|---|
| Agent 1 | Orchestrator / ledger |
| Agent 2 | CLI and workflow flags |
| Agent 3 | Spot pricing core |
| Agent 4 | i384 reference mapping |
| Agent 5 | Warning threshold and node logs |
| Agent 6 | Ursa summary and state |
| Agent 7 | Templates and packaged resources |
| Agent 8 | Docs and CLI reference |
| Agent 9 | Regression tests |
| Agent 10 | Verification and final report |

## Ledger Rows

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| GATE0_BASELINE | Ledger | Record baseline, branch, dirty state, target paths, and boundaries. | PASS | plan_amendment | Gate 0 | Agent 1 | This ledger Gate 0 table. |  | Baseline recorded before source edits. |
| CLI_FLAGS | CLI | Add `--global-spot-max-cost`, `--spot-cost-limit-pct`, and `--write-spot-pricing-warn-threshold` to `dyec create`. | PASS | feature_implementation | Gate 1 | Agent 2 | `daylily_ec/cli.py`; `source ./activate && COLUMNS=220 dyec create --help` shows all three flags. |  | CLI exposes the guarded spot-pricing inputs. |
| WORKFLOW_VALIDATION | Workflow | Validate new create args before AWS calls in `run_create_workflow`. | PASS | feature_implementation | Gate 1 | Agent 2 | `daylily_ec/workflow/create_cluster.py`; `tests/test_workflow.py::TestRunCreateWorkflow::test_spot_pricing_validation_failure_before_aws`. |  | Programmatic workflow calls reject invalid pricing values before `AWSContext.build`. |
| LOCAL_ACTIVATE_CURRENT_CHECKOUT | Local env | Make `source ./activate && dyec` use this checkout in existing DAY-EC envs. | PASS | plan_amendment | Gate 1 | Agent 2 | `activate`; `tests/test_activate.py`; `source ./activate && printf "$PYTHONPATH"` prints repo root first. |  | Existing conda envs no longer require a dependency-resolving reinstall for local checkout CLI verification. |
| SPOT_PRICING_CORE | Spot pricing | Replace bump-price behavior with percentage/global cap and structured summaries. | PASS | feature_implementation | Gate 1 | Agent 3 | `daylily_ec/aws/spot_pricing.py`; `tests/test_spot_pricing.py`; summary JSON write test. |  | Final bids use `min(reference_median * pct, global cap)` and return resource/partition summaries. |
| REMOVE_BUMP_PRICE | Spot pricing | Remove `DEFAULT_BUMP_PRICE`, `bump_price`, and legacy `-b/--bump-price`. | PASS | removable_compatibility_debt | Gate 1 | Agent 3 | `rg` found no active `DEFAULT_BUMP_PRICE`, `bump_price`, or `FALLBACK_SPOT_PRICE`; helper help has no `--bump-price`. |  | Old dollar-bump path removed from code, exports, tests, and helper CLI. |
| I384_REFERENCE_MAPPING | Spot pricing | Use i192 reference medians for i384 resources and fail hard if absent. | PASS | feature_implementation | Gate 1 | Agent 4 | `tests/test_spot_pricing.py::TestProcessSlurmQueues::test_i384_uses_i192_reference_median`; missing-reference failure test. |  | i384 resources derive capped bids from matching i192 resources or fail hard. |
| WARN_THRESHOLD_FLAG | Create workflow | Persist warning threshold through rendered templates and summary output. | PASS | feature_implementation | Gate 1 | Agent 5 | `daylily_ec/workflow/create_cluster.py`; `daylily_ec/render/renderer.py`; cluster templates contain `${REGSUB_SPOT_PRICE_WARN_THRESHOLD}`. |  | Threshold flows from CLI/workflow to rendered PCluster templates and summary rows. |
| WARN_LOG_BOOT_SCRIPTS | Boot scripts | Write JSONL warning rows to `spot_price_warn_exception_messages.log` beside per-node spot logs. | PASS | feature_implementation | Gate 1 | Agent 5 | `config/day_cluster/post_install_ubuntu_combined.sh`; `config/day_cluster/post_install_rhel8_dragen.sh`; `bash -n` passed for source and payload scripts. |  | ComputeFleet nodes append schema `dyec.spot_price_warn_exception.v1` rows above the configured threshold. |
| URSA_SUMMARY_STATE | State | Write summary JSON, extend `StateRecord`, and print partition table. | PASS | feature_implementation | Gate 1 | Agent 6 | `daylily_ec/state/models.py`; `daylily_ec/workflow/create_cluster.py`; `tests/test_state_store.py`. |  | Create writes summary JSON and state stores `spot_price_summary_path` plus partition rows. |
| DAYOA_TEMPLATE_COVERAGE | Templates | Apply changes to DayOA cluster templates. | PASS | config_or_startup_contract | Gate 2 | Agent 7 | `config/day_cluster/prod_cluster_nested_spot_mem_scratch_intel_avx512_expanded.yaml`; archive DayOA templates updated. |  | DayOA PCluster templates pass the required warning-threshold arg. |
| DRAGEN_TEMPLATE_COVERAGE | Templates | Apply changes to DRAGEN RHEL8 templates. | PASS | config_or_startup_contract | Gate 2 | Agent 7 | Four active `config/day_cluster/prod_cluster_dragen_*rhel8*.yaml` templates updated. |  | DRAGEN FSx and no-FSx templates pass the required warning-threshold arg. |
| PACKAGED_RESOURCE_SYNC | Payload | Keep packaged resource copies aligned with source templates and scripts. | PASS | contract_test | Gate 1 | Agent 7 | Source/payload boot script equality check; `tests/test_packaged_defaults.py`. |  | Packaged boot scripts and active packaged DayOA template are synchronized. |
| DOCS_CLI_REFERENCE | Docs | Update CLI docs to current signatures and spot pricing flags. | PASS | feature_implementation | Gate 1 | Agent 8 | `docs/cli_reference.md`, `docs/quickest_start.md`, `docs/ultra_rapid_start.md`, `docs/operations.md`. |  | Docs describe the current create flags, formula, cap limits, i384 exception, and removed bump behavior. |
| DOCS_URSA_WARN_LOG | Docs | Document Ursa warning log path and JSONL schema. | PASS | feature_implementation | Gate 1 | Agent 8 | `docs/cli_reference.md`; `docs/operations.md`. |  | Ursa summary JSON, state fields, and warning log paths/schema are documented. |
| REGRESSION_DOUBLE_AUTH | Tests | Add default/limit sentinels for spot-pricing constants and CLI defaults. | PASS | contract_test | Gate 1 | Agent 9 | `tests/test_spot_pricing.py::TestConstants`; `tests/test_cli_registry_v2.py::test_create_command_defaults_region_az_to_us_west_2d`. |  | Defaults `7.50`, `10.00`, `1.2`, `1.0`, `1.4`, and `6.00` are locked in two places. |
| GENERATED_PRICE_TESTS | Tests | Add cap, invalid-value, and i384 missing-reference tests. | PASS | contract_test | Gate 1 | Agent 9 | `tests/test_spot_pricing.py`; `tests/test_cli_registry_v2.py`; `tests/test_workflow.py`. |  | Generated bids cap correctly and invalid values fail before AWS calls. |
| FOCUSED_TESTS | Verification | Run focused pytest and ruff commands from the plan. | PASS | contract_test | Gate 5 | Agent 10 | `source ./activate && pytest -q tests/test_activate.py tests/test_spot_pricing.py tests/test_cli_registry_v2.py tests/test_workflow.py tests/test_state_store.py tests/test_packaged_defaults.py` -> 277 passed; Ruff clean; `git diff --check` clean. |  | Verification passed. |
| FINAL_REPORT | Final | Report terminal row counts, evidence, blockers, and residual risks. | PASS | plan_amendment | Gate 5 | Agent 1 | This ledger terminal report and final chat response. |  | All rows terminal: 20 PASS, 0 FAIL, 0 BLOCKED. |

## Terminal Report

- Terminal counts: 20 `PASS`, 0 `FAIL`, 0 `BLOCKED`, 0 open/running rows.
- Focused tests: `277 passed` for activation, spot pricing, CLI registry, workflow, state store, and packaged defaults.
- Static checks: Ruff clean on touched Python files/tests; Python compile clean; `bash -n` clean for `activate` and source/payload boot scripts; `git diff --check` clean.
- CLI evidence: `source ./activate && COLUMNS=220 dyec create --help` exposes `--global-spot-max-cost`, `--spot-cost-limit-pct`, and `--write-spot-pricing-warn-threshold`; no active bump-price implementation remains.
- Local environment note: a direct editable reinstall was attempted to refresh the existing DAY-EC console script, but the pip dependency clone of pinned DayOA stalled and was interrupted. The implemented `activate` change makes the documented local workflow use this checkout without requiring that reinstall.
