# LSMC AWS Read-Only Cost, Tag, And Utilization Audit Ledger

Generated: 2026-07-15T23:47:17Z

## Scope And Safety Boundary

- AWS account/profile: `108782052779` / `lsmc`.
- Requested action: read-only inventory, untagged-resource scan, high-cost-resource identification, and utilization reporting.
- No AWS mutations are authorized or performed. The collector is limited to `sts`, `ec2 describe`, `resource-explorer-2 list/search`, `configservice describe`, `ce get`, `cloudtrail lookup`, `cloudwatch get/list`, `fsx describe`, `rds describe/list-tags`, `elbv2 describe`, and `s3api list/get` calls.
- Billing windows: June 1-30, 2026 (last complete month) and July 1-14, 2026 (month-to-date through the last complete billing day; Cost Explorer end is exclusive at 2026-07-15).
- Utilization window: July 1-14, 2026. CloudWatch metrics are descriptive observations, not proof that a resource is safe to resize or remove.

## Gate 0: Inventory Freeze

- Controlling ledger: `docs/plans/20260715T234717Z_lsmc_aws_readonly_cost_utilization_ledger.md`.
- Owning repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch `jem-dev`, 34 commits behind `origin/jem-dev` at baseline.
- Existing untracked files under `docs/plans/` were present before this audit and are not owned or modified by this work.
- AWS CLI: `aws-cli/1.45.24`; the `lsmc` profile has no default region, so every regional call must pass an explicit region.
- Caller identity: `arn:aws:iam::108782052779:root`. This is wider authority than needed for a read-only audit and is a reportable credential-risk finding; no privileged write action is used.
- Enabled/available regions reported by EC2: 21. Resource Explorer indexes exist only in `us-west-2`, `us-east-1`, and `us-east-2`; AWS Config is recording successfully in those three regions and no Config aggregator exists.
- Live scan limitations: Resource Explorer coverage is not account-wide; direct inventory therefore covers cost-bearing EC2/EBS/EIP/NAT, FSx, RDS/Aurora, ELBv2, and S3 resources across all enabled regions, while Resource Explorer supplements other indexed resource types in its three indexed regions.
- Prior repo state: only the pre-existing untracked plan files shown by `git status --short`; no tracked modifications.
- Legacy collector incident: a dated June collector did not implement `--help` and began refreshing old evidence when invoked with that flag. It was interrupted and all 32 touched tracked files were restored to the clean Gate 0 state. No AWS state changed.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| AWS-001 | Identity/scope | Verify account, principal, regions, and read-only command boundary | SUCCESS | contract_test | Gate 0 | orchestrator | `sts get-caller-identity`; explicit-region `describe-regions`; boundary above |  | Account and scope verified; no mutation authorized. |
| AWS-002 | Untagged inventory | Inventory zero-user-tag cost-bearing resources across enabled regions and supplement indexed services with Resource Explorer | SUCCESS | feature_implementation | Gate 1 | orchestrator | `data/inventory.csv`: 194 direct resources; `data/derived_untagged_resources.csv`: 66 current zero-user-tag resources; `data/resource_explorer_untagged.csv`: 1,612 broader indexed entries |  | Current direct inventory and indexed supplement completed without AWS mutation. |
| AWS-003 | Cost | Rank June and July MTD services, usage types, regions, clusters, and resource IDs | SUCCESS | feature_implementation | Gate 1 | orchestrator | `data/service_monthly.csv`, `service_usage_monthly.csv`, `service_region_monthly.csv`, `resource_daily.csv`, `ec2_cluster_mtd.csv`; grouped totals reconcile exactly to $49,608.9175089151 and $20,620.2612475612 |  | June and July MTD cost surfaces completed and reconciled. |
| AWS-004 | Utilization | Collect CloudWatch utilization for the cost-driving EC2, FSx, RDS, EBS, NAT, and S3 resources | SUCCESS | feature_implementation | Gate 1 | orchestrator | `data/utilization_ec2_top_cost_*`, `utilization_fsx_top_cost.csv`, `utilization_s3_top_cost.csv`, `utilization_rds.csv`, `utilization_ebs.csv`, `utilization_nat.csv` |  | Utilization collected with missing telemetry explicitly labeled. |
| AWS-005 | Data quality | Reconcile service totals, resource coverage, inventory/tag gaps, and telemetry limitations | SUCCESS | contract_test | Gate 4 | orchestrator | Direct totals match grouped totals; EC2 resource-ID coverage 71.06%; top-100 sample coverage 40.18%; 99/100 IDs resolved; 70 nonzero collector calls were only expected S3 NoSuchTagSet/NoSuchLifecycleConfiguration responses |  | Coverage, missing-data, and index-scope limitations are explicit. |
| AWS-006 | Report | Produce and render a technical report with exact IDs, costs, utilization, and limitations | SUCCESS | feature_implementation | Gate 5 | orchestrator | `docs/plans/20260715T234717Z_lsmc_aws_readonly_cost_utilization_report.md`; validated `artifact.json`; Data Analytics renderer returned `ok=true` |  | Durable Markdown companion and rendered technical report completed. |

