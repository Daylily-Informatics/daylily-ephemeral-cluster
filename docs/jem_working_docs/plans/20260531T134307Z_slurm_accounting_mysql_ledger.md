# Slurm Accounting MySQL For DayEC Ledger

Created: 2026-05-31T13:43:07Z

## Gate 0: Inventory Freeze

Controlling request: implement DayEC-owned, pcluster-external Slurm accounting MySQL/MariaDB service for `sacct`, using self-managed MariaDB on EC2 in the pcluster private subnet.

Repo: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster`

Branch: `codex/dyec515-full-catalog-20260531`

Baseline status:

```text
## codex/dyec515-full-catalog-20260531...origin/codex/dyec515-full-catalog-20260531
 M docs/plans/20260531T125535Z_full_non_bcl_command_catalog_ledger.md
?? docs/plans/20260531T140000Z_dyec515_non_bcl_launches/
```

Pre-existing dirty or untracked files not owned by this work:

- `docs/plans/20260531T125535Z_full_non_bcl_command_catalog_ledger.md`
- `docs/plans/20260531T140000Z_dyec515_non_bcl_launches/`

Inventory commands:

- `rg -n "REGSUB_SLURM_ACCOUNTING|slurm_accounting|SlurmSettings|AdditionalSecurityGroups|Database:" daylily_ec config tests -S`
- `sed -n '1,220p' daylily_ec/render/renderer.py`
- `sed -n '1,190p' daylily_ec/config/models.py`
- `sed -n '940,1760p' daylily_ec/workflow/create_cluster.py`
- `sed -n '520,630p' daylily_ec/cli.py`
- `sed -n '3380,3570p' daylily_ec/cli.py`

Inspection facts:

- Existing ParallelCluster templates have `Scheduling.SlurmSettings` but no `Database` block.
- Existing head node networking has no optional accounting client security group render slot.
- Packaged resource payload mirrors active templates under `daylily_ec/resources/payload/config/day_cluster/`.
- `run_create_workflow` ensures the baseline CFN network before rendering pcluster YAML, which is the correct integration point for accounting DB discovery/creation.
- No existing `slurm_accounting` implementation or render tokens exist.

Live-system limits:

- No live AWS resource creation, deletion, drop, or reset is approved for this implementation pass.
- Live acceptance rows requiring AWS cluster creation remain blocked unless separately approved.

Assumptions:

- The accounting DB is scoped to one DayEC VPC/AZ.
- Discovery must use DayEC stack tags and fail hard on missing, multiple, unhealthy, or incomplete matches.
- pcluster only consumes endpoint/secret/client security group values; it does not own the accounting database stack.

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| SA-001 | CloudFormation | Add standalone private EC2 MariaDB accounting template with retained root volume, termination protection, Secrets Manager password, SG isolation, and required outputs. | SUCCESS | feature_implementation | Gate 1 | Codex | `config/day_cluster/slurm_accounting_mysql_ec2.yml`; `daylily_ec/resources/payload/config/day_cluster/slurm_accounting_mysql_ec2.yml`; `pytest tests/test_packaged_defaults.py -q`. |  | Added retained private Ubuntu/MariaDB EC2 template with no public IP, generated plaintext password secret, isolated client/DB SGs, wait condition readiness, termination protection, and pcluster outputs. |
| SA-002 | Config | Add Slurm accounting config keys and defaults to config model and template payloads. | SUCCESS | feature_implementation | Gate 1 | Codex | `daylily_ec/config/models.py`; `config/daylily_ephemeral_cluster_template.yaml`; `daylily_ec/resources/payload/config/daylily_ephemeral_cluster_template.yaml`; `pytest tests/test_triplets.py -q`. |  | Added required config keys and defaults for enabled/create/stack/database/user/instance type. |
| SA-003 | AWS ensure | Implement DayEC-tag-filtered discovery, exact-one auto-select, create-when-requested, output validation, and no delete/drop/reset operations. | SUCCESS | feature_implementation | Gate 1 | Codex | `daylily_ec/aws/slurm_accounting.py`; `pytest tests/test_slurm_accounting.py -q`. |  | Discovery scans only DayEC-tagged CloudFormation stacks for the selected VPC/AZ, validates health/outputs, creates only when requested, and tests assert no destructive operations. |
| SA-004 | Rendering | Inject optional `HeadNode.Networking.AdditionalSecurityGroups` and `Scheduling.SlurmSettings.Database` blocks only when accounting is enabled. | SUCCESS | feature_implementation | Gate 1 | Codex | `config/day_cluster/*.yaml`; `config/day_cluster/regions/all_clusters.yaml`; payload copies; `pytest tests/test_renderer.py -q`. |  | Disabled render leaves no accounting placeholders or database block; enabled render parses as YAML with headnode client SG and Slurm database block. |
| SA-005 | Create CLI | Add `dyec create --create-slurm-accounting-db` integration after baseline network resolution and before pcluster dry-run. | SUCCESS | feature_implementation | Gate 1 | Codex | `daylily_ec/workflow/create_cluster.py`; `daylily_ec/create.py`; `daylily_ec/cli.py`; `pytest tests/test_workflow.py tests/test_cli_registry_v2.py -q`. |  | Create workflow resolves baseline network first, ensures/selects accounting DB when enabled or requested, injects render substitutions, and persists state/next-run values. |
| SA-006 | Operator CLI | Add `dyec slurm-accounting ensure --profile lsmc --region-az us-west-2b` command that reports endpoint, secret ARN, and client SG. | SUCCESS | feature_implementation | Gate 1 | Codex | `daylily_ec/cli.py`; `pytest tests/test_cli_registry_v2.py -q`. |  | Registered `slurm-accounting ensure` as JSON-capable mutating long-running command and covered output/arguments in CLI tests. |
| SA-007 | Tests | Add unit, renderer, CLI, and AWS mock tests proving success/failure cases and no destructive AWS operations. | SUCCESS | contract_test | Gate 5 | Codex | `pytest tests/test_slurm_accounting.py tests/test_renderer.py tests/test_triplets.py tests/test_cli_registry_v2.py tests/test_packaged_defaults.py tests/test_workflow.py -q` -> 263 passed. Full `pytest -q` -> 970 passed, 7 skipped, 1 unrelated failure in `tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_rejects_dewey_options_without_artifact_registration` due missing local AWS profile `dev`. |  | Focused implementation and workflow suites are green; full suite residual is environment/profile-dependent and outside this change. |
| SA-008 | Live acceptance | Create a real DB and pcluster cluster, verify `sacct`, `sacctmgr`, `sreport`, and retained DB host after cluster deletion. | BLOCKED | contract_test | Gate 5 | Codex | DB setup completed for profile `lsmc`, region/AZ `us-west-2d`: stack `dayec-slurm-accounting-us-west-2d`, instance `i-0fec5d1a28b6d27aa`, URI `10.0.1.39:3306`, client SG `sg-0c8f3047dfc85b1c0`, secret ARN `arn:aws:secretsmanager:us-west-2:108782052779:secret:AccountingPasswordSecret-LIXjs4Jyv7oh-b82PTx`. Verified stack `CREATE_COMPLETE`, stack termination protection `true`, EC2 termination protection `true`, root EBS `DeleteOnTermination=false`, and MySQL ingress restricted to the client SG. | pcluster cluster creation/deletion and Slurm command validation were not requested in this live setup turn. | DB creation is complete; full acceptance still requires a pcluster create/dry-run using the generated DB values, Slurm accounting checks, pcluster deletion, and retained DB verification. |

## Final Status

All local implementation rows are terminal. The accounting DB stack has been created in `us-west-2d`; full pcluster/Slurm live acceptance remains `BLOCKED` pending explicit approval to create or update a pcluster cluster and run accounting checks.
