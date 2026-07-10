# Daylily AWS Permissions And Quotas Validation Report

## Outcome

- Overall: **NOT SATISFIED**
- Satisfied checks: 34 / 77
- Unsatisfied or unknown checks: 43 / 77

## Context

- Mode: `all`
- AWS profile: `lsmc`
- Account: `108782052779`
- Principal: `arn:aws:iam::108782052779:root`
- Region: `us-west-2`
- Region AZ: `us-west-2b`
- Config: `config/daylily_ephemeral_cluster_template.yaml`

## Summary

- PASS: 34
- WARN: 38
- FAIL: 5

## Area Summary

| Area | Satisfied | Unknown | Not satisfied | Total | Outcome |
|---|---:|---:|---:|---:|---|
| Identity | 1 | 0 | 0 | 1 | SATISFIED |
| Permissions | 5 | 38 | 1 | 44 | NOT SATISFIED |
| Budget readiness | 0 | 0 | 1 | 1 | NOT SATISFIED |
| Cost-center readiness | 0 | 0 | 1 | 1 | NOT SATISFIED |
| CUR and cost readiness | 3 | 0 | 0 | 3 | SATISFIED |
| Slurm accounting | 1 | 0 | 0 | 1 | SATISFIED |
| Quotas and headroom | 24 | 0 | 2 | 26 | NOT SATISFIED |

## Results Matrix

| Area | Check | Result | Status |
|---|---|---|---|
| Identity | `aws.identity` | SATISFIED | PASS |
| Permissions | `iam.policy.global` | SATISFIED | PASS |
| Permissions | `iam.policy.regional` | SATISFIED | PASS |
| Permissions | `iam.pcluster_omics_policy` | SATISFIED | PASS |
| Permissions | `ssm.session_document` | SATISFIED | PASS |
| Permissions | `iam.simulation.iam_core` | UNKNOWN | WARN |
| Permissions | `iam.simulation.iam_pass_role` | UNKNOWN | WARN |
| Permissions | `iam.simulation.cloudformation` | UNKNOWN | WARN |
| Permissions | `iam.simulation.ec2_network_compute` | UNKNOWN | WARN |
| Permissions | `iam.simulation.autoscaling_elb` | UNKNOWN | WARN |
| Permissions | `iam.simulation.fsx` | UNKNOWN | WARN |
| Permissions | `iam.simulation.s3` | UNKNOWN | WARN |
| Permissions | `iam.simulation.ssm` | UNKNOWN | WARN |
| Permissions | `iam.simulation.service_quotas` | UNKNOWN | WARN |
| Permissions | `iam.simulation.budgets` | UNKNOWN | WARN |
| Permissions | `iam.simulation.cost_explorer_reports` | UNKNOWN | WARN |
| Permissions | `iam.simulation.dynamodb_cost_center_list` | UNKNOWN | WARN |
| Permissions | `iam.simulation.dynamodb_cost_centers` | UNKNOWN | WARN |
| Permissions | `iam.simulation.cur_data_exports_list` | UNKNOWN | WARN |
| Permissions | `iam.simulation.cur_data_exports_table` | UNKNOWN | WARN |
| Permissions | `iam.simulation.cur_data_exports_create` | UNKNOWN | WARN |
| Permissions | `iam.simulation.cur_data_exports_resource` | UNKNOWN | WARN |
| Permissions | `iam.simulation.cur_data_exports_update` | UNKNOWN | WARN |
| Permissions | `iam.simulation.cur_legacy_dependency` | UNKNOWN | WARN |
| Permissions | `iam.simulation.glue_cur_catalog` | UNKNOWN | WARN |
| Permissions | `iam.simulation.athena_workgroup_list` | UNKNOWN | WARN |
| Permissions | `iam.simulation.athena_cur_queries` | UNKNOWN | WARN |
| Permissions | `iam.simulation.sns_list` | UNKNOWN | WARN |
| Permissions | `iam.simulation.sns_topic` | UNKNOWN | WARN |
| Permissions | `iam.simulation.scheduler` | UNKNOWN | WARN |
| Permissions | `iam.simulation.lambda_imagebuilder` | UNKNOWN | WARN |
| Permissions | `iam.simulation.cloudwatch_logs` | UNKNOWN | WARN |
| Permissions | `iam.simulation.dynamodb_parallelcluster` | UNKNOWN | WARN |
| Permissions | `iam.simulation.parallelcluster_backing_services` | UNKNOWN | WARN |
| Permissions | `iam.simulation.cur_s3_bucket` | UNKNOWN | WARN |
| Permissions | `iam.simulation.cur_s3_objects` | UNKNOWN | WARN |
| Permissions | `iam.simulation.service_linked_role_spot` | UNKNOWN | WARN |
| Permissions | `iam.simulation.service_linked_role_fsx` | UNKNOWN | WARN |
| Permissions | `iam.simulation.service_linked_role_s3` | UNKNOWN | WARN |
| Permissions | `iam.simulation.service_linked_role_imagebuilder` | UNKNOWN | WARN |
| Permissions | `iam.simulation.service_linked_role_ec2` | UNKNOWN | WARN |
| Permissions | `iam.simulation.service_linked_role_lambda` | UNKNOWN | WARN |
| Permissions | `iam.simulation.service_linked_role_budgets` | UNKNOWN | WARN |
| Permissions | `iam.runtime_cost_policy` | NOT SATISFIED | FAIL |
| Permissions | `iam.dragen_license_secret_policy` | SATISFIED | PASS |
| Budget readiness | `budget.readiness` | NOT SATISFIED | FAIL |
| Cost-center readiness | `cost_centers.registry_readiness` | NOT SATISFIED | FAIL |
| CUR and cost readiness | `cost_control.cur_export_readiness` | SATISFIED | PASS |
| CUR and cost readiness | `cost_control.cur_catalog_readiness` | SATISFIED | PASS |
| CUR and cost readiness | `cost_control.athena_readiness` | SATISFIED | PASS |
| Slurm accounting | `slurm_accounting.readiness` | SATISFIED | PASS |
| Quotas and headroom | `quota.vpcs` | SATISFIED | PASS |
| Quotas and headroom | `quota.elastic_ips` | SATISFIED | PASS |
| Quotas and headroom | `quota.nat_gateways` | SATISFIED | PASS |
| Quotas and headroom | `quota.internet_gateways` | SATISFIED | PASS |
| Quotas and headroom | `quota.network.baseline_stack` | NOT SATISFIED | FAIL |
| Quotas and headroom | `quota.slurm_accounting_shape` | SATISFIED | PASS |
| Quotas and headroom | `quota.budget_count` | SATISFIED | PASS |
| Quotas and headroom | `quota.dynamodb_table_count` | SATISFIED | PASS |
| Quotas and headroom | `quota.s3_bucket_count` | SATISFIED | PASS |
| Quotas and headroom | `quota.cur2_export_count` | SATISFIED | PASS |
| Quotas and headroom | `quota.athena_active_dml` | SATISFIED | PASS |
| Quotas and headroom | `quota.cloudformation_stack_count` | SATISFIED | PASS |
| Quotas and headroom | `quota.slurm_accounting.security_groups` | SATISFIED | PASS |
| Quotas and headroom | `quota.slurm_accounting.network_interfaces` | SATISFIED | PASS |
| Quotas and headroom | `quota.slurm_accounting.secrets` | SATISFIED | PASS |
| Quotas and headroom | `quota.slurm_accounting.iam_roles` | SATISFIED | PASS |
| Quotas and headroom | `quota.slurm_accounting.iam_instance_profiles` | SATISFIED | PASS |
| Quotas and headroom | `quota.cluster_shape` | SATISFIED | PASS |
| Quotas and headroom | `quota.rendered_ondemand_vcpu` | SATISFIED | PASS |
| Quotas and headroom | `quota.rendered_spot_vcpu` | SATISFIED | PASS |
| Quotas and headroom | `quota.rendered_spot_vcpu.x` | NOT SATISFIED | FAIL |
| Quotas and headroom | `quota.instance_type_offerings` | SATISFIED | PASS |
| Quotas and headroom | `quota.spot_market_signal` | SATISFIED | PASS |
| Quotas and headroom | `quota.ebs.gp3_storage` | SATISFIED | PASS |
| Quotas and headroom | `quota.fsx.lustre_scratch_filesystems` | SATISFIED | PASS |
| Quotas and headroom | `quota.fsx.lustre_scratch_storage` | SATISFIED | PASS |

## Required Admin Follow-Up

