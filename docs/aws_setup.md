# AWS Setup

This is the account and operator prerequisite guide for current DayEC.

## Profile And Region

Use an explicit named profile and region:

```bash
export AWS_PROFILE=daylily-service-lsmc
export AWS_REGION=us-west-2
export REGION_AZ=us-west-2b
export DAY_EX_CFG="$HOME/.config/daylily/daylily_ephemeral_cluster.yaml"
aws sts get-caller-identity --profile "$AWS_PROFILE"
```

If the identity check fails, fix AWS credentials before running DayEC. The AWS
validator requires both `--profile` and `--region-az`, and rejects the implicit
`default` profile. Keep the AZ explicit because instance offerings, rendered
cluster demand, networking, and several quotas are evaluated for that target.

## IAM Expectations

The operator path needs permissions for:

- STS identity inspection
- IAM inspection and DayEC bootstrap policy checks
- Service Quotas reads
- EC2 and VPC inspection
- CloudFormation
- ParallelCluster operations
- FSx for Lustre, including data repository associations and data repository tasks
- S3 list/read for reference and run buckets
- S3 write for selected analysis export destinations
- Systems Manager command and interactive sessions
- Budgets and tagging paths used by DayEC cost controls

`dyec aws validate permissions` simulates the operator principal against exact
action groups. In addition to the original cluster-lifecycle groups, current
cost and accounting coverage includes:

- budgets: `budgets:ViewBudget`, `budgets:ModifyBudget`, and
  `billing:GetBillingViewData`, with `s3:GetObject`/`s3:PutObject` coverage for
  the configured `runtime_assets/budget_tags/pcluster-project-budget-tags.tsv`
  reference object
- cost reporting: `ce:GetCostAndUsage`, `ce:GetCostAndUsageWithResources`,
  `ce:GetDimensionValues`, `ce:GetTags`, `ce:ListCostAllocationTags`,
  cost-category reads, and Resource Groups Tagging API get/list actions
- cost centers: account table discovery with `dynamodb:ListTables`, plus
  `dynamodb:DescribeTable`, `dynamodb:CreateTable`, `dynamodb:GetItem`,
  `dynamodb:PutItem`, and `dynamodb:Scan` on the `dayec-cost-centers` and
  `dayec-cost-center-usage` tables
- CUR 2.0: `bcm-data-exports:ListExports`,
  `bcm-data-exports:ListTables`, `bcm-data-exports:GetTable`,
  `bcm-data-exports:CreateExport`, `bcm-data-exports:GetExport`,
  `bcm-data-exports:UpdateExport`, `bcm-data-exports:ListExecutions`,
  `bcm-data-exports:ListTagsForResource`, and
  `bcm-data-exports:TagResource`; the required legacy
  `cur:PutReportDefinition`; and `s3:ListBucket`, `s3:GetBucketLocation`,
  `s3:CreateBucket`, `s3:GetBucketPolicy`, `s3:PutBucketPolicy`,
  `s3:GetObject`, and `s3:PutObject` on the dedicated CUR bucket/prefix
- Glue and Athena: `glue:GetDatabase`, `glue:CreateDatabase`, `glue:GetTable`,
  `glue:CreateTable`, `glue:UpdateTable`, `glue:GetPartition`, and
  `glue:CreatePartition`, plus `athena:GetWorkGroup`,
  `athena:StartQueryExecution`, `athena:GetQueryExecution`, and
  `athena:GetQueryResults` on the explicit `primary` workgroup, with
  `athena:ListWorkGroups`, `athena:ListQueryExecutions`, and
  `athena:BatchGetQueryExecution` for regional active-DML headroom
- Slurm accounting: CloudFormation describe/list/create/update/delete/event
  actions; EC2 instance, network, security-group, and tag lifecycle actions;
  `iam:PassRole` and role/profile lifecycle actions; and Secrets Manager
  create/describe/get/generate/put/update/tag/delete actions used by the
  optional accounting host
- operational signaling and quota usage: SNS actions are simulated against
  the configured `daylily-<cluster_name>-heartbeat` topic ARN, and
  `ec2:DescribeSpotInstanceRequests` is required to count open, unfulfilled
  Spot requests
- DRAGEN: `secretsmanager:DescribeSecret` metadata access and IAM policy reads,
  plus validation that the configured runtime policy grants exactly
  `secretsmanager:DescribeSecret` and `secretsmanager:GetSecretValue` on the
  configured secret ARN
