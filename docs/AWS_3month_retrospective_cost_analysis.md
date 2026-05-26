# AWS 90-Day Retrospective Cost Analysis

Generated: 2026-05-21  
AWS profile: `lsmc`  
Account: `108782052779`  
Window: 2026-02-20 through 2026-05-20 inclusive (`Cost Explorer End=2026-05-21`)  
Metric: `UnblendedCost`  

No AWS mutations were performed. Tagging, stopping, deleting, lifecycle changes, and cleanup actions below are recommendations only.

## Executive Summary

The account spent **$35,043.24** in the 90-day window. The cost profile is concentrated: **us-west-2 accounts for $31,764.92 / 90.6%**, and the top five services account for about **$33,116 / 94.5%**.

| Driver | 90-day spend | Share |
|---|---:|---:|
| Amazon EC2 Compute | $15,308.47 | 43.7% |
| Amazon FSx | $9,562.84 | 27.3% |
| Amazon S3 | $4,531.77 | 12.9% |
| EC2 - Other | $2,190.19 | 6.2% |
| RDS | $1,522.72 | 4.3% |

The clearest savings targets are:

1. **Large active FSx Lustre filesystems**: `fs-01c4180aab049f24c` (`XL-pilot`, 14,400 GiB) and `fs-017ab7a7cdbf44c54` (`dra-enabled`, 12,000 GiB) are still `AVAILABLE`; together they represent the biggest live run-rate risk.
2. **Unattached EBS gp3 volumes**: four 421 GiB available volumes are direct cleanup candidates after ownership confirmation.
3. **NAT gateways**: ten NAT gateways are live across the scanned regions; several are only CloudFormation-tagged or missing project tags.
4. **S3 lifecycle/tagging gaps**: major analysis and sequencing buckets are untagged and report no lifecycle config via `GetBucketLifecycleConfiguration`.
5. **RDS/Aurora tag and sizing review**: `dayhoff-lsmcq7-tapdb` has a `db.r8g.2xlarge` writer plus two `db.r8g.xlarge` readers and missing `Name` tags; verify this capacity is still required.

## Overview Plots

![Daily AWS spend](../aws_usage_report/images/daily_spend.svg)

![Weekly spend by top service](../aws_usage_report/images/weekly_service_spend.svg)

![Top services](../aws_usage_report/images/top_services.svg)

![Top regions](../aws_usage_report/images/top_regions.svg)

![Top ParallelCluster tag spend](../aws_usage_report/images/top_cluster_tags.svg)

![Blank tag cost buckets](../aws_usage_report/images/tag_gap_costs.svg)

![Savings candidates](../aws_usage_report/images/savings_candidates.svg)

## Time Trend

| Period | Spend |
|---|---:|
| 2026-02-20..2026-02-28 | $6,178.49 |
| 2026-03-01..2026-03-31 | $4,244.84 |
| 2026-04-01..2026-04-30 | $9,334.55 |
| 2026-05-01..2026-05-20 | $15,285.37 |

May month-to-date is the largest segment and was marked estimated by Cost Explorer. The spike is mainly EC2 compute plus FSx/S3 persistence around live and recently deleted ParallelCluster workloads.

## Cost Drivers

### Regions

| Region | Spend |
|---|---:|
| us-west-2 | $31,764.92 |
| us-east-1 | $1,511.77 |
| global | $1,016.09 |
| eu-central-1 | $376.49 |
| ap-south-1 | $321.61 |
| all other enabled regions combined | $52.44 |

### Usage Types

| Usage type | Spend |
|---|---:|
| `USW2-Storage` | $9,562.23 |
| `USW2-TimedStorage-ByteHrs` | $4,241.27 |
| `USW2-SpotUsage:m7i.metal-48xl` | $3,861.08 |
| `USW2-SpotUsage:m7i.48xlarge` | $3,200.77 |
| `USW2-SpotUsage:r7i.48xlarge` | $2,713.55 |
| `USW2-BoxUsage:r7i.2xlarge` | $1,637.02 |
| `USW2-EBS:VolumeUsage.gp3` | $909.68 |
| `Dollar` / AWS Support | $819.07 |

The dominant pattern is direct: big ParallelCluster compute, large FSx Lustre storage, large S3 Standard storage, EBS gp3, NAT gateways, and RDS.

