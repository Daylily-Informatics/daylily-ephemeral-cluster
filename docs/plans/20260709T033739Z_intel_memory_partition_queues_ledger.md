# 20260709T033739Z Intel Memory Partition Queues Ledger

## Gate 0 Inventory

- Objective: add current-format Intel Slurm queues named `i128mem`, `i128bigmem`, `i192mem`, and `i192bigmem` using the existing memory-tier compute-resource instance lists.
- Scope: local source/package config and tests only. No live ParallelCluster update, Slurm change, controller restart, or AWS mutation is included in this ledger.
- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch baseline: `jem-dev...origin/jem-dev`
- Working tree baseline: clean in this repo at start of this change.
- Active source template: `config/day_cluster/prod_cluster_nested_spot_mem_scratch_intel_avx512_expanded.yaml`
- Packaged mirror: `daylily_ec/resources/payload/config/day_cluster/prod_cluster_nested_spot_mem_scratch_intel_avx512_expanded.yaml`
- AZ-scoped Intel templates: `config/day_cluster/intel/*/*/prod_cluster_intel_*.yaml` plus packaged mirrors.
- Contract change: `tests/test_packaged_defaults.py` currently excludes `i192mem` and `i192bigmem`; this is now stale. The test contract should allow and verify the new queues.
- Current config evidence: `i128` contains `mem128` and `bigmem128`; `i192` contains `mem192` and `bigmem192`.
- Prior-style naming evidence: old local Daylily configs used `i192mem` and `i192bigmem`; no stale old YAML blocks are copied.

## Execution Rows

| Row | Work | State | Evidence |
| --- | --- | --- | --- |
| 1 | Add ledger and baseline scope | complete | This file |
| 2 | Patch active and AZ-scoped Intel source templates | complete | Added `i128mem`, `i128bigmem`, `i192mem`, and `i192bigmem` after their parent CPU-count queues |
| 3 | Sync packaged payload mirrors | complete | Source/package mirror equality verified for active and AZ-scoped Intel templates |
| 4 | Update packaged-defaults contract test | complete | Test now asserts the four alias queues exist and match parent memory resources |
| 5 | Run focused tests | complete | `source ./activate && pytest tests/test_packaged_defaults.py -q` passed: 16 passed |
| 6 | Report live-update boundary | complete | No live cluster mutation performed; applying to `ifx-reworkB` still requires a rendered config update workflow |

## Verification

- Parsed the active Intel template and representative AZ-pruned templates after patching.
- Verified every Intel source template has:
  - `i128mem` with exactly the `i128` / `mem128` compute resource.
  - `i128bigmem` with exactly the `i128` / `bigmem128` compute resource.
  - `i192mem` with exactly the `i192` / `mem192` compute resource.
  - `i192bigmem` with exactly the `i192` / `bigmem192` compute resource.
- Verified all alias queues are non-NVMe queues and do not carry `ComputeSettings`.
- Verified packaged payload mirrors match source templates for all patched Intel templates.

