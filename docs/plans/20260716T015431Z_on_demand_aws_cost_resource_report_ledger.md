# On-Demand AWS Cost And Resource Report Ledger

Generated: 2026-07-16T01:54:31Z

## Objective

Replace the dated, fixed-resource July 2026 audit scripts with a supported DYEC module and CLI command that can be run on demand. Cost classes and resource types must be discovered from current AWS responses, newly appearing types must be preserved without code changes, previously observed types that disappear must remain explicit, and missing optional lifecycle/utilization enrichers must not make the report fail. All calls remain read-only, exact-request cached, throttled, and protected by a hard Cost Explorer paid-call ceiling of $3.00 at the account's observed $0.01/request rate.

## Gate 0: Inventory Freeze

- Controlling ledger: `docs/plans/20260716T015431Z_on_demand_aws_cost_resource_report_ledger.md`.
- Owning repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`.
- Implementation worktree baseline: `codex/dyec-self-pin-10317` / `d1e2ee405cc3b2d7121ce3c14eaaf913a31b37a6`.
- Integration target: local `main`, which was independently verified at the same baseline commit before integration. Only the cost module, CLI registration, focused tests, documentation, and this ledger are in integration scope.
- Pre-existing unrelated tracked changes: `config/daylily_cli_global.yaml`, `daylily_ec/resources/payload/config/daylily_cli_global.yaml`, `docs/plans/20260716T013305Z_dyec_dirty_double_release_ledger.md`, and `tests/test_lsmc_bio_fork_contract.py`. They are not owned by this work and must not be modified or reverted.
- Existing reusable charge-control substrate: `daylily_ec/aws/api_call_audit.py` provides exact-request cache validation, atomic cache writes, service throttling, disabled SDK retries, cache-only/refresh modes, and a 300-paid-call hard ceiling.
- Existing dated report source: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/scripts/`; it hard-codes profile/account/dates and a fixed set of EC2, EBS, EIP, NAT, FSx, RDS, ELB, S3, and Resource Explorer service classes.
- Existing output contract: cost by service/usage/resource, current and untagged inventory, lifecycle state, utilization evidence, cluster state, raw/cache provenance, and machine-readable summaries.
- Safety boundary: local implementation and mocked/cache-only validation only in this workstream. No live AWS call, AWS mutation, report refresh, cluster operation, or budget change is authorized or needed.
- Cost boundary: every live Cost Explorer SDK request, including pagination, must debit the paid-call budget before invocation. The configurable budget may not exceed 300 calls / $3.00 at the observed rate. Cache hits cost zero and do not sleep.
- Discovery boundary: Resource Explorer and CloudFormation provide dynamic type discovery. Resource Explorer coverage is limited to configured indexes; absence from an index alone must never be labeled deleted. Optional enrichers can strengthen lifecycle/utilization evidence for supported types but unknown types remain first-class output rows.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| RPT-001 | Core module | Add parameterized on-demand report orchestration using the shared cached/throttled AWS reader | SUCCESS | feature_implementation | Local code | orchestrator | `daylily_ec/aws/on_demand_cost_report.py`; `run_on_demand_cost_report` |  | One-shot report module implemented; no scheduler, monitor, watcher, daemon, or background process. |
| RPT-002 | Dynamic cost classes | Derive service/resource classes from paginated Cost Explorer responses rather than a fixed service list | SUCCESS | feature_implementation | Local code | orchestrator | Mocked paginated service response introduced `Quantum Compute`; resource filter asserted returned service set |  | Cost services and billing type classes are response-derived. |
| RPT-003 | Dynamic inventory | Union Resource Explorer and CloudFormation discovery into a stable generic resource schema | SUCCESS | feature_implementation | Local code | orchestrator | `AWS::Quantum::Widget` fixture passed without an adapter; provider/tagging supplements merge into `ResourceSet` |  | Unknown/new types remain first-class output. |
| RPT-004 | Type history | Compare with an explicit prior snapshot so appeared, persisting, and disappeared types are retained without inferring deletion | SUCCESS | legitimate_safety_handling | Gate 4 | orchestrator | `test_type_history_retains_disappeared_class_without_claiming_deletion` |  | Explicit history contract distinguishes disappearance from proven deletion. |
| RPT-005 | Lifecycle/utilization | Preserve generic lifecycle/utilization status for unknown types and apply optional enrichers only where supported | SUCCESS | feature_implementation | Local code | orchestrator | Unknown widget reports `not_supported`; CloudWatch adapter and stopped ParallelCluster tests pass |  | Unsupported telemetry is explicit and non-fatal. |
| RPT-006 | Cost control | Enforce cache reuse, cache-only mode, pagination-aware paid budget, throttling, no SDK retries, and hard $3 ceiling | SUCCESS | active_product_contract | Local code | orchestrator | Synthetic first run 7 paid pages / $0.07; identical second run 0 live, 0 paid, hit ratio 1.0; 301-call config rejected |  | Every Cost Explorer page debits the budget before invocation; 300-call maximum retained. |
| RPT-007 | CLI and docs | Register a supported one-command DYEC rerun and document output/cost/coverage contracts | SUCCESS | feature_implementation | Local code | orchestrator | `dyec aws audit cost-resources --help`; `docs/aws_on_demand_cost_resource_report.md` |  | First-run, later-run, and cache-only commands documented. |
| RPT-008 | Validation | Pass focused tests, static checks, compile, CLI help, and diff checks without live AWS calls | SUCCESS | contract_test | Gate 5 | orchestrator | 172 focused tests passed; Ruff passed; local mypy passed; py_compile, CLI help, and `git diff --check` passed |  | No live AWS or pcluster calls were made during implementation/validation. |
| RPT-009 | Tags/budgets | Catalog resource tags, cost-allocation tag keys and values, and read-only budget associations/alerts/actions | SUCCESS | feature_implementation | Local code | orchestrator | `resource_tags.csv`, `service_tag_summary.csv`, `cost_by_tag_value.csv`, `budgets.csv`, and budget association/notification/subscriber/action/tag outputs; budget-derived tag test |  | Budget filter tag keys automatically join explicit tag-value cost analysis; Budget API reads do not consume the Cost Explorer paid-call counter. |
| RPT-010 | Main integration | Add the tested cost module and `dyec aws audit cost-resources` command to local `main` without including unrelated working-tree changes | SUCCESS | release_integration | Local main fast-forward | orchestrator | 172 focused tests passed; scoped path inventory; local `main` ancestry and commit-tree verification |  | Cost module, CLI registration, tests, docs, and ledger integrated; unrelated working-tree changes excluded. |

## Final Report

All rows terminal: yes

Objective complete: yes

Live AWS calls performed by this implementation work: none.

Status counts:

- SUCCESS: 10
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0

Validation:

- `pytest -q tests/test_on_demand_cost_report.py tests/test_api_call_audit.py tests/test_cli_registry_v2.py` -> 172 passed.
- `ruff check` on changed Python/test files -> passed.
- `mypy --follow-imports=skip daylily_ec/aws/on_demand_cost_report.py` -> no local issues; the repository configuration still warns that its declared Python 3.9 target is unsupported by the installed mypy.
- Python compile, CLI help, and `git diff --check` -> passed.
- Local `main` was advanced from the independently verified `d1e2ee405cc3b2d7121ce3c14eaaf913a31b37a6` baseline to the scoped cost-module commit; unrelated working-tree changes remain outside that commit.
