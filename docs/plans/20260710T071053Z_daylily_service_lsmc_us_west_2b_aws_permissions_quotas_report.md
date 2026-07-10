# Daylily AWS Permissions And Quotas Validation Report

## Outcome

- Overall: **NOT SATISFIED**
- Satisfied checks: 50 / 77
- Unsatisfied or unknown checks: 27 / 77

## Context

- Mode: `all`
- AWS profile: `daylily-service-lsmc`
- Account: `108782052779`
- Principal: `arn:aws:iam::108782052779:user/daylily-service`
- Region: `us-west-2`
- Region AZ: `us-west-2b`
- Config: `config/daylily_ephemeral_cluster_template.yaml`

## Summary

- PASS: 50
- WARN: 5
- FAIL: 22

## Area Summary

| Area | Satisfied | Unknown | Not satisfied | Total | Outcome |
|---|---:|---:|---:|---:|---|
| Identity | 1 | 0 | 0 | 1 | SATISFIED |
| Permissions | 29 | 0 | 15 | 44 | NOT SATISFIED |
| Budget readiness | 0 | 0 | 1 | 1 | NOT SATISFIED |
| Cost-center readiness | 0 | 0 | 1 | 1 | NOT SATISFIED |
| CUR and cost readiness | 0 | 0 | 3 | 3 | NOT SATISFIED |
| Slurm accounting | 1 | 0 | 0 | 1 | SATISFIED |
| Quotas and headroom | 19 | 5 | 2 | 26 | NOT SATISFIED |

## Results Matrix

| Area | Check | Result | Status |
|---|---|---|---|
| Identity | `aws.identity` | SATISFIED | PASS |
| Permissions | `iam.policy.global` | SATISFIED | PASS |
| Permissions | `iam.policy.regional` | SATISFIED | PASS |
| Permissions | `iam.pcluster_omics_policy` | SATISFIED | PASS |
| Permissions | `ssm.session_document` | SATISFIED | PASS |
| Permissions | `iam.simulation.iam_core` | SATISFIED | PASS |
| Permissions | `iam.simulation.iam_pass_role` | SATISFIED | PASS |
| Permissions | `iam.simulation.cloudformation` | SATISFIED | PASS |
| Permissions | `iam.simulation.ec2_network_compute` | SATISFIED | PASS |
| Permissions | `iam.simulation.autoscaling_elb` | SATISFIED | PASS |
| Permissions | `iam.simulation.fsx` | SATISFIED | PASS |
| Permissions | `iam.simulation.s3` | SATISFIED | PASS |
| Permissions | `iam.simulation.ssm` | SATISFIED | PASS |
| Permissions | `iam.simulation.service_quotas` | NOT SATISFIED | FAIL |
| Permissions | `iam.simulation.budgets` | NOT SATISFIED | FAIL |
| Permissions | `iam.simulation.cost_explorer_reports` | SATISFIED | PASS |
| Permissions | `iam.simulation.dynamodb_cost_center_list` | SATISFIED | PASS |
| Permissions | `iam.simulation.dynamodb_cost_centers` | NOT SATISFIED | FAIL |
| Permissions | `iam.simulation.cur_data_exports_list` | NOT SATISFIED | FAIL |
| Permissions | `iam.simulation.cur_data_exports_table` | NOT SATISFIED | FAIL |
| Permissions | `iam.simulation.cur_data_exports_create` | NOT SATISFIED | FAIL |
| Permissions | `iam.simulation.cur_data_exports_resource` | NOT SATISFIED | FAIL |
| Permissions | `iam.simulation.cur_data_exports_update` | NOT SATISFIED | FAIL |
| Permissions | `iam.simulation.cur_legacy_dependency` | NOT SATISFIED | FAIL |
| Permissions | `iam.simulation.glue_cur_catalog` | NOT SATISFIED | FAIL |
| Permissions | `iam.simulation.athena_workgroup_list` | NOT SATISFIED | FAIL |
| Permissions | `iam.simulation.athena_cur_queries` | NOT SATISFIED | FAIL |
| Permissions | `iam.simulation.sns_list` | NOT SATISFIED | FAIL |
| Permissions | `iam.simulation.sns_topic` | NOT SATISFIED | FAIL |
| Permissions | `iam.simulation.scheduler` | SATISFIED | PASS |
| Permissions | `iam.simulation.lambda_imagebuilder` | SATISFIED | PASS |
| Permissions | `iam.simulation.cloudwatch_logs` | SATISFIED | PASS |
| Permissions | `iam.simulation.dynamodb_parallelcluster` | SATISFIED | PASS |
| Permissions | `iam.simulation.parallelcluster_backing_services` | SATISFIED | PASS |
| Permissions | `iam.simulation.cur_s3_bucket` | SATISFIED | PASS |
| Permissions | `iam.simulation.cur_s3_objects` | SATISFIED | PASS |
| Permissions | `iam.simulation.service_linked_role_spot` | SATISFIED | PASS |
| Permissions | `iam.simulation.service_linked_role_fsx` | SATISFIED | PASS |
| Permissions | `iam.simulation.service_linked_role_s3` | SATISFIED | PASS |
| Permissions | `iam.simulation.service_linked_role_imagebuilder` | SATISFIED | PASS |
| Permissions | `iam.simulation.service_linked_role_ec2` | SATISFIED | PASS |
| Permissions | `iam.simulation.service_linked_role_lambda` | SATISFIED | PASS |
| Permissions | `iam.simulation.service_linked_role_budgets` | SATISFIED | PASS |
| Permissions | `iam.runtime_cost_policy` | NOT SATISFIED | FAIL |
| Permissions | `iam.dragen_license_secret_policy` | SATISFIED | PASS |
| Budget readiness | `budget.readiness` | NOT SATISFIED | FAIL |
| Cost-center readiness | `cost_centers.registry_readiness` | NOT SATISFIED | FAIL |
| CUR and cost readiness | `cost_control.cur_export_readiness` | NOT SATISFIED | FAIL |
| CUR and cost readiness | `cost_control.cur_catalog_readiness` | NOT SATISFIED | FAIL |
| CUR and cost readiness | `cost_control.athena_readiness` | NOT SATISFIED | FAIL |
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
| Quotas and headroom | `quota.cur2_export_count` | UNKNOWN | WARN |
| Quotas and headroom | `quota.athena_active_dml` | UNKNOWN | WARN |
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
| Quotas and headroom | `quota.ebs.gp3_storage` | UNKNOWN | WARN |
| Quotas and headroom | `quota.fsx.lustre_scratch_filesystems` | UNKNOWN | WARN |
| Quotas and headroom | `quota.fsx.lustre_scratch_storage` | UNKNOWN | WARN |

