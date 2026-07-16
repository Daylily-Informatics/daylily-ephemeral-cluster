# DYEC Regional FSx Persistent_2 Solution Proposal

Created: 2026-07-14T15:59:42Z

Status: PROPOSED; filed as GitHub issue `lsmc-bio/daylily-ephemeral-cluster#13`

Decision: implement DYEC-owned, cluster-bound Amazon FSx for Lustre `PERSISTENT_2` SSD filesystems at 250 MB/s/TiB, Lustre 2.15, with enhanced metadata configured in `AUTOMATIC` mode at creation. Pass the resulting `FileSystemId` to AWS ParallelCluster as external shared storage. Keep S3 and explicit exports as the durable data contract. Do not automatically substitute another deployment type, throughput tier, filesystem, region, or Availability Zone.

This supersedes `PERSISTENT_1` as the recommended target. Persistent_1 remains technically portable, but it is the previous-generation option; P2-250 has better documented disk performance and lower current storage pricing than P1-200 in every DYEC core region inspected.

No AWS resources, running clusters, budgets, or production configuration were changed while preparing this proposal.

## Gate 0: current surface

- Checkout: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Ref inspected: `jem-dev` at `1cd5242fdb43cf9cb876e515edffe043a60be526`
- Current active source templates: 20, with 20 packaged mirrors.
- Current FSx contract: ParallelCluster-managed `SCRATCH_2`, capacity substituted by DYEC, and `DeletionPolicy` substituted by DYEC.
- Current durability contract: S3 is durable; `/fsx/analysis_results` is local to the cluster until explicit export succeeds.
- Current DRA contract: FSx for Lustre 2.12/2.15 DRAs, maximum eight associations, with reference and run-time associations created around the cluster lifecycle.
- Current failure mode relevant to this decision: recent DayOA work has observed Lustre metadata/RPC stalls even while the FSx control plane reports healthy. The proposal therefore preserves an explicit path to observable and scalable P2 metadata IOPS.

## Exact core-region and AZ catalog

The phrase `us-*`, `eu-central-*`, and `ap-south-*` is not accepted as service-side discovery. The implementation must use this checked-in catalog and fail when a requested AZ is absent.

| Region | Canonical Intel compute AZs in the repo | Other active variants |
|---|---|---|
| `us-east-2` | `us-east-2a`, `us-east-2b`, `us-east-2c` | none |
| `us-west-1` | `us-west-1a`, `us-west-1b` | none |
| `us-west-2` | `us-west-2a`, `us-west-2b`, `us-west-2c`, `us-west-2d` | RHEL in `2b`/`2c`; DRAGEN in `2b` |
| `eu-central-1` | `eu-central-1a`, `eu-central-1b`, `eu-central-1c` | RHEL in `1b`/`1c` |
| `ap-south-1` | `ap-south-1a`, `ap-south-1b`, `ap-south-1c` | none |

There are 15 unique core compute AZs. `eu-central-2`, `ap-south-2`, other `us-*` regions, and Local Zones are not currently represented by canonical DYEC templates and are therefore out of scope until deliberately added to the catalog with subnet, template, pricing, quota, and canary evidence.

AWS currently documents `PERSISTENT_2`, `PERSISTENT_1`, and `SCRATCH_2` in all five cataloged regions. Regional support does not guarantee momentary physical capacity in every AZ. Only an actual create in the selected subnet proves that AZ at that time; DYEC must preserve the exact AWS failure rather than moving or downgrading silently.

## Proposed filesystem contract

```yaml
fsx_owner: DYEC
fsx_lifecycle: CLUSTER_BOUND
fsx_deployment_type: PERSISTENT_2
fsx_storage_type: SSD
fsx_lustre_version: "2.15"
fsx_throughput_mbps_per_tib: 250
fsx_metadata_mode: AUTOMATIC
fsx_encryption_mode: AWS_MANAGED_FSX
fsx_fs_size: 4800
```

Contract rules:

1. Every key above is explicit and validated. There is no inferred default, legacy alias, or fallback profile.
2. `fsx_fs_size` remains 1,200 GiB, 2,400 GiB, or a multiple of 2,400 GiB at or above 4,800 GiB.
3. The selected private subnet must resolve to the requested AZ and its account-stable Availability Zone ID. Both values are recorded in the receipt.
4. The initial KMS policy is explicitly the regional AWS-managed FSx key. A custom KMS key is a later explicit mode, never auto-discovered.
5. P2 metadata configuration is supplied at creation. `AUTOMATIC` includes 6,000 metadata IOPS for 4,800-9,600 GiB and 12,000 IOPS for 12,000-45,600 GiB. It can later be raised explicitly if CloudWatch evidence justifies it.
6. The filesystem is cluster-bound by policy but not owned by the ParallelCluster stack. DYEC controls both creation and the separately approved delete operation.
7. S3 remains authoritative. A persistent filesystem is not treated as a replacement for output export, a backup, or a cross-cluster data repository.

