## Control Ledger

Controlling request: remove generic Intel cluster template contract; use AZ-scoped Intel templates for `us-west-2a`, `us-west-2b`, `us-west-2c`, and `us-west-2d`, with maximal instance lists per AZ and partition group goals.

Ledger path: `docs/plans/20260710T012212Z_intel_az_template_contract_ledger.md`

Gate 0 baseline:
- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch/status: `jem-dev...origin/jem-dev`; only pre-existing untracked command-catalog run ledger/log artifacts under `docs/plans/20260710T002740Z_*`.
- Existing source Intel AZ templates: `config/day_cluster/intel/us-west-2/us-west-2{a,b,c,d}/prod_cluster_intel_us-west-2{a,b,c,d}.yaml`.
- Existing packaged Intel AZ templates: `daylily_ec/resources/payload/config/day_cluster/intel/us-west-2/us-west-2{a,b,c,d}/prod_cluster_intel_us-west-2{a,b,c,d}.yaml`.
- Active generic references found by `rg prod_cluster_nested_spot_mem_scratch_intel_avx512_expanded config daylily_ec tests`: packaged config defaults, resource validation, pricing helpers, tests, and the old generic source/payload YAML.
- Baseline live-offerings audit using AWS profile `lsmc`, region `us-west-2`, showed missing offered modern Intel instance types in all four AZ-specific templates under the queue vCPU/memory/NVMe contract.

## Rows

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| AZ-001 | Cluster templates | Delete the generic Intel cluster template as an active defined template in source and packaged payload. | SUCCESS | config_or_startup_contract | Gate 1 | codex | Deleted `config/day_cluster/prod_cluster_nested_spot_mem_scratch_intel_avx512_expanded.yaml` and packaged payload copy; existence check reports both false. |  | Generic Intel defined template removed from active source and payload. |
| AZ-002 | Cluster templates | Maximize `intel/us-west-2/us-west-2{a,b,c,d}` instance lists to live AZ offerings while preserving queue vCPU, memory, and NVMe-local-storage goals. | SUCCESS | feature_implementation | Gate 1 | codex | Live EC2 audit with profile `lsmc`, region `us-west-2`: `us-west-2a/b/c` each 19 compute resources, 94 unique instance types, audit ok; `us-west-2d` 19 compute resources, 72 unique instance types, audit ok. |  | All four AZ templates match current offered modern Intel instance types for their compute resource vCPU, memory, and local-NVMe contracts. |
| AZ-003 | Runtime defaults | Ensure create/validation/pricing/resource defaults do not point at the removed generic Intel template; unset create config should use exact AZ template and fail hard if missing. | SUCCESS | config_or_startup_contract | Gate 2 | codex | Patched create config triplets to unset `cluster_template_yaml`; patched validation to use `az_cluster_template_relative_path(DEFAULT_CREATE_CLUSTER_TYPE, aws_ctx.region_az)` when unset; pricing/helpers use concrete `intel/us-west-2/us-west-2d` template. |  | Generic default path removed; create/validation select exact AZ template or honor explicit set value. |
| AZ-004 | Packaged payload | Keep packaged resource payload in byte sync with source config/templates and require all four Intel `us-west-2` AZ templates. | SUCCESS | contract_test | Gate 2 | codex | `daylily_ec/resources/__init__.py` requires four Intel `us-west-2` AZ templates; byte-sync check printed `source/payload Intel us-west-2 templates match`. |  | Packaged resource contract now enumerates all four Intel AZ templates. |
| AZ-005 | Tests | Update tests so the active contract is AZ-scoped Intel templates, not the old generic template. | SUCCESS | contract_test | Gate 5 | codex | Updated `tests/test_packaged_defaults.py`, `tests/test_resources_extraction.py`, `tests/test_renderer.py`, and `tests/test_aws_validation.py`. |  | Tests assert AZ-scoped templates, source/payload sync, validation AZ selection, and generic non-existence. |
| AZ-006 | Verification | Run focused pytest, `git diff --check`, no-generic-reference sweep, and a live AWS offerings audit. | SUCCESS | contract_test | Gate 5 | codex | `pytest -q tests/test_packaged_defaults.py tests/test_resources_extraction.py tests/test_renderer.py tests/test_aws_validation.py tests/test_workflow.py::TestAzClusterTemplateResolution tests/test_cluster_request_config.py tests/test_pricing_snapshots.py` -> 83 passed; `pytest -q tests/test_cli_registry_v2.py::test_pricing_snapshot_command_passes_collection_options` -> 1 passed; `git diff --check` -> clean; active `rg` finds generic name only in negative tests. |  | Verification complete. |

## Final Status

- Ledger rows: 6 `SUCCESS`, 0 open.
- Objective complete: yes.
