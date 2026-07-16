# LSMC AWS Cost, Untagged Resource, And Utilization Audit

Generated: 2026-07-16T00:45:33.101030Z  
AWS profile/account: `lsmc` / `108782052779`  
Safety: read-only; no AWS mutations performed.

## Technical Summary

July 1-14 spend is **$20,620.26**. The daily rate is **10.9% below June**, but EC2, S3, RDS, and FSx still account for **88.1%** of July spend.

The clearest findings are:

- **63,060 Cost Explorer API requests cost $630.60** in 14 days.
- The three `dayhoff-lsmcq7` RDS instances cost **$413.56** combined while averaging **1.81%-2.88% CPU** and **zero database connections**.
- Four untagged NAT gateways in `ap-south-1` and `eu-central-1` cost **$36.30** combined and reported **zero traffic**.
- **66 current resources have zero user tags**: 26 S3 buckets, 14 EBS volumes, 13 Elastic IPs, 6 NAT gateways, 3 snapshots, 2 RDS instances, and 2 load balancers.
- The `lsmc` profile resolves to `arn:aws:iam::108782052779:root`; the scan was read-only, but the credential scope is materially broader than needed.

## Resource And Cluster Lifecycle Snapshot

Lifecycle evidence was refreshed at **2026-07-16T00:45:33.101030Z** across all 21 enabled regions. ParallelCluster explicitly does not support `ap-northeast-3` or `ap-south-2`; direct AWS inventory and CloudFormation coverage still succeeded in both regions.

### ParallelCluster