## Final Report

All rows terminal: yes

Objective complete: yes

Status counts:

- SUCCESS: 11
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
- IN_PROGRESS: 0
- OPEN: 0

Changed files:

- `docs/plans/20260715T234717Z_lsmc_aws_readonly_cost_utilization_ledger.md`
- `docs/plans/20260715T234717Z_lsmc_aws_readonly_cost_utilization_report.md`
- `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/**`

Validation:

- Python compile checks for all five collector/report scripts: success.
- `git diff --check` for the audit artifacts: success.
- Cost Explorer grouped service totals vs direct totals: exact match for June and July MTD.
- MCP artifact validation: `ok=true`, 10 datasets, 5 sources, snapshot status `ready`.
- MCP artifact render: `ok=true`.

Non-success terminal rows: none.

Live approvals not performed:

- No tagging, resizing, stopping, deletion, lifecycle change, role change, budget change, or other AWS mutation was performed.

Residual risks:

- July billing is estimated and can settle.
- Resource-level billing IDs and Resource Explorer indexing are incomplete account views; coverage is quantified in the report.
- CPU, connection, storage, and byte telemetry are descriptive and do not alone establish safe deletion or rightsizing.
- The `lsmc` profile resolves to the account root principal; future scans should use an explicitly read-only assumed role.

## Follow-Up: Resource And Cluster Lifecycle Classification

Requested: classify every resource represented by the audit and every identifiable cluster as active, deleted, stopped, orphaned, or exception, with provider-state evidence. Resolve `jemx3` explicitly.

Classification contract:

