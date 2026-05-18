# AWS Setup

This is the account and operator prerequisite guide for current DayEC.

## Profile And Region

Use an explicit named profile and region:

```bash
export AWS_PROFILE=daylily-service-lsmc
export AWS_REGION=us-west-2
aws sts get-caller-identity --profile "$AWS_PROFILE"
```

If the identity check fails, fix AWS credentials before running DayEC.

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
- set default user to `ubuntu`
- start in `/home/ubuntu`
- launch a bash login shell
- disable terminal software flow control before the shell starts

Supported shell profile shape:

```text
cd /home/ubuntu && { stty -ixon -ixoff 2>/dev/null || true; exec bash -l; }
```

`dyec headnode connect` and SSM-backed command helpers fail if this surface is wrong.

## S3 And FSx Layout

Choose:

- one target AWS region
- one target AZ in that region
- one reference bucket in that region
- one or more run-data buckets/prefixes, preferably in the same region
- one analysis-result bucket/prefix for exports

S3 buckets are regional, not AZ-scoped. Co-locate buckets and FSx in the same AWS region for the expected low-latency, lower-cost path. Cross-region reads or exports are possible only if AWS permissions and network paths allow them, and should be treated as slower and more expensive.

Current FSx DRA strategy:

- reference data DRA: `<reference-bucket>/data/` to `/fsx/data`
- run input DRA: selected S3 run prefix to `/fsx/run_dir_mounts/<mount_id>`
- export DRA: one completed `/fsx/analysis_results/ubuntu/<analysis_dir>` to the requested S3 analysis destination

The reference bucket is not automatically the export bucket. `dyec export` takes an explicit `--destination-s3-uri`.

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

`aws validate` is read-only and intended for account readiness checks. `preflight` is the final operator validator before create.

## Quotas

Quota validation covers the rendered cluster shape and baseline resources, including:

- On-Demand and Spot vCPU demand
- requested instance type offerings in the target AZ
- VPC, subnet, Elastic IP, NAT, and Internet Gateway headroom
- EBS gp3 storage
- FSx for Lustre capacity
- visible Spot price signal

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