## Why DYEC should own the filesystem

ParallelCluster can directly create P2, but its current `FsxLustreSettings` surface does not expose FSx `MetadataConfiguration`. Enhanced P2 metadata must be specified when the filesystem is created if it is to be monitored and increased later. Creating FSx through the FSx API first and then passing `FileSystemId` to ParallelCluster gives DYEC the required metadata configuration.

The rendered ParallelCluster templates become structurally simpler:

```yaml
SharedStorage:
  - MountDir: /fsx
    Name: fsx
    StorageType: FsxLustre
    FsxLustreSettings:
      FileSystemId: ${REGSUB_FSX_FILE_SYSTEM_ID}
```

When `FileSystemId` is supplied, ParallelCluster treats the filesystem as external and does not create or delete it. The duplicated deployment type, capacity, throughput, and deletion policy disappear from all compute templates; the FSx creation contract lives once in DYEC code.

## Create state machine and receipts

```text
REQUEST_VALIDATED
  -> FSX_CREATE_SUBMITTED
  -> FSX_AVAILABLE
  -> BASE_DRA_CREATE_SUBMITTED
  -> BASE_DRA_AVAILABLE
  -> PCLUSTER_CREATE_SUBMITTED
  -> CLUSTER_ACTIVE
```

Required behavior:

- Use a deterministic client request token for FSx creation and a durable receipt keyed by cluster request ID. Re-running the same request resumes observation of that exact filesystem; it does not create another one.
- Record filesystem ID, deployment type, storage size, throughput, Lustre version, metadata mode/IOPS, KMS key, subnet, AZ name, AZ ID, security groups, tags, DRA IDs, cluster name, profile, region, and creation timestamps.
- Use explicit lifecycle polling. A short CLI timeout is not failure proof and must not trigger another create.
- If FSx or DRA creation fails, stop with the exact AWS state and error. Do not create Scratch_2, P1, a smaller filesystem, or a filesystem in another AZ.
- If the ParallelCluster create fails after FSx exists, mark the receipt `ORPHANED_NEEDS_CLEANUP`; do not silently delete the filesystem. Generate the exact cleanup dry-run for separate destructive approval.

## Delete and retention behavior

`dyec delete --dry-run` must enumerate the cluster, FSx filesystem, every DRA, unexported analysis roots, filesystem lifecycle state, and S3 effects. A live deletion remains gated by the existing second explicit approval.

For `CLUSTER_BOUND`:

1. verify controller/Slurm state;
2. verify required exports and explicit no-export decisions;
3. delete the ParallelCluster stack;
4. verify cluster absence;
5. delete DRAs and the DYEC-owned FSx only after the separate destructive scope is approved;
6. verify terminal absence across ParallelCluster, CloudFormation, EC2, FSx, and DRAs;
7. close the receipt.

`RETAINED` is not part of the initial release. It requires a distinct owner, cost center, expiry/renewal policy, remount workflow, and delete command. The implementation must not overload `CLUSTER_BOUND` or the old `auto_delete_fsx` key to imply retention.

## Ursa Recent Cluster Create Jobs

Extend the existing Ursa **Recent Cluster Create Jobs** records so the FSx lifecycle is visible without opening AWS consoles or inferring state from the cluster alone. Each record should expose:

- cluster request/job ID and cluster name;
- selected region, AZ name, and account-stable AZ ID;
- deterministic FSx request token and filesystem ID;
- deployment type, Lustre version, capacity, throughput tier, metadata mode, and provisioned metadata IOPS;
- DRA IDs and lifecycle states;
- `FSX_CREATE_SUBMITTED`, `FSX_AVAILABLE`, `DRA_AVAILABLE`, `PCLUSTER_CREATE_SUBMITTED`, `CLUSTER_ACTIVE`, failure, and orphan states;
- the exact AWS error without fallback masking;
- regional hourly/month-equivalent cost estimate and actual active duration when available; and
- identifiers needed to inspect the durable DYEC lifecycle receipt.

