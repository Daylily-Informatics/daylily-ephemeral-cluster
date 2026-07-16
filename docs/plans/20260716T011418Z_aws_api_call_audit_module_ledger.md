# AWS API Call Audit Module Ledger

Generated: 2026-07-16T01:14:18Z

## Objective

Replace the fixed, one-off Cost Explorer attribution collector with a supported, re-runnable DYEC module and CLI command. Every AWS read must pass through persistent request caching and service-specific throttling, paid Cost Explorer calls must have an explicit per-run budget, and a second identical run must prove that previously returned responses are reused without any live AWS calls.

## Gate 0: Baseline And Safety Boundary

- Owning repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`.
- Baseline branch/commit: `codex/fsx-create-selection-contract` / `0e400f0ff905f5f69055cb7f0d222520916490cf`.
- The worktree already contains unrelated tracked changes in `README.md`, cluster templates, config/workflow modules, and tests. This work must not edit or revert those files unless the new audit command directly requires a narrowly scoped CLI or test registration change.
- Existing July audit evidence is untracked under `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/` and `docs/plans/20260715T234717Z_lsmc_aws_readonly_cost_utilization_*`; preserve it.
- No AWS mutation is authorized. The module is limited to read-only STS, Cost Explorer, CloudTrail LookupEvents, IAM read, and EC2 describe operations.
- Throttling controls request rate, not request count or Cost Explorer charges. Persistent exact-request caching and a paid-call budget are the charge-control mechanisms.
- User cost ceiling: the supported audit may not configure more than 300 paid calls, which is a hard **$3.00** ceiling at the account's observed **$0.01 per Cost Explorer request** rate. The normal audit makes at most one paid Cost Explorer method call, and SDK automatic retries are disabled for this module.
- Deliverable boundary: reusable module, supported CLI, tests, and concise usage documentation only. Do not create another analytical report, dashboard, or rendered artifact.
- Missing, stale, malformed, or mismatched cache entries must be explicit. Corrupt cache data must fail hard rather than silently issue replacement API calls.

## Cache And Throttle Contract

- Cache keys include schema version, AWS profile, explicit expected account id, service, region, operation, and a canonical serialization of the exact request parameters. The cached/live STS identity must match that account before any paid call.
- Each cache entry stores the exact request, raw response, collection timestamp, and content digest; writes are atomic.
- Default cache maximum age is 24 hours and is configurable. `--cache-only` guarantees zero live AWS calls and fails on any missing or stale entry.
- `--refresh` explicitly bypasses valid cache entries but remains subject to the paid-call budget and throttling.
- Cost Explorer calls are marked paid and limited by `--paid-call-budget` before the SDK method is invoked.
- The paid-call budget cannot exceed 300, and Botocore `total_max_attempts` is fixed at one so paid calls are not repeated invisibly by SDK retries.
- Service-specific minimum intervals apply only to live calls: Cost Explorer 1.0 seconds, CloudTrail 0.5 seconds, and other read APIs 0.2 seconds by supported default. All are configurable with non-negative explicit options.
- A run summary must report cache hits/misses, live calls by service/operation, paid live calls, estimated observed-rate Cost Explorer charge, and accumulated throttle sleep.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| API-001 | Module | Implement a reusable `daylily_ec.aws.api_call_audit` module with exact-request persistent caching | SUCCESS | feature_implementation | Local code | orchestrator | `daylily_ec/aws/api_call_audit.py`; exact request/account/profile key, digest validation, atomic writes |  | Reusable package module implemented; fixed-date one-off collector removed. |
| API-002 | Cost control | Enforce paid Cost Explorer call budgets, cache-only mode, and explicit refresh behavior | SUCCESS | active_product_contract | Local code | orchestrator | `test_exact_request_cache_is_reused_by_a_new_reader`, `test_paid_call_budget_is_checked_before_second_live_call`, `test_paid_call_budget_cannot_exceed_three_dollar_ceiling`, `test_cache_only_miss_fails_without_live_call`, `test_corrupt_cache_fails_hard_without_requery` |  | Normal budget is one paid call; 300-call/$3 observed-rate ceiling and no SDK retry are enforced. |
| API-003 | Rate control | Throttle live Cost Explorer, CloudTrail, IAM, STS, and EC2 reads by service | SUCCESS | contract_test | Local code | orchestrator | `test_service_rate_limiter_spaces_live_calls`; default intervals 1.0s/0.5s/0.2s |  | Cached calls do not sleep; live calls are spaced per service. |
| API-004 | Analysis | Reproduce billed-operation, caller/principal, source-IP, user-agent, and EC2 origin summaries | SUCCESS | feature_implementation | Read-only AWS | orchestrator | `test_complete_second_run_uses_only_persistent_cache`; nine JSON/CSV evidence outputs |  | Billed operations, bounded CloudTrail callers, request shapes, IAM keys, and EC2 Elastic IP origins are reproduced. |
| API-005 | CLI | Register `dyec aws audit api-calls` with explicit profile, dates, output, cache, regions, and cost controls | SUCCESS | feature_implementation | Local code | orchestrator | CLI help rendered; registry/callback tests pass | Test patch initially matched a non-unique `--profile lsmc` context | Test argv was narrowed; `aws/audit/api-calls` is read-only, JSON-capable, and long-running in the registry. |
| API-006 | Reuse proof | Run the same audit twice against a fresh cache and prove the second run performs zero live AWS calls | SUCCESS | contract_test | Local test | orchestrator | First synthetic run: 8 live/1 paid; second new reader/session: 8 cache hits, hit ratio 1.0, 0 live, 0 paid; second session fails if any client method is reached |  | Persistent response reuse is directly proven across reader instances. |
| API-007 | Documentation | Document supported rerun, cache-only, refresh, cache expiry, outputs, and charge boundaries | SUCCESS | feature_implementation | Local docs | orchestrator | `docs/aws_api_call_audit.md` |  | Concise usage documentation only; no report/dashboard artifact created. |
| API-008 | Validation | Pass focused tests, CLI help/JSON checks, compile, formatting, and diff checks without disturbing unrelated worktree changes | SUCCESS | contract_test | Gate 5 | orchestrator | 166 focused tests passed; Ruff, py_compile, mypy, CLI help, and `git diff --check` pass | Initial mypy pass found 3 local narrowing errors; full suite has 2 unrelated pre-existing failures in dirty create-workflow output tests | Type narrowing fixed. Full suite: 1,562 passed, 11 skipped, 2 unrelated failures; no scoped audit test failed. |

## Final State

- All rows terminal: yes.
- Objective complete: yes.
- AWS mutations performed: none.
- Live AWS calls performed while building/validating this module: none.
- Actual AWS API cost incurred by this implementation/validation: `$0.00`.
- Focused validation: 166 passed, 0 failed.
- Repository-wide validation: 1,562 passed, 11 skipped, 2 failed in the pre-existing dirty create-workflow SSH-output tests; those files were not changed by this module work.
- Reports or dashboards produced: none.
