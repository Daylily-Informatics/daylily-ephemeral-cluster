# AZ Cluster Template Autoselect Ledger

Created: 2026-07-08T10:00:58Z

## Objective

Add create-time cluster template autoselection by cluster type and exact region-AZ. `dyec create` will accept `--cluster-type [intel|rhel]`, default `intel`, and will select:

```text
config/day_cluster/<cluster-type>/<region>/<region-az>/prod_cluster_<cluster-type>_<region-az>.yaml
```

when `cluster_template_yaml` is not explicitly set in the config.

## Gate 0 Inventory

- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch: `jem-dev`
- Baseline status: branch at `origin/jem-dev`; untracked spot matrix artifacts under `docs/plans/20260708T094839Z_*` and `docs/plans/20260708T095022Z_*`.
- Current source templates:
  - Intel: `config/day_cluster/prod_cluster_nested_spot_mem_scratch_intel_avx512_expanded.yaml`
  - RHEL/DRAGEN: `config/day_cluster/prod_cluster_dragen_pcluster_image_rhel8.yaml`
- US-only spot matrix basis: `docs/plans/20260708T095022Z_us_only_intel_dragen_spot_az_matrix_long.csv`
- Scope decision: generate `us-west-2` AZ-scoped templates now. Intel gets `us-west-2a/b/c/d`; RHEL gets only viable `us-west-2b/c` files because `f2.6xlarge` has no spot history in `us-west-2a/d`.
- Live AWS actions: none. This is source/config/test work only.

## Tracking

| ID | Area | Requirement | Status | Category | Gate | Evidence | Terminal Note |
|---|---|---|---|---|---|---|---|
| AZCFG-001 | templates | Create source AZ-scoped Intel and RHEL template files under `config/day_cluster/<type>/<region>/<region-az>/`. | SUCCESS | config_or_startup_contract | Gate 1 | Added Intel `us-west-2a/b/c/d` templates and RHEL `us-west-2b/c` templates. `python` YAML inspection showed Intel `2a/2b/2c` have 64 types, Intel `2d` has 55 types, and RHEL `2b/2c` have `f2.6xlarge`. | Source AZ-scoped templates created. RHEL `2a/2d` intentionally absent because `f2.6xlarge` was not spot-present there. |
| AZCFG-002 | packaged resources | Mirror AZ-scoped template files into `daylily_ec/resources/payload/config/day_cluster/...`. | SUCCESS | config_or_startup_contract | Gate 1 | Added matching files under `daylily_ec/resources/payload/config/day_cluster/{intel,rhel}/...`; `cmp` loop reported `source-packaged-az-templates-match`. | Packaged mirrors match source files. |
| AZCFG-003 | create CLI | Add `--cluster-type [intel|rhel]`, default `intel`, and pass it to the create workflow. | SUCCESS | feature_implementation | Gate 1 | `daylily_ec/cli.py`; `dyec create --help` shows `--cluster-type`; CLI tests cover explicit `rhel`, default `intel`, and invalid `dragen`. | CLI option implemented and validated. |
| AZCFG-004 | template resolver | Autoselect the AZ-scoped template from `--cluster-type` and `--region-az` when config does not explicitly set `cluster_template_yaml`; fail hard when missing. | SUCCESS | feature_implementation | Gate 1 | `daylily_ec/workflow/create_cluster.py` adds `resolve_cluster_template_yaml`, exact AZ path construction, and missing-file hard failure. Tests cover derived path, explicit override, and missing RHEL `us-west-2d`. | Resolver implemented without silent fallback to generic templates. |
| AZCFG-005 | tests | Add focused tests for resolver paths, CLI pass-through, packaged mirrors, and AZ-specific pruning. | SUCCESS | contract_test | Gate 1 | Updated `tests/test_workflow.py`, `tests/test_cli_registry_v2.py`, and `tests/test_packaged_defaults.py`. | Focused coverage added. |
| AZCFG-006 | verification | Run focused local tests and YAML syntax checks. | SUCCESS | contract_test | Gate 5 | `pytest tests/test_workflow.py tests/test_cli_registry_v2.py tests/test_packaged_defaults.py tests/test_renderer.py -q` -> 281 passed. `python -m compileall -q daylily_ec/cli.py daylily_ec/workflow/create_cluster.py daylily_ec/resources/__init__.py` passed. YAML parse reported 12 AZ-scoped YAML files. | Verification complete. |

## Final State

All rows are terminal. No live AWS or Slurm actions were performed.

## 2026-07-08 Expansion

User requested additional AZ-scoped files for `ap-south-1*`, `eu-central-1*`, `us-west-1*`, and `us-east-2*`.

| ID | Area | Requirement | Status | Category | Gate | Evidence | Terminal Note |
|---|---|---|---|---|---|---|---|
| AZCFG-007 | templates | Generate source Intel templates for requested regions and RHEL templates where `f2.6xlarge` is spot-present. | SUCCESS | config_or_startup_contract | Gate 1 | Added Intel files for all requested AZs: `ap-south-1a/b/c`, `eu-central-1a/b/c`, `us-west-1a/b`, `us-east-2a/b/c`. Added RHEL files for `eu-central-1b/c`; no RHEL files for `ap-south-1*`, `us-west-1*`, or `us-east-2*` because `f2.6xlarge` was not spot-present there in `docs/plans/20260708T094839Z_intel_dragen_spot_az_matrix_long.csv`. | Requested regions generated with exact AZ-specific pruning. |
| AZCFG-008 | packaged resources | Mirror expanded AZ-scoped templates into packaged payload. | SUCCESS | config_or_startup_contract | Gate 1 | `find config/day_cluster/{intel,rhel}` shows 19 source templates; packaged payload has 19 matching files. `cmp` loop reported `source-packaged-az-templates-match`. | Packaged mirrors match source for all AZ-scoped files. |
| AZCFG-009 | tests | Update tests for expanded template set and viable RHEL AZ list. | SUCCESS | contract_test | Gate 1 | `tests/test_packaged_defaults.py` now discovers all source AZ-scoped templates and asserts 19 source files with matching packaged mirrors; RHEL viable AZs asserted as `eu-central-1b`, `eu-central-1c`, `us-west-2b`, `us-west-2c`. | Expanded template coverage is tested. |
| AZCFG-010 | verification | Re-run focused verification after expansion. | SUCCESS | contract_test | Gate 5 | Focused test subset -> 12 passed. `pytest tests/test_workflow.py tests/test_cli_registry_v2.py tests/test_packaged_defaults.py tests/test_renderer.py -q` -> 281 passed. YAML audit parsed 19 source and 19 packaged AZ-scoped templates with expected instance-type counts. | Expansion verification complete. |