## Cost guardrail by core region

Current public on-demand storage prices checked 2026-07-14. Values below use 4,800 GiB and AWS's 720-hour monthly convention. Metadata mode is `AUTOMATIC`, so there is no separately billed metadata IOPS above the included amount.

| Region | Scratch_2 $/GB-month | P2-250 $/GB-month | 4.8 TiB monthly uplift | Eight-hour uplift | P1-200 $/GB-month |
|---|---:|---:|---:|---:|---:|
| `us-east-2` | $0.140 | $0.210 | $336.00 | $3.73 | $0.290 |
| `us-west-1` | $0.154 | $0.282 | $614.40 | $6.83 | $0.357 |
| `us-west-2` | $0.140 | $0.210 | $336.00 | $3.73 | $0.290 |
| `eu-central-1` | $0.167 | $0.269 | $489.60 | $5.44 | $0.335 |
| `ap-south-1` | $0.140 | $0.240 | $480.00 | $5.33 | $0.290 |

P2-250 is 50%-83% more expensive than Scratch_2 across these regions, but 17%-27% cheaper than P1-200. The cost controller must calculate the price from the selected region, capacity, and active-hour estimate; a us-west-2 constant is not valid globally.

If 4,800 GiB metadata is later raised from the included 6,000 IOPS to 12,000 IOPS, the additional 6,000 IOPS currently add approximately $330-$414 per month-equivalent, or $3.67-$4.60 for eight hours depending on region. That change is evidence-driven and explicit, not part of the initial profile.

## Expected performance and regional caveat

AWS documents these designed per-TiB SSD characteristics:

| Deployment | Network baseline | Network burst | Disk baseline | Disk burst | RAM cache |
|---|---:|---:|---:|---:|---:|
| Scratch_2 | 200 MB/s | 1,300 MB/s | 200 read / 100 write MB/s | none listed | 6.7 GiB |
| P2-250 | 640 MB/s | 1,300 MB/s | 250 MB/s | 500 MB/s | 6.8 GiB |
| P1-200 | 750 MB/s | 1,300 MB/s | 200 MB/s | 240 MB/s | 8.8 GiB |

P2-250 is the recommended balanced tier because it exceeds Scratch_2's documented disk baseline, preserves similar cache per TiB, provides replicated storage, and supports enhanced metadata. It should not be represented as a guaranteed DayOA speedup until the canary matrix lands.

Regional caveat: AWS caps the documented persistent-filesystem network burst at up to 530 MB/s/TiB in Europe (Frankfurt), which is `eu-central-1`. Scratch_2 retains a higher short network burst on paper there. The Frankfurt acceptance test must therefore include both sustained read/write and burst-sensitive phases; P2 remains expected to win on sustained disk and resilience, but the EU wall-time result controls rollout.

## Implementation tracks

### Track A: schema, catalog, and validation (2-3 engineering days)

- Add a versioned, explicit FSx configuration contract and remove the old ambiguous `auto_delete_fsx` behavior from the new schema.
- Add the checked-in region/AZ capability catalog above, including AZ IDs resolved during account bootstrap.
- Extend `dyec aws validate` for P2 file count, storage, subnet IPs, FSx service-linked role, S3/DRA IAM, KMS mode, regional pricing, and expected cost.
- Fail before create on a missing template, subnet mismatch, missing price, missing quota, invalid configuration pair, or unsupported AZ.
- Add no-fallback regression tests.

### Track B: FSx orchestration and template boundary (3-4 engineering days)

- Add an FSx create module using the FSx API with P2-250, Lustre 2.15, metadata `AUTOMATIC`, exact subnet, security groups, tags, and deterministic client token.
- Persist create receipts and implement bounded lifecycle polling/resume.
- Replace the FSx create block in all 20 source templates and 20 packaged mirrors with the single `FileSystemId` mount contract.
- Add canonical-template and packaged-parity tests proving every active template renders the same FSx mount boundary.

### Track C: lifecycle, cost, and observability (2-3 engineering days)

- Integrate existing startup and dynamic DRA creation with the external filesystem ID.
- Extend delete inventory, export gates, destructive approval text, orphan reporting, and terminal verification to DYEC-owned FSx.
- Add CloudWatch reporting for metadata IOPS utilization, client connections, network throughput, disk throughput/IOPS, free storage, data repository age/queue, and server health.
- Add cost-center records for filesystem ID, regional rate, active seconds, and separately billed metadata IOPS.