- private DayOA checkout: operator metadata reads for the explicit deploy-key secret
  and managed policy; the managed policy must contain exactly
  `secretsmanager:DescribeSecret` and `secretsmanager:GetSecretValue` on that secret.
  DYEC attaches this policy only to the headnode. Compute queues receive no GitHub
  credential permissions, and preflight never reads the private key value.

The operator simulation is separate from `iam.runtime_cost_policy`. That check
reads the exact managed policy selected by `iam_policy_arn` for the headnode and
requires runtime budget reads plus `dynamodb:GetItem` on both cost-center
tables. A same-name policy that is not the selected policy does not satisfy the
check. The optional DRAGEN check reads secret metadata and the IAM policy
document; it does not read the secret value.
Slurm and DRAGEN operator permissions remain part of the shared service action
groups. Their config-specific results are `slurm_accounting.readiness`,
`quota.slurm_accounting_shape`, and `iam.dragen_license_secret_policy`.
IAM cannot simulate an account-root ARN. For a root profile, operator
simulation rows are therefore `WARN`/`UNKNOWN` and list their unverified SCP,
RCP, and resource-policy boundaries. Use the actual non-root operator role or
user to obtain simulated PASS/FAIL decisions.

Admin bootstrap helpers are packaged under:

- `daylily_ec/resources/payload/bin/admin/daylily_ephemeral_cluster_bootstrap_global.sh`
- `daylily_ec/resources/payload/bin/admin/daylily_ephemeral_cluster_bootstrap_region.sh`

The intended model is group-based policy attachment for operator IAM users.

## Session Manager

The supported connect path requires the regional document:

```text
SSM-SessionManagerRunShell
```

It must:

- enable `runAs`
- set default user to the cluster-appropriate remote user (`ubuntu` for Ubuntu/Intel DayOA headnodes; `ec2-user` for DRAGEN/RHEL-style headnodes)
- start in that user's home directory
- launch a bash login/interactive shell
- source `~/.bashrc`
- disable terminal software flow control before the shell starts

Supported Ubuntu shell profile shape:

```text
cd /home/ubuntu && { stty -ixon -ixoff 2>/dev/null || true; exec bash -ilc 'if [[ -f ~/.bashrc ]]; then source ~/.bashrc; fi; exec bash -i'; }
```

`dyec headnode connect` and SSM-backed command helpers fail if this surface is wrong.

## S3 And FSx Layout

Choose:

- one target AWS region
- one target AZ in that region
- one reference S3 URI in that region
- one control/validation data S3 URI in that region
- one mutable staging prefix in the raw sequencing bucket, for example `s3://lsmc-ssf-sequencing-data/staged_external_data/`
- one or more run-data buckets/prefixes, preferably in the same region
- one analysis-result S3 URI for exports

S3 buckets are regional, not AZ-scoped. Co-locate buckets and FSx in the same AWS region for the expected low-latency, lower-cost path. Cross-region reads or exports are possible only if AWS permissions and network paths allow them, and should be treated as slower and more expensive.

Current FSx DRA strategy:

- reference data DRA: `reference_s3_uri` to `/fsx/references`, including runtime assets under `/fsx/references/runtime_assets`
- control/validation data DRA: on demand from `control_data_s3_uri` to `/fsx/control_data/...`
- staging DRA: on demand from `<raw-seq-bucket>/staged_external_data/remote_stage_*/` to `/fsx/staging/staged_external_sequencing_data/remote_stage_*/`
- run input DRA: selected S3 run prefix to `/fsx/run_dir_mounts/<mount_id>`
- export DRA: one completed `/fsx/analysis_results/<executing_entity>/<analysis_id>` to the requested S3 analysis destination ending in `<executing_entity>/<analysis_id>/`

The reference S3 URI is not the control-data S3 URI, staging S3 URI, or export destination. `dyec export` takes an explicit `--destination-s3-uri`.

## Readiness Validation

```bash
dyec aws validate all \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG" \
  --gap-analysis aws_gap.md

dyec preflight \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG"
```

`aws validate` is a read-only account-readiness command. IAM simulation may
test whether mutating actions would be authorized, but the validator itself
uses identity, simulation, list, scan, describe, get, head, and Service Quotas
calls; it does not create, update, put, delete, start an Athena query, send an
SSM command, start a session, or launch a cluster. `--gap-analysis` writes only
the requested local Markdown file. `preflight` remains the final operator
validator before create.