### ParallelCluster Attribution

Only ParallelCluster cost allocation tags were useful historically. `Project`, `project`, `lsmc-project`, `Name`, and `aws:cloudformation:stack-name` were 100% blank in Cost Explorer for this window.

| `parallelcluster:cluster-name` | Spend |
|---|---:|
| blank / not cluster-tagged | $11,071.44 |
| `agbt-heavy` | $3,868.35 |
| `may26-d` | $3,688.69 |
| `ifx-go` | $2,603.90 |
| `mk-gotime3` | $1,851.03 |
| `fk-260509-use` | $1,824.33 |
| `agbt-12t-usw2d` | $1,585.74 |
| `inflextion-g24` | $1,382.12 |
| `dra-enabled` | $917.87 |
| `at-sanity` | $830.78 |

`parallelcluster:cluster-name` blank cost is **$11,071.44 / 31.6%**. Its largest services were S3, EC2 Other, RDS, EC2 Compute, and Support, so this bucket is mostly non-cluster or cluster-adjacent resources without cluster tags.

## Live Resource And Tag Investigation

Live inventory covered the material spend regions (`us-west-2`, `us-east-1`, `eu-central-1`, `ap-south-1`), global S3 buckets, and a lightweight core sweep of the remaining enabled regions. The low-spend-region sweep found no EC2, EBS, EIP, NAT, FSx, or RDS resources in the remaining regions.

Saved live-resource inventory: `docs/aws_3month_retrospective_cost_analysis_assets/data/live_resources.json` and `.csv`.

Current active ParallelClusters:

| Cluster | Region | Status |
|---|---|---|
| `XL-pilot` | us-west-2 | `CREATE_COMPLETE` |
| `dra-enabled` | us-west-2 | `CREATE_COMPLETE` |

Focused collector tag status across 142 live resources:

| Tag status | Count |
|---|---:|
| completely untagged | 41 |
| missing cluster/stack | 31 |
| missing `Name` | 28 |
| missing project | 16 |
| other tags only | 8 |
| fully attributed | 18 |

A separate tag-attribution agent scan found 199 live resources in the same material regions and reached the same conclusion: live tags exist, but `Name`, explicit project tags, and cluster/stack attribution are inconsistent.

### Live Resources To Tag