Estimated implementation size: 7-10 engineering days before completing the live regional proof matrix.

## Required live proof matrix

No production default changes until every row is terminal.

| Gate | Scope | Required proof |
|---|---|---|
| FSX-AZ | all 15 unique cataloged AZs | create 1.2 TiB P2-250 in the exact subnet, verify P2/2.15/metadata/AZ ID, mount smoke, DRA smoke, then approved cleanup |
| INTEL-REGION | one Intel cluster in each of five regions | ParallelCluster mount, controller-independent read/write/stat/rename/delete tests, reference DRA, export DRA, CloudWatch metrics |
| RHEL | one `us-west-2` and one `eu-central-1` RHEL cluster | Lustre client, mount, DRA, and workflow smoke |
| DRAGEN | `us-west-2b` | Lustre client, mount, DRA, and non-destructive DRAGEN filesystem smoke |
| DAYOA-PERF | `us-west-2d` plus `eu-central-1` | same pinned DayOA ref, manifest, compute shape, concurrency, and data state on Scratch_2 and P2-250; benchmark TSVs and CloudWatch evidence |
| FAILURE | representative region | injected create failure, DRA failure, pcluster failure after FSx create, interrupted polling, resume, orphan inventory, approved cleanup |
| DELETE | representative region | export gate, exact destructive scope, second approval, cluster deletion, FSx/DRA deletion, terminal absence proof |

Rollout order:

1. ship code with P2 profile non-default and Scratch_2 still available only when explicitly selected;
2. prove all 15 AZ filesystem-level rows;
3. prove five Intel regional rows and variant rows;
4. complete DayOA A/B in Oregon and Frankfurt;
5. make P2-250 the explicit default in a separate release only if runtime, stability, and cost gates pass;
6. keep Scratch_2 as an explicit operator-selected profile during one release train, not an automatic fallback;
7. remove Scratch_2 only after the agreed deprecation gate.

## Acceptance thresholds

- No filesystem loss caused by an FSx server/disk failure in the canary window.
- No silent region/AZ, deployment-type, tier, capacity, or KMS substitution.
- P2-250 DayOA wall time no worse than 10% versus Scratch_2 on the selected representative workflows, unless explicitly accepted for a measured reliability benefit.
- Zero unexplained metadata/RPC stalls; metadata IOPS utilization and granular metadata operation metrics must be available in the evidence package.
- Export and deletion semantics remain explicit, auditable, and independently verifiable.
- Every regional price and quota is calculated from the selected region.
- Every filesystem and DRA created during canaries is either active with a named owner/expiry or terminally absent after approved cleanup.

## Sources

- AWS FSx deployment availability and behavior: <https://docs.aws.amazon.com/fsx/latest/LustreGuide/using-fsx-lustre.html>
- AWS ParallelCluster FSx shared-storage contract: <https://docs.aws.amazon.com/parallelcluster/latest/ug/SharedStorage-v3.html>
- AWS FSx SSD performance characteristics: <https://docs.aws.amazon.com/fsx/latest/LustreGuide/ssd-storage.html>
- AWS FSx P2 metadata performance: <https://docs.aws.amazon.com/fsx/latest/LustreGuide/managing-metadata-performance.html>
- AWS FSx metadata IOPS mapping: <https://docs.aws.amazon.com/fsx/latest/LustreGuide/performance.html>
- AWS DRA support: <https://docs.aws.amazon.com/cli/latest/reference/fsx/create-data-repository-association.html>
- AWS regional price lists: `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonFSx/current/<region>/index.json`

## Decision requested

Approve this architecture as the target for the next DYEC FSx change round. Approval authorizes implementation and read-only validation work; it does not authorize live filesystem/cluster creation, budget increases, canary cleanup, or other destructive AWS actions. Those retain their existing approval gates.

## GitHub ticket filing status

- Repository: `lsmc-bio/daylily-ephemeral-cluster`.
- Issue: <https://github.com/lsmc-bio/daylily-ephemeral-cluster/issues/13>.
- Title: `Improve DYEC FSx with region-portable P2 lifecycle and metadata controls`.
- Label: `enhancement`.
- Duplicate search on 2026-07-14 found no open FSx/P2 issue.
- The first create attempt was rejected with HTTP 410 because repository Issues were disabled.
- After explicit user approval, Issues were enabled on `lsmc-bio/daylily-ephemeral-cluster`, the setting was verified, and issue #13 was created successfully on 2026-07-14.
