# AWS Permissions, Quotas, And Cost-Control Validation Ledger

Controlling request: expand the DYEC permissions-check CLI for AWS features added since the original April 2026 validator, especially budgets, cost centers, CUR 2.0, and related accounting surfaces; then generate a CLI report that states which permissions and quotas are satisfied.

Ledger path: `docs/plans/20260710T063111Z_aws_permissions_quotas_budget_validation_ledger.md`

## Gate 0: Inventory Freeze

- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch/baseline: `jem-dev` at `0f98622e` (`10.0.141`), tracking `origin/jem-dev`.
- Pre-existing changes outside this work, preserved and not owned here:
  - `config/imagebuilder/almalinux8_public_pcluster316_develop.yaml`
  - `config/imagebuilder/dragen_el8_4_5_4_pcluster315.yaml`
  - `daylily_ec/pcluster/backport.py`
  - `docs/plans/20260710T025221Z_almalinux_pcluster_native_dragen_ledger.md`
  - `tests/test_pcluster_backport.py`
  - untracked `config/iam/`
- Current validator: `daylily_ec/aws/validation.py`; CLI: `dyec aws validate permissions|quotas|all`; Markdown output: `--gap-analysis PATH`.
- Original validator commit: `363bb605` on 2026-04-25. Recent feature inventory includes DRA mounts/exports, Slurm accounting, cluster budget enforcement, cost-center DynamoDB registry and usage snapshots, CUR 2.0 Data Exports, Glue/Athena allocation queries, cluster tags, Spot logging/pricing, and DRAGEN secret access.
- Baseline counts: 17 literal permission-group declarations/generators in `validation.py`; 6 static quota definitions in `quotas.py`; 10 cost-center/Slurm-accounting CLI callbacks.
- Baseline validation: `source ./activate; pytest -q tests/test_aws_validation.py tests/test_quotas.py` -> `60 passed`.
- Live-system boundary: implementation and tests may write only repo artifacts. The final AWS validation run will use read-only identity, IAM simulation, describe/list/get, and Service Quotas calls. It will not create, update, put, delete, send SSM commands, start sessions, launch clusters, or alter budgets/accounting resources.
- Initial report assumption: explicit profile `lsmc`, AZ `us-west-2b`, and the repo default validation config (`config/daylily_ephemeral_cluster_template.yaml`, cluster `majors-cluster`). The local `~/.config/daylily/daylily_ephemeral_cluster.yaml` was not substituted because it describes the older `daylily-demo-cluster` environment. Live identity evidence showed `lsmc` is account root, while the documented working operator profile `daylily-service-lsmc` resolves to `arn:aws:iam::108782052779:user/daylily-service`; both contexts were therefore reported separately, with the non-root operator report authoritative for IAM simulation.
- Concurrent-repo note: during execution, the already-dirty imagebuilder/backport work was committed by its owning workflow as `0d7d3219` and `efb5058f` (`10.0.142`/`10.0.143`). Those commits did not overlap this validator work. The unrelated untracked `config/operational/dragen_pcluster315_almalinux8_20260710.yaml` and `config/daylily_ephemeral_cluster_dragain10_20260710.yaml` also appeared during final verification and were preserved untouched. Final verification ran at `efb5058f`.