| Cluster | Region | July $ | Lifecycle | Cluster state | Compute fleet | Stack |
| --- | --- | --- | --- | --- | --- | --- |
| jemx3 | us-west-2 | 4,577.61 | deleted | absent |  | DELETE_COMPLETE |
| illumina-94-c01 | us-west-2 | 1,350.40 | deleted | absent |  | DELETE_COMPLETE |
| illumina-94-c02 | us-west-2 | 1,254.54 | deleted | absent |  | DELETE_COMPLETE |
| partrevert | us-west-2 | 843.70 | deleted | absent |  | DELETE_COMPLETE |
| preval-hybrid-set3 | us-west-2 | 663.27 | deleted | absent |  | DELETE_COMPLETE |
| ifx-reworkB | us-west-2 | 523.24 | deleted | absent |  | DELETE_COMPLETE |
| preval-segdups-and-eh | us-west-2 | 487.46 | deleted | absent |  | DELETE_COMPLETE |
| blank/unattributed | unknown | 445.03 | unresolved | not a cluster identity |  |  |
| sent-hg003-5x-0712 | us-west-2 | 372.75 | deleted | absent |  | DELETE_COMPLETE |
| cmdcat-103-all-20260707 | us-west-2 | 325.04 | deleted | absent |  | DELETE_COMPLETE |
| jul8itelx4 | us-west-2 | 136.60 | deleted | absent |  | DELETE_COMPLETE |
| testbudgetblock | us-west-2 | 100.19 | deleted | absent |  | DELETE_COMPLETE |
| hiomr-hg003-5x-0710 | us-west-2 | 69.18 | deleted | absent |  | DELETE_COMPLETE |
| ursa-ilmnqc-0703 | us-west-2 | 35.70 | deleted | absent |  | DELETE_COMPLETE |
| dyec-costacct-005955 | us-west-2 | 30.35 | deleted | absent |  | DELETE_COMPLETE |
| ursa-m-rgx-br75 | us-west-2 | 23.41 | deleted | absent |  | DELETE_COMPLETE |
| ursa-m-rgx-bk3j | us-west-2 | 19.48 | deleted | absent |  | DELETE_COMPLETE |
| ifx-20260719h | us-west-2 | 15.40 | deleted | absent |  | DELETE_COMPLETE |
| dragain12 | us-west-2 | 13.22 | deleted | absent |  | DELETE_COMPLETE |
| ifx-hyb-all | us-west-2 | 12.84 | deleted | absent |  | DELETE_COMPLETE |
| dragain9b | us-west-2 | 11.49 | deleted | absent |  | DELETE_COMPLETE |
| sentlic-e | us-west-2 | 9.97 | deleted | absent |  | DELETE_COMPLETE |
| preval-hybrid-set2 | us-west-2 | 9.12 | deleted | absent |  | DELETE_COMPLETE |
| dragen-fix5-20260708 | us-west-2 | 7.33 | deleted | absent |  | DELETE_COMPLETE |
| dragain11 | us-west-2 | 7.14 | deleted | absent |  | DELETE_COMPLETE |
| dragain2 | us-west-2 | 6.61 | deleted | absent |  | DELETE_COMPLETE |
| ifx-sacctoff-1037 | us-west-2 | 2.85 | deleted | absent |  | DELETE_COMPLETE |
| dragen-f2-pcimg-nofsx-2c | us-west-2 | 1.17 | deleted | absent |  | DELETE_COMPLETE |
| dragen-f2-native-nofsx-2c | us-west-2 | 0.50 | deleted | absent |  | DELETE_COMPLETE |
| cost-testing | us-west-2 | 0.49 | deleted | absent |  | DELETE_COMPLETE |
| minitest | us-west-2 | 0.30 | deleted | absent |  | DELETE_COMPLETE |
| tinytst2 | us-west-2 | 0.28 | deleted | absent |  | DELETE_COMPLETE |
| ifx-20260719g | us-west-2 | 0.26 | deleted | absent |  | DELETE_COMPLETE |
| sent-liscC | us-west-2 | 0.26 | deleted | absent |  | DELETE_COMPLETE |
| jly08costck | us-west-2 | 0.20 | deleted | absent |  | DELETE_COMPLETE |
| dragen-fix4-20260708 | us-west-2 | 0.12 | deleted | absent |  | DELETE_COMPLETE |
| dragen-fix-20260708 | us-west-2 | 0.10 | deleted | absent |  | DELETE_COMPLETE |
| dragen-fix2-20260708 | us-west-2 | 0.10 | deleted | absent |  | DELETE_COMPLETE |
| dragen-fix3-20260708 | us-west-2 | 0.10 | deleted | absent |  | DELETE_COMPLETE |
| dragen-103-pg-20260707 | us-west-2 | 0.08 | deleted | absent |  | DELETE_COMPLETE |
| drg-na19235-pg | us-west-2 | 0.08 | deleted | absent |  | DELETE_COMPLETE |
| dragen-f2-native-2c | us-west-2 | 0.07 | deleted | absent |  | DELETE_COMPLETE |
| dragen-f2-pcimg-fsx-2c | us-west-2 | 0.07 | deleted | absent |  | DELETE_COMPLETE |
| dragain10 | us-west-2 | 0.05 | deleted | absent |  | DELETE_COMPLETE |
| ifx-p2-1000-120-0715 | us-west-2 | 0.00 | active | UPDATE_COMPLETE | RUNNING | UPDATE_COMPLETE |
| ifx-p2-250-0714 | us-west-2 | 0.00 | deleted | absent |  | DELETE_COMPLETE |
| tst-10315g | us-west-2 | 0.00 | provisioning_or_updating | CREATE_IN_PROGRESS | not queried while cluster is CREATE_IN_PROGRESS | CREATE_IN_PROGRESS |

`jemx3` is **deleted**, not running. ParallelCluster reports it absent, the live CloudFormation stack is absent, and CloudFormation history records `DELETE_COMPLETE` at **2026-07-05T09:22:22.181Z**. No `jemx3` EC2 instances or managed FSx `fs-07fb3448c1cb30c1c` exist.

The tag index retained eight old `jemx3` references. Service-specific checks show four EBS volumes and one DRA are deleted stale-index entries. Three CloudWatch log groups still exist after the owner stack was deleted, so those are classified **orphaned**:

| Resource | Exists | Lifecycle | Evidence |
| --- | --- | --- | --- |
| arn:aws:ec2:us-west-2:108782052779:volume/vol-0ac2c473b9345e199 | False | deleted | absent from refreshed all-region EBS inventory; tag index entry is stale |
| arn:aws:logs:us-west-2:108782052779:log-group:/aws/parallelcluster/jemx3-202606210248 | True | orphaned | log group exists after owning cluster stack DELETE_COMPLETE |
| arn:aws:ec2:us-west-2:108782052779:volume/vol-016958bd2b46c1b14 | False | deleted | absent from refreshed all-region EBS inventory; tag index entry is stale |
| arn:aws:logs:us-west-2:108782052779:log-group:/aws/lambda/pcluster-CleanupRoute53-aa87ff20-6d1b-11f1-8905-062667cba8dd | True | orphaned | log group exists after owning cluster stack DELETE_COMPLETE |
| arn:aws:ec2:us-west-2:108782052779:volume/vol-01d389f0209bf7b61 | False | deleted | absent from refreshed all-region EBS inventory; tag index entry is stale |
| arn:aws:fsx:us-west-2:108782052779:association/fs-07fb3448c1cb30c1c/dra-0d46e9663035ad25c | False | deleted | FSx returned no current association; tag index entry is stale |
| arn:aws:ec2:us-west-2:108782052779:volume/vol-0f2aa99c6c27efcdc | False | deleted | absent from refreshed all-region EBS inventory; tag index entry is stale |
| arn:aws:logs:us-west-2:108782052779:log-group:/aws/lambda/pcluster-CleanupResources-aa87ff20-6d1b-11f1-8905-062667cba8dd | True | orphaned | log group exists after owning cluster stack DELETE_COMPLETE |

At the snapshot, two clusters existed:

- `ifx-p2-1000-120-0715`: **active**, `UPDATE_COMPLETE`, compute fleet `RUNNING`.
- `tst-10315g`: **provisioning**, `CREATE_IN_PROGRESS`; compute-fleet state was intentionally not queried until cluster creation completes.

All other 44 named cluster rows are deleted. The `blank/unattributed` $445.03 billing row is unresolved because it is not a cluster identity.

### Current stopped and transitioning resources

The refreshed direct inventory contains **10 stopped resources** and **1 deleting resource**. Stopped is based only on explicit AWS provider state.

| Resource | Name | Region | July $ | Owner stack |
| --- | --- | --- | --- | --- |
| i-0b13373722116c733 | day-dr-drill-host-use1-20260619 | us-east-1 | 12.92 |  |
| i-018a4be07f5bdfa49 | Dayhoff-jemdev5-Compute/Hostprimary | us-east-1 | 11.12 | Dayhoff-jemdev5-Compute |
| i-0e70fab85d559c615 | Dayhoff-inf-Compute/Hostprimary | us-east-1 | 11.00 | Dayhoff-inf-Compute |
| i-0b6713cc15f74d360 | Dayhoff-ddev96-Compute/Hostprimary | us-east-1 | 11.00 | Dayhoff-ddev96-Compute |
| i-0de9e3f8d3208cf03 | Dayhoff-dev-Compute/Hostprimary | us-east-1 | 11.00 | Dayhoff-dev-Compute |
| i-05de16a24310099c5 | Dayhoff-joshdev-Compute/Hostprimary | us-east-1 | 11.00 | Dayhoff-joshdev-Compute |
| i-09126000eb19643b0 | Dayhoff-aws3041-Compute/Hostprimary | us-west-2 | 10.00 | Dayhoff-aws3041-Compute |
| i-0a70e6af119b993f3 | Dayhoff-lsmcq7-Compute/Hostprimary | us-west-2 | 10.00 | Dayhoff-lsmcq7-Compute |
| i-068f3aad2bedb9fa6 | Dayhoff-josh-dev-Compute/Hostprimary | us-east-1 | 9.90 | Dayhoff-josh-dev-Compute |
| i-02a5b297000e82966 | lsmc-web | us-west-2 | 0.00 |  |

