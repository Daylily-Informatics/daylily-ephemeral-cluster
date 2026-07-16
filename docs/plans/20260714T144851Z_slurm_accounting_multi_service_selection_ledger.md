# Slurm accounting multi-service selection ledger

- Started: 2026-07-14T14:48:51Z
- Repository: `daylily-ephemeral-cluster-sentieon-single`
- Branch: `sentieon-single`
- Objective: make `dyec create` continue safely when more than one regional DayEC Slurm accounting service is detected.

## Gate 0 baseline

- Existing regional naming is deterministic (`dayec-slurm-accounting-<region>`), but older AZ-suffixed stacks can coexist.
- `ensure_slurm_accounting_db` currently raises `SlurmAccountingError` whenever discovery returns more than one regional stack.
- A Slurm accounting database is compatible only when its stack is healthy, its required CloudFormation outputs are complete, and its `daylily-ec:vpc-id` equals the requested cluster VPC. The private database and client security group are not assumed reachable across unrelated VPCs.
- Ursa's checked-in configuration contract can pass an explicit `slurm_accounting_stack_name` to DYEC. The live `ursa.day.lsmc.bio/clusters` surface requires Cognito and exposes no public accounting identifier.
- A candidate's present-use signal will be the number of unique EC2 instances attached to its `AccountingClientSecurityGroupId`. This is an attached-host count, not an assertion about active MariaDB sessions.

## Selection contract

1. Zero regional services: preserve the existing create-if-missing behavior.
2. One regional service: preserve the existing compatibility checks and select it.
3. More than one regional service:
   - enumerate every detected stack with status, VPC, endpoint when readable, compatibility, and attached-host count;
   - prefer an explicit compatible `slurm_accounting_stack_name`, including the value supplied by Ursa;
   - otherwise select the compatible candidate with the largest attached-host count, with stack name as the deterministic tie-breaker;
   - emit a loud warning explaining the singleton violation, the selected candidate and reason, and wait 90 seconds before continuing so an operator can abort with Ctrl-C;
   - do not fail merely because more than one service exists.
4. No compatible healthy candidate remains a hard error. Automatically selecting an unreachable or malformed private database is outside this change.

## Execution ledger

| ID | Work | State | Evidence |
|---|---|---|---|
| SAMS-001 | Record baseline and selection contract | SUCCESS | This ledger |
| SAMS-002 | Implement candidate inspection and deterministic selection | SUCCESS | `daylily_ec/aws/slurm_accounting.py` inspects every regional stack, filters for healthy same-VPC candidates, counts unique attached EC2 instances by client security group, prefers the explicit Ursa/config stack, and otherwise ranks by attached-host count then name. |
| SAMS-003 | Wire loud warning into create and accounting CLI surfaces | SUCCESS | `daylily_ec/workflow/create_cluster.py` passes `ui.warn`; `daylily_ec/cli.py` passes `output.warning`; the warning lists every candidate and waits 60+20+10 seconds before continuing. |
| SAMS-004 | Add focused unit tests | SUCCESS | `tests/test_slurm_accounting.py` covers regional naming, explicit Ursa preference, attached-host ranking/deduplication, the exact 90-second schedule, incompatible preference fallback, and no-compatible-candidate safety; `tests/test_cli_registry_v2.py` covers CLI warning wiring. |
| SAMS-005 | Run focused validation | SUCCESS | `python -m pytest -q tests/test_slurm_accounting.py tests/test_aws_validation.py tests/test_cli_registry_v2.py tests/test_workflow.py -k 'slurm_accounting'` returned `40 passed, 311 deselected`; focused Ruff and `git diff --check` passed. |

## Safety boundary

- No AWS resources will be created, modified, or deleted while implementing or testing this change.
- The existing dirty worktree is preserved; unrelated files are not modified.

## Completion

- All ledger rows are terminal: yes.
- Objective complete: yes, at the local implementation and automated-test boundary.
- Live duplicate-stack validation was intentionally not performed because the regional duplicate was already removed and this task does not authorize recreating one.
