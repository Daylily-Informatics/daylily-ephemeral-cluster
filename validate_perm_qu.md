# Add `aws validate` For Daylily AWS Readiness

## Summary
Create branch `codex/aws-validate-command` from refreshed `origin/main`, then add a non-mutating CLI surface:

```bash
daylily-ec aws validate permissions --profile PROFILE --region-az REGION_AZ [--config PATH] [--gap-analysis PATH]
daylily-ec aws validate quotas --profile PROFILE --region-az REGION_AZ [--config PATH] [--gap-analysis PATH]
daylily-ec aws validate all --profile PROFILE --region-az REGION_AZ [--config PATH] [--gap-analysis PATH]
daylily-ec --json aws validate all --profile PROFILE --region-az REGION_AZ --config PATH
```

`--profile` and `--region-az` are mandatory. The command derives `region` from `region_az`, never uses the implicit `default` profile, and does not create, update, delete, start sessions, send commands, or run `pcluster create`.

## Key Changes
- Add `daylily_ec/aws/validation.py` with `AwsValidationOptions`, `AwsValidationReport`, and runners for `permissions`, `quotas`, and `all`; reuse `CheckResult` / `CheckStatus` from `daylily_ec/state/models.py`.
- Register nested commands under `aws/validate` in [daylily_ec/cli.py](/Users/jmajor/.codex/worktrees/f45a/daylily-ephemeral-cluster/daylily_ec/cli.py:1931) with JSON support and `mutates_state=False`.
- Permissions validation:
  - Build one explicit-profile AWS context from `--region-az`.
  - Check STS identity, Daylily global/regional policy attachment, read-only `pcluster-omics-analysis` presence, SSM session document readability/config, and relevant read probes.
  - Use IAM policy simulation for the repo’s required action groups: IAM/pass-role/service-linked roles, CloudFormation, EC2/AutoScaling/ELB, FSx, S3, SSM, Budgets, SNS, Scheduler, Lambda, ImageBuilder, CloudWatch/logs, DynamoDB `parallelcluster-*`, tagging, and ParallelCluster backing services.
  - Treat bootstrap scripts plus `docs/aws_setup.md` as the admin setup source of truth; use `config/aws/daylily-service-cluster-policy.json` as a broad reference, not the sole authority.
- Quota validation:
  - Parse the effective cluster config from `--config` or `config/daylily_ephemeral_cluster_template.yaml`.
  - Render the selected ParallelCluster template in memory with deterministic substitutions for region, max counts, headnode instance type, FSx size, and cluster shape.
  - Check existing quota set plus improved checks for rendered Spot/On-Demand vCPU demand, instance type offering in the selected AZ, EBS gp3 volume/storage needs, FSx Lustre filesystem/storage needs, and network quota needs when the baseline stack is absent.
  - Do not add PCUI-specific checks; current repo only mentions ParallelCluster UI historically and uses the `pcluster` CLI directly.
- `--gap-analysis PATH` writes an AWS-admin Markdown report with context, failed/warned checks, exact missing actions/quota codes, and admin guidance. JSON stdout remains available only through global `--json`.

## Multiagent Work Split
1. Branch and CLI registry: create branch, add command callbacks and policies, update command tree tests.
2. Permissions core: implement non-mutating IAM/policy/simulation checks.
3. Policy source mapper: extract stable action groups and admin remediation text from bootstrap scripts/docs.
4. Quota core: implement in-memory template parsing and quota demand calculations.
5. Gap report writer: implement Markdown gap report and JSON report serialization.
6. Safety guardrails: add tests proving validate never calls mutating boto3 methods, SSM send/start, or `pcluster create/delete`.
7. Docs: update README, `docs/aws_setup.md`, and `docs/cli_reference.md`.
8. Verification: run focused tests, `ruff check .`, `ruff format --check .`, `git diff --check`, then full `pytest -q` if the env is healthy.

## Test Plan
- Unit-test CLI registration, help rendering, mandatory `--profile` / `--region-az`, global `--json`, and mode dispatch.
- Unit-test IAM missing-policy, denied simulation, unreadable SSM document, quota below requirement, unavailable instance type/AZ, and gap-report content.
- Mock boto3 clients to assert no `create_*`, `update_*`, `put_*`, `delete_*`, `send_command`, `start_session`, or `pcluster create/delete` path is invoked.
- Docs verification: command examples use `--region-az`, explicit `--profile`, and explain that PCUI is not part of current validation.

## Assumptions
- The command is readiness validation, not AWS setup automation.
- WARN or FAIL means exit code `1`; all PASS means `0`; AWS context/config construction failure uses existing AWS failure semantics.
- No fallback profile, fallback region, legacy compatibility layer, or implicit region discovery is added.
