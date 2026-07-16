# Intel Spot and On-Demand Template Split Ledger

Date: 2026-07-16

## Objective

Split every active AZ-scoped Intel ParallelCluster template into explicitly named
Spot and On-Demand families. Preserve Spot as the default `--cluster-type intel`
create path. On-Demand templates must use EC2 Fleet lowest-price allocation and
must not contain Spot-only bid settings or dynamic node priorities.

## Gate 0 inventory

- Active source tree: `config/day_cluster/intel/`
- Packaged mirror: `daylily_ec/resources/payload/config/day_cluster/intel/`
- Supported AZs: 15
- Starting templates: 15 source plus 15 packaged copies
- Existing requested edit in the starting worktree: all 285 source and 285
  packaged `DynamicNodePriority` settings were already removed.
- Unrelated dirty files and untracked runtime-cache artifacts existed before this
  split and must remain untouched.
- Current create behavior resolves `--cluster-type intel` to
  `prod_cluster_intel_<az>.yaml`; the split will intentionally change this exact
  path to `prod_cluster_intel_spot_<az>.yaml` without adding a legacy fallback.

## Contract

- Spot names: `prod_cluster_intel_spot_<az>.yaml`
- On-Demand names: `prod_cluster_intel_ondemand_<az>.yaml`
- Spot queues retain `CapacityType: SPOT`, the configured Spot allocation
  strategy, and rendered `SpotPrice` bid caps.
- On-Demand queues use `CapacityType: ONDEMAND` and explicit
  `AllocationStrategy: lowest-price`.
- On-Demand compute resources contain no `SpotPrice`.
- Neither family contains `DynamicNodePriority`.
- Both families exist in the source and packaged trees and remain byte-identical
  across those mirrors.
- Default Intel cluster creation continues to select Spot. On-Demand selection is
  explicit through `cluster_template_yaml`; no inferred or silent fallback is
  added.

## Execution ledger

| ID | Requirement | Status | Evidence / terminal note |
|---|---|---|---|
| I1 | Inventory paths, consumers, and dirty baseline | SUCCESS | Gate 0 above; repository-wide reference scan completed before edits. |
| I2 | Rename all Intel templates and consumers to explicit Spot names | SUCCESS | 15 source and 15 packaged templates renamed; active code/config/test scan has no old filename reference. Default Intel resolver now returns the Spot filename. |
| I3 | Derive all On-Demand templates with the exact capacity contract | SUCCESS | 15 source and 15 packaged variants use `ONDEMAND` plus `lowest-price` and omit every compute-resource `SpotPrice`. |
| I4 | Add regressions for both families and packaged parity | SUCCESS | Tests cover exact names/counts, purchase contract, no priorities, Spot-to-On-Demand structural derivation, package parity, extraction, and schema loading. |
| I5 | Validate YAML, renderer/resources, and focused tests | SUCCESS | 60 YAMLs parsed and contract-checked; Ruff passed; ParallelCluster 3.15.0 schema coverage passed; full suite: 1,583 passed, 11 skipped. |
| I6 | Confirm all rows terminal and objective complete | SUCCESS | All rows terminal; source/package counts and parity verified; no live AWS or cluster mutation performed. |

## Acceptance checks

- No active reference to `prod_cluster_intel_<az>.yaml` remains.
- Exactly 15 Spot and 15 On-Demand source templates exist, with matching packaged
  copies.
- All 60 Intel YAML files parse.
- Spot and On-Demand structural regression tests pass.
- Resource extraction and create-template resolution tests pass.
- `git diff --check` passes for this change set.

## Final evidence

- Source templates: 15 Spot plus 15 On-Demand.
- Packaged templates: 15 Spot plus 15 On-Demand.
- Source/package mirrors: byte-identical for all 30 relative paths.
- Active old-name references: zero.
- `DynamicNodePriority` in either Intel family: zero.
- On-Demand queue allocation: explicit `lowest-price`; no compute-resource
  `SpotPrice` fields.
- Focused regression after inventory adjustment: 37 passed.
- Full repository suite: 1,583 passed, 11 skipped, one third-party deprecation
  warning.
- Objective status: complete.
