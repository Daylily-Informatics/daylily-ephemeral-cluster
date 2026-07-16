# ifx-reworkB Spot Price Update Ledger

Created: 2026-07-08T21:23:28Z

## Objective

Update live ParallelCluster cluster `ifx-reworkB` in `us-west-2` so compute-resource
`SpotPrice` values are recomputed from the reference median spot price with
`--spot-cost-limit-pct 1.55`, preserving the existing global cap behavior and the
special i384-to-i192 reference-price rule. Also update the DYEC create default for
`--spot-cost-limit-pct` to `1.55` with the maximum allowed value set to `2.0`.

## Gate 0 Inventory

| Item | State |
| --- | --- |
| Repo | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` on `jem-dev`; dirty before this task in spot-pricing code/tests. |
| Existing dirty files | `daylily_ec/aws/spot_pricing.py`, `daylily_ec/cli.py`, `daylily_ec/resources/payload/bin/calcuate_spotprice_for_cluster_yaml.py`, `tests/test_cli_registry_v2.py`, `tests/test_spot_pricing.py`. |
| Cluster | `ifx-reworkB` in `us-west-2`: `clusterStatus=CREATE_COMPLETE`, stack `CREATE_COMPLETE`, compute fleet `RUNNING`, head node `i-059642d9ee4d5c9ea`. |
| Tool versions | `dyec --json version` -> `10.0.123.dev0+g80cd9b080.d20260708`; `pcluster version` -> `3.15.0`. |
| Read-only discovery | `pcluster get-cluster-configuration` is unavailable in installed ParallelCluster CLI; use the transient `describe-cluster` configuration URL without storing the presigned URL. |
| Mutation boundary | No cluster delete, resource teardown, Slurm job manipulation, or compute fleet stop is authorized by this ledger. |

## Execution Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SRC-001 | DYEC source | Set `DEFAULT_SPOT_COST_LIMIT_PCT` to `1.55` and keep `MAX_SPOT_COST_LIMIT_PCT` at `2.0`. | SUCCESS | feature_implementation | Gate 1 | Codex | `daylily_ec/aws/spot_pricing.py`; CLI/script help now prints exact `1.55` default. |  | Source updated. |
| SRC-002 | DYEC tests | Update focused pricing/CLI tests for the `1.55` default. | SUCCESS | contract_test | Gate 1 | Codex | `pytest tests/test_spot_pricing.py tests/test_cli_registry_v2.py -q` -> `169 passed`. |  | Focused tests pass. |
| CLU-001 | AWS cluster | Fetch current cluster config without preserving presigned URL. | SUCCESS | live_config_update | Gate 1 | Codex | Saved `docs/plans/20260708T212328Z_ifx_reworkB_spot_price_update/ifx-reworkB_current_cluster_config.yaml`; sanitized status evidence in `ifx-reworkB_describe_sanitized_after_block.json`. |  | Current config captured without storing the presigned URL. |
| CLU-002 | AWS cluster | Generate `1.55` SpotPrice config and before/after pricing table, with i384 rows using i192 reference medians. | SUCCESS | live_config_update | Gate 1 | Codex | Generated `ifx-reworkB_spot_1p55_summary.json`, `ifx-reworkB_spot_1p55_partition_table.md`, `ifx-reworkB_spot_1p55_resource_table.csv`, and candidate YAMLs. |  | Candidate table and YAML generated. |
| CLU-003 | AWS cluster | Validate live update with `pcluster update-cluster --dryrun true`. | SUCCESS | live_config_update | Gate 1 | Codex | Saved `ifx-reworkB_spotonly_update_dryrun.json`; dry-run message: `Request would have succeeded, but DryRun flag is set.` Change set has 15 `SpotPrice` changes and 8 `S3Access` removals. |  | Dry-run completed, but exposed an unapproved IAM delta. |
| CLU-004 | AWS cluster | Apply live `pcluster update-cluster` only if dry-run says the update is allowed without compute-fleet stop or unapproved destructive action. | BLOCKED | live_config_update | Gate 1 | Codex | Live update not run. Candidate dry-run still includes 8 removals of write-enabled duplicate `lsmc-ssf-sequencing-data` `S3Access` entries. | Unapproved IAM permission/config delta in ParallelCluster change set. | Needs explicit approval to apply the SpotPrice update together with the reported `S3Access` removals, or a different no-IAM-delta update path. |
| CLU-005 | AWS cluster | Verify cluster status/config after update and print final partition table. | BLOCKED | contract_test | Gate 5 | Codex | Cluster remains `CREATE_COMPLETE`, compute fleet `RUNNING`, stack `CREATE_COMPLETE`; see `ifx-reworkB_describe_sanitized_after_block.json`. | Live update blocked by CLU-004. | No post-update config verification was possible because the live update was not applied. |

## Final Status

All rows are terminal. Objective is not fully complete because the live cluster
update is blocked by an unapproved non-SpotPrice `S3Access` change in the
ParallelCluster dry-run change set.

## Partition Price Table

| partition | reference_partition_rule | initial_reference_median_maxprice | old_1p2_maxprice | live_config_spotprice_before | candidate_new_1p55_maxprice |
| --- | --- | --- | --- | --- | --- |
| i8 | i8 | 0.1904 | 0.2285 | 0.2285 | 0.2951 |
| i128 | i128 | 2.7986 | 3.3583 | 3.3583 | 4.3378 |
| i128nvme | i128nvme | 2.8995 | 3.4794 | 3.4794 | 4.4942 |
| i192 | i192 | 2.7002 | 3.2402 | 3.2402 | 4.1853 |
| i192nvme | i192nvme | 5.3994 | 6.4793 | 6.5141 | 8.3691 |
| i384nvme | i192nvme | 5.3994 | 6.4793 | 6.5141 | 8.3691 |
| i192hugenvme | i192hugenvme | 5.3994 | 6.4793 | 6.5141 | 8.3691 |
