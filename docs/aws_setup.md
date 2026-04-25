# AWS Setup

This is the account and operator prerequisite guide for the current supported Daylily flow.

## 1. AWS Profile And Credential Model

Daylily expects a named AWS CLI profile and uses standard AWS SDK/CLI resolution. The simplest supported pattern is:

```bash
export AWS_PROFILE=daylily-service-lsmc
export AWS_REGION=us-west-2
```

Sanity check:

```bash
aws sts get-caller-identity --profile "$AWS_PROFILE"
```

If that fails, stop there. Nothing in Daylily will work until the base AWS identity is correct.

## 2. IAM Expectations

The current code checks for:

- a global Daylily policy attachment
- a regional Daylily policy attachment
- the presence or creation of the `pcluster-omics-analysis` policy

The current bootstrap helpers for account administrators are:

- `daylily_ec/resources/payload/bin/admin/daylily_ephemeral_cluster_bootstrap_global.sh`
- `daylily_ec/resources/payload/bin/admin/daylily_ephemeral_cluster_bootstrap_region.sh`

The global bootstrap helper creates or updates `DaylilyGlobalEClusterPolicy` and is intended to be run once per account. The regional bootstrap helper creates or updates `DaylilyRegionalEClusterPolicy-<region>` and is intended to be run once per target region.

The current policy surface allows the Daylily operator flow to use:

- STS identity inspection
- IAM inspection and bootstrap
- Service Quotas reads
- EC2/VPC inspection
- CloudFormation
- FSx
- S3
- Budgets and related tagging
- Systems Manager
- ParallelCluster-related services

## 3. IAM Group Model

The packaged admin helpers are group-oriented. The intended model is:

1. attach Daylily managed policies to an IAM group
2. ensure the operator IAM user is a member of that group

That keeps account setup cleaner than attaching everything directly to individual users.

## 4. Service-Linked Role Requirements

The Daylily bootstrap policy allows creation of service-linked roles required by the current workflow. In practice, your AWS organization must permit the account to create or use the service-linked roles needed by:

- Spot
- FSx
- the FSx S3 data-source integration
- image builder related paths used by ParallelCluster
- EC2 and Lambda support paths referenced by the bootstrap policy

If your organization blocks service-linked role creation, pre-create or delegate them before running Daylily.

## 5. Session Manager Requirements

The supported connect path requires the regional document:

```text
SSM-SessionManagerRunShell
```

The repo hard-fails unless that document is configured to:

- set `runAsEnabled` to true
- set `runAsDefaultUser` to `ubuntu`
- change directory to `/home/ubuntu` and source a login shell for `ubuntu`
  through `shellProfile.linux`

The supported shell profile is:

```text
cd /home/ubuntu && exec bash -l
```

Equivalent forms that `cd` to the ubuntu home directory before starting the
login shell are also accepted. A bare `exec bash -l` is not sufficient because
Session Manager starts in the SSM agent working directory.

If this document is missing or misconfigured, `daylily-ec headnode connect` and other supported SSM flows will fail on purpose.

## 6. Region, Availability Zone, And Bucket Alignment

Choose:

- one target region
- one target AZ in that region
- one reference bucket in that region

The bucket is not just an arbitrary storage destination. It is the durable backing store for the FSx filesystem and the place exports return to.

Sanity checks:

```bash
aws s3 ls "s3://your-reference-bucket" --profile "$AWS_PROFILE" --region "$REGION"
daylily-ec preflight --profile "$AWS_PROFILE" --region-az "$REGION_AZ" --config "$DAY_EX_CFG"
```

## 7. Quotas The Repo Checks

The current quota preflight checks these recommended minimums:

- On-Demand vCPU Max: 20
- Spot vCPU Max: 192
- VPCs: 5
- Elastic IPs: 5
- NAT Gateways: 5
- Internet Gateways: 5

Spot demand is computed from the cluster config `max_count_*` values. If the requested spot capacity is greater than or equal to the quota, preflight warns or fails depending on mode.

## 8. Network And Region Policy Expectations

Preflight also validates baseline network resources and region policy selection. The current flow expects the repo to be able to discover or create what it needs rather than relying on an older manual bootstrap script.

Operationally, that means:

- do not assume the account is "ready" just because one cluster worked once
- rerun preflight when moving regions or changing configs

## 9. Local Toolchain In DAY-EC

The supported local shell should provide:

- `daylily-ec`
- `aws`
- `pcluster`
- `session-manager-plugin`
- `jq`
- `yq`
- `rclone`
- `node`

The supported repo checkout path is:

```bash
source ./activate
```

Verify:

```bash
daylily-ec runtime status
aws --version
pcluster version
session-manager-plugin
```

## 10. First Real Validation

After account/bootstrap work is complete, the next command should be:

```bash
daylily-ec preflight \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG"
```

Treat preflight as the authoritative setup validator. If it fails, fix the reported setup gap before attempting create.
