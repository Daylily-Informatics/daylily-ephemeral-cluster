# FSx Scratch_2 vs Persistent_1 Analysis Ledger

Created: 2026-07-14T15:15:43Z

Objective: quantify the cost, configuration/behavior change, and expected performance impact of changing DYEC's cluster-owned FSx for Lustre deployment from `SCRATCH_2` to `PERSISTENT_1`.

Decision scope:

- Region: `us-west-2`, matching the active DYEC templates and recent LSMC clusters.
- Storage type: SSD.
- Capacity comparisons: current default-sized 4,800 GiB plus recent 12,000 GiB and 14,400 GiB cluster sizes.
- Persistent_1 throughput tiers: 50, 100, and 200 MB/s/TiB; 200 MB/s/TiB is the nominal-throughput match for Scratch_2.
- No AWS resources, cluster configuration, budgets, or running workflows will be changed by this analysis.

## Gate 0 inventory and baseline

- Checkout: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch/ref inspected: `jem-dev` at `1cd5242fdb43cf9cb876e515edffe043a60be526`
- Existing unrelated untracked plan artifacts were present and are not modified by this work.
- The seven active/usable `us-west-2` Intel, RHEL, and DRAGEN templates inspected all specify `DeploymentType: SCRATCH_2` and omit `PerUnitStorageThroughput`.
- Active Intel template tests explicitly enumerate four `us-west-2` Intel AZ templates.
- Cluster creation substitutes storage capacity and deletion policy, but deployment type is currently a template constant.
- The packaged create template prompts with a 4,800 GiB FSx default; recent ledgers also show 12,000 and 14,400 GiB Scratch_2 systems.
- DYEC's data-plane contract treats S3 as durable and `/fsx/analysis_results` as local to the cluster filesystem until an explicit export succeeds.

## Execution ledger

| ID | Work item | Status | Evidence / terminal note |
|---|---|---|---|
| G0 | Record repo/config/lifecycle baseline | SUCCESS | Baseline above; active template, create workflow, packaged-default tests, DRA strategy, delete workflow, and quota validation inspected. |
| COST | Resolve current official us-west-2 prices and calculate capacity/time scenarios | SUCCESS | AWS Price List API rates checked on 2026-07-14 and independently recomputed below. Repository retrospective costs for 12,000 and 14,400 GiB Scratch_2 agree exactly with the model. |
| CONFIG | Determine exact code/config/test/doc changes | SUCCESS | The literal switch is small but duplicated across 20 active source templates and 20 packaged mirrors. A supported per-cluster choice also needs two validated config inputs and conditional rendering because throughput must be present for Persistent_1 and absent for Scratch_2. |
| BEHAVIOR | Determine lifecycle, backup, replacement, DRA, delete, and export behavior changes | SUCCESS | Managed Persistent_1 with `DeletionPolicy: Delete` preserves the existing operator lifecycle and DRA/export contract; cross-cluster retention is a separate, materially larger architecture. Existing file systems cannot be converted in place. |
| PERF | Compare documented throughput, durability, recovery, and expected workload effects | SUCCESS | Persistent_1 200 matches Scratch_2's nominal read-disk throughput and improves documented write/network baselines; lower tiers can materially slow sustained storage-bound phases. No DayOA wall-time percentage is claimed without an A/B canary. |
| QA | Independently validate calculations, claims, and caveats | SUCCESS | Price rows were independently recomputed, repository retrospective figures cross-check the Scratch_2 model, source claims are linked to official AWS documentation, and the rendered report passed artifact validation. |
| REPORT | Deliver decision-ready report artifact and concise handoff | SUCCESS | Decision report rendered with a monthly-cost chart and documented-performance comparison; concise handoff delivered with the durable ledger. |

## Completion gate

Objective is complete only when every row above is terminal, calculations are reproducible from cited rates, the difference between nominal FSx capability and observed DayOA runtime is explicit, and the final report distinguishes a same-lifecycle deployment-type switch from a true cross-cluster persistent-filesystem architecture.

Completion state: all rows are terminal and the analysis objective is complete. No AWS resources, DYEC configuration, budgets, or workflows were changed, and no performance canary was run.

## Cost evidence and calculations

Current AWS Price List API products for `AmazonFSx`, `us-west-2`, `CreateFileSystem:Lustre`, checked 2026-07-14:

| Deployment / throughput | Usage type | USD per provisioned GB-month | Difference vs Scratch_2 |
|---|---|---:|---:|
| Scratch_2 SSD | `USW2-Storage` | $0.14 | baseline |
| Persistent_1 SSD, 50 MB/s/TiB | `USW2-Storage.SSD.50` | $0.14 | 0% |
| Persistent_1 SSD, 100 MB/s/TiB | `USW2-Storage.SSD.100` | $0.19 | +35.7% |
| Persistent_1 SSD, 200 MB/s/TiB | `USW2-Storage.SSD.200` | $0.29 | +107.1% |

Source: <https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonFSx/current/us-west-2/index.json>. AWS says provisioned storage is billed by average provisioned GB-month and prorated by the second: <https://aws.amazon.com/fsx/lustre/pricing/>.

Using AWS's 30-day/720-hour monthly convention, `cost = capacity_GB * rate * active_hours / 720`:

| Capacity | Tier | Cost/hour | Cost/day | Cost/30-day month | Delta/month vs Scratch_2 |
|---:|---|---:|---:|---:|---:|
| 4,800 | Scratch_2 or P1-50 | $0.9333 | $22.40 | $672 | $0 |
| 4,800 | P1-100 | $1.2667 | $30.40 | $912 | +$240 |
| 4,800 | P1-200 | $1.9333 | $46.40 | $1,392 | +$720 |
| 12,000 | Scratch_2 or P1-50 | $2.3333 | $56.00 | $1,680 | $0 |
| 12,000 | P1-100 | $3.1667 | $76.00 | $2,280 | +$600 |
| 12,000 | P1-200 | $4.8333 | $116.00 | $3,480 | +$1,800 |
| 14,400 | Scratch_2 or P1-50 | $2.8000 | $67.20 | $2,016 | $0 |
| 14,400 | P1-100 | $3.8000 | $91.20 | $2,736 | +$720 |
| 14,400 | P1-200 | $5.8000 | $139.20 | $4,176 | +$2,160 |

For an eight-hour 4,800 GiB cluster, the incremental FSx cost is about $2.67 at P1-100 or $8.00 at P1-200. This is FSx storage cost only; it does not change EC2, S3, data-transfer, backup, or optional metadata-IOPS charges.

Cross-check: `docs/AWS_3month_retrospective_cost_analysis.md` already prices 12,000 GiB Scratch_2 at $1,680/month and 14,400 GiB at $2,016/month, exactly matching $0.14/GB-month.

## Configuration impact

### Managed Persistent_1 with the current cluster lifecycle

Minimum rendered ParallelCluster change:

```yaml
FsxLustreSettings:
  StorageCapacity: ${REGSUB_FSX_SIZE}
  DeploymentType: PERSISTENT_1
  PerUnitStorageThroughput: 200
  DeletionPolicy: ${REGSUB_SAVE_FSX}
```

AWS ParallelCluster requires `PerUnitStorageThroughput` for Persistent_1 and permits 50, 100, or 200 MB/s/TiB for SSD. It also says deployment type and throughput cannot be changed by a cluster update. Source: <https://docs.aws.amazon.com/parallelcluster/latest/ug/SharedStorage-v3.html>.

Current DYEC impact:

- 20 active AZ-scoped source templates hard-code `SCRATCH_2`; all 20 packaged mirrors match those source templates. A literal global switch therefore touches 40 template files (20 source plus 20 packaged copies), adding the throughput line to each.
- A maintainable per-cluster choice should instead add explicit `fsx_deployment_type` and `fsx_per_unit_storage_throughput` configuration, validate the allowed pair, and render the throughput field only for Persistent_1. DYEC must fail hard on a missing/invalid pair; it should not infer a tier.
- Renderer required substitutions and tests, create-workflow tests, packaged-template parity tests, docs/examples, and the cluster-shape/quota tests need updates.
- The existing AWS validator already branches separately for Scratch and Persistent_1 filesystem/storage quotas based on rendered YAML, so its quota model does not need a redesign.
- The existing DRA/run-mount code rejects only `SCRATCH_1`; Persistent_1 remains compatible with the current startup reference DRA, on-demand run/control/staging DRAs, and explicit export DRAs.

Engineering size estimate:

- Hard-coded global switch: small, roughly half to one engineering day locally, but creates no safe per-cluster choice.
- Supported configurable mode with tests/docs: small-to-medium, roughly one to two engineering days locally, plus a new-cluster canary and workflow benchmark.
- No existing cluster should be updated in place; launch a new exact-version test cluster because ParallelCluster marks deployment type and throughput changes as not allowed.