- `active`: the resource currently exists and is not in a stopped or failed lifecycle state. The exact AWS provider state is retained separately; an in-progress create/update/delete is not hidden.
- `deleting`: AWS reports an in-progress deletion or instance shutdown; the object still exists but is not counted as active.
- `provisioning_or_updating`: AWS reports a non-delete in-progress transition.
- `stopped`: the resource currently exists and AWS explicitly reports a stopped/stopping state. For ParallelCluster, cluster existence and compute-fleet state are separate fields because a live head node can coexist with a stopped compute fleet.
- `deleted`: the billed or historically tagged resource no longer exists, or CloudFormation/ParallelCluster reports terminal deletion.
- `orphaned`: the resource still exists but its explicit CloudFormation or ParallelCluster owner is terminally deleted or absent. Merely untagged, unattached, or idle is not enough to assert orphaning.
- `exception`: AWS reports `DELETE_FAILED`, `CREATE_FAILED`, `ROLLBACK_FAILED`, `UPDATE_ROLLBACK_FAILED`, or another terminal failure state. The exact stack/resource status reason is retained.
- `exception_recovered`: CloudFormation records `ROLLBACK_COMPLETE` or `UPDATE_ROLLBACK_COMPLETE`; the attempted operation failed, but rollback reached a stable terminal state. This is reported separately from an unresolved failed deletion/rollback.
- `unresolved`: evidence is insufficient to assign one of the requested states without guessing. This is a hard classification gap, not a fallback inference.

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| LC-001 | Cluster inventory | Enumerate current ParallelCluster and CloudFormation state across every enabled region | SUCCESS | feature_implementation | Read-only | orchestrator | `lifecycle_clusters.csv`: 47 rows; `lifecycle_cloudformation_stacks.csv`: 419 rows; live compute-fleet reads; explicit unsupported-region evidence for `ap-northeast-3` and `ap-south-2` |  | 21-region direct/CloudFormation scan complete; ParallelCluster N/A regions explicit. |
| LC-002 | jemx3 | Prove whether `jemx3` is active, stopped, deleted, orphaned, or exceptional | SUCCESS | contract_test | Read-only | orchestrator | `jemx3_lifecycle_evidence.json`; CloudFormation `DELETE_COMPLETE` 2026-07-05T09:22:22.181Z; live ParallelCluster/EC2/FSx absence; `jemx3_related_resources.csv` |  | Cluster, head node, and managed FSx deleted; three live orphaned log groups; five stale tag-index entries verified deleted. |
| LC-003 | Resource lifecycle | Classify every current direct-inventory row and every billed historical resource represented in the audit | SUCCESS | feature_implementation | Read-only | orchestrator | `lifecycle_resources.csv`: 3,468 rows; 196 current direct rows plus 3,457 unique billed identifiers and three verified residuals, deduplicated on exact current matches |  | Counts: 178 active, 3,199 deleted, 10 stopped, 3 orphaned, 1 deleting, 77 unresolved billing identifiers. |
| LC-004 | Ownership failures | Identify proven orphans and failed CloudFormation lifecycle exceptions | SUCCESS | contract_test | Read-only | orchestrator | Three `jemx3` log groups orphaned; `Dayhoff-staging-Network` `DELETE_FAILED`; `marvain-cleanroom-20260712T103857Z` `ROLLBACK_FAILED`; five completed rollback histories separated |  | Two unresolved stack failures, five recovered rollback histories, and three proven orphan resources reported. |
| LC-005 | Report | Add lifecycle tables, definitions, evidence timestamps, and coverage limitations to the durable report/artifact | SUCCESS | feature_implementation | Read-only | orchestrator | Updated Markdown report; artifact validation `ok=true` with 10 datasets/5 sources; artifact render `ok=true`; Python compile and `git diff --check` pass |  | Full CSV plus bounded 500-row interactive preview delivered. |

### Follow-Up Final State

- Snapshot: `2026-07-16T00:45:33.101030Z`.
- Current clusters: `ifx-p2-1000-120-0715` active with fleet `RUNNING`; `tst-10315g` provisioning at `CREATE_IN_PROGRESS`.
- `jemx3`: deleted, not running.
- Full lifecycle resource counts: active 178; deleted 3,199; stopped 10; orphaned 3; deleting 1; unresolved 77.
- CloudFormation: active 57; deleted 353; unresolved exceptions 2; recovered exceptions 5; provisioning/updating 2.
- Read-only verification: 435 recorded calls; 74 nonzero calls were exactly 24 missing S3 tag sets, 46 missing S3 lifecycle configurations, 2 explicitly unsupported ParallelCluster regions, and 2 expected `jemx3` absence proofs.
- All rows terminal: yes.
- Objective complete: yes.

## Follow-Up: Cost Explorer API Call Attribution

Requested: identify the origin of the 63,060 July 1-14 Cost Explorer API requests and distinguish the verified caller from the application-level cause.

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| CE-001 | Billing shape | Reconcile the 63,060 billed requests to Cost Explorer operations and daily volume | IN_PROGRESS | metric_diagnostic | Read-only | orchestrator | Pending `cost_explorer_operation_daily.csv` |  |  |
| CE-002 | Caller | Attribute a day-stratified CloudTrail sample to principal, access key, source IP, and user agent | IN_PROGRESS | metric_diagnostic | Read-only | orchestrator | Pending `cost_explorer_caller_summary.csv` |  |  |
| CE-003 | Host and code | Map the source IP to a live AWS resource and match request parameters to the deployed service code/config | IN_PROGRESS | contract_test | Read-only | orchestrator | Pending `cost_explorer_origin_summary.json`; local Ursa/Dayhoff source |  |  |
| CE-004 | Report | Update the durable report and rendered artifact with the attribution, confidence, and recommended remediation boundary | IN_PROGRESS | feature_implementation | Read-only | orchestrator | Pending report/artifact validation |  |  |

### Follow-Up Working State

- All rows terminal: no.
- Objective complete: no.
- No AWS mutation is authorized or performed.
