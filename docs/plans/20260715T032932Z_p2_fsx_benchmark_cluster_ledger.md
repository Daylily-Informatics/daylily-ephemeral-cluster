# PERSISTENT_2 FSx Benchmark Cluster Ledger

- Created: `2026-07-15T03:29:32Z`
- AWS account: `108782052779`
- AWS profile: `lsmc`
- AWS region/AZ: `us-west-2` / `us-west-2d` (`usw2-az4`)
- DYEC worktree: `/Users/jmajor/projects/lsmc/.worktrees/dyec-p2-fsx-canary-20260715`
- DYEC branch/ref: `codex/p2-fsx-canary` at `fb308fbebbc6664c79b99453515a4b37f36c2e82`
- Proposed cluster: `ifx-p2-250-0714`
- Objective: create a like-for-like Intel DayOA cluster with higher-performance FSx for Lustre, verify the read/write and DRA contracts, then run a pinned A/B workload and report observed elapsed-time and cost differences.

## Gate 0 inventory and decisions

No AWS resources were created, updated, or deleted by this ledger or the implementation work recorded before the explicit execution gates below.

| Surface | Current evidence | Decision |
| --- | --- | --- |
| Source cluster | `ifx-sacctoff-1037`, created `2026-07-14T18:36:35Z`, ParallelCluster `3.15.0`, Intel template, `r7i.2xlarge` headnode, `us-west-2d`. | Mirror its current compute, subnet, IAM, boot-config, budget-tag, and Slurm topology for the storage A/B. |
| Source FSx | `fs-006b74a47b7602930`, `AVAILABLE`, `SCRATCH_2`, SSD, `4,800 GiB`, mounted at `/fsx`, reference DRA only. | Preserve capacity, SSD type, mountpoint, and reference DRA semantics. Change only the explicitly recorded FSx performance/lifecycle attributes. |
| Target FSx | Not yet created. | `PERSISTENT_2`, SSD, `4,800 GiB`, `250 MB/s/TiB`, Lustre `2.15`, enhanced metadata `AUTOMATIC`, AWS-managed FSx encryption, DYEC-owned and cluster-bound. No tier/AZ/capacity fallback. |
| Target storage cost | AWS Price List effective `2026-06-01`: `$0.210/GB-month` for Oregon P2-250, versus `$0.140/GB-month` for Scratch. | P2 costs `$1,008/month` equivalent, `$1.40/hour`, or `$11.20/8h`; Scratch costs `$672/month`, `$0.9333/hour`, or `$7.47/8h`; 8-hour incremental storage cost is `$3.73`. |
| FSx quotas | Oregon live Service Quotas: 100 PERSISTENT_2 file systems and 100,800 GiB PERSISTENT_2 capacity. | 4,800 GiB target fits both quotas. An actual create in `us-west-2d` remains the capacity proof. |
| Regional cluster cap | Gate 0 initially found five records. A refreshed fail-closed create check at `2026-07-15T03:45Z` found 13 non-deleted records after eight Ursa service clusters were created between `02:40Z` and `02:47Z`: `ursa-m-rgx-bw2b`, `bwbs`, `bwm6`, `bwxm`, `bx62`, `bxfg`, `bxrx`, and `by1b`. | Target creation projects 14 against the default cap of five. Deleting `ursa-m-rgx-br75` alone is no longer sufficient. Do not delete the eight new service-owned clusters or raise the cap silently. |
| Benchmark truth | No P2 cluster or A/B run exists yet. | Do not claim a wall-time speedup until the same pinned DayOA ref, manifest, targets, compute limits, concurrency, and data state have completed on both filesystems. |

## Execution ledger