| Resource | Name | Region | Provider state | Owner cluster |
| --- | --- | --- | --- | --- |
| i-02c0da227ad61dcd0 | Compute | us-west-2 | shutting-down | ifx-p2-1000-120-0715 |

### CloudFormation exceptions

Two stacks remain in unresolved failure states; five other stacks record completed rollback states and are reported separately as `exception_recovered`.

| Stack | Region | Classification | AWS state | Reason |
| --- | --- | --- | --- | --- |
| Dayhoff-josh-dev-Budget | us-east-1 | exception_recovered | UPDATE_ROLLBACK_COMPLETE |  |
| Dayhoff-staging-Network | us-east-1 | exception | DELETE_FAILED | The following resource(s) failed to delete: [VpcprivateSubnet2Subnet2DE7549C, VpcprivateSubnet1SubnetCEAD3716].  |
| tapdb-dev | us-east-1 | exception_recovered | UPDATE_ROLLBACK_COMPLETE |  |
| marvain-cleanroom-20260712T103857Z | us-west-1 | exception | ROLLBACK_FAILED | The following resource(s) failed to delete: [AgentWorkerSecurityGroup].  |
| tst-10315g-ComputeFleetQueuesNestedStackQueuesNestedStackResource4C142E85-8RM1HODL0274 | us-west-2 | provisioning_or_updating | CREATE_IN_PROGRESS |  |
| tst-10315g | us-west-2 | provisioning_or_updating | CREATE_IN_PROGRESS |  |
| pcluster-vpc-stack-2b | us-west-2 | exception_recovered | ROLLBACK_COMPLETE |  |
| pcluster-vpc-stack-2a | us-west-2 | exception_recovered | ROLLBACK_COMPLETE |  |
| Dayhoff-aws3041-Compute | us-west-2 | exception_recovered | UPDATE_ROLLBACK_COMPLETE |  |

The unresolved failures are:

- `Dayhoff-staging-Network` (`us-east-1`): `DELETE_FAILED`; two private subnets failed deletion.
- `marvain-cleanroom-20260712T103857Z` (`us-west-1`): `ROLLBACK_FAILED`; `AgentWorkerSecurityGroup` failed deletion.

### Full lifecycle inventory

The canonical lifecycle table contains **3,468 rows** covering all **196 current direct-inventory resources** plus all **3,457 unique July billed identifiers**, with matching live/billed rows deduplicated. Overall classifications are {"active": 178, "deleted": 3199, "deleting": 1, "orphaned": 3, "stopped": 10, "unresolved": 77}. The 77 `unresolved` rows are billing identifiers that do not represent a directly enumerable resource type; they are not guessed as deleted.

