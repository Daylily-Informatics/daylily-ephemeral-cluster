# Intel region-AZ partition validity execution ledger

## Objective

Expand the `sentieon-single` `us-west-2c` ParallelCluster template with an
8-vCPU local-NVMe partition, and make every active Intel cluster template
defined by DYEC valid for its exact availability zone. The current complete
active inventory is the 15 templates under `config/day_cluster/intel/` across
`us-*`, `ap-south-1`, and `eu-central-1`.
The source and packaged template copies must remain byte-identical. This work
changes future cluster configuration only; it does not update or administer
the live `sent-hg003-5x-0712` cluster.

## Gate 0 inventory

Controlling plan and ledger:
`docs/plans/20260714T151002Z_intel_az_partition_validity_ledger.md`

| Item | Baseline evidence |
|---|---|
| Repo | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster-sentieon-single`, branch `sentieon-single`, HEAD `11272166bff896800036b93f2959f29814381eea` |
| Dirty boundary | Pre-existing edits in Slurm-accounting source/tests and pre-existing runtime ledgers/scripts are preserved. No cleanup, reset, or unrelated staging is authorized. |
| Active Intel templates | 15 source templates and 15 packaged copies: `ap-south-1{a,b,c}`, `eu-central-1{a,b,c}`, `us-east-2{a,b,c}`, `us-west-1{a,b}`, and `us-west-2{a,b,c,d}` |
| Sentieon-single templates | One source and one packaged template, both for `us-west-2c` only |
| Sentieon queue baseline | `i96nvme,i128nvme,i192nvme,i384nvme`; requested `i8` is absent |
| Intel queue baseline | Existing templates include `i8`, 128/192 CPU and memory variants, and NVMe tiers, but lack `i96nvme`, which is part of the current DayOA CPU/NVMe placement contract |
| Capacity accounting | Existing config and quota logic has 8-, 128-, 192-, and 384-vCPU max-count families; there is no explicit 96-vCPU max-count family. Reusing a different tier would make quota demand incorrect and is prohibited. |
| AWS evidence boundary | EC2 instance-type offerings will be read from profile `lsmc` for each exact region-AZ before template mutation. No live AWS mutation is in scope. |
| Live workflow boundary | HG002 exact DayOA `11.0.3` is running independently on `sent-hg003-5x-0712`; this template work must not cancel, requeue, or reconfigure that run or cluster. |

Gate 0 sweep commands:

- `git status --short --branch`
- `rg --files config/day_cluster/intel`
- `rg --files daylily_ec/resources/payload/config/day_cluster/intel`
- queue-name and substitution scans over source, payload, renderer, config,
  validation, quota, and tests
- AWS `DescribeInstanceTypeOfferings` per exact availability zone

## Control ledger

| ID | Area | Requirement | Status | Category | Approval gate | Owner | Evidence | Root cause | Terminal note |
|---|---|---|---|---|---|---|---|---|---|
| AZ-001 | Inventory | Freeze target templates, repo dirt, queue baseline, and live-system boundary | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | Gate 0 inventory above records 15 Intel AZs, one sentieon AZ, missing partitions, and unrelated dirty files |  | Inventory frozen before template mutation |
| AZ-002 | AWS offerings | Record exact offered instance types for every queue in every target AZ | SUCCESS | contract_test | Gate 0 | orchestrator | Read-only profile `lsmc` `DescribeInstanceTypeOfferings`/`DescribeInstanceTypes` audit on `2026-07-14`: every listed type in every non-empty queue is offered in its exact AZ; all 15 AZs offer 17-31 eligible 96-vCPU local-NVMe Intel CPU types; `ap-south-1a/b` now offer `c8id.96xlarge,c8id.metal-96xl` while `ap-south-1c` and `us-west-1a/b` have no eligible 384-vCPU pool; `us-west-2c` offers four modern 8-vCPU Intel types with at least 1200 GB local NVMe (`i3en.2xlarge`, `i4i.2xlarge`, `i7i.2xlarge`, `i7ie.2xlarge`) |  | Live offering inventory completed without AWS mutation |
| AZ-003 | Capacity contract | Add an explicit 96-vCPU max-count/substitution/quota-demand family without fallback aliases | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Added required `max_count_96I_NVME` through config models, validation, rendering, create/preflight workflows, and Spot-vCPU demand. Missing values fail explicitly in both create paths. |  | The 96-vCPU tier is accounted independently; no alias or inferred fallback was added |
| AZ-004 | Sentieon us-west-2c | Add `i8` using only offered 8-vCPU instance-store types and the existing `/scratch` contract | SUCCESS | feature_implementation | Gate 2 | orchestrator | Source and payload now render `i8` with `i3en.2xlarge,i4i.2xlarge,i7i.2xlarge,i7ie.2xlarge`; all four pass exact-AZ offering, current Linux Spot, Intel x86_64, local-NVMe, and no-accelerator checks. |  | The queue uses `/scratch`, `MinCount: 0`, `MaxCount: 12`, and does not alter the existing four tiers |
| AZ-005 | Intel templates | Add `i96nvme`, retain only types offered in each exact AZ, and omit unsupported queues rather than emitting empty resources | SUCCESS | feature_implementation | Gate 2 | orchestrator | All 15 active Intel templates now contain an exact-AZ/current-Linux-Spot intersection of 17-31 `i96nvme` types. `i384nvme` is omitted in `ap-south-1a/b/c` and `us-west-1a/b`, where no eligible current Linux Spot pool exists; it remains in the other 10 AZs. No queue has an empty compute-resource list. |  | Complete active Intel inventory refreshed without touching archived templates |
| AZ-006 | Packaged payload | Keep every active source/payload template pair byte-identical | SUCCESS | contract_test | Gate 5 | orchestrator | Deterministic `--check` covered all 15 Intel pairs plus sentieon `us-west-2c` and returned `mode=check changed=0`; resource extraction tests passed. |  | All 16 source/payload pairs are byte-identical |
| AZ-007 | Regression gates | Update partition-contract tests and add per-AZ offering/capacity-accounting validation | SUCCESS | contract_test | Gate 5 | orchestrator | Initial focused suite: 104 passed. Broader suite initially found three incomplete synthetic fixtures; fixtures were corrected to provide the deliberately required 96-vCPU key rather than weakening production validation. Final full suite: `1508 passed, 11 skipped, 1 warning in 61.03s`; Ruff and `git diff --check` both passed. Final live-AWS generator check returned `mode=check changed=0`. |  | Regression coverage proves the new tier, exact queue sets, quota demand, required assets, and fail-closed config contract |
| AZ-008 | Release boundary | Commit and push only owned, validated changes to `sentieon-single`; do not create or move a release tag without an explicit version request | SUCCESS | legitimate_safety_handling | Gate 5 | orchestrator | Ownership-audited implementation commit `051a276d` (`Expand Intel AZ partition coverage`) pushed from `sentieon-single` to `origin/sentieon-single`; unrelated Slurm-accounting, CPU-policy, campaign, and live-run files remained unstaged. |  | Source release completed without creating or moving a tag |
| AZ-009 | Live boundary | Confirm no live-cluster configuration change was made | SUCCESS | legitimate_safety_handling | Gate 5 | orchestrator | Only local source, packaged payload, validation, and tests changed. No `pcluster update-cluster`, queue administration, job mutation, or AWS write occurred. HG002 independently advanced to 12/182 steps during the final checks. |  | The live cluster will not gain `i8` until a separately authorized update or replacement |
| AMD-001 | Plan amendment | Omit `i384nvme` in all five templates whose June snapshot has empty resources | NO_LONGER_NEEDED | plan_amendment | Gate 2 | orchestrator | A complete live 384-vCPU candidate query superseded the initial inference: `ap-south-1a/b` now offer two eligible `c8id` types, while only `ap-south-1c` and `us-west-1a/b` remain unsupported |  | Superseded before any template write; AMD-003 is the corrected exact-AZ action |
| AMD-002 | Plan amendment | Expand coverage to every active Intel cluster definition in DYEC | SUCCESS | plan_amendment | Gate 0 | orchestrator | `rg --files config/day_cluster` found exactly 15 active Intel AZ templates, all already in the Gate 0 inventory; separate `archive_do_not_use` YAMLs are explicitly non-active |  | Scope now explicitly covers the complete active Intel inventory, and packaged-resource requirements will enumerate all 15 |
| AMD-003 | Plan amendment | Populate newly AZ-offered `i384nvme` pools before checking Spot evidence | NO_LONGER_NEEDED | plan_amendment | Gate 2 | orchestrator | A stricter Linux Spot price-history audit found no Spot evidence for the newly AZ-offered `c8id.96xlarge,c8id.metal-96xl` in `ap-south-1a/b` |  | Superseded before commit by AMD-004; AZ offering alone is not sufficient for a `CapacityType: SPOT` queue |
| AMD-004 | Plan amendment | Require exact-AZ offering and current Linux Spot evidence for every newly generated 8/96/384 candidate | SUCCESS | plan_amendment | Gate 2 | orchestrator | Bounded current-price Spot audit excludes `c8id.24xlarge` in `ap-south-1a/b`, `m8idb.24xlarge,m8idn.24xlarge` in `us-east-2a/b/c`, and both 384-vCPU `c8id` candidates in `ap-south-1a/b`; sentieon `i8` has Spot evidence for all four types. Existing non-generated queue pools retain their prior Spot-vetted lists and separately pass current exact-AZ offering checks. |  | Generator intersects exact-AZ offerings with current Linux Spot evidence for refreshed tiers and omits all five originally empty 384 queues |

## Acceptance contract

- Every target template parses after explicit substitution.
- Every emitted instance type is offered in the exact template AZ.
- `sentieon-single/us-west-2c` contains `i8` plus the existing NVMe tiers.
- Every active Intel template contains `i96nvme,i128nvme,i192nvme` in addition
  to its general Intel queues. `i384nvme` is present only where the exact AZ
  has an eligible 384-vCPU local-NVMe Intel offering with current Linux Spot
  evidence; it is omitted otherwise.
- The 96-vCPU tier has explicit config, rendering, and quota accounting.
- All source/payload pairs are byte-identical.
- Missing configuration and empty offering intersections fail explicitly; no
  fallback partition, alias, or silent substitution is introduced.
- No live cluster or running workflow is changed by this work.

## Completion

All control-ledger rows are terminal and the source objective is complete.
Commit `051a276d` is the pushed implementation. Applying these future-cluster
templates to a live ParallelCluster remains a separate, explicitly approved
operation and was not performed here.