| ID | Requirement | Status | Approval gate | Evidence / terminal note |
| --- | --- | --- | --- | --- |
| G0-001 | Record repo, live source cluster, FSx, quota, price, and regional-cap baseline. | `SUCCESS` | Gate 0 | Gate 0 table above. |
| IMP-001 | Implement an explicit supported P2 lifecycle: deterministic FSx/SG/DRA creation, external `FileSystemId` render, receipt/state, cluster-bound delete handling, and no fallback. | `SUCCESS` | None | Implemented on the isolated branch; Scratch behavior is unchanged unless P2 is explicitly selected, and every P2 field is exact/fail-closed. |
| IMP-002 | Add focused unit/integration-contract tests and run repository validation. | `SUCCESS` | IMP-001 | `ruff check` passed; full suite: `1522 passed, 11 skipped` in `61.86s`. |
| CAP-001 | Authorize a regional capacity override for the exact projected count, or reduce the live count through separately approved cleanup. | `SUCCESS` | Explicit user choice | User explicitly authorized regional cap `14` and both DYEC cap-risk acknowledgements for `ifx-p2-250-0714` after disclosure that live count is 13 and the requested create projects 14. |
| DEL-001 | Delete previously requested `ursa-m-rgx-br75`, if separately confirmed after exact-effect disclosure. | `BLOCKED` | Second destructive approval | Refreshed at `2026-07-15T03:37Z` with empty Slurm queue, no controller/tmux process, no compute nodes, and its FSx still `AVAILABLE`; deletion would reduce count only from 13 to 12 and does not unblock the target create. |
| PRE-001 | Run DYEC preflight and pcluster dry-run for the exact target configuration. | `BLOCKED` | CAP-001 | DYEC read-only preflight passed all 12 checks. PCluster dry-run requires the real external `FileSystemId`, which is intentionally not created before the cap gate is resolved. |
| AWS-001 | Create the P2 FSx, shared security group, reference DRA, and ParallelCluster. | `PENDING` | PRE-001 | User requested cluster creation; no regional-cap override, budget-cap increase, deletion, or fallback is implied. |
| VER-001 | Verify create completion, exact FSx attributes/tags, `/fsx` read/write from head and compute, DRA/reference reads, Slurm `sinfo`, `squeue`, `sacct`, and sweep-preservation tags. | `PENDING` | AWS-001 | Read/write probes must use dedicated disposable paths, not `/fsx/analysis_results/**`. |
| PERF-001 | Run the pinned like-for-like DayOA workload through `dy-r` in a persistent headnode tmux with analysis-root visit/lock controls. | `PENDING` | VER-001 plus exact workload pin | No raw Snakemake. |
| PERF-002 | Collect combined benchmark TSVs, controller wall time, Slurm/accounting evidence, and FSx CloudWatch metrics; calculate time and cost deltas. | `PENDING` | PERF-001 | Separate task wall time, controller elapsed time, startup/pending time, and storage cost. |
| CLOSE-001 | Bring every row to a terminal state and state whether the objective is complete. | `PENDING` | All rows | The objective is not complete while the live cluster and A/B proof do not exist. |

## Exact no-fallback contract

- Do not substitute `PERSISTENT_1`, Scratch, Intelligent-Tiering, another throughput tier, a smaller/larger filesystem, another AZ, or another cluster template.
- Do not reuse or attach an unrelated existing FSx filesystem.
- Do not increase the five-cluster regional cap without a separate explicit authorization for that capacity/cost-risk override.
- Do not increase an existing AWS Budget or DYEC cost-center cap without restating old/new values and receiving the required second approval.
- Preserve S3 as the durable data contract. The target filesystem is performance infrastructure, not the sole durable copy of benchmark outputs.

## Live execution events

- `2026-07-15T04:52Z`: first cap-14 attempt stopped before AWS mutation because `codex/p2-fsx-canary` was not published on `origin`; branch publication was required by the exact headnode bootstrap contract.
- `2026-07-15T04:53:45Z`: canary commit `904c1c9b` was created and pushed to `origin/codex/p2-fsx-canary`; this is a canary branch, not a release or tag.
- `2026-07-15T04:54:56Z`: second attempt passed cap `14`, all 14 create preflight checks, resource resolution, boot-bundle publication, and budget ensure. FSx rejected the create request because the SHA-256 idempotency token was 64 characters while the API maximum is 63. No ParallelCluster stack or FSx filesystem was created. Exact partial state: reused global budget `daylily-global` at `$600`; created/reused cluster budget `ifx-p2-250-0714` at `$200`; created tagged client security group `sg-0033f808bf4e7559d`. The retry must reuse these exact resources.

## Completion condition

The objective is complete only after the exact cluster and FSx attributes are live and verified, the read/write and reference-DRA contracts pass on head and compute nodes, the pinned A/B workload reaches a terminal result on both storage variants, and observed elapsed-time plus cost deltas are recorded with their evidence. Creating the cluster alone is not completion.