## Control Ledger

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| VAL-001 | DYEC | Inventory the April validator, current dirty state, recent AWS feature additions, and baseline tests. | SUCCESS | feature_implementation | Gate 0 | orchestrator | Gate 0 above; git history from `363bb605` through `0f98622e`; focused baseline `60 passed`. |  | Baseline recorded before implementation; unrelated changes are explicitly excluded. |
| VAL-002 | Permissions | Add exact IAM simulation coverage for budget/cost reporting, global cost-center DynamoDB tables, CUR 2.0 Data Exports, Glue/Athena, Slurm accounting, and other current owned AWS calls missing from the April groups. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `daylily_ec/aws/validation.py`; `tests/test_aws_validation_cost_controls.py`; live syntax probe returned 226 evaluations across all 38 groups without an invalid/missing action and proved the configured SNS resource as `daylily-majors-cluster-heartbeat`. | April action catalog predated July cost-control/accounting surfaces and overclaimed root simulation. | Added scoped action/resource groups, selected headnode-policy inspection, conditional-allow protection, per-group failure continuation, configured-topic SNS simulation, open-Spot-request reads, and honest root UNKNOWN boundaries. |
| VAL-003 | Quotas/readiness | Add non-mutating checks for budget headroom, DynamoDB registry table headroom/readiness, CUR 2.0 export headroom, and current cost-control resource availability. | SUCCESS | feature_implementation | Gate 1 | orchestrator | New `budget.readiness`, `cost_centers.registry_readiness`, CUR/Glue/Athena/accounting probes; 26 quota/headroom rows in each report. The root companion proves 24 satisfied and 2 not satisfied. | Existing validator checked legacy quota ceilings but not the recently added resources or full runtime contracts. | Added live spend/limit/filter/notification, cap/freshness, exact CUR/Glue delivery, Athena active usage, current-plus-rendered family-specific EC2 demand including open Spot requests, network demand, gp3 demand, exact Scratch/Persistent/Intelligent-Tiering FSx quota routing, and conditional accounting-resource headroom checks without AWS writes. |
| VAL-004 | CLI report | Make the Markdown report an answer-first satisfied/not-satisfied report while preserving machine-readable JSON and exact check details. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `write_gap_analysis`; report outcome, area summary, complete matrix, exact remediation/details, and AWS datetime/Decimal-safe serialization in both report artifacts. | Gap-only framing did not answer which areas were satisfied. | `--gap-analysis` now writes a complete permissions/readiness/quotas report; JSON behavior remains complete and machine-readable. |
| VAL-005 | Tests/docs | Add focused no-mutation, action coverage, quota, report, and CLI/doc coverage. | SUCCESS | contract_test | Gate 1 | orchestrator | Focused relevant suite: `301 passed`; full suite: `1346 passed, 11 skipped`; Ruff check/format, compileall, and `git diff --check` passed. Updated `docs/aws_setup.md` and `docs/cli_reference.md`. | New read-only and status semantics needed regression coverage. | Added 16 focused cost-control tests plus open-Spot, exact DL-quota, SNS-scope, mixed Persistent_2 FSx-family, orchestration, and report regression coverage; no skipped full-suite test is related to this work. |
| VAL-006 | Live report | Run the expanded CLI read-only against the explicit LSMC context and save the permissions/quota report under `docs/plans/`. | SUCCESS | legitimate_safety_handling | Gate 5 | orchestrator | Operator report `20260710T071053Z_daylily_service_lsmc_us_west_2b_aws_permissions_quotas_report.md`: PASS=50, WARN=5, FAIL=22. Root companion `20260710T065102Z_lsmc_us_west_2b_aws_permissions_quotas_report.md`: PASS=34, WARN=38, FAIL=5. | Operator policies omit recent services; root cannot be used as an IAM simulation source. | Reports were generated by read-only CLI runs. Account readiness is explicitly NOT SATISFIED; no AWS resource was changed. |

## Final Report

All rows terminal: yes

Objective complete: yes. The validator/reporting objective is complete; the reported AWS account/operator gaps remain intentionally unfixed.

Status counts:

- SUCCESS: 6
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
- IN_PROGRESS: 0
- OPEN: 0

Validation: `source ./activate; pytest -q` -> `1346 passed, 11 skipped in 46.91s`; focused AWS/cost-control/CLI suite -> `301 passed`; Ruff check/format, compileall, `git diff --check`, CLI help, 77 valid JSON detail blocks in each live read-only report, and a 38-group/226-evaluation IAM action-syntax simulation probe all passed.

Residual risks: the account-root profile cannot prove operator permissions and is reported as UNKNOWN for all 38 simulation groups. The authoritative non-root operator report remains NOT SATISFIED (50 PASS, 5 UNKNOWN, 22 FAIL); it identifies 15 permission failures, five direct readiness failures, two confirmed quota failures, and five quota checks that cannot be completed until the missing read permissions are granted. The root companion proves 24 of 26 quota/headroom checks and all three CUR/Glue/Athena readiness checks currently pass. Its confirmed failures are the selected runtime policy, configured budgets, cost-center usage state, the rolled-back baseline network stack, and X-family Spot vCPU headroom.