### A filesystem that actually survives cluster deletion

`PERSISTENT_1` does not by itself mean cross-cluster lifetime. With DYEC's current `DeletionPolicy: Delete`, ParallelCluster still deletes the managed filesystem and its data with the cluster. Keeping it requires `Retain`, followed by a later cluster mounting the existing `FileSystemId`; ParallelCluster says that when `FileSystemId` is used, only `MountDir` and `FileSystemId` apply.

That is a materially larger change: explicit retained-FSx ownership and cost accounting, file-system-ID handoff, same-AZ/network/security validation, DRA ownership and reuse rules, deletion workflow changes, stale-resource reporting, and a distinct destructive cleanup path. Estimate: approximately one to two weeks including live lifecycle tests, not a template-only change.

## Behavior impact

- Persistent_1 replicates SSD data within one Availability Zone and automatically replaces failed infrastructure. Scratch_2 does not replicate data; a server/disk failure can cause immediate I/O errors for affected files and the failed server is not replaced. Source: <https://docs.aws.amazon.com/fsx/latest/LustreGuide/using-fsx-lustre.html>.
- Same managed lifecycle: mount remains `/fsx`; reference/run/control/staging/output DRA paths remain the same; explicit output export remains required; the DRA limit remains eight; delete approval remains destructive while `DeletionPolicy` is `Delete`.
- Persistent_1 cannot be created in the AWS console; AWS documents CLI/API creation only. ParallelCluster uses the API path, so this is an operator-console limitation rather than a DYEC blocker.
- Automatic FSx backups do not become available under DYEC's present design because AWS supports persistent Lustre backups only when the file system is not linked to S3. DYEC links the startup reference DRA and creates additional DRAs. Source: <https://docs.aws.amazon.com/fsx/latest/LustreGuide/using-backups-fsx.html>.
- Persistent replication reduces hardware-failure risk, but it does not prove that observed Lustre client stalls, S3/DRA hydration, metadata contention, full filesystems, or application I/O patterns will improve.

## Performance evidence and interpretation

AWS's current designed per-TiB SSD characteristics are:

| Tier | Network baseline | Network burst | Disk baseline | Disk burst | RAM cache |
|---|---:|---:|---:|---:|---:|
| Scratch_2 | 200 MB/s | 1,300 MB/s | 200 MB/s read; 100 MB/s write | none listed | 6.7 GiB |
| Persistent_1 50 | 250 MB/s | 1,300 MB/s | 50 MB/s | 240 MB/s | 2.2 GiB |
| Persistent_1 100 | 500 MB/s | 1,300 MB/s | 100 MB/s | 240 MB/s | 4.4 GiB |
| Persistent_1 200 | 750 MB/s | 1,300 MB/s | 200 MB/s | 240 MB/s | 8.8 GiB |

Source: <https://docs.aws.amazon.com/fsx/latest/LustreGuide/ssd-storage.html>. AWS labels Persistent_1 as a previous-generation SSD option.

Decision interpretation:

- P1-200 is the closest safe comparison. Its documented disk-read baseline matches Scratch_2, disk-write baseline is twice Scratch_2's listed write baseline, network baseline is higher, and network burst is the same. It should not be presumed slower; storage-bound writes may improve.
- P1-100 can be up to 2x slower for sustained read-disk-bound phases, while its 100 MB/s disk baseline matches Scratch_2's listed write baseline. Bursty workloads may see less difference because P1 can burst to 240 MB/s/TiB.
- P1-50 can be up to 4x slower for sustained read-disk-bound phases and about 2x slower against Scratch_2's listed write baseline. It is price-neutral but not performance-neutral.
- End-to-end DayOA runtime will move less than the storage-bound phase unless FSx is the dominant bottleneck. A defensible runtime percentage requires the same DayOA ref, manifest, cluster shape, data state, and concurrency on Scratch_2 and P1, with CloudWatch FSx metrics plus rule benchmark TSVs.

Recommended canary: Persistent_1 at 200 MB/s/TiB on a new 4,800 GiB cluster, `DeletionPolicy: Delete`, exact pinned DYEC/DayOA refs, and one representative read-heavy plus one write-heavy workflow. This isolates the durability/performance question without introducing retained-filesystem lifecycle changes.