Full table: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/lifecycle_resources.csv`

## Cost Concentration

June total: **$49,608.92** (final). July 1-14 total: **$20,620.26** (estimated). Daily cost fell from **$1,653.63** to **$1,472.88**.

| Service | July MTD $ | Share % | June $ |
| --- | --- | --- | --- |
| Amazon Elastic Compute Cloud - Compute | 11,358.17 | 55.08 | 31,617.02 |
| Amazon Simple Storage Service | 3,712.43 | 18.00 | 7,008.04 |
| Amazon Relational Database Service | 1,635.90 | 7.93 | 4,479.20 |
| Amazon FSx | 1,465.77 | 7.11 | 2,395.89 |
| AWS Cost Explorer | 632.11 | 3.07 | 386.83 |
| AWS Support (Developer) | 597.02 | 2.90 | 1,407.35 |
| EC2 - Other | 537.23 | 2.61 | 1,035.16 |
| AWS Config | 229.36 | 1.11 | 0.00 |
| AWS Security Hub | 147.73 | 0.72 | 432.71 |
| Amazon Virtual Private Cloud | 80.16 | 0.39 | 162.16 |

Non-resource platform activity also matters: Cost Explorer API calls are the fifth-largest July service cost at **$632.11** total, including **$630.60 / 63,060 requests** under `USE1-APIRequest`; AWS Config recorded **71,399 configuration items** for **$214.20**.

## High-Cost Resources And Utilization

| Category | Resource | Region | July $ | Utilization | Tags | Live |
| --- | --- | --- | --- | --- | --- | --- |
| S3 bucket | lsmc-ssf-sequencing-data | us-west-2 | 953.69 | 218.046 TiB; 5,503,555 objects; request metrics not enabled | tagged | live |
| S3 bucket | lsmc-dayoa-omics-analysis-us-west-2 | us-west-2 | 278.01 | 61.428 TiB; 4,000,574 objects; request metrics not enabled | tagged | live |
| RDS instance | dayhoff-lsmcq7-tapdb-writer | us-west-2 | 206.78 | CPU avg 1.81%, p95 1.90%; connections avg 0.00 | tagged | live |
| FSx file system | fs-07fb3448c1cb30c1c | us-west-2 | 190.43 | 50.112 TiB read; 12.908 TiB write; 419,915,451 metadata ops | not observable after deletion | not live at scan time |
| FSx file system | fs-0b57687e1517a9181 | us-west-2 | 151.45 | 0.000 TiB read; 0.001 TiB write; 7,395,317 metadata ops | not observable after deletion | not live at scan time |
| RDS instance | dayhoff-lsmcq7-tapdb-reader-api | us-west-2 | 103.39 | CPU avg 2.54%, p95 2.56%; connections avg 0.00 | tagged | live |
| RDS instance | dayhoff-lsmcq7-tapdb-reader-ha | us-west-2 | 103.39 | CPU avg 2.88%, p95 3.23%; connections avg 0.00 | tagged | live |
| EBS volume | vol-0840104f024bda559 | unknown | 87.10 | not live at scan time; no current utilization | not observable after deletion | not live at scan time |
| FSx file system | fs-02cac31094f973e29 | us-west-2 | 74.40 | 12.352 TiB read; 1.066 TiB write; 46,158,791 metadata ops | not observable after deletion | not live at scan time |
| FSx file system | fs-0b9e294bd75a9ad9d | us-west-2 | 72.41 | 4.774 TiB read; 4.663 TiB write; 9,523,749 metadata ops | not observable after deletion | not live at scan time |
| S3 bucket | lsmc-dayoa-staging-usw2 | us-west-2 | 50.01 | 11.047 TiB; 56,018 objects; request metrics not enabled | tagged | live |
| S3 bucket | lsmc-dayoa-control-data-usw2 | us-west-2 | 46.57 | 10.286 TiB; 31,980 objects; request metrics not enabled | tagged | live |
| RDS instance | labcore-dev-instance-1 | us-west-2 | 46.08 | CPU avg 2.75%, p95 2.79%; connections avg 0.00 | untagged | live |
| RDS instance | dayhoff-lsmcok1-tapdb-writer | us-west-2 | 39.74 | CPU avg 5.81%, p95 5.90%; connections avg 14.18 | tagged | live |
| RDS instance | auruse1-writer | us-east-1 | 37.44 | CPU avg 8.16%, p95 8.27%; connections avg 0.00 | tagged | live |
| RDS instance | dev-writer | us-west-2 | 37.44 | CPU avg 8.92%, p95 9.18%; connections avg 0.00 | tagged | live |
| NAT gateway | nat-00f3c26e43ede9b10 | us-west-2 | 33.00 | 1,992.128 GiB across four CloudWatch byte counters | untagged | live |
| FSx file system | fs-03e6f0d7589e629c8 | us-west-2 | 30.56 | 0.006 TiB read; 0.013 TiB write; 16,978,284 metadata ops | not observable after deletion | not live at scan time |
| S3 bucket | lsmc-public-ont-data | us-west-2 | 25.38 | 5.604 TiB; 2,474 objects; request metrics not enabled | untagged | live |
| FSx file system | fs-0dd06f7c3c3e0c1ef | us-west-2 | 23.38 | 0.000 TiB read; 0.000 TiB write; 35,578 metadata ops | not observable after deletion | not live at scan time |
| RDS instance | dr-drill-standalone-20260521 | us-west-2 | 13.14 | no current CloudWatch row; instance not live at scan time | not observable after deletion | not live at scan time |
| FSx file system | fs-072fc57baf4bc48b5 | us-west-2 | 10.54 | 0.000 TiB read; 0.000 TiB write; 7,506,014 metadata ops | not observable after deletion | not live at scan time |
| RDS instance | dev-writer | us-east-1 | 10.51 | CPU avg 15.20%, p95 16.04%; connections avg 6.55 | tagged | live |
| RDS instance | staging-writer | us-west-2 | 10.51 | CPU avg 10.12%, p95 10.28%; connections avg 0.00 | tagged | live |
| NAT gateway | nat-05f85018216cac061 | ap-south-1 | 9.41 | 0.000 GiB across four CloudWatch byte counters | untagged | live |
| NAT gateway | nat-01dc061291fc51e75 | ap-south-1 | 9.41 | 0.000 GiB across four CloudWatch byte counters | untagged | live |
| RDS instance | dr-drill-standalone-use1-20260526 | us-east-1 | 9.39 | no current CloudWatch row; instance not live at scan time | not observable after deletion | not live at scan time |
| S3 bucket | lsmc-copy-ultimagen-lsmc-cro-316 | us-west-2 | 9.11 | 2.024 TiB; 109 objects; request metrics not enabled | tagged | live |
| FSx file system | fs-05627d04a7ce25fe5 | us-west-2 | 9.10 | 0.000 TiB read; 0.000 TiB write; 7,155,874 metadata ops | not observable after deletion | not live at scan time |
| NAT gateway | nat-0ec6ae9605269bef4 | eu-central-1 | 8.74 | 0.000 GiB across four CloudWatch byte counters | untagged | live |

The largest S3 buckets are `lsmc-ssf-sequencing-data` at **218.046 TiB / $953.69** and `lsmc-dayoa-omics-analysis-us-west-2` at **61.428 TiB / $278.01**. None of the top-cost buckets had S3 request metrics enabled, so this scan can measure stored capacity but not request activity.

The highest resource-ID FSx cost was `fs-07fb3448c1cb30c1c` at **$190.43**, with **50.112 TiB read**, **12.908 TiB written**, and **419,915,451 metadata operations**. By contrast, `fs-0b57687e1517a9181` cost **$151.45** with essentially no data I/O (0 read, 0.001 TiB written), though it still had 7.4M metadata operations. These file systems were no longer live at scan time; CloudWatch history supplied the measurements.

## EC2 CPU Sample

Resource-level IDs cover **71.06%** of July EC2 cost. The top-100 instance sample covers **40.18%** of total EC2 service spend; 99 IDs resolved to exact metadata and 5-minute CPU, while `i-01db42c813d037c0e` ($27.96) remained unresolved.

| Cluster | Full July $ | Sample $ | Coverage % | Measured vCPU-h | CPU busy % |
| --- | --- | --- | --- | --- | --- |
| jemx3 | 4,577.61 | 1,825.58 | 39.88 | 62,694.67 | 3.03 |
| illumina-94-c01 | 1,350.40 | 825.77 | 61.15 | 24,280.00 | 13.82 |
| illumina-94-c02 | 1,254.54 | 537.80 | 42.87 | 15,192.00 | 20.34 |
| preval-hybrid-set3 | 663.27 | 584.26 | 88.09 | 17,927.33 | 9.98 |
| preval-segdups-and-eh | 487.46 | 436.54 | 89.55 | 13,072.00 | 15.68 |
| cmdcat-103-all-20260707 | 325.04 | 37.34 | 11.49 | 1,152.00 | 12.21 |
| testbudgetblock | 100.19 | 100.19 | 100.00 | 1,514.67 | 0.42 |
| ursa-ilmnqc-0703 | 35.70 | 35.70 | 100.01 | 540.00 | 0.59 |
| dyec-costacct-005955 | 30.35 | 30.33 | 99.93 | 459.33 | 0.73 |
| untagged/unattributed | 0.00 | 122.58 | None | 3,952.00 | 2.97 |
| unknown | 0.00 | 27.96 | None | 0.00 | None |

This is CPU utilization, not workflow efficiency. High-I/O jobs, scheduler gaps, node startup, and deliberately oversized memory instances can all produce low CPU. Pair these results with Slurm/job benchmark data before rightsizing.

## Untagged Resources

Direct service APIs found **66 current resources with zero non-AWS tags**. Exact resource-level billing IDs join **$187.46** of July cost to 45 of them; this is a lower bound because resource-level Cost Explorer coverage is incomplete.

| Category | Resource | Region | July $ | Utilization | State |
| --- | --- | --- | --- | --- | --- |
| db_instance | labcore-dev-instance-1 | us-west-2 | 46.08 | CPU avg 2.75%; connections avg 0.00 | available |
| nat_gateway | nat-00f3c26e43ede9b10 | us-west-2 | 33.00 | 1,992.128 GiB across four byte counters | available |
| bucket | lsmc-public-ont-data | us-west-2 | 25.38 | 5.604 TiB; request metrics not enabled | live |
| nat_gateway | nat-05f85018216cac061 | ap-south-1 | 9.41 | 0.000 GiB across four byte counters | available |
| nat_gateway | nat-01dc061291fc51e75 | ap-south-1 | 9.41 | 0.000 GiB across four byte counters | available |
| nat_gateway | nat-0ec6ae9605269bef4 | eu-central-1 | 8.74 | 0.000 GiB across four byte counters | available |
| nat_gateway | nat-0a2bfbfedf38f8e87 | eu-central-1 | 8.74 | 0.000 GiB across four byte counters | available |
| volume | vol-0aa3f5a0f5cdca9a0 | us-east-1 | 6.07 | 33 observed hours; idle 99.8% of observed hours | in-use |
| volume | vol-0dba752186e34e08c | us-east-1 | 6.07 | 59 observed hours; idle 99.8% of observed hours | in-use |
| volume | vol-0f2da5c82d0de1378 | us-east-1 | 6.07 | 39 observed hours; idle 99.2% of observed hours | in-use |
| volume | vol-00cbb7ba932dbd3a4 | us-east-1 | 6.07 | 33 observed hours; idle 99.7% of observed hours | in-use |
| volume | vol-0f9efeb41e207d738 | us-east-1 | 6.07 | 33 observed hours; idle 99.8% of observed hours | in-use |
| volume | vol-014b3f723fb89dc63 | us-east-1 | 6.07 | 33 observed hours; idle 99.7% of observed hours | in-use |
| volume | vol-0c26833469cf6995a | us-west-2 | 4.23 | no CloudWatch datapoints in window | in-use |
| load_balancer | lsmc-mvp-dev-alb | us-west-2 | 3.24 | not collected for this resource type | active |
| bucket | lsmc-illumina-public-data | us-west-2 | 0.58 | 0.124 TiB; request metrics not enabled | live |
| snapshot | snap-053909bfd492a6457 | ap-south-1 | 0.54 | not collected for this resource type | completed |
| snapshot | snap-07690eaa1400bc7f6 | us-east-1 | 0.30 | not collected for this resource type | completed |
| snapshot | snap-0356dd0198dfe4b00 | us-west-2 | 0.30 | not collected for this resource type | completed |
| load_balancer | lsmc-mvp-v1-labcore-alb | us-west-2 | 0.18 | not collected for this resource type | active |
| volume | vol-09454929e2c583ae7 | us-east-1 | 0.14 | 336 observed hours; idle 100.0% of observed hours | in-use |
| volume | vol-0b6a14b3d2c01264d | us-west-2 | 0.14 | 336 observed hours; idle 100.0% of observed hours | in-use |
| volume | vol-0af8f94e0cd058ddf | us-west-2 | 0.14 | 336 observed hours; idle 99.9% of observed hours | in-use |
| volume | vol-0b98b1e8d330cca41 | us-west-2 | 0.04 | 336 observed hours; idle 100.0% of observed hours | in-use |
| bucket | cdk-hnb659fds-assets-108782052779-us-east-1 | us-east-1 | 0.03 | not collected for this resource type | live |
| bucket | lsmc-aws-config-108782052779 | us-west-2 | 0.03 | 0.002 TiB; request metrics not enabled | live |
| bucket | parallelcluster-4da281c1dc024f1c-v1-do-not-delete | us-west-2 | 0.03 | 0.000 TiB; request metrics not enabled | live |
| bucket | aquarium-tfstate-dev | us-west-2 | 0.02 | not collected for this resource type | live |
| bucket | aquarium-tfstate-prod | us-west-2 | 0.02 | not collected for this resource type | live |
| bucket | cdk-hnb659fds-assets-108782052779-us-west-2 | us-west-2 | 0.02 | not collected for this resource type | live |

Resource Explorer separately returned **1,612 untagged indexed entries** in its three indexed regions. That population is dominated by 510 EC2 fleets, 232 security-group rules, 222 spot requests, 137 ECR repositories, and 79 RDS cluster snapshots; it is useful for ownership cleanup but is not a deletion or savings list.

## Method And Definitions

- **Cost:** Cost Explorer `UnblendedCost`; June 1-30 is final and July 1-14 is estimated. Grouped service totals reconcile exactly to direct totals.
- **Untagged:** zero non-AWS tags in current direct service inventory.
- **Coverage:** 21 enabled regions for EC2/EBS/EIP/NAT, FSx, RDS/Aurora, ELBv2, and S3; Resource Explorer supplementation only in `us-west-2`, `us-east-1`, and `us-east-2`.
- **EC2 busy share:** `vCPUs x 5/60 x CPUUtilization%`, summed over 5-minute points, divided by measured vCPU-hours.
- **NAT traffic:** sum of four directional byte counters; this is not equivalent to billable bytes and can double-count a flow.
- **S3 utilization:** latest daily bucket size/object count. Request metrics were not enabled for the top buckets.

## Recommendations

1. Identify and throttle the automation responsible for the 63,060 Cost Explorer API requests.
2. Review the three `dayhoff-lsmcq7` instances and untagged `labcore-dev-instance-1` with service owners before any resize/stop decision.
3. Confirm whether the four zero-traffic NAT gateways are required for DR; if not, prepare a separate destructive-change proposal. Tag the active untagged NATs now only through an approved tagging change.
4. Apply ownership, cost-center, and lifecycle tags to the 66 direct untagged resources, starting with `lsmc-public-ont-data`, the two RDS instances, and the cost-bearing NAT/EBS resources.
5. Review S3 lifecycle/storage-class policy for the 218 TiB sequencing bucket and 61 TiB analysis bucket.
6. Use an explicitly read-only assumed role for future audits instead of root-profile credentials.

## Limitations And Open Questions

- Missing metrics are labeled missing, never interpreted as idle.
- Several billed resources were already deleted, so only retained historical metrics are available.
- CPU, connection, and byte counters do not establish safe deletion or rightsizing.
- Which automation is issuing the Cost Explorer calls?
- Are the zero-connection RDS instances retained for standby/recovery objectives?
- Are the zero-traffic NAT gateways intentional DR capacity?
- Which S3 buckets are authoritative archives versus working copies eligible for colder lifecycle tiers?

## Evidence

- Canonical MCP payload: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/artifact.json`
- Direct inventory: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/inventory.csv`
- Untagged current resources: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/derived_untagged_resources.csv`
- Cost/resource evidence: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/derived_high_cost_resources.csv`
- EC2 cluster sample: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/derived_ec2_clusters.csv`
- Command audit records: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/command_records.json`
- Full resource lifecycle: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/lifecycle_resources.csv`
- Cluster lifecycle: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/lifecycle_clusters.csv`
- CloudFormation lifecycle: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/lifecycle_cloudformation_stacks.csv`
- Lifecycle command audit: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/lifecycle_command_records.json`
- jemx3 exact evidence: `docs/aws_readonly_cost_utilization_20260715T234717Z_assets/data/jemx3_lifecycle_evidence.json`
