# FSx Create Selection Contract Ledger

Created: 2026-07-16T00:58:52Z

Controlling request: make DYEC cluster creation explicitly select the per-cluster FSx deployment type, capacity, and throughput instead of silently applying the repository P2 profile.

## Gate 0: Inventory Freeze

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch: `codex/fsx-create-selection-contract` from `main` at `0e400f0ff905f5f69055cb7f0d222520916490cf`.
- Initial worktree: existing untracked reports, ledgers, and cost-utilization assets were present before this work and are not owned by this change.
- Current default config: `fsx_deployment_type=PERSISTENT_2`, `fsx_fs_size=4800`, and `fsx_throughput_mbps_per_tib=250` are all `USESETVALUE` entries.
- Current resolver: deployment type and throughput are read directly from triplet `set_value`; the size prompt is bypassed when `fsx_fs_size` resolves to a configured value.
- Current live boundary: no AWS mutation, cluster change, FSx creation/deletion, DRA mutation, or sweeper-tag change is authorized or included in this implementation.
- Baseline focused checks: `pytest -q tests/test_fsx_persistent2.py tests/test_delete.py` -> `28 passed`; `pytest -q tests/test_export.py` -> collection failure from the existing `daylily_ec.repositories` / `daylily_ec.workflow.export_data` circular import.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| FSX-001 | Interactive create | Prompt for FSx deployment type when the config does not explicitly auto-select it. | SUCCESS | feature_implementation | Gate 2 | orchestrator | `_resolve_fsx_deployment_type`; canonical template uses `PROMPTUSER` |  | Interactive creation presents `SCRATCH_2` and `PERSISTENT_2`. |
| FSX-002 | Interactive create | Prompt for capacity and, for P2, the allowed throughput tier. | SUCCESS | feature_implementation | Gate 2 | orchestrator | `_resolve_fsx_size`; `_resolve_fsx_persistent2_throughput`; focused tests |  | Capacity is always selected; throughput is selected only for P2. |
| FSX-003 | Non-interactive create | Require explicit type, capacity, and applicable throughput; fail hard when missing. | SUCCESS | config_or_startup_contract | Gate 4 | orchestrator | Missing-value tests in `tests/test_workflow.py` |  | Non-interactive defaults are rejected; explicit profile values remain supported. |
| FSX-004 | Operator disclosure | Show the exact dedicated FSx contract before live provisioning and label the provisioning stage as live AWS creation/resume. | SUCCESS | legitimate_safety_handling | Gate 4 | orchestrator | INIT details and `LIVE AWS STORAGE PROVISIONING` phase |  | The command no longer describes live provisioning as a generic ensure step. |
| FSX-005 | Configuration | Remove silent global P2 selection from the canonical source and packaged default templates while preserving explicit profile configs. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Source/package templates match; `auto_delete_fsx` removed from the active default schema |  | Type, size, and speed prompt; retained FSx is not offered as a current mode. |
| FSX-006 | Contracts/tests | Add focused tests for prompts, explicit non-interactive failures, allowed values, and template parity. | SUCCESS | contract_test | Gate 5 | orchestrator | `pytest -q tests/test_workflow.py tests/test_triplets.py tests/test_attach_slurm_accounting.py tests/test_packaged_defaults.py tests/test_fsx_persistent2.py tests/test_delete.py` -> `250 passed` |  | Prompt, explicit-config, P2, deletion-policy, and package contracts pass. |
| FSX-007 | Documentation | Document interactive versus non-interactive selection and the live external-P2 provisioning boundary. | SUCCESS | feature_implementation | Gate 5 | orchestrator | `README.md` per-cluster FSx selection section |  | Documentation states the selection, lifecycle, export, and pre-provision boundary. |
| FSX-008 | Acceptance | Run focused and broader relevant tests; record all residual failures and live-validation limits. | SUCCESS | contract_test | Gate 5 | orchestrator | Focused `ruff check` on every changed Python file -> passed; full `pytest -q` -> `1551 passed, 11 skipped, 1 warning` |  | All owned checks pass; no live AWS creation was performed. Full-tree `ruff check .` still reports 33 pre-existing errors in historical `docs/**` scripts outside this change. |
| FSX-009 | Interactive defaults | Offer P2, 4,800 GiB, and 250 MB/s/TiB as the visible defaults while retaining explicit prompts. | SUCCESS | plan_amendment | Gate 2 | orchestrator | Canonical and packaged templates plus prompt-default assertions in `tests/test_workflow.py` |  | Pressing Enter accepts P2-4800-250; operators can select a different listed contract. |
| UX-010 | Ursa handoff | Prompt for an optional explicit Ursa root URL before AWS work and end a successful create with the canonical cluster-detail URL. | SUCCESS | plan_amendment | Gate 2 | orchestrator | `_resolve_ursa_root_url`, `_build_ursa_cluster_url`; Ursa source route `/clusters/{cluster_name}?region={region}` confirmed in the sibling checkout |  | The service root is explicit and optional; it is never inferred. |
| COST-011 | Idle cost | Resolve current AWS Price List rates before create-side mutations and print the idle headnode, root EBS, FSx, public IPv4, and total hourly estimate at completion. | SUCCESS | plan_amendment | Gate 4 | orchestrator | `daylily_ec/aws/idle_cost.py`; live read-only default P2 lookup: headnode 0.5292 + root EBS 0.0461 + FSx 1.3808 + IPv4 0.0050 = 1.9612 USD/hour |  | Missing or ambiguous AWS Price List products fail before create-side mutations. |
| TEST-012 | Acceptance | Add focused URL, pricing, prompt-order, success-output, source/package parity, and regression coverage, then rerun the full suite. | SUCCESS | contract_test | Gate 5 | orchestrator | Focused `263 passed`; full `pytest -q` -> `1573 passed, 11 skipped, 1 warning`; focused Ruff and `git diff --check` passed |  | No live cluster creation was performed in this implementation pass. |

## Final Report

All rows terminal: yes

Objective complete: yes for source, configuration, documentation, AWS Price List read-only validation, and local tests. No live cluster creation was performed in this implementation pass.

Status counts:

- IN_PROGRESS: 0
- OPEN: 0
- SUCCESS: 12
- FAIL: 0
- BLOCKED: 0