The permissions mode also performs read-only live readiness probes from the
selected config:

- `budget.readiness`: the account-wide and selected cluster budgets exist and
  their configured limits, current spend, type, monthly/USD shape, cluster-tag
  filters, expected thresholds, and configured subscriber are consistent
- `cost_centers.registry_readiness`: both DynamoDB tables are active with the
  exact key schemas, the reserved `idle` row exists, and every active cost
  center has a current-month usage snapshot no more than 36 hours old and
  monthly spend remains below its registered cap
- `cost_control.cur_export_readiness`: the dedicated bucket region and required
  Data Exports policy statement, exact named CUR 2.0 definition and delivery
  destination, `HEALTHY` state, latest `DELIVERY_SUCCESS`, and required schema
  are visible
- `cost_control.cur_catalog_readiness`: the Glue database, full managed table
  schema/storage contract, and exact current-month partition S3 location match
- `cost_control.athena_readiness`: the explicit `primary` workgroup is enabled;
  no query is started
- `slurm_accounting.readiness`: when accounting is enabled, the baseline VPC
  and matching healthy accounting stack are discoverable, its EC2 host is
  running, and its client security group and secret metadata still exist

The target cluster region comes from the explicit AZ. Cost-center registry
checks intentionally use the current `us-west-2` home-region contract, while
CUR 2.0, its S3 bucket, Glue catalog, and Athena workgroup are checked in the
current `us-east-1` billing-region contract. The validator does not discover or
substitute alternate regional resources.

Use `--gap-analysis` for the complete answer-first report. Its outcome is
`SATISFIED` only when every check passes. A warning is reserved for an
unverifiable result and reported as `UNKNOWN`; known missing, stale, exhausted,
or drifted state is `FAIL`/`NOT SATISFIED`. Either makes the overall outcome
`NOT SATISFIED`. The report includes the profile/account/principal/region/AZ,
PASS/WARN/FAIL counts, a complete results matrix, remediation and details for
every gap, and details for every passing check. `--json` preserves the same
complete check set for machine consumers.

## Quotas

Quota validation covers the rendered cluster shape and baseline resources, including:

- On-Demand and Spot vCPU demand
- separate Standard, X, F, G/VT, P, Inf, Trn, DL, HPC, and High Memory vCPU
  quota families, using current running/pending instances, open unfulfilled
  Spot requests, and the maximum rendered demand for every allowed family in
  mixed compute resources
- requested instance type offerings in the target AZ
- VPC, customer-managed Amazon-pool Elastic IP, per-AZ NAT, and Internet
  Gateway current use plus baseline-stack demand
- EBS gp3 current storage plus new headnode/accounting demand
- FSx for Lustre current use plus rendered demand against the exact Scratch,
  Persistent_1, Persistent_2, or Intelligent-Tiering file-system and storage
  quota family; Intelligent-Tiering also checks read-cache and throughput
  capacity
- visible Spot price signal
- AWS Budget count, including missing global and selected-cluster budgets
- DynamoDB table count, including the two global cost-center tables
- S3 general-purpose bucket count, including the dedicated CUR bucket
- the five-export CUR 2.0 limit, including the named DayEC export
- Athena active-DML current usage plus one allocation query
- CloudFormation stack count when Slurm accounting is enabled

When `slurm_accounting_enabled` is true, quota demand also includes the
configured accounting instance's On-Demand vCPUs, 20 GiB of gp3 storage, and
one accounting CloudFormation stack when that stack does not already exist.
The accounting checks also measure current-use-plus-demand headroom for two VPC
security groups, one network interface, one Secrets Manager secret, one IAM
role, and one instance profile. IAM role/profile counts and ceilings come from
`iam:GetAccountSummary`; the regional resources use Service Quotas plus their
service list/describe APIs. When accounting is disabled, the conditional
additions are zero and no accounting stack is required.

Rerun validation when moving regions, changing AZs, changing cluster size, or changing the cluster template.

## Local Toolchain

Use:

```bash
source ./activate
dyec runtime status
dyec runtime check
aws --version
pcluster version
session-manager-plugin
```

The supported checkout environment is `DAY-EC`.

This repo targets exactly `aws-parallelcluster==3.15.0`; `pcluster version` must report `3.15.0` before cluster lifecycle work. This target only affects local/repo tooling until a separately approved live cluster create or update is performed.