## Required Admin Follow-Up

### iam.simulation.service_quotas - FAIL

Attach or update Daylily AWS policies so the principal can perform Service Quotas reads used by validation. Denied actions: servicequotas:ListAWSDefaultServiceQuotas, servicequotas:ListServiceQuotas

```json
{
  "actions": [
    "servicequotas:GetServiceQuota",
    "servicequotas:ListServiceQuotas",
    "servicequotas:ListAWSDefaultServiceQuotas"
  ],
  "decisions": [
    {
      "action": "servicequotas:GetServiceQuota",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "servicequotas:ListServiceQuotas",
      "decision": "implicitDeny",
      "resource": "*"
    },
    {
      "action": "servicequotas:ListAWSDefaultServiceQuotas",
      "decision": "implicitDeny",
      "resource": "*"
    }
  ],
  "denied_actions": [
    "servicequotas:ListAWSDefaultServiceQuotas",
    "servicequotas:ListServiceQuotas"
  ],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.budgets - FAIL

Attach or update Daylily AWS policies so the principal can perform Budgets and cost-tag enforcement. Denied actions: billing:GetBillingViewData

```json
{
  "actions": [
    "budgets:ViewBudget",
    "budgets:ModifyBudget",
    "billing:GetBillingViewData"
  ],
  "decisions": [
    {
      "action": "budgets:ViewBudget",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "budgets:ModifyBudget",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "billing:GetBillingViewData",
      "decision": "implicitDeny",
      "resource": "*"
    }
  ],
  "denied_actions": [
    "billing:GetBillingViewData"
  ],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.dynamodb_cost_centers - FAIL

Attach or update Daylily AWS policies so the principal can perform global cost-center registry and monthly usage snapshots. Denied actions: dynamodb:CreateTable, dynamodb:DescribeTable, dynamodb:GetItem, dynamodb:PutItem, dynamodb:Scan

```json
{
  "actions": [
    "dynamodb:DescribeTable",
    "dynamodb:CreateTable",
    "dynamodb:GetItem",
    "dynamodb:PutItem",
    "dynamodb:Scan"
  ],
  "decisions": [
    {
      "action": "dynamodb:DescribeTable",
      "decision": "implicitDeny",
      "resource": "arn:aws:dynamodb:us-west-2:108782052779:table/dayec-cost-centers"
    },
    {
      "action": "dynamodb:DescribeTable",
      "decision": "implicitDeny",
      "resource": "arn:aws:dynamodb:us-west-2:108782052779:table/dayec-cost-center-usage"
    },
    {
      "action": "dynamodb:CreateTable",
      "decision": "implicitDeny",
      "resource": "arn:aws:dynamodb:us-west-2:108782052779:table/dayec-cost-centers"
    },
    {
      "action": "dynamodb:CreateTable",
      "decision": "implicitDeny",
      "resource": "arn:aws:dynamodb:us-west-2:108782052779:table/dayec-cost-center-usage"
    },
    {
      "action": "dynamodb:GetItem",
      "decision": "implicitDeny",
      "resource": "arn:aws:dynamodb:us-west-2:108782052779:table/dayec-cost-centers"
    },
    {
      "action": "dynamodb:GetItem",
      "decision": "implicitDeny",
      "resource": "arn:aws:dynamodb:us-west-2:108782052779:table/dayec-cost-center-usage"
    },
    {
      "action": "dynamodb:PutItem",
      "decision": "implicitDeny",
      "resource": "arn:aws:dynamodb:us-west-2:108782052779:table/dayec-cost-centers"
    },
    {
      "action": "dynamodb:PutItem",
      "decision": "implicitDeny",
      "resource": "arn:aws:dynamodb:us-west-2:108782052779:table/dayec-cost-center-usage"
    },
    {
      "action": "dynamodb:Scan",
      "decision": "implicitDeny",
      "resource": "arn:aws:dynamodb:us-west-2:108782052779:table/dayec-cost-centers"
    },
    {
      "action": "dynamodb:Scan",
      "decision": "implicitDeny",
      "resource": "arn:aws:dynamodb:us-west-2:108782052779:table/dayec-cost-center-usage"
    }
  ],
  "denied_actions": [
    "dynamodb:CreateTable",
    "dynamodb:DescribeTable",
    "dynamodb:GetItem",
    "dynamodb:PutItem",
    "dynamodb:Scan"
  ],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "arn:aws:dynamodb:us-west-2:108782052779:table/dayec-cost-centers",
    "arn:aws:dynamodb:us-west-2:108782052779:table/dayec-cost-center-usage"
  ]
}
```

### iam.simulation.cur_data_exports_list - FAIL

Attach or update Daylily AWS policies so the principal can perform CUR 2.0 Data Exports discovery. Denied actions: bcm-data-exports:ListExports, bcm-data-exports:ListTables

```json
{
  "actions": [
    "bcm-data-exports:ListExports",
    "bcm-data-exports:ListTables"
  ],
  "decisions": [
    {
      "action": "bcm-data-exports:ListExports",
      "decision": "implicitDeny",
      "resource": "*"
    },
    {
      "action": "bcm-data-exports:ListTables",
      "decision": "implicitDeny",
      "resource": "*"
    }
  ],
  "denied_actions": [
    "bcm-data-exports:ListExports",
    "bcm-data-exports:ListTables"
  ],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.cur_data_exports_table - FAIL

Attach or update Daylily AWS policies so the principal can perform CUR 2.0 table schema inspection. Denied actions: bcm-data-exports:GetTable

```json
{
  "actions": [
    "bcm-data-exports:GetTable"
  ],
  "decisions": [
    {
      "action": "bcm-data-exports:GetTable",
      "decision": "implicitDeny",
      "resource": "arn:aws:bcm-data-exports:us-east-1:108782052779:table/COST_AND_USAGE_REPORT"
    }
  ],
  "denied_actions": [
    "bcm-data-exports:GetTable"
  ],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "arn:aws:bcm-data-exports:us-east-1:108782052779:table/COST_AND_USAGE_REPORT"
  ]
}
```

### iam.simulation.cur_data_exports_create - FAIL

Attach or update Daylily AWS policies so the principal can perform CUR 2.0 creation across the export and source table. Denied actions: bcm-data-exports:CreateExport

```json
{
  "actions": [
    "bcm-data-exports:CreateExport"
  ],
  "decisions": [
    {
      "action": "bcm-data-exports:CreateExport",
      "decision": "implicitDeny",
      "resource": "arn:aws:bcm-data-exports:us-east-1:108782052779:table/COST_AND_USAGE_REPORT"
    },
    {
      "action": "bcm-data-exports:CreateExport",
      "decision": "implicitDeny",
      "resource": "arn:aws:bcm-data-exports:us-east-1:108782052779:export/*"
    }
  ],
  "denied_actions": [
    "bcm-data-exports:CreateExport"
  ],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "arn:aws:bcm-data-exports:us-east-1:108782052779:export/*",
    "arn:aws:bcm-data-exports:us-east-1:108782052779:table/COST_AND_USAGE_REPORT"
  ]
}
```

### iam.simulation.cur_data_exports_resource - FAIL

Attach or update Daylily AWS policies so the principal can perform CUR 2.0 export inspection and tagging. Denied actions: bcm-data-exports:GetExport, bcm-data-exports:ListExecutions, bcm-data-exports:ListTagsForResource, bcm-data-exports:TagResource

```json
{
  "actions": [
    "bcm-data-exports:GetExport",
    "bcm-data-exports:ListExecutions",
    "bcm-data-exports:ListTagsForResource",
    "bcm-data-exports:TagResource"
  ],
  "decisions": [
    {
      "action": "bcm-data-exports:GetExport",
      "decision": "implicitDeny",
      "resource": "arn:aws:bcm-data-exports:us-east-1:108782052779:export/*"
    },
    {
      "action": "bcm-data-exports:ListExecutions",
      "decision": "implicitDeny",
      "resource": "arn:aws:bcm-data-exports:us-east-1:108782052779:export/*"
    },
    {
      "action": "bcm-data-exports:ListTagsForResource",
      "decision": "implicitDeny",
      "resource": "arn:aws:bcm-data-exports:us-east-1:108782052779:export/*"
    },
    {
      "action": "bcm-data-exports:TagResource",
      "decision": "implicitDeny",
      "resource": "arn:aws:bcm-data-exports:us-east-1:108782052779:export/*"
    }
  ],
  "denied_actions": [
    "bcm-data-exports:GetExport",
    "bcm-data-exports:ListExecutions",
    "bcm-data-exports:ListTagsForResource",
    "bcm-data-exports:TagResource"
  ],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "arn:aws:bcm-data-exports:us-east-1:108782052779:export/*"
  ]
}
```

### iam.simulation.cur_data_exports_update - FAIL

Attach or update Daylily AWS policies so the principal can perform CUR 2.0 updates across the export and source table. Denied actions: bcm-data-exports:UpdateExport

```json
{
  "actions": [
    "bcm-data-exports:UpdateExport"
  ],
  "decisions": [
    {
      "action": "bcm-data-exports:UpdateExport",
      "decision": "implicitDeny",
      "resource": "arn:aws:bcm-data-exports:us-east-1:108782052779:export/*"
    },
    {
      "action": "bcm-data-exports:UpdateExport",
      "decision": "implicitDeny",
      "resource": "arn:aws:bcm-data-exports:us-east-1:108782052779:table/COST_AND_USAGE_REPORT"
    }
  ],
  "denied_actions": [
    "bcm-data-exports:UpdateExport"
  ],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "arn:aws:bcm-data-exports:us-east-1:108782052779:export/*",
    "arn:aws:bcm-data-exports:us-east-1:108782052779:table/COST_AND_USAGE_REPORT"
  ]
}
```

### iam.simulation.cur_legacy_dependency - FAIL

Attach or update Daylily AWS policies so the principal can perform legacy CUR authorization required to create CUR 2.0 exports. Denied actions: cur:PutReportDefinition

```json
{
  "actions": [
    "cur:PutReportDefinition"
  ],
  "decisions": [
    {
      "action": "cur:PutReportDefinition",
      "decision": "implicitDeny",
      "resource": "*"
    }
  ],
  "denied_actions": [
    "cur:PutReportDefinition"
  ],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.glue_cur_catalog - FAIL

Attach or update Daylily AWS policies so the principal can perform Glue catalog used by hourly cost-center allocation. Denied actions: glue:CreateDatabase, glue:CreatePartition, glue:CreateTable, glue:GetDatabase, glue:GetPartition, glue:GetTable, glue:UpdateTable

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
  "decisions": [
    {
      "action": "glue:GetDatabase",
      "decision": "implicitDeny",
      "resource": "*"
    },
    {
      "action": "glue:CreateDatabase",
      "decision": "implicitDeny",
      "resource": "*"
    },
    {
      "action": "glue:GetTable",
      "decision": "implicitDeny",
      "resource": "*"
    },
    {
      "action": "glue:CreateTable",
      "decision": "implicitDeny",
      "resource": "*"
    },
    {
      "action": "glue:UpdateTable",
      "decision": "implicitDeny",
      "resource": "*"
    },
    {
      "action": "glue:GetPartition",
      "decision": "implicitDeny",
      "resource": "*"
    },
    {
      "action": "glue:CreatePartition",
      "decision": "implicitDeny",
      "resource": "*"
    }
  ],
  "denied_actions": [
    "glue:CreateDatabase",
    "glue:CreatePartition",
    "glue:CreateTable",
    "glue:GetDatabase",
    "glue:GetPartition",
    "glue:GetTable",
    "glue:UpdateTable"
  ],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.athena_workgroup_list - FAIL

Attach or update Daylily AWS policies so the principal can perform Athena workgroup discovery for regional DML headroom. Denied actions: athena:ListWorkGroups

```json
{
  "actions": [
    "athena:ListWorkGroups"
  ],
  "decisions": [
    {
      "action": "athena:ListWorkGroups",
      "decision": "implicitDeny",
      "resource": "*"
    }
  ],
  "denied_actions": [
    "athena:ListWorkGroups"
  ],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.athena_cur_queries - FAIL

Attach or update Daylily AWS policies so the principal can perform Athena queries used by hourly cost-center allocation. Denied actions: athena:BatchGetQueryExecution, athena:GetQueryExecution, athena:GetQueryResults, athena:GetWorkGroup, athena:ListQueryExecutions, athena:StartQueryExecution

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
  "decisions": [
    {
      "action": "athena:GetWorkGroup",
      "decision": "implicitDeny",
      "resource": "arn:aws:athena:us-east-1:108782052779:workgroup/*"
    },
    {
      "action": "athena:StartQueryExecution",
      "decision": "implicitDeny",
      "resource": "arn:aws:athena:us-east-1:108782052779:workgroup/*"
    },
    {
      "action": "athena:GetQueryExecution",
      "decision": "implicitDeny",
      "resource": "arn:aws:athena:us-east-1:108782052779:workgroup/*"
    },
    {
      "action": "athena:GetQueryResults",
      "decision": "implicitDeny",
      "resource": "arn:aws:athena:us-east-1:108782052779:workgroup/*"
    },
    {
      "action": "athena:ListQueryExecutions",
      "decision": "implicitDeny",
      "resource": "arn:aws:athena:us-east-1:108782052779:workgroup/*"
    },
    {
      "action": "athena:BatchGetQueryExecution",
      "decision": "implicitDeny",
      "resource": "arn:aws:athena:us-east-1:108782052779:workgroup/*"
    }
  ],
  "denied_actions": [
    "athena:BatchGetQueryExecution",
    "athena:GetQueryExecution",
    "athena:GetQueryResults",
    "athena:GetWorkGroup",
    "athena:ListQueryExecutions",
    "athena:StartQueryExecution"
  ],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "arn:aws:athena:us-east-1:108782052779:workgroup/*"
  ]
}
```

### iam.simulation.sns_list - FAIL

Attach or update Daylily AWS policies so the principal can perform SNS account-level topic and subscription discovery. Denied actions: sns:ListSubscriptions, sns:ListTopics

```json
{
  "actions": [
    "sns:ListTopics",
    "sns:ListSubscriptions"
  ],
  "decisions": [
    {
      "action": "sns:ListTopics",
      "decision": "implicitDeny",
      "resource": "arn:${Partition}:sns:$region:108782052779:*"
    },
    {
      "action": "sns:ListSubscriptions",
      "decision": "implicitDeny",
      "resource": "arn:${Partition}:sns:$region:108782052779:*"
    }
  ],
  "denied_actions": [
    "sns:ListSubscriptions",
    "sns:ListTopics"
  ],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.sns_topic - FAIL

Attach or update Daylily AWS policies so the principal can perform SNS topic integration. Denied actions: sns:CreateTopic, sns:ListSubscriptionsByTopic, sns:Unsubscribe

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
  "decisions": [
    {
      "action": "sns:CreateTopic",
      "decision": "implicitDeny",
      "resource": "arn:aws:sns:us-west-2:108782052779:daylily-majors-cluster-heartbeat"
    },
    {
      "action": "sns:ListSubscriptionsByTopic",
      "decision": "implicitDeny",
      "resource": "arn:aws:sns:us-west-2:108782052779:daylily-majors-cluster-heartbeat"
    },
    {
      "action": "sns:GetTopicAttributes",
      "decision": "allowed",
      "resource": "arn:aws:sns:us-west-2:108782052779:daylily-majors-cluster-heartbeat"
    },
    {
      "action": "sns:SetTopicAttributes",
      "decision": "allowed",
      "resource": "arn:aws:sns:us-west-2:108782052779:daylily-majors-cluster-heartbeat"
    },
    {
      "action": "sns:Subscribe",
      "decision": "allowed",
      "resource": "arn:aws:sns:us-west-2:108782052779:daylily-majors-cluster-heartbeat"
    },
    {
      "action": "sns:Unsubscribe",
      "decision": "implicitDeny",
      "resource": "arn:aws:sns:us-west-2:108782052779:daylily-majors-cluster-heartbeat"
    },
    {
      "action": "sns:Publish",
      "decision": "allowed",
      "resource": "arn:aws:sns:us-west-2:108782052779:daylily-majors-cluster-heartbeat"
    },
    {
      "action": "sns:DeleteTopic",
      "decision": "allowed",
      "resource": "arn:aws:sns:us-west-2:108782052779:daylily-majors-cluster-heartbeat"
    }
  ],
  "denied_actions": [
    "sns:CreateTopic",
    "sns:ListSubscriptionsByTopic",
    "sns:Unsubscribe"
  ],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "arn:aws:sns:us-west-2:108782052779:daylily-majors-cluster-heartbeat"
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

Grant DynamoDB DescribeTable access to both DayEC cost-center tables.

```json
{
  "error": "An error occurred (AccessDeniedException) when calling the DescribeTable operation: User: arn:aws:iam::108782052779:user/daylily-service is not authorized to perform: dynamodb:DescribeTable on resource: arn:aws:dynamodb:us-west-2:108782052779:table/dayec-cost-centers because no identity-based policy allows the dynamodb:DescribeTable action",
  "home_region": "us-west-2",
  "tables": {}
}
```

### cost_control.cur_export_readiness - FAIL

Grant read access to the CUR S3 bucket and BCM Data Exports, then rerun validation. The validator does not create or update these resources.

```json
{
  "billing_region": "us-east-1",
  "bucket": "dayec-cur-108782052779-us-east-1",
  "bucket_policy_valid": true,
  "bucket_region": "us-east-1",
  "cluster_tag_key": "user_parallelcluster_cluster_name",
  "error": "An error occurred (AccessDeniedException) when calling the ListExports operation: User: arn:aws:iam::108782052779:user/daylily-service is not authorized to perform: bcm-data-exports:ListExports on resource: arn:aws:bcm-data-exports:us-east-1:108782052779:/ListExports because no identity-based policy allows the bcm-data-exports:ListExports action",
  "export_arn": "",
  "export_definition_matches": false,
  "export_name": "dayec-cur2-hourly",
  "export_status": {},
  "invalid": [],
  "latest_execution": null,
  "missing": [],
  "schema_columns": []
}
```

### cost_control.cur_catalog_readiness - FAIL

Grant Glue GetDatabase, GetTable, and GetPartition for the DayEC CUR catalog.

```json
{
  "billing_period": "2026-07",
  "database": "dayec_cur",
  "database_exists": false,
  "error": "An error occurred (AccessDeniedException) when calling the GetTable operation: User: arn:aws:iam::108782052779:user/daylily-service is not authorized to perform: bcm-data-exports:GetTable on resource: arn:aws:bcm-data-exports:us-east-1:108782052779:table/COST_AND_USAGE_REPORT because no identity-based policy allows the bcm-data-exports:GetTable action",
  "invalid": [],
  "managed": false,
  "missing": [],
  "partition_contract_matches": false,
  "partition_exists": false,
  "region": "us-east-1",
  "schema_columns": [],
  "table": "cur2_hourly",
  "table_contract_matches": false,
  "table_exists": false
}
```

### cost_control.athena_readiness - FAIL

Grant athena:GetWorkGroup on the primary workgroup. No query was started.

```json
{
  "error": "An error occurred (AccessDeniedException) when calling the GetWorkGroup operation: You are not authorized to perform: athena:GetWorkGroup on the resource. After your AWS administrator or you have updated your permissions, please try again.",
  "query_started": false,
  "region": "us-east-1",
  "workgroup": "primary"
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

### quota.cur2_export_count - WARN

Grant BCM Data Exports ListExports and GetExport access.

```json
{
  "error": "An error occurred (AccessDeniedException) when calling the ListExports operation: User: arn:aws:iam::108782052779:user/daylily-service is not authorized to perform: bcm-data-exports:ListExports on resource: arn:aws:bcm-data-exports:us-east-1:108782052779:/ListExports because no identity-based policy allows the bcm-data-exports:ListExports action",
  "quota": 5,
  "region": "us-east-1",
  "source": "https://docs.aws.amazon.com/cur/latest/userguide/dataexports-quotas.html"
}
```

### quota.athena_active_dml - WARN

Grant athena:ListWorkGroups, athena:ListQueryExecutions, and athena:BatchGetQueryExecution across regional workgroups so active DML headroom can be measured.

```json
{
  "current_used": null,
  "current_value": 200.0,
  "error": "An error occurred (AccessDeniedException) when calling the ListWorkGroups operation: User: arn:aws:iam::108782052779:user/daylily-service is not authorized to perform: athena:ListWorkGroups because no identity-based policy allows the athena:ListWorkGroups action",
  "quota_code": "L-FC5F6546",
  "region": "us-east-1",
  "required_new": 1,
  "service_code": "athena",
  "workgroups_inspected": []
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

### quota.ebs.gp3_storage - WARN

Unable to list Service Quotas for ebs. Grant servicequotas:ListServiceQuotas and servicequotas:ListAWSDefaultServiceQuotas, then verify EBS gp3 regional storage manually.

```json
{
  "additional_slurm_accounting_gp3_gib": 0,
  "current_used_gib": 2875,
  "error": "An error occurred (AccessDeniedException) when calling the ListServiceQuotas operation: User: arn:aws:iam::108782052779:user/daylily-service is not authorized to perform: servicequotas:ListServiceQuotas because no identity-based policy allows the servicequotas:ListServiceQuotas action",
  "quota_name_fragments": [
    "Storage for General Purpose SSD (gp3) volumes"
  ],
  "required_new_gib": 421,
  "required_unit": "TiB",
  "required_value": 0.4111328125,
  "service_code": "ebs"
}
```

### quota.fsx.lustre_scratch_filesystems - WARN

Unable to list Service Quotas for fsx. Grant servicequotas:ListServiceQuotas and servicequotas:ListAWSDefaultServiceQuotas, then verify FSx for Lustre file system count manually.

```json
{
  "current_used": 3,
  "error": "An error occurred (AccessDeniedException) when calling the ListServiceQuotas operation: User: arn:aws:iam::108782052779:user/daylily-service is not authorized to perform: servicequotas:ListServiceQuotas because no identity-based policy allows the servicequotas:ListServiceQuotas action",
  "quota_name_fragments": [
    "Lustre Scratch file systems"
  ],
  "required_new": 1,
  "required_unit": "file system",
  "required_value": 1,
  "service_code": "fsx"
}
```

### quota.fsx.lustre_scratch_storage - WARN

Unable to list Service Quotas for fsx. Grant servicequotas:ListServiceQuotas and servicequotas:ListAWSDefaultServiceQuotas, then verify FSx for Lustre storage capacity manually.

```json
{
  "current_used": 28800,
  "error": "An error occurred (AccessDeniedException) when calling the ListServiceQuotas operation: User: arn:aws:iam::108782052779:user/daylily-service is not authorized to perform: servicequotas:ListServiceQuotas because no identity-based policy allows the servicequotas:ListServiceQuotas action",
  "quota_name_fragments": [
    "Lustre Scratch storage capacity"
  ],
  "required_new": 4800,
  "required_unit": "GiB",
  "required_value": 4800,
  "service_code": "fsx"
}
```

## Passing Validation Checks

### aws.identity - PASS

```json
{
  "account_id": "108782052779",
  "caller_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "profile": "daylily-service-lsmc",
  "region": "us-west-2",
  "region_az": "us-west-2b"
}
```

### iam.policy.global - PASS

```json
{
  "policy": "DaylilyGlobalEClusterPolicy",
  "user": "daylily-service"
}
```

### iam.policy.regional - PASS

```json
{
  "policy": "DaylilyRegionalEClusterPolicy-us-west-2",
  "user": "daylily-service"
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

### iam.simulation.iam_core - PASS

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
  "decisions": [
    {
      "action": "iam:ListPolicies",
      "decision": "allowed",
      "resource": "arn:aws:iam::108782052779:policy/"
    },
    {
      "action": "iam:GetPolicy",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "iam:GetPolicyVersion",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "iam:ListAttachedUserPolicies",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "iam:ListGroupsForUser",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "iam:ListAttachedGroupPolicies",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "iam:ListRoles",
      "decision": "allowed",
      "resource": "arn:aws:iam::108782052779:role/"
    },
    {
      "action": "iam:ListInstanceProfiles",
      "decision": "allowed",
      "resource": "arn:aws:iam::108782052779:instance-profile/"
    },
    {
      "action": "iam:GetAccountSummary",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "iam:GetRole",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "iam:CreateRole",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "iam:DeleteRole",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "iam:CreateInstanceProfile",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "iam:DeleteInstanceProfile",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "iam:AddRoleToInstanceProfile",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "iam:RemoveRoleFromInstanceProfile",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "iam:AttachRolePolicy",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "iam:DetachRolePolicy",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "iam:PutRolePolicy",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "iam:DeleteRolePolicy",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "iam:TagRole",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "iam:UntagRole",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "iam:SimulatePrincipalPolicy",
      "decision": "allowed",
      "resource": "*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.iam_pass_role - PASS

```json
{
  "actions": [
    "iam:PassRole"
  ],
  "decisions": [
    {
      "action": "iam:PassRole",
      "decision": "allowed",
      "resource": "arn:aws:iam::108782052779:role/daylily-validation-role"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "arn:aws:iam::108782052779:role/daylily-validation-role"
  ]
}
```

### iam.simulation.cloudformation - PASS

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
  "decisions": [
    {
      "action": "cloudformation:DescribeStacks",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "cloudformation:ListStacks",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "cloudformation:CreateStack",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "cloudformation:UpdateStack",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "cloudformation:DeleteStack",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "cloudformation:DescribeStackEvents",
      "decision": "allowed",
      "resource": "*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.ec2_network_compute - PASS

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
  "decisions": [
    {
      "action": "ec2:DescribeAvailabilityZones",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:DescribeInstanceTypes",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:DescribeInstanceTypeOfferings",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:DescribeSpotPriceHistory",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:DescribeSpotInstanceRequests",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:DescribeSubnets",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:DescribeVpcs",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:DescribeInstances",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:DescribeImages",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:DescribeSecurityGroups",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:DescribeNetworkInterfaces",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:DescribeRouteTables",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:DescribeVolumes",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:DescribeAddresses",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:DescribeInternetGateways",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:DescribeNatGateways",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:CreateVpc",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:DeleteVpc",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:CreateSubnet",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:DeleteSubnet",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:CreateInternetGateway",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:AttachInternetGateway",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:DetachInternetGateway",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:CreateNatGateway",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:DeleteNatGateway",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:AllocateAddress",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:ReleaseAddress",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:CreateSecurityGroup",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:AuthorizeSecurityGroupIngress",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:AuthorizeSecurityGroupEgress",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:RunInstances",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:TerminateInstances",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:CreateTags",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ec2:DeleteTags",
      "decision": "allowed",
      "resource": "*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.autoscaling_elb - PASS

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
  "decisions": [
    {
      "action": "autoscaling:DescribeAutoScalingGroups",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "autoscaling:CreateAutoScalingGroup",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "autoscaling:DeleteAutoScalingGroup",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "elasticloadbalancing:DescribeLoadBalancers",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "elasticloadbalancing:CreateLoadBalancer",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "elasticloadbalancing:DeleteLoadBalancer",
      "decision": "allowed",
      "resource": "*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.fsx - PASS

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
  "decisions": [
    {
      "action": "fsx:DescribeFileSystems",
      "decision": "allowed",
      "resource": "arn:${Partition}:fsx:${Region}:${Account}:file-system/*"
    },
    {
      "action": "fsx:CreateFileSystem",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "fsx:DeleteFileSystem",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "fsx:CreateDataRepositoryAssociation",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "fsx:DescribeDataRepositoryAssociations",
      "decision": "allowed",
      "resource": "arn:${Partition}:fsx:${Region}:${Account}:association/*"
    },
    {
      "action": "fsx:DeleteDataRepositoryAssociation",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "fsx:CreateDataRepositoryTask",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "fsx:DescribeDataRepositoryTasks",
      "decision": "allowed",
      "resource": "arn:${Partition}:fsx:${Region}:${Account}:task/*"
    },
    {
      "action": "fsx:TagResource",
      "decision": "allowed",
      "resource": "*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.s3 - PASS

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
  "decisions": [
    {
      "action": "s3:ListAllMyBuckets",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "s3:GetBucketLocation",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "s3:CreateBucket",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "s3:GetBucketPolicy",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "s3:PutBucketPolicy",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "s3:ListBucket",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "s3:GetObject",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "s3:PutObject",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "s3:DeleteObject",
      "decision": "allowed",
      "resource": "*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.ssm - PASS

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
  "decisions": [
    {
      "action": "ssm:GetDocument",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ssm:GetParameter",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ssm:GetParameters",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ssm:DescribeInstanceInformation",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ssm:StartSession",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ssm:TerminateSession",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ssm:DescribeSessions",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ssm:SendCommand",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ssm:GetCommandInvocation",
      "decision": "allowed",
      "resource": "*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.cost_explorer_reports - PASS

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
  "decisions": [
    {
      "action": "ce:GetCostAndUsage",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ce:GetCostAndUsageWithResources",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ce:GetDimensionValues",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ce:GetTags",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ce:ListCostAllocationTags",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ce:DescribeCostCategoryDefinition",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ce:ListCostCategoryDefinitions",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "tag:GetResources",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "tag:GetTagKeys",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "tag:GetTagValues",
      "decision": "allowed",
      "resource": "*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.dynamodb_cost_center_list - PASS

```json
{
  "actions": [
    "dynamodb:ListTables"
  ],
  "decisions": [
    {
      "action": "dynamodb:ListTables",
      "decision": "allowed",
      "resource": "arn:aws:dynamodb:${Region}:${Account}:table/*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.scheduler - PASS

```json
{
  "actions": [
    "scheduler:CreateSchedule",
    "scheduler:GetSchedule",
    "scheduler:ListSchedules",
    "scheduler:UpdateSchedule",
    "scheduler:DeleteSchedule"
  ],
  "decisions": [
    {
      "action": "scheduler:CreateSchedule",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "scheduler:GetSchedule",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "scheduler:ListSchedules",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "scheduler:UpdateSchedule",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "scheduler:DeleteSchedule",
      "decision": "allowed",
      "resource": "*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.lambda_imagebuilder - PASS

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
  "decisions": [
    {
      "action": "lambda:CreateFunction",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "lambda:GetFunction",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "lambda:ListFunctions",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "lambda:DeleteFunction",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "lambda:AddPermission",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "lambda:RemovePermission",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "imagebuilder:ListImages",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "imagebuilder:GetImage",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "imagebuilder:CreateImage",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "imagebuilder:DeleteImage",
      "decision": "allowed",
      "resource": "*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.cloudwatch_logs - PASS

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
  "decisions": [
    {
      "action": "cloudwatch:PutMetricData",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "cloudwatch:DescribeAlarms",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "cloudwatch:PutMetricAlarm",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "cloudwatch:DeleteAlarms",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "logs:CreateLogGroup",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "logs:CreateLogStream",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "logs:DescribeLogGroups",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "logs:PutLogEvents",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "logs:DeleteLogGroup",
      "decision": "allowed",
      "resource": "*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.dynamodb_parallelcluster - PASS

```json
{
  "actions": [
    "dynamodb:CreateTable",
    "dynamodb:DescribeTable",
    "dynamodb:UpdateTable",
    "dynamodb:DeleteTable",
    "dynamodb:TagResource"
  ],
  "decisions": [
    {
      "action": "dynamodb:CreateTable",
      "decision": "allowed",
      "resource": "arn:aws:dynamodb:us-west-2:108782052779:table/parallelcluster-validation"
    },
    {
      "action": "dynamodb:DescribeTable",
      "decision": "allowed",
      "resource": "arn:aws:dynamodb:us-west-2:108782052779:table/parallelcluster-validation"
    },
    {
      "action": "dynamodb:UpdateTable",
      "decision": "allowed",
      "resource": "arn:aws:dynamodb:us-west-2:108782052779:table/parallelcluster-validation"
    },
    {
      "action": "dynamodb:DeleteTable",
      "decision": "allowed",
      "resource": "arn:aws:dynamodb:us-west-2:108782052779:table/parallelcluster-validation"
    },
    {
      "action": "dynamodb:TagResource",
      "decision": "allowed",
      "resource": "arn:aws:dynamodb:us-west-2:108782052779:table/parallelcluster-validation"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "arn:aws:dynamodb:us-west-2:108782052779:table/parallelcluster-validation"
  ]
}
```

### iam.simulation.parallelcluster_backing_services - PASS

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
  "decisions": [
    {
      "action": "tag:GetResources",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "tag:TagResources",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "tag:UntagResources",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "route53:ListHostedZones",
      "decision": "allowed",
      "resource": "arn:aws:route53::108782052779:hostedzone/*"
    },
    {
      "action": "route53:ChangeResourceRecordSets",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "apigateway:GET",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "apigateway:POST",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "apigateway:DELETE",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "secretsmanager:CreateSecret",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "secretsmanager:DescribeSecret",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "secretsmanager:ListSecrets",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "secretsmanager:GetSecretValue",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "secretsmanager:GetRandomPassword",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "secretsmanager:PutSecretValue",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "secretsmanager:UpdateSecret",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "secretsmanager:TagResource",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "secretsmanager:DeleteSecret",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ecr:GetAuthorizationToken",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ecr:DescribeRepositories",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ecr:CreateRepository",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "ecr:DeleteRepository",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "cognito-idp:ListUserPools",
      "decision": "allowed",
      "resource": "*"
    },
    {
      "action": "elasticfilesystem:DescribeFileSystems",
      "decision": "allowed",
      "resource": "*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.cur_s3_bucket - PASS

```json
{
  "actions": [
    "s3:ListBucket",
    "s3:GetBucketLocation",
    "s3:CreateBucket",
    "s3:GetBucketPolicy",
    "s3:PutBucketPolicy"
  ],
  "decisions": [
    {
      "action": "s3:ListBucket",
      "decision": "allowed",
      "resource": "arn:aws:s3:::dayec-cur-108782052779-us-east-1"
    },
    {
      "action": "s3:GetBucketLocation",
      "decision": "allowed",
      "resource": "arn:aws:s3:::dayec-cur-108782052779-us-east-1"
    },
    {
      "action": "s3:CreateBucket",
      "decision": "allowed",
      "resource": "arn:aws:s3:::dayec-cur-108782052779-us-east-1"
    },
    {
      "action": "s3:GetBucketPolicy",
      "decision": "allowed",
      "resource": "arn:aws:s3:::dayec-cur-108782052779-us-east-1"
    },
    {
      "action": "s3:PutBucketPolicy",
      "decision": "allowed",
      "resource": "arn:aws:s3:::dayec-cur-108782052779-us-east-1"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "arn:aws:s3:::dayec-cur-108782052779-us-east-1"
  ]
}
```

### iam.simulation.cur_s3_objects - PASS

```json
{
  "actions": [
    "s3:GetObject",
    "s3:PutObject"
  ],
  "decisions": [
    {
      "action": "s3:GetObject",
      "decision": "allowed",
      "resource": "arn:aws:s3:::dayec-cur-108782052779-us-east-1/dayec-cur/*"
    },
    {
      "action": "s3:PutObject",
      "decision": "allowed",
      "resource": "arn:aws:s3:::dayec-cur-108782052779-us-east-1/dayec-cur/*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "arn:aws:s3:::dayec-cur-108782052779-us-east-1/dayec-cur/*"
  ]
}
```

### iam.simulation.service_linked_role_spot - PASS

```json
{
  "actions": [
    "iam:CreateServiceLinkedRole"
  ],
  "decisions": [
    {
      "action": "iam:CreateServiceLinkedRole",
      "decision": "allowed",
      "resource": "*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.service_linked_role_fsx - PASS

```json
{
  "actions": [
    "iam:CreateServiceLinkedRole"
  ],
  "decisions": [
    {
      "action": "iam:CreateServiceLinkedRole",
      "decision": "allowed",
      "resource": "*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.service_linked_role_s3 - PASS

```json
{
  "actions": [
    "iam:CreateServiceLinkedRole"
  ],
  "decisions": [
    {
      "action": "iam:CreateServiceLinkedRole",
      "decision": "allowed",
      "resource": "*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.service_linked_role_imagebuilder - PASS

```json
{
  "actions": [
    "iam:CreateServiceLinkedRole"
  ],
  "decisions": [
    {
      "action": "iam:CreateServiceLinkedRole",
      "decision": "allowed",
      "resource": "*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.service_linked_role_ec2 - PASS

```json
{
  "actions": [
    "iam:CreateServiceLinkedRole"
  ],
  "decisions": [
    {
      "action": "iam:CreateServiceLinkedRole",
      "decision": "allowed",
      "resource": "*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.service_linked_role_lambda - PASS

```json
{
  "actions": [
    "iam:CreateServiceLinkedRole"
  ],
  "decisions": [
    {
      "action": "iam:CreateServiceLinkedRole",
      "decision": "allowed",
      "resource": "*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.simulation.service_linked_role_budgets - PASS

```json
{
  "actions": [
    "iam:CreateServiceLinkedRole"
  ],
  "decisions": [
    {
      "action": "iam:CreateServiceLinkedRole",
      "decision": "allowed",
      "resource": "*"
    }
  ],
  "denied_actions": [],
  "principal_arn": "arn:aws:iam::108782052779:user/daylily-service",
  "resources": [
    "*"
  ]
}
```

### iam.dragen_license_secret_policy - PASS

```json
{
  "configured": false,
  "secret_value_read": false
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