### iam.simulation.iam_core - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "iam:ListPolicies",
    "iam:GetPolicy",
    "iam:GetPolicyVersion",
    "iam:ListAttachedUserPolicies",
    "iam:ListGroupsForUser",
    "iam:ListAttachedGroupPolicies",
    "iam:ListRoles",
    "iam:ListInstanceProfiles",
    "iam:GetAccountSummary",
    "iam:GetRole",
    "iam:CreateRole",
    "iam:DeleteRole",
    "iam:CreateInstanceProfile",
    "iam:DeleteInstanceProfile",
    "iam:AddRoleToInstanceProfile",
    "iam:RemoveRoleFromInstanceProfile",
    "iam:AttachRolePolicy",
    "iam:DetachRolePolicy",
    "iam:PutRolePolicy",
    "iam:DeleteRolePolicy",
    "iam:TagRole",
    "iam:UntagRole",
    "iam:SimulatePrincipalPolicy"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.iam_pass_role - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "iam:PassRole"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "arn:aws:iam::108782052779:role/daylily-validation-role"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.cloudformation - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "cloudformation:DescribeStacks",
    "cloudformation:ListStacks",
    "cloudformation:CreateStack",
    "cloudformation:UpdateStack",
    "cloudformation:DeleteStack",
    "cloudformation:DescribeStackEvents"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.ec2_network_compute - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "ec2:DescribeAvailabilityZones",
    "ec2:DescribeInstanceTypes",
    "ec2:DescribeInstanceTypeOfferings",
    "ec2:DescribeSpotPriceHistory",
    "ec2:DescribeSpotInstanceRequests",
    "ec2:DescribeSubnets",
    "ec2:DescribeVpcs",
    "ec2:DescribeInstances",
    "ec2:DescribeImages",
    "ec2:DescribeSecurityGroups",
    "ec2:DescribeNetworkInterfaces",
    "ec2:DescribeRouteTables",
    "ec2:DescribeVolumes",
    "ec2:DescribeAddresses",
    "ec2:DescribeInternetGateways",
    "ec2:DescribeNatGateways",
    "ec2:CreateVpc",
    "ec2:DeleteVpc",
    "ec2:CreateSubnet",
    "ec2:DeleteSubnet",
    "ec2:CreateInternetGateway",
    "ec2:AttachInternetGateway",
    "ec2:DetachInternetGateway",
    "ec2:CreateNatGateway",
    "ec2:DeleteNatGateway",
    "ec2:AllocateAddress",
    "ec2:ReleaseAddress",
    "ec2:CreateSecurityGroup",
    "ec2:AuthorizeSecurityGroupIngress",
    "ec2:AuthorizeSecurityGroupEgress",
    "ec2:RunInstances",
    "ec2:TerminateInstances",
    "ec2:CreateTags",
    "ec2:DeleteTags"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.autoscaling_elb - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "autoscaling:DescribeAutoScalingGroups",
    "autoscaling:CreateAutoScalingGroup",
    "autoscaling:DeleteAutoScalingGroup",
    "elasticloadbalancing:DescribeLoadBalancers",
    "elasticloadbalancing:CreateLoadBalancer",
    "elasticloadbalancing:DeleteLoadBalancer"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.fsx - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "fsx:DescribeFileSystems",
    "fsx:CreateFileSystem",
    "fsx:DeleteFileSystem",
    "fsx:CreateDataRepositoryAssociation",
    "fsx:DescribeDataRepositoryAssociations",
    "fsx:DeleteDataRepositoryAssociation",
    "fsx:CreateDataRepositoryTask",
    "fsx:DescribeDataRepositoryTasks",
    "fsx:TagResource"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.s3 - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "s3:ListAllMyBuckets",
    "s3:GetBucketLocation",
    "s3:CreateBucket",
    "s3:GetBucketPolicy",
    "s3:PutBucketPolicy",
    "s3:ListBucket",
    "s3:GetObject",
    "s3:PutObject",
    "s3:DeleteObject"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.ssm - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "ssm:GetDocument",
    "ssm:GetParameter",
    "ssm:GetParameters",
    "ssm:DescribeInstanceInformation",
    "ssm:StartSession",
    "ssm:TerminateSession",
    "ssm:DescribeSessions",
    "ssm:SendCommand",
    "ssm:GetCommandInvocation"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.service_quotas - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "servicequotas:GetServiceQuota",
    "servicequotas:ListServiceQuotas",
    "servicequotas:ListAWSDefaultServiceQuotas"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.budgets - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "budgets:ViewBudget",
    "budgets:ModifyBudget",
    "billing:GetBillingViewData"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.cost_explorer_reports - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "ce:GetCostAndUsage",
    "ce:GetCostAndUsageWithResources",
    "ce:GetDimensionValues",
    "ce:GetTags",
    "ce:ListCostAllocationTags",
    "ce:DescribeCostCategoryDefinition",
    "ce:ListCostCategoryDefinitions",
    "tag:GetResources",
    "tag:GetTagKeys",
    "tag:GetTagValues"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.dynamodb_cost_center_list - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "dynamodb:ListTables"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.dynamodb_cost_centers - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "dynamodb:DescribeTable",
    "dynamodb:CreateTable",
    "dynamodb:GetItem",
    "dynamodb:PutItem",
    "dynamodb:Scan"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "arn:aws:dynamodb:us-west-2:108782052779:table/dayec-cost-centers",
    "arn:aws:dynamodb:us-west-2:108782052779:table/dayec-cost-center-usage"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.cur_data_exports_list - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "bcm-data-exports:ListExports",
    "bcm-data-exports:ListTables"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.cur_data_exports_table - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "bcm-data-exports:GetTable"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "arn:aws:bcm-data-exports:us-east-1:108782052779:table/COST_AND_USAGE_REPORT"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.cur_data_exports_create - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "bcm-data-exports:CreateExport"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "arn:aws:bcm-data-exports:us-east-1:108782052779:export/*",
    "arn:aws:bcm-data-exports:us-east-1:108782052779:table/COST_AND_USAGE_REPORT"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.cur_data_exports_resource - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "bcm-data-exports:GetExport",
    "bcm-data-exports:ListExecutions",
    "bcm-data-exports:ListTagsForResource",
    "bcm-data-exports:TagResource"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "arn:aws:bcm-data-exports:us-east-1:108782052779:export/*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.cur_data_exports_update - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "bcm-data-exports:UpdateExport"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "arn:aws:bcm-data-exports:us-east-1:108782052779:export/*",
    "arn:aws:bcm-data-exports:us-east-1:108782052779:table/COST_AND_USAGE_REPORT"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.cur_legacy_dependency - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "cur:PutReportDefinition"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.glue_cur_catalog - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "glue:GetDatabase",
    "glue:CreateDatabase",
    "glue:GetTable",
    "glue:CreateTable",
    "glue:UpdateTable",
    "glue:GetPartition",
    "glue:CreatePartition"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.athena_workgroup_list - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "athena:ListWorkGroups"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.athena_cur_queries - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "athena:GetWorkGroup",
    "athena:StartQueryExecution",
    "athena:GetQueryExecution",
    "athena:GetQueryResults",
    "athena:ListQueryExecutions",
    "athena:BatchGetQueryExecution"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "arn:aws:athena:us-east-1:108782052779:workgroup/*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.sns_list - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "sns:ListTopics",
    "sns:ListSubscriptions"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.sns_topic - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "sns:CreateTopic",
    "sns:ListSubscriptionsByTopic",
    "sns:GetTopicAttributes",
    "sns:SetTopicAttributes",
    "sns:Subscribe",
    "sns:Unsubscribe",
    "sns:Publish",
    "sns:DeleteTopic"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "arn:aws:sns:us-west-2:108782052779:daylily-majors-cluster-heartbeat"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.scheduler - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "scheduler:CreateSchedule",
    "scheduler:GetSchedule",
    "scheduler:ListSchedules",
    "scheduler:UpdateSchedule",
    "scheduler:DeleteSchedule"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.lambda_imagebuilder - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "lambda:CreateFunction",
    "lambda:GetFunction",
    "lambda:ListFunctions",
    "lambda:DeleteFunction",
    "lambda:AddPermission",
    "lambda:RemovePermission",
    "imagebuilder:ListImages",
    "imagebuilder:GetImage",
    "imagebuilder:CreateImage",
    "imagebuilder:DeleteImage"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.cloudwatch_logs - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "cloudwatch:PutMetricData",
    "cloudwatch:DescribeAlarms",
    "cloudwatch:PutMetricAlarm",
    "cloudwatch:DeleteAlarms",
    "logs:CreateLogGroup",
    "logs:CreateLogStream",
    "logs:DescribeLogGroups",
    "logs:PutLogEvents",
    "logs:DeleteLogGroup"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.dynamodb_parallelcluster - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "dynamodb:CreateTable",
    "dynamodb:DescribeTable",
    "dynamodb:UpdateTable",
    "dynamodb:DeleteTable",
    "dynamodb:TagResource"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "arn:aws:dynamodb:us-west-2:108782052779:table/parallelcluster-validation"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.parallelcluster_backing_services - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "tag:GetResources",
    "tag:TagResources",
    "tag:UntagResources",
    "route53:ListHostedZones",
    "route53:ChangeResourceRecordSets",
    "apigateway:GET",
    "apigateway:POST",
    "apigateway:DELETE",
    "secretsmanager:CreateSecret",
    "secretsmanager:DescribeSecret",
    "secretsmanager:ListSecrets",
    "secretsmanager:GetSecretValue",
    "secretsmanager:GetRandomPassword",
    "secretsmanager:PutSecretValue",
    "secretsmanager:UpdateSecret",
    "secretsmanager:TagResource",
    "secretsmanager:DeleteSecret",
    "ecr:GetAuthorizationToken",
    "ecr:DescribeRepositories",
    "ecr:CreateRepository",
    "ecr:DeleteRepository",
    "cognito-idp:ListUserPools",
    "elasticfilesystem:DescribeFileSystems"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.cur_s3_bucket - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "s3:ListBucket",
    "s3:GetBucketLocation",
    "s3:CreateBucket",
    "s3:GetBucketPolicy",
    "s3:PutBucketPolicy"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "arn:aws:s3:::dayec-cur-108782052779-us-east-1"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.cur_s3_objects - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "s3:GetObject",
    "s3:PutObject"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "arn:aws:s3:::dayec-cur-108782052779-us-east-1/dayec-cur/*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.service_linked_role_spot - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "iam:CreateServiceLinkedRole"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.service_linked_role_fsx - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "iam:CreateServiceLinkedRole"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.service_linked_role_s3 - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "iam:CreateServiceLinkedRole"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.service_linked_role_imagebuilder - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "iam:CreateServiceLinkedRole"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.service_linked_role_ec2 - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "iam:CreateServiceLinkedRole"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.service_linked_role_lambda - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "iam:CreateServiceLinkedRole"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.simulation.service_linked_role_budgets - WARN

IAM does not accept an account-root ARN as a policy-simulation source. Run this validator with the actual non-root operator role/user to prove these actions, or have an AWS administrator verify the listed SCP, RCP, and resource-policy boundaries.

```json
{
  "actions": [
    "iam:CreateServiceLinkedRole"
  ],
  "denied_actions": null,
  "implicit_root_access": true,
  "principal_arn": "arn:aws:iam::108782052779:root",
  "resources": [
    "*"
  ],
  "simulation_performed": false,
  "unverified_boundaries": [
    "AWS Organizations service control policies",
    "AWS Organizations resource control policies",
    "resource-based explicit denies"
  ]
}
```

### iam.runtime_cost_policy - FAIL

Update the selected headnode managed policy with the missing budget and cost-center reads. An older same-name policy is not sufficient.

```json
{
  "actor": "headnode",
  "default_version_id": "v5",
  "missing_permissions": [
    {
      "action": "billing:GetBillingViewData",
      "resource": "*"
    }
  ],
  "policy_arn": "arn:aws:iam::108782052779:policy/pclusterTagsAndBudget",
  "required_permissions": [
    {
      "action": "budgets:ViewBudget",
      "resource": "arn:aws:budgets::108782052779:budget/*"
    },
    {
      "action": "billing:GetBillingViewData",
      "resource": "*"
    },
    {
      "action": "dynamodb:GetItem",
      "resource": "arn:aws:dynamodb:us-west-2:108782052779:table/dayec-cost-centers"
    },
    {
      "action": "dynamodb:GetItem",
      "resource": "arn:aws:dynamodb:us-west-2:108782052779:table/dayec-cost-center-usage"
    }
  ]
}
```

### budget.readiness - FAIL

Create the missing budgets explicitly: majors-cluster Reconcile the live budget limits, current spend, and notification subscriptions with the explicit DayEC configuration.

```json
{
  "actor": "operator",
  "budget_configuration_gaps": [
    {
      "budget": "daylily-global",
      "reason": "live limit differs from configured limit"
    },
    {
      "budget": "daylily-global",
      "reason": "live cost filters differ from the configured cluster-tag filter"
    },
    {
      "budget": "majors-cluster",
      "reason": "budget is missing"
    }
  ],
  "budget_snapshots": {
    "daylily-global": {
      "actual_spend_amount": "0.0",
      "actual_spend_below_limit": true,
      "actual_spend_unit": "USD",
      "budget_type": "COST",
      "budget_type_valid": true,
      "configured_limit_usd": "200",
      "cost_filter_matches_config": false,
      "cost_filters": {
        "TagKeyValue": [
          "user:aws-parallelcluster-project$daylily-global",
          "user:aws-parallelcluster-clustername$lsmc-oa-us-west-2d-init"
        ]
      },
      "currency_valid": true,
      "exists": true,
      "expected_cost_filter": {
        "TagKeyValue": [
          "user:aws-parallelcluster-clustername$majors-cluster"
        ]
      },
      "expected_notification_thresholds_percent": [
        25,
        50,
        75,
        99
      ],
      "forecast_spend_amount": "",
      "forecast_spend_unit": "",
      "last_updated_time": "2026-07-10T04:04:05.012000Z",
      "limit_amount": "300.0",
      "limit_matches_config": false,
      "limit_unit": "USD",
      "missing_notification_thresholds_percent": [],
      "notifications": [
        {
          "comparison_operator": "GREATER_THAN",
          "notification_type": "ACTUAL",
          "subscriber_addresses": [
            "johnm@lsmc.com"
          ],
          "threshold": 25.0,
          "threshold_type": ""
        },
        {
          "comparison_operator": "GREATER_THAN",
          "notification_type": "ACTUAL",
          "subscriber_addresses": [
            "johnm@lsmc.com"
          ],
          "threshold": 50.0,
          "threshold_type": ""
        },
        {
          "comparison_operator": "GREATER_THAN",
          "notification_type": "ACTUAL",
          "subscriber_addresses": [
            "johnm@lsmc.com"
          ],
          "threshold": 75.0,
          "threshold_type": ""
        },
        {
          "comparison_operator": "GREATER_THAN",
          "notification_type": "ACTUAL",
          "subscriber_addresses": [
            "johnm@lsmc.com"
          ],
          "threshold": 99.0,
          "threshold_type": ""
        }
      ],
      "time_unit": "MONTHLY",
      "time_unit_valid": true
    },
    "majors-cluster": {
      "configured_limit_usd": "200",
      "exists": false,
      "expected_cost_filter": {
        "TagKeyValue": [
          "user:aws-parallelcluster-clustername$majors-cluster"
        ]
      },
      "expected_notification_thresholds_percent": [
        75
      ]
    }
  },
  "cluster_budget": "majors-cluster",
  "cluster_exists": false,
  "enforcement": "true",
  "global_budget": "daylily-global",
  "global_exists": true
}
```

### cost_centers.registry_readiness - FAIL

Refresh current-month usage snapshots and reconcile exhausted caps for every active cost center; the Slurm wrapper rejects missing, stale, or at-cap snapshots.

```json
{
  "active_cost_centers": [
    "cc005955a",
    "cc005955b",
    "cc005955cap",
    "cmdcat-103-all-20260707",
    "cmdcat-103-deny-20260707",
    "dragen-followup-20260708",
    "ifx-reworkB",
    "jul8itelx4",
    "partrevert"
  ],
  "current_month": "2026-07",
  "exhausted_usage": [
    {
      "cost_center": "cc005955cap",
      "monthly_cap_usd": "1",
      "monthly_spend_usd": "1"
    },
    {
      "cost_center": "cmdcat-103-deny-20260707",
      "monthly_cap_usd": "1",
      "monthly_spend_usd": "1"
    }
  ],
  "home_region": "us-west-2",
  "invalid_tables": {},
  "max_usage_age_hours": 36,
  "missing_tables": [],
  "missing_usage": [],
  "reserved_idle_present": true,
  "stale_usage": [
    {
      "age_hours": 127.03,
      "cost_center": "cc005955a",
      "latest_processed_hour": "2026-07-05T01:00:00Z"
    },
    {
      "age_hours": 127.03,
      "cost_center": "cc005955b",
      "latest_processed_hour": "2026-07-05T01:00:00Z"
    },
    {
      "age_hours": 127.03,
      "cost_center": "cc005955cap",
      "latest_processed_hour": "2026-07-05T01:00:00Z"
    },
    {
      "age_hours": 63.03,
      "cost_center": "cmdcat-103-all-20260707",
      "latest_processed_hour": "2026-07-07T17:00:00Z"
    },
    {
      "age_hours": 63.03,
      "cost_center": "cmdcat-103-deny-20260707",
      "latest_processed_hour": "2026-07-07T17:00:00Z"
    },
    {
      "age_hours": 43.03,
      "cost_center": "dragen-followup-20260708",
      "latest_processed_hour": "2026-07-08T13:00:00Z"
    },
    {
      "age_hours": 41.03,
      "cost_center": "jul8itelx4",
      "latest_processed_hour": "2026-07-08T15:00:00Z"
    }
  ],
  "tables": {
    "dayec-cost-center-usage": {
      "item_count": 10,
      "key_schema": [
        {
          "AttributeName": "cost_center",
          "KeyType": "HASH"
        },
        {
          "AttributeName": "month",
          "KeyType": "RANGE"
        }
      ],
      "status": "ACTIVE"
    },
    "dayec-cost-centers": {
      "item_count": 11,
      "key_schema": [
        {
          "AttributeName": "cost_center",
          "KeyType": "HASH"
        }
      ],
      "status": "ACTIVE"
    }
  },
  "usage_snapshots": {
    "cc005955a": {
      "age_hours": 127.03,
      "latest_processed_hour": "2026-07-05T01:00:00Z",
      "monthly_cap_usd": "200",
      "monthly_spend_usd": "0",
      "spend_below_cap": true
    },
    "cc005955b": {
      "age_hours": 127.03,
      "latest_processed_hour": "2026-07-05T01:00:00Z",
      "monthly_cap_usd": "200",
      "monthly_spend_usd": "0",
      "spend_below_cap": true
    },
    "cc005955cap": {
      "age_hours": 127.03,
      "latest_processed_hour": "2026-07-05T01:00:00Z",
      "monthly_cap_usd": "1",
      "monthly_spend_usd": "1",
      "spend_below_cap": false
    },
    "cmdcat-103-all-20260707": {
      "age_hours": 63.03,
      "latest_processed_hour": "2026-07-07T17:00:00Z",
      "monthly_cap_usd": "5000",
      "monthly_spend_usd": "0",
      "spend_below_cap": true
    },
    "cmdcat-103-deny-20260707": {
      "age_hours": 63.03,
      "latest_processed_hour": "2026-07-07T17:00:00Z",
      "monthly_cap_usd": "1",
      "monthly_spend_usd": "1",
      "spend_below_cap": false
    },
    "dragen-followup-20260708": {
      "age_hours": 43.03,
      "latest_processed_hour": "2026-07-08T13:00:00Z",
      "monthly_cap_usd": "250",
      "monthly_spend_usd": "0",
      "spend_below_cap": true
    },
    "ifx-reworkB": {
      "age_hours": 30.03,
      "latest_processed_hour": "2026-07-09T02:00:00Z",
      "monthly_cap_usd": "200",
      "monthly_spend_usd": "0",
      "spend_below_cap": true
    },
    "jul8itelx4": {
      "age_hours": 41.03,
      "latest_processed_hour": "2026-07-08T15:00:00Z",
      "monthly_cap_usd": "200",
      "monthly_spend_usd": "0",
      "spend_below_cap": true
    },
    "partrevert": {
      "age_hours": 25.03,
      "latest_processed_hour": "2026-07-09T07:00:00Z",
      "monthly_cap_usd": "5000",
      "monthly_spend_usd": "0",
      "spend_below_cap": true
    }
  }
}
```

### quota.network.baseline_stack - FAIL

Baseline network stack is absent or unreadable. Ensure VPC, NAT Gateway, Elastic IP, and Internet Gateway quotas can support the first Daylily stack in this AZ.

```json
{
  "network_quota_checks": [
    "quota.vpcs",
    "quota.nat_gateways",
    "quota.internet_gateways"
  ],
  "stack_name": "pcluster-vpc-stack-2b",
  "stack_status": "ROLLBACK_COMPLETE"
}
```

### quota.rendered_spot_vcpu.x - FAIL

Current use plus rendered demand requires 1736 vCPUs from All X Spot Instance Requests, but quota L-E3A00192 is 128. Request an increase or reduce the configured queue MaxCount/instance-family choices.

```json
{
  "additional_slurm_accounting_vcpus": 0,
  "capacity_type": "SPOT",
  "covered_instance_types": [
    "x2idn.32xlarge",
    "x2idn.metal",
    "x2iedn.2xlarge",
    "x2iedn.32xlarge",
    "x2iedn.metal",
    "x8i.2xlarge",
    "x8i.32xlarge",
    "x8i.48xlarge",
    "x8i.metal-48xl"
  ],
  "current_instance_count": 0,
  "current_open_spot_request_count": 0,
  "current_used_vcpus": 0,
  "current_value": 128.0,
  "projected_used_vcpus": 1736,
  "quota_code": "L-E3A00192",
  "quota_group": "x",
  "quota_name": "All X Spot Instance Requests",
  "remaining_after_required_vcpus": -1608,
  "rendered_demand_vcpus": 1736,
  "service_code": "ec2"
}
```

## Passing Validation Checks

### aws.identity - PASS

```json
{
  "account_id": "108782052779",
  "caller_arn": "arn:aws:iam::108782052779:root",
  "profile": "lsmc",
  "region": "us-west-2",
  "region_az": "us-west-2b"
}
```

### iam.policy.global - PASS

```json
{
  "note": "root account \u2014 implicit full access",
  "policy": "DaylilyGlobalEClusterPolicy",
  "user": "root"
}
```

### iam.policy.regional - PASS

```json
{
  "note": "root account \u2014 implicit full access",
  "policy": "DaylilyRegionalEClusterPolicy-us-west-2",
  "user": "root"
}
```

### iam.pcluster_omics_policy - PASS

```json
{
  "arn": "arn:aws:iam::108782052779:policy/pcluster-omics-analysis",
  "policy": "pcluster-omics-analysis",
  "read_only": true
}
```

### ssm.session_document - PASS

```json
{
  "document": "SSM-SessionManagerRunShell",
  "runAsDefaultUser": "ubuntu",
  "runAsEnabled": true,
  "shellProfileLinux": "cd /home/ubuntu && { stty -ixon -ixoff 2>/dev/null || true; exec bash -l; }"
}
```

### iam.dragen_license_secret_policy - PASS

```json
{
  "configured": false,
  "secret_value_read": false
}
```

### cost_control.cur_export_readiness - PASS

```json
{
  "billing_region": "us-east-1",
  "bucket": "dayec-cur-108782052779-us-east-1",
  "bucket_policy_valid": true,
  "bucket_region": "us-east-1",
  "cluster_tag_key": "user_parallelcluster_cluster_name",
  "expected_export_definition": {
    "DataQuery": {
      "QueryStatement": "SELECT line_item_resource_id, line_item_usage_start_date, line_item_usage_end_date, line_item_product_code, line_item_usage_type, line_item_operation, line_item_unblended_cost, line_item_currency_code, line_item_line_item_type, pricing_term, product_region_code, resource_tags FROM COST_AND_USAGE_REPORT",
      "TableConfigurations": {
        "COST_AND_USAGE_REPORT": {
          "INCLUDE_MANUAL_DISCOUNT_COMPATIBILITY": "FALSE",
          "INCLUDE_RESOURCES": "TRUE",
          "INCLUDE_SPLIT_COST_ALLOCATION_DATA": "FALSE",
          "TIME_GRANULARITY": "HOURLY"
        }
      }
    },
    "Description": "DayEC hourly CUR 2.0 export for Slurm cost-center allocation.",
    "DestinationConfigurations": {
      "S3Destination": {
        "S3Bucket": "dayec-cur-108782052779-us-east-1",
        "S3BucketOwner": "108782052779",
        "S3OutputConfigurations": {
          "Compression": "PARQUET",
          "Format": "PARQUET",
          "OutputType": "CUSTOM",
          "Overwrite": "OVERWRITE_REPORT"
        },
        "S3Prefix": "dayec-cur",
        "S3Region": "us-east-1"
      }
    },
    "Name": "dayec-cur2-hourly",
    "RefreshCadence": {
      "Frequency": "SYNCHRONOUS"
    }
  },
  "export_arn": "arn:aws:bcm-data-exports:us-east-1:108782052779:export/dayec-cur2-hourly-1298e4fd-17f5-4a1d-8426-2e47493e0a45",
  "export_definition": {
    "DataQuery": {
      "QueryStatement": "SELECT line_item_resource_id, line_item_usage_start_date, line_item_usage_end_date, line_item_product_code, line_item_usage_type, line_item_operation, line_item_unblended_cost, line_item_currency_code, line_item_line_item_type, pricing_term, product_region_code, resource_tags FROM COST_AND_USAGE_REPORT",
      "TableConfigurations": {
        "COST_AND_USAGE_REPORT": {
          "BILLING_VIEW_ARN": "arn:aws:billing::108782052779:billingview/primary",
          "INCLUDE_MANUAL_DISCOUNT_COMPATIBILITY": "FALSE",
          "INCLUDE_RESOURCES": "TRUE",
          "INCLUDE_SPLIT_COST_ALLOCATION_DATA": "FALSE",
          "TIME_GRANULARITY": "HOURLY"
        }
      }
    },
    "Description": "DayEC hourly CUR 2.0 export for Slurm cost-center allocation.",
    "DestinationConfigurations": {
      "S3Destination": {
        "S3Bucket": "dayec-cur-108782052779-us-east-1",
        "S3BucketOwner": "108782052779",
        "S3OutputConfigurations": {
          "Compression": "PARQUET",
          "Format": "PARQUET",
          "OutputType": "CUSTOM",
          "Overwrite": "OVERWRITE_REPORT"
        },
        "S3Prefix": "dayec-cur",
        "S3Region": "us-east-1"
      }
    },
    "ExportArn": "arn:aws:bcm-data-exports:us-east-1:108782052779:export/dayec-cur2-hourly-1298e4fd-17f5-4a1d-8426-2e47493e0a45",
    "Name": "dayec-cur2-hourly",
    "RefreshCadence": {
      "Frequency": "SYNCHRONOUS"
    }
  },
  "export_definition_matches": true,
  "export_name": "dayec-cur2-hourly",
  "export_status": {
    "CreatedAt": "2026-07-05T09:37:37.389000Z",
    "LastRefreshedAt": "2026-07-10T03:55:54.913000Z",
    "LastUpdatedAt": "2026-07-05T09:37:37.389000Z",
    "StatusCode": "HEALTHY"
  },
  "invalid": [],
  "latest_execution": {
    "ExecutionId": "6ddf17ff-b767-346c-b1dd-001cbeeefbfa",
    "ExecutionStatus": {
      "CreatedAt": "2026-07-10T03:36:03.858000Z",
      "LastUpdatedAt": "2026-07-10T03:55:54.905433Z",
      "StatusCode": "DELIVERY_SUCCESS"
    }
  },
  "missing": [],
  "missing_query_columns": [],
  "schema_columns": [
    "line_item_currency_code",
    "line_item_line_item_type",
    "line_item_operation",
    "line_item_product_code",
    "line_item_resource_id",
    "line_item_unblended_cost",
    "line_item_usage_end_date",
    "line_item_usage_start_date",
    "line_item_usage_type",
    "pricing_term",
    "product_region_code",
    "resource_tags"
  ]
}
```

### cost_control.cur_catalog_readiness - PASS

```json
{
  "billing_period": "2026-07",
  "database": "dayec_cur",
  "database_exists": true,
  "expected_partition_location": "s3://dayec-cur-108782052779-us-east-1/dayec-cur/dayec-cur2-hourly/data/BILLING_PERIOD=2026-07/",
  "expected_table_location": "s3://dayec-cur-108782052779-us-east-1/dayec-cur/dayec-cur2-hourly/data/",
  "invalid": [],
  "managed": true,
  "missing": [],
  "partition_contract_matches": true,
  "partition_exists": true,
  "partition_location": "s3://dayec-cur-108782052779-us-east-1/dayec-cur/dayec-cur2-hourly/data/BILLING_PERIOD=2026-07/",
  "region": "us-east-1",
  "schema_columns": [
    "line_item_currency_code",
    "line_item_line_item_type",
    "line_item_operation",
    "line_item_product_code",
    "line_item_resource_id",
    "line_item_unblended_cost",
    "line_item_usage_end_date",
    "line_item_usage_start_date",
    "line_item_usage_type",
    "pricing_term",
    "product_region_code",
    "resource_tags"
  ],
  "table": "cur2_hourly",
  "table_contract_matches": true,
  "table_exists": true,
  "table_location": "s3://dayec-cur-108782052779-us-east-1/dayec-cur/dayec-cur2-hourly/data/"
}
```

### cost_control.athena_readiness - PASS

```json
{
  "query_started": false,
  "region": "us-east-1",
  "state": "ENABLED",
  "workgroup": "primary"
}
```

### slurm_accounting.readiness - PASS

```json
{
  "configured": false,
  "create_if_missing": false,
  "stack_name": "",
  "status": ""
}
```

### quota.vpcs - PASS

```json
{
  "current_used": 6,
  "current_value": 10.0,
  "projected_used": 7,
  "quota_code": "L-F678F1CE",
  "recommended_min": 5,
  "remaining_after_required": 3,
  "required_new": 1,
  "scope": "us-west-2",
  "service_code": "vpc"
}
```

### quota.elastic_ips - PASS

```json
{
  "current_used": 9,
  "current_value": 10.0,
  "projected_used": 10,
  "quota_code": "L-0263D0A3",
  "recommended_min": 5,
  "remaining_after_required": 0,
  "required_new": 1,
  "scope": "us-west-2",
  "service_code": "ec2"
}
```

### quota.nat_gateways - PASS

```json
{
  "current_used": 0,
  "current_value": 5.0,
  "projected_used": 1,
  "quota_code": "L-FE5A380F",
  "recommended_min": 5,
  "remaining_after_required": 4,
  "required_new": 1,
  "scope": "us-west-2b",
  "service_code": "vpc"
}
```

### quota.internet_gateways - PASS

```json
{
  "current_used": 6,
  "current_value": 10.0,
  "projected_used": 7,
  "quota_code": "L-A4707A72",
  "recommended_min": 5,
  "remaining_after_required": 3,
  "required_new": 1,
  "scope": "us-west-2",
  "service_code": "vpc"
}
```

### quota.slurm_accounting_shape - PASS

```json
{
  "additional_gp3_gib": 0,
  "additional_ondemand_vcpus": 0,
  "configured": false
}
```

### quota.budget_count - PASS

```json
{
  "current_used": 128,
  "missing_budget_names": [
    "majors-cluster"
  ],
  "projected_used": 129,
  "quota": 20000,
  "remaining_after_required": 19871,
  "required_budget_names": [
    "daylily-global",
    "majors-cluster"
  ],
  "required_new": 1,
  "source": "https://docs.aws.amazon.com/cost-management/latest/userguide/management-limits.html"
}
```

### quota.dynamodb_table_count - PASS

```json
{
  "current_used": 26,
  "current_value": 2500.0,
  "error": "",
  "missing_table_names": [],
  "projected_used": 26,
  "quota_code": "L-F98FE922",
  "region": "us-west-2",
  "remaining_after_required": 2474,
  "required_new": 0
}
```

### quota.s3_bucket_count - PASS

```json
{
  "current_used": 45,
  "current_value": 10000.0,
  "desired_bucket": "dayec-cur-108782052779-us-east-1",
  "projected_used": 45,
  "quota_code": "L-DC2B2D3D",
  "remaining_after_required": 9955,
  "required_new": 0
}
```

### quota.cur2_export_count - PASS

```json
{
  "current_used": 1,
  "desired_export": "dayec-cur2-hourly",
  "desired_export_exists": true,
  "projected_used": 1,
  "quota": 5,
  "region": "us-east-1",
  "remaining_after_required": 4,
  "required_new": 0,
  "source": "https://docs.aws.amazon.com/cur/latest/userguide/dataexports-quotas.html"
}
```

### quota.athena_active_dml - PASS

```json
{
  "active_query_execution_ids": [],
  "current_used": 0,
  "current_value": 200.0,
  "projected_used": 1,
  "quota_code": "L-FC5F6546",
  "region": "us-east-1",
  "remaining_after_required": 199,
  "required_new": 1,
  "service_code": "athena",
  "workgroups_inspected": [
    "primary"
  ]
}
```

### quota.cloudformation_stack_count - PASS

```json
{
  "required_new": 0,
  "slurm_accounting_enabled": false
}
```

### quota.slurm_accounting.security_groups - PASS

```json
{
  "configured": false,
  "quota_code": "L-E79EC296",
  "required_new": 0
}
```

### quota.slurm_accounting.network_interfaces - PASS

```json
{
  "configured": false,
  "quota_code": "L-DF5E4CA3",
  "required_new": 0
}
```

### quota.slurm_accounting.secrets - PASS

```json
{
  "configured": false,
  "quota_code": "L-2F66C23C",
  "required_new": 0
}
```

### quota.slurm_accounting.iam_roles - PASS

```json
{
  "configured": false,
  "quota_code": "RolesQuota",
  "required_new": 0
}
```

### quota.slurm_accounting.iam_instance_profiles - PASS

```json
{
  "configured": false,
  "quota_code": "InstanceProfilesQuota",
  "required_new": 0
}
```

### quota.cluster_shape - PASS

```json
{
  "cluster_name": "majors-cluster",
  "compute_resources": [
    {
      "capacity_type": "SPOT",
      "demand_vcpus": 8,
      "instance_types": [
        "r5.2xlarge",
        "r5n.2xlarge",
        "r6i.2xlarge",
        "r6id.2xlarge",
        "r7i.2xlarge",
        "r8i.2xlarge",
        "i4i.2xlarge",
        "i7i.2xlarge",
        "i7ie.2xlarge",
        "x8i.2xlarge",
        "r6idn.2xlarge",
        "r6in.2xlarge",
        "r7iz.2xlarge",
        "r8id.2xlarge",
        "r8idb.2xlarge",
        "r8idn.2xlarge",
        "x2iedn.2xlarge"
      ],
      "max_count": 1,
      "max_vcpus_per_instance": 8,
      "name": "price8",
      "queue": "i8"
    },
    {
      "capacity_type": "SPOT",
      "demand_vcpus": 128,
      "instance_types": [
        "c6i.32xlarge",
        "c6i.metal",
        "c6in.32xlarge",
        "c6in.metal",
        "m6i.32xlarge",
        "m6i.metal",
        "m6id.32xlarge",
        "m6id.metal",
        "m6in.32xlarge",
        "m6in.metal",
        "m6idn.32xlarge",
        "m6idn.metal",
        "r6i.32xlarge",
        "r6i.metal",
        "r6id.32xlarge",
        "r6id.metal",
        "i4i.32xlarge",
        "i4i.metal",
        "x2idn.32xlarge",
        "x2idn.metal",
        "x2iedn.32xlarge",
        "x2iedn.metal",
        "c8i.32xlarge",
        "m8i.32xlarge",
        "r8i.32xlarge",
        "x8i.32xlarge",
        "c8id.32xlarge",
        "m8id.32xlarge",
        "m8idb.32xlarge",
        "m8idn.32xlarge",
        "r6idn.32xlarge",
        "r6idn.metal",
        "r6in.32xlarge",
        "r6in.metal",
        "r7iz.32xlarge",
        "r7iz.metal-32xl",
        "r8id.32xlarge",
        "r8idb.32xlarge",
        "r8idn.32xlarge"
      ],
      "max_count": 1,
      "max_vcpus_per_instance": 128,
      "name": "price128",
      "queue": "i128"
    },
    {
      "capacity_type": "SPOT",
      "demand_vcpus": 128,
      "instance_types": [
        "m6i.32xlarge",
        "m6i.metal",
        "m6id.32xlarge",
        "m6id.metal",
        "m6in.32xlarge",
        "m6in.metal",
        "m6idn.32xlarge",
        "m6idn.metal",
        "r6i.32xlarge",
        "r6i.metal",
        "r6id.32xlarge",
        "r6id.metal",
        "i4i.32xlarge",
        "i4i.metal",
        "x2idn.32xlarge",
        "x2idn.metal",
        "x2iedn.32xlarge",
        "x2iedn.metal",
        "m8i.32xlarge",
        "r8i.32xlarge",
        "x8i.32xlarge",
        "m8id.32xlarge",
        "m8idb.32xlarge",
        "m8idn.32xlarge",
        "r6idn.32xlarge",
        "r6idn.metal",
        "r6in.32xlarge",
        "r6in.metal",
        "r7iz.32xlarge",
        "r7iz.metal-32xl",
        "r8id.32xlarge",
        "r8idb.32xlarge",
        "r8idn.32xlarge"
      ],
      "max_count": 1,
      "max_vcpus_per_instance": 128,
      "name": "mem128",
      "queue": "i128"
    },
    {
      "capacity_type": "SPOT",
      "demand_vcpus": 128,
      "instance_types": [
        "r6i.32xlarge",
        "r6i.metal",
        "r6id.32xlarge",
        "r6id.metal",
        "i4i.32xlarge",
        "i4i.metal",
        "x2idn.32xlarge",
        "x2idn.metal",
        "x2iedn.32xlarge",
        "x2iedn.metal",
        "r8i.32xlarge",
        "x8i.32xlarge",
        "r6idn.32xlarge",
        "r6idn.metal",
        "r6in.32xlarge",
        "r6in.metal",
        "r7iz.32xlarge",
        "r7iz.metal-32xl",
        "r8id.32xlarge",
        "r8idb.32xlarge",
        "r8idn.32xlarge"
      ],
      "max_count": 1,
      "max_vcpus_per_instance": 128,
      "name": "bigmem128",
      "queue": "i128"
    },
    {
      "capacity_type": "SPOT",
      "demand_vcpus": 128,
      "instance_types": [
        "m6i.32xlarge",
        "m6i.metal",
        "m6id.32xlarge",
        "m6id.metal",
        "m6in.32xlarge",
        "m6in.metal",
        "m6idn.32xlarge",
        "m6idn.metal",
        "r6i.32xlarge",
        "r6i.metal",
        "r6id.32xlarge",
        "r6id.metal",
        "i4i.32xlarge",
        "i4i.metal",
        "x2idn.32xlarge",
        "x2idn.metal",
        "x2iedn.32xlarge",
        "x2iedn.metal",
        "m8i.32xlarge",
        "r8i.32xlarge",
        "x8i.32xlarge",
        "m8id.32xlarge",
        "m8idb.32xlarge",
        "m8idn.32xlarge",
        "r6idn.32xlarge",
        "r6idn.metal",
        "r6in.32xlarge",
        "r6in.metal",
        "r7iz.32xlarge",
        "r7iz.metal-32xl",
        "r8id.32xlarge",
        "r8idb.32xlarge",
        "r8idn.32xlarge"
      ],
      "max_count": 1,
      "max_vcpus_per_instance": 128,
      "name": "mem128",
      "queue": "i128mem"
    },
    {
      "capacity_type": "SPOT",
      "demand_vcpus": 128,
      "instance_types": [
        "r6i.32xlarge",
        "r6i.metal",
        "r6id.32xlarge",
        "r6id.metal",
        "i4i.32xlarge",
        "i4i.metal",
        "x2idn.32xlarge",
        "x2idn.metal",
        "x2iedn.32xlarge",
        "x2iedn.metal",
        "r8i.32xlarge",
        "x8i.32xlarge",
        "r6idn.32xlarge",
        "r6idn.metal",
        "r6in.32xlarge",
        "r6in.metal",
        "r7iz.32xlarge",
        "r7iz.metal-32xl",
        "r8id.32xlarge",
        "r8idb.32xlarge",
        "r8idn.32xlarge"
      ],
      "max_count": 1,
      "max_vcpus_per_instance": 128,
      "name": "bigmem128",
      "queue": "i128bigmem"
    },
    {
      "capacity_type": "SPOT",
      "demand_vcpus": 128,
      "instance_types": [
        "i4i.32xlarge",
        "i4i.metal",
        "r6id.32xlarge",
        "r6id.metal",
        "r6idn.32xlarge",
        "r6idn.metal",
        "r8id.32xlarge",
        "r8idb.32xlarge",
        "r8idn.32xlarge",
        "x2idn.32xlarge",
        "x2idn.metal",
        "x2iedn.32xlarge",
        "x2iedn.metal"
      ],
      "max_count": 1,
      "max_vcpus_per_instance": 128,
      "name": "price128nvme",
      "queue": "i128nvme"
    },
    {
      "capacity_type": "SPOT",
      "demand_vcpus": 192,
      "instance_types": [
        "c7i.48xlarge",
        "c7i.metal-48xl",
        "m7i.48xlarge",
        "m7i.metal-48xl",
        "r7i.48xlarge",
        "r7i.metal-48xl",
        "c8i.48xlarge",
        "c8i.metal-48xl",
        "m8i.48xlarge",
        "m8i.metal-48xl",
        "r8i.48xlarge",
        "r8i.metal-48xl",
        "i7i.48xlarge",
        "i7i.metal-48xl",
        "i7ie.48xlarge",
        "i7ie.metal-48xl",
        "x8i.48xlarge",
        "x8i.metal-48xl",
        "c8id.48xlarge",
        "c8id.metal-48xl",
        "m8id.48xlarge",
        "m8id.metal-48xl",
        "m8idb.48xlarge",
        "m8idn.48xlarge",
        "r8id.48xlarge",
        "r8id.metal-48xl",
        "r8idb.48xlarge",
        "r8idn.48xlarge"
      ],
      "max_count": 1,
      "max_vcpus_per_instance": 192,
      "name": "price192",
      "queue": "i192"
    },
    {
      "capacity_type": "SPOT",
      "demand_vcpus": 192,
      "instance_types": [
        "m7i.48xlarge",
        "m7i.metal-48xl",
        "r7i.48xlarge",
        "r7i.metal-48xl",
        "m8i.48xlarge",
        "m8i.metal-48xl",
        "r8i.48xlarge",
        "r8i.metal-48xl",
        "i7i.48xlarge",
        "i7i.metal-48xl",
        "i7ie.48xlarge",
        "i7ie.metal-48xl",
        "x8i.48xlarge",
        "x8i.metal-48xl",
        "m8id.48xlarge",
        "m8id.metal-48xl",
        "m8idb.48xlarge",
        "m8idn.48xlarge",
        "r8id.48xlarge",
        "r8id.metal-48xl",
        "r8idb.48xlarge",
        "r8idn.48xlarge"
      ],
      "max_count": 1,
      "max_vcpus_per_instance": 192,
      "name": "mem192",
      "queue": "i192"
    },
    {
      "capacity_type": "SPOT",
      "demand_vcpus": 192,
      "instance_types": [
        "r7i.48xlarge",
        "r7i.metal-48xl",
        "r8i.48xlarge",
        "r8i.metal-48xl",
        "i7i.48xlarge",
        "i7i.metal-48xl",
        "i7ie.48xlarge",
        "i7ie.metal-48xl",
        "x8i.48xlarge",
        "x8i.metal-48xl",
        "r8id.48xlarge",
        "r8id.metal-48xl",
        "r8idb.48xlarge",
        "r8idn.48xlarge"
      ],
      "max_count": 1,
      "max_vcpus_per_instance": 192,
      "name": "bigmem192",
      "queue": "i192"
    },
    {
      "capacity_type": "SPOT",
      "demand_vcpus": 192,
      "instance_types": [
        "m7i.48xlarge",
        "m7i.metal-48xl",
        "r7i.48xlarge",
        "r7i.metal-48xl",
        "m8i.48xlarge",
        "m8i.metal-48xl",
        "r8i.48xlarge",
        "r8i.metal-48xl",
        "i7i.48xlarge",
        "i7i.metal-48xl",
        "i7ie.48xlarge",
        "i7ie.metal-48xl",
        "x8i.48xlarge",
        "x8i.metal-48xl",
        "m8id.48xlarge",
        "m8id.metal-48xl",
        "m8idb.48xlarge",
        "m8idn.48xlarge",
        "r8id.48xlarge",
        "r8id.metal-48xl",
        "r8idb.48xlarge",
        "r8idn.48xlarge"
      ],
      "max_count": 1,
      "max_vcpus_per_instance": 192,
      "name": "mem192",
      "queue": "i192mem"
    },
    {
      "capacity_type": "SPOT",
      "demand_vcpus": 192,
      "instance_types": [
        "r7i.48xlarge",
        "r7i.metal-48xl",
        "r8i.48xlarge",
        "r8i.metal-48xl",
        "i7i.48xlarge",
        "i7i.metal-48xl",
        "i7ie.48xlarge",
        "i7ie.metal-48xl",
        "x8i.48xlarge",
        "x8i.metal-48xl",
        "r8id.48xlarge",
        "r8id.metal-48xl",
        "r8idb.48xlarge",
        "r8idn.48xlarge"
      ],
      "max_count": 1,
      "max_vcpus_per_instance": 192,
      "name": "bigmem192",
      "queue": "i192bigmem"
    },
    {
      "capacity_type": "SPOT",
      "demand_vcpus": 192,
      "instance_types": [
        "i7i.48xlarge",
        "i7i.metal-48xl",
        "i7ie.48xlarge",
        "i7ie.metal-48xl",
        "c8id.48xlarge",
        "c8id.metal-48xl",
        "m8id.48xlarge",
        "m8id.metal-48xl",
        "m8idb.48xlarge",
        "m8idn.48xlarge",
        "r8id.48xlarge",
        "r8id.metal-48xl",
        "r8idb.48xlarge",
        "r8idn.48xlarge"
      ],
      "max_count": 1,
      "max_vcpus_per_instance": 192,
      "name": "price192nvme",
      "queue": "i192nvme"
    },
    {
      "capacity_type": "SPOT",
      "demand_vcpus": 192,
      "instance_types": [
        "i7i.48xlarge",
        "i7i.metal-48xl",
        "i7ie.48xlarge",
        "i7ie.metal-48xl",
        "m8id.48xlarge",
        "m8id.metal-48xl",
        "m8idb.48xlarge",
        "m8idn.48xlarge",
        "r8id.48xlarge",
        "r8id.metal-48xl",
        "r8idb.48xlarge",
        "r8idn.48xlarge"
      ],
      "max_count": 1,
      "max_vcpus_per_instance": 192,
      "name": "mem192nvme",
      "queue": "i192nvme"
    },
    {
      "capacity_type": "SPOT",
      "demand_vcpus": 192,
      "instance_types": [
        "i7i.48xlarge",
        "i7i.metal-48xl",
        "i7ie.48xlarge",
        "i7ie.metal-48xl",
        "r8id.48xlarge",
        "r8id.metal-48xl",
        "r8idb.48xlarge",
        "r8idn.48xlarge"
      ],
      "max_count": 1,
      "max_vcpus_per_instance": 192,
      "name": "bigmem192nvme",
      "queue": "i192nvme"
    },
    {
      "capacity_type": "SPOT",
      "demand_vcpus": 384,
      "instance_types": [
        "c8id.96xlarge",
        "c8id.metal-96xl",
        "m8id.96xlarge",
        "m8id.metal-96xl",
        "m8idn.96xlarge",
        "m8idb.96xlarge",
        "r8id.96xlarge",
        "r8id.metal-96xl",
        "r8idn.96xlarge",
        "r8idb.96xlarge"
      ],
      "max_count": 1,
      "max_vcpus_per_instance": 384,
      "name": "price384nvme",
      "queue": "i384nvme"
    },
    {
      "capacity_type": "SPOT",
      "demand_vcpus": 384,
      "instance_types": [
        "m8id.96xlarge",
        "m8id.metal-96xl",
        "m8idn.96xlarge",
        "m8idb.96xlarge",
        "r8id.96xlarge",
        "r8id.metal-96xl",
        "r8idn.96xlarge",
        "r8idb.96xlarge"
      ],
      "max_count": 1,
      "max_vcpus_per_instance": 384,
      "name": "mem384nvme",
      "queue": "i384nvme"
    },
    {
      "capacity_type": "SPOT",
      "demand_vcpus": 384,
      "instance_types": [
        "r8id.96xlarge",
        "r8id.metal-96xl",
        "r8idn.96xlarge",
        "r8idb.96xlarge"
      ],
      "max_count": 1,
      "max_vcpus_per_instance": 384,
      "name": "bigmem384nvme",
      "queue": "i384nvme"
    },
    {
      "capacity_type": "SPOT",
      "demand_vcpus": 192,
      "instance_types": [
        "i7i.48xlarge",
        "i7i.metal-48xl",
        "i7ie.48xlarge",
        "i7ie.metal-48xl",
        "r8id.48xlarge",
        "r8id.metal-48xl",
        "r8idb.48xlarge",
        "r8idn.48xlarge"
      ],
      "max_count": 1,
      "max_vcpus_per_instance": 192,
      "name": "price192hugenvme",
      "queue": "i192hugenvme"
    }
  ],
  "fsx_deployment_type": "SCRATCH_2",
  "fsx_read_cache_gib": 0,
  "fsx_storage_gib": 4800,
  "fsx_storage_type": "SSD",
  "fsx_throughput_capacity": 0,
  "headnode_instance_type": "r7i.2xlarge",
  "headnode_root_volume_gib": 421,
  "headnode_root_volume_type": "gp3",
  "headnode_vcpus": 8,
  "instance_types": [
    "c6i.32xlarge",
    "c6i.metal",
    "c6in.32xlarge",
    "c6in.metal",
    "c7i.48xlarge",
    "c7i.metal-48xl",
    "c8i.32xlarge",
    "c8i.48xlarge",
    "c8i.metal-48xl",
    "c8id.32xlarge",
    "c8id.48xlarge",
    "c8id.96xlarge",
    "c8id.metal-48xl",
    "c8id.metal-96xl",
    "i4i.2xlarge",
    "i4i.32xlarge",
    "i4i.metal",
    "i7i.2xlarge",
    "i7i.48xlarge",
    "i7i.metal-48xl",
    "i7ie.2xlarge",
    "i7ie.48xlarge",
    "i7ie.metal-48xl",
    "m6i.32xlarge",
    "m6i.metal",
    "m6id.32xlarge",
    "m6id.metal",
    "m6idn.32xlarge",
    "m6idn.metal",
    "m6in.32xlarge",
    "m6in.metal",
    "m7i.48xlarge",
    "m7i.metal-48xl",
    "m8i.32xlarge",
    "m8i.48xlarge",
    "m8i.metal-48xl",
    "m8id.32xlarge",
    "m8id.48xlarge",
    "m8id.96xlarge",
    "m8id.metal-48xl",
    "m8id.metal-96xl",
    "m8idb.32xlarge",
    "m8idb.48xlarge",
    "m8idb.96xlarge",
    "m8idn.32xlarge",
    "m8idn.48xlarge",
    "m8idn.96xlarge",
    "r5.2xlarge",
    "r5n.2xlarge",
    "r6i.2xlarge",
    "r6i.32xlarge",
    "r6i.metal",
    "r6id.2xlarge",
    "r6id.32xlarge",
    "r6id.metal",
    "r6idn.2xlarge",
    "r6idn.32xlarge",
    "r6idn.metal",
    "r6in.2xlarge",
    "r6in.32xlarge",
    "r6in.metal",
    "r7i.2xlarge",
    "r7i.48xlarge",
    "r7i.metal-48xl",
    "r7iz.2xlarge",
    "r7iz.32xlarge",
    "r7iz.metal-32xl",
    "r8i.2xlarge",
    "r8i.32xlarge",
    "r8i.48xlarge",
    "r8i.metal-48xl",
    "r8id.2xlarge",
    "r8id.32xlarge",
    "r8id.48xlarge",
    "r8id.96xlarge",
    "r8id.metal-48xl",
    "r8id.metal-96xl",
    "r8idb.2xlarge",
    "r8idb.32xlarge",
    "r8idb.48xlarge",
    "r8idb.96xlarge",
    "r8idn.2xlarge",
    "r8idn.32xlarge",
    "r8idn.48xlarge",
    "r8idn.96xlarge",
    "x2idn.32xlarge",
    "x2idn.metal",
    "x2iedn.2xlarge",
    "x2iedn.32xlarge",
    "x2iedn.metal",
    "x8i.2xlarge",
    "x8i.32xlarge",
    "x8i.48xlarge",
    "x8i.metal-48xl"
  ],
  "rendered_ondemand_vcpus": 8,
  "rendered_spot_vcpus": 3656,
  "template_path": "config/day_cluster/intel/us-west-2/us-west-2b/prod_cluster_intel_us-west-2b.yaml"
}
```

### quota.rendered_ondemand_vcpu - PASS

```json
{
  "additional_slurm_accounting_vcpus": 0,
  "capacity_type": "ONDEMAND",
  "covered_instance_types": [
    "r7i.2xlarge"
  ],
  "current_instance_count": 12,
  "current_open_spot_request_count": 0,
  "current_used_vcpus": 88,
  "current_value": 3048.0,
  "projected_used_vcpus": 96,
  "quota_code": "L-1216C47A",
  "quota_group": "standard",
  "quota_name": "Running On-Demand Standard (A, C, D, H, I, M, R, T, Z) instances",
  "remaining_after_required_vcpus": 2952,
  "rendered_demand_vcpus": 8,
  "service_code": "ec2"
}
```

### quota.rendered_spot_vcpu - PASS

```json
{
  "additional_slurm_accounting_vcpus": 0,
  "capacity_type": "SPOT",
  "covered_instance_types": [
    "c6i.32xlarge",
    "c6i.metal",
    "c6in.32xlarge",
    "c6in.metal",
    "c7i.48xlarge",
    "c7i.metal-48xl",
    "c8i.32xlarge",
    "c8i.48xlarge",
    "c8i.metal-48xl",
    "c8id.32xlarge",
    "c8id.48xlarge",
    "c8id.96xlarge",
    "c8id.metal-48xl",
    "c8id.metal-96xl",
    "i4i.2xlarge",
    "i4i.32xlarge",
    "i4i.metal",
    "i7i.2xlarge",
    "i7i.48xlarge",
    "i7i.metal-48xl",
    "i7ie.2xlarge",
    "i7ie.48xlarge",
    "i7ie.metal-48xl",
    "m6i.32xlarge",
    "m6i.metal",
    "m6id.32xlarge",
    "m6id.metal",
    "m6idn.32xlarge",
    "m6idn.metal",
    "m6in.32xlarge",
    "m6in.metal",
    "m7i.48xlarge",
    "m7i.metal-48xl",
    "m8i.32xlarge",
    "m8i.48xlarge",
    "m8i.metal-48xl",
    "m8id.32xlarge",
    "m8id.48xlarge",
    "m8id.96xlarge",
    "m8id.metal-48xl",
    "m8id.metal-96xl",
    "m8idb.32xlarge",
    "m8idb.48xlarge",
    "m8idb.96xlarge",
    "m8idn.32xlarge",
    "m8idn.48xlarge",
    "m8idn.96xlarge",
    "r5.2xlarge",
    "r5n.2xlarge",
    "r6i.2xlarge",
    "r6i.32xlarge",
    "r6i.metal",
    "r6id.2xlarge",
    "r6id.32xlarge",
    "r6id.metal",
    "r6idn.2xlarge",
    "r6idn.32xlarge",
    "r6idn.metal",
    "r6in.2xlarge",
    "r6in.32xlarge",
    "r6in.metal",
    "r7i.2xlarge",
    "r7i.48xlarge",
    "r7i.metal-48xl",
    "r7iz.2xlarge",
    "r7iz.32xlarge",
    "r7iz.metal-32xl",
    "r8i.2xlarge",
    "r8i.32xlarge",
    "r8i.48xlarge",
    "r8i.metal-48xl",
    "r8id.2xlarge",
    "r8id.32xlarge",
    "r8id.48xlarge",
    "r8id.96xlarge",
    "r8id.metal-48xl",
    "r8id.metal-96xl",
    "r8idb.2xlarge",
    "r8idb.32xlarge",
    "r8idb.48xlarge",
    "r8idb.96xlarge",
    "r8idn.2xlarge",
    "r8idn.32xlarge",
    "r8idn.48xlarge",
    "r8idn.96xlarge"
  ],
  "current_instance_count": 6,
  "current_open_spot_request_count": 0,
  "current_used_vcpus": 1088,
  "current_value": 22173.0,
  "projected_used_vcpus": 4744,
  "quota_code": "L-34B43A08",
  "quota_group": "standard",
  "quota_name": "All Standard (A, C, D, H, I, M, R, T, Z) Spot Instance Requests",
  "remaining_after_required_vcpus": 17429,
  "rendered_demand_vcpus": 3656,
  "service_code": "ec2"
}
```

### quota.instance_type_offerings - PASS

```json
{
  "instance_types": [
    "c6i.32xlarge",
    "c6i.metal",
    "c6in.32xlarge",
    "c6in.metal",
    "c7i.48xlarge",
    "c7i.metal-48xl",
    "c8i.32xlarge",
    "c8i.48xlarge",
    "c8i.metal-48xl",
    "c8id.32xlarge",
    "c8id.48xlarge",
    "c8id.96xlarge",
    "c8id.metal-48xl",
    "c8id.metal-96xl",
    "i4i.2xlarge",
    "i4i.32xlarge",
    "i4i.metal",
    "i7i.2xlarge",
    "i7i.48xlarge",
    "i7i.metal-48xl",
    "i7ie.2xlarge",
    "i7ie.48xlarge",
    "i7ie.metal-48xl",
    "m6i.32xlarge",
    "m6i.metal",
    "m6id.32xlarge",
    "m6id.metal",
    "m6idn.32xlarge",
    "m6idn.metal",
    "m6in.32xlarge",
    "m6in.metal",
    "m7i.48xlarge",
    "m7i.metal-48xl",
    "m8i.32xlarge",
    "m8i.48xlarge",
    "m8i.metal-48xl",
    "m8id.32xlarge",
    "m8id.48xlarge",
    "m8id.96xlarge",
    "m8id.metal-48xl",
    "m8id.metal-96xl",
    "m8idb.32xlarge",
    "m8idb.48xlarge",
    "m8idb.96xlarge",
    "m8idn.32xlarge",
    "m8idn.48xlarge",
    "m8idn.96xlarge",
    "r5.2xlarge",
    "r5n.2xlarge",
    "r6i.2xlarge",
    "r6i.32xlarge",
    "r6i.metal",
    "r6id.2xlarge",
    "r6id.32xlarge",
    "r6id.metal",
    "r6idn.2xlarge",
    "r6idn.32xlarge",
    "r6idn.metal",
    "r6in.2xlarge",
    "r6in.32xlarge",
    "r6in.metal",
    "r7i.2xlarge",
    "r7i.48xlarge",
    "r7i.metal-48xl",
    "r7iz.2xlarge",
    "r7iz.32xlarge",
    "r7iz.metal-32xl",
    "r8i.2xlarge",
    "r8i.32xlarge",
    "r8i.48xlarge",
    "r8i.metal-48xl",
    "r8id.2xlarge",
    "r8id.32xlarge",
    "r8id.48xlarge",
    "r8id.96xlarge",
    "r8id.metal-48xl",
    "r8id.metal-96xl",
    "r8idb.2xlarge",
    "r8idb.32xlarge",
    "r8idb.48xlarge",
    "r8idb.96xlarge",
    "r8idn.2xlarge",
    "r8idn.32xlarge",
    "r8idn.48xlarge",
    "r8idn.96xlarge",
    "x2idn.32xlarge",
    "x2idn.metal",
    "x2iedn.2xlarge",
    "x2iedn.32xlarge",
    "x2iedn.metal",
    "x8i.2xlarge",
    "x8i.32xlarge",
    "x8i.48xlarge",
    "x8i.metal-48xl"
  ],
  "missing_instance_types": [],
  "offered_instance_types": [
    "c6i.32xlarge",
    "c6i.metal",
    "c6in.32xlarge",
    "c6in.metal",
    "c7i.48xlarge",
    "c7i.metal-48xl",
    "c8i.32xlarge",
    "c8i.48xlarge",
    "c8i.metal-48xl",
    "c8id.32xlarge",
    "c8id.48xlarge",
    "c8id.96xlarge",
    "c8id.metal-48xl",
    "c8id.metal-96xl",
    "i4i.2xlarge",
    "i4i.32xlarge",
    "i4i.metal",
    "i7i.2xlarge",
    "i7i.48xlarge",
    "i7i.metal-48xl",
    "i7ie.2xlarge",
    "i7ie.48xlarge",
    "i7ie.metal-48xl",
    "m6i.32xlarge",
    "m6i.metal",
    "m6id.32xlarge",
    "m6id.metal",
    "m6idn.32xlarge",
    "m6idn.metal",
    "m6in.32xlarge",
    "m6in.metal",
    "m7i.48xlarge",
    "m7i.metal-48xl",
    "m8i.32xlarge",
    "m8i.48xlarge",
    "m8i.metal-48xl",
    "m8id.32xlarge",
    "m8id.48xlarge",
    "m8id.96xlarge",
    "m8id.metal-48xl",
    "m8id.metal-96xl",
    "m8idb.32xlarge",
    "m8idb.48xlarge",
    "m8idb.96xlarge",
    "m8idn.32xlarge",
    "m8idn.48xlarge",
    "m8idn.96xlarge",
    "r5.2xlarge",
    "r5n.2xlarge",
    "r6i.2xlarge",
    "r6i.32xlarge",
    "r6i.metal",
    "r6id.2xlarge",
    "r6id.32xlarge",
    "r6id.metal",
    "r6idn.2xlarge",
    "r6idn.32xlarge",
    "r6idn.metal",
    "r6in.2xlarge",
    "r6in.32xlarge",
    "r6in.metal",
    "r7i.2xlarge",
    "r7i.48xlarge",
    "r7i.metal-48xl",
    "r7iz.2xlarge",
    "r7iz.32xlarge",
    "r7iz.metal-32xl",
    "r8i.2xlarge",
    "r8i.32xlarge",
    "r8i.48xlarge",
    "r8i.metal-48xl",
    "r8id.2xlarge",
    "r8id.32xlarge",
    "r8id.48xlarge",
    "r8id.96xlarge",
    "r8id.metal-48xl",
    "r8id.metal-96xl",
    "r8idb.2xlarge",
    "r8idb.32xlarge",
    "r8idb.48xlarge",
    "r8idb.96xlarge",
    "r8idn.2xlarge",
    "r8idn.32xlarge",
    "r8idn.48xlarge",
    "r8idn.96xlarge",
    "x2idn.32xlarge",
    "x2idn.metal",
    "x2iedn.2xlarge",
    "x2iedn.32xlarge",
    "x2iedn.metal",
    "x8i.2xlarge",
    "x8i.32xlarge",
    "x8i.48xlarge",
    "x8i.metal-48xl"
  ],
  "region_az": "us-west-2b"
}
```

### quota.spot_market_signal - PASS

```json
{
  "errors": {},
  "missing_price_history": [],
  "region_az": "us-west-2b",
  "spot_instance_types": [
    "c6i.32xlarge",
    "c6i.metal",
    "c6in.32xlarge",
    "c6in.metal",
    "c7i.48xlarge",
    "c7i.metal-48xl",
    "c8i.32xlarge",
    "c8i.48xlarge",
    "c8i.metal-48xl",
    "c8id.32xlarge",
    "c8id.48xlarge",
    "c8id.96xlarge",
    "c8id.metal-48xl",
    "c8id.metal-96xl",
    "i4i.2xlarge",
    "i4i.32xlarge",
    "i4i.metal",
    "i7i.2xlarge",
    "i7i.48xlarge",
    "i7i.metal-48xl",
    "i7ie.2xlarge",
    "i7ie.48xlarge",
    "i7ie.metal-48xl",
    "m6i.32xlarge",
    "m6i.metal",
    "m6id.32xlarge",
    "m6id.metal",
    "m6idn.32xlarge",
    "m6idn.metal",
    "m6in.32xlarge",
    "m6in.metal",
    "m7i.48xlarge",
    "m7i.metal-48xl",
    "m8i.32xlarge",
    "m8i.48xlarge",
    "m8i.metal-48xl",
    "m8id.32xlarge",
    "m8id.48xlarge",
    "m8id.96xlarge",
    "m8id.metal-48xl",
    "m8id.metal-96xl",
    "m8idb.32xlarge",
    "m8idb.48xlarge",
    "m8idb.96xlarge",
    "m8idn.32xlarge",
    "m8idn.48xlarge",
    "m8idn.96xlarge",
    "r5.2xlarge",
    "r5n.2xlarge",
    "r6i.2xlarge",
    "r6i.32xlarge",
    "r6i.metal",
    "r6id.2xlarge",
    "r6id.32xlarge",
    "r6id.metal",
    "r6idn.2xlarge",
    "r6idn.32xlarge",
    "r6idn.metal",
    "r6in.2xlarge",
    "r6in.32xlarge",
    "r6in.metal",
    "r7i.2xlarge",
    "r7i.48xlarge",
    "r7i.metal-48xl",
    "r7iz.2xlarge",
    "r7iz.32xlarge",
    "r7iz.metal-32xl",
    "r8i.2xlarge",
    "r8i.32xlarge",
    "r8i.48xlarge",
    "r8i.metal-48xl",
    "r8id.2xlarge",
    "r8id.32xlarge",
    "r8id.48xlarge",
    "r8id.96xlarge",
    "r8id.metal-48xl",
    "r8id.metal-96xl",
    "r8idb.2xlarge",
    "r8idb.32xlarge",
    "r8idb.48xlarge",
    "r8idb.96xlarge",
    "r8idn.2xlarge",
    "r8idn.32xlarge",
    "r8idn.48xlarge",
    "r8idn.96xlarge",
    "x2idn.32xlarge",
    "x2idn.metal",
    "x2iedn.2xlarge",
    "x2iedn.32xlarge",
    "x2iedn.metal",
    "x8i.2xlarge",
    "x8i.32xlarge",
    "x8i.48xlarge",
    "x8i.metal-48xl"
  ]
}
```

### quota.ebs.gp3_storage - PASS

```json
{
  "additional_slurm_accounting_gp3_gib": 0,
  "current_used_gib": 2875,
  "current_value": 52.0,
  "projected_used_gib": 3296,
  "quota_code": "L-7A658B76",
  "quota_name": "Storage for General Purpose SSD (gp3) volumes, in TiB",
  "remaining_after_required_gib": 49952,
  "required_new_gib": 421,
  "required_unit": "TiB",
  "required_value": 0.4111328125,
  "service_code": "ebs"
}
```

### quota.fsx.lustre_scratch_filesystems - PASS

```json
{
  "current_used": 3,
  "current_value": 100.0,
  "projected_used": 4,
  "quota_code": "L-C48231E5",
  "quota_name": "Lustre Scratch file systems",
  "remaining_after_required": 96,
  "required_new": 1,
  "required_unit": "file system",
  "required_value": 1,
  "service_code": "fsx"
}
```

### quota.fsx.lustre_scratch_storage - PASS

```json
{
  "current_used": 28800,
  "current_value": 100800.0,
  "projected_used": 33600,
  "quota_code": "L-AD2FC696",
  "quota_name": "Lustre Scratch storage capacity",
  "remaining_after_required": 67200,
  "required_new": 4800,
  "required_unit": "GiB",
  "required_value": 4800,
  "service_code": "fsx"
}
```