| Resource | Problem | Console |
|---|---|---|
| `labcore-dev-instance-1` RDS | completely untagged | [open](https://console.aws.amazon.com/rds/home?region=us-west-2#database:id=labcore-dev-instance-1;is-cluster=false) |
| `labcore-dev` RDS cluster | completely untagged | [open](https://console.aws.amazon.com/rds/home?region=us-west-2#database:id=labcore-dev;is-cluster=true) |
| `i-09f66b3f11ea42c60` / `labplatform-mvp` | `Name` only, missing project/cluster | [open](https://us-west-2.console.aws.amazon.com/ec2/home?region=us-west-2#InstanceDetails:instanceId=i-09f66b3f11ea42c60) |
| `i-071ccd80c69969d92` / `terrarium-dev-tailscale-router` | missing cluster/stack | [open](https://us-west-2.console.aws.amazon.com/ec2/home?region=us-west-2#InstanceDetails:instanceId=i-071ccd80c69969d92) |
| `i-03a38912d7d651f1a` / `terrarium-prod-tailscale-router` | missing cluster/stack | [open](https://us-west-2.console.aws.amazon.com/ec2/home?region=us-west-2#InstanceDetails:instanceId=i-03a38912d7d651f1a) |
| `vol-0c69ba6b467620e14` | completely untagged 336 GiB EBS | [open](https://us-west-2.console.aws.amazon.com/ec2/home?region=us-west-2#VolumeDetails:volumeId=vol-0c69ba6b467620e14) |
| `vol-0ea36895cc2b979ac` | completely untagged 336 GiB EBS | [open](https://us-west-2.console.aws.amazon.com/ec2/home?region=us-west-2#VolumeDetails:volumeId=vol-0ea36895cc2b979ac) |
| `vol-0c26833469cf6995a` | completely untagged 234 GiB EBS attached to stopped `lsmc-web` | [open](https://us-west-2.console.aws.amazon.com/ec2/home?region=us-west-2#VolumeDetails:volumeId=vol-0c26833469cf6995a) |
| `dra-0e036df15b52f3f85` | FSx DRA has only non-attribution tags | [open](https://us-west-2.console.aws.amazon.com/fsx/home?region=us-west-2#data-repository-association-details/dra-0e036df15b52f3f85) |
| `dra-006ba927d666a551f` | FSx DRA has only non-attribution tags | [open](https://us-west-2.console.aws.amazon.com/fsx/home?region=us-west-2#data-repository-association-details/dra-006ba927d666a551f) |
| `lsmc-ssf-sequencing-data` | S3 bucket completely untagged, no lifecycle returned | [open](https://s3.console.aws.amazon.com/s3/buckets/lsmc-ssf-sequencing-data?region=us-west-2&bucketType=general) |
| `lsmc-dayoa-omics-analysis-us-west-2` | S3 bucket completely untagged, no lifecycle returned | [open](https://s3.console.aws.amazon.com/s3/buckets/lsmc-dayoa-omics-analysis-us-west-2?region=us-west-2&bucketType=general) |
| `lsmc-healthomics-results` | S3 bucket completely untagged, no lifecycle returned | [open](https://s3.console.aws.amazon.com/s3/buckets/lsmc-healthomics-results?region=us-west-2&bucketType=general) |
| `lsmc-ursa-customers-usw2` | S3 bucket completely untagged, no lifecycle returned | [open](https://s3.console.aws.amazon.com/s3/buckets/lsmc-ursa-customers-usw2?region=us-west-2&bucketType=general) |

Full table: `docs/aws_3month_retrospective_cost_analysis_assets/data/untagged_live_resources.csv`.

## Zombie And Savings Candidates

These are review targets, not deletion instructions.

| Target | Evidence | Estimated monthly run-rate | Console |
|---|---|---:|---|
| `fs-01c4180aab049f24c` / `XL-pilot` FSx | `AVAILABLE`, 14,400 GiB SCRATCH_2 | ~$2,016 | [open](https://us-west-2.console.aws.amazon.com/fsx/home?region=us-west-2#file-system-details/fs-01c4180aab049f24c) |
| `fs-017ab7a7cdbf44c54` / `dra-enabled` FSx | `AVAILABLE`, 12,000 GiB SCRATCH_2 | ~$1,680 | [open](https://us-west-2.console.aws.amazon.com/fsx/home?region=us-west-2#file-system-details/fs-017ab7a7cdbf44c54) |
| `vol-067169329e7a92af1` | unattached 421 GiB gp3 EBS | ~$33.68 | [open](https://us-west-2.console.aws.amazon.com/ec2/home?region=us-west-2#VolumeDetails:volumeId=vol-067169329e7a92af1) |
| `vol-0f5e5d7eec5982fa8` | unattached 421 GiB gp3 EBS | ~$33.68 | [open](https://us-west-2.console.aws.amazon.com/ec2/home?region=us-west-2#VolumeDetails:volumeId=vol-0f5e5d7eec5982fa8) |
| `vol-0c90d4fbaada3820a` | unattached 421 GiB gp3 EBS | ~$33.68 | [open](https://us-west-2.console.aws.amazon.com/ec2/home?region=us-west-2#VolumeDetails:volumeId=vol-0c90d4fbaada3820a) |
| `vol-042a5f5daead20490` | unattached 421 GiB gp3 EBS | ~$33.68 | [open](https://us-west-2.console.aws.amazon.com/ec2/home?region=us-west-2#VolumeDetails:volumeId=vol-042a5f5daead20490) |
| `eipalloc-02ef5760f8f8700fd` | unassociated Elastic IP | ~$3.60 | [open](https://us-west-2.console.aws.amazon.com/ec2/home?region=us-west-2#Addresses:PublicIp=eipalloc-02ef5760f8f8700fd) |
| NAT gateways | ten active NAT gateways across material regions; several missing project/cluster attribution | ~$32.40 each before data processing | see inventory CSV |
| `dayhoff-lsmcq7-tapdb-writer` | `db.r8g.2xlarge` Aurora writer remains available | not estimated | [open](https://us-west-2.console.aws.amazon.com/rds/home?region=us-west-2#database:id=dayhoff-lsmcq7-tapdb-writer;is-cluster=false) |

The two FSx filesystems are the largest clear savings surface. If their backing data has already been exported and no jobs are active, they should be prioritized for delete-plan review under the usual second-confirmation destructive-action policy.

## Ursa Production Automation Notes

This report family should be turned into a scheduled producer plus read-only Ursa consumer. Do not put Cost Explorer or regional inventory scans on a dashboard request path.

Recommended producer behavior:

- Run daily after Cost Explorer data is expected to settle.
- Use explicit config only; missing config fails closed.
- Write versioned artifacts to a configured S3 bucket/prefix.
- Do not infer an S3 bucket from Ursa internal output buckets, cluster tags, default profile state, or service-side discovery.
- Precompute console links, plot artifacts, and stale/error metadata.

Recommended artifact layout:

```text
current/summary.json
current/resources.json
current/savings.json
current/report.md
current/plots/*.svg
runs/<run_id>/summary.json
runs/<run_id>/resources.json
runs/<run_id>/savings.json
runs/<run_id>/report.md
runs/<run_id>/plots/*.svg
```

Future Ursa config keys:

```yaml
cost_report_bucket: <required>
cost_report_prefix: <required>
cost_report_profile: <required>
cost_report_region: <required>
cost_report_max_age_hours: <required>
```

Recommended Ursa route/API shape:

- Add a read-only admin page such as `/usage/aws-cost`.
- Add `GET /api/v1/aws-cost-report/current`.
- Return freshness state, run ID, generated timestamp, report link, plot links, top cost drivers, untagged live resources, and savings candidates.
- Show explicit `missing`, `stale`, or `error` states when artifacts are absent or too old.
- Keep this separate from the existing Ursa spot-pricing monitor; that monitor captures partition spot-price availability, not actual Cost Explorer spend.

Future tests should prove:

- Missing config fails hard.
- Stale artifacts render a stale state.
- Dashboard/API routes do not call Cost Explorer or regional inventory APIs directly.
- Artifact reads use only the explicit configured bucket/prefix/profile/region.

## Evidence And Artifacts

Raw Cost Explorer JSON:

- `docs/aws_3month_retrospective_cost_analysis_assets/raw/ce_total_daily.json`
- `docs/aws_3month_retrospective_cost_analysis_assets/raw/ce_service_daily.json`
- `docs/aws_3month_retrospective_cost_analysis_assets/raw/ce_service_monthly.json`
- `docs/aws_3month_retrospective_cost_analysis_assets/raw/ce_region_monthly.json`
- `docs/aws_3month_retrospective_cost_analysis_assets/raw/ce_usage_type_monthly.json`
- `docs/aws_3month_retrospective_cost_analysis_assets/raw/ce_operation_monthly.json`
- `docs/aws_3month_retrospective_cost_analysis_assets/raw/ce_tag_parallelcluster_cluster-name.json`

Derived data:

- `docs/aws_3month_retrospective_cost_analysis_assets/data/summary.json`
- `docs/aws_3month_retrospective_cost_analysis_assets/data/live_resources.json`
- `docs/aws_3month_retrospective_cost_analysis_assets/data/untagged_live_resources.csv`
- `docs/aws_3month_retrospective_cost_analysis_assets/data/zombie_candidates.csv`
- `docs/aws_3month_retrospective_cost_analysis_assets/data/low_spend_region_sweep.json`

Read-only command evidence is preserved in:

- `docs/aws_3month_retrospective_cost_analysis_assets/data/inventory_commands.json`

Cost Explorer evidence is preserved as raw response JSON under `docs/aws_3month_retrospective_cost_analysis_assets/raw/`; those filenames encode the grouped query dimensions.

Expected metadata misses:

- 32 S3 buckets returned `NoSuchLifecycleConfiguration`.
- 21 S3 buckets returned `NoSuchTagSet`.

Those are findings, not collector failures. After filtering those expected metadata misses, there were no unresolved read failures in the focused live inventory.

## Limits

- Cost Explorer reflects historical cost and tag activation state; it cannot prove that a historical resource is still running.
- Live scan is current as of 2026-05-21 and may differ from historical spend sources that have since been deleted.
- Live resource coverage is deepest for the material regions and global S3. A core EC2/EBS/EIP/NAT/FSx/RDS sweep of remaining enabled regions found no resources.
- Savings estimates for FSx, EBS, EIP, and NAT are approximate run-rate estimates for prioritization, not invoices.
